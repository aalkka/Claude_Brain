# -*- coding: utf-8 -*-
"""세이브포인트 감시 회귀 시험 — 실제 훅 파일을 격리 볼트에 놓고 시간 상수만 줄여 돌린다(모델 호출 없음).

  py -3 3_시스템/_eval/idle_save_check.py [--hook <idle-save.py>]

세션 파일(`sessions/<CLAUDE_PID>.json`)은 시험 폴더에 가짜로 둔다. 실제 앱 동작은 11-03 에 따로 쟀다
(/clear 뒤 0.5~0.6초 만에 sessionId 가 바뀜 · 훅 환경에 CLAUDE_PID 있음).
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--hook", default=os.path.join(HERE, "..", "hooks", "idle-save.py"))
hook = os.path.abspath(ap.parse_args().hook)

SID, OTHER, PID = "aaaaaaaa-1111-4111-8111-111111111111", "bbbbbbbb-2222-4222-8222-222222222222", "99999"
ROOT = tempfile.mkdtemp(prefix="idle-")
res = []
lock = threading.Lock()


def ok(name, cond, detail=""):
    with lock:
        res.append(bool(cond))
        print("%s %s%s" % ("통과" if cond else "실패", name, "" if cond else " — %s" % (detail,)))


def line(d):
    """앱이 쓰는 꼴 그대로 — 훅이 '"type":"user"' 글자로 먼저 거른다"""
    return json.dumps(d, separators=(",", ":"), ensure_ascii=False) + "\n"


def case(name, session=SID, env=None, during=None, usage_pct=None):
    """훅을 한 번 돌린다 → (종료 코드, stderr, 로그, 걸린 초, 격리 볼트)"""
    v = os.path.join(ROOT, name)
    hooks, idx = os.path.join(v, "3_시스템", "hooks"), os.path.join(v, "3_시스템", "_index")
    os.makedirs(hooks)
    os.makedirs(idx)
    s = open(hook, encoding="utf-8").read()
    for a, b in (("IDLE_MIN = 50 ", "IDLE_MIN = 0.1 "), ("POLL_S = 30", "POLL_S = 1")):
        assert a in s, a
        s = s.replace(a, b)
    p = os.path.join(hooks, "idle-save.py")
    open(p, "w", encoding="utf-8").write(s)
    home = os.path.join(v, "home")
    os.makedirs(os.path.join(home, "sessions"))
    sf = os.path.join(home, "sessions", PID + ".json")
    if session is not None:
        open(sf, "w", encoding="utf-8").write(session if session.startswith("{") else json.dumps({"pid": int(PID), "sessionId": session}))
    tr = os.path.join(v, "t.jsonl")
    now = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    with open(tr, "w", encoding="utf-8") as f:
        f.write(line({"type": "user", "promptId": "p", "timestamp": now, "message": {"content": "hi"}}))
        f.write(line({"type": "assistant", "timestamp": now, "message": {"usage": {"input_tokens": 150000}}}))
    if usage_pct is not None:
        os.makedirs(os.path.join(idx, "usage"))
        json.dump({"ts": time.time(), "five_hour": {"used_percentage": usage_pct, "resets_at": 1}}, open(os.path.join(idx, "usage", "x.json"), "w"))
    e = {k: v2 for k, v2 in os.environ.items() if not k.startswith("CLAUDE")}
    e.update(CLAUDE_CONFIG_DIR=home, CLAUDE_PID=PID, PYTHONIOENCODING="utf-8")
    for k, x in (env or {}).items():
        if x is None:
            e.pop(k, None)
        else:
            e[k] = x
    t0 = time.time()
    pr = subprocess.Popen([sys.executable, p], stdin=subprocess.PIPE, stderr=subprocess.PIPE, env=e)
    pr.stdin.write(json.dumps({"session_id": SID, "transcript_path": tr}).encode("utf-8"))
    pr.stdin.close()
    if during:
        time.sleep(2)
        during(sf, tr)
    err = pr.stderr.read().decode("utf-8", "replace")
    rc = pr.wait(60)
    lp = os.path.join(idx, "hooks.log")
    return rc, err, open(lp, encoding="utf-8").read() if os.path.exists(lp) else "", time.time() - t0, v


def fired(v):
    return os.path.exists(os.path.join(v, "3_시스템", "_index", "stubs", ".idle-fired-" + SID[:8]))


def t_same():
    rc, err, log, _, v = case("same")
    ok("같은 세션 = 유휴 뒤 깨움(지시에 세션 id)", rc == 2 and "[idle-save]" in err and SID[:8] in err and "fire idle" in log and fired(v), (rc, log))


def t_clear():
    def clear(sf, tr):
        json.dump({"pid": int(PID), "sessionId": OTHER}, open(sf, "w", encoding="utf-8"))
    rc, err, log, _, v = case("clear", during=clear)
    ok("/clear 로 세션이 바뀜 = 안 깨움 · 까닭을 로그에 · 표시 파일 없음", rc == 0 and not err and "exit session-changed " + OTHER[:8] in log and not fired(v), (rc, err[:80], log))


def t_nopid():
    rc, err, log, _, _v = case("nopid", env={"CLAUDE_PID": None})
    ok("CLAUDE_PID 없음 = 모르니 종전대로 깨움 · 로그 session?", rc == 2 and "[idle-save]" in err and "session?" in log, (rc, log))


def t_nofile():
    rc, err, log, _, _v = case("nofile", session=None)
    ok("세션 파일 없음 = 종전대로 깨움 · 로그 session?", rc == 2 and "session?" in log, (rc, log))


def t_broken():
    rc, err, log, _, _v = case("broken", session="{깨진")
    ok("세션 파일 깨짐 = 종전대로 깨움 · 로그 session?", rc == 2 and "session?" in log, (rc, log))


def t_nokey():
    rc, err, log, _, _v = case("nokey", session='{"pid": 99999}')
    ok("세션 파일에 sessionId 없음 = 종전대로 깨움", rc == 2 and "session?" in log, (rc, log))


def t_activity():
    def act(sf, tr):
        with open(tr, "a", encoding="utf-8") as f:
            later = time.strftime("%Y-%m-%dT%H:%M:%S.999Z", time.gmtime(time.time() + 5))
            f.write(line({"type": "user", "timestamp": later, "message": {"content": "x"}}))
    rc, err, log, _, _v = case("activity", during=act)
    ok("새 활동 = 안 깨움(종전과 같음)", rc == 0 and not err and "exit activity" in log, (rc, log))


def t_unattended():
    rc, err, log, dt, _v = case("unattended", env={"CLAUDE_CODE_SESSION_ATTENDED": "0"})
    ok("무인 실행 = 바로 빠짐(종전과 같음)", rc == 0 and not err and dt < 3, (rc, dt))


def t_usage():
    rc, err, log, dt, _v = case("usage", usage_pct=90)
    ok("5시간 사용률 = 턴 끝에 바로 깨움(종전과 같음)", rc == 2 and "5시간 사용량 90%" in err and dt < 3, (rc, dt, err[:80]))


ts = [threading.Thread(target=f) for f in (t_same, t_clear, t_nopid, t_nofile, t_broken, t_nokey, t_activity, t_unattended, t_usage)]
for t in ts:
    t.start()
for t in ts:
    t.join()
shutil.rmtree(ROOT, ignore_errors=True)
print("%d/%d" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
