#!/usr/bin/env python3
"""기록 보존 순찰(코어 · 11-17 mobility 범용화 M8) — 마지막 커밋이 24시간 넘었으면 훅과 같은 커밋 진입점을 한 번 부른다.

왜: 커밋은 Claude 세션 훅(Stop·SessionEnd)에서만 돈다 — 구독이 끊기거나 며칠 안 쓰면 수집·옵시디언 편집이 커밋되지 않는다.
11-12(사용자 안 A)부터 폰 서버(mobility) 안에서 돌던 순찰을 코어로 옮겼다. 폰 모듈을 떼도 PC 기록 보존은 계속된다.

  py -3 3_시스템/autocommit.py tick [--by schedule|server]   한 번 순찰 → {"result": …} 한 줄
  py -3 3_시스템/autocommit.py status                         상태 JSON(_index/autocommit.json + 예약 주인)
  py -3 3_시스템/autocommit.py installed                      예약 «외부뇌 기록 보존»이 이 볼트를 가리키나 — 종료 0 됨 · 1 없음 · 2 모름 · 3 다른 볼트
  py -3 3_시스템/autocommit.py --install                      예약 등록(30분마다 · 사람 승인 뒤 · 다른 볼트가 맡았으면 안 함 = 종료 3)
  py -3 3_시스템/autocommit.py --remove                       이 볼트를 가리키는 예약만 지움

커밋 = `3_시스템/hooks/stop-check.py --commit-only --vault <V> --tag 기록보존` — 커밋 잠금(.autocommit.lock)·pre-commit 은 훅 그대로.
push 없음. 이 대본은 훅 본문(검사·받은함)을 대신 돌리지 않는다 — 진입점이 없는 옛 훅이면 «진입점 없음».
순찰끼리는 _index/autocommit.lock(msvcrt · 죽으면 OS 가 풂)으로 하나씩 — 예약과 폰 서버(옛 순찰 · 예약이 없을 때만)가 겹쳐도 커밋은 한 번.
상태 = 3_시스템/_index/autocommit.json(git 밖) — drift.py «자동 커밋(순찰)» 건강 줄이 읽는다. 옛 자리 _index/server/autocommit.json 은 처음 한 번 옮겨 읽는다.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
STATE = os.path.join(HERE, "_index", "autocommit.json")
OLD_STATE = os.path.join(HERE, "_index", "server", "autocommit.json")     # 11-12~11-17 폰 서버가 쓰던 자리(옮겨 읽기만)
LOCK = os.path.join(HERE, "_index", "autocommit.lock")
TASK = "외부뇌 기록 보존"
EVERY = 30 * 60                     # 예약 간격
AGE = 24 * 3600                     # 이보다 오래 커밋이 없으면 부른다
RETRY = 6 * 3600                    # 막힌 뒤 다시 해 보기까지
ALIVE = 2 * EVERY + 5 * 60          # 예약이 이 안에 돌았으면 «예약이 맡음»(폰 서버의 옛 순찰은 쉰다)
OK = ("커밋", "없음", "잠금")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def load(state=None):
    """상태 · 새 자리가 없으면 옛 자리(폰 서버)를 읽는다(막힘 알림을 다시 띄우지 않게)."""
    path = state or STATE
    d = _read(path)
    if not d and path == STATE:
        d = {k: v for k, v in _read(OLD_STATE).items() if k in ("at", "result", "fail_at", "alerted")}
    return d


def save(d, state=None):
    path = state or STATE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    os.replace(tmp, path)


class _Lock:
    """순찰끼리 하나씩 — 못 잡으면 None(다른 순찰이 도는 중)."""

    def __init__(self, path):
        self.path, self.f = path, None

    def __enter__(self):
        try:
            import msvcrt
        except ImportError:                    # 윈도 밖(시험) — 잠금 없이
            return self
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = open(self.path, "a+b")
        try:
            self.f.seek(0)
            msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.f.close()
            self.f = None
            return None
        return self

    def __exit__(self, *a):
        if self.f:
            try:
                import msvcrt
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            self.f.close()


def _hooklog(vault, msg):
    try:
        with open(os.path.join(vault, "3_시스템", "_index", "hooks.log"), "a", encoding="utf-8", newline="") as f:
            f.write("{} {}\r\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def _toast(title, body):
    if os.environ.get("BRAIN_NO_TOAST"):
        return
    try:
        sys.path.insert(0, HERE)
        import claude_bin
        claude_bin._toast(title, body)
    except Exception:
        pass


def _commit(vault):
    hook = os.path.join(vault, "3_시스템", "hooks", "stop-check.py")
    try:
        with open(hook, encoding="utf-8") as f:
            entry = "--commit-only" in f.read()
    except OSError:
        entry = False
    if not entry:                              # 진입점이 승인·적용되기 전 — 훅 본문을 대신 돌리지 않는다
        return "진입점 없음"
    py = sys.executable.replace("pythonw.exe", "python.exe")
    try:
        r = subprocess.run([py, hook, "--commit-only", "--vault", vault, "--tag", "기록보존"], capture_output=True, timeout=3600, creationflags=NOWIN)
        return json.loads(r.stdout.decode("utf-8", "replace") or "{}").get("result") or f"종료 {r.returncode}"
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return f"실패 {type(e).__name__}"


def tick(vault=None, state=None, now=None, by="schedule", lock=None):
    """한 번 순찰 → 한 일(글). 시험이 vault·state·now·lock 을 준다.
    «도는 중» = 다른 순찰이 잠금을 쥠 · «최근 커밋» · «막힌 뒤 기다림» · «잠금»(index.lock) · «진입점 없음» · 훅 결과(커밋·없음·막힘·add 실패 …)."""
    vault, now = vault or VAULT, now or time.time()
    state = state or (STATE if vault == VAULT else os.path.join(vault, "3_시스템", "_index", "autocommit.json"))
    lock = lock or (LOCK if vault == VAULT else os.path.join(vault, "3_시스템", "_index", "autocommit.lock"))
    with _Lock(lock) as held:
        if held is None:
            return "도는 중"
        st = load(state)
        res = _judge(vault, st, now)
        if res is None:
            try:
                age = now - os.stat(os.path.join(vault, ".git", "logs", "HEAD")).st_mtime
            except OSError:
                age = 0
            res = _commit(vault)
            _hooklog(vault, f"기록보존({by}) {int(age // 3600)}시간 만에: {res}")
            if res in OK:
                st = {"at": now, "result": res}
            else:
                if not st.get("alerted"):     # 막힘은 한 번만 알린다 — 풀릴 때(커밋됨)까지 다시 안 알림 · 건강 줄은 hooks.log «BLOCKED» 로 drift 가 센다
                    st["alerted"] = now
                    _toast("자동 커밋이 막혔습니다", f"{res} · 3_시스템/_index/hooks.log · 스테이지에 남은 파일 확인")
                st.update(at=now, result=res, fail_at=now)
        st.update(checked=now, last=res, by=by)
        if by == "schedule":
            st["sched_at"] = now
        save(st, state)
        return res


def _judge(vault, st, now):
    """부르지 않을 까닭 · 부를 때 None."""
    try:
        age = now - os.stat(os.path.join(vault, ".git", "logs", "HEAD")).st_mtime
    except OSError:
        return "저장소 없음"
    if age < AGE:
        return "최근 커밋"
    if st.get("fail_at") and now - st["fail_at"] < RETRY:
        return "막힌 뒤 기다림"
    if os.path.exists(os.path.join(vault, ".git", "index.lock")):
        return "잠금"
    return None


def schedule_alive(state=None, now=None):
    """예약이 최근(ALIVE 안)에 돌았나 — 폰 서버의 옛 순찰은 이때 쉰다."""
    t = load(state).get("sched_at")
    return isinstance(t, (int, float)) and 0 <= (now or time.time()) - t < ALIVE


# ───────── 예약 «외부뇌 기록 보존» ─────────

def _schtasks(*args):
    try:
        r = subprocess.run(["schtasks", *args], capture_output=True, creationflags=NOWIN, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    for enc in ("utf-8", "cp949", "utf-16"):
        try:
            return r.returncode, (r.stdout + r.stderr).decode(enc)
        except UnicodeDecodeError:
            continue
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")


ARG_PY = re.compile(r'"([^"]+autocommit\.py)"')


def owner(xml=None):
    """예약이 가리키는 볼트 → (상태, 볼트) · 상태 = 됨(이 볼트) · 없음 · 다른 볼트 · 모름. xml = 시험이 넣음."""
    if xml is None:
        rc, out = _schtasks("/Query", "/TN", TASK, "/XML")
        if rc:
            rc2, _ = _schtasks("/Query", "/FO", "CSV", "/NH")
            return ("없음", "") if rc2 == 0 else ("모름", "")
        xml = out
    m = ARG_PY.search(xml)
    if not m:
        return "모름", ""
    v = os.path.dirname(os.path.dirname(m.group(1)))
    if os.path.normcase(os.path.abspath(v)) == os.path.normcase(os.path.abspath(VAULT)):
        return "됨", v
    return ("다른 볼트", v) if os.path.isfile(m.group(1)) else ("없음", v)     # 사라진 사본을 가리키면 주인 없음 = 이 볼트가 되찾는다


def task_xml():
    """30분마다 끝없이 · 놓치면 곧 · 겹치면 새것 무시 · 1시간 · 배터리에서도 · PC 를 깨우지 않음 · 로그온한 사용자 권한(창 없음 = pyw)."""
    import shutil
    from xml.sax.saxutils import escape
    start = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 120))
    pyw = shutil.which("pyw") or r"C:\Windows\pyw.exe"
    args = f'-3 "{os.path.abspath(__file__)}" tick --by schedule'
    return ('<?xml version="1.0" encoding="UTF-16"?>\n<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
            f'<RegistrationInfo><Description>{escape("외부뇌 기록 보존: 마지막 커밋이 24시간 넘으면 훅과 같은 커밋을 한 번(push 없음) · 3_시스템/autocommit.py")}</Description></RegistrationInfo>'
            f'<Triggers><TimeTrigger><Repetition><Interval>PT30M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>'
            f'<StartBoundary>{start}</StartBoundary><Enabled>true</Enabled></TimeTrigger></Triggers>'
            '<Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>'
            '<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>'
            '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable>'
            '<ExecutionTimeLimit>PT1H</ExecutionTimeLimit><Priority>7</Priority>'
            '<IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings></Settings>'
            f'<Actions Context="Author"><Exec><Command>{escape(pyw)}</Command><Arguments>{escape(args)}</Arguments><WorkingDirectory>{escape(VAULT)}</WorkingDirectory></Exec></Actions></Task>')


def install():
    st, v = owner()
    if st == "다른 볼트":
        print(f"{TASK}: 다른 볼트가 맡음({v}) — 덮지 않음")
        return 3
    if st == "모름":
        print(f"{TASK}: 예약 목록을 못 읽음 — 등록 안 함")
        return 2
    fd, tmp = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-16") as f:
            f.write(task_xml())
        rc, out = _schtasks("/Create", "/TN", TASK, "/XML", tmp, "/F")
    finally:
        os.remove(tmp)
    print(f"{TASK}: " + ("30분마다(이 볼트)" if rc == 0 else "못 등록 " + out.strip()[-200:]))
    return 0 if rc == 0 else 1


def remove():
    st, v = owner()
    if st != "됨":
        print(f"{TASK}: 이 볼트 예약이 아님({st}{' · ' + v if v else ''}) — 안 지움")
        return 0 if st == "없음" else 1
    rc, out = _schtasks("/Delete", "/TN", TASK, "/F")
    print(f"{TASK}: " + ("지움" if rc == 0 else "못 지움 " + out.strip()[-200:]))
    return rc


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.path.insert(0, HERE)
    try:
        import nowin
        nowin.install()                        # 예약(pyw)으로 돌면 콘솔이 없다 — 훅·git 이 보이는 창을 띄우지 않게
    except Exception:
        pass
    if "--install" in argv:
        return install()
    if "--remove" in argv:
        return remove()
    cmd = argv[0] if argv and not argv[0].startswith("-") else "tick"
    if cmd == "installed":
        st, v = owner()
        print(st + (f" · {v}" if v and st != "됨" else ""))
        return {"됨": 0, "없음": 1, "모름": 2, "다른 볼트": 3}[st]
    if cmd == "status":
        st, v = owner()
        print(json.dumps({**load(), "task": st, "schedule_alive": schedule_alive()}, ensure_ascii=False))
        return 0
    if cmd == "tick":
        by = argv[argv.index("--by") + 1] if "--by" in argv and argv.index("--by") + 1 < len(argv) else "schedule"
        print(json.dumps({"result": tick(by=by)}, ensure_ascii=False))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
