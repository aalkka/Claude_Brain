# 웹 공지 보존 회귀 시험(11-03 · ADR-029) · 실행: py -3 3_시스템/_eval/web_expire_check.py — 격리 볼트에서 마감 + 30일 지난 글만 휴지통으로 가는지 · 두는 경우(마감 모름·쓸모 표시·노트가 가리킴·표 처리 바꿈)를 건드리지 않는지
import datetime, json, os, shutil, subprocess, sys, tempfile

REAL = r"C:\Claude_Brain\3_시스템"
root = tempfile.mkdtemp(prefix="wexp-")
V = os.path.join(root, "vault")
S = os.path.join(V, "3_시스템")
os.makedirs(os.path.join(S, "collect"))
for f in ("fileops.py", "roles.py", "roles.json", "web-collect.py"):
    shutil.copy2(os.path.join(REAL, f), os.path.join(S, f))
R = json.load(open(os.path.join(S, "roles.json"), encoding="utf-8"))["roles"]
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", FILEOPS_NO_OBSIDIAN="1")
res = []
today = datetime.date.today()
old = (today - datetime.timedelta(days=31)).isoformat()      # 마감 + 30일 지남
edge = (today - datetime.timedelta(days=30)).isoformat()     # 딱 30일 — 아직 둠
SID = "ku-test"
N = R["school_notice"] + "/장학"
NB = N.replace("/", "\\")


def a(r):
    return os.path.join(V, *r.split("/"))


def put(r, s="글\n"):
    os.makedirs(os.path.dirname(a(r)), exist_ok=True)
    open(a(r), "w", encoding="utf-8").write(s)


def ok(name, cond, detail=""):
    res.append(bool(cond))
    print("%s %s%s" % ("통과" if cond else "실패", name, "" if cond else " — %s" % (detail,)))


def retention(how="자동 휴지통", days=30):
    put(R["retention"], "# 보존\n```json\n" + json.dumps({"칸": {"웹공지": {"기준": "마감", "날": days, "처리": how}}}, ensure_ascii=False) + "\n```\n")


def run(*args):
    r = subprocess.run([sys.executable, os.path.join(S, "web-collect.py"), *args], cwd=V, env=ENV, capture_output=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def state():
    return json.load(open(os.path.join(S, "_index", "collect", SID + ".json"), encoding="utf-8"))["items"]


def ops():
    p = os.path.join(S, "ledger", "ops.jsonl")
    return [json.loads(x) for x in open(p, encoding="utf-8")] if os.path.exists(p) else []


# 조리법 · 판정 대역(notice-filter 는 판정 캐시를 읽는 층 — 여기선 값만 준다)
json.dump({"id": SID, "family": "regex", "contract": "시험", "filter": {"card": "x"}, "folder": "@school_notice/장학"},
          open(os.path.join(S, "collect", SID + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
J = {"a1": ("해당", "", old), "a2": ("확인 필요", "", edge), "a3": ("확인 필요", "", None), "a4": ("해당", "", old), "a5": ("해당", "", old), "a6": ("해당", "", "0000-00-00")}
open(os.path.join(S, "notice-filter.py"), "w", encoding="utf-8").write(
    "J = %r\ndef judged(sid):\n    return J\ndef load_marks():\n    return {%r: {'평가': '쓸모'}}\n" % (J, SID + ":a4"))
items = {}
for k in J:
    put("%s/%s 공지.md" % (N, k), "# %s\n" % k)
    items[k] = {"date": "2026-01-01", "title": k + " 공지", "path": "%s\\%s 공지.md" % (NB, k), "run": "r", "verdict": "해당"}
put("%s/a1 공지/붙임.pdf" % N, "PDF")
put("1_수집/.web/%s/a1.html" % SID, "<html>")
put(R["schedule"] + "/장학-마감.md", "- [ ] %s [[a1 공지|원본]]\n" % old)     # 생성되는 일정 파일은 세지 않는다
put(R["field_notes"] + "/장학 정리.md", "[[a5 공지]]\n")                        # 사람 노트가 가리키면 둔다
os.makedirs(os.path.join(S, "_index", "collect"), exist_ok=True)
json.dump({"items": items}, open(os.path.join(S, "_index", "collect", SID + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
retention()

code, out = run("--expire", "--dry")
ok("미리 보기 = 아무것도 안 옮김", code == 0 and "a1 공지" in out and os.path.exists(a("%s/a1 공지.md" % N)) and not ops(), out)
code, out = run("--expire")
ok("마감 + 30일 지남 = 글·첨부 폴더·원시 휴지통", code == 0 and not os.path.exists(a("%s/a1 공지.md" % N)) and not os.path.exists(a("%s/a1 공지" % N)) and not os.path.exists(a("1_수집/.web/%s/a1.html" % SID)), out)
e = ops()
ok("장부 = script:web-collect · 휴지통 자리 · 3줄", len(e) == 3 and all(x["op"] == "rm" and x["by"] == "script:web-collect" and x["dst"].startswith(".trash/") and x.get("user_asked") for x in e), e)
st = state()
ok("상태 = expired · 지남 · 다시 안 받음(글 번호 남음)", st["a1"].get("expired") and "path" not in st["a1"] and st["a1"]["verdict"] == "지남", st["a1"])
ok("딱 30일 = 둠", os.path.exists(a("%s/a2 공지.md" % N)) and st["a2"].get("path"))
ok("마감 모름 = 둠", os.path.exists(a("%s/a3 공지.md" % N)) and os.path.exists(a("%s/a6 공지.md" % N)))
ok("쓸모 표시 = 둠", os.path.exists(a("%s/a4 공지.md" % N)) and st["a4"].get("path"))
ok("노트가 가리킴 = 둠", os.path.exists(a("%s/a5 공지.md" % N)) and st["a5"].get("path"))
code, out = run("--expire")
ok("두 번째 = 그대로", code == 0 and len(ops()) == 3, ops())
code, out = subprocess.run([sys.executable, os.path.join(S, "fileops.py"), "undo", e[0]["batch"]], cwd=V, env=ENV, capture_output=True, encoding="utf-8", errors="replace").returncode, ""
ok("되돌리기 = 제자리", code == 0 and os.path.exists(a("%s/a1 공지.md" % N)) and os.path.exists(a("%s/a1 공지/붙임.pdf" % N)))
# 표로 끄기 — «후보»·날 null 이면 자동으로 안 지움
st_ = json.load(open(os.path.join(S, "_index", "collect", SID + ".json"), encoding="utf-8"))
st_["items"]["a1"]["path"] = st_["items"]["a1"].pop("expired")
json.dump(st_, open(os.path.join(S, "_index", "collect", SID + ".json"), "w", encoding="utf-8"), ensure_ascii=False)
n0 = len(ops())
retention(how="후보")
run("--expire")
ok("표의 처리 = 후보 → 안 지움", len(ops()) == n0 and os.path.exists(a("%s/a1 공지.md" % N)))
retention(days=None)
run("--expire")
ok("표의 날 = null → 안 지움", len(ops()) == n0 and os.path.exists(a("%s/a1 공지.md" % N)))
shutil.rmtree(root, ignore_errors=True)
print("%d/%d" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
