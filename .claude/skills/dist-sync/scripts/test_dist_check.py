"""dist-check 시험 — 임시 사본(볼트·배포판 worktree·원격)에 어긋남을 하나씩 만들어 센다.

  py -3 .claude/skills/dist-sync/scripts/test_dist_check.py

0 = 어긋남 없는 사본 → 0건(익명화로 늘 다른 파일·시각만 바뀐 파일은 안 잡힘)
① 볼트만 고침 → 안 올린 고침 1 · ② 배포판 커밋 push 안 함 → 1 · ③ 원격만 앞섬 → 받을 것 1
덤: 볼트에서 지운 코어 · 배포판 worktree 의 커밋 안 한 고침 · 안 싣기로 적은 판(ack)
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("dist_check", os.path.join(HERE, "dist-check.py"))
dc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dc)

FAIL = []
TASK = "3_시스템/demo-task.ps1"  # mf:allow-path  (임시 저장소 안 · 볼트 밖 설정 추적 시험)
PY = "3_시스템/search.py"  # mf:allow-path  (임시 사본 안의 코어 자리 — 진짜 볼트는 안 건드림)


def run(cwd, *args, env=None):
    e = dict(os.environ, **(env or {}))
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main", *args],
                       cwd=cwd, capture_output=True, env=e)
    if r.returncode:
        raise RuntimeError("git %s: %s" % (" ".join(args), r.stderr.decode("utf-8", "replace")))
    return r.stdout.decode("utf-8", "replace").strip()


def put(root, rel, text, mtime=None):
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    if mtime:
        os.utime(p, (mtime, mtime))


def counts(r):
    return (len(r["unsynced"]), len(r["uncommitted"]), len(r["unpushed"]), len(r["remote_only"]))


def expect(name, r, want):
    got = counts(r)
    ok = got == want
    print("%s %s — 안 올린 고침·커밋 안 함·push 안 함·받을 것 = %s%s" % ("✓" if ok else "✗", name, got, "" if ok else " (기대 %s)" % (want,)))
    if not ok:
        FAIL.append(name)
        print(dc.report(r))
    return ok


def load_doctor(vault, cache):
    s = importlib.util.spec_from_file_location("dist_doctor", os.path.join(HERE, "doctor.py"))
    d = importlib.util.module_from_spec(s)
    s.loader.exec_module(d)
    d.VAULT, d.CACHE = vault, cache
    return d


def doctor_line(d):
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = d.main()
    return code, (buf.getvalue().strip().splitlines() or [""])[-1]


def external_tests(A, E):
    """볼트 밖 설정 — 추적(scan)이 목록 없는 볼트 밖 코드를 잡고 · 확인 명령이 안 된 설정을 «안 됨»으로 재는가."""
    s = importlib.util.spec_from_file_location("dist_external", os.path.join(HERE, "external.py"))
    ex = importlib.util.module_from_spec(s)
    s.loader.exec_module(ex)
    os.makedirs(E)
    run(E, "init")
    put(E, TASK, "Register-ScheduledTask -TaskName demo\n")
    run(E, "add", ".")
    item = {"id": "demo-task", "이름": "예약", "종류": ["작업 스케줄러"], "쓰는 곳": [TASK], "확인": "exit 0", "안내": ["하나", "둘"]}
    gaps, _ = ex.scan([E], items=[])
    ok = [g[:2] for g in gaps] == [(TASK, "작업 스케줄러")]
    gaps2, bad2 = ex.scan([E], items=[item])
    gaps3, bad3 = ex.scan([E], items=[dict(item, 종류=["레지스트리"])])
    _, bad4 = ex.scan([E], items=[dict(item, 확인="", 안내=["하나"])])
    ok = ok and not gaps2 and not bad2 and len(gaps3) == 1 and len(bad4) == 2
    print("%s 바깥 설정 추적 — 목록 없음 %d · 덮음 %d · 종류 다름 %d · 항목 결함 %d" % ("✓" if ok else "✗", len(gaps), len(gaps2), len(gaps3), len(bad4)))
    if not ok:
        FAIL.append("바깥 설정 추적")
    # 확인 명령 — 진짜 목록의 git 두 칸을 «안 된» 저장소(훅 없음·가지 없음)에서
    items = {it["id"]: it for it in ex.load()}
    run(E, "commit", "-q", "-m", "x")
    run(E, "checkout", "-q", "--detach")
    got = {i: ex.run(items[i]["확인"], cwd=E) for i in ("git-hooks", "git-branch")}
    run(E, "config", "core.hooksPath", "3_시스템/hooks")  # mf:allow-path  (임시 저장소의 git 설정)
    run(E, "switch", "-q", "-c", "work")
    got2 = {i: ex.run(items[i]["확인"], cwd=E) for i in ("git-hooks", "git-branch")}
    ok = set(got.values()) == {False} and set(got2.values()) == {True}
    print("%s 바깥 설정 확인 — 안 했을 때 %s · 한 뒤 %s" % ("✓" if ok else "✗", got, got2))
    if not ok:
        FAIL.append("바깥 설정 확인")
    rows = ex.check(A)          # 임시 볼트에는 검색 대본만 있다 — 그것을 쓰는 항목만 묻는다
    want = {it["id"] for it in items.values() if PY in it["쓰는 곳"]}
    ok = {r["id"] for r in rows} == want and want
    print("%s 있는 기능만 물음 — %s" % ("✓" if ok else "✗", sorted(r["id"] for r in rows)))
    if not ok:
        FAIL.append("있는 기능만 물음")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    tmp = tempfile.mkdtemp(prefix="distcheck-")
    try:
        R, A, B, C = (os.path.join(tmp, x) for x in ("remote.git", "vault", "dist", "other"))
        run(tmp, "init", "--bare", R)
        # 볼트 — 코어 둘 + 실명이 든 README(배포판과 늘 다름) + 볼트에만 있는 오래된 코어
        files = {".claude/skills/demo/SKILL.md": "demo v1\n", PY: "print(1)\n"}
        os.makedirs(A)
        run(A, "init")
        for rel, txt in files.items():
            put(A, rel, txt)
        put(A, "README.md", "제작자 안내\n")
        put(A, ".claude/skills/demo/old.md", "볼트에만 · 오래됨\n")
        run(A, "add", ".")
        when = "@%d +0900" % (time.time() - 200)
        run(A, "commit", "-m", "vault", env={"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})
        # 배포판 worktree — 볼트 저장소의 dist-sync 가지(진짜와 같은 꼴) · README 는 익명화한 판
        run(A, "worktree", "add", "-q", "--orphan", "-b", "dist-sync", B)
        for rel, txt in files.items():
            put(B, rel, txt)
        put(B, "README.md", "사용자 안내\n")
        run(B, "add", ".")
        run(B, "commit", "-m", "sync(dist): 처음")
        run(A, "remote", "add", "dist", R)
        run(B, "push", "-q", "dist", "dist-sync:main")
        run(B, "branch", "--set-upstream-to=dist/main")
        t = int(run(B, "log", "-1", "--format=%ct"))
        for rel in list(files) + ["README.md", ".claude/skills/demo/old.md"]:
            os.utime(os.path.join(A, rel), (t - 100, t - 100))            # 배포 커밋보다 먼저 고친 것
        os.utime(os.path.join(A, "README.md"), (t + 100, t + 100))       # 시각만 바뀜(checkout 등) — 고침 아님

        if dc.find_dist(A) != os.path.abspath(B):
            FAIL.append("배포판 worktree 찾기")
        r = dc.check(A, None, True)
        expect("0 어긋남 없는 사본", r, (0, 0, 0, 0))
        doc = load_doctor(A, os.path.join(tmp, "check.json"))
        code, line = doctor_line(doc)
        print("  건강 줄(어긋남 없음): 종료 %d · %s" % (code, line))
        if code != 0 or "어긋남" in line.replace("어긋남 0", ""):
            FAIL.append("건강 줄 — 없으면 안 뜸")

        put(A, PY, "print(2)\n", t + 100)
        r = dc.check(A, B)
        expect("① 볼트만 고침", r, (1, 0, 0, 0)) and r["unsynced"][0]["path"] == PY or FAIL.append("① 경로")
        os.remove(doc.CACHE)                                             # 담아 둔 점검(6시간)을 비우고 다시 잰다
        code, line = doctor_line(doc)
        print("  건강 줄(어긋남 있음): 종료 %d · %s" % (code, line))
        if code != 1 or "안 올린 고침 1" not in line or "할 일" not in line:
            FAIL.append("건강 줄 — 있으면 뜸")

        put(B, "LICENSE", "MIT\n")
        run(B, "add", "LICENSE")
        run(B, "commit", "-m", "sync(dist): 허가")
        expect("② push 안 함", dc.check(A, B), (1, 0, 1, 0))

        run(tmp, "clone", "-q", R, C)
        put(C, "NOTE.md", "원격에서 고침\n")
        run(C, "add", "NOTE.md")
        run(C, "commit", "-m", "다른 곳에서")
        run(C, "push", "-q", "origin", "HEAD:main")
        expect("③ 원격만 앞섬(받기 전)", dc.check(A, B), (1, 0, 1, 0))
        r = dc.check(A, B, True)
        expect("③ 원격만 앞섬(받은 뒤)", r, (1, 0, 1, 1))
        s = dc.summary(r)
        print("  건강 줄: " + s)
        if not all(w in s for w in ("안 올린 고침 1", "push 안 함 1", "받을 것 1", "할 일")):
            FAIL.append("건강 줄 말")

        time.sleep(1.1)
        os.remove(os.path.join(A, ".claude/skills/demo/SKILL.md"))
        run(A, "rm", "-q", "--cached", ".claude/skills/demo/SKILL.md")
        run(A, "commit", "-m", "지움")
        r = dc.check(A, B)
        expect("덤 볼트에서 지움", r, (2, 0, 1, 1)) and any(x["what"] == "볼트에서 지움" for x in r["unsynced"]) or FAIL.append("지움 칸")

        put(B, PY, "print(1)  # 고치는 중\n")
        expect("덤 커밋 안 한 고침", dc.check(A, B), (2, 1, 1, 1))
        run(B, "checkout", "-q", "--", PY)

        external_tests(A, os.path.join(tmp, "ext"))

        dc.ack(A, [PY, ".claude/skills/demo/SKILL.md"])
        expect("덤 안 싣기로 적음", dc.check(A, B), (0, 0, 1, 1))
        put(A, PY, "print(3)\n", time.time() + 100)
        expect("덤 적은 뒤 다시 고침", dc.check(A, B), (1, 0, 1, 1))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("통과" if not FAIL else "실패: " + ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
