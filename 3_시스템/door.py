# -*- coding: utf-8 -*-
"""**받는 문** — 볼트 밖 파일을 받은함으로 «옮긴다»(2026-11-03).

왜: 받은함에 넣으려면 옵시디언을 켜고 끌어 넣어야 했고, 복사라 원래 파일을 또 지워야 했다 — 폴더에 직접 넣는 것과 다를 게 없었다.
문 셋(우클릭 메뉴 · 단축키 · 탐색기 왼쪽 즐겨찾기)이 이 엔진 하나로 들어온다. 정리(inbox.py · 확신 높음만 제자리로)는 볼트가 켜져 있을 때만 한다
(11-03 «볼트를 켜면 그때 · 예약 필요 없음») — 켜져 있으면 넣자마자 · 꺼져 있으면 받은함에서 기다렸다 brain-base 가 켤 때 sweep 을 부른다.
우클릭·단축키·즐겨찾기 등록에 쓰는 작은 실행 파일은 볼트 밖 빌더에서 만들며 배포판에는 없다(자리 = `DOOR_APP`). 없어도 put·list·recent·sweep·undo 는 돈다.

  py -3 3_시스템/door.py put <경로...>      옮김(볼트가 켜져 있으면 바로 정리)
  py -3 3_시스템/door.py list <목록 파일>    우클릭·단축키가 부른다(줄마다 경로 · 읽고 지움)
  py -3 3_시스템/door.py recent             내려받기에서 방금 받은 파일 하나
  py -3 3_시스템/door.py sweep              받은함에 새로 든 것 정리(brain-base 가 켤 때 · 켜진 동안 받은함에 새로 들 때)
  py -3 3_시스템/door.py undo <토큰>         알림의 되돌리기(원래 자리로)
  py -3 3_시스템/door.py install | remove | status   즐겨찾기·단축키·보내기·알림·Shift+우클릭 등록·해제·확인(지속 설정 — 사람이 승인)

장부에는 «내려받기/이름»만 적는다(outside.py 와 같음). 원래 자리 절대 경로는 되돌리기 칸(`_index/door/undo` · git 밖 · 하루)에만 둔다.
"""
import base64
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
APP = os.environ.get("DOOR_APP") or r"C:\brain-inbox\app"
PIN = os.path.join(os.path.dirname(APP), "받은함")  # 즐겨찾기에 «받은함»으로 보이게 — 받은함을 가리키는 연결(junction)
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
        fileops.op_cp(ctx, a, dst, "받는 문", dup_ok=True, src_label=label(a), move=True, quiet=True)
        return dst.rsplit("/", 1)[-1]
    files = [f for f in fileops.files_under(a) if os.path.basename(f).lower() not in JUNK]
    if not files:
        raise fileops.Stop("빈 폴더")
    dst = inbox.free(base, taken, isdir=True)
    for f in files:
        rel = os.path.relpath(f, a).replace("\\", "/")
        fileops.op_cp(ctx, f, dst + "/" + rel, "받는 문", dup_ok=True, src_label=label(f), move=True, quiet=True)
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
    d = roles.abs("inbox")
    try:
        return sorted(n for n in os.listdir(d) if not n.startswith((".", "_")) and n.lower() not in JUNK)
    except OSError:
        return []


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


def sweep():
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
        put_key(k, MUIVerb="받은함으로", Icon=dll + ",0", ExplorerCommandHandler=CLSID)


def write_cfg():
    """실행 파일 옆 설정(README 없는 빌더 산출 칸) — 레지스트리·시작 메뉴를 건드리지 않는다."""
    py = shutil.which("py") or os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "py.exe")
    with open(os.path.join(APP, "door.cfg"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join([py, os.path.abspath(__file__), VAULT]) + "\n")


def install():
    exe = os.path.join(APP, "brain-key.exe")
    if not os.path.exists(exe):
        print("없음: %s — 이 판에는 실행 파일이 없다. 받은함 폴더에 직접 넣어도 같다" % exe)
        return 1
    write_cfg()
    set_keys(True)
    ps = """
$ErrorActionPreference='Stop'
$sh=New-Object -ComObject Shell.Application
$ws=New-Object -ComObject WScript.Shell
$pin=%(pin)s; $inbox=%(inbox)s; $exe=%(exe)s
if(-not (Test-Path -LiteralPath $pin)){ New-Item -ItemType Junction -Path $pin -Target $inbox | Out-Null }
$qa=$sh.Namespace('shell:::{679f85cb-0220-4080-b29b-5540cc05aab6}')
if(-not ($qa.Items() | Where-Object { $_.Path -eq $pin })){ $sh.Namespace($pin).Self.InvokeVerb('pintohome') }
$s=$ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Programs')) '외부뇌 받은함.lnk'))
$s.TargetPath=$exe; $s.Hotkey=%(hotkey)s; $s.IconLocation=$exe+',0'; $s.Description='받은함으로'; $s.Save()
$s=$ws.CreateShortcut((Join-Path ([Environment]::GetFolderPath('SendTo')) '외부뇌 받은함.lnk'))
$s.TargetPath=$exe; $s.IconLocation=$exe+',0'; $s.Description='받은함으로'; $s.Save()
""" % {"pin": lit(PIN), "inbox": lit(roles.abs("inbox")), "exe": lit(exe), "hotkey": lit(HOTKEY)}
    r = powershell(ps)
    if r.returncode != 0:
        print("등록 실패:\n" + (r.stderr or r.stdout)[-1500:])
        return 1
    mark_seen(names_in_inbox())     # 지금 받은함에 있는 것은 사람이 볼 것 — 새로 든 것만 정리한다
    return status()


def remove():
    set_keys(False)
    ps = """
$sh=New-Object -ComObject Shell.Application
$pin=%(pin)s
$qa=$sh.Namespace('shell:::{679f85cb-0220-4080-b29b-5540cc05aab6}')
foreach($it in $qa.Items()){ if($it.Path -eq $pin){ $it.InvokeVerb('unpinfromhome') } }
if(Test-Path -LiteralPath $pin){ [IO.Directory]::Delete($pin) }
foreach($d in 'Programs','SendTo'){ $l=Join-Path ([Environment]::GetFolderPath($d)) '외부뇌 받은함.lnk'; if(Test-Path -LiteralPath $l){ Remove-Item -LiteralPath $l } }
""" % {"pin": lit(PIN)}
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
""" % {"pin": lit(PIN)})
    print(r.stdout.strip())
    import winreg as w
    try:
        w.CloseKey(w.OpenKey(w.HKEY_CURRENT_USER, r"Software\Classes\*\shell\BrainInbox"))
        print("Shift+우클릭 True")
    except OSError:
        print("Shift+우클릭 False")
    return 0


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
            return install()
        if cmd == "remove":
            return remove()
        if cmd == "status":
            return status()
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
