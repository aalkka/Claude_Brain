# 볼트 개혁 R9 받은함 정리 회귀 시험(10-30 · 11-02 재료·폴더·잠금 개정) · 실행: py -3 3_시스템/_eval/r9_inbox_check.py — 격리 볼트에 받은 것을 심고 inbox.py 가 가르는지 · --apply 가 확실한 것만 하는지 · 잠긴 폴더를 옮기면 아무것도 안 변하는지
import json, os, shutil, subprocess, sys, tempfile, time

REAL = r"C:\Claude_Brain\3_시스템"
root = tempfile.mkdtemp(prefix="r9in-")
V = os.path.join(root, "vault")
S = os.path.join(V, "3_시스템")
os.makedirs(S)
for f in ("fileops.py", "roles.py", "roles.json", "inbox.py", "work.py", "work.json"):
    shutil.copy2(os.path.join(REAL, f), os.path.join(S, f))
R = json.load(open(os.path.join(S, "roles.json"), encoding="utf-8"))["roles"]
def put(r, data=b"x"):
    a = os.path.join(V, *r.split("/"))
    os.makedirs(os.path.dirname(a), exist_ok=True)
    open(a, "wb").write(data if isinstance(data, bytes) else data.encode("utf-8"))
put(R["topics"], ("# 주제\n```json\n" + json.dumps({"topics": [
    {"이름": "과목A", "영역": "배움", "별칭": ["과A"], "학기": "2026-2", "상태": "진행"},
    {"이름": "프로젝트P", "영역": "프로젝트", "별칭": ["proj"], "상태": "진행"}]}, ensure_ascii=False) + "\n```\n").encode("utf-8"))
sch = R["school"] + "/과목A"
wk = R["work"] + "/배움/과목A"
put(sch + "/강의자료/old.pdf", b"PDF-OLD")
I = R["inbox"]
# 낱파일 — 문서
put(I + "/과목A 3주차 강의.pdf", b"PDF-1")       # 높음 → 강의자료
put(I + "/과A_과제2.hwp", b"HWP-2")             # 별칭 · 과제 → 높음
put(I + "/과목A 메모.pdf", b"PDF-3")             # 주제만 → 보통
put(I + "/과목A hwp 변환.pdf", b"PDF-4")         # «hw» 가 «hwp» 에 걸리면 안 됨 → 보통
put(I + "/아무거나.pdf", b"PDF-5")               # 주제 없음 → 낮음
put(I + "/생각.md", "과목A 에 대한 생각")          # md → 승격(Claude) · 낮음
put(I + "/중복.pdf", b"PDF-OLD")                 # 같은 내용 있음 → 버림
put(I + "/proj 설계.docx", b"DOCX-7")            # 프로젝트 → 작업 자리 제안 · 낮음
# 낱파일 — 재료
put(I + "/과목A 실험 사진.jpg", b"JPG-8")         # 재료 → 작업 자리 · 원본 층 안 감
put(I + "/과목A 족보 사진.jpg", b"JPG-9")         # 사진이라도 족보 = 원본
put(I + "/과목A ana_final.py", b"PY-10")         # «final» 이어도 코드 = 재료(시험 칸으로 안 감)
put(I + "/쌍둥이1.pdf", b"PDF-TWIN")             # 받은함끼리 같음 → 같음으로 안 침(둘 다 버려지면 안 됨)
put(I + "/쌍둥이2.pdf", b"PDF-TWIN")
put(".trash/2026-01-01/x/옛것.pdf", b"PDF-TRASH")
put(I + "/휴지통본.pdf", b"PDF-TRASH")           # 휴지통에만 같은 것 → 같음으로 안 침
# 폴더
os.makedirs(os.path.join(V, *I.split("/"), "과목A 시험자료"))   # 빈 폴더 → 치움
for f, b in (("a.jpg", b"F1"), ("b.csv", b"F2"), ("code.txt", b"F3")):
    put(I + "/과A 새재료/" + f, b)               # 재료만 · 쓴 작업 없음 → 작업 자리(한 번에)
put(I + "/기록/과A 측정.csv", b"F4")              # 폴더 이름에 주제 없음 → 안 파일 이름
put(I + "/모두같음/사본.pdf", b"PDF-OLD")          # 안이 모두 같은 내용 → 버림
for f, b in (("1.jpg", b"G1"), ("2.csv", b"G2"), ("메모.md", b"G3")):
    put(I + "/과A md섞임/" + f, b)                # 끝난 작업 재료인데 md 가 섞임 → 자동 안 버림
for f, b in (("1-1.csv", b"H1"), ("1-1.jpg", b"H2")):
    put(I + "/과A 끝난재료/" + f, b)               # 끝난 작업이 경로를 적음 → 버림
for f, b in (("x.csv", b"K1"),):
    put(I + "/과A 쓰는재료/" + f, b)               # 진행 중 작업이 경로를 적음(역슬래시) → 그 작업 안으로 제안 · 자동 안 함
put(I + "/과A 끝난재료2/same.png", b"SAME-FIG")   # 끝난 작업 안에 같은 내용 파일 → 쓴 것
put(I + "/과A 끝난재료2/other.csv", b"H3")
put(I + "/과A 비슷한이름/y.csv", b"K2")            # «과A 끝난재료» 와 앞이 같은 경로 글에 안 걸림 — 이름 시험 아래
for f, b in (("3주차 강의.pdf", b"M1"), ("사진.png", b"M2"), ("sub/코드.v", b"M3"), ("사본.pdf", b"PDF-OLD")):
    put(I + "/과목A 섞임/" + f, b)                 # 문서 + 재료 + 같은 내용 → 풀기(휴지통 낌)
for f, b in (("과제 안내.pdf", b"N1"), ("그림.png", b"N2")):
    put(I + "/과목A 풀기/" + f, b)                 # 문서 + 재료 → 풀기(휴지통 없음 · 칸 정해짐 → 자동)
put(I + "/_기계칸/끝난 것.md", b"# x")          # _ 칸 = 안 봄
# 작업들
put(wk + "/실험1/작업.md", "---\ntype: work\n단계: 제출\n보냄: 실험1.pdf\n---\n")
put(wk + "/실험1/fig/same.png", b"SAME-FIG")
put(wk + "/실험1/ana.py", "D='C:/Claude_Brain/1_수집/받은함/과A 끝난재료/'\nM='1_수집/받은함/과A md섞임'\n")
put(wk + "/실험2/메모.md", "자료 = C:\\\\Claude_Brain\\\\1_수집\\\\받은함\\\\과A 쓰는재료\\\\x.csv\n")
put(wk + "/실험3/ana.py", "D='1_수집/받은함/과A 비슷한이름표/'\n")   # 다른 폴더 경로
put(I + "/과A 매주/새 측정.csv", b"W1")            # 지난주 끝난 작업이 같은 이름을 적었지만 이번 주에 새로 넣음 → 쓴 것 아님
put(wk + "/실험1/old.py", "D='1_수집/받은함/과A 매주/'\n")
os.utime(os.path.join(V, *(wk + "/실험1/old.py").split("/")), (time.time() - 7 * 86400, time.time() - 7 * 86400))
env = dict(os.environ, PYTHONIOENCODING="utf-8", FILEOPS_NO_OBSIDIAN="1")
env.pop("CLAUDECODE", None)
run = lambda *a: subprocess.run([sys.executable, os.path.join(S, "inbox.py"), *a], capture_output=True, text=True, encoding="utf-8", env=env, cwd=V)
fo = lambda *a: subprocess.run([sys.executable, os.path.join(S, "fileops.py"), *a], capture_output=True, text=True, encoding="utf-8", env=env, cwd=V)
ex = lambda r: os.path.exists(os.path.join(V, *r.split("/")))
def ledger():
    p = os.path.join(S, "ledger", "ops.jsonl")
    return [json.loads(l) for l in open(p, encoding="utf-8")] if os.path.exists(p) else []
res = []
def ok(name, cond, detail=""):
    res.append(bool(cond)); print(("통과" if cond else "실패"), name, detail)
p0 = run("--json")
j = json.loads(p0.stdout) if p0.stdout.strip() else sys.exit("inbox.py 실패: " + p0.stderr)
by = {x["name"]: x for x in j["items"]}
ok("_ 칸은 안 봄", "_기계칸" not in by, str(len(by)))
ok("문서: 이름 + «주차» → 강의자료 · 높음", by["과목A 3주차 강의.pdf"]["dst"] == sch + "/강의자료/과목A 3주차 강의.pdf" and by["과목A 3주차 강의.pdf"]["sure"] == "높음" and by["과목A 3주차 강의.pdf"]["act"] == "원본")
ok("문서: 별칭 «과A» + «과제» → 과제 · 높음", by["과A_과제2.hwp"]["dst"] == sch + "/과제/과A_과제2.hwp" and by["과A_과제2.hwp"]["sure"] == "높음", by["과A_과제2.hwp"]["why"])
ok("문서: 하위 못 정함 → 주제 폴더 · 보통", by["과목A 메모.pdf"]["sure"] == "보통" and by["과목A 메모.pdf"]["dst"] == sch + "/과목A 메모.pdf")
ok("«hw» 가 «hwp» 에 걸리지 않음", by["과목A hwp 변환.pdf"]["sure"] == "보통", by["과목A hwp 변환.pdf"]["why"])
ok("주제 없음 → 낮음 · 자리 없음", by["아무거나.pdf"]["sure"] == "낮음" and by["아무거나.pdf"]["dst"] is None and by["아무거나.pdf"]["act"] == "그대로")
ok("md → 승격은 Claude · 낮음", by["생각.md"]["sure"] == "낮음" and "승격" in by["생각.md"]["why"] and "과목A" in by["생각.md"]["why"] and not by["생각.md"]["ops"])
ok("같은 내용 → 버림", by["중복.pdf"]["dup"] == sch + "/강의자료/old.pdf" and by["중복.pdf"]["act"] == "버림", str(by["중복.pdf"]["dup"]))
ok("프로젝트 주제 → 작업 자리 제안 · 낮음", by["proj 설계.docx"]["sure"] == "낮음" and by["proj 설계.docx"]["dst"].startswith(R["work"] + "/") and "프로젝트P" in by["proj 설계.docx"]["dst"], by["proj 설계.docx"]["dst"])
ok("재료 낱파일 → 작업 자리(원본 층 안 감)", by["과목A 실험 사진.jpg"]["act"] == "재료" and by["과목A 실험 사진.jpg"]["dst"] == wk + "/과목A 실험 사진.jpg" and by["과목A 실험 사진.jpg"]["sure"] == "높음", str(by["과목A 실험 사진.jpg"]["dst"]))
ok("사진이라도 «족보» → 원본", by["과목A 족보 사진.jpg"]["dst"] == sch + "/족보/과목A 족보 사진.jpg", str(by["과목A 족보 사진.jpg"]["dst"]))
ok("코드 «ana_final» → 재료(시험 칸 아님)", by["과목A ana_final.py"]["act"] == "재료" and by["과목A ana_final.py"]["dst"].startswith(wk + "/"), str(by["과목A ana_final.py"]["dst"]))
ok("받은함끼리 같음 → 같음 아님", by["쌍둥이1.pdf"]["dup"] is None and by["쌍둥이2.pdf"]["dup"] is None)
ok("휴지통에만 같음 → 같음 아님", by["휴지통본.pdf"]["dup"] is None)
ok("빈 폴더 → 치움 · 높음", by["과목A 시험자료"]["act"] == "지움" and by["과목A 시험자료"]["sure"] == "높음" and by["과목A 시험자료"]["ops"][0]["op"] == "rmdir")
x = by["과A 새재료"]
ok("재료 폴더 → 통째로 작업 자리 · 높음 · 원본 층 안 감 · 한 번에", x["act"] == "재료" and x["dst"] == wk + "/과A 새재료" and x["sure"] == "높음" and len(x["ops"]) == 1 and x["n"] == 3, str(x["dst"]))
ok("폴더 이름에 주제 없음 → 안 파일 이름", by["기록"]["act"] == "재료" and by["기록"]["dst"] == wk + "/기록", str(by["기록"]["dst"]))
ok("안이 모두 같은 내용 → 버림", by["모두같음"]["act"] == "버림" and by["모두같음"]["ops"][0]["op"] == "rm" and by["모두같음"]["dup"], by["모두같음"]["why"])
x = by["과A 끝난재료"]
ok("끝난 작업이 경로를 적은 재료 → 버림 · 높음", x["act"] == "버림" and x["sure"] == "높음" and "실험1" in x["why"] and x["ops"][0]["user_asked"] is True, x["why"])
ok("끝난 작업 안에 같은 내용 파일 → 쓴 것 → 버림", by["과A 끝난재료2"]["act"] == "버림", by["과A 끝난재료2"]["why"])
ok("md 섞인 끝난 재료 → 자동 안 버림(보통)", by["과A md섞임"]["act"] == "버림" and by["과A md섞임"]["sure"] == "보통", by["과A md섞임"]["why"])
x = by["과A 쓰는재료"]
ok("쓰는 중(역슬래시 경로) → 그 작업 안 제안 · 보통", x["act"] == "재료" and x["sure"] == "보통" and x["dst"] == wk + "/실험2/과A 쓰는재료", str(x["dst"]))
x = by["과A 비슷한이름"]
ok("비슷한 이름의 다른 경로엔 안 걸림", x["act"] == "재료" and x["dst"] == wk + "/과A 비슷한이름", str(x["dst"]))
x = by["과A 매주"]
ok("같은 이름을 다시 넣음 — 들어오기 전에 쓴 끝난 작업 글은 근거 아님 → 안 버림", x["act"] == "재료" and x["dst"] == wk + "/과A 매주" and x["sure"] == "높음", x["why"])
x = by["과목A 섞임"]
ok("문서 섞인 폴더 → 풀기(문서 칸 · 재료 작업 자리 · 같은 내용 휴지통 · 끝에 치움)", x["act"] == "풀기" and x["n"] == 4 and x["ops"][-1]["op"] == "rmdir"
   and any(o.get("dst") == sch + "/강의자료/3주차 강의.pdf" for o in x["ops"]) and any(o.get("dst") == wk + "/과목A 섞임/sub/코드.v" for o in x["ops"]) and sum(o["op"] == "rm" for o in x["ops"]) == 1, json.dumps(x["ops"], ensure_ascii=False)[:300])
ok("옮길 때 원본 층에 재료 안 감(전 항목)", not any(o.get("dst", "").startswith(R["sources"] + "/") and os.path.splitext(o["dst"])[1].lower() in (".csv", ".v", ".png", ".py", ".txt") for r in j["items"] for o in r["ops"]))
# 실행 — 대본·Claude 도 휴지통까지(사용자 11-03 «확인했으면 비움» · 휴지통은 되살림)
a = run("--apply", "--json")
A = json.loads(a.stdout)
want = {"과목A 3주차 강의.pdf", "과A_과제2.hwp", "과목A 실험 사진.jpg", "과목A 족보 사진.jpg", "과목A ana_final.py", "과목A 시험자료", "과A 새재료", "기록", "과A 비슷한이름", "과목A 풀기", "과A 매주",
        "중복.pdf", "모두같음", "과A 끝난재료", "과A 끝난재료2", "과목A 섞임"}
ok("--apply = 확신 높음 전부(휴지통 포함)", set(A["moved"]) == want, str(sorted(set(A["moved"]) ^ want)))
led = ledger()
ok("장부 by=script:inbox", led and all(e["by"] == "script:inbox" for e in led), str(len(led)))
ok("옮긴 것은 새 자리에 · 받은함에서 사라짐", ex(sch + "/강의자료/과목A 3주차 강의.pdf") and ex(wk + "/과A 새재료/b.csv") and not ex(I + "/과A 새재료") and not ex(I + "/과목A 시험자료") and ex(sch + "/강의자료/과제 안내.pdf") is False and ex(sch + "/과제/과제 안내.pdf") and ex(wk + "/과목A 풀기/그림.png") and not ex(I + "/과목A 풀기"))
ok("재료 폴더는 원본 층에 사본 없음", not ex(sch + "/과A 새재료") and not ex(R["sources"] + "/배움/과목A/기록"))
ok("낮음·보통은 그대로", ex(I + "/과목A 메모.pdf") and ex(I + "/과A 쓰는재료/x.csv") and ex(I + "/과A md섞임/1.jpg"))
ok("휴지통까지 함 · 받은함에서 사라짐", not ex(I + "/중복.pdf") and not ex(I + "/과A 끝난재료") and not ex(I + "/과A 끝난재료2") and not ex(I + "/모두같음") and not ex(I + "/과목A 섞임") and ex(sch + "/강의자료/3주차 강의.pdf") and ex(wk + "/과목A 섞임/sub/코드.v"))
ok("휴지통 = 되살릴 자리 · 장부 user_asked", any(e["op"] == "rm" and e["by"] == "script:inbox" and e.get("user_asked") and e["src"] == I + "/과A 끝난재료" and ex(e["dst"]) for e in led))
ok("같은 내용 근거는 그대로 남음", ex(sch + "/강의자료/old.pdf") and ex(".trash/2026-01-01/x/옛것.pdf") and ex(I + "/쌍둥이1.pdf") and ex(I + "/쌍둥이2.pdf"))
b = run("--apply", "--by", "obsidian")
ok("요약이 마지막 줄", b.stdout.strip().splitlines()[-1].startswith("받은함 정리 · 옮김 ") and "휴지통 " in b.stdout.strip().splitlines()[-1] and "남음 " in b.stdout.strip().splitlines()[-1], b.stdout.strip().splitlines()[-1])
# 한 항목 — 한 묶음 · 되돌리기
d = run("--do", "과목A 메모.pdf")
ok("--do = 보통도 제안대로", d.returncode == 0 and ex(sch + "/과목A 메모.pdf") and not ex(I + "/과목A 메모.pdf"), d.stdout.strip().splitlines()[-1])
d2 = run("--do", "과A md섞임")
ok("--do = md 섞인 끝난 재료도 고르면 휴지통", d2.returncode == 0 and not ex(I + "/과A md섞임"), d2.stdout.strip().splitlines()[-1])
d4 = run("--do", "없는 항목")
ok("--do 없는 항목 = 실패", d4.returncode == 1)
t = run("--take", "휴지통본.pdf", sch + "/공지/휴지통본.pdf")
ok("--take = 사람이 고른 자리로", t.returncode == 0 and ex(sch + "/공지/휴지통본.pdf") and not ex(I + "/휴지통본.pdf"), t.stdout.strip())
batch = next(e["batch"] for e in reversed(ledger()) if e["src"].startswith(I + "/과목A 섞임/") and e["op"] == "mv")
u = fo("undo", batch)
ok("풀기 한 묶음 = 한 번에 되돌림", u.returncode == 0 and ex(I + "/과목A 섞임/3주차 강의.pdf") and ex(I + "/과목A 섞임/sub/코드.v") and ex(I + "/과목A 섞임/사본.pdf") and not ex(wk + "/과목A 섞임/sub/코드.v"), (u.stdout + u.stderr).strip()[-200:])
# 잠금 — 파이썬이 파일을 연 채(공유 지우기 없음) 폴더를 옮기면: 아무것도 안 변함 · 사본 없음 · 장부 없음 · 쥔 프로그램 이름
L = I + "/과A 잠긴재료"
for f in ("가.csv", "나.jpg", "다.jpg"):
    put(L + "/" + f, b"LOCK-" + f.encode("utf-8"))
holder = subprocess.Popen([sys.executable, "-c", "import sys,time\nf=open(sys.argv[1],'rb')\nprint('열림',flush=True)\ntime.sleep(120)", os.path.join(V, *L.split("/"), "나.jpg")], stdout=subprocess.PIPE, text=True, encoding="utf-8")
holder.stdout.readline()
before = len(ledger())
files = lambda r: sorted(os.listdir(os.path.join(V, *r.split("/"))))
newdir = sch + "/새 칸/더 깊이"
m = fo("mv", L, newdir + "/과A 잠긴재료")
ok("잠금: fileops mv = 실패 · 쥔 프로그램 이름·pid·파일", m.returncode == 1 and "pid %d" % holder.pid in m.stdout and "나.jpg" in m.stdout, m.stdout.strip()[:200])
ok("잠금: 옛 자리 그대로(3개) · 새 자리 없음 · 만든 폴더 치움", files(L) == ["가.csv", "나.jpg", "다.jpg"] and not ex(sch + "/새 칸"))
ok("잠금: 장부에 안 남음", len(ledger()) == before)
r2 = fo("rm", L, "--user-asked", "--why", "시험")
ok("잠금: rm 도 그대로 · 이름 나옴", r2.returncode == 1 and "pid %d" % holder.pid in r2.stdout and files(L) == ["가.csv", "나.jpg", "다.jpg"] and len(ledger()) == before, r2.stdout.strip()[:160])
w = fo("who", L)
ok("잠금: who = 쥔 프로그램 · 장부 없음", w.returncode == 0 and "pid %d" % holder.pid in w.stdout and len(ledger()) == before, w.stdout.strip())
d5 = run("--do", "과A 잠긴재료", "--by", "obsidian")
ok("잠금: inbox --do = 종료 1 · 까닭에 이름 · 그대로", d5.returncode == 1 and "pid %d" % holder.pid in d5.stdout and files(L) == ["가.csv", "나.jpg", "다.jpg"], d5.stdout.strip().splitlines()[-2][:160] if len(d5.stdout.strip().splitlines()) > 1 else d5.stdout)
holder.kill(); holder.wait(); holder.stdout.close()
time.sleep(0.2)
ok("잠금: 풀리면 who 비어 있음", not fo("who", L).stdout.strip())
d6 = run("--do", "과A 잠긴재료", "--by", "obsidian")
ok("잠금: 풀린 뒤 = 정상 처리", d6.returncode == 0 and not ex(L) and ex(wk + "/과A 잠긴재료/나.jpg"), d6.stdout.strip().splitlines()[-1])
print("%d/%d" % (sum(res), len(res)))
shutil.rmtree(root, ignore_errors=True)
sys.exit(0 if all(res) else 1)
