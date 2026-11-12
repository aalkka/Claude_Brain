"""가짜 claude — 구독 끊김 흉내(시험 전용 · 모델을 부르지 않는다 · 사용량 0). fake_claude.cs 로 만든 claude.exe 가 이 파일을 부른다.

흉내 갈래 = 같은 폴더 fake_claude.mode 한 줄(없으면 lapsed):
  lapsed   auth status = 로그인됨 · subscriptionType 없음 / -p = error oauth_org_not_allowed (실제 해지 글은 안 잼 — 꼴만 흉내)
  callfail auth status = 정상(pro) / -p = error oauth_org_not_allowed (상태로는 못 잡고 호출에서 잡히는 경우)
  nologin  auth status = loggedIn false(rc 1) / -p = error authentication_failed «Not logged in · Please run /login» (11-11 빈 설정 폴더로 잰 꼴 그대로)
  ratelimit       auth status 정상 / -p = rate_limit_event rejected + error rate_limit + 실행 파일의 한도 글 꼴(«/upgrade …»·«Upgrade to Max …» 든 글)
  ratelimit-noerr 위와 같고 error 칸만 없음(글만으로 갈라질 때도 해지로 안 읽히나)
  real     같은 폴더 real.path 의 진짜 claude 로 넘긴다(흉내 걷음)
부른 것은 calls.log 에 한 줄씩.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def mode():
    try:
        with open(os.path.join(HERE, "fake_claude.mode"), encoding="utf-8") as f:
            return f.read().strip() or "lapsed"
    except OSError:
        return "lapsed"


def emit(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main(args):
    m = mode()
    with open(os.path.join(HERE, "calls.log"), "a", encoding="utf-8") as f:
        f.write(f"{m} {json.dumps(args[:3], ensure_ascii=False)}\n")
    if m == "real":
        with open(os.path.join(HERE, "real.path"), encoding="utf-8") as f:
            real = f.read().strip()
        return subprocess.call([real] + args)
    if args[:1] == ["--version"]:
        print("2.1.999 (Claude Code)")
        return 0
    if args[:2] == ["auth", "status"]:
        if m == "nologin":
            print(json.dumps({"loggedIn": False, "authMethod": "none", "apiProvider": "firstParty", "loginExpiresAt": None}, indent=2))
            return 1
        d = {"loggedIn": True, "authMethod": "claude.ai", "apiProvider": "firstParty", "subscriptionType": "pro", "planTier": "pro"}
        if m == "lapsed":
            d.update(subscriptionType=None, planTier=None)
        print(json.dumps(d, indent=2))
        return 0
    if args[:1] == ["remote-control"]:
        print("Not logged in · Please run /login")
        return 1
    if "-p" not in args:
        print("fake claude: 모르는 명령", args[:2], file=sys.stderr)
        return 2
    if m.startswith("ratelimit"):       # 사용량 한도(5시간 창 100%) — 글은 2.1.321 실행 파일의 한도 글 꼴 · ratelimit-noerr = error 칸이 빠진 꼴(가르기 단단함 재기)
        err, text = ("" if m == "ratelimit-noerr" else "rate_limit"), "You've hit your limit · resets 1:50am · /upgrade to keep using Claude Code · Upgrade to Max or Ultra for higher session limits"
    else:
        err, text = (("authentication_failed", "Not logged in · Please run /login") if m == "nologin"
                     else ("oauth_org_not_allowed", "Your organization does not have access to Claude Code (흉내)"))
    out = args[args.index("--output-format") + 1] if "--output-format" in args else "text"
    if out != "stream-json":
        print(text)
        return 1
    sid = "fake-0000"

    def turn():
        emit({"type": "system", "subtype": "init", "session_id": sid, "apiKeySource": "none", "model": "claude-opus-5-5", "tools": []})
        if m.startswith("ratelimit"):
            emit({"type": "rate_limit_event", "rate_limit_info": {"status": "rejected", "rateLimitType": "five_hour", "resetsAt": 1794419400,
                  "unifiedWindows": {"five_hour": {"utilization": 1.0, "resetsAt": 1794419400}}}, "session_id": sid})
        a = {"type": "assistant", "message": {"id": "fake", "model": "<synthetic>", "role": "assistant", "content": [{"type": "text", "text": text}]},
             "session_id": sid, "parent_tool_use_id": None}
        if err:
            a["error"] = err
        emit(a)
        emit({"type": "result", "subtype": "success", "is_error": True, "result": text, "session_id": sid, "terminal_reason": "api_error",
              "usage": {"input_tokens": 0, "output_tokens": 0}, "total_cost_usd": 0, "duration_ms": 5})

    if "--input-format" in args and args[args.index("--input-format") + 1] == "stream-json":
        for ln in sys.stdin:
            try:
                d = json.loads(ln.lstrip("﻿"))
            except ValueError:
                continue
            if d.get("type") == "control_request":
                rid = d.get("request_id")
                sub = (d.get("request") or {}).get("subtype")
                resp = {"commands": [], "models": [{"value": "opus", "displayName": "Opus", "resolvedModel": "claude-opus-5-5"}]} if sub == "initialize" else {}
                emit({"type": "control_response", "response": {"subtype": "success", "request_id": rid, "response": resp}})
            elif d.get("type") == "user":
                turn()
        return 0
    turn()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
