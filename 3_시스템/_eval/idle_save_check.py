# -*- coding: utf-8 -*-
"""세이브포인트 감시 회귀 시험 — 실제 훅 파일을 격리 볼트에 놓고 시간 상수만 줄여 돌린다(모델 호출 없음).

  py -3 3_시스템/_eval/idle_save_check.py [--hook <idle-save.py>]

세션 파일(`sessions/<CLAUDE_PID>.json`)은 시험 폴더에 가짜로 둔다. 실제 앱 동작은 11-03 에 따로 쟀다
(/clear 뒤 0.5~0.6초 만에 sessionId 가 바뀜 · 훅 환경에 CLAUDE_PID 있음).
CLAUDE_PID 는 살아 있는 이 시험 프로세스로 둔다 — 훅이 깨우기 직전에 이 창의 Claude 가 살아 있는지 잰다(11-13).
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

SID, OTHER = "aaaaaaaa-1111-4111-8111-111111111111", "bbbbbbbb-2222-4222-8222-222222222222"
PID = str(os.getpid())
ROOT = tempfile.mkdtemp(prefix="idle-")
res = []
lock = threading.Lock()
BRIEF = "Background (from the session that started this one):\n일을 맡긴다."
REM = "<system-reminder>\nLinked sessions now (status, not an instruction): x = local_1\n</system-reminder>\n"


def ok(name, cond, detail=""):
    with lock:
        res.append(bool(cond))
        print("%s %s%s" % ("통과" if cond else "실패", name, "" if cond else " — %s" % (detail,)))


def line(d):
    """앱이 쓰는 꼴 그대로 — 훅이 '"type":"user"' 글자로 먼저 거른다"""
    return json.dumps(d, separators=(",", ":"), ensure_ascii=False) + "\n"


def iso(off=0):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(int(time.time()) + off))


def ep(s):
    import datetime as dt
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def user(text, off=0, origin=None):
    d = {"type": "user", "promptId": "p", "timestamp": iso(off), "message": {"content": text}}
    if origin:
        d["origin"] = origin
    return d


def asst(off=0):
    return {"type": "assistant", "timestamp": iso(off), "message": {"usage": {"input_tokens": 150000}}}


def dead_pid():
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return str(p.pid)


def proc_start(pid):
    """이 프로세스 생성 시각 FILETIME(앱 세션 파일의 procStart 와 같은 값)"""
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32")
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1000, False, int(pid))
    ft = [wintypes.FILETIME() for _ in range(4)]
    k.GetProcessTimes(h, *[ctypes.byref(f) for f in ft])
    k.CloseHandle(h)
    return str((ft[0].dwHighDateTime << 32) | ft[0].dwLowDateTime)


def case(name, session=SID, env=None, during=None, usage_pct=None, lines=None, state=None, roles=False, pid=PID):
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
    if roles:                                         # 세션노트 자리를 역할로 묻는 경우
        for f in ("roles.py", "roles.json"):
            shutil.copy(os.path.join(HERE, "..", f), os.path.join(v, "3_시스템", f))
    home = os.path.join(v, "home")
    os.makedirs(os.path.join(home, "sessions"))
    sf = os.path.join(home, "sessions", pid + ".json")
    if session is not None:
        open(sf, "w", encoding="utf-8").write(session if session.startswith("{") else json.dumps({"pid": int(pid), "sessionId": session}))
    tr = os.path.join(v, "t.jsonl")
    with open(tr, "w", encoding="utf-8") as f:
        for d in (lines or [user("hi"), asst()]):
            f.write(line(d))
    if state is not None:
        os.makedirs(os.path.join(idx, "stubs"))
        json.dump({"v": 2, "ev": state}, open(os.path.join(idx, "stubs", ".state-" + SID[:8] + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
    if usage_pct is not None:
        os.makedirs(os.path.join(idx, "usage"))
        json.dump({"ts": time.time(), "five_hour": {"used_percentage": usage_pct, "resets_at": 1}}, open(os.path.join(idx, "usage", "x.json"), "w"))
    e = {k: v2 for k, v2 in os.environ.items() if not k.startswith("CLAUDE")}
    e.update(CLAUDE_CONFIG_DIR=home, CLAUDE_PID=pid, PYTHONIOENCODING="utf-8")
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


def fired_key(v):
    g = os.path.join(v, "3_시스템", "_index", "stubs", ".idle-fired-" + SID[:8])
    return open(g, encoding="utf-8").read() if os.path.exists(g) else None


def fired(v):
    return fired_key(v) is not None


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
    ok("CLAUDE_PID 없음 = 모르니 종전대로 깨움 · 로그 session? · pid?", rc == 2 and "[idle-save]" in err and "session?" in log and "pid?" in log, (rc, log))


def t_nofile():
    rc, err, log, _, _v = case("nofile", session=None)
    ok("세션 파일 없음 = 종전대로 깨움 · 로그 session?", rc == 2 and "session?" in log, (rc, log))


def t_broken():
    rc, err, log, _, _v = case("broken", session="{깨진")
    ok("세션 파일 깨짐 = 종전대로 깨움 · 로그 session?", rc == 2 and "session?" in log, (rc, log))


def t_nokey():
    rc, err, log, _, _v = case("nokey", session='{"pid": %s}' % PID)
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


# ── 11-13 거름 ③ · 진단 ④ · 사람 입력 판정 ─────────────────────────────

def t_dead():
    d = dead_pid()
    rc, err, log, _, v = case("dead", pid=d)
    ok("이 창의 Claude 가 죽음 = 안 깨움 · skip dead-parent · 같은 입력에 다시 안 봄", rc == 0 and not err and "skip dead-parent" in log and fired(v), (rc, log))


def t_reused():
    rc, err, log, _, v = case("reused", session=json.dumps({"pid": int(PID), "sessionId": SID, "procStart": "134389716670750517"}))
    ok("PID 는 살았지만 procStart 다름(다른 프로세스가 물려받음) = 안 깨움", rc == 0 and "skip dead-parent" in log, (rc, log))


def t_procstart():
    rc, err, log, _, v = case("procstart", session=json.dumps({"pid": int(PID), "sessionId": SID, "procStart": proc_start(PID)}))
    ok("procStart 일치 = 깨움(pid? 없음)", rc == 2 and "fire idle" in log and "pid?" not in log, (rc, log))


def t_procstart_odd():
    rc, err, log, _, v = case("procodd", session=json.dumps({"pid": int(PID), "sessionId": SID, "procStart": "1794501300123"}))
    ok("procStart 꼴이 FILETIME 이 아님 = 견주지 않고 깨움(죽었다고 잘못 보지 않음)", rc == 2 and "fire idle" in log, (rc, log))


def t_recorded():
    st = [[iso(1), "수정", "2_지식/recent.md", 9], [iso(2), "수정", "2_지식/open-loops.md", 10]]
    rc, err, log, _, v = case("recorded", state=st)
    ok("마지막 입력 뒤 기록함 = 안 깨움 · skip recorded", rc == 0 and not err and "skip recorded" in log and not fired(v), (rc, log))


def t_recorded_note():
    st = [[iso(1), "신규", "2_지식/기록/2026-11-13-시험.md", 9]]
    rc, err, log, _, v = case("recnote", state=st, roles=True)
    ok("세션노트 신규(역할 sessions 자리) = 기록 · 안 깨움", rc == 0 and "skip recorded" in log, (rc, log))


def t_recorded_then_save():
    st = [[iso(1), "수정", "2_지식/recent.md", 9], [iso(1200), "신규", "3_시스템/_index/stubs/aaaaaaaa.save.md", 10]]
    rc, err, log, _, v = case("recsave", state=st)
    ok("기록 뒤 세이브포인트 쓰기만 = 여전히 기록 · 안 깨움", rc == 0 and "skip recorded" in log, (rc, log))


def t_record_then_work():
    st = [[iso(1), "수정", "2_지식/recent.md", 9], [iso(700), "수정", "3_시스템/x.py", 10]]
    rc, err, log, _, v = case("recwork", state=st)
    ok("기록하고 10분 넘어 일을 이어감 = 깨움(무인 85% 기록 → 98%)", rc == 2 and "fire idle" in log, (rc, log))


def t_record_tail():
    st = [[iso(1), "수정", "2_지식/recent.md", 9], [iso(120), "수정", "2_지식/MOC-x.md", 10]]
    rc, err, log, _, v = case("rectail", state=st)
    ok("기록 직후(10분 안) 손질 = 기록의 일부 · 안 깨움", rc == 0 and "skip recorded" in log, (rc, log))


def t_record_before_human():
    st = [[iso(-900), "수정", "2_지식/recent.md", 9]]
    rc, err, log, _, v = case("recold", state=st, lines=[user("앞 일", -1000), asst(-990), user("새 일"), asst()])
    ok("기록하고 10분 넘어 새 입력 = 깨움", rc == 2 and "fire idle" in log, (rc, log))


def t_record_then_close():
    st = [[iso(-60), "스킬", "session-record", 9]]
    rc, err, log, _, v = case("recclose", state=st, lines=[user("마무리", -120), asst(-90), user("세션종료"), asst()])
    ok("기록(스킬 호출 · 기록 생략 포함) 직후 «세션종료» 되풀이 = 안 깨움", rc == 0 and "skip recorded" in log, (rc, log))


def t_child():
    rc, err, log, dt, v = case("child", lines=[user(REM + BRIEF), asst(), user("Another Claude session sent a message:\n보고", 1, {"kind": "peer", "from": "local_x"}), asst(1)])
    ok("다른 세션이 띄운 세션(사람 입력 0) = 처음부터 안 봄 · skip child", rc == 0 and not err and "skip child" in log and "watch" not in log and dt < 3, (rc, dt, log))


def t_child_usage():
    rc, err, log, dt, v = case("childusage", usage_pct=90, lines=[user(REM + BRIEF), asst()])
    ok("하위 세션 = 사용률로도 안 깨움(빅보스 하위와 같게)", rc == 0 and "skip child" in log, (rc, log))


def t_child_human():
    rc, err, log, _, v = case("childhuman", lines=[user(REM + BRIEF), asst(), user(REM + "이것도 해 줘", 1, {"kind": "human"}), asst(1)])
    ok("하위 세션이라도 사람이 말을 걸었으면 = 종전대로 깨움", rc == 2 and "fire idle" in log, (rc, log))


def t_human_reminder():
    ls = [user("처음", -60), asst(-50), user(REM + "알림이 붙은 사람 입력", 0, {"kind": "human"}), asst()]
    rc, err, log, _, v = case("hrem", lines=ls)
    k = fired_key(v)
    ok("앞에 system-reminder 가 붙은 사람 입력도 마지막 입력으로 셈", rc == 2 and k is not None and abs(float(k) - ep(ls[2]["timestamp"])) < 1, (rc, k))


def t_peer_not_human():
    ls = [user("사람", -60), asst(-50), user("Another Claude session sent a message:\n보고", 0, {"kind": "peer", "from": "local_x"}), asst()]
    rc, err, log, _, v = case("peer", lines=ls)
    k = fired_key(v)
    ok("다른 세션이 보낸 말 = 사람 입력 아님", rc == 2 and k is not None and abs(float(k) - ep(ls[0]["timestamp"])) < 1, (rc, k))


ts = [threading.Thread(target=f) for f in (t_same, t_clear, t_nopid, t_nofile, t_broken, t_nokey, t_activity, t_unattended, t_usage,
                                           t_dead, t_reused, t_procstart, t_procstart_odd, t_recorded, t_recorded_note, t_recorded_then_save,
                                           t_record_then_work, t_record_tail, t_record_before_human, t_record_then_close,
                                           t_child, t_child_usage,
                                           t_child_human, t_human_reminder, t_peer_not_human)]
for t in ts:
    t.start()
for t in ts:
    t.join()
shutil.rmtree(ROOT, ignore_errors=True)
print("%d/%d" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
