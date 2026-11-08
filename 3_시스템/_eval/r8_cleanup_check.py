# 볼트 개혁 R8 회귀 시험(10-30) · 실행: py -3 3_시스템/_eval/r8_cleanup_check.py — — 격리 볼트에 사례를 심고 cleanup.py 가 가르는지 · 계획이 fileops plan 미리 보기를 통과하는지
import json, os, shutil, subprocess, sys, tempfile, time

REAL = r"C:\Claude_Brain\3_시스템"
root = tempfile.mkdtemp(prefix="r8-")
V = os.path.join(root, "vault")
S = os.path.join(V, "3_시스템")
os.makedirs(S)
for f in ("fileops.py", "roles.py", "roles.json", "cleanup.py"):
    shutil.copy2(os.path.join(REAL, f), os.path.join(S, f))
def put(r, data=b"x", age_days=0):
    a = os.path.join(V, *r.split("/"))
    os.makedirs(os.path.dirname(a), exist_ok=True)
    open(a, "wb").write(data)
    if age_days:
        t = time.time() - age_days * 86400
        os.utime(a, (t, t))
    return a
put("1_수집/학교/과목/제출/보고서.pdf", b"PDF-A")
put("0_작업/과목/보고서.pdf", b"PDF-A", age_days=40)          # 제출된 작업 파일(40일) → 후보
put("0_작업/과목/새 보고서.pdf", b"PDF-B")
put("1_수집/학교/과목/제출/새 보고서.pdf", b"PDF-B")          # 작업 쪽이 갓 만든 것 → 아직
put("1_수집/학교/과목/강의자료/a.pdf", b"PDF-C")
put("1_수집/학교/과목/강의자료/a 사본.pdf", b"PDF-C")          # 원본끼리 사본 → 후보(나중 것)
put("1_수집/_색인/학교/과목/강의자료/a.pdf.색인.md", b"")       # 색인 칸 = 기계 → 안 봄
put("0_작업/과목/빈.txt", b"")                                  # 빈 파일 → 후보
os.makedirs(os.path.join(V, "0_작업", "과목", "빈 폴더"))       # 빈 폴더 → 후보
os.makedirs(os.path.join(V, "1_수집", "학교", "과목", "족보"))  # 고정 하위 → 안 봄
put("1_수집/받은함/오래 머문 것.pdf", b"PDF-D", age_days=9)    # 머무름 보고
env = dict(os.environ, PYTHONIOENCODING="utf-8")
env.pop("CLAUDECODE", None)
r = subprocess.run([sys.executable, os.path.join(S, "cleanup.py"), "--json", "--days", "30"], capture_output=True, text=True, encoding="utf-8", env=env, cwd=V)
res = []
def ok(name, cond, detail=""):
    res.append(bool(cond)); print(("통과" if cond else "실패"), name, detail)
c = json.loads(r.stdout.strip().splitlines()[-1])
ok("사본 = 원본끼리 1(나중 것 · 남김 = 먼저 것)", [d["src"] for d in c["dup"]] == ["1_수집/학교/과목/강의자료/a 사본.pdf"], json.dumps(c["dup"], ensure_ascii=False))
ok("제출된 작업 파일 40일 = 후보 · 갓 만든 것 = 아직 1", [x["src"] for x in c["promoted_work"]] == ["0_작업/과목/보고서.pdf"] and c["promoted_work_young"] == 1, json.dumps(c["promoted_work"], ensure_ascii=False))
ok("빈 파일 = 작업 칸 1(색인 칸 빈 파일은 안 봄)", c["empty_files"] == ["0_작업/과목/빈.txt"], str(c["empty_files"]))
ok("빈 폴더 = 1(고정 하위 «족보» 는 안 봄)", c["empty_dirs"] == ["0_작업/과목/빈 폴더"], str(c["empty_dirs"]))
ok("받은함 머무름 보고 1", [x["path"] for x in c["inbox_stay"]] == ["1_수집/받은함/오래 머문 것.pdf"])
plan = os.path.join(V, *c["plan"].split("/"))
d = subprocess.run([sys.executable, os.path.join(S, "fileops.py"), "plan", plan], capture_output=True, text=True, encoding="utf-8", env=env, cwd=V)
ok("계획 = fileops 미리 보기 통과(아무것도 안 바뀜)", d.returncode == 0 and os.path.exists(os.path.join(V, "0_작업", "과목", "빈.txt")) and not os.path.exists(os.path.join(S, "ledger", "ops.jsonl")), d.stdout.strip().splitlines()[0] if d.stdout.strip() else d.stderr[-200:])
a = subprocess.run([sys.executable, os.path.join(S, "fileops.py"), "plan", plan, "--apply"], capture_output=True, text=True, encoding="utf-8", env=env, cwd=V)
led = [json.loads(l) for l in open(os.path.join(S, "ledger", "ops.jsonl"), encoding="utf-8")] if os.path.exists(os.path.join(S, "ledger", "ops.jsonl")) else []
ok("승인 뒤 적용 = 휴지통 4건 · 장부 4줄 · 남길 것은 그대로", a.returncode == 0 and len(led) == 4 and all(e["op"] == "rm" for e in led) and os.path.exists(os.path.join(V, "1_수집", "학교", "과목", "강의자료", "a.pdf")), "%d줄 %s" % (len(led), a.stdout.strip().splitlines()[-1:] if a.stdout else a.stderr[-200:]))
# 보존 표 칸(11-03) — 강의자료·공지(학기 끝 + 날) · 보관 칸(학기 끝) · 고아 첨부
shutil.copy2(os.path.join(os.path.dirname(REAL) if False else r"C:\Claude_Brain\2_지식", "보존.md"), os.path.join(V, "2_지식", "보존.md")) if os.path.isdir(os.path.join(V, "2_지식")) else (os.makedirs(os.path.join(V, "2_지식")), shutil.copy2(r"C:\Claude_Brain\2_지식\보존.md", os.path.join(V, "2_지식", "보존.md")))
put("2_지식/주제.md", ("```json\n" + json.dumps({"topics": [{"이름": "옛과목", "영역": "배움", "학기": "2020-1"}, {"이름": "새과목", "영역": "배움", "학기": "2099-2"}]}, ensure_ascii=False) + "\n```\n").encode("utf-8"))
for r_ in ("옛과목/강의자료/x.pdf", "옛과목/공지/y.md", "옛과목/과제/z.pdf", "새과목/강의자료/n.pdf"):
    put("1_수집/배움/" + r_, ("내용 " + r_).encode("utf-8"))
ARC = "3_시스템/_index/collect"
put(ARC + "/archive/1_수집/배움/학교공지/장학/옛글.md", b"old")
put(ARC + "/archive/1_수집/배움/학교공지/장학/새글.md", b"new")
put(ARC + "/t.json", json.dumps({"items": {"a1": {"archived": "1_수집\\배움\\학교공지\\장학\\옛글.md", "archived_run": "20200101-0000"}, "a2": {"archived": "1_수집\\배움\\학교공지\\장학\\새글.md", "archived_run": "20991231-0000"}, "a3": {"path": "1_수집\\배움\\x.md"}}}, ensure_ascii=False).encode("utf-8"))
put("2_지식/분야/안 쓰는 그림.png", b"PNG-A")
put("2_지식/분야/쓰는 그림.png", b"PNG-B")
put("2_지식/분야/그림 노트.md", "![[쓰는 그림.png]]\n".encode("utf-8"))
r = subprocess.run([sys.executable, os.path.join(S, "cleanup.py"), "--json"], capture_output=True, text=True, encoding="utf-8", env=env, cwd=V)
c = json.loads(r.stdout.strip().splitlines()[-1])
ok("강의자료 = 학기 끝 + 날 지난 과목의 강의자료·공지만(과제·새 과목은 둠)", sorted(x["src"] for x in c["lecture_old"]) == ["1_수집/배움/옛과목/강의자료", "1_수집/배움/옛과목/공지"], str(c["lecture_old"]))
ok("보관 칸 = 학기 끝 지난 글만", [x["src"] for x in c["archive_old"]] == [ARC + "/archive/1_수집/배움/학교공지/장학/옛글.md"], str(c["archive_old"]))
ok("고아 첨부 = 이름을 안 쓴 것만", c["orphan_attach"] == ["2_지식/분야/안 쓰는 그림.png"], str(c["orphan_attach"]))
a = subprocess.run([sys.executable, os.path.join(S, "fileops.py"), "plan", os.path.join(V, *c["plan"].split("/")), "--apply"], capture_output=True, text=True, encoding="utf-8", env=env, cwd=V)
gone = lambda r_: not os.path.exists(os.path.join(V, *r_.split("/")))
ok("승인 뒤 적용 = 후보만 휴지통", a.returncode == 0 and gone("1_수집/배움/옛과목/강의자료") and gone(ARC + "/archive/1_수집/배움/학교공지/장학/옛글.md") and gone("2_지식/분야/안 쓰는 그림.png") and not gone("1_수집/배움/옛과목/과제/z.pdf") and not gone("1_수집/배움/새과목/강의자료/n.pdf") and not gone("2_지식/분야/쓰는 그림.png"), a.stdout[-300:] + a.stderr[-200:])
print("%d/%d" % (sum(res), len(res)))
shutil.rmtree(root, ignore_errors=True)
