"""privguard 시험 — 임시 볼트·임시 저장소에 가짜 개인 값을 넣어 막힘·통과를 센다(진짜 값·진짜 저장소는 안 씀).

  py -3 .claude/skills/dist-sync/scripts/test_privguard.py

① 제품 저장소 커밋: 가짜 값 = 거절 · 일반 표현 = 통과 · 있는 가짜 값 줄을 지우는 고침 = 통과 · personal/·매니페스트 자리 = 통과
② 볼트 저장소에는 훅을 걸지 않음(자동 커밋·노트 커밋 안 막힘) — 걸기를 거절하고, 노트에 가짜 값을 넣은 커밋이 그대로 됨
③ Claude Code 훅: 제품 경로 Write·Edit = 알림 · 노트 = 조용 · 지우는 Edit = 조용 · block 설정의 PreToolUse = 끝 코드 2
④ 지식 꼴: 노트 제목·별칭·일정·수집 이름에서 꼴이 생기고 흔한 말·짧은 말은 안 생김
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PG = os.path.join(HERE, "privguard.py")
spec = importlib.util.spec_from_file_location("privguard", PG)
pg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pg)

FAKE = "가짜과목테스트"        # 시험 전용 가짜 값(진짜 값 아님)
FAKE2 = "fake-sess-7781"
FAIL = []


def check(name, ok, info=""):
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else " — " + info))
    if not ok:
        FAIL.append(name)


def git(cwd, *a, ok=True):
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "init.defaultBranch=main",
                        "-c", "core.quotepath=off", *a], cwd=cwd, capture_output=True)
    if ok and r.returncode:
        raise RuntimeError("git %s: %s" % (a, r.stderr.decode("utf-8", "replace")))
    return r


def write(p, s):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def main():
    tmp = tempfile.mkdtemp(prefix="pg-test-")
    try:
        vault = os.path.join(tmp, "vault")
        rules = os.path.join(tmp, "rules.txt")
        write(rules, "%s\t시험 과목\n%s\t시험 세션 이름\n" % (FAKE, FAKE2))
        # 임시 볼트 — roles.json 만 진짜에서 복사(자리 이름표 · 개인 값 없음)
        write(os.path.join(vault, "3_시스템", "roles.json"), open(os.path.join(pg.VAULT, "3_시스템", "roles.json"), encoding="utf-8").read())
        os.makedirs(os.path.join(vault, pg.LOCAL))
        git(vault, "init", "-q")
        write(os.path.join(vault, "README.md"), "vault\n")
        git(vault, "add", "README.md")
        git(vault, "commit", "-qm", "init")

        # ① 제품 저장소
        repo = os.path.join(tmp, "product")
        os.makedirs(repo)
        git(repo, "init", "-q")
        write(os.path.join(repo, "src", "a.ts"), "export const x = 1;\n")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "init")
        r = subprocess.run([sys.executable, PG, "install-hook", repo, "--vault", vault], capture_output=True)
        check("① 훅 걸기", r.returncode == 0, r.stdout.decode("utf-8", "replace"))
        hook = os.path.join(repo, ".git", "hooks", "pre-commit")
        body = open(hook, encoding="utf-8").read()
        # 시험은 가짜 꼴 파일로 — 훅 줄에 --rules 를 붙인다
        write(hook, body.replace("--repo-product", '--repo-product --rules "%s"' % rules.replace("\\", "/")))
        conf = pg.load_conf(vault)
        check("① 저장소가 개인 설정에 적힘", pg.norm(repo) in conf.get("repos", []), str(conf))

        write(os.path.join(repo, "src", "a.ts"), "export const x = 1;\n// %s 일정\n" % FAKE)
        git(repo, "add", "-A")
        r = git(repo, "commit", "-qm", "leak", ok=False)
        err = r.stderr.decode("utf-8", "replace") + r.stdout.decode("utf-8", "replace")
        check("① 가짜 값 커밋 거절", r.returncode != 0 and "커밋 거절" in err and FAKE not in err, err[:300])
        check("① 값은 가려서", "가●" in err, err[:300])

        write(os.path.join(repo, "src", "a.ts"), "export const x = 1;\n// 과목A 일정\n")
        git(repo, "add", "-A")
        r = git(repo, "commit", "-qm", "generic", ok=False)
        check("① 일반 표현 통과", r.returncode == 0, r.stderr.decode("utf-8", "replace"))

        # 있는 개인 값 줄(훅 없이 들어간 옛 줄)을 지우는 고침
        write(os.path.join(repo, "src", "old.ts"), "a\n// %s\nb\n" % FAKE2)
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "old", "--no-verify")
        write(os.path.join(repo, "src", "old.ts"), "a\nb\n")
        git(repo, "add", "-A")
        r = git(repo, "commit", "-qm", "remove", ok=False)
        check("① 지우는 고침 통과", r.returncode == 0, r.stderr.decode("utf-8", "replace"))
        # 있는 값 줄의 곁을 고침·줄 옮김(수 같음) = 통과
        write(os.path.join(repo, "src", "keep.ts"), "a\n// %s 옛 주석\nb\n" % FAKE2)
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "keep", "--no-verify")
        write(os.path.join(repo, "src", "keep.ts"), "// %s 고친 주석\na\nb\n" % FAKE2)
        git(repo, "add", "-A")
        r = git(repo, "commit", "-qm", "edit beside", ok=False)
        check("① 곁 고침·줄 옮김(수 같음) 통과", r.returncode == 0, r.stderr.decode("utf-8", "replace"))
        write(os.path.join(repo, "src", "keep.ts"), "// %s 고친 주석\na\n// %s 하나 더\nb\n" % (FAKE2, FAKE2))
        git(repo, "add", "-A")
        r = git(repo, "commit", "-qm", "one more", ok=False)
        check("① 같은 값 하나 더(수 늚) 거절", r.returncode != 0)
        git(repo, "checkout", "-q", "HEAD", "--", "src/keep.ts")
        # 새 파일의 값 = 거절
        write(os.path.join(repo, "src", "old2.ts"), "// %s\n" % FAKE2)
        git(repo, "add", "-A")
        r = git(repo, "commit", "-qm", "again", ok=False)
        check("① 새 줄의 가짜 세션 이름 거절", r.returncode != 0)
        git(repo, "reset", "-q", "HEAD", "--", "src/old2.ts")
        os.remove(os.path.join(repo, "src", "old2.ts"))

        write(os.path.join(repo, "feature", "personal", "values.json"), '{"subject": "%s"}\n' % FAKE)
        write(os.path.join(repo, "mod", "module.json"), '{"personal": ["local/*.json"]}\n')
        write(os.path.join(repo, "mod", "local", "me.json"), '{"s": "%s"}\n' % FAKE)
        git(repo, "add", "-A")
        r = git(repo, "commit", "-qm", "personal parts", ok=False)
        check("① 개인화 파트(personal/ · 매니페스트 자리) 통과", r.returncode == 0, r.stderr.decode("utf-8", "replace"))

        # ② 볼트에는 걸지 않음
        r = subprocess.run([sys.executable, PG, "install-hook", vault, "--vault", vault], capture_output=True)
        check("② 볼트 훅 걸기 거절", r.returncode == 2 and not os.path.exists(os.path.join(vault, ".git", "hooks", "pre-commit")),
              r.stdout.decode("utf-8", "replace"))
        write(os.path.join(vault, "2_지식", "일", "노트.md"), "---\ntitle: t\n---\n%s 기록\n" % FAKE)
        git(vault, "add", "-A")
        r = git(vault, "commit", "-qm", "session: auto", ok=False)
        check("② 볼트 노트 자동 커밋 안 막힘", r.returncode == 0, r.stderr.decode("utf-8", "replace"))
        # 볼트 스테이지 검사(제품 경로만)도 노트는 안 봄
        r = subprocess.run([sys.executable, PG, "--diff", "HEAD~1..HEAD", "--vault", vault, "--rules", rules], cwd=vault, capture_output=True)
        check("② 볼트 diff 검사 — 노트 안 걸림", r.returncode == 0, r.stdout.decode("utf-8", "replace"))

        # ③ Claude Code 훅
        def run_hook(ev, ti, conf_mode=None):
            if conf_mode:
                c = pg.load_conf(vault)
                c["hook"] = conf_mode
                pg.save_conf(vault, c)
            data = json.dumps({"hook_event_name": ev, "tool_name": "Write", "tool_input": ti}, ensure_ascii=False)
            return subprocess.run([sys.executable, PG, "--hook", "--vault", vault, "--rules", rules],
                                  input=data.encode("utf-8"), capture_output=True)

        skill = os.path.join(vault, ".claude", "skills", "demo", "scripts", "x.py")
        write(skill, "print(1)\n")
        pre = "PreToolUse"     # 기본 = 늘면 막음
        r = run_hook(pre, {"file_path": skill, "content": "print(1)\n# %s\n" % FAKE})
        err = r.stderr.decode("utf-8", "replace")
        check("③ 새 값 Write = 막음(끝 코드 2 · 값 가림)", r.returncode == 2 and "privguard" in err and FAKE not in err and "가●" in err, err[:300])
        write(skill, "print(1)\n# %s 주석\n" % FAKE)
        r = run_hook(pre, {"file_path": skill, "old_string": "# %s 주석\n" % FAKE, "new_string": "# 과목A 주석\n"})
        check("③ 지우는 Edit = 통과", r.returncode == 0 and not r.stdout.strip(), err)
        r = run_hook(pre, {"file_path": skill, "old_string": "# %s 주석\n" % FAKE, "new_string": "# %s 고친 주석\n" % FAKE})
        check("③ 곁 고침 Edit(수 같음) = 통과", r.returncode == 0)
        r = run_hook(pre, {"file_path": skill, "content": "# %s 주석\nprint(1)\n" % FAKE})
        check("③ 줄 옮김 Write(수 같음) = 통과", r.returncode == 0)
        r = run_hook(pre, {"file_path": skill, "old_string": "# %s 주석\n" % FAKE, "new_string": "# %s 주석\n" % FAKE2})
        check("③ 다른 개인 값으로 바꿈 = 막음", r.returncode == 2)
        r = run_hook(pre, {"file_path": skill, "edits": [{"old_string": "print(1)", "new_string": "print('%s')" % FAKE}]})
        check("③ MultiEdit 같은 값 하나 더 = 막음", r.returncode == 2)
        note = os.path.join(vault, "2_지식", "일", "노트2.md")
        r = run_hook(pre, {"file_path": note, "content": "%s\n" % FAKE})
        check("③ 노트 = 조용", r.returncode == 0 and not r.stdout.strip() and not r.stderr.strip())
        pers = os.path.join(vault, ".claude", "skills", "demo", "personal", "v.json")
        r = run_hook(pre, {"file_path": pers, "content": FAKE})
        check("③ 스킬의 personal/ = 조용", r.returncode == 0 and not r.stderr.strip())
        r = run_hook(pre, {"file_path": skill, "content": "# 일반 글\n"})
        check("③ 일반 글 = 통과", r.returncode == 0)
        r = run_hook(pre, {"file_path": skill, "content": "# %s\n" % FAKE2}, conf_mode="alert")
        out = r.stdout.decode("utf-8", "replace")
        ok = False
        try:
            ok = "additionalContext" in json.loads(out)["hookSpecificOutput"]
        except (ValueError, KeyError):
            pass
        check("③ alert 설정 = 알림만(끝 코드 0)", r.returncode == 0 and ok, out[:200])
        # 오류 넷 = 통과(끝 코드 0) + «못 잼» 기록 — 2(막음)는 늘어남을 센 때만
        c = pg.load_conf(vault)
        c.pop("hook", None)
        pg.save_conf(vault, c)

        def raw_hook(inp, extra=()):
            return subprocess.run([sys.executable, PG, "--hook", "--vault", vault, *extra], input=inp, capture_output=True)

        good = json.dumps({"hook_event_name": "PreToolUse", "tool_input": {"file_path": skill, "content": "# %s\n" % FAKE2}}).encode()
        cases = [("꼴 파일 없음", raw_hook(good, ["--rules", os.path.join(tmp, "없는.txt")])),
                 ("깨진 JSON", raw_hook(b"{not json", ["--rules", rules])),
                 ("객체 아닌 입력", raw_hook(b"[1, 2]", ["--rules", rules])),
                 ("대본 안 예외", raw_hook(json.dumps({"hook_event_name": "PreToolUse", "tool_input": {"file_path": 12345}}).encode(), ["--rules", rules]))]
        for name, r in cases:
            check("③ 오류 «%s» = 통과(0)·못 잼 알림" % name, r.returncode == 0 and "검사 못 함" in r.stdout.decode("utf-8", "replace"),
                  "%d %s %s" % (r.returncode, r.stdout[-200:], r.stderr[-200:]))
        log = open(os.path.join(vault, pg.LOCAL, pg.LOG), encoding="utf-8").read()
        check("③ 오류 넷 = 기록 «못 잼» 4줄", log.count(" 못 잼 ") == 4, log)
        check("③ 기록에 값 없음", FAKE not in log and FAKE2 not in log and log.count("\n") >= 4, log)

        # ④ 지식 꼴
        kv = os.path.join(tmp, "kv")
        write(os.path.join(kv, "3_시스템", "roles.json"), open(os.path.join(vault, "3_시스템", "roles.json"), encoding="utf-8").read())
        write(os.path.join(kv, "2_지식", "배움", "가짜노트제목하나.md"), "---\ntitle: 가짜노트제목하나\naliases: [가짜별칭하나, 가짜]\n---\n")
        write(os.path.join(kv, "2_지식", "배움", "결과.md"), "---\ntitle: 결과\n---\n")
        write(os.path.join(kv, "2_지식", "일정", "내-일정.md"), "- [ ] 2030-01-02 (수) 10:00 가짜과목이름 · 가짜 일정 할 일 하나 둘 [[x]]\n")
        write(os.path.join(kv, "1_수집", "배움", "가짜수집폴더", "2030-01-01 가짜 공지 파일 이름.pdf"), "x")
        vals = dict(pg.knowledge_values(kv, set(), set()))
        for v in ("가짜노트제목하나", "가짜별칭하나", "가짜과목이름", "가짜 일정 할 일 하나 둘", "가짜수집폴더", "가짜 공지 파일 이름"):
            check("④ 꼴 생김: " + v, v in vals, str(sorted(vals)))
        check("④ 흔한 말(결과)·짧은 별칭 안 생김", "결과" not in vals and "가짜" not in vals)
        check("④ 날짜·확장자 뺀 값", "2030-01-01 가짜 공지 파일 이름" in vals and "배움" not in vals, str(sorted(vals)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("\n%s" % ("전부 통과" if not FAIL else "실패 %d: %s" % (len(FAIL), ", ".join(FAIL))))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
