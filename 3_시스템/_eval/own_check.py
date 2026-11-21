#!/usr/bin/env python3
"""own.py 판정 시험 — 가짜 프로세스 표·세션 장부로 R1~R3·압박·지키는 것을 잰다(진짜 프로세스는 안 건드림).

  py -3 3_시스템/_eval/own_check.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import own  # noqa: E402

NOW = 1_000_000.0
H = 3600


def P(ppid, name, start, cmd="", cpu=None, priv=100 << 20):
    return {"ppid": ppid, "name": name, "start": start, "cmd": cmd, "cpu": cpu, "priv": priv}


def S(name, last, busy=False, alive=True):
    return {"sid": name + "-0000", "short": name[:8], "name": name, "entry": "sdk-cli", "busy": busy, "last": last, "alive": alive}


def cfg(off=(), **kw):
    c = dict(own.DEFAULTS, test_avds={"test-avd-a", "test-avd-b"}, locks=[], on={r: r not in off for r in own.FEATURES})
    c.update(kw)
    return c


def run(case, procs, sess, prev=None, mach=None, ledger=None, locked=False, off=()):
    own.CFG = cfg(off)
    own.machine = lambda: mach or {"ram": 14.0, "avail": 6.0, "commit": 12.0}
    own.ledger = lambda: ledger or {}
    own.heavy_locked = lambda: locked
    kill, rows, info = own.judge(procs, sess, prev or {}, NOW)
    return {p: r for p, r, *_ in kill}


ok = fail = 0


def check(name, got, want):
    global ok, fail
    if got == want:
        ok += 1
        print("✓", name)
    else:
        fail += 1
        print("✗", name, "got", got, "want", want)


base = {1: P(0, "explorer.exe", NOW - 100 * H), 10: P(1, "claude.exe", NOW - 50 * H), 20: P(1, "claude.exe", NOW - 50 * H)}
# T1 R3: 주인 7시간 일 없음 + 배경 python 1코어(직전 tick 600초 전 CPU 0 → 지금 600) → 끔
procs = {**base, 11: P(10, "bash.exe", NOW - 70 * H, "bash -c ..."), 12: P(11, "python.exe", NOW - 70 * H, "python -", cpu=600.0)}
prev = {"t": NOW - 600, "cpu": {"12": [0.0, NOW - 70 * H], "11": [0.0, NOW - 70 * H]}}
check("T1 R3 쉬는 주인 + 1코어 배경 작업", run("t1", procs, {10: S("세션B", NOW - 7 * H)}, prev), {12: "R3"})
# T2 같은 것이지만 주인이 2시간 전에 일함 → 안 끔
check("T2 주인 최근 일함 = 안 끔", run("t2", procs, {10: S("세션B", NOW - 2 * H)}, prev), {})
# T3 주인이 일하는 중(busy) → 안 끔
check("T3 주인 일하는 중 = 안 끔", run("t3", procs, {10: S("세션B", NOW, busy=True)}, prev), {})
# T4 CPU 낮은 감시기(감시 세션 대기 명령) → 안 끔
prev4 = {"t": NOW - 600, "cpu": {"12": [599.0, NOW - 70 * H]}}
check("T4 0.002코어 감시기 = 안 끔", run("t4", procs, {10: S("감시", NOW - 7 * H)}, prev4), {})
# T5 직전 tick 없음(첫 tick) → R3 판정 안 함
check("T5 첫 tick = R3 판정 안 함", run("t5", procs, {10: S("세션B", NOW - 7 * H)}, {}), {})
# T6 pid 재사용(직전 기록의 시작 시각이 다름) → 평균 안 냄
prev6 = {"t": NOW - 600, "cpu": {"12": [0.0, NOW - 1 * H]}}
check("T6 pid 재사용 = 안 끔", run("t6", procs, {10: S("세션B", NOW - 7 * H)}, prev6), {})
# T7 R2: 볼트 시험 AVD 에뮬레이터 · 주인 없음(부모 죽음) · 잠금 없음 → 끔
emu = {**base, 30: P(999, "emulator.exe", NOW - 30 * H, "emulator.exe -avd test-avd-a -no-window"),
       31: P(30, "qemu-system-x86_64-headless.exe", NOW - 30 * H, "qemu -avd test-avd-a", priv=4 << 30)}
check("T7 R2 주인 없는 시험 에뮬레이터", run("t7", emu, {}), {30: "R2"})
# T7b 주인 없음이어도 띄운 지 4분(분리 실행해 쓰는 중일 수 있음) → 안 끔 · 11-20 01:45 잘못 끔
emu7b = {**base, 30: P(999, "emulator.exe", NOW - 240, "emulator.exe -avd test-avd-a -no-window")}
check("T7b 주인 없음 · 띄운 지 4분 = 안 끔", run("t7b", emu7b, {}), {})
# T8 같은 것 · 시험 잠금 있음 → 안 끔
check("T8 시험 잠금 = 안 끔", run("t8", emu, {}, locked=True), {})
# T9 사용자 AVD(시험 AVD 아님) → 안 끔
emu9 = {**base, 30: P(999, "emulator.exe", NOW - 30 * H, "emulator.exe -avd user-avd")}
check("T9 사용자 AVD = 안 끔", run("t9", emu9, {}), {})
# T10 시험 에뮬레이터 · 주인 1시간 쉼 → 평소 안 끔 · 압박이면 끔(문턱 0.5시간)
emu10 = {**base, 30: P(10, "emulator.exe", NOW - 3 * H, "emulator.exe -avd test-avd-b")}
sess10 = {10: S("하위", NOW - 1 * H)}
check("T10a 주인 1시간 쉼 · 평소 = 안 끔", run("t10a", emu10, sess10), {})
check("T10b 주인 1시간 쉼 · 압박 = 끔", run("t10b", emu10, sess10, mach={"ram": 14.0, "avail": 1.0, "commit": 29.0}), {30: "R2"})
# T11 격리 옵시디언(다른 프로필) 주인 없음 → 끔 · 사용자 옵시디언 → 안 끔
home = os.path.join(os.environ.get("APPDATA", ""), "obsidian")
obs = {**base, 40: P(999, "Obsidian.exe", NOW - 5 * H, "Obsidian.exe --user-data-dir=C:/tmp/test-profile --remote-debugging-port=9336"),
       41: P(1, "Obsidian.exe", NOW - 5 * H, "Obsidian.exe")}
check("T11 격리 옵시디언만", run("t11", obs, {}), {40: "R2"})
# T12 Claude 세션 자신 · 터미널은 쉬어도 안 끔
cl = {**base, 50: P(10, "claude.exe", NOW - 70 * H, "claude.exe --print", cpu=6000.0), 51: P(1, "WindowsTerminal.exe", NOW - 90 * H, "", cpu=6000.0)}
prev12 = {"t": NOW - 600, "cpu": {"50": [0.0, NOW - 70 * H], "51": [0.0, NOW - 90 * H]}}
check("T12 claude·터미널 = 안 끔", run("t12", cl, {10: S("세션B", NOW - 20 * H)}, prev12), {})
# T13 훅(훅 자리의 대본) 은 쉬는 주인 아래 오래 돌아도 안 끔
HOOK_PY = os.path.join(own.VAULT, own._sys_rel(), "hooks", "stop-check.py")   # 볼트 뿌리에서 · 이름 목록이 아니라 훅 자리로 걸리는지
hk = {**base, 60: P(10, "python.exe", NOW - 8 * H, "python " + HOOK_PY, cpu=600.0)}
check("T13 훅 = 안 끔", run("t13", hk, {10: S("세션B", NOW - 7 * H)}, {"t": NOW - 600, "cpu": {"60": [0.0, NOW - 8 * H]}}), {})
# T14 R1: 장부 · 주인 끝남 → 끔 / 주인 없이 띄움(사람) · 수명 안 넘음 → 안 끔 / 수명 넘음 → 끔 / keep + 주인 살아 있음 → 안 끔
lp = {**base, 70: P(10, "node.exe", NOW - 1 * H, "node test.mjs")}
check("T14a 장부 · 주인 끝남", run("t14a", lp, {10: S("하위", NOW, alive=False)}, ledger={70: {"pid": 70, "start": NOW - H, "owner": 10, "ttl": None}}), {70: "R1"})
check("T14b 장부 · 주인 없이 · 수명 안 넘음", run("t14b", lp, {}, ledger={70: {"pid": 70, "start": NOW - H, "owner": None, "ttl": 3 * H}}), {})
check("T14c 장부 · 수명 넘음", run("t14c", lp, {10: S("하위", NOW)}, ledger={70: {"pid": 70, "start": NOW - H, "owner": 10, "ttl": 1800}}), {70: "R1"})
check("T14d 장부 · keep · 주인 살아 있음", run("t14d", lp, {10: S("하위", NOW)}, ledger={70: {"pid": 70, "start": NOW - H, "owner": 10, "ttl": 1800, "keep": True}}), {})
# T15 가족: 부모와 자식이 둘 다 걸리면 부모만(가족째 끔)
fam = {**base, 30: P(999, "emulator.exe", NOW - 30 * H, "emulator.exe -avd test-avd-a"), 31: P(30, "qemu-system-x86_64-headless.exe", NOW - 30 * H, "qemu -avd test-avd-a")}
check("T15 가족은 맨 위만", run("t15", fam, {}), {30: "R2"})

# T17~19 R4: Claude 세션 자신 · 3일 넘게 일 없음 = 닫음 · 50시간 = 둠 · 일하는 중 = 둠 · 죽은 세션 = 셈 안 함
cs = {**base, 11: P(10, "bash.exe", NOW - 80 * H, "bash")}
check("T17 R4 80시간 쉰 세션 닫음(가족 맨 위만)", run("t17", cs, {10: S("세션A", NOW - 80 * H)}), {10: "R4"})
check("T18 50시간 = 둠", run("t18", cs, {10: S("세션A", NOW - 50 * H)}), {})
check("T19 일하는 중 = 둠", run("t19", cs, {10: S("세션A", NOW - 80 * H, busy=True)}), {})
check("T19b 죽은 세션 장부 = 셈 안 함", run("t19b", cs, {10: S("세션A", NOW - 80 * H, alive=False)}), {})

# T20~22 규칙마다 켬/끔(기능 단계 proc.reclaim.*) — 끈 규칙만 빠지고 나머지는 그대로
check("T20 배경 작업 끔 · R3 안 끔", run("t20", procs, {10: S("세션B", NOW - 7 * H)}, prev, off=("R3",)), {})
check("T20b 쉬는 세션 닫기 끔 · R4 안 끔", run("t20b", cs, {10: S("세션A", NOW - 80 * H)}, off=("R4",)), {})
check("T21 R3·R4 끔이어도 R2 는 끔", run("t21", emu, {}, off=("R3", "R4")), {30: "R2"})
check("T22 시험 프로세스 끔 · R2 안 끔", run("t22", emu, {}, off=("R2",)), {})
check("T22b 주인 끝난 것 끔 · R1 안 끔", run("t22b", lp, {10: S("하위", NOW, alive=False)}, ledger={70: {"pid": 70, "start": NOW - H, "owner": 10, "ttl": None}}, off=("R1",)), {})
check("T22c 압박 앞당기기 끔 · 압박이어도 평소 문턱", run("t22c", emu10, sess10, mach={"ram": 14.0, "avail": 1.0, "commit": 29.0}, off=("press",)), {})
check("T22d 압박 앞당기기 켬 · 압박이면 앞당김", run("t22d", emu10, sess10, mach={"ram": 14.0, "avail": 1.0, "commit": 29.0}), {30: "R2"})
# T23 이 PC 값: own.local.json 의 test_avds · locks 가 설정에 들어감 · 없으면 비움
import json as _j
d = tempfile.mkdtemp()
own.LOCAL = os.path.join(d, "own.local.json")
c0 = own.cfg({})
check("T23a 설정 파일 없음 = 시험 AVD 없음", (c0["test_avds"], c0["locks"] == own.LOCKS), (set(), True))
_j.dump({"test_avds": ["x1"], "locks": ["a/b.lock"]}, open(own.LOCAL, "w", encoding="utf-8"))
c1 = own.cfg({})
check("T23b 설정 파일 값", (c1["test_avds"], c1["locks"][-1]), ({"x1"}, "a/b.lock"))
# T24 설정에 없는 AVD 의 에뮬레이터는 시험 종류 아님(배포판 기본)
own.CFG = dict(c0)
check("T24 기본 = 에뮬레이터 안 셈", own.kind_of(P(1, "emulator.exe", NOW, "emulator.exe -avd test-avd-a")), "")

# T16 doctor 줄: 상태 파일 없으면 △
own.CFG = cfg()
own.STATE = os.path.join(tempfile.mkdtemp(), "tick.json")
st, line = own.doctor_row()
check("T16 tick 없음 = △", st, "warn")
print("%d/%d" % (ok, ok + fail))
sys.exit(1 if fail else 0)
