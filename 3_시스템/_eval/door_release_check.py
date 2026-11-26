# 받는 문 구동부 받기 시험(2026-11-26 · 실행 파일은 릴리스 첨부로 — 저장소의 해시 표와 맞을 때만 놓는다)
# 실행: py -3 3_시스템/_eval/door_release_check.py — 가짜 릴리스(로컬 파일 주소) · 진짜 레지스트리·탐색기·네트워크는 안 건드림
import json, os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)
root = tempfile.mkdtemp(prefix="door-rel-")
V = os.path.join(root, "vault")
S = os.path.join(V, "3_시스템")
A = os.path.join(S, "door-app")
REL = os.path.join(root, "release")  # 가짜 릴리스 첨부 자리
os.makedirs(A)
os.makedirs(REL)
for f in ("fileops.py", "roles.py", "roles.json", "inbox.py", "work.py", "work.json", "follow.py", "outside.py", "door.py"):
    shutil.copy2(os.path.join(SYS, f), os.path.join(S, f))
NAMES = ("brain-key.exe", "brain-inbox-menu.dll", "brain-inbox-menu.msix")
for i, n in enumerate(NAMES):  # 줄끝 두 가지가 섞인 글 아닌 내용 — 받는 길이 한 바이트도 안 바꾸는지
    open(os.path.join(REL, n), "wb").write(b"MZ\r\n\x00\x01" + bytes([i]) * 64 + b"\n\r\n")
URL = "file:///" + REL.replace("\\", "/") + "/"
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", DOOR_NO_TOAST="1", DOOR_NO_PIN="1")
ENV.pop("CLAUDECODE", None)
ENV.pop("DOOR_APP", None)
res = []


def ok(name, cond, detail=""):
    res.append(bool(cond))
    print("%s %s%s" % ("통과" if cond else "실패", name, "" if cond else " — %s" % (detail,)))


def door(*a, env=None):
    r = subprocess.run([sys.executable, os.path.join(S, "door.py"), *a], capture_output=True, encoding="utf-8", errors="replace", env=env or ENV, cwd=V)
    return r.returncode, (r.stdout + r.stderr).strip()


def call(expr, env=None):
    """door.py 의 함수 하나를 그 볼트에서 부른다(등록까지 가는 install 은 부르지 않는다)."""
    code = "import sys, json; sys.path.insert(0, %r); import door; print(json.dumps(%s, ensure_ascii=False))" % (S, expr)
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, encoding="utf-8", errors="replace", env=env or ENV, cwd=V)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return ["오류", r.stdout + r.stderr]


def have():
    return sorted(n for n in os.listdir(A) if n in NAMES or n.endswith(".part"))


# 표 만들기(출시 쪽 relhash) — 주소는 가짜 릴리스
c, o = door("relhash", REL, "door-app-test", URL)
T = json.load(open(os.path.join(A, "release.json"), encoding="utf-8"))
ok("relhash: 표에 판·주소·파일 셋(크기·sha256)", c == 0 and T["판"] == "door-app-test" and [f["이름"] for f in T["파일"]] == list(NAMES) and all(len(f["sha256"]) == 64 for f in T["파일"]), o)
c, o = door("relcheck")
ok("relcheck: 올린 첨부가 표와 맞음 = 0 · 볼트에는 아무것도 안 놓음", c == 0 and have() == [], (c, o, have()))

# 상태 셋
c, o = door("state")
ok("state: 구동부 없음 + 받을 수 있음", c == 0 and "받을 수 있음" in o, o)
c, o = door("installed")
ok("installed: 구동부 없음 = 안 됨(종료 1) · 받는 길을 말함", c == 1 and "릴리스 첨부" in o, o)

# ㉠ 맞는 해시 = 놓임(바이트 그대로)
r = call("door.fetch(door.DRIVERS[:2])")
same = all(open(os.path.join(A, n), "rb").read() == open(os.path.join(REL, n), "rb").read() for n in NAMES[:2])
ok("㉠ 맞는 해시: 받아 놓음 · 바이트가 첨부와 같음 · 남은 임시 파일 0", r[0] == "ok" and have() == sorted(NAMES[:2]) and same, (r, have()))
r = call("door.fetch(door.DRIVERS)")
ok("㉠ 첫 메뉴용 셋째도 받음", r[0] == "ok" and have() == sorted(NAMES), (r, have()))

# ㉣ 이미 있는 볼트 = 다시 받지 않음(표와 다른 제 빌드여도 건드리지 않음 · 받을 곳이 없어도 ok)
open(os.path.join(A, NAMES[0]), "wb").write(b"my own build")
r = call("door.fetch(door.DRIVERS)", env=dict(ENV, DOOR_RELEASE="file:///" + os.path.join(root, "nowhere").replace("\\", "/")))
ok("㉣ 이미 있음: 다시 받지 않음 · 있던 파일 그대로", r[0] == "ok" and open(os.path.join(A, NAMES[0]), "rb").read() == b"my own build", r)
c, o = door("state", "--no-probe")
ok("state: 구동부 있음(등록 전)", "구동부 있음" in o, o)

# ㉡ 바뀐 파일 = 거절·지움
for n in NAMES:
    os.remove(os.path.join(A, n))
open(os.path.join(REL, NAMES[1]), "ab").write(b"!")
r = call("door.fetch(door.DRIVERS[:2])")
ok("㉡ 바뀐 첨부(1바이트 더함): 거절 · 그 파일을 안 놓고 임시 파일도 지움", r[0] == "bad" and NAMES[1] not in have() and not [x for x in have() if x.endswith(".part")], (r, have()))
ok("㉡ 까닭을 말함(파일 이름·크기·sha256)", NAMES[1] in r[1] and "sha256" in r[1], r)
b = bytearray(open(os.path.join(REL, NAMES[0]), "rb").read()); b[5] ^= 1
open(os.path.join(REL, NAMES[0]), "wb").write(bytes(b))
for n in have():
    os.remove(os.path.join(A, n))
r = call("door.fetch(door.DRIVERS[:1])")
ok("㉡ 크기는 같고 내용만 다름: 거절", r[0] == "bad" and have() == [], (r, have()))
c, o = door("relcheck")
ok("relcheck: 첨부가 표와 다르면 종료 1", c == 1, (c, o))
c, o = door("install")  # 구동부를 못 놓으면 등록까지 안 간다(레지스트리 안 건드림)
ok("install: 값이 다르면 깔지 않고 종료 1", c == 1 and "깔지 않는다" in o, (c, o))

# ㉢ 네트워크 없음 = 바른 안내 · 실패 아님
OFF = dict(ENV, DOOR_RELEASE="http://127.0.0.1:9/none/")
r = call("door.fetch(door.DRIVERS[:2])", env=OFF)
ok("㉢ 못 받음: offline · 놓인 것 0", r[0] == "offline" and have() == [], (r, have()))
c, o = door("install", env=OFF)
ok("㉢ install: 실패 아님(종료 0) · «나중에 · 받은함 폴더로 끌어 넣기» 안내", c == 0 and "끌어 넣" in o and "나중에" in o, (c, o))
c, o = door("state", env=OFF)
ok("㉢ state: 못 받음", c == 1 and "못 받음" in o, (c, o))
c, o = door("menu", env=OFF)
ok("㉢ menu: 구동부를 못 받으면 관리자 창을 띄우지 않고 안내(설치 대본이 없으면 그 말)", "없음" in o or "나중에" in o, (c, o))

# 표가 없는 볼트(옛 판)
os.remove(os.path.join(A, "release.json"))
r = call("door.fetch(door.DRIVERS[:2])")
ok("표 없음: none · install 은 실패 아님", r[0] == "none" and door("install")[0] == 0, r)
c, o = door("state")
ok("state: 표도 구동부도 없으면 못 받음 · 끌어 넣기는 된다고 말함", c == 1 and "끌어 넣" in o, o)

shutil.rmtree(root, ignore_errors=True)
print("%d/%d" % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
