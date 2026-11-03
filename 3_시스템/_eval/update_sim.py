# -*- coding: utf-8 -*-
"""업데이터 전 경로 시험 — 옛 배포판을 clone 한 가짜 사용자 볼트를 꾸며 README·update 스킬의 명령 그대로 올린다.

  py -3 3_시스템/_eval/update_sim.py --dist <배포판 worktree> [--old <옛 커밋·태그>] [--out <시험 폴더>] [--only 시나리오,...]

배포판 worktree 의 커밋 안 한 변경까지 «새 판» 으로 삼는다. 모든 쓰기는 시험 폴더 안에서만 한다.
플러그인 교체는 옵시디언이 켜져 있으면 멈추므로(본 볼트와 무관) 함수를 직접 부른다.
시나리오: full(사용자 자료·수정 전부) · undo(스킬대로 되돌리기) · v0(초판에서) · crlf(줄바꿈만 다름) · conflict(못 합침·뺀 파일 고침·같은 이름)
· next(그다음 판 · 표가 이번 판을 안다) · samename(같은 이름 폴더) · shallow(얕은 복제) · notable(표 없는 배포판 거절)
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
ENV = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", FILEOPS_NO_OBSIDIAN="1", PYTHONDONTWRITEBYTECODE="1")
ENV.pop("CLAUDE_PROJECT_DIR", None)
GIT = ["git", "-c", "user.name=x", "-c", "user.email=x@x", "-c", "core.quotepath=false"]
DD = ".claude/skills/dist-sync/scripts/dist-diff.py"
FO = "3_시스템/fileops.py"
KNOWN = ".claude/skills/dist-sync/known-hashes.json"
MIG = "0001-목적별-다섯-영역"
fails, passes = [], 0


def ok(name, cond, detail=""):
    global passes
    if cond:
        passes += 1
    else:
        fails.append(name)
        print("  ✗ %s %s" % (name, str(detail)[:300]))


def run(cmd, cwd=None, env=None, timeout=600):
    # 표준 입력을 닫는다 — 훅 대본(session-stub.py)은 입력을 끝까지 읽는다
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env or ENV, timeout=timeout, stdin=subprocess.DEVNULL)


def git(args, cwd):
    r = run(GIT + args, cwd)
    if r.returncode:
        raise SystemExit("git %s 실패: %s" % (" ".join(args), r.stderr[-400:]))
    return r.stdout


def onerr(f, p, _):
    os.chmod(p, stat.S_IWRITE)
    f(p)


def wipe(p):
    if os.path.exists(p):
        shutil.rmtree(p, onerror=onerr)


def w(v, rel, data, mode="w"):
    p = os.path.join(v, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if isinstance(data, bytes):
        with open(p, "wb") as f:
            f.write(data)
    else:
        with open(p, mode, encoding="utf-8", newline="\n") as f:
            f.write(data)


def rd(v, rel):
    return open(os.path.join(v, *rel.split("/")), encoding="utf-8", errors="replace").read()


def has(v, rel):
    return os.path.exists(os.path.join(v, *rel.split("/")))


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


SKIP = (".git", ".trash/", "3_시스템/ledger/", "3_시스템/_index/", "2_지식/장부.md")


def tree(v):
    out = {}
    for d, ds, fs in os.walk(v):
        for f in fs:
            r = os.path.relpath(os.path.join(d, f), v).replace("\\", "/")
            if not r.startswith(SKIP) and "__pycache__" not in r:
                out[r] = sha(os.path.join(d, f))
    return out


PDF = b"%PDF-1.4 fake pdf"
NOTE = "---\ntitle: 내노트\n---\n본문\n[[내노트2]]\n[[2_지식/notes/내노트2|둘째]]\n[상대](내노트2.md)\n![[1_수집/학교/과목/강의.pdf]]\n[[2_지식/sessions/2026-10-01-세션]]\n"
PERSONAL = {
    "2_지식/notes/내노트.md": NOTE,
    "2_지식/notes/내노트2.md": "---\ntitle: 내노트2\n---\n[[하위/깊은노트]]\n",
    "2_지식/notes/하위/깊은노트.md": "---\ntitle: 깊은노트\n---\n깊은 본문\n",
    "2_지식/sessions/2026-10-01-세션.md": "---\ntitle: 세션\n---\n내 세션 기록\n",
    "2_지식/decisions/ADR-900-내결정.md": "---\ntitle: 내결정\n---\n내 결정\n",
    "1_수집/학교/과목/강의.md": "내 짝 메모\n",
    "1_수집/내자료/메모.md": "내 메모\n",
    "3_시스템/_claude-memory/mem.md": "내 노트 자리 2_지식/notes/내노트.md\n",
    "2_지식/비밀/비번.md": "---\ntitle: 비번\n---\n가짜 비밀\n",
    ".claude/skills/내스킬/SKILL.md": "---\nname: 내스킬\n---\n내가 만든 스킬\n",
    "3_시스템/내대본.py": "print('내 대본')\n",
    ".obsidian/bookmarks.json": json.dumps({"items": [{"type": "file", "path": "2_지식/notes/내노트.md"}, {"type": "folder", "path": "2_지식/sessions"}]}, ensure_ascii=False),
    ".obsidian/graph.json": json.dumps({"colorGroups": [{"query": "path:2_지식/notes"}, {"query": 'path:"2_지식/notes-비슷한이름"'}]}, ensure_ascii=False),
    ".obsidian/workspace.json": json.dumps({"lastOpenFiles": ["2_지식/notes/내노트.md"]}, ensure_ascii=False),
    ".obsidian/plugins/brain-source/data.json": json.dumps({"내설정": 1, "폴더": "2_지식/notes"}, ensure_ascii=False),
}


def install(S, name, rev):
    """README 대로 clone 한 사용자 볼트 + 2단계(dist 원격·옆 폴더)."""
    v = os.path.join(S, name)
    git(["clone", "-q", os.path.join(S, "dist.git"), "--branch", rev, v], S)
    git(["remote", "rename", "origin", "dist"], v)
    git(["checkout", "-q", "-b", "내볼트"], v)
    return v


def user_data(v, mods=True):
    for r, t in PERSONAL.items():
        w(v, r, t)
    w(v, "1_수집/학교/과목/강의.pdf", PDF)
    for r in ["2_지식/open-loops.md", "2_지식/recent.md", "2_지식/MOC.md", "2_지식/profile.md"]:
        w(v, r, "- [ ] 내 항목 [[2_지식/notes/내노트]]\n", "a")
    c = rd(v, "CLAUDE.md")
    c = re.sub(r"(^## §0[^\n]*\n)", r"\1호칭: 홍길동(내 §0)\n", c, count=1, flags=re.M)
    if mods:
        c = c.rstrip("\n") + "\n\n내가 끝에 더한 규칙\n"
        cfg = json.loads(rd(v, "3_시스템/config.json"))
        cfg["내설정"] = "유지"
        w(v, "3_시스템/config.json", json.dumps(cfg, ensure_ascii=False, indent=1))
        w(v, "3_시스템/search.py", "# 내 수정\n", "a")
        w(v, "3_시스템/conventions.md", "\n내가 더한 규칙\n", "a")
        w(v, "3_시스템/hooks/session-start.ps1", "\n# 내 훅 수정\n", "a")
        st = json.loads(rd(v, ".claude/settings.json"))
        st.setdefault("permissions", {}).setdefault("allow", []).append("Bash(내명령:*)")
        w(v, ".claude/settings.json", json.dumps(st, ensure_ascii=False, indent=2))
    w(v, ".gitignore", "\n2_지식/비밀/\n", "a")
    w(v, "CLAUDE.md", c)
    git(["add", "-A"], v)
    git(["commit", "-qm", "내 자료"], v)
    git(["fetch", "-q", "dist"], v)
    a = v + "-dist"
    git(["worktree", "add", "-q", a, "dist/main"], v)
    return a


def plan_of(v, a):
    idx = os.path.join(v, "3_시스템", "_index", "dist-sync")
    os.makedirs(idx, exist_ok=True)
    p = os.path.join(idx, "update-plan.json")
    if os.path.exists(p):
        os.remove(p)
    r = run(["py", "-3", a + "/" + DD, "--a", a, "--b", v, "--mode", "update", "--out", idx + "/update.md", "--plan-out", p], v)
    return (json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None), r, p


def preview(v, a, p):
    return run(["py", "-3", a + "/" + FO, "--vault", v, "update", p], v), run(["py", "-3", a + "/" + FO, "--vault", v, "migrate", "--from", a + "/3_시스템/migrations"], v)


def apply_all(v, a, p, plugins=True):
    r1 = run(["py", "-3", a + "/" + FO, "--vault", v, "update", p, "--apply"], v)
    r0 = None
    if plugins:
        code = "import importlib.util as u;s=u.spec_from_file_location('dd',r'%s');m=u.module_from_spec(s);s.loader.exec_module(m);print(m.plugins(r'%s',r'%s',False)[1])" % (a + "/" + DD, a, v)
        r0 = run(["py", "-3", "-c", code], v)
    r2 = run(["py", "-3", os.path.join(v, *FO.split("/")), "migrate", "--apply"], v)
    return r1, r0, r2


def live(v, name):
    out = []
    for d, ds, fs in os.walk(v):
        ds[:] = [x for x in ds if x not in (".git", ".trash")]
        out += [os.path.relpath(os.path.join(d, f), v).replace("\\", "/") for f in fs if f == name]
    return out


def links_ok(v, rel):
    bad = []
    for m in re.finditer(r"!?\[\[([^\]|#]+)", rd(v, rel)):
        x = m.group(1).strip()
        if "/" in x and not any(has(v, x + e) for e in ("", ".md")):
            bad.append(x)
    return bad


def health(tag, v):
    d = run(["py", "-3", os.path.join(v, "3_시스템/brain.py"), "doctor"], v)
    ok(tag + " doctor 코드", d.returncode in (0, 1), d.stderr[-200:])
    bad = [l[:110] for l in d.stdout.splitlines() if l[:1] == "✗"]
    ok(tag + " doctor ✗ 없음", not bad, bad)
    s = run(["py", "-3", os.path.join(v, "3_시스템/search.py"), "--q", "내노트", "--k", "1"], v)
    ok(tag + " search.py 돈다", s.returncode == 0, s.stderr[-200:])
    s = run(["py", "-3", os.path.join(v, "3_시스템/session-stub.py"), "--help"], v)
    ok(tag + " session-stub.py 뜬다", "ModuleNotFoundError" not in s.stderr, s.stderr[-200:])


def s_full(S, old):
    print("· full — 사용자 자료·수정 전부")
    v = install(S, "full", old)
    a = user_data(v)
    plan, r, p = plan_of(v, a)
    ok("full 계획 나옴", plan is not None, r.stderr[-300:])
    u0, m0 = preview(v, a, p)
    ok("full 미리 보기가 파일을 안 바꿈", has(v, "2_지식/notes/내노트.md") and not has(v, "3_시스템/fileops.py"))
    ok("full 미리 보기에 이전이 보임", "2_지식/notes" in m0.stdout and "미리 보기" in m0.stdout, m0.stdout[:200] + m0.stderr[-200:])
    ok("full 미리 보기에 옵시디언 설정", ".obsidian/bookmarks.json" in m0.stdout, m0.stdout[-300:])
    ok("full 미리 보기가 기억의 옛 경로를 알림", "_claude-memory/mem.md" in m0.stdout, m0.stdout[-300:])
    report = rd(v, "3_시스템/_index/dist-sync/update.md")
    ok("full 리포트에 개인 이름 없음", not re.search(r"내결정|2026-10-01-세션|비번|내노트", report), [x for x in re.findall(r".*(?:내결정|세션|비번|내노트).*", report)][:3])
    ok("full 리포트가 새 절차로 안내", "update/SKILL.md" in report and "옛 판" in report)
    why = {}
    for o in plan["ops"]:
        why.setdefault(o.get("why"), []).append(o["rel"])
    merged = why.get("내 수정과 합침", [])
    print("    계획: %s · 못 합침 %s · 남김 %s" % ({k: len(x) for k, x in why.items()}, [c["rel"] for c in plan["conflicts"]], plan["kept"]))
    for r_ in ["3_시스템/search.py", "3_시스템/conventions.md", ".gitignore", ".claude/settings.json"]:
        ok("full 합침 " + r_, r_ in merged, merged)
    r1, r0, r2 = apply_all(v, a, p)
    for n, x in (("update", r1), ("plugins", r0), ("migrate", r2)):
        ok("full %s 코드 0" % n, x.returncode == 0, x.stdout[-200:] + x.stderr[-300:])
    # 개인 자료
    for rel, want in [("2_지식/분야/내노트2.md", None), ("2_지식/분야/하위/깊은노트.md", PERSONAL["2_지식/notes/하위/깊은노트.md"]),
                      ("2_지식/기록/2026-10-01-세션.md", PERSONAL["2_지식/sessions/2026-10-01-세션.md"]),
                      ("2_지식/일/외부뇌/결정/ADR-900-내결정.md", PERSONAL["2_지식/decisions/ADR-900-내결정.md"]),
                      ("1_수집/배움/과목/강의.md", PERSONAL["1_수집/학교/과목/강의.md"]), ("1_수집/내자료/메모.md", PERSONAL["1_수집/내자료/메모.md"]),
                      ("2_지식/비밀/비번.md", PERSONAL["2_지식/비밀/비번.md"]), ("3_시스템/_claude-memory/mem.md", PERSONAL["3_시스템/_claude-memory/mem.md"]),
                      (".claude/skills/내스킬/SKILL.md", PERSONAL[".claude/skills/내스킬/SKILL.md"]), ("3_시스템/내대본.py", PERSONAL["3_시스템/내대본.py"])]:
        ok("full 있음 " + rel, has(v, rel))
        if want and has(v, rel):
            ok("full 내용 같음 " + rel, rd(v, rel) == want)
    ok("full PDF 그대로", has(v, "1_수집/배움/과목/강의.pdf") and open(os.path.join(v, "1_수집/배움/과목/강의.pdf"), "rb").read() == PDF)
    ok("full 옛 자리 없음", not any(has(v, x) for x in ["2_지식/notes", "2_지식/sessions", "2_지식/decisions", "1_수집/학교"]))
    ok("full 경로 링크 안 깨짐", not links_ok(v, "2_지식/분야/내노트.md"), links_ok(v, "2_지식/분야/내노트.md"))
    for s_ in ["2_지식/open-loops.md", "2_지식/recent.md", "2_지식/MOC.md", "2_지식/profile.md"]:
        ok("full 씨앗 항목 " + s_, "- [ ] 내 항목 [[2_지식/분야/내노트]]" in rd(v, s_))
    ok("full config 내설정", json.loads(rd(v, "3_시스템/config.json")).get("내설정") == "유지")
    # 고친 코어
    c = rd(v, "CLAUDE.md")
    ok("full §0 호칭", "홍길동" in c)
    ok("full §0 밖 내 규칙 안 잃음", "내가 끝에 더한 규칙" in c, [x["rel"] for x in plan["conflicts"]])
    ok("full CLAUDE.md 는 새 본문", rd(a, "CLAUDE.md").split("## §1")[1][:40] in c or any(x["rel"] == "CLAUDE.md" for x in plan["conflicts"]))
    t = rd(v, "3_시스템/search.py")
    ok("full search.py 내 수정 + 새 판", "# 내 수정" in t and "import roles" in t)
    t = rd(v, "3_시스템/conventions.md")
    ok("full conventions 내 수정 + 새 판", "내가 더한 규칙" in t and rd(a, "3_시스템/conventions.md").splitlines()[5] in t)
    st = json.loads(rd(v, ".claude/settings.json"))
    new_st = json.loads(rd(a, ".claude/settings.json"))
    ok("full settings 내 허용", "Bash(내명령:*)" in st.get("permissions", {}).get("allow", []))
    ok("full settings 새 훅", st.get("hooks") == new_st.get("hooks"), list(st.get("hooks", {}))[:5])
    for m in re.findall(r"3_시스템/[\w\-./]+\.(?:ps1|py)", json.dumps(st.get("hooks", {}), ensure_ascii=False)):
        ok("full 훅 대본 있음 " + m, has(v, m))
    g = rd(v, ".gitignore")
    ok("full .gitignore 내 줄", "2_지식/비밀/" in g)
    ok("full .gitignore 새 줄", ".trash" in g and "1_수집/**" in g)
    ok("full 비번 git 제외", run(GIT + ["check-ignore", "-q", "2_지식/비밀/비번.md"], v).returncode == 0)
    # 뺀 파일·씨앗·플러그인
    for r_ in [".claude/skills/inbox-sort/SKILL.md", ".claude/skills/search/SKILL.md", ".claude/skills/module-forge/skills/new/SKILL.md"]:
        ok("full 뺀 스킬 치움 " + r_, not has(v, r_))
        ok("full 뺀 스킬 휴지통 " + r_, any(x.endswith(r_) for x in [os.path.relpath(os.path.join(d, f), v).replace("\\", "/") for d, _, fs in os.walk(os.path.join(v, ".trash")) for f in fs]))
    ok("full 씨앗 넣음", has(v, "2_지식/주제.md") and has(v, "2_지식/보존.md"))
    ok("full 플러그인 설정 그대로", json.loads(rd(v, ".obsidian/plugins/brain-source/data.json")) == {"내설정": 1, "폴더": "2_지식/notes"})
    ok("full 첫 진입 설정", json.loads(rd(v, ".obsidian/plugins/brain-base/data.json")).get("replaceExplorer") is False)
    ok("full 플러그인 본체", has(v, ".obsidian/plugins/brain-base/main.js"))
    # 옵시디언 설정
    b = rd(v, ".obsidian/bookmarks.json")
    ok("full 책갈피 새 자리", "2_지식/분야/내노트.md" in b and "2_지식/기록" in b and "2_지식/notes" not in b, b)
    gr = rd(v, ".obsidian/graph.json")
    ok("full 그래프 새 자리", "path:2_지식/분야" in gr, gr)
    ok("full 비슷한 이름은 그대로", "2_지식/notes-비슷한이름" in gr, gr)
    ok("full 열린 탭 새 자리", "2_지식/분야/내노트.md" in rd(v, ".obsidian/workspace.json"))
    ok("full 알림 기억", "_claude-memory/mem.md" in r2.stdout, r2.stdout[-300:])
    ok("full 알림 플러그인 설정", "plugins/brain-source/data.json" in r2.stdout, r2.stdout[-300:])
    ok("full 알림에 배포판 파일 없음", "restructure.py" not in r2.stdout and "gate-cases" not in r2.stdout, r2.stdout[-400:])
    # 다시 돌려도 같다
    plan2, _, _ = plan_of(v, a)
    ok("full 두 번째 계획 0", plan2 is not None and not plan2["ops"], [(o.get("why"), o["rel"]) for o in (plan2 or {"ops": []})["ops"]][:6])
    ok("full 두 번째 못 합침 0", plan2 is not None and not plan2["conflicts"], (plan2 or {}).get("conflicts"))
    r3 = run(["py", "-3", os.path.join(v, *FO.split("/")), "migrate"], v)
    ok("full 밀린 이전 없음", "밀린 이전 없음" in r3.stdout, r3.stdout[-200:])
    health("full", v)
    # 실제 훅 — 세션 시작(PowerShell 5.1) · pre-commit 을 켠 자동 커밋
    t = rd(v, "3_시스템/hooks/session-start.ps1")
    ok("full 고친 훅 내 수정 + 새 판", "# 내 훅 수정" in t and "follow" in t or any(c["rel"].endswith("session-start.ps1") for c in plan["conflicts"]), [c["rel"] for c in plan["conflicts"]])
    h = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(v, "3_시스템/hooks/session-start.ps1")], v, dict(ENV, CLAUDE_PROJECT_DIR=v))
    ok("full 세션 시작 훅 코드 0", h.returncode == 0, h.stderr[-300:])
    ok("full 세션 시작 훅 오류 없음", not h.stderr.strip(), h.stderr[-300:])
    ok("full 세션 시작에 내 항목", "내 항목" in h.stdout, h.stdout[:200])
    git(["config", "core.hooksPath", "3_시스템/hooks"], v)
    git(["add", "-A", "--", ":!1_수집"], v)
    c1 = run(GIT + ["commit", "-qm", "session: 시험"], v)
    ok("full 실제 pre-commit 통과", c1.returncode == 0, c1.stdout[-300:] + c1.stderr[-300:])
    idx = git(["ls-files"], v)
    ok("full 비번 커밋 안 됨", "비번" not in idx)
    ok("full 휴지통 커밋 안 됨", ".trash" not in idx)
    ok("full 합본 칸 커밋 안 됨", "_index/dist-sync" not in idx)


def s_undo(S, old):
    print("· undo — 스킬대로 되돌리기")
    v = install(S, "undo", old)
    a = user_data(v)
    before = tree(v)
    plan, _, p = plan_of(v, a)
    r1, _, r2 = apply_all(v, a, p, plugins=False)
    m = re.search(r"undo (b[0-9a-z-]+)", r1.stdout)
    ok("undo 묶음 id", bool(m), r1.stdout[-200:])
    u1 = run(["py", "-3", os.path.join(v, *FO.split("/")), "migrate", "--undo", MIG], v)
    u2 = run(["py", "-3", a + "/" + FO, "--vault", v, "undo", m.group(1)], v)
    ok("undo 이전 코드 0", u1.returncode == 0, u1.stdout[-200:] + u1.stderr[-300:])
    ok("undo 업데이트 코드 0", u2.returncode == 0, u2.stdout[-200:] + u2.stderr[-300:])
    after = tree(v)
    miss, extra = sorted(set(before) - set(after)), sorted(set(after) - set(before))
    diff = sorted(r for r in before if r in after and before[r] != after[r])
    ok("undo 없어진 것 0", not miss, miss[:6])
    ok("undo 더 생긴 것 0", not extra, extra[:6])
    ok("undo 달라진 것 = 링크 표기뿐", diff == ["2_지식/notes/내노트2.md"], diff[:6])
    ok("undo 달라진 노트의 링크 유효", not links_ok(v, "2_지식/notes/내노트2.md"), links_ok(v, "2_지식/notes/내노트2.md"))
    print("    달라진 것: %s" % diff)


def s_v0(S):
    print("· v0 — 초판에서")
    v = install(S, "v0", "v0-template")
    a = user_data(v, mods=False)
    plan, r, p = plan_of(v, a)
    ok("v0 계획 나옴", plan is not None, r.stderr[-300:])
    print("    못 합침 %s · 남김 %s" % ([c["rel"] for c in plan["conflicts"]], plan["kept"][:4]))
    ok("v0 고친 것으로 오해한 파일 없음", not [o for o in plan["ops"] if o.get("why") == "내 수정과 합침" and o["rel"] != ".gitignore"], [o["rel"] for o in plan["ops"] if o.get("why") == "내 수정과 합침"][:6])
    r1, r0, r2 = apply_all(v, a, p)
    ok("v0 적용 코드 0", r1.returncode == 0 and r2.returncode == 0, r1.stderr[-300:] + r2.stderr[-300:])
    ok("v0 노트 옮김", has(v, "2_지식/분야/내노트.md") and rd(v, "2_지식/분야/하위/깊은노트.md") == PERSONAL["2_지식/notes/하위/깊은노트.md"])
    ok("v0 §0", "홍길동" in rd(v, "CLAUDE.md"))
    health("v0", v)


def s_crlf(S, old):
    print("· crlf — 줄바꿈만 다른 볼트")
    v = install(S, "crlf", old)
    a = user_data(v, mods=False)
    n = 0
    for sub in (".claude", "3_시스템"):
        for d, ds, fs in os.walk(os.path.join(v, sub)):
            ds[:] = [x for x in ds if x not in ("_index", "_claude-memory")]
            for f in fs:
                if f.endswith((".md", ".py", ".ps1", ".json", ".tsv", ".txt")) and "내" not in f:
                    p = os.path.join(d, f)
                    data = open(p, "rb").read()
                    if b"\r\n" not in data:
                        open(p, "wb").write(data.replace(b"\n", b"\r\n"))
                        n += 1
    p_ = os.path.join(v, "CLAUDE.md")
    data = open(p_, "rb").read()
    open(p_, "wb").write(data.replace(b"\n", b"\r\n"))
    plan, r, _ = plan_of(v, a)
    wrong = [o["rel"] for o in plan["ops"] if o.get("why") == "내 수정과 합침" and o["rel"] != ".gitignore"]
    print("    CRLF 로 바꾼 파일 %d" % n)
    ok("crlf 고친 것으로 오해 없음", not wrong, wrong[:6])
    ok("crlf 못 합침 없음", not plan["conflicts"], plan["conflicts"][:3])
    ok("crlf §0", "홍길동" in open(os.path.join(v, "3_시스템/_index/dist-sync/CLAUDE.merged.md"), encoding="utf-8").read())


def s_conflict(S, old):
    print("· conflict — 못 합침 · 뺀 파일을 고침 · 같은 이름으로 만듦")
    v = install(S, "conflict", old)
    a = user_data(v, mods=False)
    w(v, "3_시스템/search.py", "print('내가 통째로 고친 판')\n")
    w(v, "3_시스템/holidays.py", "print('내가 만든 같은 이름 대본')\n")
    w(v, ".claude/skills/inbox-sort/SKILL.md", "내가 고친 줄\n", "a")
    keep_s, keep_h = sha(os.path.join(v, "3_시스템/search.py")), sha(os.path.join(v, "3_시스템/holidays.py"))
    git(["add", "-A"], v)
    git(["commit", "-qm", "내 수정"], v)
    plan, r, p = plan_of(v, a)
    c = {x["rel"]: x for x in plan["conflicts"]}
    ok("conflict search.py 못 합침", "3_시스템/search.py" in c, plan["conflicts"])
    ok("conflict holidays.py 못 합침", "3_시스템/holidays.py" in c, plan["conflicts"])
    ok("conflict 뺀 스킬 고침 = 남김", any("inbox-sort" in k for k in plan["kept"]), plan["kept"])
    report = rd(v, "3_시스템/_index/dist-sync/update.md")
    ok("conflict 리포트에 못 합침", "못 합침" in report and "3_시스템/search.py" in report)
    r1, _, r2 = apply_all(v, a, p, plugins=False)
    ok("conflict 적용 코드 0", r1.returncode == 0 and r2.returncode == 0, r1.stderr[-300:] + r2.stderr[-300:])
    ok("conflict 출력에 못 합침", "못 합쳐" in r1.stdout, r1.stdout[-200:])
    ok("conflict search.py 그대로", sha(os.path.join(v, "3_시스템/search.py")) == keep_s)
    ok("conflict holidays.py 그대로", sha(os.path.join(v, "3_시스템/holidays.py")) == keep_h)
    ok("conflict 뺀 스킬 남음", "내가 고친 줄" in rd(v, ".claude/skills/inbox-sort/SKILL.md"))
    ok("conflict 새 판 자리", os.path.exists(c["3_시스템/search.py"]["new"]) and "import roles" in open(c["3_시스템/search.py"]["new"], encoding="utf-8").read())
    # 사람이 «새 판으로» 를 고른 뒤
    one = os.path.join(v, "3_시스템/_index/dist-sync/one.json")
    json.dump({"version": "손으로", "ops": [{"op": "put", "rel": "3_시스템/search.py", "src": c["3_시스템/search.py"]["new"], "why": "사람이 고름"}]}, open(one, "w", encoding="utf-8"), ensure_ascii=False)
    r3 = run(["py", "-3", a + "/" + FO, "--vault", v, "update", one, "--apply"], v)
    ok("conflict 사람이 고른 판 적용", r3.returncode == 0 and "import roles" in rd(v, "3_시스템/search.py"), r3.stderr[-200:])
    ok("conflict 내 판은 휴지통", any(f == "search.py" and "내가 통째로" in open(os.path.join(d, f), encoding="utf-8").read() for d, _, fs in os.walk(os.path.join(v, ".trash")) for f in fs))


def s_samename(S, old):
    print("· samename — 같은 이름 폴더가 이미 있을 때")
    v = install(S, "samename", old)
    w(v, "2_지식/분야/기존.md", "---\ntitle: 기존\n---\n내 분야 노트\n")
    w(v, "2_지식/기록/내일기.md", "---\ntitle: 일기\n---\n내 일기\n")
    a = user_data(v, mods=False)
    plan, _, p = plan_of(v, a)
    r1, _, r2 = apply_all(v, a, p, plugins=False)
    ok("samename 적용 코드 0", r1.returncode == 0 and r2.returncode == 0, r2.stderr[-300:])
    ok("samename 기존 그대로", "내 분야 노트" in rd(v, "2_지식/분야/기존.md") and "내 일기" in rd(v, "2_지식/기록/내일기.md"))
    ok("samename 내노트 안 잃음", live(v, "내노트.md") == ["2_지식/분야/notes/내노트.md"], live(v, "내노트.md"))
    ok("samename 경로 링크", not links_ok(v, "2_지식/분야/notes/내노트.md"), links_ok(v, "2_지식/분야/notes/내노트.md"))
    ok("samename 책갈피 실제 자리", "2_지식/분야/notes/내노트.md" in rd(v, ".obsidian/bookmarks.json"), rd(v, ".obsidian/bookmarks.json"))


def s_shallow(S, old):
    print("· shallow — 얕은 복제에서(기준 판을 못 읽음)")
    base = os.path.join(S, "shallow")
    v = install(S, "shallow", old)
    a = user_data(v)
    url = "file:///" + os.path.join(S, "dist.git").replace("\\", "/")
    sa = base + "-a"
    git(["clone", "-q", "--depth", "1", url, sa], S)
    plan, r, p = plan_of(v, sa)
    ok("shallow 계획 나옴", plan is not None, r.stderr[-300:])
    c = [x["rel"] for x in plan["conflicts"]]
    ok("shallow 고친 search.py = 못 합침", "3_시스템/search.py" in c, c)
    ok("shallow 안 고친 파일은 새 판", any(o["rel"] == "3_시스템/hooks/stop-check.ps1" and o.get("why") == "새 판으로 바꿈" for o in plan["ops"]))
    gi = [o for o in plan["ops"] if o["rel"] == ".gitignore"]
    ok("shallow .gitignore 내 줄 유지", gi and "2_지식/비밀/" in open(gi[0]["src"], encoding="utf-8").read(), gi)


def s_notable(S, old):
    print("· notable — 표 없는 배포판은 계획을 안 낸다")
    v = install(S, "notable", old)
    a = user_data(v, mods=False)
    os.remove(os.path.join(a, *KNOWN.split("/")))
    plan, r, _ = plan_of(v, a)
    ok("notable 계획 없음", plan is None and r.returncode == 2, r.stdout[-200:] + r.stderr[-200:])
    ok("notable 까닭을 말함", "판 해시 표" in r.stderr, r.stderr[-200:])


def s_next(S, old, dev):
    print("· next — 그다음 판(표가 이번 판을 안다 · 사용자 값 유지)")
    v = install(S, "next", old)
    a = user_data(v, mods=False)
    plan, _, p = plan_of(v, a)
    apply_all(v, a, p, plugins=False)
    roles = json.loads(rd(v, "3_시스템/roles.json"))
    key = next(k for k, x in roles["roles"].items() if x == "2_지식/분야") if "roles" in roles else None
    roles["roles"]["내역할"] = "2_지식/분야/내자리"
    w(v, "3_시스템/roles.json", json.dumps(roles, ensure_ascii=False, indent=1))
    w(v, "3_시스템/default-layout.json", json.dumps({"schema": 1, "내배치": True}, ensure_ascii=False))
    w(v, "3_시스템/conventions.md", "\n내가 더한 규칙\n", "a")
    # 제작자가 그다음 판을 낸다
    w(dev, "3_시스템/conventions.md", "\n다음 판의 새 규칙\n", "a")
    w(dev, ".gitignore", "\n# 다음 판의 줄\n다음판제외/\n", "a")
    w(dev, "3_시스템/tokens.py", "# 다음 판 주석\n", "a")
    nr = json.loads(rd(dev, "3_시스템/roles.json"))
    nr["다음판칸"] = 1
    w(dev, "3_시스템/roles.json", json.dumps(nr, ensure_ascii=False, indent=1))
    w(dev, "3_시스템/default-layout.json", json.dumps({"schema": 1, "다음판": True}))
    git(["add", "-A"], dev)
    git(["commit", "-qm", "다음 판"], dev)
    rb = run(["py", "-3", dev + "/" + DD, "--build-known", dev], dev)
    ok("next 표 다시 만듦", rb.returncode == 0, rb.stderr[-300:])
    git(["add", "-A"], dev)
    git(["commit", "-qm", "표"], dev)
    git(["push", "-q", os.path.join(S, "dist.git"), "HEAD:main"], dev)
    git(["fetch", "-q", "dist"], v)
    git(["-C", a, "checkout", "-q", "--detach", "dist/main"], v)
    plan2, r, p2 = plan_of(v, a)
    ok("next 계획 나옴", plan2 is not None, r.stderr[-300:])
    why = {}
    for o in plan2["ops"]:
        why.setdefault(o.get("why"), []).append(o["rel"])
    print("    계획: %s · 못 합침 %s · 남김 %s" % (why, [c["rel"] for c in plan2["conflicts"]], plan2["kept"]))
    ok("next 안 고친 것만 새 판", set(why.get("새 판으로 바꿈", [])) <= {"3_시스템/tokens.py", KNOWN}, why.get("새 판으로 바꿈"))
    r1 = run(["py", "-3", a + "/" + FO, "--vault", v, "update", p2, "--apply"], v)
    ok("next 적용 코드 0", r1.returncode == 0, r1.stderr[-300:])
    plan3, _, _ = plan_of(v, a)
    ok("next 두 번째 계획 0", plan3 is not None and not plan3["ops"], [(o.get("why"), o["rel"]) for o in (plan3 or {"ops": []})["ops"]][:6])
    ok("next 두 번째 못 합침 0", plan3 is not None and not plan3["conflicts"], (plan3 or {}).get("conflicts"))
    rj = json.loads(rd(v, "3_시스템/roles.json"))
    ok("next roles 내 값 + 새 칸", rj["roles"].get("내역할") == "2_지식/분야/내자리" and rj.get("다음판칸") == 1, list(rj)[:6])
    t = rd(v, "3_시스템/conventions.md")
    ok("next conventions 양쪽", "내가 더한 규칙" in t and "다음 판의 새 규칙" in t)
    ok("next default-layout 내 것", "내배치" in rd(v, "3_시스템/default-layout.json"))
    g = rd(v, ".gitignore")
    ok("next .gitignore 양쪽", "2_지식/비밀/" in g and "다음판제외/" in g)
    ok("next tokens 새 판", "다음 판 주석" in rd(v, "3_시스템/tokens.py"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True)
    ap.add_argument("--old", default="v2.1-template")
    ap.add_argument("--out")
    ap.add_argument("--only")
    a = ap.parse_args()
    S = a.out or os.path.join(tempfile.gettempdir(), "update_sim")
    wipe(S)
    os.makedirs(S)
    dist = os.path.abspath(a.dist)
    # 제작자 쪽: 배포판 이력 + 커밋 안 한 변경 = 새 판 → 표 → 바깥 저장소
    dev = os.path.join(S, "dev")
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"], dist).strip()
    git(["clone", "-q", "--no-local", "--single-branch", "--branch", branch, dist, dev], S)
    git(["fetch", "-q", "origin", "refs/tags/v*-template:refs/tags/v*-template"], dev)   # 다른 줄기의 설치 태그까지
    git(["tag", "시험옛판", a.old], dev)
    for line in git(["status", "--porcelain", "-z", "--untracked-files=all"], dist).split("\0"):
        if line:
            r = line[3:]
            s, d = os.path.join(dist, *r.split("/")), os.path.join(dev, *r.split("/"))
            if os.path.isfile(s):
                os.makedirs(os.path.dirname(d), exist_ok=True)
                shutil.copy2(s, d)
            elif os.path.exists(d):
                os.remove(d)
    git(["add", "-A"], dev)
    if git(["status", "--porcelain"], dev).strip():
        git(["commit", "-qm", "새 판(시험)"], dev)
    b = run(["py", "-3", dev + "/" + DD, "--build-known", dev], dev)
    print(b.stdout.strip() or b.stderr[-300:], "· 표 %.1fKB" % (os.path.getsize(os.path.join(dev, *KNOWN.split("/"))) / 1024))
    git(["add", "-A"], dev)
    if git(["status", "--porcelain"], dev).strip():
        git(["commit", "-qm", "표(시험)"], dev)
    git(["clone", "-q", "--bare", dev, os.path.join(S, "dist.git")], S)
    git(["branch", "-m", branch, "main"], os.path.join(S, "dist.git"))
    git(["remote", "add", "up", os.path.join(S, "dist.git")], dev)
    want = a.only.split(",") if a.only else ["full", "undo", "v0", "crlf", "conflict", "samename", "shallow", "notable", "next"]
    old = "시험옛판"
    for n in want:
        if n == "full":
            s_full(S, old)
        elif n == "undo":
            s_undo(S, old)
        elif n == "v0":
            s_v0(S)
        elif n == "crlf":
            s_crlf(S, old)
        elif n == "conflict":
            s_conflict(S, old)
        elif n == "samename":
            s_samename(S, old)
        elif n == "shallow":
            s_shallow(S, old)
        elif n == "notable":
            s_notable(S, old)
        elif n == "next":
            s_next(S, old, dev)
    print("통과 %d · 실패 %d" % (passes, len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
