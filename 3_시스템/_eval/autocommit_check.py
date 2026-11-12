"""서버 자동 커밋(11-12 · 사용자 안 A) 시험 — 임시 저장소에서 24시간 흉내. 진짜 볼트 git 은 건드리지 않는다.

  py -3 3_시스템/_eval/autocommit_check.py <고친 stop-check.py>   # 승인 전 = 사본 경로 · 적용 뒤 = 3_시스템/hooks/stop-check.py

잰다: 24시간 안 = 안 부름 · 넘음 = 커밋(session:·user: 둘) · index.lock = 건너뜀 · pre-commit 막힘 = «막힘» + 알림 한 번(다시 안 알림 · 6시간 기다림)
· 풀리면 커밋·알림 지움 · 진입점 없는 옛 훅 = 안 부름 · push 없음 · Stop 훅 길 = 고치기 전과 같은 커밋.
"""
import json, os, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)
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
    import server
    toasts = []
    import claude_bin
    claude_bin._toast = lambda t, b: toasts.append(t)
    os.environ.pop("BRAIN_NO_TOAST", None)
    root = tempfile.mkdtemp(prefix="autocommit-")
    server.LOG, server.STATE = os.path.join(root, "server.log"), root     # 진짜 서버 로그에 시험 줄이 섞였다(11-12 · 막힘·커밋 줄 둘)
    st = os.path.join(root, "autocommit.json")
    v = repo(root, "v", NEW)
    tick = lambda now=None: server.autocommit_tick(vault=v, state=st, now=now)

    change(v, 1)
    ok("24시간 안 = 안 부름", tick() == "최근 커밋", tick())
    n0 = git(v, "rev-list", "--count", "HEAD")
    old_head(v)
    r = tick()
    subj = git(v, "log", "-2", "--format=%s|%an").splitlines()
    ok("24시간 넘음 = 커밋(볼트 session: Claude · 1_수집 user: User)", r == "커밋" and len(subj) == 2 and subj[0].startswith("user: ") and subj[1].startswith("session: ") and "Claude" in subj[1], f"{r} {subj}")
    ok("깨끗해짐", git(v, "status", "--porcelain") == "", git(v, "status", "--porcelain"))
    ok("push 없음(원격 없음 · 오류 없음)", git(v, "remote") == "" and r == "커밋")

    change(v, 2)
    old_head(v)
    open(os.path.join(v, ".git", "index.lock"), "w").close()
    ok("index.lock = 건너뜀", tick() == "잠금" and git(v, "rev-list", "--count", "HEAD") == str(int(n0) + 2))
    os.remove(os.path.join(v, ".git", "index.lock"))

    hook = os.path.join(v, ".git", "hooks", "pre-commit")
    open(hook, "w", newline="\n").write("#!/bin/sh\necho 비밀값 흉내 >&2\nexit 1\n")
    os.chmod(hook, 0o755)
    now = time.time()
    r1 = tick(now)
    s1 = json.load(open(st, encoding="utf-8"))
    hl = open(os.path.join(v, "3_시스템", "_index", "hooks.log"), encoding="utf-8").read()
    ok("pre-commit 막힘 = «막힘» · hooks.log BLOCKED(건강 줄) · 알림 1", r1 == "막힘" and "서버 commit BLOCKED" in hl and len(toasts) == 1 and s1.get("alerted"), f"{r1} {toasts} {hl[-120:]}")
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

    w = repo(root, "w", OLD if "--commit-only" not in open(OLD, encoding="utf-8").read() else NEW)
    if "--commit-only" not in open(OLD, encoding="utf-8").read():
        change(w, 1)
        old_head(w)
        ok("진입점 없는 옛 훅 = 안 부름(훅 본문을 대신 안 돌림)", server.autocommit_tick(vault=w, state=os.path.join(root, "w.json")) == "진입점 없음" and git(w, "status", "--porcelain") != "")

    # Stop 훅 길 = 고치기 전과 같은 커밋(같은 바뀜 · 옛 훅 vs 새 훅)
    a, b = repo(root, "a", OLD), repo(root, "b", NEW)
    for x in (a, b):
        change(x, 9)
        subprocess.run([sys.executable, os.path.join(x, "3_시스템", "hooks", "stop-check.py")], input=b"{}", capture_output=True, timeout=300)
    la = git(a, "log", "--format=%s|%an", "-3")
    lb = git(b, "log", "--format=%s|%an", "-3")
    fa = git(a, "show", "--stat", "--format=", "HEAD~1..HEAD")
    fb = git(b, "show", "--stat", "--format=", "HEAD~1..HEAD")
    ok("Stop 훅 길 = 옛 훅과 같은 커밋(제목·저자·파일)", la == lb and fa == fb and la.count("|") == 3, f"{la!r} vs {lb!r}")

    shutil.rmtree(root, ignore_errors=True)
    print(f"\n합계 {len(rows) - len(fails)}/{len(rows)} 통과" + (f" · 실패 {fails}" if fails else ""))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
