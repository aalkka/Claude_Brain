# -*- coding: utf-8 -*-
"""상태줄 = 사용률·캐시 상태의 **공급자** (statusLine 명령 · 결정론층).

왜 있나(2026-09-24): 세이브포인트 감시(`idle-save.py`)는 5시간 사용률과 프롬프트 캐시
만료 시각이 필요한데, 스크립트가 그 값을 받는 **공식 경로는 상태줄 입력뿐**이다
(`rate_limits.five_hour.used_percentage` · `prompt_cache.expires_at`, statusline 문서).
로컬 트랜스크립트 합산은 한도 도달 42건에서 750만~1,400만으로 두 배 가까이 퍼져
임계 판정에 못 쓴다(실측) — 그래서 추정하지 않고 받은 값을 파일로 넘긴다.

⚠ 데스크탑 앱은 statusLine 을 실행하지 않는 것으로 보인다(10-03 실측: 최근 이틀 데스크탑 세션 3개에서
`_index/usage/` 파일 0개). 안 돌면 idle-save 는 사용률 트리거만 끄고 유휴 트리거는 50분 고정으로
동작한다(fail-open).

경계: 판정하지 않는다. 받은 JSON 에서 필요한 칸만 `_index/usage/<sid8>.json` 에 원자 교체로 쓴다.
계약: stdout = 상태줄 한 줄(CLI 에서 보임). 어떤 예외에도 빈 줄(fail-open).
"""
import json, os, sys, time

VAULT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
UDIR = os.path.join(VAULT, "3_시스템", "_index", "usage")
KEEP_S = 2 * 86400        # 이보다 오래된 세션 파일은 지운다(디렉터리가 세션 수만큼 자라지 않게)


def pick(d, *path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="")
    except Exception:
        pass
    line = ""
    try:
        d = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        sid = d.get("session_id") or ""
        cw = d.get("context_window") or {}
        cu = cw.get("current_usage") or {}
        ctx = sum((cu.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                              "cache_read_input_tokens"))
        pc = d.get("prompt_cache") or {}
        rec = {
            "ts": int(time.time()), "session_id": sid,
            "five_hour": pick(d, "rate_limits", "five_hour"),
            "seven_day": pick(d, "rate_limits", "seven_day"),
            "ctx_tokens": ctx or cw.get("total_input_tokens"),
            "prompt_cache": {k: pc.get(k) for k in ("warm", "ttl", "expires_at",
                                                    "recache_tokens_if_cold", "misses",
                                                    "last_miss_cause")} if pc else None,
        }
        if sid:
            os.makedirs(UDIR, exist_ok=True)
            path = os.path.join(UDIR, sid[:8] + ".json")
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="") as fh:
                json.dump(rec, fh, ensure_ascii=False)
            os.replace(tmp, path)
            now = time.time()
            for f in os.listdir(UDIR):
                p = os.path.join(UDIR, f)
                if now - os.path.getmtime(p) > KEEP_S:
                    os.remove(p)
        parts = []
        fh5 = rec["five_hour"] or {}
        if fh5.get("used_percentage") is not None:
            parts.append("5h {:.0f}%".format(fh5["used_percentage"]))
        sd = rec["seven_day"] or {}
        if sd.get("used_percentage") is not None:
            parts.append("7d {:.0f}%".format(sd["used_percentage"]))
        if rec["ctx_tokens"]:
            parts.append("ctx {:.0f}K".format(rec["ctx_tokens"] / 1000))
        exp = pc.get("expires_at")
        if exp:
            parts.append("캐시 {:.0f}분".format(max(0, exp - time.time()) / 60))
        line = " · ".join(parts)
    except Exception:
        line = ""
    sys.stdout.write(line)


if __name__ == "__main__":
    main()
