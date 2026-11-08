# 따라가기 회귀 시험(11-03 · 설계안 §19.3) · 실행: py -3 3_시스템/_eval/follow_check.py — 격리 볼트에서 바깥 이동·지움을 일으켜 follow.py 가 장부·링크·색인·짝 메모·LMS 목록을 맞추는지 · 장부 안 일을 두 번 적지 않는지 · 못 고르는 것·떼로 사라짐을 건드리지 않는지
import json, os, shutil, subprocess, sys, tempfile

REAL = r"C:\Claude_Brain\3_시스템"
root = tempfile.mkdtemp(prefix="follow-")
V = os.path.join(root, "vault")
S = os.path.join(V, "3_시스템")
os.makedirs(S)
for f in ("fileops.py", "roles.py", "roles.json", "follow.py"):
    shutil.copy2(os.path.join(REAL, f), os.path.join(S, f))
R = json.load(open(os.path.join(S, "roles.json"), encoding="utf-8"))["roles"]
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", FILEOPS_NO_OBSIDIAN="1", FOLLOW_NO_INGEST="1")
TXT = "내용이 충분히 긴 줄 " * 12
K, W, SCH, IDX = R["field_notes"], R["work"], R["school"], R["source_index"]
MAN = os.path.join(S, "_index", "lms", "manifest.json")
res = []


def a(r):
    return os.path.join(V, *r.split("/"))


def put(r, data=TXT):
    os.makedirs(os.path.dirname(a(r)), exist_ok=True)
    open(a(r), "wb").write(data if isinstance(data, bytes) else data.encode("utf-8"))


def read(r):
    return open(a(r), encoding="utf-8").read()


def mv(o, n):
    os.makedirs(os.path.dirname(a(n)), exist_ok=True)
    os.rename(a(o), a(n))


def run(script, *args):
    r = subprocess.run([sys.executable, os.path.join(S, script), *args], cwd=V, env=ENV, capture_output=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def fol(*args):
    return run("follow.py", *args)


def rep():
    code, out = fol("--json")
    return json.loads(out.splitlines()[-1])


def ops():
    p = os.path.join(S, "ledger", "ops.jsonl")
    return [json.loads(x) for x in open(p, encoding="utf-8")] if os.path.exists(p) else []


def mine(n0):
    return ops()[n0:]


def ok(name, cond, detail=""):
    res.append(bool(cond))
    print("%s %s%s" % ("통과" if cond else "실패", name, "" if cond else " — %s" % detail))


# ── 씨앗 ──
put(K + "/컴/가.md", "# 가\n" + TXT)
put(K + "/컴/나.md", "# 나\n" + TXT + "나")
put(K + "/컴/링크.md", "[[가]] [[2_지식/분야/컴/가]] [[나]] [[나|별칭]] [보기](나.md)\n"
                     "![[1_수집/배움/과목A/강의자료/s.pdf]] [[1_수집/_색인/배움/과목A/강의자료/s.pdf.색인]]\n"
                     "[[0_작업/배움/과목A/보고서/초안]]\n")
put(K + "/x/다.md", "# x 다\n" + TXT)
put(K + "/y/다.md", "# y 다\n" + TXT)
put(K + "/이름링크.md", "[[다]]\n")
put(K + "/rel/노트.md", "[[./옆]]\n" + TXT)
put(K + "/rel/옆.md", "옆\n" + TXT)
put(K + "/고친채옮김.md", "처음\n" + TXT)
put(K + "/Eng.md", "eng\n" + TXT)
put(SCH + "/과목A/강의자료/s.pdf", b"PDF-S " * 40)
put(SCH + "/과목A/강의자료/s.md", "s 의 짝 메모\n")
put(IDX + "/배움/과목A/강의자료/s.pdf.색인.md", "색인\n")
put(SCH + "/과목A/강의자료/lost.pdf", b"PDF-LOST " * 40)
put(SCH + "/과목A/강의자료/lost2.pdf", b"PDF-LOST2 " * 40)
put(SCH + "/과목A/강의자료/lost3.pdf", b"PDF-LOST3 " * 40)
put(SCH + "/과목A/강의자료/사본.pdf", b"PDF-COPY " * 40)
put(SCH + "/과목A/강의자료/사본2.pdf", b"PDF-COPY " * 40)
put(SCH + "/과목A/공지/2026-10-01 공지.md", "공지\n")
put(SCH + "/과목A/같은이름/x.pdf", b"PDF-X " * 40)
put(SCH + "/과목A/같은이름/x.hwp", b"HWP-X " * 40)
put(SCH + "/과목A/같은이름/x.md", "x 짝\n")
put(SCH + "/과목A/쌍둥이/하나.pdf", b"TWIN " * 40)
put(SCH + "/과목A/쌍둥이/둘.pdf", b"TWIN " * 40)
put(R["school_notice"] + "/장학/공지.md", "웹 공지\n" + TXT)
put(W + "/배움/과목A/보고서/초안.md", "# 초안\n" + TXT)
put(W + "/배움/과목A/보고서/그림.png", b"PNG " * 40)
put(W + "/배움/과목A/기록.sheet", b"SHEET " * 40)
put(W + "/배움/과목A/기록.md", "시트 짝\n")
put(W + "/배움/과목A/~$초안.docx", b"LOCK")
for i in range(130):
    put(SCH + "/과목C/떼/f%03d.pdf" % i, ("BULK%03d " % i).encode() * 20)
sha = lambda r: __import__("hashlib").sha256(open(a(r), "rb").read()).hexdigest()
os.makedirs(os.path.dirname(MAN), exist_ok=True)
json.dump({"items": {"ann:1": {"hash": "h", "path": "1_수집\\배움\\과목A\\공지\\2026-10-01 공지.md", "run": "r"}},
           "files": {"canvas:1": {"sha": sha(SCH + "/과목A/강의자료/s.pdf"), "path": "1_수집\\배움\\과목A\\강의자료\\s.pdf", "run": "r"},
                     "canvas:2": {"sha": sha(SCH + "/과목A/강의자료/lost.pdf"), "path": "1_수집\\배움\\과목A\\강의자료\\lost.pdf", "run": "r"},
                     "board:7:/posts/9:lost2.pdf": {"sha": sha(SCH + "/과목A/강의자료/lost2.pdf"), "path": "1_수집\\배움\\과목A\\강의자료\\lost2.pdf", "run": "r"},
                     "canvas:4": {"sha": sha(SCH + "/과목A/강의자료/사본.pdf"), "path": "1_수집\\배움\\과목A\\강의자료\\사본.pdf", "run": "r"}},
           "board": {"7": {"글|날짜": {"path": "/posts/9", "run": "r", "md": None}}}},
          open(MAN, "w", encoding="utf-8"), ensure_ascii=False)

# ① 처음 = 사진만
r = rep()
ok("처음 = 사진만 · 장부 0", r["first"] and not ops() and os.path.exists(os.path.join(S, "_index", "follow", "snapshot.json")), r)
# ② 그대로면 아무것도 안 함 · 세션 시작 줄 글자 0
ok("그대로 = «바뀐 것 없음»", fol()[1].endswith("바뀐 것 없음"), fol()[1])
ok("그대로 = --hook 글자 0", fol("--hook")[1] == "", fol("--hook")[1])
# ③ 이름 바꿈 — 이름 링크·경로 링크·마크다운 링크
n0 = len(ops())
mv(K + "/컴/나.md", K + "/컴/나2.md")
r = rep()
t = read(K + "/컴/링크.md")
e = mine(n0)
ok("이름 바꿈 = 장부 rename(바깥) 1줄", len(e) == 1 and e[0]["op"] == "rename" and e[0].get("outside") and e[0]["via"] == "follow" and e[0]["by"] == "user", e)
ok("이름 바꿈 = 이름·별칭·마크다운 링크 고침", "[[나2]]" in t and "[[나2|별칭]]" in t and "(나2.md)" in t and "[[나]]" not in t, t)
ok("이름 바꿈 = 다시 돌려도 안 적음", (fol("--hook")[1] == "" and len(mine(n0)) == 1), mine(n0))
# ④ 자리 옮김 — 이름 링크는 그대로 · 경로 링크만
mv(K + "/컴/가.md", K + "/컴2/가.md")
rep()
t = read(K + "/컴/링크.md")
ok("자리 옮김 = 경로 링크 고침 · 이름 링크 그대로", "[[2_지식/분야/컴2/가]]" in t and "[[가]]" in t, t)
# ⑤ 옮기며 고침 — 파일번호로 잡음
n0 = len(ops())
mv(K + "/고친채옮김.md", K + "/컴2/고친채옮김.md")
put(K + "/컴2/고친채옮김.md", read(K + "/컴2/고친채옮김.md") + "더함\n") if False else open(a(K + "/컴2/고친채옮김.md"), "a", encoding="utf-8").write("더함\n")
r = rep()
ok("옮기며 고침 = 옮김(파일번호)", r["moved"] == 1 and r["gone"] == 0, r)
# ⑥ 대소문자만
n0 = len(ops())
mv(K + "/Eng.md", K + "/eng.md")
r = rep()
ok("대소문자만 = 이름 바꿈", r["moved"] == 1 and mine(n0)[-1]["op"] == "rename", r)
# ⑦ 옛 이름이 다른 파일에도 있으면 이름 링크를 안 고침(남의 링크 오염 방지)
mv(K + "/x/다.md", K + "/x/다2.md")
r = rep()
ok("같은 이름 있음 = [[다]] 그대로 + 알림", read(K + "/이름링크.md").strip() == "[[다]]" and any("같은 이름" in w for w in r["warn"]), (read(K + "/이름링크.md"), r))
# ⑧ 상대 링크
mv(K + "/rel/노트.md", K + "/rel2/노트.md")
rep()
ok("상대 링크 = 새 폴더 기준", "[[../rel/옆]]" in read(K + "/rel2/노트.md"), read(K + "/rel2/노트.md"))
# ⑨ 복사 후 지움(파일번호가 달라짐) — 해시 · 원본 뒤처리 전부
n0 = len(ops())
dst = SCH + "/과목A/과제/s.pdf"
os.makedirs(os.path.dirname(a(dst)), exist_ok=True)
shutil.copy2(a(SCH + "/과목A/강의자료/s.pdf"), a(dst))
os.remove(a(SCH + "/과목A/강의자료/s.pdf"))
r = rep()
t = read(K + "/컴/링크.md")
man = json.load(open(MAN, encoding="utf-8"))
ok("복사 후 지움 = 옮김(해시)", r["moved"] == 1 and r["gone"] == 0, r)
ok("원본 옮김 = 짝 메모 따라감", os.path.exists(a(SCH + "/과목A/과제/s.md")) and not os.path.exists(a(SCH + "/과목A/강의자료/s.md")), r)
ok("원본 옮김 = 색인 거울 옮김", os.path.exists(a(IDX + "/배움/과목A/과제/s.pdf.색인.md")) and not os.path.exists(a(IDX + "/배움/과목A/강의자료/s.pdf.색인.md")), r)
ok("원본 옮김 = 원본·색인 링크 고침", "![[1_수집/배움/과목A/과제/s.pdf]]" in t and "[[1_수집/_색인/배움/과목A/과제/s.pdf.색인]]" in t, t)
ok("원본 옮김 = LMS 목록 경로(역슬래시 그대로)", man["files"]["canvas:1"]["path"] == "1_수집\\배움\\과목A\\과제\\s.pdf", man["files"]["canvas:1"])
ok("원본 옮김 = 짝 메모까지 같은 묶음", len({x["batch"] for x in mine(n0)}) == 1 and len(mine(n0)) == 2 and mine(n0)[1]["by"] == "script:follow", mine(n0))
# ⑩ 되돌리기 — 묶음째 · 그 뒤 비교가 바깥으로 안 적음
code, out = run("fileops.py", "undo", mine(n0)[0]["batch"])
ok("되돌리기 = 원본·짝 메모 제자리 · 링크 돌아옴", os.path.exists(a(SCH + "/과목A/강의자료/s.pdf")) and os.path.exists(a(SCH + "/과목A/강의자료/s.md")) and "![[1_수집/배움/과목A/강의자료/s.pdf]]" in read(K + "/컴/링크.md"), out)
n1 = len(ops())
r = rep()
ok("되돌리기 뒤 = 바깥으로 안 적음", r["moved"] == 0 and r["gone"] == 0 and len(ops()) == n1, r)
# ⑪ 같은 이름 다른 원본이 옆에 남으면 X.md 는 안 끌고 감
mv(SCH + "/과목A/같은이름/x.pdf", SCH + "/과목A/같은이름2/x.pdf")
rep()
ok("x.hwp 가 남으면 x.md 는 그대로", os.path.exists(a(SCH + "/과목A/같은이름/x.md")) and not os.path.exists(a(SCH + "/과목A/같은이름2/x.md")))
# ⑫ 폴더째 옮김 = 장부 한 줄 · 안쪽 링크 고침 · 되돌리기
n0 = len(ops())
mv(W + "/배움/과목A/보고서", W + "/배움/과목B/보고서")
r = rep()
e = mine(n0)
ok("폴더째 = 한 줄(파일 2)", r["moved"] == 2 and len(e) == 1 and e[0]["kind"] == "dir" and e[0]["n"] == 2 and e[0]["src"].endswith("과목A/보고서"), e)
ok("폴더째 = 안쪽 파일 링크 고침", "[[0_작업/배움/과목B/보고서/초안]]" in read(K + "/컴/링크.md"), read(K + "/컴/링크.md"))
code, out = run("fileops.py", "undo", e[0]["batch"])
ok("폴더째 되돌리기", code == 0 and os.path.exists(a(W + "/배움/과목A/보고서/초안.md")), out)
rep()
# ⑬ 시트 짝 — 한쪽만 옮겨도 함께
mv(W + "/배움/과목A/기록.sheet", W + "/배움/과목B/기록.sheet")
rep()
ok("시트만 옮김 = md 따라감", os.path.exists(a(W + "/배움/과목B/기록.md")) and not os.path.exists(a(W + "/배움/과목A/기록.md")))
# ⑭ 장부 안 일은 바깥이 아니다
n0 = len(ops())
put(K + "/컴/장부안.md", "장부 안\n" + TXT)
put(K + "/컴/장부안2.md", "장부 안 2\n" + TXT)
put(K + "/컴/기록.md", "옵시디언\n" + TXT)
rep()
code, _ = run("fileops.py", "mv", K + "/컴/장부안.md", K + "/컴2/장부안.md", "--why", "시험")
code2, _ = run("fileops.py", "rm", K + "/컴/장부안2.md", "--why", "시험")
mv(K + "/컴/기록.md", K + "/컴2/기록.md")
code3, o3 = run("fileops.py", "record", "mv", K + "/컴/기록.md", K + "/컴2/기록.md")
n1 = len(ops())
r = rep()
ok("fileops·옵시디언 기록 = 안 겹침", code == 0 and code2 == 0 and code3 == 0 and r["moved"] == 0 and r["gone"] == 0 and len(ops()) == n1, (r, o3))
# ⑮ 뒤늦은 옵시디언 기록(follow 가 먼저 적음) = 두 번 안 적음
mv(K + "/컴/링크.md", K + "/컴2/링크.md")
rep()
n1 = len(ops())
code, o4 = run("fileops.py", "record", "mv", K + "/컴/링크.md", K + "/컴2/링크.md")
ok("follow 다음 record = 건너뜀", code == 0 and len(ops()) == n1, o4)
# ⑯ 바깥에서 지움 — 장부 · 되살리기 단추 없음
n0 = len(ops())
os.remove(a(K + "/rel/옆.md"))
r = rep()
e = mine(n0)
ok("지움 = 장부 rm(바깥) · 휴지통 자리 없음", r["gone"] == 1 and e[0]["op"] == "rm" and e[0]["trash"] == "gone" and not e[0].get("dst"), e)
code, out = run("fileops.py", "restore", e[0]["id"])
ok("지움 = fileops 되살리기는 거절", code == 1 and "사라짐" in out, out)
# ⑰ 폴더째 지움 = 한 줄
n0 = len(ops())
shutil.rmtree(a(SCH + "/과목A/쌍둥이"))
r = rep()
e = mine(n0)
ok("폴더째 지움 = 한 줄", r["gone"] == 2 and len(e) == 1 and e[0]["kind"] == "dir" and e[0]["n"] == 2 and e[0].get("user_asked"), e)
# ⑱ LMS 원본 — 묻기 · 그대로 · 되받기
os.remove(a(SCH + "/과목A/강의자료/lost.pdf"))
os.remove(a(SCH + "/과목A/강의자료/lost2.pdf"))
os.remove(a(SCH + "/과목A/공지/2026-10-01 공지.md"))
r = rep()
ok("LMS 원본 지움 = 답 기다림 3", r["pending"] == 3, r)
h = fol("--hook")[1]
ok("세션 시작 줄 = 답 기다림", "답 기다림 3" in h, h)
code, out = fol("keep", SCH + "/과목A/강의자료/lost.pdf")
man = json.load(open(MAN, encoding="utf-8"))
ok("그대로 = 목록에서만 뺌 · LMS 목록 유지", code == 0 and "canvas:2" in man["files"] and "답 기다림 2" in fol("--hook")[1], out)
code, out = fol("refetch", "--all")
man = json.load(open(MAN, encoding="utf-8"))
ok("되받기 = LMS 목록에서 뺌(게시판 첨부면 글 키도 · 알림 글 항목도)", code == 0 and "board:7:/posts/9:lost2.pdf" not in man["files"] and not man["board"]["7"] and "ann:1" not in man["items"], (out, man))
ok("되받기 뒤 = 답 기다림 0", fol("--hook")[1] == "", fol("--hook")[1])
# ⑲ 같은 내용이 볼트에 남으면 묻지 않음
os.remove(a(SCH + "/과목A/강의자료/사본.pdf"))
r = rep()
ok("같은 내용 남음 = 안 묻고 장부에 적음", r["gone"] == 1 and r["pending"] == 0 and "같은 내용" in ops()[-1]["why"], r)
# ⑳ 못 고름 — 같은 내용 둘이 함께 사라지고 둘이 새로
put(SCH + "/과목A/모호/원1.pdf", b"AMBI " * 40)
put(SCH + "/과목A/모호/원2.pdf", b"AMBI " * 40)
rep()
os.makedirs(a(SCH + "/과목A/모호2"))
shutil.copy2(a(SCH + "/과목A/모호/원1.pdf"), a(SCH + "/과목A/모호2/새1.pdf"))
shutil.copy2(a(SCH + "/과목A/모호/원2.pdf"), a(SCH + "/과목A/모호2/새2.pdf"))
os.remove(a(SCH + "/과목A/모호/원1.pdf"))
os.remove(a(SCH + "/과목A/모호/원2.pdf"))
r = rep()
ok("같은 내용 둘 = 고르지 않고 알림", r["moved"] == 0 and r["unknown"] == 2 and r["pending"] == 2, r)
fol("keep", "--all")
# ㉑ 웹 수집 보관 칸으로 간 것 = 지움 아님
arch = os.path.join(S, "_index", "collect", "archive", *(R["school_notice"] + "/장학/공지.md").split("/"))
os.makedirs(os.path.dirname(arch))
n0 = len(ops())
os.rename(a(R["school_notice"] + "/장학/공지.md"), arch)
r = rep()
ok("보관 칸 거울 있음 = 안 적음", r["gone"] == 0 and len(ops()) == n0, r)
# ㉒ 임시 파일
os.remove(a(W + "/배움/과목A/~$초안.docx"))
put(K + "/컴2/저장중.tmp", b"T")
n0 = len(ops())
r = rep()
os.remove(a(K + "/컴2/저장중.tmp"))
r2 = rep()
ok("임시 파일 = 안 적음", r["gone"] == 0 and r2["gone"] == 0 and len(ops()) == n0, (r, r2))
# ㉓ 떼로 사라짐 = 묻기 · 받아들이면 한 줄
n0 = len(ops())
shutil.rmtree(a(SCH + "/과목C/떼"))
r = rep()
h = fol("--hook")[1]
ok("떼로 사라짐 = 지움으로 안 침 · 장부 0 · 알림", r["held"] == 130 and r["gone"] == 0 and len(ops()) == n0 and "한꺼번에" in h, (r, h))
os.makedirs(a(SCH + "/과목C/떼"))
put(SCH + "/과목C/떼/f000.pdf", b"BULK000 " * 20)
code, out = fol("--accept")
e = mine(n0)
ok("받아들임 = 장부에 적음(남은 파일은 낱개)", code == 0 and sum(x.get("n", 1) for x in e) == 129, (out, e[:2]))
# ㉔ 못 읽은 폴더·옮기는 중 = 지움 아님(판정만)
sys.path.insert(0, S)
os.chdir(V)
import follow  # noqa: E402
m, g, u = follow.judge({"a/b/c.md": [1, 1, 5, "s"], "a/d.md": [1, 1, 6, "t"], "e/f.md": [1, 1, 7, "u"]}, {"z/f.md": [1, 1, 7, "u"]}, blind=["a/b"], expected=[("e", "z")])
ok("못 읽은 폴더·옮기는 중 = 건드리지 않음", not m and list(g) == ["a/d.md"] and not u, (m, g, u))
os.chdir(REAL)
shutil.rmtree(root, ignore_errors=True)
print("%d/%d" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
