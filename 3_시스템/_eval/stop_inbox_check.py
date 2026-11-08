# 받은함 되먹임 회귀 시험(ADR-028 · 11-03) · 실행: py -3 3_시스템/_eval/stop_inbox_check.py — 격리 볼트에 stop-check.ps1 사본을 두고 PowerShell 5.1 로 돌린다.
# 훅 입력은 실제처럼 UTF-8 바이트 · 세션 기록은 한글 경로(사용자 이름)에 둔다 — 시스템 코드 페이지가 65001 이 아닌 PC(cp949)에서 돌리면 경로가 깨져 되먹임이 조용히 안 걸린다(ADR-028 한계).
import json, os, shutil, subprocess, sys, tempfile

REAL = r"C:\Claude_Brain\3_시스템"
root = tempfile.mkdtemp(prefix="stopib-")
V = os.path.join(root, "vault")
H = os.path.join(V, "3_시스템", "hooks")
os.makedirs(H)
shutil.copy2(os.path.join(REAL, "hooks", "stop-check.ps1"), H)
shutil.copy2(os.path.join(REAL, "roles.json"), os.path.join(V, "3_시스템"))
R = json.load(open(os.path.join(REAL, "roles.json"), encoding="utf-8"))["roles"]
HOOK = os.path.join(H, "stop-check.ps1")
TR_DIR = os.path.join(root, "기록 한글")
os.makedirs(TR_DIR)
def put(r, s="x\n"):
    a = os.path.join(V, *r.split("/"))
    os.makedirs(os.path.dirname(a), exist_ok=True)
    open(a, "w", encoding="utf-8", newline="\n").write(s)
put(R["moc"], "---\ntitle: MOC\n---\n# MOC\n")
put(".gitignore", "3_시스템/_index/\n")
I = R["inbox"]
put(I + "/.gitkeep", "")
git = lambda *a: subprocess.run(["git", "-C", V, *a], capture_output=True, text=True, encoding="utf-8", errors="replace")
git("init", "-q"); git("config", "user.name", "시험"); git("config", "user.email", "t@local"); git("config", "commit.gpgsign", "false")
git("add", "-A"); git("commit", "-qm", "처음")
commits = lambda: int(git("rev-list", "--count", "HEAD").stdout.strip() or 0)
def transcript(name, lines):
    p = os.path.join(TR_DIR, name + ".jsonl")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        for l in lines:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    return p
def use(cmd):
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": cmd}}]}}
def said(text):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}
def stop(sid="s1", tr=None, raw=None, active=False):
    body = raw if raw is not None else json.dumps({"session_id": sid, "transcript_path": tr, "stop_hook_active": active}, ensure_ascii=False).encode("utf-8")
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", HOOK], input=body, capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", "replace").strip()
def blocked(out):
    try:
        j = json.loads(out)
    except ValueError:
        return None
    return j.get("reason") if j.get("decision") == "block" else None
res = []
def ok(name, cond, detail=""):
    res.append(bool(cond)); print(("통과" if cond else "실패"), name, str(detail)[:200])
touch = transcript("touch", [use("py -3 ana.py 1_수집/받은함/기물실/2_3.94.csv")])
ok("시험 전제: 세션 기록 경로에 한글", any(ord(c) > 127 for c in touch), touch)
# 받은함 빔
c, o = stop(tr=touch)
ok("받은함 빔 → 통과 · 출력 없음", c == 0 and o == "", o)
# 항목 있음
put(I + "/기물실/2_3.94.csv")
c, o = stop(sid="n0", tr=transcript("other", [use("ls")]))
ok("건드리지 않은 세션 → 통과", c == 0 and o == "", o)
c, o = stop(sid="n1", tr=transcript("said", [said("1_수집/받은함/기물실 을 나중에 봅니다")]))
ok("글로 말했을 뿐(도구 호출 아님) → 통과", c == 0 and o == "", o)
before = commits()
put("2_지식/바뀐 노트.md", "---\ntitle: 바뀐 노트\ncreated: 2026-11-03\n---\n# x\n")
put(R["moc"], "---\ntitle: MOC\n---\n# MOC\n- [[바뀐 노트]]\n")
c, o = stop(sid="s1", tr=touch)
why = blocked(o)
ok("건드리고 그대로 둠 → 되먹임 · 항목 이름 · inbox.py", c == 0 and why and "기물실" in why and "inbox.py" in why, why or o)
ok("되먹여도 자동 커밋은 함", commits() == before + 1, "%d → %d" % (before, commits()))
c, o = stop(sid="s1", tr=touch)
ok("같은 세션 같은 항목 두 번째 → 통과(한 번만)", c == 0 and o == "", o)
c, o = stop(sid="s2", tr=touch, active=True)
ok("stop_hook_active → 통과 · 소모 안 함", c == 0 and o == "", o)
c, o = stop(sid="s2", tr=touch)
ok("다른 세션은 따로 되먹임", blocked(o) is not None, o)
back = transcript("back", [use("type 1_수집\\받은함\\기물실\\2_3.94.csv")])
c, o = stop(sid="s3", tr=back)
ok("역슬래시 경로도 잡음", blocked(o) is not None, o)
# 다른 항목 · 칸
put(I + "/_기계칸/끝.md"); put(I + "/다른것.pdf")
c, o = stop(sid="s4", tr=transcript("skip", [use("cat 1_수집/받은함/_기계칸/끝.md"), use("cat 1_수집/받은함/.gitkeep")]))
ok("_ 칸·점 파일은 항목 아님 → 통과", c == 0 and o == "", o)
c, o = stop(sid="s5", tr=transcript("two", [use("cat 1_수집/받은함/기물실/a.csv 1_수집/받은함/다른것.pdf")]))
ok("둘 다 건드림 → 둘 다 이름", blocked(o) and "기물실" in blocked(o) and "다른것.pdf" in blocked(o), blocked(o))
# 다른 위반이 먼저 · 받은함 되먹임은 소모되지 않음
put(R["doing_notes"] + "/속성 없음.md", "# 없음\n")
c, o = stop(sid="s6", tr=touch)
why = blocked(o)
ok("다른 위반이 먼저 — 그 위반만 알림", why and "프론트매터 누락" in why and "받은함" not in why, why)
os.remove(os.path.join(V, *(R["doing_notes"] + "/속성 없음.md").split("/")))
c, o = stop(sid="s6", tr=touch)
ok("위반 고친 뒤 받은함 되먹임", blocked(o) is not None and "기물실" in blocked(o), o)
# 실패 방향 = 통과
c, o = stop(sid="s7", tr=os.path.join(TR_DIR, "없는 기록.jsonl"))
ok("세션 기록 없음 → 통과", c == 0 and o == "", o)
c, o = stop(raw=b"not json")
ok("입력이 깨짐 → 통과", c == 0 and o == "", o)
c, o = stop(raw=b"")
ok("입력 없음 → 통과", c == 0 and o == "", o)
# 비우면 끝
shutil.rmtree(os.path.join(V, *(I + "/기물실").split("/")))
os.remove(os.path.join(V, *(I + "/다른것.pdf").split("/")))
c, o = stop(sid="s8", tr=touch)
ok("비운 뒤 → 통과", c == 0 and o == "", o)
print("%d/%d" % (sum(res), len(res)))
shutil.rmtree(root, ignore_errors=True)
sys.exit(0 if all(res) else 1)
