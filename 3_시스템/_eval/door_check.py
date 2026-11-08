# 받는 문 회귀 시험(11-03 · 설계안 §13.3 B2) · 실행: py -3 3_시스템/_eval/door_check.py — 격리 볼트 + 가짜 내려받기 · 등록(install)·실행 파일은 안 건드림
import json, os, shutil, subprocess, sys, tempfile, time

REAL = r"C:\Claude_Brain\3_시스템"
root = tempfile.mkdtemp(prefix="door-")
V = os.path.join(root, "vault")
S = os.path.join(V, "3_시스템")
D = os.path.join(root, "내려받기폴더")
os.makedirs(S)
os.makedirs(D)
for f in ("fileops.py", "roles.py", "roles.json", "inbox.py", "work.py", "work.json", "follow.py", "outside.py", "door.py"):
    shutil.copy2(os.path.join(REAL, f), os.path.join(S, f))
R = json.load(open(os.path.join(S, "roles.json"), encoding="utf-8"))["roles"]
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", FILEOPS_NO_OBSIDIAN="1", OUTSIDE_DIRS="내려받기=" + D, DOOR_NO_TOAST="1", DOOR_VAULT_ON="1")
ENV.pop("CLAUDECODE", None)
res = []
I = R["inbox"]


def ok(name, cond, detail=""):
    res.append(bool(cond))
    print("%s %s%s" % ("통과" if cond else "실패", name, "" if cond else " — %s" % (detail,)))


def vpath(r):
    return os.path.join(V, *r.split("/"))


def vput(r, data=b"x"):
    a = vpath(r)
    os.makedirs(os.path.dirname(a), exist_ok=True)
    open(a, "wb").write(data if isinstance(data, bytes) else data.encode("utf-8"))
    return a


def dl(name, data=b"x"):
    a = os.path.join(D, name)
    os.makedirs(os.path.dirname(a), exist_ok=True)
    open(a, "wb").write(data)
    return a


def door(*a):
    r = subprocess.run([sys.executable, os.path.join(S, "door.py"), *a], cwd=V, env=ENV, capture_output=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr).strip()


def last_toast():
    lines = [x for x in open(os.path.join(S, "_index", "door", "door.log"), encoding="utf-8") if " 알림: " in x]
    return lines[-1].split(" 알림: ", 1)[1].strip() if lines else ""


def tokens():
    d = os.path.join(S, "_index", "door", "undo")
    return sorted(os.listdir(d), key=lambda x: os.path.getmtime(os.path.join(d, x))) if os.path.isdir(d) else []


def last_token():
    t = tokens()
    return t[-1][:-5] if t else ""


def ledger():
    return [json.loads(x) for x in open(os.path.join(S, "ledger", "ops.jsonl"), encoding="utf-8")]


vput(R["topics"], "# 주제\n```json\n" + json.dumps({"topics": [{"이름": "과목A", "영역": "배움", "별칭": ["과A"], "학기": "2026-2", "상태": "진행"}]}, ensure_ascii=False) + "\n```\n")
sch = R["school"] + "/과목A"
vput(sch + "/강의자료/old.pdf", b"PDF-OLD")
os.makedirs(vpath(I), exist_ok=True)

# 1. 주제 없는 파일 = 받은함에 남음 · 옮김(원래 자리에 없음) · 장부에 볼트 밖 경로 없음
a = dl("아무거나.pdf", b"A1")
code, out = door("put", a)
ok("옮겨짐(복사 아님)", code == 0 and not os.path.exists(a) and os.path.exists(vpath(I + "/아무거나.pdf")), out)
e = ledger()[-1]
ok("장부 = 들임 · 내려받기/이름 · 절대 경로 없음", e["op"] == "cp" and e["src"] == "내려받기/아무거나.pdf" and e.get("moved") and D not in json.dumps(ledger(), ensure_ascii=False), e)
ok("알림 = 이름 · 받은함 · 되돌리기", last_toast() == "아무거나.pdf | 받은함 | 되돌리기", last_toast())

# 2. 되돌리기 = 원래 자리로
tk = last_token()
code, out = door("undo", tk)
ok("되돌리기 = 내려받기로 돌아옴 · 받은함에 없음", code == 0 and os.path.exists(a) and not os.path.exists(vpath(I + "/아무거나.pdf")), out)
ok("되돌리기 칸 지움 · 다시 눌러도 무해", door("undo", tk)[0] == 1 and "지남" in last_toast(), last_toast())
ok("이상한 토큰 거절", door("undo", "../../x")[0] == 1)

# 3. 확신 높음 = 바로 제자리 · 되돌리면 받은함을 거쳐 원래 자리로
b = dl("과목A 3주차 강의.pdf", b"B1")
code, out = door("put", b)
fin = vpath(sch + "/강의자료/과목A 3주차 강의.pdf")
ok("바로 제자리로", code == 0 and os.path.exists(fin) and not os.path.exists(vpath(I + "/과목A 3주차 강의.pdf")), out)
ok("알림 = 간 자리", "과목A/강의자료" in last_toast(), last_toast())
code, out = door("undo", last_token())
ok("되돌리기 = 제자리에서도 원래 자리로", code == 0 and os.path.exists(b) and not os.path.exists(fin), out)

# 3-1. 볼트가 꺼져 있으면 = 받은함에서 기다림 · 켤 때(sweep) 제자리로 · 예약 작업 없음
ENV["DOOR_VAULT_ON"] = "0"
b2 = dl("과목A 4주차 강의.pdf", b"B2")
code, out = door("put", b2)
ok("꺼져 있으면 받은함까지만", code == 0 and not os.path.exists(b2) and os.path.exists(vpath(I + "/과목A 4주차 강의.pdf")), out)
ok("알림 = 받은함", "| 받은함 |" in last_toast(), last_toast())
ENV["DOOR_VAULT_ON"] = "1"
src = open(os.path.join(S, "door.py"), encoding="utf-8").read()
open(os.path.join(S, "door.py"), "w", encoding="utf-8").write(src.replace("SETTLE = 20", "SETTLE = 0"))
code, out = door("sweep")
ok("켤 때 sweep = 제자리로", code == 0 and os.path.exists(vpath(sch + "/강의자료/과목A 4주차 강의.pdf")), out + last_toast())
os.remove(vpath(sch + "/강의자료/과목A 4주차 강의.pdf"))
open(os.path.join(S, "door.py"), "w", encoding="utf-8").write(src)

# 4. 같은 내용 = 받은함이 휴지통으로 · 원래 자리 비움
c = dl("사본.pdf", b"PDF-OLD")
code, out = door("put", c)
ok("같은 내용 = 볼트 휴지통 · 원래 자리 비움", code == 0 and not os.path.exists(c) and not os.path.exists(vpath(I + "/사본.pdf")), out)
ok("알림 = 이미 있음", "이미 있음" in last_toast(), last_toast())
code, out = door("undo", last_token())
ok("되돌리기 = 휴지통에서도 원래 자리로", code == 0 and os.path.exists(c), out)
os.remove(c)

# 5. 이름 겹침 · 여러 개 · 폴더
vput(I + "/겹침.pdf", b"OLD")
d1, d2 = dl("겹침.pdf", b"NEW"), dl("둘째.pdf", b"D2")
fold = dl("묶음/안/파일.pdf", b"F1")
open(os.path.join(D, "묶음", "desktop.ini"), "w").write("x")
code, out = door("put", d1, d2, os.path.join(D, "묶음"))
ok("겹치면 « 2» · 있던 것 그대로", open(vpath(I + "/겹침 2.pdf"), "rb").read() == b"NEW" and open(vpath(I + "/겹침.pdf"), "rb").read() == b"OLD", out)
ok("여러 개 알림", last_toast().startswith("3개"), last_toast())
ok("폴더 = 안까지 옮김 · 원래 폴더 사라짐", os.path.exists(vpath(I + "/묶음/안/파일.pdf")) and not os.path.exists(os.path.join(D, "묶음")), out)
code, out = door("undo", last_token())
ok("여러 개 되돌리기", code == 0 and os.path.exists(d1) and os.path.exists(d2) and os.path.exists(fold) and open(vpath(I + "/겹침.pdf"), "rb").read() == b"OLD", out)
for x in (d1, d2):
    os.remove(x)
shutil.rmtree(os.path.join(D, "묶음"))

# 6. 받지 않는 것
inv = vput(I + "/안.pdf", b"IN")
ok("볼트 안 파일 거절", door("put", inv)[0] == 1 and "볼트 안" in last_toast() and os.path.exists(inv), last_toast())
ok("볼트를 품은 폴더 거절", door("put", root)[0] == 1 and "볼트를 품은" in last_toast() and os.path.isdir(V), last_toast())
home = os.path.expanduser("~")
ok("사용자 폴더 거절", door("put", os.path.join(home, "Downloads"))[0] == 1 and "사용자 폴더" in last_toast() and os.path.isdir(os.path.join(home, "Downloads")), last_toast())
cr = dl("받는중.pdf.crdownload", b"P")
ok("받는 중 거절", door("put", cr)[0] == 1 and "받는 중" in last_toast() and os.path.exists(cr), last_toast())
os.remove(cr)
os.remove(inv)
lk = dl("잠김.pdf", b"L")
h = open(lk, "rb")
code, out = door("put", lk)
h.close()
ok("열려 있는 파일 = 못 옮김 · 그대로", code == 1 and os.path.exists(lk) and not os.path.exists(vpath(I + "/잠김.pdf")) and "못 옮김" in last_toast(), last_toast())
os.remove(lk)

# 7. 방금 받은 파일
old = dl("옛날.pdf", b"O")
os.utime(old, (time.time() - 3 * 86400, time.time() - 3 * 86400))
new = dl("새것.pdf", b"N")
dl("받는중2.pdf.crdownload", b"P")
dl("설치.exe", b"E")
time.sleep(0.05)
code, out = door("recent")
ok("recent = 가장 새 문서 · 받는 중·설치 파일 건너뜀", code == 0 and not os.path.exists(new) and os.path.exists(vpath(I + "/새것.pdf")) and os.path.exists(old), out + last_toast())
for x in os.listdir(D):
    if x != "옛날.pdf":
        os.remove(os.path.join(D, x))
code, out = door("recent")
print("  (옛날.pdf 만듦 시각이 방금이라 recent 판정 = %s)" % last_toast())

# 8. 즐겨찾기로 끌어 넣은 것 = sweep
door("sweep")   # 지금까지 남은 것을 본 것으로
sw = vput(I + "/과A_과제2.hwp", b"S1")
code, out = door("sweep")
ok("막 들어온 것은 안 건드림(끌어 넣는 중일 수 있음)", code == 0 and os.path.exists(sw), out)
t = time.time() - 120
os.utime(sw, (t, t))
ctime_guard = os.path.getctime(sw)
# 만든 시각은 못 바꾼다 — 시험만 SETTLE 을 0 으로
src = open(os.path.join(S, "door.py"), encoding="utf-8").read().replace("SETTLE = 20", "SETTLE = 0")
open(os.path.join(S, "door.py"), "w", encoding="utf-8").write(src)
code, out = door("sweep")
fin2 = vpath(sch + "/과제/과A_과제2.hwp")
ok("sweep = 확신 높음 제자리 · 알림", code == 0 and os.path.exists(fin2) and "과목A/과제" in last_toast(), out + last_toast())
n0 = len(ledger())
low = vput(I + "/애매.pdf", b"S2")
door("sweep")
ok("애매한 것 = 받은함에 남음", os.path.exists(low), "")
stamp = os.path.getmtime(os.path.join(S, "_index", "door", "seen.json"))
code, out = door("sweep")
ok("두 번째부터 다시 안 봄(새것 0)", code == 0 and os.path.exists(low) and ledger()[-1]["op"] == "cp" or len(ledger()) == n0, ledger()[-1])
code, out = door("undo", last_token())
ok("sweep 되돌리기 = 받은함으로 · 다시 안 옮김", code == 0 and os.path.exists(vpath(I + "/과A_과제2.hwp")) and not os.path.exists(fin2), out)
door("sweep")
ok("되돌린 것은 다음 정리가 안 건드림", os.path.exists(vpath(I + "/과A_과제2.hwp")) and not os.path.exists(fin2), "")

# 9. 잠금 — 다른 정리가 도는 중이면 sweep 은 조용히 빠짐
open(os.path.join(S, "_index", "door", "lock"), "w").close()
vput(I + "/과A_과제3.hwp", b"S3")
code, out = door("sweep")
ok("잠겨 있으면 sweep 은 건너뜀", code == 0 and os.path.exists(vpath(I + "/과A_과제3.hwp")), out)
os.remove(os.path.join(S, "_index", "door", "lock"))

# 10. 따라가기 — 들이고 되돌려도 «바깥에서 지움»으로 안 적음(장부의 out 을 안다)
ENV["FOLLOW_NO_INGEST"] = "1"


def follow():
    r = subprocess.run([sys.executable, os.path.join(S, "follow.py"), "--json"], cwd=V, env=ENV, capture_output=True, encoding="utf-8", errors="replace")
    return json.loads(r.stdout.strip().splitlines()[-1])


follow()    # 사진
fa = dl("따라가기시험.pdf", b"FA")
door("put", fa)
follow()    # 받은함에 든 뒤 사진
n0 = len(ledger())
code, out = door("undo", last_token())
j = follow()
ok("되돌리기 = 따라가기가 바깥으로 안 적음", code == 0 and os.path.exists(fa) and not j.get("gone") and not j.get("moved") and all(e["op"] != "rm" for e in ledger()[n0:]), j)

shutil.rmtree(root, ignore_errors=True)
print("%d/%d" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
