# -*- coding: utf-8 -*-
"""**받는 문** — 볼트 밖 파일을 받은함으로 «옮긴다»(2026-11-03).

왜: 받은함에 넣으려면 옵시디언을 켜고 끌어 넣어야 했고, 복사라 원래 파일을 또 지워야 했다 — 폴더에 직접 넣는 것과 다를 게 없었다.
문 셋(우클릭 메뉴 · 단축키 · 탐색기 왼쪽 즐겨찾기)이 이 엔진 하나로 들어온다. 정리(inbox.py · 확신 높음만 제자리로)는 볼트가 켜져 있을 때만 한다
(11-03 «볼트를 켜면 그때 · 예약 필요 없음») — 켜져 있으면 넣자마자 · 꺼져 있으면 받은함에서 기다렸다 brain-base 가 켤 때 sweep 을 부른다.
우클릭·단축키의 작은 실행 파일(구동부 셋)은 `3_시스템/door-app/` 에 놓인다 — 서명 없는 실행 파일이라 저장소에는 싣지 않고 릴리스 첨부로 낸다(사용자 2026-11-26).
없으면 `install`·`menu` 가 `door-app/release.json`(주소·크기·sha256 · 저장소에 실림)대로 받아, 적어 둔 값과 같을 때만 놓는다. 못 받으면 즐겨찾기만 넣고 끌어 넣기를 안내한다(실패 아님).
`door.cfg`·`install-menu.log` 는 설치할 때 이 PC 값으로 쓰는 파일이라 git 밖이다.

  py -3 3_시스템/door.py put <경로...>      옮김(볼트가 켜져 있으면 바로 정리)
  py -3 3_시스템/door.py list <목록 파일>    우클릭·단축키가 부른다(줄마다 경로 · 읽고 지움)
  py -3 3_시스템/door.py recent             내려받기에서 방금 받은 파일 하나
  py -3 3_시스템/door.py sweep              받은함에 새로 든 것 정리 + 끝난 작업 비우기(brain-base 가 켤 때 · 켜진 동안 받은함에 새로 들 때)
  py -3 3_시스템/door.py undo <토큰>         알림의 되돌리기(원래 자리로)
  py -3 3_시스템/door.py install | remove | status   즐겨찾기·단축키·보내기·알림·Shift+우클릭 등록·해제·확인(지속 설정 — 사람이 승인)
  py -3 3_시스템/door.py installed          이 볼트의 것이 등록됐나(종료 0 됨 · 1 안 됨 · 읽기만)
  py -3 3_시스템/door.py menu [--remove]    탐색기 첫 우클릭 메뉴에도 넣기·빼기(윈도 관리자 확인 1번 — 사람이 «예»)
  py -3 3_시스템/door.py state [--no-probe] 구동부 상태 한 줄: 깔림 / 받을 수 있음 / 못 받음(읽기만)
  py -3 3_시스템/door.py relhash <폴더> <판 꼬리표> <주소> | relcheck   출시 쪽: release.json 다시 쓰기 · 올린 첨부가 표와 맞는지

장부에는 «내려받기/이름»만 적는다(outside.py 와 같음). 원래 자리 절대 경로는 되돌리기 칸(`_index/door/undo` · git 밖 · 하루)에만 둔다.
"""
import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import traceback
from xml.sax.saxutils import escape

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import roles  # noqa: E402

BY = "script:door"
OUT = os.path.join(HERE, "_index", "door")
SEEN = os.path.join(OUT, "seen.json")
LOCK = os.path.join(OUT, "lock")
LOG = os.path.join(OUT, "door.log")
UNDO = os.path.join(OUT, "undo")
APP = os.environ.get("DOOR_APP") or os.path.join(HERE, "door-app")
REL = os.path.join(HERE, "door-app", "release.json")  # 릴리스 첨부 표(주소·크기·sha256) — 구동부가 없을 때 install 이 여기서 받는다
DRIVERS = ("brain-key.exe", "brain-inbox-menu.dll", "brain-inbox-menu.msix")  # 앞 둘 = 단축키·Shift+우클릭 · 셋째 = 첫 우클릭 메뉴(menu)
HOTKEY = "Ctrl+Alt+B"
AUMID = "Claude_Brain.Door"
CLSID = "{6F1D2C84-3B7A-4E95-A1C6-7D2E9B40F513}"
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
JUNK = ("desktop.ini", "thumbs.db")  # fileops 빈 폴더 판정과 같은 표
BUSY = (".crdownload", ".part", ".tmp", ".download")  # 받는 중
NOT_RECENT = BUSY + (".exe", ".msi", ".lnk", ".ini")  # «방금 받은 파일»로 집지 않는다
RECENT_MIN = 30
SETTLE = 20  # 초 — 끌어 넣는 중인 것을 건드리지 않게


def log(msg):
    os.makedirs(OUT, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (time.strftime("%m-%d %H:%M:%S"), msg))


def load(p, default):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, p)


class Busy(Exception):
    pass


class Lock:
    """한 번에 하나 — 우클릭·단축키·예약 작업이 겹쳐도 같은 자리를 잡지 않게."""

    def __init__(self, wait=30):
        self.wait = wait

    def __enter__(self):
        os.makedirs(OUT, exist_ok=True)
        end = time.time() + self.wait
        while True:
            try:
                os.close(os.open(LOCK, os.O_CREAT | os.O_EXCL))
                return self
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(LOCK) > 600:  # 죽은 프로세스가 남긴 것
                        os.remove(LOCK)
                        continue
                except OSError:
                    pass
                if time.time() >= end:
                    raise Busy()
                time.sleep(0.2)

    def __exit__(self, *a):
        try:
            os.remove(LOCK)
        except OSError:
            pass


def hidden(*args):
    """콘솔 없는 창으로 다시 — pyw 에서 부르면 옵시디언 CLI·OCR 같은 콘솔 프로그램이 창을 띄운다."""
    py = os.path.join(os.path.dirname(sys.executable), "python.exe")
    subprocess.Popen([py, os.path.abspath(__file__), *args], creationflags=NO_WINDOW, cwd=VAULT)


def toast(title, body="", token=None):
    log("알림: %s | %s%s" % (title, body, " | 되돌리기" if token else ""))
    if os.environ.get("DOOR_NO_TOAST"):
        return
    act = ""
    if token:
        act = '<actions><action content="되돌리기" activationType="protocol" arguments="brainbox:undo/%s"/></actions>' % token
    xml = ('<toast><visual><binding template="ToastGeneric"><text>%s</text><text>%s</text></binding></visual>'
           '<audio silent="true"/>%s</toast>') % (escape(title), escape(body), act)
    ps = ("$null=[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime];"
          "$null=[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom,ContentType=WindowsRuntime];"
          "$x=New-Object Windows.Data.Xml.Dom.XmlDocument;$x.LoadXml(@'\n" + xml + "\n'@);"
          "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('" + AUMID + "')"
          ".Show((New-Object Windows.UI.Notifications.ToastNotification $x))")
    enc = base64.b64encode(ps.encode("utf-16-le")).decode()
    subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc], creationflags=NO_WINDOW,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ── 들이기 ──────────────────────────────────────

def inside(a, root):
    a, root = os.path.normcase(a).rstrip("\\/"), os.path.normcase(root).rstrip("\\/")
    return a == root or a.startswith(root + os.sep)


def known_dirs():
    """옮기면 안 되는 자리 — 사용자 폴더·드라이브·윈도(안의 파일은 된다 · 그 폴더 자체만 막음)."""
    home = os.path.expanduser("~")
    out = [home] + [os.path.join(home, n) for n in ("Downloads", "Desktop", "Documents", "Pictures", "Music", "Videos", "OneDrive")]
    try:
        import ctypes
        for csidl in (0x0010, 0x0005, 0x0027, 0x000d, 0x000e):
            b = ctypes.create_unicode_buffer(520)
            if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, b) == 0:
                out.append(b.value)
    except (AttributeError, OSError):
        pass
    return out


def refuse(a):
    """받지 않는 까닭 · 받으면 None."""
    if not os.path.exists(a):
        return "없음"
    if inside(a, VAULT):
        return "볼트 안 파일"
    if inside(VAULT, a) or os.path.dirname(a.rstrip("\\/")) == a.rstrip("\\/"):
        return "볼트를 품은 폴더"
    if os.path.isfile(a) and a.lower().endswith(BUSY):
        return "받는 중"
    if os.path.isdir(a):
        if any(os.path.normcase(a.rstrip("\\/")) == os.path.normcase(k.rstrip("\\/")) for k in known_dirs()):
            return "사용자 폴더"
        if any(v and inside(a, v) for v in (os.environ.get("WINDIR"), os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"))):
            return "시스템 폴더"
    return None


def label(a):
    """장부에 적는 출처 — 볼트 밖 절대 경로를 적지 않는다."""
    import outside
    for name, d in outside.places():
        if inside(a, d):
            return name + "/" + os.path.relpath(a, d).replace("\\", "/")
    return "밖/" + os.path.basename(a.rstrip("\\/"))


def bring(ctx, a, inbox, taken):
    """하나를 받은함으로 옮김 → 받은함 안 항목 이름. 파일 = 원자적 이름 바꾸기(같은 드라이브) · 폴더 = 안 파일마다 장부에."""
    import fileops
    base = roles.path("inbox") + "/" + os.path.basename(a.rstrip("\\/"))
    if os.path.isfile(a):
        dst = inbox.free(base, taken)
        fileops.op_cp(ctx, a, dst, "받는 문", dup_ok=True, src_label=label(a), move=True, quiet=True, back=True)
        return dst.rsplit("/", 1)[-1]
    files = [f for f in fileops.files_under(a) if os.path.basename(f).lower() not in JUNK]
    if not files:
        raise fileops.Stop("빈 폴더")
    dst = inbox.free(base, taken, isdir=True)
    for f in files:
        rel = os.path.relpath(f, a).replace("\\", "/")
        fileops.op_cp(ctx, f, dst + "/" + rel, "받는 문", dup_ok=True, src_label=label(f), move=True, quiet=True, back=True)
    for d, _, names in os.walk(a, topdown=False):
        for n in names:
            if n.lower() in JUNK:
                try:
                    os.chmod(os.path.join(d, n), 0o666)
                    os.remove(os.path.join(d, n))
                except OSError:
                    pass
        try:
            os.rmdir(d)
        except OSError:
            pass
    return dst.rsplit("/", 1)[-1]


def reason(e):
    if isinstance(e, PermissionError) or "닫고 다시" in str(e):
        return "사용 중"
    return str(e)[:60] or e.__class__.__name__


# ── 정리 ──────────────────────────────────────

def fingerprint(a):
    """바뀌었는지 볼 지문 → [크기·개수, 늦은 시각]."""
    if os.path.isdir(a):
        n, latest = 0, os.path.getctime(a)
        for d, _, names in os.walk(a):
            for x in names:
                try:
                    st = os.stat(os.path.join(d, x))
                    n += 1
                    latest = max(latest, st.st_mtime, st.st_ctime)
                except OSError:
                    pass
        return [n, latest]
    st = os.stat(a)
    return [st.st_size, max(st.st_mtime, st.st_ctime)]


def names_in_inbox():
    """받은함 항목 — 튜토리얼 연습 파일은 뺀다(정리·본 기록 0 · 엔진이 바로 지움 · fileops.practice_paths)."""
    import fileops
    d = roles.abs("inbox")
    base, (tt, _) = roles.path("inbox"), fileops.practice_paths(VAULT)
    try:
        return sorted(n for n in os.listdir(d) if not n.startswith((".", "_")) and n.lower() not in JUNK and not fileops.in_practice(base + "/" + n, tt))
    except OSError:
        return []


def practice_put(a):
    """튜토리얼 연습 파일(볼트 밖 · 연습 장부에 적힌 것)을 우클릭·단축키로 넣음 → 받은함으로 그냥 옮기고 참(brain-base 0.46.4).
    장부 줄·장부 보기·정리·되돌리기 칸·알림을 남기지 않는다 — 엔진이 받은함에서 해시를 맞춰 바로 지운다(사용자 11-09 «로그에 안 남게»)."""
    import fileops
    _, out = fileops.practice_paths(VAULT)
    if os.path.normcase(os.path.abspath(a)) not in out or not os.path.isfile(a):
        return False
    dst = os.path.join(roles.abs("inbox"), os.path.basename(a))
    if os.path.exists(dst):
        return True     # 이미 넣음(엔진 것) — 같은 이름의 사람 파일이면 엔진이 이름을 바꿔 만든다
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.move(a, dst)
    return True


def mark_seen(names):
    seen = load(SEEN, {})
    d = roles.abs("inbox")
    for n in names:
        try:
            seen[n] = fingerprint(os.path.join(d, n))
        except OSError:
            pass
    save(SEEN, seen)


def fresh():
    """정리할 새 항목 — 본 적 없고 다 들어온 것(SETTLE 초 동안 안 바뀜) · 사라진 항목은 기억에서 뺀다."""
    names, seen, now = names_in_inbox(), load(SEEN, {}), time.time()
    keep = {n: seen[n] for n in names if n in seen}
    if len(keep) != len(seen):
        save(SEEN, keep)
    d = roles.abs("inbox")
    out = []
    for n in names:
        try:
            fp = fingerprint(os.path.join(d, n))
        except OSError:
            continue
        if keep.get(n) != fp and now - fp[1] >= SETTLE:
            out.append(n)
    return out


def vault_on():
    """옵시디언이 이 볼트를 열고 있나(시험 = DOOR_VAULT_ON)."""
    env = os.environ.get("DOOR_VAULT_ON")
    if env is not None:
        return env == "1"
    import fileops
    return bool(fileops.obsidian_cli(fileops.Ctx(VAULT, by=BY, dry=True)))


def settle(names):
    """확신 높은 것만 제자리로(inbox.py 와 같은 판단·같은 실행) → 줄들. 나머지는 받은함에 두고 다시 보지 않는다."""
    import fileops
    import inbox
    ctx = fileops.Ctx(VAULT, by=BY, dry=True)
    rows = []
    for n in names:
        try:
            rows.append(inbox.classify_one(n, ctx))
        except Exception:  # noqa: BLE001 — 하나가 깨져도 나머지는 정리
            log("판단 실패 %s\n%s" % (n, traceback.format_exc()))
    inbox.execute(rows, {r["name"] for r in rows if r["sure"] == "높음" and r["ops"]}, BY)
    mark_seen([r["name"] for r in rows if not r.get("moved") and r.get("tag") != "실패"])
    batch = batches([r["name"] for r in rows if r.get("moved")])
    for r in rows:
        r["batch"] = batch.get(r["name"])
    return rows


def batches(names):
    """방금 정리가 남긴 장부 묶음 — 되돌릴 때 쓴다."""
    if not names:
        return {}
    import fileops
    base = roles.path("inbox") + "/"
    out = {}
    for e in reversed(fileops.load_events(fileops.Ctx(VAULT, by=BY, dry=True))[-400:]):
        s = e.get("src", "")
        if e.get("op") in ("mv", "rm", "rmdir") and s.startswith(base):
            n = s[len(base):].split("/", 1)[0]
            if n in names and n not in out:
                out[n] = e.get("batch")
    return out


def where(r):
    """알림에 쓰는 자리 — 끝 두 칸."""
    if not r or not r.get("moved"):
        return "받은함"
    if r.get("act") == "버림":
        return "이미 있음" if r.get("dup") else "휴지통"
    d = (r.get("dst") or "").rsplit("/", 1)[0].split("/")
    return "/".join(d[-2:]) or "받은함"


def keep_undo(items):
    """되돌리기 칸 → 토큰 · 하루 지난 것은 지운다."""
    os.makedirs(UNDO, exist_ok=True)
    for x in os.listdir(UNDO):
        p = os.path.join(UNDO, x)
        try:
            if time.time() - os.path.getmtime(p) > 86400:
                os.remove(p)
        except OSError:
            pass
    token = secrets.token_hex(8)
    save(os.path.join(UNDO, token + ".json"), {"items": items})
    return token


def put(paths):
    import fileops
    import inbox
    paths = [p for p in paths if not practice_put(p)]     # 튜토리얼 연습 파일 — 장부·알림 없이 옮기기만
    if not paths:
        return 0
    with Lock():
        ctx = fileops.Ctx(VAULT, by=BY)
        got, bad, taken = [], [], set()
        for p in paths:
            a = os.path.abspath(p)
            why = refuse(a)
            if why:
                bad.append((os.path.basename(a.rstrip("\\/")), why))
                continue
            try:
                got.append({"name": bring(ctx, a, inbox, taken), "orig": a})
            except (fileops.Stop, OSError) as e:
                bad.append((os.path.basename(a.rstrip("\\/")), reason(e)))
        if ctx.events:
            fileops.write_view(ctx)
            print("묶음 %s — 되돌리기 = py -3 3_시스템/fileops.py undo %s (원래 자리로)" % (ctx.batch, ctx.batch))   # 11-28 · 알림 단추 밖의 되돌리기 길을 글에도
        rows = {r["name"]: r for r in settle([g["name"] for g in got])} if got and vault_on() else {}
    for g in got:
        r = rows.get(g["name"], {})
        g.update(dst=roles.path("inbox") + "/" + g["name"], batch=r.get("batch"), where=where(r))
    for name, why in bad:
        log("못 옮김 %s — %s" % (name, why))
    if len(got) == 1 and not bad:
        toast(got[0]["name"], got[0]["where"], keep_undo(got))
    elif got or len(bad) > 1:
        parts = {}
        for g in got:
            parts[g["where"]] = parts.get(g["where"], 0) + 1
        body = " · ".join("%s %d" % kv for kv in parts.items())
        if bad:
            body = (body + " · " if body else "") + "못 옮김 %d" % len(bad)
        toast("%d개" % (len(got) + len(bad)), body, keep_undo(got) if got else None)
    elif bad:
        toast(bad[0][0], "못 옮김 · " + bad[0][1])
    return 0 if got else 1


def recent():
    """내려받기에서 가장 최근에 받은 파일 하나 — 탐색기 밖에서 단축키를 눌렀을 때."""
    import outside
    best, when = None, 0
    now = time.time()
    for name, d in outside.places():
        if name != "내려받기":
            continue
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            try:
                if not e.is_file(follow_symlinks=False) or e.name.lower().endswith(NOT_RECENT) or e.name.startswith(("~", ".")):
                    continue
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            t = max(st.st_mtime, st.st_ctime)
            if st.st_size and t > when:
                best, when = e.path, t
    if not best or now - when > RECENT_MIN * 60:
        toast("방금 받은 파일 없음")
        return 1
    return put([best])


def sweep_work():
    """끝난 작업 비우기(work.py sweep · 볼트를 켤 때 함께) — 실패해도 받은함 정리는 돈다."""
    try:
        import work
        with Lock(wait=0):
            done = work.sweep()
    except Busy:
        return
    except Exception:  # noqa: BLE001
        log("작업 비우기 실패\n" + traceback.format_exc())
        return
    if done:
        items = [{"name": d["path"].rsplit("/", 1)[-1], "dst": d["path"], "batch": d["batch"], "orig": None} for d in done]
        toast("끝난 작업 비움", " · ".join(i["name"] for i in items), keep_undo(items))


def sweep():
    sweep_work()
    if not fresh():
        return 0
    try:
        with Lock(wait=0):
            rows = settle(fresh())
    except Busy:
        return 0
    moved = [r for r in rows if r.get("moved")]
    if moved:
        items = [{"name": r["name"], "dst": roles.path("inbox") + "/" + r["name"], "batch": r.get("batch"), "orig": None} for r in moved]
        if len(moved) == 1:
            toast(moved[0]["name"], where(moved[0]), keep_undo(items))
        else:
            toast("%d개" % len(moved), "제자리로", keep_undo(items))
    return 0


def undo(token):
    if not re.fullmatch(r"[0-9a-f]{16}", token or ""):
        return 1
    p = os.path.join(UNDO, token + ".json")
    rec = load(p, None)
    if not rec:
        toast("되돌리기 지남")
        return 1
    import fileops
    done, stay = [], []
    with Lock():
        ctx = fileops.Ctx(VAULT, by=BY)
        for it in rec["items"]:
            try:
                if it.get("batch"):
                    fileops.op_undo(ctx, it["batch"])
                if it.get("orig"):
                    a = ctx.abs(it["dst"])
                    back, k = it["orig"], 2
                    stem, ext = os.path.splitext(it["orig"])
                    while os.path.exists(back):
                        back, k = "%s %d%s" % (stem, k, ext), k + 1
                    os.makedirs(os.path.dirname(back), exist_ok=True)
                    shutil.move(a, back)
                    ctx.add("out", src=it["dst"], dst=label(back), why="되돌리기")
                else:
                    stay.append(it["name"])
                done.append(it["name"])
            except (fileops.Stop, OSError) as e:
                log("되돌리기 실패 %s — %s" % (it["name"], reason(e)))
        if ctx.events:
            fileops.write_view(ctx)
        mark_seen(stay)
    os.remove(p)
    toast("되돌림", done[0] if len(done) == 1 else "%d개" % len(done))
    return 0 if done else 1


# ── 등록 ──────────────────────────────────────

def powershell(script):
    enc = base64.b64encode(("[Console]::OutputEncoding=[Text.Encoding]::UTF8\n" + script).encode("utf-16-le")).decode()
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", enc], capture_output=True, encoding="utf-8",
                          errors="replace", creationflags=NO_WINDOW)


def lit(s):
    return "'" + s.replace("'", "''") + "'"


def set_keys(on):
    """이 사용자 레지스트리만(HKCU · 관리자 불필요) — 알림 이름 · brainbox: · Shift+우클릭 메뉴."""
    import winreg as w

    def put_key(path, **vals):
        with w.CreateKey(w.HKEY_CURRENT_USER, path) as k:
            for name, v in vals.items():
                w.SetValueEx(k, "" if name == "default" else name, 0, w.REG_SZ, v)

    def drop(path):
        with w.OpenKey(w.HKEY_CURRENT_USER, path, 0, w.KEY_READ | w.KEY_WRITE) as k:
            while True:
                try:
                    drop(path + "\\" + w.EnumKey(k, 0))
                except OSError:
                    break
        w.DeleteKey(w.HKEY_CURRENT_USER, path)

    c = r"Software\Classes"
    keys = [c + r"\AppUserModelId\\" + AUMID, c + r"\brainbox", c + "\\CLSID\\" + CLSID, c + r"\*\shell\BrainInbox", c + r"\Directory\shell\BrainInbox"]
    if not on:
        for k in keys:
            try:
                drop(k.replace("\\\\", "\\"))
            except OSError:
                pass
        return
    dll = os.path.join(APP, "brain-inbox-menu.dll")
    pyw = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "pyw.exe")
    put_key(keys[0].replace("\\\\", "\\"), DisplayName="외부뇌", IconUri=os.path.join(APP, "inbox.png"))
    put_key(keys[1], **{"default": "URL:brainbox", "URL Protocol": ""})
    put_key(keys[1] + r"\shell\open\command", default='"%s" -3 "%s" url "%%1"' % (pyw, os.path.abspath(__file__)))
    put_key(keys[2], default="BrainInbox")
    put_key(keys[2] + r"\InprocServer32", default=dll, ThreadingModel="Apartment")
    for k in keys[3:]:
        put_key(k, MUIVerb="외부뇌 받은함으로", Icon=dll + ",0", ExplorerCommandHandler=CLSID)


def write_cfg():
    """실행 파일 옆 설정 — 레지스트리·시작 메뉴를 건드리지 않는다."""
    py = shutil.which("py") or os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "py.exe")
    with open(os.path.join(APP, "door.cfg"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join([py, os.path.abspath(__file__), VAULT]) + "\n")


def pin_path():
    """왼쪽 즐겨찾기 = 받은함 진짜 자리"""
    return os.path.normpath(roles.abs("inbox"))


def release():
    """릴리스 첨부 표(door-app/release.json · 저장소에 실림) — {"판", "주소", "파일": [{"이름", "크기", "sha256"}]} · 없으면 None."""
    d = load(REL, None)
    return d if isinstance(d, dict) and isinstance(d.get("파일"), list) else None


def file_sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


def fetch(names, into=None, force=False):
    """없는 구동부를 릴리스 첨부에서 받는다 → (상태, 글).
    ok = 다 있다(이미 있던 것은 다시 받지 않고 건드리지 않는다) · none = 받을 표가 없다 · offline = 못 받았다(네트워크) · bad = 받았는데 적어 둔 값과 다르다(지웠다).
    받은 파일은 크기와 sha256 이 표와 같을 때만 제자리에 놓는다 — 서명 없는 실행 파일이라 저장소가 적어 둔 값이 유일한 확인이다."""
    import urllib.error
    import urllib.request
    into = into or APP
    need = [n for n in names if force or not os.path.exists(os.path.join(into, n))]
    if not need:
        return "ok", ""
    rel = release()
    table = {f.get("이름"): f for f in (rel or {}).get("파일", [])}
    if not rel or any(n not in table for n in need):
        return "none", "구동부 없음(%s) — 받을 곳을 적은 표(door-app/release.json)에도 없다" % ", ".join(need)
    base = (os.environ.get("DOOR_RELEASE") or rel.get("주소") or "").rstrip("/") + "/"
    os.makedirs(into, exist_ok=True)
    for n in need:
        tmp = os.path.join(into, n + ".part")
        try:
            with urllib.request.urlopen(base + n, timeout=30) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
        except (urllib.error.URLError, OSError, ValueError) as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            return "offline", "구동부를 못 받음(%s: %s)" % (n, reason_net(e))
        size, sha = os.path.getsize(tmp), file_sha(tmp)
        want = table[n]
        if size != want.get("크기") or sha != want.get("sha256"):
            os.remove(tmp)
            return "bad", "받은 %s 이 적어 둔 값과 다르다(크기 %s ↔ %s · sha256 %s… ↔ %s…) — 지웠고 깔지 않는다" % (
                n, size, want.get("크기"), sha[:12], str(want.get("sha256"))[:12])
        os.replace(tmp, os.path.join(into, n))
        log("받음 %s %s %s" % (n, rel.get("판"), sha[:12]))
    return "ok", "받음: %s(%s · sha256 확인)" % (", ".join(need), rel.get("판"))


def reason_net(e):
    return str(getattr(e, "reason", e))[:120]


LATER = "우클릭·단축키는 나중에(네트워크가 될 때 `py -3 3_시스템/door.py install` 다시) — 지금은 탐색기 왼쪽 «받은함» 즐겨찾기나 받은함 폴더로 끌어 넣으면 같다"


def pin_only():
    """구동부 없이도 되는 것 — 탐색기 왼쪽 즐겨찾기(받은함 진짜 자리)."""
    if os.environ.get("DOOR_NO_PIN"):  # 시험: 진짜 탐색기를 안 건드린다
        return None
    return powershell("""
$sh=New-Object -ComObject Shell.Application
$pin=%(pin)s
$qa=$sh.Namespace('shell:::{679f85cb-0220-4080-b29b-5540cc05aab6}')
if(-not ($qa.Items() | Where-Object { $_.Path -eq $pin })){ $sh.Namespace($pin).Self.InvokeVerb('pintohome') }
""" % {"pin": lit(pin_path())})


def state(probe=True):
    """받는 문의 세 상태 한 줄(바깥 설정 점검·안내가 읽는다 · 읽기만): 깔림 / 받을 수 있음 / 못 받음."""
    have = all(os.path.exists(os.path.join(APP, n)) for n in DRIVERS[:2])
    if have:
        print("구동부 있음 — " + ("깔림" if installed(quiet=True) == 0 else "아직 등록 전(py -3 3_시스템/door.py install)"))
        return 0
    rel = release()
    if not rel:
        print("못 받음 — 구동부도, 받을 곳을 적은 표도 없다 · 받은함 폴더로 끌어 넣기는 된다")
        return 1
    if probe:
        import urllib.error
        import urllib.request
        base = (os.environ.get("DOOR_RELEASE") or rel.get("주소") or "").rstrip("/") + "/"
        try:
            urllib.request.urlopen(urllib.request.Request(base + DRIVERS[0], method="HEAD"), timeout=8).close()
        except (urllib.error.URLError, OSError, ValueError) as e:
            print("못 받음(%s) — %s" % (reason_net(e), LATER))
            return 1
    print("받을 수 있음 — `py -3 3_시스템/door.py install` 이 릴리스 첨부(%s)에서 받아 sha256 을 확인하고 깐다" % rel.get("판"))
    return 0


def relhash(folder, tag, url):
    """출시 쪽: 그 폴더의 구동부 셋으로 release.json 을 다시 쓴다(판 꼬리표·주소·크기·sha256)."""
    files = []
    for n in DRIVERS:
        p = os.path.join(folder, n)
        files.append({"이름": n, "크기": os.path.getsize(p), "sha256": file_sha(p)})
    with open(REL, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"판": tag, "주소": url.rstrip("/") + "/", "파일": files}, f, ensure_ascii=False, indent=1)
        f.write("\n")
    for x in files:
        print("%s %d %s" % (x["이름"], x["크기"], x["sha256"]))
    return 0


def relcheck():
    """출시 쪽: release.json 이 가리키는 첨부를 실제로 받아 크기·sha256 이 맞는지(임시 폴더 · 볼트 것은 안 건드림) — 종료 0 = 맞음."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        st, msg = fetch(DRIVERS, into=td, force=True)
    rel = release() or {}
    print("%s — %s %s" % ("맞음" if st == "ok" else "안 맞음(%s)" % st, rel.get("판"), msg))
    return 0 if st == "ok" else 1


def win11():
    """윈도 11(빌드 22000 이상) — 우클릭 첫 메뉴가 «현대 메뉴»라 옛 레지스트리 동사는 «더 많은 옵션 표시» 안으로 숨는다."""
    try:
        return sys.getwindowsversion().build >= 22000
    except AttributeError:
        return False


def menu_pkg():
    """첫 메뉴 꾸러미(BrainInbox.Menu)가 이 사용자에게 등록됐나."""
    r = powershell("if (Get-AppxPackage -Name 'BrainInbox.Menu') { 'yes' } else { 'no' }")
    return r.stdout.strip().endswith("yes")


def install(with_menu=True):
    exe = os.path.join(APP, "brain-key.exe")
    st, msg = fetch(DRIVERS[:2])
    if msg:
        print(msg)
    if st == "bad":
        return 1
    if st != "ok":
        # 구동부를 못 받았다 — 실패로 끝내지 않는다: 구동부 없이 되는 즐겨찾기만 넣고 바르게 안내한다
        pin_only()
        mark_seen(names_in_inbox())
        print(LATER)
        return 0
    write_cfg()
    set_keys(True)
    ps = """
$ErrorActionPreference='Stop'
$sh=New-Object -ComObject Shell.Application
$ws=New-Object -ComObject WScript.Shell
$pin=%(pin)s; $exe=%(exe)s
$qa=$sh.Namespace('shell:::{679f85cb-0220-4080-b29b-5540cc05aab6}')
if(-not ($qa.Items() | Where-Object { $_.Path -eq $pin })){ $sh.Namespace($pin).Self.InvokeVerb('pintohome') }
$s=$ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Programs')) '외부뇌 받은함.lnk'))
$s.TargetPath=$exe; $s.Hotkey=%(hotkey)s; $s.IconLocation=$exe+',0'; $s.Description='외부뇌 받은함으로'; $s.Save()
$s=$ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('SendTo')) '외부뇌 받은함.lnk'))
$s.TargetPath=$exe; $s.IconLocation=$exe+',0'; $s.Description='외부뇌 받은함으로'; $s.Save()
""" % {"pin": lit(pin_path()), "exe": lit(exe), "hotkey": lit(HOTKEY)}
    r = powershell(ps)
    if r.returncode != 0:
        print("등록 실패:\n" + (r.stderr or r.stdout)[-1500:])
        return 1
    mark_seen(names_in_inbox())     # 지금 받은함에 있는 것은 사람이 볼 것 — 새로 든 것만 정리한다
    if with_menu and win11() and not menu_pkg():
        # 윈도 11 은 첫 메뉴가 따로다 — 안 넣으면 «우클릭 › 더 많은 옵션 › 보내기» 에만 뜬다(11-27 빈 윈도 · 사용자 «우클릭하자마자 뜨게»).
        # 윈도가 관리자 확인을 한 번 묻는다(사람이 «예»). 빼려면 install --no-menu · 나중에 menu.
        print("첫 우클릭 메뉴 넣기 — 윈도의 관리자 확인 창에서 «예»")
        return menu()
    return status()


def remove():
    set_keys(False)
    ps = """
$sh=New-Object -ComObject Shell.Application
$pin=%(pin)s
$qa=$sh.Namespace('shell:::{679f85cb-0220-4080-b29b-5540cc05aab6}')
foreach($it in $qa.Items()){ if($it.Path -eq $pin){ $it.InvokeVerb('unpinfromhome') } }
foreach($d in 'Programs','SendTo'){ $l=Join-Path ([Environment]::GetFolderPath($d)) '외부뇌 받은함.lnk'; if(Test-Path -LiteralPath $l){ Remove-Item -LiteralPath $l } }
""" % {"pin": lit(pin_path())}
    r = powershell(ps)
    print("지움" if r.returncode == 0 else "일부 실패:\n" + r.stderr[-800:])
    return status()


def status():
    r = powershell("""
$sh=New-Object -ComObject Shell.Application
$pin=%(pin)s
'즐겨찾기 ' + [bool]($sh.Namespace('shell:::{679f85cb-0220-4080-b29b-5540cc05aab6}').Items() | Where-Object { $_.Path -eq $pin })
$l=Join-Path ([Environment]::GetFolderPath('Programs')) '외부뇌 받은함.lnk'
'단축키 ' + $(if(Test-Path -LiteralPath $l){ (New-Object -ComObject WScript.Shell).CreateShortcut($l).Hotkey } else { 'False' })
'첫 메뉴 패키지 ' + [bool](Get-AppxPackage -Name 'BrainInbox.Menu')
""" % {"pin": lit(pin_path())})
    print(r.stdout.strip())
    print("구동부 %s %s" % (os.path.exists(os.path.join(APP, "brain-key.exe")), APP))
    import winreg as w
    try:
        w.CloseKey(w.OpenKey(w.HKEY_CURRENT_USER, r"Software\Classes\*\shell\BrainInbox"))
        print("Shift+우클릭 True")
    except OSError:
        print("Shift+우클릭 False")
    return 0


def installed(quiet=False):
    """이 볼트의 받는 문이 등록됐나(바깥 설정 점검이 부름 · 읽기만) — 종료 0 = 됨 · 1 = 안 됨.
    됨 = 구동부 파일이 있고, 이 사용자 레지스트리의 우클릭 처리기가 «이 볼트»의 구동부를 가리킨다(다른 볼트가 등록한 것은 안 됨으로 센다)."""
    import winreg as w
    say = (lambda s: None) if quiet else print
    dll = os.path.join(APP, "brain-inbox-menu.dll")
    if not (os.path.exists(os.path.join(APP, "brain-key.exe")) and os.path.exists(dll)):
        say("안 됨 — 구동부 없음(door.py install 이 릴리스 첨부에서 받는다 · 받을 수 있나 = door.py state) " + APP)
        return 1
    try:
        with w.OpenKey(w.HKEY_CURRENT_USER, "Software\\Classes\\CLSID\\" + CLSID + "\\InprocServer32") as k:
            reg = w.QueryValueEx(k, "")[0]
    except OSError:
        say("안 됨 — 등록 없음(door.py install)")
        return 1
    if os.path.normcase(os.path.normpath(reg)) != os.path.normcase(os.path.normpath(dll)):
        say("안 됨 — 다른 볼트가 등록함 " + reg)
        return 1
    if win11() and not menu_pkg():
        say("안 됨 — 윈도 11 첫 우클릭 메뉴 없음(지금은 «더 많은 옵션 › 보내기» 에만 · door.py menu · 관리자 확인 1번)")
        return 1
    say("됨")
    return 0


def menu(drop=False):
    """탐색기 첫 우클릭 메뉴(Shift 없이 «외부뇌 받은함으로») — 윈도가 관리자 확인을 한 번 묻는다(사람이 «예»). 결과 = door-app/install-menu.log."""
    ps1 = os.path.join(APP, "install-menu.ps1")
    if not os.path.exists(ps1):
        print("없음: %s" % ps1)
        return 1
    if not drop:
        st, msg = fetch(DRIVERS)
        if msg:
            print(msg)
        if st == "bad":
            return 1
        if st != "ok":
            print(LATER)
            return 0
    r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1] + (["-Remove"] if drop else []),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print((r.stdout or r.stderr).strip()[-600:])
    return status()


def main(argv=None):
    a = list(sys.argv[1:] if argv is None else argv)
    cmd = a.pop(0) if a else ""
    try:
        if cmd == "put":
            return put(a)
        if cmd == "list":
            with open(a[0], encoding="utf-8") as f:
                paths = [x.strip() for x in f if x.strip()]
            try:
                os.remove(a[0])
            except OSError:
                pass
            return put(paths)
        if cmd == "recent":
            return recent()
        if cmd == "sweep":
            return sweep()
        if cmd == "undo":
            return undo(a[0] if a else "")
        if cmd == "url":
            m = re.fullmatch(r"brainbox:undo/([0-9a-f]{16})/?", a[0] if a else "")
            if m:
                hidden("undo", m.group(1))
            return 0
        if cmd == "cfg":
            write_cfg()
            return 0
        if cmd == "install":
            return install("--no-menu" not in a)
        if cmd == "remove":
            return remove()
        if cmd == "status":
            return status()
        if cmd == "installed":
            return installed()
        if cmd == "state":
            return state("--no-probe" not in a)
        if cmd == "relhash":
            return relhash(a[0], a[1], a[2])
        if cmd == "relcheck":
            return relcheck()
        if cmd == "menu":
            return menu("--remove" in a)
    except Busy:
        toast("잠시 뒤 다시", "다른 정리가 도는 중")
        return 1
    except Exception:  # noqa: BLE001 — 창이 없어 여기서 막지 않으면 사람이 아무것도 못 본다
        log("오류 %s\n%s" % (cmd, traceback.format_exc()))
        toast("받는 문 오류", traceback.format_exc().strip().splitlines()[-1][:80])
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
