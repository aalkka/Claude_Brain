# 볼트 밖 후보 회귀 시험(11-03 · 설계안 §13.3 B2②) · 실행: py -3 3_시스템/_eval/outside_check.py — 격리 볼트 + 가짜 내려받기 폴더에서 볼트에 없는 문서만 보이는지 · 들이기가 복사이고 경로를 안 남기는지
import json, os, shutil, subprocess, sys, tempfile, time

REAL = r"C:\Claude_Brain\3_시스템"
root = tempfile.mkdtemp(prefix="outside-")
V = os.path.join(root, "vault")
S = os.path.join(V, "3_시스템")
D = os.path.join(root, "내려받기폴더")
os.makedirs(S)
os.makedirs(D)
for f in ("fileops.py", "roles.py", "roles.json", "follow.py", "outside.py"):
    shutil.copy2(os.path.join(REAL, f), os.path.join(S, f))
R = json.load(open(os.path.join(S, "roles.json"), encoding="utf-8"))["roles"]
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", FILEOPS_NO_OBSIDIAN="1", FOLLOW_NO_INGEST="1", OUTSIDE_DIRS="내려받기=" + D)
res = []


def ok(name, cond, detail=""):
    res.append(bool(cond))
    print("%s %s%s" % ("통과" if cond else "실패", name, "" if cond else " — %s" % (detail,)))


def put(p, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "wb").write(data)


def run(script, *args):
    r = subprocess.run([sys.executable, os.path.join(S, script), *args], cwd=V, env=ENV, capture_output=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def rows():
    return json.loads(run("outside.py", "--json")[1].splitlines()[-1])


inv = os.path.join(V, *(R["school"] + "/과목A/강의자료/있음.pdf").split("/"))
put(inv, b"PDF-IN " * 30)
code, out = run("outside.py", "--json")
ok("사진 없으면 = 빈 목록(첫 사진을 안 찍음)", code == 0 and json.loads(out) == [] and not os.path.exists(os.path.join(S, "_index", "follow", "snapshot.json")), out)
run("follow.py")
put(os.path.join(D, "없음.pdf"), b"PDF-OUT " * 30)
put(os.path.join(D, "숨길.hwp"), b"HWP-OUT " * 30)
put(os.path.join(D, "이름만다름.pdf"), b"PDF-IN " * 30)     # 볼트와 같은 내용
put(os.path.join(D, "사진.jpg"), b"JPG " * 30)              # 문서 아님
put(os.path.join(D, "~$임시.docx"), b"LOCK")
put(os.path.join(D, "옛것.pdf"), b"PDF-OLD " * 30)
old = time.time() - 90 * 86400
os.utime(os.path.join(D, "옛것.pdf"), (old, old))
r = rows()
names = sorted(x["name"] for x in r)
ok("볼트에 없는 최근 문서만", names == ["숨길.hwp", "없음.pdf"], names)
ok("JSON 에 경로 없음", all("a" not in x and "sha" not in x for x in r), r)
code, out = run("outside.py", "hide", "숨길.hwp")
ok("숨김 = 목록에서 빠짐 · 파일 그대로", code == 0 and [x["name"] for x in rows()] == ["없음.pdf"] and os.path.exists(os.path.join(D, "숨길.hwp")), out)
key = rows()[0]["key"]
code, out = run("outside.py", "take", key)
dst = os.path.join(V, *(R["inbox"] + "/없음.pdf").split("/"))
ok("받은함으로 = 옮김(원래 자리에 안 남음)", code == 0 and os.path.exists(dst) and not os.path.exists(os.path.join(D, "없음.pdf")), out)
ops = [json.loads(x) for x in open(os.path.join(S, "ledger", "ops.jsonl"), encoding="utf-8")]
ok("장부 = 들임 · 볼트 밖 절대 경로 없음", ops[-1]["op"] == "cp" and ops[-1]["src"] == "내려받기/없음.pdf" and D not in json.dumps(ops, ensure_ascii=False), ops[-1])
ok("들인 뒤 = 목록에서 빠짐", rows() == [], rows())
cache = open(os.path.join(S, "_index", "outside", "cache.json"), encoding="utf-8").read()
ok("캐시에 이름·경로 없음", "없음" not in cache and "내려받기" not in cache, cache[:120])
code, out = run("follow.py", "--json")
ok("들임은 장부 안 일 = 따라가기가 바깥으로 안 적음", json.loads(out)["moved"] == 0 and json.loads(out)["gone"] == 0, out)
shutil.rmtree(root, ignore_errors=True)
print("%d/%d" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
