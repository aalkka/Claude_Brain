#!/usr/bin/env python3
"""Claude 데스크톱 앱 로그인이 풀렸나 — 앱 기록(main.log · remote-control.log)을 읽기만 한다. 11-20 사고(_ref/incident-2026-11-20-…):
07:11 «sign-in is too old (session_stale_relogin)» 로 Code 탭·원격 제어가 멈췄는데 13:00 사람이 올 때까지 아무도 몰랐다.
로그인 수명은 서버가 정하니 막을 수 없고 빨리 알게만 한다 — 건강 줄(drift.mem_rows · 늘)과 폰 알림(mobility 서버 순찰 · 있을 때).

  py -3 3_시스템/claude_login.py [--json]

풀림 = 마지막 «되찾음» 뒤에 «풀림» 줄이 있음. 풀린 때(episode) = 그 뒤 첫 «풀림» 줄의 시각 — 같은 만료에 알림이 되풀이되지 않게 이 값으로 가른다.
  main.log           풀림 = session_stale_relogin(되찾음 줄 둘은 뺌) · 되찾음 = «clearing latched session_stale_relogin» · «dropped the stored session_stale_relogin»
  remote-control.log 풀림 = «→ auth_stale» · 되찾음 = «auth_stale →»
기록 자리 = %LOCALAPPDATA%\\Claude\\Logs(윈도 데스크톱 앱 · 환경 CLAUDE_APP_LOGS 로 바꿈) · 없으면 «모름»."""
import json
import os
import re
import sys

TAIL = 3_000_000            # main.log 은 크다(7.6MB ≈ 4일) — 끝 3MB 만(앱이 풀린 동안 갱신 실패를 되풀이해 적는다 · remote-control 은 통째)
TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
RULES = {
    "main.log": (lambda ln: "session_stale_relogin" in ln and not ("clearing latched" in ln or "dropped the stored" in ln),
                 lambda ln: "clearing latched session_stale_relogin" in ln or "dropped the stored session_stale_relogin" in ln),
    "remote-control.log": (lambda ln: "→ auth_stale" in ln, lambda ln: "auth_stale →" in ln),
}


def logs_dir():
    d = os.environ.get("CLAUDE_APP_LOGS")
    if d:
        return d
    la = os.environ.get("LOCALAPPDATA")
    return os.path.join(la, "Claude", "Logs") if la else None


def _lines(p, tail):
    try:
        with open(p, "rb") as f:
            if tail:
                f.seek(0, 2)
                f.seek(max(0, f.tell() - tail))
                if f.tell():
                    f.readline()           # 잘린 첫 줄
            return f.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return None


def events(d=None):
    """[(시각, 'stale'|'ok', 파일)] — 시각 차례."""
    d = d or logs_dir()
    out, seen = [], False
    if not d:
        return out, seen
    for name, (bad, good) in RULES.items():
        ls = _lines(os.path.join(d, name), TAIL if name == "main.log" else 0)
        if ls is None:
            continue
        seen = True
        for ln in ls:
            m = TS.match(ln)
            if not m:
                continue
            if good(ln):
                out.append((m.group(1), "ok", name))
            elif bad(ln):
                out.append((m.group(1), "stale", name))
    out.sort(key=lambda x: x[0])
    return out, seen


def state(d=None):
    """{'state': stale|ok|unknown, 'since': 풀린 때, 'last': 마지막 풀림 줄, 'src': 파일}"""
    ev, seen = events(d)
    if not seen:
        return {"state": "unknown", "why": "앱 기록 없음"}
    last_ok = max((t for t, k, _ in ev if k == "ok"), default="")
    bad = [(t, f) for t, k, f in ev if k == "stale" and t > last_ok]
    if not bad:
        return {"state": "ok", "since": None, "recovered": last_ok or None}
    return {"state": "stale", "since": bad[0][0], "last": bad[-1][0], "src": bad[0][1]}


def health_rows(st=None):
    """건강 줄(drift.mem_rows) — 풀렸을 때만 한 줄."""
    st = st or state()
    if st.get("state") != "stale":
        return []
    return [("Claude 로그인", "warn", f"데스크톱 앱 로그인 풀림({st['since'][5:16]}부터 · 서버가 «로그인이 오래됨»으로 거절) — "
             "Code 탭 세션·원격 제어가 멈춤 · 앱에서 다시 로그인")]


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    st = state()
    if "--json" in argv:
        return print(json.dumps(st, ensure_ascii=False))
    print({"stale": f"풀림 {st.get('since')}부터(마지막 {st.get('last')} · {st.get('src')})", "ok": "로그인 됨",
           "unknown": "모름(" + st.get("why", "") + ")"}[st["state"]])


if __name__ == "__main__":
    main(sys.argv[1:])
