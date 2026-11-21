#!/usr/bin/env python3
"""볼트 속도 — 사람이 기다리는 시간을 재고 한계와 견준다. 읽기만 한다(주간 점검 «속도» 칸).

  py -3 3_시스템/speed.py [--days 7] [--no-run] [--json]

쌓이는 것(git 개체·색인 크기·작업 파일·자국·로그·디스크)은 `brain.py doctor` «볼트 무게»가 본다.
여기는 그 결과로 늘어나는 «시간»이다. 한 줄 = ✓/△/✗ 이름 값 (한계).
  - Stop 훅(턴 끝 기다림)·SessionStart 훅: 대화 기록(~/.claude/projects/<볼트>/*.jsonl)에 앱이 남긴 durationMs
    (문서에 없는 형식 — 앱 판이 바뀌어 0건이면 «기록 없음»으로 알린다)
  - 커밋 턴 비율: Stop 이 도는 동안 자동 커밋(session:)이 났는가 — 높으면 턴 끝이 커밋을 기다린다
  - 모듈 줄: 켜진 모듈 module.json 의 contributes.speed(명령 · {py} {days}) — 출력 = JSON 목록
    [{name, median_ms, p90_ms, n, limit_ms}] · 못 돌거나 빈 목록이면 줄 없음(예: mobility «폰 홈»)
  - 찾기 한 번(search.py --q) · 홈(brain.py home): 지금 한 번 돌려 잰다(--no-run 이면 뺌)
한계를 넘으면 느린 자리를 부품별로 다시 잴 때다(훅 안 · 찾기 색인 · 홈 계산 · git 정리).
근거 = 11-16 실측(Stop 중앙 3초 · 찾기 5초 · 홈 2초) · session-notice 3초(11-07 1.5초 → 11-16 2.3초).
"""
import glob
import json
import os
import re
import statistics as st
import subprocess
import sys
import time
import datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
# 한계(밀리초) — 중앙값 기준 · 넘으면 △, 두 배면 ✗
LIMIT = {"stop": 3000, "start": 3000, "search": 5000, "home": 2000, "commit_turn": 0.6}

try:
    import psutil
    psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)   # 사용자 작업을 밀지 않는다
except Exception:
    pass


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, max(0, int(round(p * (len(v) - 1)))))] if v else None


def project_dir():
    # 앱이 쓰는 프로젝트 폴더 이름 = 볼트 경로의 영숫자 밖 글자를 «-» 로
    name = re.sub(r"[^A-Za-z0-9]", "-", VAULT)
    return os.path.join(os.path.expanduser("~"), ".claude", "projects", name)


def hook_times(days):
    """Stop 턴마다 동기 훅 가장 긴 것(= 사람이 기다린 시간) · SessionStart 의 session-notice."""
    cut = time.time() - days * 86400
    stop, start = [], []
    for f in glob.glob(os.path.join(project_dir(), "*.jsonl")):
        if os.path.getmtime(f) < cut:
            continue
        with open(f, "rb") as fh:
            for ln in fh:
                if b"durationMs" not in ln:
                    continue
                try:
                    d = json.loads(ln)
                except Exception:
                    continue
                ts = d.get("timestamp") or ""
                try:
                    t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
                except Exception:
                    continue
                if t < cut:
                    continue
                if b"stop_hook_summary" in ln:
                    ms = [h.get("durationMs") for h in d.get("hookInfos") or [] if isinstance(h.get("durationMs"), (int, float))]
                    if ms:
                        stop.append((t, max(ms)))
                    continue
                at = d.get("attachment") if isinstance(d.get("attachment"), dict) else d
                if (at.get("hookEvent") or at.get("hookName") or "").startswith("SessionStart") and "session-notice" in (at.get("command") or ""):
                    if isinstance(at.get("durationMs"), (int, float)):
                        start.append(at["durationMs"])
    return stop, start


def commit_share(stop, days):
    if not stop:
        return None
    out = subprocess.run(["git", "-C", VAULT, "log", "--since=%d days ago" % (days + 1), "--format=%ct %s"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    cs = sorted(int(l.split()[0]) for l in out.splitlines() if l.split(" ", 1)[-1].startswith("session:"))
    import bisect
    hit = 0
    for t, ms in stop:
        i = bisect.bisect_left(cs, t - ms / 1000 - 2)
        hit += i < len(cs) and cs[i] <= t + 2
    return hit / len(stop)


def module_rows(days):
    """켜진 모듈이 낸 속도 줄(contributes.speed) — [(이름, 중앙, p90, 번, 한계)] · 모듈 없음·실패는 조용히 뺌(11-21 «폰 홈» 줄을 mobility 로 옮김)"""
    out = []
    try:
        sys.path.insert(0, HERE)
        import roles
        mods = roles.modules(on_only=True, vault=VAULT)
    except Exception:  # noqa: BLE001
        return out
    for m in mods:
        cmd = ((m.get("json") or {}).get("contributes") or {}).get("speed") if isinstance((m.get("json") or {}).get("contributes"), dict) else None
        if not isinstance(cmd, list) or not cmd:
            continue
        argv = [sys.executable if t == "{py}" else ("%g" % days if t == "{days}" else (os.path.join(VAULT, t) if t.endswith(".py") and not os.path.isabs(t) else t)) for t in cmd]
        try:
            r = subprocess.run(argv, capture_output=True, timeout=30, cwd=VAULT,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            got = json.loads(r.stdout.decode("utf-8", "replace") or "[]") if r.returncode == 0 else []
        except Exception:  # noqa: BLE001
            continue
        for it in got if isinstance(got, list) else []:
            try:
                out.append((str(it["name"]), float(it["median_ms"]), float(it["p90_ms"]), int(it["n"]), float(it["limit_ms"])))
            except (KeyError, TypeError, ValueError):
                continue
    return out


def timed(args, timeout):
    t = time.time()
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, cwd=VAULT,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return (time.time() - t) * 1000 if r.returncode == 0 else None
    except Exception:
        return None


def mark(v, lim):
    if v is None:
        return "·"
    return "✓" if v <= lim else ("△" if v <= 2 * lim else "✗")


def sec(ms):
    return "%.1f초" % (ms / 1000)


def main(argv):
    days = float(argv[argv.index("--days") + 1]) if "--days" in argv else 7
    rows = []   # (표시, 이름, 값 글, 한계 글)
    stop, start = hook_times(days)
    if stop:
        v = [ms for _, ms in stop]
        md = st.median(v)
        # 최근 하루를 따로 — 고친 것(예: 턴 끝 커밋을 뒤로)의 효과가 7일 값에 묻히지 않게
        day = [ms for t, ms in stop if t >= time.time() - 86400]
        d1 = " · 최근 하루 중앙 %s(%d턴)" % (sec(st.median(day)), len(day)) if day else ""
        rows.append((mark(md, LIMIT["stop"]), "턴 끝(Stop 훅)", "중앙 %s · p90 %s · %d턴%s" % (sec(md), sec(q(v, .9)), len(v), d1), "중앙 " + sec(LIMIT["stop"])))
        cs = commit_share(stop, days)
        if cs is not None:
            rows.append(("✓" if cs <= LIMIT["commit_turn"] else "△", "커밋 턴 비율", "%.0f%%" % (cs * 100), "%.0f%%" % (LIMIT["commit_turn"] * 100)))
    else:
        rows.append(("·", "턴 끝(Stop 훅)", "기록 없음 — 앱 기록 형식이 바뀌었나 볼 것", ""))
    if start:
        md = st.median(start)
        rows.append((mark(md, LIMIT["start"]), "세션 시작(session-notice)", "중앙 %s · p90 %s · %d번" % (sec(md), sec(q(start, .9)), len(start)), sec(LIMIT["start"])))
    for name, md, p90, n, lim in module_rows(days):
        rows.append((mark(md, lim), name, "중앙 %s · p90 %s · %d번" % (sec(md), sec(p90), n), sec(lim)))
    if "--no-run" not in argv:
        ms = timed([sys.executable, os.path.join(HERE, "brain.py"), "home"], 60)
        rows.append((mark(ms, LIMIT["home"]), "홈(brain.py home)", sec(ms) if ms else "실패", sec(LIMIT["home"])))
        # 두 번 — 첫 번은 디스크 캐시가 차가워 크게 나온다(11-17 잼: 19.3초 → 이어서 5.6~8.0초) · 판정은 두 번째
        cold = timed([sys.executable, os.path.join(HERE, "search.py"), "--q", "주간 점검 기록", "--k", "8"], 120)
        ms = timed([sys.executable, os.path.join(HERE, "search.py"), "--q", "볼트 속도 재기", "--k", "8"], 120)
        rows.append((mark(ms, LIMIT["search"]), "찾기(search.py --q · 두 번째)", "%s(첫 번 %s)" % (sec(ms), sec(cold) if cold else "실패") if ms else "실패", sec(LIMIT["search"])))
    if "--json" in argv:
        print(json.dumps([dict(zip(("mark", "name", "value", "limit"), r)) for r in rows], ensure_ascii=False))
        return 0
    for m, name, val, lim in rows:
        print("- %s %s: %s%s" % (m, name, val, " (한계 %s)" % lim if lim else ""))
    over = [r[1] for r in rows if r[0] in "△✗"]
    print("- 한계 넘음: %s — 느린 자리를 부품별로 다시 잴 때" % " · ".join(over) if over else "- 모두 한계 안")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
