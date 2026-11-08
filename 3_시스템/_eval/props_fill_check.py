# 새 노트 속성 표 채우기 회귀 시험(ADR-027) · 실행: py -3 3_시스템/_eval/props_fill_check.py [대본 자리] — 격리 볼트·격리 git · 실제 pre-commit 으로 돌린다
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8")
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REAL = r"C:\Claude_Brain\3_시스템"
try:
    import yaml
except ImportError:
    yaml = None
root = tempfile.mkdtemp(prefix="propfill-")
V = os.path.join(root, "볼트")
S = os.path.join(V, "3_시스템")
os.makedirs(S)
for f in ("props-sync.py", "roles.py", "roles.json"):
    shutil.copy2(os.path.join(SRC, f), os.path.join(S, f))
res = []


def ok(name, cond, detail=""):
    res.append(bool(cond))
    print(("통과" if cond else "실패"), name, detail if not cond else "")


def put(rel, data, old=False):
    a = os.path.join(V, *rel.split("/"))
    os.makedirs(os.path.dirname(a), exist_ok=True)
    with open(a, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))
    if old:
        t = time.time() - 86400 * 3
        os.utime(a, (t, t))
    return a


def raw(rel):
    with open(os.path.join(V, *rel.split("/")), "rb") as f:
        return f.read()


def get(rel):
    return raw(rel).decode("utf-8-sig")


def keys(text):
    fm = text.split("---", 2)[1]
    return [ln.split(":")[0] for ln in fm.replace("\r", "").split("\n") if ln and ln[0] not in " -#"]


def valid(text):
    return yaml is None or isinstance(yaml.safe_load(text.split("---", 2)[1]), dict)


put("2_지식/주제.md", "# 주제\n```json\n" + json.dumps({"topics": [{"이름": "과목A", "영역": "배움", "별칭": ["과A"], "상태": "진행"}, {"이름": "일감", "영역": "일", "상태": "진행"}]}, ensure_ascii=False) + "\n```\n")
spec = importlib.util.spec_from_file_location("props_sync", os.path.join(S, "props-sync.py"))
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)
R = json.load(open(os.path.join(S, "roles.json"), encoding="utf-8"))["props"]
WORK, KNOW = R["work"], R["knowledge"]


def fill(rel):
    return ps.fill(os.path.join(V, *rel.split("/")), rel)


# ── 한 노트 ──
OLD = "---\ntitle: 전과사유서\ncreated: 2026-11-01\nupdated: 2026-11-01\ntags: [전과]\nlinks: [\"[[다른]]\"]\nstatus: active\nsource: claude\n---\n# 본문\n\n내용 --- 줄\n"
a = put("0_작업/배움/과목A/과제1/노트.md", OLD, old=True)
mt = os.path.getmtime(a)
got = fill("0_작업/배움/과목A/과제1/노트.md")
t = get("0_작업/배움/과목A/과제1/노트.md")
ok("옛 꼴 작업 노트 = 표 순서 + 그 밖 뒤", keys(t) == WORK + ["links", "status"], str(keys(t)))
ok("넣은 키만 보고", got == ["주제", "마감", "단계", "의도", "aliases"], str(got))
ok("주제 = 자리로 · 빈 칸은 키만", "주제: 과목A\n마감:\n단계:\n의도:\naliases: []\n" in t, t[:200])
ok("있는 값 그대로 · 본문 그대로 · YAML 유효", "tags: [전과]" in t and 'links: ["[[다른]]"]' in t and t.endswith("---\n# 본문\n\n내용 --- 줄\n") and valid(t), t)
ok("수정 시각 되돌림 · 임시 파일 안 남음", abs(os.path.getmtime(a) - mt) < 1 and not os.path.exists(a + ".~props"))
ok("다시 돌려도 같음", fill("0_작업/배움/과목A/과제1/노트.md") is None)
put("2_지식/일/일감/지식.md", "---\ntype: decision\ntitle: ADR\ncreated: 2026-11-01\ntags: []\nlinks: []\nstatus: accepted\nsource: session\n---\n# x\n", old=True)
fill("2_지식/일/일감/지식.md")
t = get("2_지식/일/일감/지식.md")
ok("지식 층 표 · type 은 뒤로 · status 값 안 덮음", keys(t) == KNOW + ["type"] and "status: accepted" in t and valid(t), str(keys(t)))
ok("옛 source session = claude", "source: claude" in t and "session" not in t, t)
put("0_작업/일/일감/source없음.md", "---\ntitle: a\n---\nb\n", old=True)
fill("0_작업/일/일감/source없음.md")
ok("source 모르면 빈 칸(거짓 표시 안 함)", "\nsource:\n" in get("0_작업/일/일감/source없음.md"), get("0_작업/일/일감/source없음.md"))
# 손대지 않는 것
for rel, body, why in [
    ("0_작업/일/일감/CLAUDE.새안.md", "# 코어 초안\n내용\n", "속성 없는 md(코어 초안)"),
    ("0_작업/일/일감/가로줄.md", "---\n그냥 글\ntitle: 글 속 줄\n---\n뒤 글\n", "맨 위 가로줄 사이 글"),
    ("0_작업/일/일감/SKILL.md", "---\nname: x\ndescription: y\n---\n본문\n", "표 키가 없는 머리"),
    ("0_작업/일/일감/빈틀.md", "---\n---\nb\n", "빈 머리"),
    ("0_작업/일/일감/닫힘없음.md", "---\ntitle: a\n본문 닫는 줄 없음\n", "닫는 줄 없음"),
    ("0_작업/일/x/node_modules/p/README.md", "---\ntitle: p\n---\nb\n", "node_modules"),
]:
    put(rel, body, old=True)
    got = fill(rel)
    ok("손대지 않음 — " + why, got is None and get(rel) == body, str(got) + " " + get(rel)[:80])
put("0_작업/일/일감/제목.md", '---\ntags: []\n---\nb\n', old=True)
put("0_작업/일/일감/[초안] 이름.md", '---\ntags: []\n---\nb\n', old=True)
fill("0_작업/일/일감/[초안] 이름.md")
ok("특수 글자 제목 = 큰따옴표 · YAML 유효", 'title: "[초안] 이름"\n' in get("0_작업/일/일감/[초안] 이름.md") and valid(get("0_작업/일/일감/[초안] 이름.md")), get("0_작업/일/일감/[초안] 이름.md"))
put("0_작업/일/일감/crlf.md", b"\xef\xbb\xbf---\r\ntitle: c\r\ncreated: 2026-11-01\r\n---\r\nbody\r\n", old=True)
fill("0_작업/일/일감/crlf.md")
b = raw("0_작업/일/일감/crlf.md")
ok("BOM·CRLF 유지", b.startswith(b"\xef\xbb\xbf---\r\n") and b"\n" not in b.replace(b"\r\n", b"") and b.endswith(b"---\r\nbody\r\n"), repr(b[:80]))
put("0_작업/일/일감/여러줄.md", "---\ntitle: >\n  긴 제목\ntags:\n  - a\n  - b\ncreated: 2026-11-01\n---\nb\n", old=True)
fill("0_작업/일/일감/여러줄.md")
t = get("0_작업/일/일감/여러줄.md")
ok("여러 줄 값은 덩이로 옮김 · YAML 유효", "title: >\n  긴 제목\n" in t and "tags:\n  - a\n  - b\n주제:" in t and valid(t), t)
put("0_작업/일/일감/작업.md", "---\n단계: 끝\n---\n", old=True)
fill("0_작업/일/일감/작업.md")
t = get("0_작업/일/일감/작업.md")
ok("탐색기 «끝냄» 작업.md = 표 + 단계 값 유지", keys(t) == WORK and "단계: 끝\n" in t, t)
wk = importlib.util.spec_from_file_location("work_real", os.path.join(REAL, "work.py"))
w = importlib.util.module_from_spec(wk)
wk.loader.exec_module(w)
fm = w.front(os.path.join(V, "0_작업", "일", "일감", "작업.md"))
ok("work.py 가 읽는 단계 그대로 · 빈 칸은 빈 글", fm.get("단계") == "끝" and fm.get("마감") == "" and fm.get("의도") == "", str(fm))
ok("표 없는 자리", all(ps.table_of(r) is None for r in ["2_지식/_x/a.md", "1_수집/배움/과목A/메모.md", "2_지식/MOC.md", "2_지식/recent.md", "2_지식/일정/내-일정.md", "2_지식/일/외부뇌/설계노트.md"]))
import roles as rr  # 시험 볼트의 roles
rr.VAULT = V
put("0_작업/배움/과목A/빈주제.md", "---\ntitle: x\n주제:\n마감:\n---\n", old=True)
ok("빈 «주제:» = 다음 줄을 값으로 잡아도 자리로 돌아감", rr.topic_of("0_작업/배움/과목A/과제1/노트.md") == "과목A", str(rr.topic_of("0_작업/배움/과목A/과제1/노트.md")))

# ── git: 실제 pre-commit ──
env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")


def git(*a):
    return subprocess.run(["git", "-c", "core.quotepath=false", *a], cwd=V, capture_output=True, env=env)


git("init", "-q")
git("config", "core.autocrlf", "false")
shutil.copy2(os.path.join(REAL, "hooks", "pre-commit"), os.path.join(V, ".git", "hooks", "pre-commit"))
OLDNOTE = "---\ntitle: 옛\ncreated: 2026-01-01\nupdated: 2026-01-01\ntags: []\nlinks: []\nstatus: active\nimportance: 3\nsource: session\n---\n# 옛 노트 — 표 없이 그대로\n" + "내용\n" * 40
put("2_지식/일/일감/옛노트.md", OLDNOTE, old=True)
put("2_지식/일/일감/옮길노트.md", OLDNOTE.replace("옛 노트", "옮길"), old=True)
RECENT = OLDNOTE.replace("created: 2026-01-01", "created: 2026-11-01").replace("옛 노트", "요즘 노트")
put("2_지식/일/일감/요즘노트.md", RECENT, old=True)
git("add", "-A")
git("commit", "-qm", "base", "--no-verify")
put("2_지식/일/일감/옛노트.md", OLDNOTE + "덧붙임\n", old=True)
put("2_지식/일/일감/요즘노트.md", RECENT + "덧붙임\n", old=True)
git("mv", "2_지식/일/일감/옮길노트.md", "2_지식/일/일감/옮긴노트.md")
NEW = "---\ntitle: 새\ncreated: 2026-11-03\ntags: []\nlinks: [\"[[a]]\"]\nstatus: active\nsource: claude\n---\n# 새 노트\n"
put("0_작업/일/일감/새노트.md", NEW)
put("2_지식/일/일감/새지식.md", NEW)
SENS = NEW.replace("source: claude\n", "source: claude\nsensitive: true\n").replace("# 새 노트", "# 민감 본문 비밀문구XYZ")
put("0_작업/일/일감/민감.md", SENS)
put("2_지식/일/일감/민감지식.md", SENS)
put("0_작업/일/일감/코어초안.md", "# 코어 초안\n")
git("add", "-A")
c = git("commit", "-qm", "t")
ok("커밋 성공(실제 pre-commit)", c.returncode == 0, (c.stdout + c.stderr).decode("utf-8", "replace"))
show = git("show", "HEAD:0_작업/일/일감/새노트.md").stdout.decode("utf-8")
ok("새 노트 = 커밋 내용에 표", keys(show)[: len(WORK)] == WORK, show[:200])
ok("작업본도 같음 · 남는 변경 없음", get("0_작업/일/일감/새노트.md") == show and not [ln for ln in git("status", "--porcelain").stdout.decode("utf-8").splitlines() if "새노트" in ln])
ok("코어 초안 = 그대로 커밋", git("show", "HEAD:0_작업/일/일감/코어초안.md").stdout.decode("utf-8") == "# 코어 초안\n")
tree = git("ls-tree", "-r", "--name-only", "HEAD").stdout.decode("utf-8")
ok("민감 노트 2개 = 표 넣고도 커밋 안 됨", "민감" not in tree and "비밀문구XYZ" not in git("log", "-p", "--all").stdout.decode("utf-8", "replace"), tree)
ok("민감 노트 = 작업본엔 표 · 민감 줄 유지 · 표 뒤로", keys(get("0_작업/일/일감/민감.md")) == WORK + ["links", "status", "sensitive"] and "\nsensitive: true\n" in get("0_작업/일/일감/민감.md"), get("0_작업/일/일감/민감.md")[:260])
oldc = git("show", "HEAD:2_지식/일/일감/옛노트.md").stdout.decode("utf-8")
ok("고친 옛 노트 = 표 안 넣음 · updated 만", "주제" not in oldc and "importance: 3" in oldc and "source: session" in oldc and "updated: 2026-01-01" not in oldc, oldc[:220])
rec = git("show", "HEAD:2_지식/일/일감/요즘노트.md").stdout.decode("utf-8")
ok("고친 요즘 노트(created ≥ SINCE) = 표", keys(rec)[: len(KNOW)] == KNOW and "source: claude" in rec, rec[:220])
mvd = git("show", "HEAD:2_지식/일/일감/옮긴노트.md").stdout.decode("utf-8")
ok("옮긴 옛 노트 = 표 안 넣음", "주제" not in mvd and "source: session" in mvd, mvd[:200])
# Claude 가 통째로 덮어써 표가 빠져도 다음 커밋에 돌아옴
put("0_작업/일/일감/새노트.md", NEW + "덮어씀\n", old=True)
git("add", "-A")
git("commit", "-qm", "t2")
ok("통째로 덮어쓴 새 노트 = 다음 커밋에 표 돌아옴", keys(git("show", "HEAD:0_작업/일/일감/새노트.md").stdout.decode("utf-8"))[: len(WORK)] == WORK)
# 대본이 깨져도 커밋은 된다
good = open(os.path.join(S, "roles.json"), encoding="utf-8").read()
with open(os.path.join(S, "roles.json"), "w", encoding="utf-8") as f:
    f.write("{ 깨진 json")
put("0_작업/일/일감/깨진때.md", NEW)
git("add", "-A")
c = git("commit", "-qm", "t3")
ok("roles.json 이 깨져도 커밋은 된다(표만 안 들어감)", c.returncode == 0 and "깨진때" in git("ls-tree", "-r", "--name-only", "HEAD").stdout.decode("utf-8"), (c.stdout + c.stderr).decode("utf-8", "replace"))
with open(os.path.join(S, "roles.json"), "w", encoding="utf-8") as f:
    f.write(good)
# (옛 결함 재현) 민감 노트를 옮기면 pre-commit 이 못 본다 — ACM 만 보고 R 을 건너뜀
put("2_지식/일/일감/옮길민감.md", NEW.replace("source: claude\n", "source: claude\n") + "민감 표시 전\n" * 30, old=True)
git("add", "-A")
git("commit", "-qm", "t4", "--no-verify")
body = get("2_지식/일/일감/옮길민감.md").replace("status: active\n", "status: active\nsensitive: true\n", 1)
put("2_지식/일/일감/옮길민감.md", body, old=True)
git("mv", "2_지식/일/일감/옮길민감.md", "2_지식/일/일감/옮긴민감.md")
git("add", "-A")
git("commit", "-qm", "t5")
leak = "sensitive: true" in git("show", "HEAD:2_지식/일/일감/옮긴민감.md").stdout.decode("utf-8", "replace")
print("참고(옛 결함) 민감 표시 + 이름 바꿈 = 커밋에 들어감:", leak)
print("%d/%d" % (sum(res), len(res)))
shutil.rmtree(root, ignore_errors=True)
sys.exit(0 if all(res) else 1)
