#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""restart.py 시험 — 가짜 사실로 경우마다 «끔/미룸»이 맞는지 · tick 의 시각·마감·하루 한 번 · after 의 다시 띄움·잼.
⛔ 실제 재시작·로그오프·절전은 나가지 않는다: do_restart 와 subprocess 의 shutdown 을 막아 두고(부르면 시험 실패), 기록 자리는 임시 폴더.

  py -3 3_시스템/_eval/restart_check.py
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import restart as R  # noqa: E402

BLOCKED = []
_real_run, _real_popen = subprocess.run, subprocess.Popen


def _guard(argv):
    a = " ".join(argv) if isinstance(argv, (list, tuple)) else str(argv)
    if any(w in a.lower() for w in ("shutdown", "logoff", "rundll32 powrprof", "setsuspendstate", "/sg", "restart-computer")):
        BLOCKED.append(a)
        raise RuntimeError("시험 중 재시작 명령 막음: " + a)


def run_guard(argv, *a, **k):
    _guard(argv)
    return _real_run(argv, *a, **k)


def popen_guard(argv, *a, **k):
    _guard(argv)
    return _real_popen(argv, *a, **k)


subprocess.run, subprocess.Popen = run_guard, popen_guard
R.do_restart = lambda c, dry: (_ for _ in ()).throw(RuntimeError("do_restart 불림"))

C = copy.deepcopy(R.DEFAULTS)
C["on"] = True
NOW = time.time()
CLEAN = {
    "t": NOW, "boot": NOW - 3 * 86400,
    "user": {"idle_s": 4 * 3600, "notif": 1, "locked": True, "audio": False},
    "claude": [{"name": "쉬는 세션", "short": "abcd1234", "busy": False, "idle_min": 300}],
    "reclaim": [], "ledger": [], "heavy_lock": False, "gpu": [],
    "procs": [{"pid": 100, "name": "svchost.exe", "exe": r"C:\Windows\System32\svchost.exe", "cmd": "", "core": 0.02, "io_kbs": 3},
              {"pid": 101, "name": "chrome.exe", "exe": r"C:\Program Files\Google\Chrome\Application\chrome.exe", "cmd": "", "core": 0.01, "io_kbs": 0}],
    "net_kbs": 3.0, "partial": [], "battery": False,
    "windows": [{"pid": 101, "name": "chrome.exe", "title": "새 탭 - Chrome"}],
}


def F(**over):
    f = copy.deepcopy(CLEAN)
    for k, v in over.items():
        if "." in k:
            a, b = k.split(".")
            f[a][b] = v
        else:
            f[k] = v
    return f


def P(name, core=0.0, io=0.0, exe=None, cmd="", pid=500):
    return {"pid": pid, "name": name, "exe": exe or (r"C:\Program Files\X\\" + name), "cmd": cmd, "core": core, "io_kbs": io}


def W(title, name="app.exe", pid=600):
    return {"pid": pid, "name": name, "title": title}


def cfgx(**k):
    c = copy.deepcopy(C)
    c.update(k)
    return c


CASES = [
    # (이름, 사실, 설정, 기대 판정, 까닭 갈래 하나라도)
    ("깨끗함(잠금·4시간 쉼·쉬는 Claude)", F(), C, "끔", None),
    ("사용자 입력 1분 전", F(**{"user.idle_s": 60, "user.locked": False}), C, "미룸", "사람"),
    ("잠금 화면·입력 10분 전", F(**{"user.idle_s": 600, "user.locked": True}), C, "끔", None),
    ("잠금 화면·입력 1분 전(암호 치는 중)", F(**{"user.idle_s": 60, "user.locked": True}), C, "미룸", "사람"),
    ("안 잠김·입력 40분 전", F(**{"user.idle_s": 2400, "user.locked": False}), C, "끔", None),
    ("전체 화면 영상", F(**{"user.notif": 3, "user.locked": False}), C, "미룸", "사람"),
    ("소리 재생 중", F(**{"user.audio": True}), C, "미룸", "사람"),
    ("Claude busy", F(claude=[{"name": "일꾼", "short": "x", "busy": True, "idle_min": 0}]), C, "미룸", "Claude"),
    ("Claude 5분 전 일함", F(claude=[{"name": "일꾼", "short": "x", "busy": False, "idle_min": 5}]), C, "미룸", "Claude"),
    ("Claude 열림만(claude_open=any)", F(), cfgx(claude_open="any"), "미룸", "Claude"),
    ("일하는 프로그램 CPU", F(procs=[P("ffmpeg.exe", core=2.0)]), C, "미룸", "프로그램"),
    ("일하는 프로그램 디스크", F(procs=[P("robocopy2.exe", io=8000)]), C, "미룸", "프로그램"),
    ("헛도는 프로그램(own.py 되찾을 것)", F(procs=[P("node.exe", core=1.0, pid=777)], reclaim=[777]), C, "끔", None),
    ("헛도는 프로그램(spin_ok 이름)", F(procs=[P("busyloop.exe", core=1.0)]), cfgx(spin_ok=["BusyLoop.exe"]), "끔", None),
    ("휴대폰과 연결 CPU 만(cpu_ok)", F(procs=[P("CrossDeviceService.exe", core=0.3)]), C, "끔", None),
    ("휴대폰과 연결 파일 전송(디스크)", F(procs=[P("CrossDeviceService.exe", core=0.3, io=4000)]), C, "미룸", "프로그램"),
    ("문턱 아래 프로그램", F(procs=[P("steam.exe", core=0.1, io=200)]), C, "끔", None),
    ("Windows 시스템 프로세스 CPU", F(procs=[P("svchost.exe", core=1.5, exe=r"C:\Windows\System32\svchost.exe")]), C, "끔", None),
    ("Windows 업데이트 설치 중", F(procs=[P("TiWorker.exe", core=0.6, exe=r"C:\Windows\WinSxS\x\TiWorker.exe")]), C, "미룸", "프로그램"),
    ("Windows 업데이트 쉼", F(procs=[P("TiWorker.exe", core=0.0, exe=r"C:\Windows\WinSxS\x\TiWorker.exe")]), C, "끔", None),
    ("설치 프로그램 창", F(procs=[P("Foo_Setup.exe")]), C, "미룸", "프로그램"),
    ("msiexec 서비스(/V)", F(procs=[P("msiexec.exe", exe=r"C:\Windows\System32\msiexec.exe", cmd=r"C:\Windows\system32\msiexec.exe /V")]), C, "끔", None),
    ("msiexec 설치", F(procs=[P("msiexec.exe", exe=r"C:\Windows\System32\msiexec.exe", cmd="msiexec /i a.msi")]), C, "미룸", "프로그램"),
    ("저장 안 된 메모장", F(windows=[W("*제목 없음 - 메모장", "notepad.exe")]), C, "미룸", "저장"),
    ("저장 안 된 VS Code", F(windows=[W("● restart.py - Claude_Brain - Visual Studio Code", "code.exe")]), C, "미룸", "저장"),
    ("한글 문서 창", F(windows=[W("보고서.hwp - 한글", "Hwp.exe")]), C, "미룸", "저장"),
    ("워드 문서 창", F(windows=[W("보고서.docx - Word", "WINWORD.EXE")]), C, "미룸", "저장"),
    ("보통 창", F(windows=[W("외부뇌 - Obsidian", "Obsidian.exe")]), C, "끔", None),
    ("받는 중인 파일", F(partial=["큰파일.zip.crdownload"]), C, "미룸", "프로그램"),
    ("망 많이 씀", F(net_kbs=3000.0), C, "미룸", "프로그램"),
    ("볼트 장부 일 도는 중", F(ledger=[{"pid": 900, "kind": "ocr", "cmd": "x"}]), C, "미룸", "프로그램"),
    ("볼트 장부 일 되찾을 것", F(ledger=[{"pid": 900, "kind": "ocr", "cmd": "x"}], reclaim=[900]), C, "끔", None),
    ("시험 잠금", F(heavy_lock=True), C, "미룸", "프로그램"),
    ("GPU 일", F(gpu=[["python.exe", 80.0]]), C, "미룸", "프로그램"),
    ("배터리", F(battery=True), C, "미룸", "전원"),
    ("배터리(설정 끔)", F(battery=True), cfgx(hold_on_battery=False), "끔", None),
    ("모름: 마지막 입력", F(**{"user.idle_s": None}), C, "미룸", "모름"),
    ("모름: 소리", F(**{"user.audio": None}), C, "미룸", "모름"),
    ("모름: Claude 장부", F(claude=None), C, "미룸", "모름"),
    ("모름: 프로그램 활동", F(procs=None), C, "미룸", "모름"),
    ("모름: GPU", F(gpu=None), C, "미룸", "모름"),
    ("모름: 창 목록", F(windows=None), C, "미룸", "모름"),
    ("모름: 망", F(net_kbs=None), C, "미룸", "모름"),
]


def main():
    bad = 0
    for name, f, c, want, kind in CASES:
        v, why = R.judge(f, c)
        ok = v == want and (kind is None or any(w[0] == kind for w in why))
        bad += not ok
        print("%s %-36s %s %s" % ("✓" if ok else "✗", name, v, " · ".join("%s:%s" % w for w in why)[:90]))

    # tick — 임시 자리 · 가짜 사실 · dry
    tmp = tempfile.mkdtemp(prefix="restart_check_")
    R.DIR, R.STATE, R.BEFORE, R.AFTER, R.LOG = tmp, os.path.join(tmp, "state.json"), os.path.join(tmp, "before.json"), os.path.join(tmp, "after.json"), os.path.join(tmp, "log.jsonl")
    sent = []
    R.notify = lambda c, t, x, dry=False: sent.append((t, x))
    R.cfg = lambda: copy.deepcopy(C)
    R.declarations = lambda: []

    seq = [0]

    def fake(f):
        seq[0] += 1
        p = os.path.join(tmp, "f%d.json" % seq[0])
        with open(p, "w", encoding="utf-8") as h:
            json.dump(f, h, ensure_ascii=False)
        return p
    T = [
        ("tick 05:00 전 = 아직", ["tick", "--dry", "--fake", fake(F()), "--now", "04:50"], 0, None),
        ("tick 켜진 지 2시간 = 건너뜀", ["tick", "--dry", "--fake", fake(F(boot=NOW - 7200)), "--now", "05:00"], 0, None),
        ("tick 사람 있음 05:15 = 미룸(3)", ["tick", "--dry", "--fake", fake(F(**{"user.idle_s": 30, "user.locked": False})), "--now", "05:15"], 3, None),
        ("tick 사람 있음 07:05 = 건너뜀+알림", ["tick", "--dry", "--fake", fake(F(**{"user.idle_s": 30, "user.locked": False})), "--now", "07:05"], 3, "오늘 자동 재시작 건너뜀"),
        ("tick 깨끗 05:30 = 끔(dry · 재시작 안 함)", ["tick", "--dry", "--fake", fake(F()), "--now", "05:30"], 0, None),
    ]
    for name, argv, rc, alert in T:
        sent.clear()
        got = R.main(argv)
        out = open(R.STATE, encoding="utf-8").read() if os.path.exists(R.STATE) else ""
        ok = got == rc and (alert is None or any(alert in s[0] for s in sent)) and not os.path.exists(R.BEFORE)
        bad += not ok
        print("%s %-36s rc=%s 알림=%s" % ("✓" if ok else "✗", name, got, [s[0] for s in sent]))

    # 하루 한 번: 오늘 상태가 «재시작»이면 다시 안 함
    with open(R.STATE, "w", encoding="utf-8") as h:
        json.dump({"day": time.strftime("%Y-%m-%d"), "status": "재시작"}, h)
    got = R.main(["tick", "--dry", "--fake", fake(F()), "--now", "05:30"])
    ok = got == 0
    bad += not ok
    print("%s %-36s rc=%s" % ("✓" if ok else "✗", "tick 오늘 이미 재시작 = 안 함", got))
    os.remove(R.STATE)

    # on 이 꺼져 있으면 dry 없이 불러도 아무것도 안 함
    R.cfg = lambda: dict(copy.deepcopy(C), on=False)
    got = R.main(["tick", "--fake", fake(F()), "--now", "05:30"])
    ok = got == 0 and not os.path.exists(R.BEFORE) and not os.path.exists(R.STATE)
    bad += not ok
    print("%s %-36s rc=%s" % ("✓" if ok else "✗", "tick 설정 끔 = 아무것도 안 함", got))
    R.cfg = lambda: copy.deepcopy(C)

    # after — 가짜 재시작 기록 · 숨은 무해 프로세스를 띄우고 잼
    mark = "restart_check_marker_%d" % os.getpid()
    items = [
        {"id": "t.up", "name": "이미 떠 있음", "when": "always", "check": {"proc": {"cmd": "restart_check\\.py"}}, "_src": "시험"},
        {"id": "t.launch", "name": "띄워야 함", "when": "always", "check": {"proc": {"cmd": mark}},
         "run": [sys.executable, "-c", "import time; time.sleep(40) # " + mark], "hidden": True, "wait_s": 20, "_src": "시험"},
        {"id": "t.was", "name": "그때 없었음", "when": "was_running", "was": {"name": "nothing.exe"}, "check": {"proc": {"name": "nothing.exe"}}, "_src": "시험"},
        {"id": "t.fail", "name": "안 뜨는 것", "when": "always", "check": {"proc": {"name": "never-ever.exe"}}, "_src": "시험"},
    ]
    R.declarations = lambda: items
    with open(R.BEFORE, "w", encoding="utf-8") as h:
        json.dump({"t": 0, "at": "시험", "was": {"t.was": False}}, h)
    sent.clear()
    got = R.main(["after"])
    a = json.load(open(R.AFTER, encoding="utf-8"))
    st = {r["id"]: r for r in a["items"]}
    ok = (got == 1 and st["t.up"]["ok"] and st["t.launch"]["ok"] and st["t.launch"]["did"] == "띄움" and "안 띄움" in st["t.was"]["state"]
          and st["t.fail"]["ok"] is False and a["bad"] == 1 and any("안 뜬 것" in s[0] for s in sent) and not os.path.exists(R.BEFORE))
    bad += not ok
    print("%s %-36s rc=%s bad=%s 알림=%s" % ("✓" if ok else "✗", "after 이미 뜸·띄움·건너뜀·실패 알림", got, a["bad"], [s[0] for s in sent]))
    try:
        import psutil
        for p in psutil.process_iter(["cmdline"]):
            if mark in " ".join(p.info["cmdline"] or []):
                p.kill()
    except Exception:  # noqa: BLE001
        pass
    got = R.main(["after"])
    ok = got == 0
    bad += not ok
    print("%s %-36s rc=%s" % ("✓" if ok else "✗", "after 기록 없음 = 할 일 없음", got))

    print("막은 재시작 명령:", BLOCKED or "없음")
    n = len(CASES) + len(T) + 4
    print("결과: %d/%d 통과" % (n - bad, n))
    return 1 if bad or BLOCKED else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
