"""기록 보존 순찰(코어 3_시스템/autocommit.py · M8 11-17) 시험 — 임시 저장소에서 24시간 흉내. 진짜 볼트 git·예약은 건드리지 않는다.

  py -3 3_시스템/_eval/autocommit_check.py [<고친 stop-check.py>]   # 기본 = 3_시스템/hooks/stop-check.py

잰다: 24시간 안 = 안 부름 · 넘음 = 커밋(session:·user: 둘) · index.lock = 건너뜀 · pre-commit 막힘 = «막힘» + 알림 한 번(다시 안 알림 · 6시간 기다림)
· 풀리면 커밋·알림 지움 · 진입점 없는 옛 훅 = 안 부름 · push 없음 · 두 순찰(예약 + 폰 서버 옛 순찰)이 겹쳐도 커밋 한 번
· 예약이 돌면 schedule_alive(폰 서버는 쉼) · 옛 상태 자리 옮겨 읽기 · 예약 주인 가름(이 볼트·다른 볼트·사라진 사본) · drift 건강 줄이 새 자리를 읽음
· 예약 XML 에 이 볼트 대본·30분 · Stop 훅 길 = 고치기 전과 같은 커밋.
"""
# mf:allow-path-file — 시험 픽스처: 임시 볼트 안의 1_수집·3_시스템 자리를 만들고 잰다(본 볼트 안 건드림)
import json, os, shutil, subprocess, sys, tempfile, threading, time

SYS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, SYS)
NEW = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(SYS, "hooks", "stop-check.py")
OLD = os.path.join(SYS, "hooks", "stop-check.py")
rows, fails = [], []


def ok(name, cond, got=""):
    rows.append(name)
    if not cond:
        fails.append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  — {str(got)[:300]}"), flush=True)


def git(repo, *a):
    r = subprocess.run(["git", "-C", repo] + list(a), capture_output=True)
    return r.stdout.decode("utf-8", "replace").strip()


def repo(root, name, hook):
    v = os.path.join(root, name)
    for d in ("2_지식", "1_수집", os.path.join("3_시스템", "hooks"), os.path.join("3_시스템", "_index")):
        os.makedirs(os.path.join(v, d), exist_ok=True)
    shutil.copy2(hook, os.path.join(v, "3_시스템", "hooks", "stop-check.py"))
    shutil.copy2(os.path.join(SYS, "roles.json"), os.path.join(v, "3_시스템", "roles.json"))
    open(os.path.join(v, "2_지식", "MOC.md"), "w", encoding="utf-8").write("---\ntitle: MOC\n---\n# MOC\n")
    open(os.path.join(v, ".gitignore"), "w").write("3_시스템/_index/\n")
    git(v, "init", "-q")
    git(v, "config", "user.name", "t")
    git(v, "config", "user.email", "t@t")
    git(v, "add", "-A")
    git(v, "commit", "-q", "-m", "처음")
    return v


def old_head(v, hours=25):
    p = os.path.join(v, ".git", "logs", "HEAD")
    t = time.time() - hours * 3600
    os.utime(p, (t, t))


def change(v, n):
    open(os.path.join(v, "2_지식", f"노트{n}.md"), "w", encoding="utf-8").write(f"---\ntitle: {n}\n---\n본문 {n}\n")
    open(os.path.join(v, "1_수집", f"원본{n}.txt"), "w", encoding="utf-8").write(f"원본 {n}\n")


def main():
    import autocommit as ac
    toasts = []
    import claude_bin
    claude_bin._toast = lambda t, b: toasts.append(t)
    os.environ.pop("BRAIN_NO_TOAST", None)
    root = tempfile.mkdtemp(prefix="autocommit-")
    try:
        run(ac, toasts, root)
    finally:
        def unlock(fn, p, _e):                   # git 객체는 읽기 전용 — 윈도에서 rmtree 가 조용히 남긴다(옛 시험 임시 폴더가 남은 까닭)
            os.chmod(p, 0o700)
            fn(p)
        shutil.rmtree(root, onerror=unlock)
    print(f"\n합계 {len(rows) - len(fails)}/{len(rows)} 통과" + (f" · 실패 {fails}" if fails else ""))
    sys.exit(1 if fails else 0)


def run(ac, toasts, root):
    v = repo(root, "v", NEW)
    st = os.path.join(v, "3_시스템", "_index", "autocommit.json")
    tick = lambda now=None, by="schedule": ac.tick(vault=v, now=now, by=by)

    change(v, 1)
    ok("24시간 안 = 안 부름", tick() == "최근 커밋", tick())
    n0 = git(v, "rev-list", "--count", "HEAD")
    old_head(v)
    r = tick()
    subj = git(v, "log", "-2", "--format=%s|%an").splitlines()
    ok("24시간 넘음 = 커밋(볼트 session: Claude · 1_수집 user: User)", r == "커밋" and len(subj) == 2 and subj[0].startswith("user: ") and subj[1].startswith("session: ") and "Claude" in subj[1], f"{r} {subj}")
    ok("깨끗해짐", git(v, "status", "--porcelain") == "", git(v, "status", "--porcelain"))
    ok("push 없음(원격 없음 · 오류 없음)", git(v, "remote") == "" and r == "커밋")
    hl = open(os.path.join(v, "3_시스템", "_index", "hooks.log"), encoding="utf-8").read()
    ok("hooks.log 에 «기록보존(schedule)» 줄", "기록보존(schedule) " in hl and ": 커밋" in hl, hl[-200:])
    s = json.load(open(st, encoding="utf-8"))
    ok("상태 = 새 자리(_index/autocommit.json) · 예약이 돈 시각", s.get("result") == "커밋" and s.get("sched_at") and s.get("by") == "schedule", s)
    ok("예약이 돌았으면 schedule_alive(폰 서버 옛 순찰은 쉼)", ac.schedule_alive(state=st) is True and ac.schedule_alive(state=st, now=time.time() + 2 * 3600) is False)

    change(v, 2)
    old_head(v)
    open(os.path.join(v, ".git", "index.lock"), "w").close()
    ok("index.lock = 건너뜀", tick() == "잠금" and git(v, "rev-list", "--count", "HEAD") == str(int(n0) + 2))
    os.remove(os.path.join(v, ".git", "index.lock"))

    # 두 순찰(예약 + 폰 서버)이 겹쳐도 커밋 한 번 — 한쪽이 순찰 잠금을 쥔 동안 다른 쪽 = «도는 중»
    lockp = os.path.join(v, "3_시스템", "_index", "autocommit.lock")
    held = ac._Lock(lockp).__enter__()
    try:
        r_other = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, {SYS!r}); import autocommit as a; print(a.tick(vault={v!r}, by='server'))"],
                                 capture_output=True, timeout=120).stdout.decode("utf-8", "replace").strip()
    finally:
        held.__exit__()
    ok("순찰 잠금을 다른 프로세스가 쥐면 = «도는 중»(커밋 안 함)", r_other == "도는 중" and git(v, "rev-list", "--count", "HEAD") == str(int(n0) + 2), r_other)
    outs = []
    ths = [threading.Thread(target=lambda: outs.append(subprocess.run(
        [sys.executable, "-c", f"import sys; sys.path.insert(0, {SYS!r}); import autocommit as a; print(a.tick(vault={v!r}, by={by!r}))"],
        capture_output=True, timeout=600).stdout.decode("utf-8", "replace").strip())) for by in ("schedule", "server")]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    added = int(git(v, "rev-list", "--count", "HEAD")) - (int(n0) + 2)
    ok("두 순찰이 같은 때 = 커밋 한 벌(session:+user:)", added == 2 and outs.count("커밋") == 1, f"{outs} 늘어난 커밋 {added}")

    change(v, 3)
    old_head(v)
    hook = os.path.join(v, ".git", "hooks", "pre-commit")
    open(hook, "w", newline="\n").write("#!/bin/sh\necho 비밀값 흉내 >&2\nexit 1\n")
    os.chmod(hook, 0o755)
    now = time.time()
    r1 = tick(now)
    s1 = json.load(open(st, encoding="utf-8"))
    hl = open(os.path.join(v, "3_시스템", "_index", "hooks.log"), encoding="utf-8").read()
    ok("pre-commit 막힘 = «막힘» · hooks.log BLOCKED(건강 줄) · 알림 1", r1 == "막힘" and "기록보존 commit BLOCKED" in hl and len(toasts) == 1 and s1.get("alerted"), f"{r1} {toasts} {hl[-160:]}")
    r2 = tick(now + 60)
    ok("막힌 뒤 6시간은 다시 안 함", r2 == "막힌 뒤 기다림", r2)
    r3 = tick(now + 7 * 3600)
    ok("6시간 뒤 다시 해도 막힘 = 알림 안 되풀이", r3 == "막힘" and len(toasts) == 1, f"{r3} {toasts}")
    os.remove(hook)
    git(v, "reset", "-q")
    old_head(v)
    r4 = tick(now + 14 * 3600)
    s4 = json.load(open(st, encoding="utf-8"))
    ok("풀리면 커밋 · 알림 표시 지움", r4 == "커밋" and not s4.get("alerted") and not s4.get("fail_at"), f"{r4} {s4}")

    if "--commit-only" not in open(OLD, encoding="utf-8").read():
        w = repo(root, "w", OLD)
        change(w, 1)
        old_head(w)
        ok("진입점 없는 옛 훅 = 안 부름(훅 본문을 대신 안 돌림)", ac.tick(vault=w) == "진입점 없음" and git(w, "status", "--porcelain") != "")

    # 옛 상태 자리(폰 서버가 쓰던 _index/server/autocommit.json) 옮겨 읽기 — 막힘 알림을 다시 띄우지 않게
    o_state, o_old = ac.STATE, ac.OLD_STATE
    try:
        ac.STATE, ac.OLD_STATE = os.path.join(root, "new.json"), os.path.join(root, "old.json")
        json.dump({"at": 1, "result": "막힘", "fail_at": 1, "alerted": 1, "checked": 5}, open(ac.OLD_STATE, "w", encoding="utf-8"))
        got = ac.load()
        ok("옛 자리 상태를 옮겨 읽음(at·result·fail_at·alerted)", got == {"at": 1, "result": "막힘", "fail_at": 1, "alerted": 1}, got)
    finally:
        ac.STATE, ac.OLD_STATE = o_state, o_old

    # 예약 주인 가름 — 진짜 예약은 읽기·쓰기 안 함(xml 을 넣음)
    me = os.path.abspath(ac.__file__)
    other = os.path.join(root, "other", "3_시스템", "autocommit.py")
    os.makedirs(os.path.dirname(other))
    open(other, "w").close()
    gone = os.path.join(root, "gone", "3_시스템", "autocommit.py")
    ok("예약 주인: 이 볼트 = 됨", ac.owner(f'<Arguments>-3 "{me}" tick</Arguments>')[0] == "됨")
    ok("예약 주인: 다른 볼트(대본 있음) = 다른 볼트 → 설치가 안 덮음", ac.owner(f'<Arguments>-3 "{other}" tick</Arguments>')[0] == "다른 볼트")
    ok("예약 주인: 사라진 사본 = 없음(되찾음)", ac.owner(f'<Arguments>-3 "{gone}" tick</Arguments>')[0] == "없음")
    x = ac.task_xml()
    ok("예약 XML = 이 볼트 대본 · 30분 · 배터리에서도 · pyw(창 없음)", me in x and "PT30M" in x and "<StopIfGoingOnBatteries>false" in x and "pyw" in x.lower() and "tick --by schedule" in x)

    # drift 건강 줄이 새 자리를 읽는다(실패만 · 막힘은 BLOCKED 줄이 센다)
    src = open(os.path.join(SYS, "drift.py"), encoding="utf-8").read()
    ok("drift.py 가 새 상태 자리(_index/autocommit.json)를 읽음", '"_index", "autocommit.json"' in src and "자동 커밋(순찰)" in src)

    # Stop 훅 길 = 고치기 전과 같은 커밋(같은 바뀜 · 옛 훅 vs 새 훅)
    a, b = repo(root, "a", OLD), repo(root, "b", NEW)
    for x in (a, b):
        change(x, 9)
        subprocess.run([sys.executable, os.path.join(x, "3_시스템", "hooks", "stop-check.py")], input=b"{}", capture_output=True, timeout=300)
    for _ in range(120):                       # Stop 훅은 커밋을 뒤에서 띄운다(11-16 commit_behind) — 둘 다 끝날 때까지
        if all(git(x, "rev-list", "--count", "HEAD") == "3" and not git(x, "status", "--porcelain") for x in (a, b)):
            break
        time.sleep(0.5)
    la = git(a, "log", "--format=%s|%an", "-3")
    lb = git(b, "log", "--format=%s|%an", "-3")
    fa = git(a, "show", "--stat", "--format=", "HEAD~1..HEAD")
    fb = git(b, "show", "--stat", "--format=", "HEAD~1..HEAD")
    ok("Stop 훅 길 = 옛 훅과 같은 커밋(제목·저자·파일)", la == lb and fa == fb and la.count("|") == 3, f"{la!r} vs {lb!r}")


if __name__ == "__main__":
    main()
