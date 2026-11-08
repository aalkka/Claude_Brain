# 작업 폴더 보편화 회귀 시험(설계안 §19.8 · 2026-11-02) · 실행: py -3 3_시스템/_eval/work_check.py
# 격리 볼트에 학교 밖 작업(외부뇌·여행·부업·생활·분야)과 학교 과제를 심고 work.py 판정·정리 계획이 근거 표(work.json)대로인지 ·
# 계획 하나를 fileops 로 적용해 결과물이 원본 층 «보냄/»(학교 = «제출/»)으로 가는지 본다.
import datetime as dt
import io, json, os, shutil, subprocess, sys, tempfile, time, zipfile

REAL = r"C:\Claude_Brain\3_시스템"
root = tempfile.mkdtemp(prefix="work-")
V = os.path.join(root, "vault")
S = os.path.join(V, "3_시스템")
os.makedirs(S)
for f in ("fileops.py", "roles.py", "roles.json", "work.py", "work.json", "topic.py", "docpdf.py"):
    shutil.copy2(os.path.join(REAL, f), os.path.join(S, f))
R = json.load(open(os.path.join(S, "roles.json"), encoding="utf-8"))["roles"]


def put(r, data="x", age=0):
    a = os.path.join(V, *r.split("/"))
    os.makedirs(os.path.dirname(a), exist_ok=True)
    open(a, "wb").write(data.encode("utf-8") if isinstance(data, str) else data)
    if age:
        t = time.time() - age * 86400
        os.utime(a, (t, t))


put(R["topics"], "# 주제\n```json\n" + json.dumps({"topics": [
    {"이름": "외부뇌", "영역": "일", "상태": "진행"}, {"이름": "부업", "영역": "일", "상태": "진행"},
    {"이름": "여행", "영역": "생활", "상태": "진행"}, {"이름": "건강", "영역": "생활", "상태": "진행"},
    {"이름": "컴퓨터·AI", "영역": "분야", "상태": "진행"},
    {"이름": "시험과목", "영역": "배움", "종류": "학교", "별칭": ["시과"], "학기": "2026-2", "상태": "진행"}]}, ensure_ascii=False) + "\n```\n")
past = (dt.date.today() - dt.timedelta(days=3)).isoformat()
put(R["schedule"] + "/내-일정.md", "# 내 일정\n\n- [ ] %s 부업 · 포트폴리오 마감\n" % past)
W = R["work"]
# W1 외부뇌 · 끝냄(표시) — md·그림·측정은 지식으로 · 대본·만든 그림·md 에서 내보낸 docx 는 휴지통
put(W + "/일/외부뇌/설계문서/작업.md", "---\n단계: 끝\n---\n")
put(W + "/일/외부뇌/설계문서/설계.md", "# 설계")
put(W + "/일/외부뇌/설계문서/화면.png", b"PNG")
put(W + "/일/외부뇌/설계문서/fig/plot.png", b"PNG2")
put(W + "/일/외부뇌/설계문서/분석.py", "print(1)")
put(W + "/일/외부뇌/설계문서/측정.csv", "a,b")
put(W + "/일/외부뇌/설계문서/보고.md", "# 보고")
put(W + "/일/외부뇌/설계문서/보고.docx", b"PK")
put(W + "/일/외부뇌/설계문서/받은 양식.hwp", b"HWP")
# W1b 제작 원본 — 결과 PDF 가 뒤에 있으면 휴지통(사용자 11-05) · 고치고 아직 안 만든 원본은 지식으로
put(W + "/일/외부뇌/풀이지/작업.md", "---" + chr(10) + "단계: 끝" + chr(10) + "---" + chr(10))
put(W + "/일/외부뇌/풀이지/풀이.typ", "#x", age=1)
put(W + "/일/외부뇌/풀이지/풀이.pdf", b"PDF")
put(W + "/일/외부뇌/고침중/작업.md", "---" + chr(10) + "단계: 끝" + chr(10) + "---" + chr(10))
put(W + "/일/외부뇌/고침중/초안.typ", "#x")
put(W + "/일/외부뇌/고침중/초안.pdf", b"PDF", age=1)
# W2 여행 · 보냄(메일) — 결과물 = 맨 위 문서 · 사진은 재료 · 원본 층 주제 자리가 없어도 등록부 영역으로 «보냄/»
put(W + "/생활/여행/항공권/작업.md", "---\n보냄: 메일 · 여행사\n---\n")
put(W + "/생활/여행/항공권/신청서.pdf", b"%PDF")
put(W + "/생활/여행/항공권/여권사진.jpg", b"JPG")
put(W + "/생활/여행/항공권/메모.md", "# 메모")
# W3 부업 · 단계: 제출 + 결과물 이름 — 초안은 휴지통
put(W + "/일/부업/지원서/작업.md", "---\n단계: 제출\n결과물: [지원서_최종.docx]\n---\n")
put(W + "/일/부업/지원서/지원서_최종.docx", b"PK1")
put(W + "/일/부업/지원서/지원서_초안.docx", b"PK0")
# W4 일정 근거(학교 밖) — «부업 · 포트폴리오 마감» 이 지남
put(W + "/일/부업/포트폴리오/작품.md", "# 작품")
# W5 git — 가지가 원격 기본 가지에 병합 → 보냄 · 병합 안 된 가지 → 진행
repo, bare = os.path.join(root, "repo"), os.path.join(root, "remote.git")
g = lambda *a, cwd=repo: subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)  # noqa: E731
subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
os.makedirs(repo)
g("init", "-q", "-b", "main"); g("config", "user.email", "t@t"); g("config", "user.name", "t")
open(os.path.join(repo, "a.txt"), "w").write("a"); g("add", "."); g("commit", "-qm", "a")
g("checkout", "-qb", "feat"); open(os.path.join(repo, "b.txt"), "w").write("b"); g("add", "."); g("commit", "-qm", "b")
g("checkout", "-qb", "wip"); open(os.path.join(repo, "c.txt"), "w").write("c"); g("add", "."); g("commit", "-qm", "c")
g("checkout", "-q", "main"); g("merge", "-q", "feat"); g("remote", "add", "origin", bare); g("push", "-q", "origin", "main")
g("remote", "set-head", "origin", "main")
put(W + "/일/외부뇌/기능/작업.md", "---\n저장소: %s\n가지: feat\n---\n" % repo.replace("\\", "/"))
put(W + "/일/외부뇌/기능/메모.md", "# 메모")
put(W + "/일/외부뇌/실험중/작업.md", "---\n저장소: %s\n가지: wip\n---\n" % repo.replace("\\", "/"))
# W6 멈춤 · W7 진행
put(W + "/생활/건강/식단/식단.md", "# 식단", age=10)
put(W + "/생활/건강/운동/계획.md", "# 계획")
# W8 보냄인데 결과물이 어디에도 없음 → 지우는 계획 없음
put(W + "/생활/여행/비자/작업.md", "---\n보냄: 대사관\n결과물: [없는결과물_zzq9.pdf]\n---\n")
put(W + "/생활/여행/비자/메모.md", "# 비자")
# W9 md 낱파일 작업 — 그 노트 속성 «단계: 끝»
put(W + "/분야/컴퓨터·AI/읽을거리.md", "---\n단계: 끝\n---\n# 읽을거리")
# W10 학교 과제 — LMS 내 제출 · 결과물이 작업 안에 → «제출/»(종류 학교)
put("3_시스템/lms/courses.json", json.dumps({"111": "시험과목"}))
put(R["sources"] + "/_lms/lms-canvas-1.json", json.dumps({"courses": [{"id": 111, "assignments": [{"id": 1, "name": "보고서 1", "submission": {
    "workflow_state": "submitted", "submitted_at": "2026-10-20T00:00:00Z", "attachments": [{"display_name": "보고서1_결과_학번.pdf"}]}}]}]}))
put(R["school"] + "/시험과목/강의자료/1주.pdf", b"%PDF")
put(W + "/배움/시험과목/보고서1/보고서1_결과_학번.pdf", b"%PDF-R")
put(W + "/배움/시험과목/보고서1/측정값.xlsx", b"PKX")
# W11~W14 보고서(사용자 11-03 «재료도 휴지통 · docx 는 PDF 변환해 PDF 만») — 진짜 docx(Word 로 변환)


def docx_bytes(text):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr("word/document.xml", '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>%s</w:t></w:r></w:p></w:body></w:document>' % text)
    return b.getvalue()


# W11 docx 만 있음(PDF 없음) → 변환 · 재료·대본 휴지통
put(W + "/배움/시험과목/보고서2/작업.md", "---\n단계: 제출\n---\n")
put(W + "/배움/시험과목/보고서2/보고서2.docx", docx_bytes("보고서 둘 본문"))
put(W + "/배움/시험과목/보고서2/사진.jpg", b"JPG2")
put(W + "/배움/시험과목/보고서2/측정.csv", "t,x")
put(W + "/배움/시험과목/보고서2/ana.py", "print(1)")
# W12 «보냄: …pdf» · PDF 는 이미 제출 자리 → docx 는 변환 없이 지우기만
put(W + "/배움/시험과목/보고서3/작업.md", "---\n보냄: 보고서3_최종.pdf\n---\n")
put(W + "/배움/시험과목/보고서3/보고서3_최종.docx", docx_bytes("보고서 셋"))
put(W + "/배움/시험과목/보고서3/fig/setup.jpg", b"JPG3")
put(R["school"] + "/시험과목/제출/보고서3_최종.pdf", b"%PDF-3")
# W13 제출 자리에 docx 로 보관됨(LMS 내 제출) → 변환 · 제출 자리 docx 도 지움
put(W + "/배움/시험과목/보고서4/작업.md", "---\n단계: 제출\n결과물: 보고서4.docx\n---\n")
put(W + "/배움/시험과목/보고서4/메모.md", "# 메모")
put(R["school"] + "/시험과목/제출/보고서4.docx", docx_bytes("보고서 넷"))
# W14 망가진 docx → 변환 실패 → 계획이 멈춰 docx 를 안 지움
put(W + "/배움/시험과목/보고서5/작업.md", "---\n단계: 제출\n---\n")
put(W + "/배움/시험과목/보고서5/보고서5.docx", b"PK-broken")

py = sys.executable
run = lambda *a: subprocess.run([py, "-X", "utf8", os.path.join(S, a[0]), *a[1:]], capture_output=True, text=True, encoding="utf-8")  # noqa: E731
res = []


def ok(name, cond, detail=""):
    res.append(bool(cond))
    print(("통과 " if cond else "실패 ") + name + ("" if cond else "  ← " + str(detail)[:400]))


st = {t["path"].split("/", 1)[1]: t for t in json.loads(run("work.py", "--json").stdout)["items"]}
s = lambda k: (st.get(k) or {}).get("state")  # noqa: E731
ok("W1 표시 «단계: 끝» = 끝냄", s("일/외부뇌/설계문서") == "끝냄", st.get("일/외부뇌/설계문서"))
ok("W2 표시 «보냄:» = 보냄 · 결과물(맨 위 문서) 작업 안", s("생활/여행/항공권") == "보냄" and st["생활/여행/항공권"]["here"] == [W + "/생활/여행/항공권/신청서.pdf"], st.get("생활/여행/항공권"))
ok("W3 «단계: 제출» + «결과물:» = 보냄", s("일/부업/지원서") == "보냄" and len(st["일/부업/지원서"]["here"]) == 1, st.get("일/부업/지원서"))
ok("W4 일정 줄(학교 밖) 지남 = 마감 지남", s("일/부업/포트폴리오") == "마감 지남", st.get("일/부업/포트폴리오"))
ok("W5 git 가지 병합 = 보냄(저장소) · 안 된 가지 = 진행", s("일/외부뇌/기능") == "보냄" and (st["일/외부뇌/기능"]["kept"] or "").startswith("저장소") and s("일/외부뇌/실험중") == "진행",
   (st.get("일/외부뇌/기능"), st.get("일/외부뇌/실험중")))
ok("W6 멈춤 · W7 진행", s("생활/건강/식단") == "멈춤" and s("생활/건강/운동") == "진행", (st.get("생활/건강/식단"), st.get("생활/건강/운동")))
ok("W8 결과물 없음 표시(missing)", s("생활/여행/비자") == "보냄" and st["생활/여행/비자"]["missing"] is True, st.get("생활/여행/비자"))
ok("W9 md 낱파일 «단계: 끝» = 끝냄", s("분야/컴퓨터·AI/읽을거리.md") == "끝냄", st.get("분야/컴퓨터·AI/읽을거리.md"))
ok("W10 학교 과제 LMS 제출 = 보냄 · 결과물 작업 안", s("배움/시험과목/보고서1") == "보냄" and st["배움/시험과목/보고서1"]["here"], st.get("배움/시험과목/보고서1"))

out = json.loads(run("work.py", "plan", "--json").stdout)
plans = {r["path"].split("/", 1)[1]: r for r in out}


def ops(k):
    p = plans.get(k, {}).get("plan")
    return json.load(open(os.path.join(V, *p.split("/")), encoding="utf-8"))["ops"] if p else []


def where(k):
    return {o["src"].rsplit("/", 1)[-1]: (o["op"], o.get("dst", "")) for o in ops(k) if o["op"] != "rmdir"}


w1 = where("일/외부뇌/설계문서")
ok("P1 끝냄 = md·그림·측정·받은 양식 → 2_지식/일/외부뇌/설계문서 · 대본·fig·내보낸 docx·작업.md → 휴지통",
   all(w1[n] == ("mv", "2_지식/일/외부뇌/설계문서/" + n) for n in ("설계.md", "화면.png", "측정.csv", "보고.md", "받은 양식.hwp"))
   and all(w1[n][0] == "rm" for n in ("plot.png", "분석.py", "보고.docx", "작업.md")), w1)
wt, wk = where("일/외부뇌/풀이지"), where("일/외부뇌/고침중")
ok("P1b 제작 원본 = 결과 PDF 가 뒤에 있으면 휴지통 · PDF 는 지식으로 · 고치고 안 만든 원본은 지식으로",
   wt.get("풀이.typ", ("",))[0] == "rm" and wt.get("풀이.pdf") == ("mv", "2_지식/일/외부뇌/풀이지/풀이.pdf")
   and wk.get("초안.typ") == ("mv", "2_지식/일/외부뇌/고침중/초안.typ"), (wt, wk))
w2 = where("생활/여행/항공권")
ok("P2 보냄 = 결과물 → 1_수집/생활/여행/보냄/ · 사진 → 보냄/항공권/ · 메모 → 2_지식 · 작업.md → 휴지통",
   w2.get("신청서.pdf") == ("mv", "1_수집/생활/여행/보냄/신청서.pdf") and w2.get("여권사진.jpg") == ("mv", "1_수집/생활/여행/보냄/항공권/여권사진.jpg")
   and w2.get("메모.md") == ("mv", "2_지식/생활/여행/항공권/메모.md") and w2.get("작업.md", ("",))[0] == "rm", w2)
w3 = where("일/부업/지원서")
ok("P3 결과물만 보냄/ · 초안 docx → 휴지통", w3.get("지원서_최종.docx") == ("mv", "1_수집/일/부업/보냄/지원서_최종.docx") and w3.get("지원서_초안.docx", ("",))[0] == "rm", w3)
w5 = where("일/외부뇌/기능")
ok("P5 저장소로 보냄 = 앎 꼴(메모 → 지식)", w5.get("메모.md") == ("mv", "2_지식/일/외부뇌/기능/메모.md"), w5)
ok("P8 결과물 없음 = 계획 없음(지우지 않음)", not plans.get("생활/여행/비자", {}).get("plan") and "결과물 없음" in plans.get("생활/여행/비자", {}).get("note", ""), plans.get("생활/여행/비자"))
w10 = where("배움/시험과목/보고서1")
ok("P10 학교 = «제출/»(종류 학교) · 측정값 = 휴지통(재료 1회용)", w10.get("보고서1_결과_학번.pdf") == ("mv", "1_수집/배움/시험과목/제출/보고서1_결과_학번.pdf")
   and w10.get("측정값.xlsx", ("",))[0] == "rm", w10)
o11 = [(o["op"], o.get("src", o.get("path", "")).rsplit("/", 1)[-1], o.get("dst", "")) for o in ops("배움/시험과목/보고서2")]
ok("P11 docx 만 있음 = PDF 먼저 · docx 지움 · 재료·대본·표시 휴지통 · 제출에 재료 없음",
   o11.index(("pdf", "보고서2.docx", "1_수집/배움/시험과목/제출/보고서2.pdf")) < o11.index(("rm", "보고서2.docx", ""))
   and all(("rm", n, "") in o11 for n in ("사진.jpg", "측정.csv", "ana.py", "작업.md")) and not any(d.startswith("1_수집/") and not d.endswith(".pdf") for _, _, d in o11), o11)
ok("W12 «보냄: …pdf» = 보낸 파일 이름 · 제출에 보관됨", (st["배움/시험과목/보고서3"].get("kept") or "").endswith("보고서3_최종.pdf"), st.get("배움/시험과목/보고서3"))
w12 = where("배움/시험과목/보고서3")
ok("P12 PDF 보관됨 = docx 변환 없이 지움 · 사진 휴지통", w12.get("보고서3_최종.docx", ("",))[0] == "rm" and w12.get("setup.jpg", ("",))[0] == "rm"
   and not any(o["op"] == "pdf" for o in ops("배움/시험과목/보고서3")), w12)
o13 = ops("배움/시험과목/보고서4")
ok("P13 제출에 docx 보관 = 그 자리에 PDF · 제출 docx 지움(user_asked) · md 는 지식으로", o13[0]["op"] == "pdf" and o13[0]["dst"] == "1_수집/배움/시험과목/제출/보고서4.pdf"
   and o13[1]["op"] == "rm" and o13[1]["src"] == "1_수집/배움/시험과목/제출/보고서4.docx" and o13[1]["user_asked"] is True
   and where("배움/시험과목/보고서4").get("메모.md", ("",))[0] == "mv", o13)
ok("P3 학교 밖 docx·재료는 그대로(보고서 규칙 안 탐)", w2.get("여권사진.jpg", ("",))[0] == "mv" and w3.get("지원서_최종.docx", ("",))[0] == "mv", (w2, w3))
ok("P0 진행·멈춤 아닌 것만 계획 · 진행 = 없음", "생활/건강/운동" not in plans and "일/외부뇌/실험중" not in plans, list(plans))

# 적용 — 여행 항공권 계획을 fileops 로
r = run("fileops.py", "--by", "script:work_check", "plan", os.path.join(V, *plans["생활/여행/항공권"]["plan"].split("/")), "--apply")
moved = os.path.isfile(os.path.join(V, "1_수집", "생활", "여행", "보냄", "신청서.pdf")) and os.path.isfile(os.path.join(V, "1_수집", "생활", "여행", "보냄", "항공권", "여권사진.jpg"))
gone = not os.path.exists(os.path.join(V, *W.split("/"), "생활", "여행", "항공권"))
ok("A1 적용 = 결과물·사진 보냄/ 으로 · 작업 폴더 비워 지움", r.returncode == 0 and moved and gone, r.stdout[-400:] + r.stderr[-400:])
# 폴더째 비우기(11-02) — 하위 폴더(fig/) 있는 작업 · 하나뿐이던 주제·영역 폴더까지 · 다른 작업이 남은 주제 폴더는 그대로
for k in ("일/외부뇌/설계문서", "분야/컴퓨터·AI/읽을거리.md"):
    run("fileops.py", "--by", "script:work_check", "plan", os.path.join(V, *plans[k]["plan"].split("/")), "--apply")
wv = os.path.join(V, *W.split("/"))
ok("A3 폴더째 비움 = 하위 폴더째 · 하나뿐이던 주제·영역 폴더까지 · 다른 작업 있는 주제는 남김",
   not os.path.exists(os.path.join(wv, "일", "외부뇌", "설계문서")) and os.path.isdir(os.path.join(wv, "일", "외부뇌"))
   and not os.path.exists(os.path.join(wv, "분야")) and os.path.isfile(os.path.join(V, "2_지식", "일", "외부뇌", "설계문서", "설계.md")), os.listdir(wv))
st2 = {t["path"].split("/", 1)[1]: t for t in json.loads(run("work.py", "--json").stdout)["items"]}
ok("A2 적용 뒤 그 작업은 목록에서 빠짐", "생활/여행/항공권" not in st2, list(st2))
# 보고서 — 진짜 Word 변환


def hidden_word():
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Process -Filter \"Name='WINWORD.EXE'\" | Where-Object { $_.CommandLine -match 'Embedding' } | ForEach-Object { $_.ProcessId }"], capture_output=True, text=True)
    return {int(x) for x in r.stdout.split()}


word0 = hidden_word()
sub1 = os.path.join(V, "1_수집", "배움", "시험과목", "제출")
r = run("fileops.py", "--by", "script:work_check", "plan", os.path.join(V, *plans["배움/시험과목/보고서2"]["plan"].split("/")), "--apply")
pdf2 = os.path.join(sub1, "보고서2.pdf")
head = open(pdf2, "rb").read(5) if os.path.isfile(pdf2) else b""
ok("A4 보고서 적용 = 제출에 PDF(Word 변환) · docx·재료는 휴지통 · 제출에 재료 폴더 없음 · 작업 폴더 비움", r.returncode == 0 and head == b"%PDF-" and not os.path.exists(os.path.join(sub1, "보고서2"))
   and not os.path.exists(os.path.join(sub1, "보고서2.docx")) and not os.path.exists(os.path.join(wv, "배움", "시험과목", "보고서2")), r.stdout[-400:] + r.stderr[-300:])
led = [json.loads(l) for l in open(os.path.join(S, "ledger", "ops.jsonl"), encoding="utf-8")]
b2 = next(e["batch"] for e in reversed(led) if e.get("dst", "").endswith("제출/보고서2.pdf"))
u = run("fileops.py", "--by", "script:work_check", "undo", b2)
ok("A5 한 묶음 되돌리기 = docx·재료 제자리 · PDF 빠짐", u.returncode == 0 and os.path.isfile(os.path.join(wv, "배움", "시험과목", "보고서2", "보고서2.docx")) and os.path.isfile(os.path.join(wv, "배움", "시험과목", "보고서2", "사진.jpg")) and not os.path.exists(pdf2), u.stdout[-300:] + u.stderr[-200:])
r = run("fileops.py", "--by", "script:work_check", "plan", os.path.join(V, *plans["배움/시험과목/보고서4"]["plan"].split("/")), "--apply")
ok("A6 제출 docx = PDF 만 남음", r.returncode == 0 and open(os.path.join(sub1, "보고서4.pdf"), "rb").read(5) == b"%PDF-" and not os.path.exists(os.path.join(sub1, "보고서4.docx")), r.stdout[-300:] + r.stderr[-200:])
r = run("fileops.py", "--by", "script:work_check", "plan", os.path.join(V, *plans["배움/시험과목/보고서5"]["plan"].split("/")), "--apply")
ok("A7 변환 실패 = 멈춤 · docx 그대로 · PDF 없음", r.returncode == 1 and "PDF 변환 실패" in r.stdout and os.path.isfile(os.path.join(wv, "배움", "시험과목", "보고서5", "보고서5.docx")) and not os.path.exists(os.path.join(sub1, "보고서5.pdf")), r.stdout[-300:])
time.sleep(6)
word1 = hidden_word() - word0
ok("A8 변환 뒤 숨은 Word 가 안 남음(성공·실패 모두)", not word1, sorted(word1))
for p in word1:
    subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True)

# S1 sweep(사용자 11-03 «끝나면 무조건 비운다») — 보냄·끝냄은 승인 없이 · 마감 지남·멈춤·진행·결과물 없음은 그대로 · 되돌린 것은 다시 안 비움
sw_env = dict(os.environ, PYTHONIOENCODING="utf-8", FILEOPS_NO_OBSIDIAN="1")
wr = subprocess.run([sys.executable, os.path.join(S, "work.py"), "sweep"], cwd=V, env=sw_env, capture_output=True, text=True, encoding="utf-8")
ex = lambda r: os.path.exists(os.path.join(V, *r.split("/")))  # noqa: E731
gone = [l.split()[1] for l in wr.stdout.splitlines() if l.startswith("비움 ")]
ok("S1 보냄·끝냄 = 승인 없이 비움", gone and all(not ex(g) for g in gone), wr.stdout[-600:] + wr.stderr)
ok("S1 마감 지남·멈춤·진행 = 그대로", ex("0_작업/일/부업/포트폴리오") and ex("0_작업/생활/건강/식단") and ex("0_작업/생활/건강/운동"), wr.stdout[-300:])
ok("S1 결과물 없음 = 그대로", ex("0_작업/생활/여행/비자"), wr.stdout[-300:])
back = next((l for l in wr.stdout.splitlines() if l.startswith("비움 ")), "")
subprocess.run([sys.executable, os.path.join(S, "fileops.py"), "undo", back.rsplit(" ", 1)[-1]], cwd=V, env=sw_env, capture_output=True)
was = ex(back.split()[1]) if back else False
subprocess.run([sys.executable, os.path.join(S, "work.py"), "sweep"], cwd=V, env=sw_env, capture_output=True)
ok("S1 되돌린 작업은 다시 안 비움", was and ex(back.split()[1]), back)

# F1 finish(사용자 11-03 «끝났는지 체크») — 진행 중인 작업도 사람이 체크하면 바로 비움 · 되돌리면 돌아오고 저절로 다시 안 비움
fr = subprocess.run([sys.executable, os.path.join(S, "work.py"), "finish", "0_작업/생활/건강/운동", "--by", "obsidian"], cwd=V, env=sw_env, capture_output=True, text=True, encoding="utf-8")
fj = json.loads(fr.stdout.strip().splitlines()[-1]) if fr.stdout.strip() else {}
ok("F1 진행 중인 작업 체크 = 바로 비움", fj.get("batch") and not ex("0_작업/생활/건강/운동"), fr.stdout[-400:] + fr.stderr[-300:])
subprocess.run([sys.executable, os.path.join(S, "fileops.py"), "undo", fj.get("batch") or "x"], cwd=V, env=sw_env, capture_output=True)
ok("F1 되돌리면 돌아옴", ex("0_작업/생활/건강/운동"), str(fj))
subprocess.run([sys.executable, os.path.join(S, "work.py"), "sweep"], cwd=V, env=sw_env, capture_output=True)
ok("F1 되돌린 뒤 저절로 안 비움", ex("0_작업/생활/건강/운동"))
fr = subprocess.run([sys.executable, os.path.join(S, "work.py"), "finish", "0_작업/생활/여행/비자"], cwd=V, env=sw_env, capture_output=True, text=True, encoding="utf-8")
ok("F2 결과물 없음도 체크하면 비움(사람이 끝났다고 함)", not ex("0_작업/생활/여행/비자"), fr.stdout[-300:])
fr = subprocess.run([sys.executable, os.path.join(S, "work.py"), "finish", "2_지식/없는것"], cwd=V, env=sw_env, capture_output=True, text=True, encoding="utf-8")
ok("F3 작업이 아니면 error", "error" in json.loads(fr.stdout.strip().splitlines()[-1]), fr.stdout[-200:])

shutil.rmtree(root, ignore_errors=True)
print("%d/%d" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
