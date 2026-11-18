"""PC 메모리 건강 줄(drift.mem_rows · 11-18) 시험 — 가짜 값으로 줄마다 뜨고 사라지는지 · 남은 시험 프로세스 끄기는 가짜 프로세스로.
진짜 프로세스는 끄지 않는다(끄기 시험은 넣어 준 가짜 목록의 pid 만).

  py -3 3_시스템/_eval/mem_check.py

잰다: 메모리 넘침(커밋 > 램 1.5배 · 큰 것 셋) ↔ ✓ 줄 · 켜진 지 7일 넘음 = 재부팅 · NVIDIA 오버레이 · 남은 시험 프로세스(에뮬레이터·adb·격리 옵시디언 —
기본 프로필 옵시디언·렌더러는 안 셈) · 시험 잠금이 있으면 안 뜸 · 묵은 잠금(6시간 넘음)은 안 셈 · 못 잰 칸은 조용히 빠짐 · 끄기 = 자식째 · 잠금이면 안 끔
· 실제 PC 재기 1초 안 · brain.py doctor 가 이 줄을 부름.
"""
import os, subprocess, sys, tempfile, time

SYS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, SYS)
import drift  # noqa: E402

fails = []
GB = 2 ** 30


def ok(name, cond, got=""):
    if not cond:
        fails.append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  — {str(got)[:400]}"), flush=True)


def names(rows):
    return {n: (s, t) for n, s, t in rows}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    big = {1: (0, "claude.exe", 6 * GB, ""), 2: (0, "claude.exe", 5 * GB, ""), 3: (0, "NVIDIA Overlay.exe", int(1.75 * GB), ""),
           4: (0, "WindowsTerminal.exe", int(1.45 * GB), ""), 5: (0, "pwsh.exe", int(0.1 * GB), "")}
    r = names(drift.mem_rows({"ram": 13.9, "commit": 29.0, "up_days": 3.5, "procs": big}, locked=False))
    ok("M1 커밋 29 > 램 13.9×1.5 = «메모리 넘침 29/13.9 GB» · 큰 것 셋(이름별 합 · 0.5GB 넘는 것)",
       r.get("메모리") == ("warn", "메모리 넘침 29/13.9 GB(커밋/램) · 큰 것: claude 2개 11.0GB, NVIDIA Overlay 1.8GB, WindowsTerminal 1.4GB"), r.get("메모리"))
    ok("M2 NVIDIA 오버레이가 돌면 한 줄", r.get("NVIDIA 오버레이") == ("warn", "NVIDIA 오버레이 켜짐(약 1.8GB) · NVIDIA 앱에서 끔"), r.get("NVIDIA 오버레이"))
    ok("M3 켜진 지 3.5일 = 재부팅 줄 없음 · 시험 프로세스 없음 = 줄 없음", "재부팅" not in r and "시험 프로세스" not in r, r)
    calm = {1: (0, "claude.exe", 2 * GB, "")}
    r = names(drift.mem_rows({"ram": 13.9, "commit": 18.0, "up_days": 8.4, "procs": calm}, locked=False))
    ok("M4 커밋 18 ≤ 20.9 = 넘침 사라짐(✓ 커밋/램 한 줄) · 오버레이 꺼짐 = 줄 사라짐",
       r.get("메모리") == ("ok", "커밋 18/13.9 GB(램의 1.3배)") and "NVIDIA 오버레이" not in r, r)
    ok("M5 켜진 지 8.4일 = «켜진 지 8일 · 재부팅 권함»", r.get("재부팅") == ("warn", "켜진 지 8일 · 재부팅 권함"), r.get("재부팅"))

    prof = os.path.join(tempfile.gettempdir(), "obs-test-profile")
    appdata = os.path.join(os.environ.get("APPDATA", "C:\\x"), "obsidian")
    tp = {10: (0, "qemu-system-x86_64.exe", GB, ""), 11: (10, "emulator.exe", 0, ""), 12: (0, "adb.exe", 0, ""),
          13: (0, "Obsidian.exe", 0, f'"C:\\Obsidian\\Obsidian.exe" --user-data-dir={prof} --remote-debugging-port=9336'),
          14: (13, "Obsidian.exe", 0, f"C:\\Obsidian\\Obsidian.exe --type=renderer --user-data-dir={prof}"),
          15: (0, "Obsidian.exe", 0, "C:\\Obsidian\\Obsidian.exe"),
          16: (15, "Obsidian.exe", 0, f"C:\\Obsidian\\Obsidian.exe --type=renderer --user-data-dir={appdata}"),
          17: (0, "Obsidian.exe", 0, f'"C:\\Obsidian\\Obsidian.exe" "--user-data-dir={prof} 2"')}
    left = sorted(drift.test_procs(tp))
    ok("M6 시험 프로세스 = 에뮬레이터(qemu·emulator) · adb · 격리 옵시디언 주 프로세스(따옴표 경로도) — 기본 프로필·렌더러는 안 셈",
       left == [(10, "에뮬레이터"), (11, "에뮬레이터"), (12, "adb"), (13, "격리 옵시디언"), (17, "격리 옵시디언")], left)
    r = names(drift.mem_rows({"procs": tp}, locked=False))
    ok("M7 시험 잠금 없음 = «남은 시험 프로세스 5개(…)» + 끄기 명령(«고치기»로)",
       r.get("시험 프로세스", ("", ""))[0] == "warn" and r["시험 프로세스"][1].startswith("남은 시험 프로세스 5개(에뮬레이터 2, adb 1, 격리 옵시디언 2)")
       and drift.KILL_CMD in r["시험 프로세스"][1], r.get("시험 프로세스"))
    ok("M8 시험 잠금 있음 = 줄 사라짐", "시험 프로세스" not in names(drift.mem_rows({"procs": tp}, locked=True)))
    ok("M9 못 잰 칸은 조용히 빠짐(값 없음 = 줄 없음 · 프로세스만 = 메모리 줄 없음)",
       drift.mem_rows({}, locked=False) == [] and "메모리" not in names(drift.mem_rows({"procs": calm}, locked=False)))

    keep = drift.HERE
    tmp = tempfile.mkdtemp(prefix="memchk-")
    try:
        drift.HERE = tmp
        lk = os.path.join(tmp, "_index", "bigboss", "run-x", "heavy.lock")
        os.makedirs(os.path.dirname(lk))
        no_lock = drift.heavy_locked()
        open(lk, "w").close()
        fresh = drift.heavy_locked()
        os.utime(lk, (time.time() - 7 * 3600,) * 2)
        stale = drift.heavy_locked()
        ok("M10 잠금 = 있을 때만 · 6시간 넘은 묵은 잠금은 안 셈", not no_lock and fresh and not stale, (no_lock, fresh, stale))
    finally:
        drift.HERE = keep
        try:
            os.remove(lk)
            os.removedirs(os.path.dirname(lk))
        except OSError:
            pass

    # 끄기 — 가짜 «adb»(파이썬)와 그 자식만 넣은 목록으로. 진짜 adb·에뮬레이터는 목록에 없어 안 끈다.
    fake = subprocess.Popen([sys.executable, "-c", "import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); time.sleep(60)"])
    time.sleep(1.0)
    kid = [p for p, row in drift.processes().items() if row[0] == fake.pid and row[1].lower() == "python.exe"]
    procs = {fake.pid: (os.getpid(), "adb.exe", 0, "")}
    procs.update({k: (fake.pid, "python.exe", 0, "") for k in kid})
    held = drift.kill_test(procs, locked=True)
    ok("M11 시험 잠금이 있으면 안 끔", held is None and fake.poll() is None and all(drift._start(k) for k in kid), (held, kid))
    done = drift.kill_test(procs, locked=False)
    time.sleep(0.5)
    ok("M12 끄기 = 넣은 목록의 시험 프로세스를 자식째", done == [(fake.pid, "adb", True)] and fake.poll() is not None and len(kid) == 1 and drift._start(kid[0]) is None, (done, kid))
    for k in kid:
        if drift._start(k):
            subprocess.run(["taskkill", "/F", "/PID", str(k)], capture_output=True)

    t = time.time()
    m = drift.machine()
    took = time.time() - t
    ok("M13 실제 PC 재기 1초 안 · 램·커밋·켜진 날·프로세스", took < 1.0 and m.get("ram", 0) > 1 and m.get("commit", 0) > 0 and m.get("up_days", -1) >= 0 and len(m.get("procs") or {}) > 20,
       f"{took:.2f}초 {[(k, v if not isinstance(v, dict) else len(v)) for k, v in m.items()]}")
    src = open(os.path.join(SYS, "brain.py"), encoding="utf-8").read()
    ok("M14 건강 창(brain.py doctor)이 이 줄을 부름", "drift.mem_rows()" in src)
    print(f"== 실패 {len(fails)}건" + (": " + " · ".join(fails) if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
