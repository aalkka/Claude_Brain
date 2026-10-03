# -*- coding: utf-8 -*-
"""세이브포인트 감시 (Stop 훅 · asyncRewake · 결정론층).

왜 있나 — 실측(2026-09-24, 최근 30일 131 세션):
  · 유휴 65분 초과 뒤 첫 요청의 86%(51/59)가 캐시를 통째로 다시 썼다 · 1,565만 토큰 · 97% 데스크탑.
  · 5시간 한도(«session limit») 도달이 여러 번 있었다 — 걸리면 그 턴은 끝나고, 리셋 뒤 재개는 재작성이다.
  · 그런데 지금의 session-record 1회는 컨텍스트 40~65만 세션에서 가중 51만~267만(창의 4~22%)이라
    «유휴 때 자동 기록»은 재작성(창의 ≈5%)만큼 비싸다. 그래서 무거운 기록 대신
    **Write 1회짜리 세이브포인트**(요청 2~3회 · 창의 1~2%)만 남기게 한다.
  · 유휴 55분+ 뒤 같은 세션으로 돌아온 비율 0.26~0.51 > 손익분기 0.18~0.28(컨텍스트 구간별).

무엇을 하나 — 매 턴 끝(Stop)에 뒤에서 뜬다(asyncRewake: 종료코드 2 = 유휴 세션도 깨운다).
  ① 5시간 사용률 ≥ USAGE_PCT(상태줄이 준 값) → 즉시 깨워 세이브포인트(창마다 1회).
  ② 사람 입력 없이 IDLE_MIN 분(캐시 만료 시각을 알면 만료 SAFETY_MIN 분 전) → 깨워 세이브포인트
     (같은 사람 입력에 대해 1회). 그 사이 새 활동이 있으면 조용히 빠진다 — 다음 Stop 이 새로 띄운다.
⛔ 한계(09-24 실측, 데스크탑 30일): 앱이 유휴 세션 프로세스를 내렸다 올리면(SessionStart:resume —
  15~60분 간격의 18%, 60분+ 의 38%) 이 감시도 함께 죽는다(프로세스 트리째 종료된다).
  그리고 재기동 뒤 첫 요청은 **60분 안이어도 90%(28/31)가 전량 재작성**이다 — TTL 이 아니라 재기동이
  캐시를 깬다. 이 경우는 여기서 못 막는다. 사용률 트리거(①)는 턴 끝에 즉시 판정하므로 영향 없다.
경계: 판정만 한다. 쓰는 것은 Claude 다(맥락은 Claude 에게만 있다).
계약: 조건 미충족·예외 = 종료코드 0(fail-open). 깨울 때만 stderr + 종료코드 2.
"""
import json, os, sys, time

VAULT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
IDX = os.path.join(VAULT, "3_시스템", "_index")
IDLE_MIN = 50          # 캐시 TTL 1시간 − 여유 10분
SAFETY_MIN = 8         # 만료 시각을 알 때 그보다 이만큼 먼저 깨운다
MIN_CTX = 100_000      # 이 미만은 재작성 손실이 작다(제작자 볼트 실측: 100K 미만 손실 0)
USAGE_PCT = 80         # 한 턴이 창의 5~15%를 쓰기도 한다(09-24 이 세션 7%) — 여유를 둔다
USAGE_FRESH_S = 900    # 상태줄 값이 이보다 오래됐으면 믿지 않는다
POLL_S = 30
TAIL = 1_500_000       # 트랜스크립트 끝에서 이만큼만 읽는다(수십 MB 세션 대비)


def log(short, msg):
    """판정 흔적(10-03 계측). 시작 줄만 있고 끝 줄이 없으면 = 프로세스가 중간에 죽었다."""
    try:
        with open(os.path.join(IDX, "hooks.log"), "a", encoding="utf-8", newline="") as fh:
            fh.write("{} idle-save {} {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), short, msg))
    except Exception:
        pass


def last_activity(path):
    """마지막 user/assistant 줄 시각(ISO 문자열). 턴 끝에 앱이 덧붙이는 메타 줄
    (stop_hook_summary·custom-title·last-prompt …)은 활동이 아니다 — 파일 크기로 재면
    감시가 첫 확인에서 늘 빠진다(10-03 실측: 유휴 3건 모두 이 줄이 낌 · 세이브포인트 0)."""
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        fh.seek(max(0, size - 200_000))
        raw = fh.read().decode("utf-8", "replace")
    last = ""
    for ln in raw.splitlines():
        if '"type":"user"' in ln or '"type":"assistant"' in ln:
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("type") in ("user", "assistant") and not d.get("isSidechain"):
                last = max(last, d.get("timestamp") or "")
    return last


def tail_facts(path):
    """끝부분에서 (마지막 사람 입력 시각, 마지막 요청 컨텍스트)."""
    size = os.path.getsize(path)
    with open(path, "rb") as fh:
        fh.seek(max(0, size - TAIL))
        raw = fh.read().decode("utf-8", "replace")
    human, ctx = 0.0, 0
    for ln in raw.splitlines():
        if '"type":"user"' not in ln and '"type":"assistant"' not in ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("isSidechain"):
            continue
        if d.get("type") == "assistant":
            u = (d.get("message") or {}).get("usage") or {}
            c = sum((u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                               "cache_read_input_tokens"))
            if c:
                ctx = c
        elif d.get("promptId") and not d.get("isMeta"):
            c = (d.get("message") or {}).get("content")
            txt = c if isinstance(c, str) else "".join(
                x.get("text", "") for x in (c or []) if isinstance(x, dict) and x.get("type") == "text")
            if txt and not txt.lstrip().startswith("<"):
                try:
                    import datetime as dt
                    human = dt.datetime.fromisoformat(d["timestamp"].replace("Z", "+00:00")).timestamp()
                except Exception:
                    pass
    return human, ctx


def usage(short):
    """(5시간 사용률 %, 리셋 epoch, 이 세션 캐시 만료 epoch, ttl) — 없으면 None."""
    udir = os.path.join(IDX, "usage")
    if not os.path.isdir(udir):
        return None, None, None, None
    now = time.time()
    pct = reset = exp = ttl = None
    newest = 0
    for f in os.listdir(udir):
        if not f.endswith(".json"):
            continue
        try:
            r = json.load(open(os.path.join(udir, f), encoding="utf-8"))
        except Exception:
            continue
        if now - (r.get("ts") or 0) > USAGE_FRESH_S:
            continue
        fh5 = r.get("five_hour") or {}
        if fh5.get("used_percentage") is not None and r["ts"] > newest:   # 사용률은 계정 단위
            newest, pct, reset = r["ts"], fh5["used_percentage"], fh5.get("resets_at")
        if f.startswith(short):
            pc = r.get("prompt_cache") or {}
            exp, ttl = pc.get("expires_at"), pc.get("ttl")
    return pct, reset, exp, ttl


def instruction(short, why):
    save = "3_시스템/_index/stubs/{}.save.md".format(short)
    return (
        "[idle-save] {why}\n"
        "지금 세이브포인트를 남겨라 — 캐시가 살아 있는 동안이라 싸다.\n"
        "① **Write 1회**로 `{save}` 를 쓴다(있으면 통째로 새로 쓴다 · 60줄 이하). "
        "파일 읽기·검색·다른 도구 호출 금지 — 이미 컨텍스트에 있는 것만 쓴다.\n"
        "   형식: `# 세이브포인트 {short} (<KST 시각>)` · `## 목표` · `## 결정과 이유` · `## 기각한 것` · "
        "`## 현재 상태`(수정 파일·커밋·미커밋) · `## 다음 행동` · `## 열린 질문`.\n"
        "② 본문 한 줄로 끝낸다: «세이브포인트 저장({short}). 오래 비우면 새 세션에서 "
        "'이어가기 {short}' 가 이 세션을 이어가는 것보다 쌉니다.»\n"
        "사용자가 방금 말을 걸어 둔 게 아니라면 다른 작업을 시작하지 않는다."
    ).format(why=why, save=save, short=short)


def main():
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    try:
        if os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0":
            return 0                                  # 무인 실행은 깨우지 않는다
        hin = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        sid, path = hin.get("session_id") or "", hin.get("transcript_path") or ""
        if not sid or not os.path.exists(path):
            return 0
        short = sid[:8]
        stubs = os.path.join(IDX, "stubs")
        os.makedirs(stubs, exist_ok=True)
        save = os.path.join(stubs, short + ".save.md")
        human, ctx = tail_facts(path)
        pct, reset, exp, ttl = usage(short)

        # ① 사용률 — 창(리셋 시각)마다 1회
        if pct is not None and pct >= USAGE_PCT:
            g = os.path.join(stubs, ".usage-fired-" + short)
            key = str(reset)
            if not (os.path.exists(g) and open(g, encoding="utf-8").read() == key):
                open(g, "w", encoding="utf-8").write(key)
                log(short, "fire usage {:.0f}%".format(pct))
                sys.stderr.write(instruction(short, "5시간 사용량 {:.0f}% — 한도에 걸리면 이 턴이 끊기고, "
                                 "리셋 뒤 재개는 캐시 재작성(컨텍스트 {:.0f}K)이다.".format(pct, ctx / 1000)))
                return 2

        # ② 유휴
        if ctx < MIN_CTX or ttl == "5m":
            return 0                                  # 손실이 작거나, 5분 TTL 이면 매 휴식마다 깨게 된다
        if os.path.exists(save) and os.path.getmtime(save) > human:
            return 0                                  # 마지막 사람 입력 이후 이미 저장됨
        g = os.path.join(stubs, ".idle-fired-" + short)
        if os.path.exists(g) and open(g, encoding="utf-8").read() == str(human):
            return 0                                  # 이 입력에 대해 이미 한 번 깨웠다(무시당했어도 반복 안 함)
        start = time.time()
        deadline = start + IDLE_MIN * 60
        if exp and exp - SAFETY_MIN * 60 > start:
            deadline = min(deadline, exp - SAFETY_MIN * 60)
        act = last_activity(path)
        size = os.path.getsize(path)
        log(short, "watch ctx={}K wait={:.0f}m".format(ctx // 1000, (deadline - start) / 60))
        while time.time() < deadline:
            time.sleep(min(POLL_S, max(1, deadline - time.time())))
            if os.path.getsize(path) != size:         # 크기는 싼 1차 거름 — 판정은 user/assistant 줄로
                size = os.path.getsize(path)
                if last_activity(path) != act:
                    log(short, "exit activity {:.0f}m".format((time.time() - start) / 60))
                    return 0                          # 새 활동 — 다음 Stop 이 새 감시를 띄운다
        open(g, "w", encoding="utf-8").write(str(human))
        idle = (time.time() - start) / 60
        log(short, "fire idle {:.0f}m".format(idle))
        sys.stderr.write(instruction(short, "유휴 {:.0f}분 · 컨텍스트 {:.0f}K — 캐시가 곧 식는다. 식은 뒤 이 세션을 "
                         "이어가면 전량 재작성(가중 ≈{:.0f}K)이다.".format(idle, ctx / 1000, 2 * ctx / 1000)))
        return 2
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
