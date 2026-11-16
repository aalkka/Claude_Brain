"""dist-check 시험 — 임시 사본(볼트·배포판 worktree·원격)에 어긋남을 하나씩 만들어 센다.

  py -3 .claude/skills/dist-sync/scripts/test_dist_check.py

새 파일 = 배포판에 없는 코어는 배포 커밋보다 먼저 생겨도 1건 → ack 해야만 빠짐
0 = 어긋남 없는 사본 → 0건(익명화로 늘 다른 파일·시각만 바뀐 파일은 안 잡힘)
① 볼트만 고침 → 안 올린 고침 1 · ② 배포판 커밋 push 안 함 → 1 · ③ 원격만 앞섬 → 받을 것 1
덤: 볼트에서 지운 코어 · 배포판 worktree 의 커밋 안 한 고침 · 안 싣기로 적은 판(ack)
안 보던 자리: 옵시디언 설정·스니펫·새 플러그인(폴더째 ack · 까닭) · «필요 ←»(배포판 코어가 부름) · 안 싣기로 했는데 부름
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
OBS_APP = ".obsidian/app.json"  # mf:allow-path  (임시 사본 안 — 배포판에 손으로 넣은 옵시디언 설정 자리)


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


def ship_tests(root):
    """배포 목록(기본 거부) — 목록 밖 새 코어 = 정할 것(① 아님) · 배포판에 있는데 목록 밖 = 빼기 후보 · 자리째 ack · 폴더째 적은 자리 ·
    ⑥ 배포판 글이 배포판에 없는 모듈·코드를 가리킴 · publish 리포트 갈래."""
    A, B = os.path.join(root, "vault"), os.path.join(root, "dist")
    SHIP = ".claude/skills/dist-sync/ship.json"  # mf:allow-path  (임시 사본 안)
    NEWP = "3_시스템/_eval/phone_only_check.py"   # mf:allow-path  (임시 사본 안 — 개인 프로젝트 대본 흉내)
    OLDP = "3_시스템/_eval/old_personal_check.py"  # mf:allow-path  (임시 사본 안 — 잘못 실린 것 흉내)
    LIST = '{"기능": {"데모": [".claude/skills/demo/", ".claude/skills/dist-sync/", "README.md", "' + PY + '"%s]}}\n'
    os.makedirs(A)
    run(A, "init")
    put(A, ".claude/skills/demo/SKILL.md", "demo\n")
    put(A, "README.md", "사용법\n")
    put(A, PY, "print(1)\n")
    put(A, OLDP, "print('개인')\n")
    put(A, ".claude/skills/secret/SKILL.md", "개인 모듈\n")
    put(A, SHIP, LIST % "")
    run(A, "add", ".")
    run(A, "commit", "-m", "vault")
    run(A, "worktree", "add", "-q", "--orphan", "-b", "dist-sync", B)
    STRAY = "3_시스템/stray-x.py"   # mf:allow-path  (임시 사본 안 — 층 규칙에 없는 자리(미분류)에 손으로 실린 것)
    for rel, txt in ((".claude/skills/demo/SKILL.md", "demo\n"), (PY, "print(1)\n"), (OLDP, "print('개인')\n"), (SHIP, LIST % ""), ("README.md", "사용법\n"),
                     (STRAY, "print('손')\n")):
        put(B, rel, txt)
    run(B, "add", ".")
    run(B, "commit", "-m", "sync(dist): 처음")
    t = int(run(B, "log", "-1", "--format=%ct"))
    for rel in (".claude/skills/demo/SKILL.md", PY, OLDP, SHIP, ".claude/skills/secret/SKILL.md", "README.md"):
        os.utime(os.path.join(A, rel), (t - 100, t - 100))
    ok = True

    def say(name, cond, detail=""):
        nonlocal ok
        print("%s 배포 목록 — %s%s" % ("✓" if cond else "✗", name, (" · " + str(detail)) if detail else ""))
        if not cond:
            ok = False
            FAIL.append("배포 목록 " + name)

    r = dc.check(A, B)
    say("빼기 후보 = 배포판에 있는데 목록 밖(코어·미분류)", [x["path"] for x in r["drops"]] == [OLDP, STRAY], [x["path"] for x in r["drops"]])
    say("목록 밖 새 모듈 = 정할 것", [x["path"] for x in r["undecided"]] == [".claude/skills/secret/SKILL.md"], r["undecided"])
    dc.ack(A, [".claude/skills/secret/SKILL.md"], "개인 모듈", always=True)
    r = dc.check(A, B)
    say("목록 안 · 같은 파일 = ① 0", r["unsynced"] == [] and r["undecided"] == [], (r["unsynced"], r["undecided"]))
    put(A, NEWP, "print('폰')\n")
    r = dc.check(A, B)
    say("목록 밖 새 코어 = 정할 것(① 아님)", [x["path"] for x in r["undecided"]] == [NEWP] and r["unsynced"] == [],
        ([x["path"] for x in r["undecided"]], [x["path"] for x in r["unsynced"]]))
    s = dc.summary(r)
    say("건강 줄에 정할 것·빼기 후보", "정할 것 1" in s and "빼기 후보 2" in s and "정하기" in s, s)
    try:
        dc.ack(A, [NEWP], always=True)
        say("자리째 ack 는 까닭 없으면 거부", False)
    except ValueError:
        say("자리째 ack 는 까닭 없으면 거부", True)
    dc.ack(A, [NEWP], "개인 프로젝트", always=True)
    put(A, NEWP, "print('폰 2')\n", time.time() + 100)
    say("자리째 ack 뒤 다시 고쳐도 안 뜸", dc.check(A, B)["undecided"] == [])
    put(A, ".claude/skills/demo/new.md", "모듈 폴더 안 새 파일\n")
    r = dc.check(A, B)
    say("목록에 적은 모듈 폴더 안 새 파일 = ①", [x["path"] for x in r["unsynced"]] == [".claude/skills/demo/new.md"], [x["path"] for x in r["unsynced"]])
    # ⑥ — 배포판 글이 배포판에 없는 모듈·볼트에만 있는 코드를 가리킴
    put(B, "README.md", "사용법 · /secret:run 으로 · phone_only_check.py 가 울린다\n")
    r = dc.check(A, B)
    got = {x["path"]: x["why"] for x in r["pointers"]}
    say("가리킴 — 없는 스킬(module.json 없음)·볼트에만 있는 코드", sorted(got.get("README.md", [])) == ["배포판에 없는 스킬 secret", "볼트에만 있는 phone_only_check.py"], got)
    dc.ack(A, ["README.md"], "시험 — 안내 글", ref_of=r["pointers"])
    say("가리킴 확인함 뒤 0", dc.check(A, B)["pointers"] == [])
    put(B, "README.md", "사용법 · /secret:run · phone_only_check.py · old_personal_check.py 도\n")
    r = dc.check(A, B)
    # old_personal_check.py 는 배포판에 있으니 «볼트에만»이 아니다 — 새 이름 없음 → 그대로 0
    say("배포판에 있는 이름은 가리킴 아님", r["pointers"] == [], r["pointers"])
    put(A, "3_시스템/server-x.py", "print('서버')\n")   # mf:allow-path  (임시 사본 안)
    put(B, "README.md", "사용법 · /secret:run · phone_only_check.py · server-x.py\n")
    r = dc.check(A, B)
    say("확인한 뒤 새 이름 = 다시 뜸", [x["why"] for x in r["pointers"]] == [["볼트에만 있는 server-x.py"]], r["pointers"])
    # 목록 잘못 — 여러 기능이 같이 쓰는 자리를 폴더째
    put(A, SHIP, LIST % ', "3_시스템/_ref/"')  # mf:allow-path  (임시 사본 안 — 폴더째 적은 자리 흉내)
    r = dc.check(A, B)
    say("폴더째 적은 자리 = 목록 잘못", r["ship"]["잘못"] == ["3_시스템/_ref/"], r["ship"])  # mf:allow-path  (임시 사본 안)
    put(A, SHIP, LIST % "")
    # publish 리포트 — 목록 밖은 «통째 교체»에 안 넣고 «정할 것» · 빼기 후보
    text, _ = dc.dd.report(A, B, "publish")
    core = text.split("## 코어 — 통째 교체 가능")[1].split("\n## ")[0] if "## 코어 — 통째 교체 가능" in text else ""
    say("리포트 — 목록 밖 새 파일은 통째 교체에 없음", NEWP not in core and ".claude/skills/demo/new.md" in core, core.strip()[:120])
    sec = lambda h: text.split(h)[1].split("\n## ")[0] if h in text else ""
    say("리포트 — 정할 것 칸에 목록 밖 새 코어", ("`%s`" % NEWP) in sec("## 배포 목록 밖 — 옮기지 않는다(정할 것)"), sec("## 배포 목록 밖 — 옮기지 않는다(정할 것)").strip()[:160])
    say("리포트 — 빼기 후보 칸", ("`%s`" % OLDP) in sec("## 배포판에 있는데 목록 밖 — 빼기 후보"), sec("## 배포판에 있는데 목록 밖 — 빼기 후보").strip()[:160])
    return ok


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
        put(A, OBS_APP, '{"a": 1}\n')
        run(A, "add", ".")
        when = "@%d +0900" % (time.time() - 200)
        run(A, "commit", "-m", "vault", env={"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when})
        # 배포판 worktree — 볼트 저장소의 dist-sync 가지(진짜와 같은 꼴) · README 는 익명화한 판
        run(A, "worktree", "add", "-q", "--orphan", "-b", "dist-sync", B)
        for rel, txt in files.items():
            put(B, rel, txt)
        put(B, "README.md", "사용자 안내\n")
        put(B, OBS_APP, '{"a": 1}\n')                                     # 배포판에 손으로 넣은 옵시디언 설정
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
        r = dc.check(A, B)              # 배포판에 없는 새 파일은 배포 커밋보다 먼저 생겼어도 센다(11-13 draft·gpu_guard 가 조용히 빠졌다)
        expect("새 파일 — 배포 커밋 앞에 생김", r, (1, 0, 0, 0)) and r["unsynced"][0]["path"] == ".claude/skills/demo/old.md" \
            and r["unsynced"][0]["what"] == "새 파일" or FAIL.append("새 파일 칸")
        dc.ack(A, [".claude/skills/demo/old.md"])                         # 안 싣기로 적어야만 빠진다
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

        # 층 규칙이 안 보는 자리 — 옵시디언 설정·스니펫·새 플러그인 · 배포판 코어가 부르는 새 파일 · 안 싣기로 했는데 부름
        NEED = ".claude/skills/demo/need.md"
        put(A, OBS_APP, '{"a": 2}\n')
        put(A, ".obsidian/snippets/x.css", "p{}\n")
        put(A, ".obsidian/plugins/foo/manifest.json", '{"id": "foo"}\n')
        put(A, NEED, "새 문서\n")
        put(B, "README.md", "사용자 안내 · %s 를 본다\n" % NEED)
        got = {x["path"]: x for x in dc.check(A, B)["unsynced"]}
        ok = (got.get(OBS_APP, {}).get("what") == "옵시디언 설정 다름" and got.get(".obsidian/snippets/x.css", {}).get("what") == "새 스니펫"
              and got.get(".obsidian/plugins/foo/", {}).get("what") == "새 플러그인"
              and got.get(NEED, {}).get("why", [""])[0].startswith("필요 ← README.md"))
        dc.ack(A, [OBS_APP, ".obsidian/snippets/x.css", ".obsidian/plugins/foo"], "시험")
        put(A, ".obsidian/plugins/foo/manifest.json", '{"id": "foo", "version": "2"}\n')    # 플러그인은 판을 올려도 안 깨어남
        left = {x["path"] for x in dc.check(A, B)["unsynced"]}
        ok = ok and not left & {OBS_APP, ".obsidian/snippets/x.css", ".obsidian/plugins/foo/"} \
            and dc.load_ack(A)[".obsidian/plugins/foo/"] == {"판": "플러그인", "까닭": "시험"}
        dc.ack(A, [NEED])
        back = {x["path"]: x["what"] for x in dc.check(A, B)["unsynced"]}
        ok = ok and back.get(NEED) == "안 싣기로 했는데 배포판이 부름"
        print("%s 안 보던 자리·가를 까닭 — 처음 %s · 적은 뒤 남음 %s · 부르는데 안 실음 %s" % ("✓" if ok else "✗", sorted(got), sorted(left), back.get(NEED)))
        if not ok:
            FAIL.append("안 보던 자리")

        ship_tests(os.path.join(tmp, "ship"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("통과" if not FAIL else "실패: " + ", ".join(FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
