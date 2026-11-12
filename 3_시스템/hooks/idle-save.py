# -*- coding: utf-8 -*-
"""세이브포인트 감시 (Stop 훅 · asyncRewake · 결정론층).

왜 있나 — 실측(2026-09-24, 최근 30일 131 세션):
  · 유휴 65분 초과 뒤 첫 요청의 86%(51/59)가 캐시를 통째로 다시 썼다 · 1,565만 토큰 · 97% 데스크탑.
  · 5시간 한도(«session limit») 도달이 여러 번 있었다 — 걸리면 그 턴은 끝나고, 리셋 뒤 재개는 재작성이다.
  · 그런데 지금의 session-record 1회는 컨텍스트 40~65만 세션에서 가중 51만~267만(창의 4~22%)이라
    «유휴 때 자동 기록»은 재작성(창의 ≈5%)만큼 비싸다. 그래서 무거운 기록 대신
    **Write 1회짜리 세이브포인트**(요청 2~3회 · 창의 1~2%)만 남기게 한다.
  · 유휴 55분+ 뒤 같은 세션으로 돌아온 비율 0.26~0.51 > 손익분기 0.18~0.28(컨텍스트 구간별).
  · 11-13 재측정(10-04~11-13 깨움 106건): 같은 세션 복귀 0.15 — 가치는 «캐시»보다 «세션종료 못 한 세션의
    기록·이어가기 재료»다. 깨움의 28%는 이미 기록을 마친 세션, 16%는 다른 세션이 띄운 하위 세션이었다(③).

무엇을 하나 — 매 턴 끝(Stop)에 뒤에서 뜬다(asyncRewake: 종료코드 2 = 유휴 세션도 깨운다).
  ① 5시간 사용률 ≥ USAGE_PCT(상태줄이 준 값) → 즉시 깨워 세이브포인트(창마다 1회).
  ② 사람 입력 없이 IDLE_MIN 분(캐시 만료 시각을 알면 만료 SAFETY_MIN 분 전) → 깨워 세이브포인트
     (같은 사람 입력에 대해 1회). 그 사이 새 활동이 있으면 조용히 빠진다 — 다음 Stop 이 새로 띄운다.
  ③ 거름(11-13): 다른 세션이 띄웠고 사람 입력이 없는 세션은 처음부터 안 본다(상태는 띄운 쪽이 든다 ·
     ADR-051 결정 7 을 빅보스 밖으로). 기한이 되면 깨우기 **직전에** session-stub 상태를 읽어, 기록
     (session-record·세션노트·recent·open-loops)을 마쳤고 그 뒤 일·새 입력이 없으면 깨우지 않는다 — 기다리는
     사이 다른 세션이 대신 기록할 수도 있어 기다리기 전이 아니라 뒤에 잰다.
  ④ 진단(11-13): 10-14~11-13 발동 172건 중 83건은 대화에 아무것도 붙지 않았다(대화 마지막 줄이 꼭 50분 전).
     세션은 내려가고 감시만 남은 것으로 보이나 미확인이다 — 깨우기 직전에 이 창의 Claude 프로세스
     (CLAUDE_PID + 세션 파일의 procStart)를 재서, 죽었으면 깨우지 않고 로그에 `skip dead-parent` 를 남긴다.
⛔ 한계(09-24 실측, 데스크탑 30일): 앱이 유휴 세션 프로세스를 내렸다 올리면(SessionStart:resume —
  15~60분 간격의 18%, 60분+ 의 38%) 이 감시도 함께 죽는다(taskkill /T · incident-2026-09-04).
  그리고 재기동 뒤 첫 요청은 **60분 안이어도 90%(28/31)가 전량 재작성**이다 — TTL 이 아니라 재기동이
  캐시를 깬다. 이 경우는 여기서 못 막는다. 사용률 트리거(①)는 턴 끝에 즉시 판정하므로 영향 없다.
⛔ `/clear` 는 프로세스를 두고 세션만 바꾼다(11-03 재현) — 감시는 살아남고, 옛 대화 파일이 더 안 자라니 «유휴»로 본다.
  그대로 깨우면 지금 세션에 옛 세션 id 로 쓰라는 지시가 간다. 그래서 기다리는 동안 이 창의 지금 세션을 견준다.
경계: 판정만 한다. 쓰는 것은 Claude 다(맥락은 Claude 에게만 있다).
계약: 조건 미충족·예외 = 종료코드 0(fail-open). 깨울 때만 stderr + 종료코드 2.
  거름(③④)은 모르면 깨운다 — 상태 파일·세션 파일이 없거나 깨지면 종전대로.
"""
import json, os, re, sys, time

VAULT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
IDX = os.path.join(VAULT, "3_시스템", "_index")
IDLE_MIN = 50          # 캐시 TTL 1시간 − 여유 10분
SAFETY_MIN = 8         # 만료 시각을 알 때 그보다 이만큼 먼저 깨운다
MIN_CTX = 100_000      # 이 미만은 재작성 손실이 작다(100K 미만 손실 0 · 캐시-재작성-손실-전수실측)
USAGE_PCT = 80         # 한 턴이 창의 5~15%를 쓰기도 한다(09-24 이 세션 7%) — 여유를 둔다
USAGE_FRESH_S = 900    # 상태줄 값이 이보다 오래됐으면 믿지 않는다
POLL_S = 30
TAIL = 1_500_000       # 트랜스크립트 끝에서 이만큼만 읽는다(수십 MB 세션 대비)
HEAD = 300_000         # 첫 메시지(하위 세션 머리)를 찾을 때 앞에서 이만큼만 읽는다
BIGBOSS_FRESH_S = 3 * 3600  # 빅보스 감시기는 바퀴(2분)마다 state.json 을 쓴다 — 이보다 오래되면 끝난 run
RECORD_TAIL_S = 600    # 기록 뒤 이만큼 안의 편집은 기록의 일부(MOC 줄·마무리 손질)로 본다
# 앱이 붙이는 머리(11-13 실측): 하위 세션 첫 메시지 · 다른 세션이 보낸 말 · 사람 입력 앞의 «Linked sessions» 알림(81건)
BRIEF = "Background (from the session that started this one)"
PEER = "Another Claude session sent a message"
REMINDER_RX = re.compile(r"^(?:\s*<system-reminder>.*?</system-reminder>)+", re.S)
STUBS_REL = "3_시스템/_index/stubs/"   # 세이브포인트 자리 — 이 쓰기는 일도 기록도 아니다


def bigboss_sub(sid):
    """돌고 있는 빅보스 run 의 하위 세션인가(ADR-051 · 11-13 사용자 승인).
    하위 세션의 상태는 보스가 들고 있다(작업 노트·넘김 글) — 세이브포인트는 맥락 전체로 턴 하나를 더 쓸 뿐이다.
    quad-1111(11-12): 하위 넷에서 4번 · 맥락 468K 까지. 보스 세션은 로스터에 없으니 종전대로 저장한다.
    읽기만 한다 · 모듈이 없거나 못 읽으면 아니다(= 종전대로 저장)."""
    import glob
    now = time.time()
    for p in glob.glob(os.path.join(IDX, "bigboss", "*", "state.json")):
        try:                                          # 한 run 파일이 깨져도 다른 run 은 본다
            if now - os.path.getmtime(p) > BIGBOSS_FRESH_S:
                continue
            with open(p, encoding="utf-8") as fh:
                known = json.load(fh).get("known") or {}
            if any(isinstance(v, dict) and v.get("cli") == sid for v in known.values()):
                return True
        except Exception:
            continue
    return False


def log(short, msg):
    """판정 흔적(10-03 계측). 시작 줄만 있고 끝 줄이 없으면 = 프로세스가 중간에 죽었다."""
    try:
        with open(os.path.join(IDX, "hooks.log"), "a", encoding="utf-8", newline="") as fh:
            fh.write("{} idle-save {} {}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), short, msg))
    except Exception:
        pass


def epoch(iso):
    try:
        import datetime as dt
        return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def body(d):
    """user 줄의 글(앞에 붙은 system-reminder 는 뗀다)."""
    c = (d.get("message") or {}).get("content")
    t = c if isinstance(c, str) else "".join(
        x.get("text", "") for x in (c or []) if isinstance(x, dict) and x.get("type") == "text")
    return REMINDER_RX.sub("", t).lstrip()


def human_text(d):
    """사람이 친 입력이면 그 글, 아니면 ''. 다른 세션이 보낸 말·하위 세션 지시문·작업 알림·깨움은 사람 입력이 아니다.
    앱은 연결 세션이 있으면 사람 입력 앞에 system-reminder 를 붙인다 — 떼고 본다(11-13 실측 81건이 «<» 로 시작)."""
    if d.get("type") != "user" or not d.get("promptId") or d.get("isMeta") or d.get("isSidechain"):
        return ""
    if (d.get("origin") or {}).get("kind") not in (None, "human"):
        return ""
    t = body(d)
    if not t or t.startswith("<") or t.startswith(BRIEF) or t.startswith(PEER):
        return ""
    return t


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


def session_file(pid):
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(home, "sessions", pid + ".json")


def current_session():
    """이 창(CLAUDE_PID)의 지금 세션 id · 모르면 None. 앱 내부 파일이라(문서에 없음) 판이 바뀌면 못 읽을 수 있다."""
    pid = os.environ.get("CLAUDE_PID")
    if not pid:
        return None
    try:
        with open(session_file(pid), encoding="utf-8") as fh:
            return json.load(fh).get("sessionId") or None
    except Exception:
        return None


def parent_alive():
    """이 창의 Claude 프로세스가 살아 있나 — True / False / 모르면 None.
    procStart(세션 파일) = 프로세스 생성 시각 FILETIME 이다(11-13 실측: 살아 있는 9개 모두 차이 0) —
    같은 PID 를 다른 프로세스가 물려받았는지 이것으로 가린다. 끝난 프로세스도 핸들은 열릴 수 있어 종료 코드를 본다."""
    pid = os.environ.get("CLAUDE_PID")
    if not pid or not pid.isdigit():
        return None
    start = None
    try:
        with open(session_file(pid), encoding="utf-8") as fh:
            start = json.load(fh).get("procStart")
    except Exception:
        pass
    try:
        if os.name != "nt":
            os.kill(int(pid), 0)
            return True
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.OpenProcess.restype = wintypes.HANDLE
        h = k.OpenProcess(0x1000, False, int(pid))    # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False if ctypes.get_last_error() == 87 else None   # 87 = 그런 PID 없음 · 그 밖(권한 등)은 모름
        try:
            code = wintypes.DWORD()
            if not k.GetExitCodeProcess(h, ctypes.byref(code)):
                return None
            if code.value != 259:                     # STILL_ACTIVE
                return False
            if str(start or "").isdigit() and int(start) > 10 ** 17:   # FILETIME 꼴일 때만 — 앱이 꼴을 바꾸면 견주지 않는다(죽었다고 잘못 보지 않게)
                ft = [wintypes.FILETIME() for _ in range(4)]
                if k.GetProcessTimes(h, *[ctypes.byref(f) for f in ft]):
                    made = (ft[0].dwHighDateTime << 32) | ft[0].dwLowDateTime
                    if made != int(start):
                        return False                  # PID 를 다른 프로세스가 물려받음
            return True
        finally:
            k.CloseHandle(h)
    except ProcessLookupError:
        return False
    except Exception:
        return None


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
        elif human_text(d):
            human = epoch(d.get("timestamp") or "") or human
    return human, ctx


def spawned_child(path):
    """다른 세션이 띄웠고(첫 메시지가 앱의 하위 세션 머리) 사람 입력이 한 번도 없는 세션인가.
    10-04~11-13 깨움 106건 중 17건 — 그 상태는 띄운 세션(보스·부모)이 들고 있다. 사람이 그 창에 말을 걸었으면 아니다."""
    with open(path, "rb") as fh:
        head = fh.read(HEAD).decode("utf-8", "replace")
    first = None
    for ln in head.splitlines():
        if '"type":"user"' not in ln:
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("type") == "user" and not d.get("isSidechain") and body(d):
            first = d
            break
    if first is None or not body(first).startswith(BRIEF):
        return False
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln in fh:
            if '"promptId"' in ln and '"type":"user"' in ln:
                try:
                    if human_text(json.loads(ln)):
                        return False
                except Exception:
                    continue
    return True


def sessions_prefix():
    """세션노트 자리(역할 «sessions») · 모르면 None — 그때는 recent·open-loops 표지만 본다."""
    try:
        sys.path.insert(0, os.path.join(VAULT, "3_시스템"))
        import roles
        return roles.path("sessions").rstrip("/") + "/"
    except Exception:
        return None


def recorded_after(ev, since, sess=None):
    """세션종료(기록)를 마쳤고 그 뒤 일이 없나 — session-stub 상태 이벤트로 판정한다.
    기록 표지 = session-record 스킬 호출 또는 세션노트(sessions 자리)·recent.md·open-loops.md 쓰기
    (session-stub 의 기록 판정 scan_pending 과 같은 쓰기 표지 + 스킬 — 기록 «생략»으로 끝낸 세션종료도 세션종료다).
    마지막 기록 RECORD_TAIL_S 뒤에 편집(세이브포인트 제외)이 있거나 사람 입력(since)이 있으면 기록 뒤 일을 이어간 것이다
    (무인 진행 85% 기록 → 98%). 기록 직후의 «세션종료» 되풀이·MOC 손질은 기록의 일부로 본다(11-13 재판정)."""
    rec = None
    for e in ev:
        if len(e) < 3:
            continue
        t = epoch(e[0] or "")
        if t is None:
            continue
        k, p = e[1], e[2]
        if (k == "스킬" and p == "session-record") or (k in ("신규", "수정") and (
                (sess and p.startswith(sess)) or p.endswith("recent.md") or p.endswith("open-loops.md"))):
            rec = t
        elif k in ("신규", "수정") and rec is not None and not p.startswith(STUBS_REL) and t > rec + RECORD_TAIL_S:
            rec = None                                # 기록 뒤 일을 이어감 — 다음 기록이 다시 세운다
    return rec is not None and since <= rec + RECORD_TAIL_S


def recorded(short, since):
    """True = 기록을 마친 세션 · False = 아님 · None = 상태를 못 읽음(= 종전대로 깨움)."""
    try:
        with open(os.path.join(IDX, "stubs", ".state-" + short + ".json"), encoding="utf-8") as fh:
            ev = json.load(fh).get("ev") or []
    except Exception:
        return None
    return recorded_after(ev, since, sessions_prefix())


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
        if bigboss_sub(sid):
            log(short, "skip bigboss-sub")
            return 0                                  # 빅보스 하위 세션 — 사용률·유휴 둘 다 안 깨운다
        try:
            child = spawned_child(path)
        except Exception:
            child = False                             # 모르면 종전대로
        if child:
            log(short, "skip child")
            return 0                                  # 다른 세션이 띄운 세션 — 사용률·유휴 둘 다 안 깨운다
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
        log(short, "watch ctx={}K wait={:.0f}m{}".format(ctx // 1000, (deadline - start) / 60,
                                                         "" if current_session() else " session?"))
        while time.time() < deadline:
            time.sleep(min(POLL_S, max(1, deadline - time.time())))
            cur = current_session()                   # 모르면 종전대로 — 기능이 조용히 죽는 쪽이 더 나쁘다
            if cur and cur != sid:
                log(short, "exit session-changed {}".format(cur[:8]))
                return 0                              # /clear — 이 세션은 더 안 이어진다
            if os.path.getsize(path) != size:         # 크기는 싼 1차 거름 — 판정은 user/assistant 줄로
                size = os.path.getsize(path)
                if last_activity(path) != act:
                    log(short, "exit activity {:.0f}m".format((time.time() - start) / 60))
                    return 0                          # 새 활동 — 다음 Stop 이 새 감시를 띄운다
        idle = (time.time() - start) / 60
        # ③ 깨우기 직전 거름 — 기다리는 사이 이 세션이나 다른 세션이 기록했을 수 있다
        if recorded(short, human):
            log(short, "skip recorded {:.0f}m".format(idle))
            return 0
        # ④ 이 창의 Claude 가 이미 내려갔으면 깨워도 닿지 않는다
        alive = parent_alive()
        open(g, "w", encoding="utf-8").write(str(human))
        if alive is False:
            log(short, "skip dead-parent {:.0f}m".format(idle))
            return 0
        log(short, "fire idle {:.0f}m{}".format(idle, " pid?" if alive is None else ""))
        sys.stderr.write(instruction(short, "유휴 {:.0f}분 · 컨텍스트 {:.0f}K — 캐시가 곧 식는다. 식은 뒤 이 세션을 "
                         "이어가면 전량 재작성(가중 ≈{:.0f}K)이다.".format(idle, ctx / 1000, 2 * ctx / 1000)))
        return 2
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
