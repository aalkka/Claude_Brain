#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""자동 재시작 — 정한 시각에 «끌 수 있는지» 재고, 되면 다시 시작하고, 로그인 뒤 모듈마다 선언한 것을 다시 띄운다.

왜(11-20 사용자): 모바일을 쓰려고 PC 를 끄지 않고 절전으로 두는데, 켜 둔 날이 길어지면 끄고 싶어진다(메모리·업데이트).
무턱대고 끄면 쓰는 중인 사람·Claude·프로그램이 끊기고, 끈 뒤에는 폰이 닿을 길(서버·RC·옵시디언)이 안 뜬다.
설계 = 제작자 설계 노트(배포판 미포함)

  py -3 3_시스템/restart.py check [--json] [--fake 사실.json]   지금 끌 수 있나(끔 · 미룸 + 까닭) · 읽기만
  py -3 3_시스템/restart.py tick [--dry] [--fake 사실.json] [--now HH:MM]   예약 작업이 부름 · 시각·마감·하루 한 번을 보고 되면 재시작
  py -3 3_시스템/restart.py after [--dry]     로그온 예약 작업이 부름 · 재시작 기록이 있으면 선언한 것을 다시 띄우고 잰다
  py -3 3_시스템/restart.py plan              재시작 뒤 할 일 목록(본체 + 켜진 모듈 · 지금 떠 있나)
  py -3 3_시스템/restart.py status            설정 · 오늘 상태 · 최근 기록
  py -3 3_시스템/restart.py install [--print] | remove   예약 작업 둘(«외부뇌 자동 재시작» · «외부뇌 재시작 뒤») — 사람이 허락

판단(끄지 않는 쪽으로 기움 · 하나라도 «미룸»이나 «모름»이면 끄지 않음):
  사람   마지막 입력 · 전체 화면/발표 · 소리 재생 · (잠금이면 입력 문턱을 짧게)
  Claude 세션 장부 busy · 최근 일함(문턱) · 설정 claude_open=any 면 열린 세션만 있어도 미룸
  프로그램 볼트 장부(own.py)의 살아 있는 일 · 시험 잠금 · GPU 일(gpu_guard) · CPU/디스크/망으로 «일함» · 설치·Windows 업데이트 ·
         받는 중인 파일 · 저장 안 된 창(제목 표시) · 문서 앱 창 · 배터리
  «헛돎» = 문턱 아래이거나 own.py 가 되찾을 것(주인 끝남·시험 잔재·주인 오래 쉼) · spin_ok 이름 — 막지 않는다.
재시작 = `shutdown /g /t 60` (Windows 자동 재시작 로그인 ARSO 가 켜져 있으면 로그인하고 잠금 · 등록된 앱 다시 켬 · 60초 안 `shutdown /a` 로 취소).
다시 세팅 = 본체 3_시스템/after_restart.json + 켜진 모듈 module.json contributes.after_restart(파일 경로) — 항목마다 was(그때 떠 있었나) ·
         check(떴나) · run(띄우기) · grace(Windows 가 스스로 띄울 때까지 기다림) · wait_s.
⛔ 시험은 --fake·--dry 로만 한다. 실제 재시작은 설정 on 이 켜져 있고 --dry 가 없을 때만 나간다.
"""
import argparse
import ctypes
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
DIR = os.path.join(HERE, "_index", "restart")
STATE = os.path.join(DIR, "state.json")        # 오늘 상태 {day, status, holds, last}
BEFORE = os.path.join(DIR, "before.json")      # 재시작 직전 기록(after 가 읽고 last-before.json 으로 옮김)
AFTER = os.path.join(DIR, "after.json")        # 마지막 다시 세팅 결과
LOG = os.path.join(DIR, "log.jsonl")
LOCAL = os.path.join(HERE, "restart.local.json")
CORE_DECL = os.path.join(HERE, "after_restart.json")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
TASK, TASK_AFTER = "외부뇌 자동 재시작", "외부뇌 재시작 뒤"

# 설정(기능마다 따로 — options 칸이 생기면 restart.auto · restart.relaunch · restart.notify 로 · 지금은 이 값 위에 restart.local.json)
DEFAULTS = {
    "on": False,              # restart.auto 켬/끔 — 기능 단계가 덮어씀 · 예약을 넣어야 돎
    "at": "05:00",            # 재기 시작 시각
    "retry_min": 15,          # 미루면 몇 분마다 다시
    "deadline": "06:30",      # 넘으면 그날 건너뜀 + 알림(이른 아침 수집 전 · 사용자 11-20 «추천»)
    "min_uptime_h": 12,       # 켜진 지 이보다 짧으면 그날 건너뜀(이미 새로 켜짐)
    "user_idle_min": 30,      # 마지막 입력이 이보다 가까우면 미룸
    "locked_idle_min": 3,     # 잠겨 있으면 이 문턱(잠금 화면에서 암호를 치는 중일 수 있음)
    "claude_idle_min": 20,    # Claude 세션이 이보다 가깝게 일했으면 미룸
    "claude_open": "idle",    # idle = 쉬는 세션은 끊고 재시작 · any = 열린 세션이 하나라도 있으면 미룸
    "sample_s": 20,           # CPU·디스크·망을 재는 시간
    "cpu_core": 0.25,         # 이 넘게 먹으면 «돎»
    "io_kbs": 1024,           # 디스크 입출력 이 넘으면 «일함»
    "net_kbs": 512,           # 망 받기·보내기 이 넘으면 «일함»(누가인지는 모름)
    "gpu_util": 5.0,          # 외장 GPU 사용률 이 넘으면 «일함»
    "hold_on_battery": True,  # 배터리면 미룸(밖에서 쓰는 중)
    "spin_ok": [],            # 돌아도 막지 않을 이름(헛도는 것으로 잰 것만)
    "cpu_ok": ["crossdeviceservice.exe"],   # CPU 만으로는 막지 않을 배경 동기화 — 디스크를 쓰면(파일 전송) 막음
                              # (11-20 잼: «휴대폰과 연결» 쉴 때 3분 평균 0.002코어 · 17:10 한 번 0.28코어로 몰아서 일함 = 헛돎 아님 · 끊어도 다시 동기화)
    "doc_apps": ["winword.exe", "excel.exe", "powerpnt.exe", "hwp.exe", "hword.exe", "hcell.exe", "hshow.exe"],
    "relaunch": True,         # restart.relaunch — 로그인 뒤 다시 띄움
    "notify": True,           # restart.notify — 건너뜀·실패를 폰으로(mobility 가 있을 때)
    "notify_ok": False,       # 다 떴을 때도 알림
}
FEATURES = {"on": "restart.auto", "relaunch": "restart.relaunch", "notify": "restart.notify"}

UPDATE = re.compile(r"^(tiworker|trustedinstaller|mousocoreworker|wuauclt|usoclient|dism|dismhost|setuphost|windows10upgraderapp)\.exe$", re.I)
INSTALL = re.compile(r"(^|[-_ .])(setup|install|installer|unins\d*|winget|choco)[^\\/]*\.exe$|^msiexec\.exe$", re.I)
RESIDENT = re.compile(r"^(claude|explorer|dwm|csrss|winlogon|lsass|services|smss|system|registry|idle|svchost|conhost|openconsole|"
                      r"windowsterminal|msmpeng|nissrv|searchindexer|audiodg|fontdrvhost|tailscaled|tailscale-ipn|"
                      r"memcompression|securityhealthservice|mpdefendercoreservice)\.exe$|^(system|registry|idle|memory compression)$", re.I)
DIRTY = re.compile(r"^\*|\*\s*$|\*\s+[-–—]\s|●|\(수정됨\)|수정됨\s*[-–—]|저장되지 않|\bunsaved\b|\[modified\]", re.I)
PARTIAL = ("*.crdownload", "*.part", "*.partial", "*.download", "*.!ut", "*.opdownload")


# ── 설정 ──────────────────────────────────────────────────────────────────
def cfg():
    c = json.loads(json.dumps(DEFAULTS))
    try:
        sys.path.insert(0, HERE)
        import options
        for k, fid in FEATURES.items():
            try:
                if not options.declarations(VAULT, only=fid):   # 칸이 없으면 level 이 "high"(켬)를 돌려준다 — 기본값을 지킴
                    continue
                lv = options.level(fid)
            except Exception:  # noqa: BLE001 — 칸이 아직 없음
                continue
            c[k] = lv != "off"
            try:
                c.update({a: b for a, b in (options.params(fid, lv) or {}).items() if a in DEFAULTS})
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        pass
    try:
        with open(LOCAL, encoding="utf-8") as h:
            loc = json.load(h)
        if isinstance(loc, dict):
            c.update({k: v for k, v in loc.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return c


def _hm(s):
    h, m = (int(x) for x in str(s).split(":"))
    return h * 60 + m


# ── 사실 재기(하나라도 못 재면 None = 모름) ───────────────────────────────
class LASTINPUT(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_uint), ("t", ctypes.c_uint)]


def user_idle_s():
    try:
        li = LASTINPUT(ctypes.sizeof(LASTINPUT), 0)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li)):
            return None
        return ((ctypes.windll.kernel32.GetTickCount() - li.t) & 0xFFFFFFFF) / 1000
    except Exception:  # noqa: BLE001
        return None


def notif_state():
    """SHQueryUserNotificationState — 2 바쁨(전체 화면) · 3 D3D 전체 화면 · 4 발표 · 5 받음 · 7 앱(Win8+ 몰입) · 1 아님"""
    try:
        v = ctypes.c_int()
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(v)) != 0:
            return None
        return v.value
    except Exception:  # noqa: BLE001
        return None


def locked(names):
    """잠금 화면이 떠 있나 — LogonUI.exe 가 있으면 잠김(로그인 화면 포함)"""
    return "logonui.exe" in names


class GUID(ctypes.Structure):
    _fields_ = [("a", ctypes.c_uint32), ("b", ctypes.c_uint16), ("c", ctypes.c_uint16), ("d", ctypes.c_ubyte * 8)]

    def __init__(self, s):
        super().__init__()
        ctypes.oledll.ole32.CLSIDFromString(ctypes.c_wchar_p(s), ctypes.byref(self))


def _vfn(obj, idx, *argtypes):
    vt = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)(vt[idx])


def audio_playing(samples=10, gap=0.2):
    """기본 재생 장치의 소리 크기(IAudioMeterInformation · 모든 앱 합) — 재생 중 True · 장치 없음 False · 못 잼 None"""
    held = []
    try:
        ole = ctypes.windll.ole32
        ole.CoInitializeEx(None, 0)
        en = ctypes.c_void_p()
        hr = ole.CoCreateInstance(ctypes.byref(GUID("{BCDE0395-E52F-467C-8E3D-C4579291692E}")), None, 23,
                                  ctypes.byref(GUID("{A95664D2-9614-4F35-A746-DE8DB63617E6}")), ctypes.byref(en))
        if hr != 0:
            return None
        held.append(en)
        dev = ctypes.c_void_p()
        hr = _vfn(en, 4, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(en, 0, 0, ctypes.byref(dev))
        if hr & 0xFFFFFFFF == 0x80070490:      # 재생 장치 없음
            return False
        if hr != 0:
            return None
        held.append(dev)
        met = ctypes.c_void_p()
        hr = _vfn(dev, 3, ctypes.POINTER(GUID), ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(
            dev, ctypes.byref(GUID("{C02216F6-8C67-4B5B-9D00-D008E73E0064}")), 23, None, ctypes.byref(met))
        if hr != 0:
            return None
        held.append(met)
        get = _vfn(met, 3, ctypes.POINTER(ctypes.c_float))
        peak = 0.0
        for _ in range(samples):
            f = ctypes.c_float()
            if get(met, ctypes.byref(f)) != 0:
                return None
            peak = max(peak, f.value)
            time.sleep(gap)
        return peak > 0.0005
    except Exception:  # noqa: BLE001
        return None
    finally:
        for o in reversed(held):
            try:
                _vfn(o, 2)(o)
            except Exception:  # noqa: BLE001
                pass


def windows():
    """[(pid, 제목)] 보이는 창"""
    out = []
    try:
        from ctypes import wintypes
        u = ctypes.windll.user32

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def cb(h, _):
            if u.IsWindowVisible(h):
                n = u.GetWindowTextLengthW(h)
                if n:
                    b = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(h, b, n + 1)
                    p = wintypes.DWORD()
                    u.GetWindowThreadProcessId(h, ctypes.byref(p))
                    out.append((p.value, b.value))
            return True
        u.EnumWindows(cb, 0)
    except Exception:  # noqa: BLE001
        return None
    return out


def _own():
    sys.path.insert(0, HERE)
    import own
    return own


def _gpu_guard():
    """외장 GPU 재기(find_dgpu·dstate·gpu_time) — gpu_guard 모듈 · 없으면 새 이름 self_sleep 의 dgpu.py · 둘 다 없으면 None"""
    import importlib.util
    for mod, f in (("gpu_guard", "gpu_guard.py"), ("self_sleep", "dgpu.py")):
        p = os.path.join(VAULT, ".claude", "skills", mod, "scripts", f)
        if os.path.isfile(p):
            sys.path.insert(0, os.path.dirname(p))
            spec = importlib.util.spec_from_file_location("_restart_dgpu_" + mod, p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            if all(hasattr(m, x) for x in ("find_dgpu", "dstate", "gpu_time")):
                return m
    return None


def gpu_busy(c, span):
    """외장 GPU 를 일로 쓰는 프로세스 [(이름, 사용률)] · 외장 GPU 없음·꺼짐(D3) = [] · 못 잼 None. 깨우지 않음(D0 일 때만 잼)."""
    try:
        g = _gpu_guard()
        if not g:
            return []
        inst = g.find_dgpu()
        if not inst or g.dstate(inst) != "D0":
            return []
        import psutil
        t0, a = time.time(), g.gpu_time()
        time.sleep(max(2, min(span, 10)))
        t1, b = time.time(), g.gpu_time()
        use = {}
        for k, v in b.items():
            if k in a:
                use[k[0]] = max(use.get(k[0], 0), (v - a[k]) / ((t1 - t0) * 1e7) * 100)
        out = []
        for pid, u in use.items():
            if u >= c["gpu_util"]:
                try:
                    out.append((psutil.Process(pid).name(), round(u, 1)))
                except Exception:  # noqa: BLE001
                    out.append(("pid %d" % pid, round(u, 1)))
        return out
    except Exception:  # noqa: BLE001
        return None


def partial_files(now):
    d = os.path.join(os.path.expanduser("~"), "Downloads")
    out = []
    for pat in PARTIAL:
        for f in glob.glob(os.path.join(d, pat)):
            try:
                if now - os.path.getmtime(f) < 300:
                    out.append(os.path.basename(f))
            except OSError:
                pass
    return out


def gather(c):
    """지금 사실 — judge 가 읽는 꼴(시험은 같은 꼴의 가짜 사실을 준다)"""
    import psutil
    now = time.time()
    me = {os.getpid(), os.getppid()}
    f = {"t": now, "boot": psutil.boot_time()}
    procs = {}
    for p in psutil.process_iter(["name", "exe", "cmdline", "ppid", "create_time"]):
        procs[p.pid] = p
    names = {(p.info["name"] or "").lower() for p in procs.values()}
    f["user"] = {"idle_s": user_idle_s(), "notif": notif_state(), "locked": locked(names), "audio": audio_playing()}
    # Claude
    try:
        own = _own()
        sess = own.sessions()
        f["claude"] = [{"name": s["name"], "short": s["short"], "busy": s["busy"], "idle_min": (now - s["last"]) / 60 if s["last"] else None}
                       for s in sess.values() if s["alive"]]
        # own.py 판정: 되찾을 것 = 헛돎 · 장부에서 살아 있는 일
        kill, _rows, _m = own.judge()
        f["reclaim"] = sorted({k[0] for k in kill})
        f["ledger"] = [{"pid": pid, "kind": e.get("kind", ""), "cmd": (e.get("cmd") or "")[:80]} for pid, e in own.ledger().items()]
        f["heavy_lock"] = bool(own.heavy_locked())
    except Exception as e:  # noqa: BLE001
        f["claude"] = f["reclaim"] = f["ledger"] = f["heavy_lock"] = None
        f["own_err"] = str(e)[:120]
    # CPU·디스크·망
    t0, cpu0, io0 = time.time(), {}, {}
    for pid, p in procs.items():
        try:
            cpu0[pid] = sum(p.cpu_times()[:2])
            k = p.io_counters()
            io0[pid] = k.read_bytes + k.write_bytes
        except Exception:  # noqa: BLE001
            pass
    try:
        n0 = psutil.net_io_counters()
    except Exception:  # noqa: BLE001
        n0 = None
    f["gpu"] = gpu_busy(c, c["sample_s"])
    rest = c["sample_s"] - (time.time() - t0)
    if rest > 0:
        time.sleep(rest)
    span = time.time() - t0
    rows = []
    for pid, p in procs.items():
        if pid in me or pid in (0, 4) or pid not in cpu0:   # 0 = 쉬는 시간(System Idle) · 4 = System
            continue
        try:
            cpu = (sum(p.cpu_times()[:2]) - cpu0[pid]) / span
            k = p.io_counters()
            io = (k.read_bytes + k.write_bytes - io0.get(pid, 0)) / span / 1024
            cmd = " ".join(p.info["cmdline"] or [])
        except Exception:  # noqa: BLE001
            continue
        rows.append({"pid": pid, "name": p.info["name"] or "", "exe": p.info["exe"] or "", "cmd": cmd[:200],
                     "core": round(cpu, 3), "io_kbs": round(io, 1)})
    f["procs"] = rows
    try:
        n1 = psutil.net_io_counters()
        f["net_kbs"] = round(((n1.bytes_recv - n0.bytes_recv) + (n1.bytes_sent - n0.bytes_sent)) / span / 1024, 1) if n0 else None
    except Exception:  # noqa: BLE001
        f["net_kbs"] = None
    w = windows()
    f["windows"] = None if w is None else [{"pid": pid, "name": (procs[pid].info["name"] or "") if pid in procs else "", "title": t[:120]} for pid, t in w]
    f["partial"] = partial_files(now)
    try:
        b = psutil.sensors_battery()
        f["battery"] = None if b is None else (not b.power_plugged)
    except Exception:  # noqa: BLE001
        f["battery"] = None
    return f


# ── 판정(순수 — 사실과 설정만 봄) ─────────────────────────────────────────
def _sysdir(exe):
    w = os.path.normcase(os.environ.get("SystemRoot", r"C:\Windows"))
    return os.path.normcase(exe or "").startswith(w + os.sep)


def judge(f, c):
    """(«끔»|«미룸», [(갈래, 까닭)]) — 미룸 까닭이 하나라도 있으면 미룸 · 못 잰 것도 미룸(«모름»)"""
    hold = []

    def unk(what):
        hold.append(("모름", what + "을(를) 못 잼"))

    u = f.get("user") or {}
    lk = u.get("locked")
    idle = u.get("idle_s")
    if idle is None:
        unk("마지막 입력")
    else:
        lim = (c["locked_idle_min"] if lk else c["user_idle_min"]) * 60
        if idle < lim:
            hold.append(("사람", "마지막 입력 %d분 전%s" % (idle // 60, " · 잠금 화면" if lk else "")))
    ns = u.get("notif")
    if ns is None:
        unk("전체 화면 여부")
    elif ns in (2, 3, 4) and not lk:
        hold.append(("사람", {2: "전체 화면 앱", 3: "전체 화면 게임·영상", 4: "발표 모드"}[ns]))
    au = u.get("audio")
    if au is None:
        unk("소리 재생")
    elif au:
        hold.append(("사람", "소리 재생 중"))

    cl = f.get("claude")
    if cl is None:
        unk("Claude 세션 장부")
    else:
        for s in cl:
            if s["busy"]:
                hold.append(("Claude", "«%s» 일하는 중" % (s["name"] or s["short"])[:30]))
            elif s["idle_min"] is None:          # 일한 때 모름 = 일하는 중일 수 있어 미룸
                hold.append(("Claude", "«%s» 일한 때 모름" % (s["name"] or s["short"])[:30]))
            elif s["idle_min"] < c["claude_idle_min"]:
                hold.append(("Claude", "«%s» %d분 전 일함" % ((s["name"] or s["short"])[:30], s["idle_min"])))
            elif c["claude_open"] == "any":
                hold.append(("Claude", "«%s» 열려 있음" % (s["name"] or s["short"])[:30]))

    if f.get("heavy_lock"):
        hold.append(("프로그램", "시험 잠금(heavy.lock) 있음"))
    reclaim = set(f.get("reclaim") or [])
    for e in f.get("ledger") or []:
        if e["pid"] not in reclaim:
            hold.append(("프로그램", "볼트 일 «%s» 도는 중" % (e.get("kind") or e.get("cmd") or e["pid"])))
    g = f.get("gpu")
    if g is None:
        unk("GPU 일")
    else:
        for n, ut in g:
            hold.append(("프로그램", "GPU 일 %s %.0f%%" % (n, ut)))

    spin = {x.lower() for x in c["spin_ok"]}
    cpu_ok = {x.lower() for x in c.get("cpu_ok") or []}
    pr = f.get("procs")
    if pr is None:
        unk("프로그램 활동")
    for p in pr or []:
        n = p["name"].lower()
        if p["pid"] in reclaim or n in spin:
            continue
        if UPDATE.match(n):
            if p["core"] >= 0.1 or p["io_kbs"] >= c["io_kbs"]:
                hold.append(("프로그램", "Windows 업데이트 설치 중(%s)" % p["name"]))
            continue
        if INSTALL.search(n) and not (n == "msiexec.exe" and re.search(r"\s/V\b", p.get("cmd", ""), re.I)):
            hold.append(("프로그램", "설치 프로그램 %s" % p["name"]))
            continue
        if RESIDENT.match(n) or _sysdir(p.get("exe")):
            continue
        if p["io_kbs"] >= c["io_kbs"]:
            hold.append(("프로그램", "%s 디스크 %.0fKB/s" % (p["name"], p["io_kbs"])))
        elif p["core"] >= c["cpu_core"] and n not in cpu_ok:
            hold.append(("프로그램", "%s CPU %.2f코어" % (p["name"], p["core"])))
    nk = f.get("net_kbs")
    if nk is None:
        unk("망 사용")
    elif nk >= c["net_kbs"]:
        hold.append(("프로그램", "망 %.0fKB/s(받는 중)" % nk))
    for x in f.get("partial") or []:
        hold.append(("프로그램", "받는 중인 파일 %s" % x[:40]))

    w = f.get("windows")
    if w is None:
        unk("창 목록")
    docs = {x.lower() for x in c["doc_apps"]}
    seen = set()
    for x in w or []:
        n = (x.get("name") or "").lower()
        if DIRTY.search(x["title"]):
            hold.append(("저장", "저장 안 된 창 «%s»" % x["title"][:40]))
        elif n in docs and n not in seen:
            seen.add(n)
            hold.append(("저장", "문서 창 %s(저장 여부 모름)" % x["name"]))

    bat = f.get("battery")
    if bat and c["hold_on_battery"]:
        hold.append(("전원", "배터리로 도는 중"))
    return ("미룸" if hold else "끔"), hold


# ── 기록 ──────────────────────────────────────────────────────────────────
def _load(p, d=None):
    try:
        with open(p, encoding="utf-8") as h:
            return json.load(h)
    except (OSError, ValueError):
        return d


def _save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(obj, h, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def _log(ev, **kw):
    os.makedirs(DIR, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as h:
        h.write(json.dumps({"t": dt.datetime.now().isoformat(timespec="seconds"), "ev": ev, **kw}, ensure_ascii=False) + "\n")


def alert_script():
    p = os.path.join(VAULT, ".claude", "skills", "mobility", "scripts", "alert.py")
    try:
        sys.path.insert(0, HERE)
        import roles
        if not roles.module_on("mobility"):
            return None
    except Exception:  # noqa: BLE001
        pass
    return p if os.path.exists(p) else None


def notify(c, title, text, dry=False):
    if not c["notify"]:
        return
    a = alert_script()
    if not a:
        return
    cmd = [sys.executable, a, "now", title, "--text", text, "--system", "자동 재시작"] + (["--dry"] if dry else [])
    try:
        subprocess.run(cmd, capture_output=True, timeout=30, creationflags=NOWIN)
    except Exception:  # noqa: BLE001
        pass


# ── 재시작 뒤 할 일(선언) ─────────────────────────────────────────────────
def declarations():
    """[항목] — 본체 after_restart.json 다음 켜진 모듈의 contributes.after_restart(파일)"""
    out = []

    def add(path, src):
        d = _load(path, {})
        for it in (d.get("항목") or d.get("items") or []) if isinstance(d, dict) else []:
            if isinstance(it, dict) and it.get("id"):
                out.append(dict(it, _src=src))
    add(CORE_DECL, "본체")
    try:
        sys.path.insert(0, HERE)
        import roles
        for m in roles.modules(on_only=True, vault=VAULT):
            rel = ((m.get("json") or {}).get("contributes") or {}).get("after_restart")
            if isinstance(rel, str):
                add(os.path.join(VAULT, *rel.split("/")), m["id"])
    except Exception:  # noqa: BLE001
        pass
    return [it for it in out if not it.get("module") or _module_on(it["module"])]


def _module_on(mid):
    try:
        import roles
        return roles.module_on(mid) and os.path.isdir(os.path.join(VAULT, ".claude", "skills", mid))
    except Exception:  # noqa: BLE001
        return os.path.isdir(os.path.join(VAULT, ".claude", "skills", mid))


def _subst(a):
    lad = os.environ.get("LOCALAPPDATA", "")
    if "{claude}" in a:
        try:
            sys.path.insert(0, HERE)
            import claude_bin
            cb = claude_bin.newest()
        except Exception:  # noqa: BLE001
            cb = "claude"
        a = a.replace("{claude}", cb)
    return a.replace("{py}", sys.executable).replace("{vault}", VAULT).replace("{localappdata}", lad)


def _plist():
    import psutil
    out = []
    for p in psutil.process_iter(["name", "cmdline", "ppid"]):
        try:
            out.append(((p.info["name"] or "").lower(), " ".join(p.info["cmdline"] or []), p.info["ppid"]))
        except Exception:  # noqa: BLE001
            pass
    return out


def proc_match(spec, plist):
    n = (spec.get("name") or "").lower()
    rx = re.compile(spec["cmd"], re.I) if spec.get("cmd") else None
    nx = re.compile(spec["not_cmd"], re.I) if spec.get("not_cmd") else None
    return sum(1 for name, cmd, _pp in plist if (not n or name == n) and (not rx or rx.search(cmd)) and not (nx and nx.search(cmd)))


def _task_state(name):
    try:
        r = subprocess.run(["schtasks", "/query", "/tn", name, "/fo", "csv", "/nh"], capture_output=True, timeout=20, creationflags=NOWIN)
        t = r.stdout.decode("cp949", "replace") if r.returncode == 0 else ""
        return t.strip().split('","')[-1].strip('"\r\n ') if t else None
    except Exception:  # noqa: BLE001
        return None


def check_item(it, plist=None):
    """(됨 bool, 까닭) — check = {"proc": {...}} · {"task": 이름} · {"cmd": [...]}(종료 0)"""
    ch = it.get("check") or {}
    if "proc" in ch:
        k = proc_match(ch["proc"], _plist() if plist is None else plist)
        return k >= int(ch["proc"].get("min", 1)), "프로세스 %d개" % k
    if "task" in ch:
        s = _task_state(ch["task"])
        return s is not None and s not in ("사용 안 함", "Disabled"), "예약 %s" % (s or "없음")
    if "cmd" in ch:
        try:
            r = subprocess.run([_subst(a) for a in ch["cmd"]], capture_output=True, timeout=int(ch.get("timeout", 30)), cwd=VAULT, creationflags=NOWIN)
            tail = (r.stdout.decode("utf-8", "replace").strip().splitlines() or [""])[-1][:80]
            return r.returncode == 0, tail or "종료 %d" % r.returncode
        except Exception as e:  # noqa: BLE001
            return False, str(e)[:80]
    return True, "잴 것 없음"


def launch(it):
    run = it.get("run")
    if not run:
        return False, "띄우는 법 없음"
    argv = [_subst(a) for a in run]
    si = None
    if it.get("minimized"):
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 7            # SW_SHOWMINNOACTIVE — 초점을 안 뺏음
    try:
        flags = 0x00000200 | (NOWIN if it.get("hidden") else 0x00000008)   # 새 묶음 · 숨김(콘솔) 아니면 DETACHED
        subprocess.Popen(argv, cwd=_subst(it["cwd"]) if it.get("cwd") else VAULT, startupinfo=si, creationflags=flags,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        return True, "띄움"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:80]


def snapshot(items):
    pl = _plist()
    return {it["id"]: (proc_match(it["was"], pl) > 0 if it.get("was") else None) for it in items}


# ── 명령 ──────────────────────────────────────────────────────────────────
def cmd_check(a):
    c = cfg()
    f = _load(a.fake) if a.fake else gather(c)
    v, why = judge(f, c)
    if a.json:
        print(json.dumps({"verdict": v, "why": why}, ensure_ascii=False))
    else:
        print(v + (" — " + " · ".join("%s: %s" % w for w in why) if why else ""))
    return 0 if v == "끔" else 3


def do_restart(c, dry):
    """실제 재시작 — on 이 켜져 있고 dry 가 아닐 때만"""
    if dry or not c["on"]:
        return "dry"
    r = subprocess.run(["shutdown", "/g", "/t", "60", "/d", "p:0:0", "/c", "외부뇌 자동 재시작 — 취소하려면 shutdown /a"],
                       capture_output=True, timeout=20, creationflags=NOWIN)
    return "ok" if r.returncode == 0 else "fail %d %s" % (r.returncode, r.stderr.decode("cp949", "replace").strip()[:80])


def cmd_tick(a):
    c = cfg()
    if not c["on"] and not a.dry:
        return 0
    now = dt.datetime.now()
    if a.now:
        h, m = a.now.split(":")
        now = now.replace(hour=int(h), minute=int(m))
    day = now.strftime("%Y-%m-%d")
    st = _load(STATE, {}) or {}
    if st.get("day") == day and st.get("status") in ("재시작", "건너뜀"):
        print("오늘은 이미 %s" % st["status"])
        return 0
    mins = now.hour * 60 + now.minute
    at, dead = _hm(c["at"]), _hm(c["deadline"])
    if not (at <= mins if at <= dead else (mins >= at or mins <= dead)):
        print("아직(%s)" % c["at"])
        return 0
    f = _load(a.fake) if a.fake else gather(c)
    up_h = (f.get("t", time.time()) - f.get("boot", 0)) / 3600
    st = {"day": day, "holds": st.get("holds", 0) if st.get("day") == day else 0}
    if up_h < c["min_uptime_h"]:
        st.update(status="건너뜀", last=[["전원", "켜진 지 %.1f시간(이미 새로 켜짐)" % up_h]])
        _save(STATE, st) if not a.dry else None
        _log("skip", why="uptime", up_h=round(up_h, 1), dry=a.dry)
        print("건너뜀 — 켜진 지 %.1f시간" % up_h)
        return 0
    v, why = judge(f, c)
    late = (mins > dead) if at <= dead else (dead < mins < at)
    if v == "미룸":
        st["holds"] += 1
        st["last"] = why
        if late:
            st["status"] = "건너뜀"
            notify(c, "오늘 자동 재시작 건너뜀", " · ".join(w[1] for w in why[:4]), dry=a.dry)
        else:
            st["status"] = "미룸"
        if not a.dry:
            _save(STATE, st)
        _log("hold" if not late else "skip", why=why, dry=a.dry)
        print("%s — %s" % (st["status"], " · ".join("%s: %s" % w for w in why)))
        return 3
    items = declarations()
    before = {"t": time.time(), "at": now.isoformat(timespec="seconds"), "boot": f.get("boot"), "was": snapshot(items),
              "claude": [s.get("name") or s.get("short") for s in (f.get("claude") or [])]}
    if a.dry:
        print("끔 — (dry) 재시작하지 않음 · 기록할 것: " + json.dumps(before["was"], ensure_ascii=False))
        _log("go", dry=True)
        return 0
    _save(BEFORE, before)
    res = do_restart(c, a.dry)
    st.update(status="재시작" if res == "ok" else "실패", last=[["재시작", res]])
    _save(STATE, st)
    _log("restart", res=res, was=before["was"])
    if res != "ok":
        notify(c, "자동 재시작 실패", res)
    print("재시작 " + res)
    return 0 if res == "ok" else 1


def cmd_after(a):
    c = cfg()
    b = _load(BEFORE)
    if not b:
        print("재시작 기록 없음 — 할 일 없음")
        return 0
    import psutil
    if psutil.boot_time() < b["t"] and not a.dry:
        print("아직 재시작 전")
        return 0
    if not c["relaunch"]:
        _log("after", skipped="relaunch off")
        os.replace(BEFORE, os.path.join(DIR, "last-before.json"))
        return 0
    items = declarations()
    # 기다림(grace_s)이 있는 항목은 뒤로 — 11-20 실제 시험: 크롬 기다림 120초가 앞에 있어 서버가 로그온 4분 뒤에야 뜸
    items = [it for it in items if not it.get("grace_s")] + [it for it in items if it.get("grace_s")]
    res = []
    for it in items:
        was = b.get("was", {}).get(it["id"])
        if it.get("when", "always") == "was_running" and not was:
            res.append({"id": it["id"], "name": it.get("name"), "state": "안 띄움(그때 없었음)"})
            continue
        ok, why = check_item(it)
        if not ok and it.get("grace_s") and not a.dry:
            end = time.time() + it["grace_s"]
            while not ok and time.time() < end:
                time.sleep(10)
                ok, why = check_item(it)
        did = ""
        if not ok and it.get("run"):
            if a.dry:
                did = "(dry) 띄울 것"
            else:
                _lok, did = launch(it)
                end = time.time() + int(it.get("wait_s", 120))
                while not ok and time.time() < end:
                    time.sleep(5)
                    ok, why = check_item(it)
        res.append({"id": it["id"], "name": it.get("name"), "src": it["_src"], "ok": ok, "why": why, "did": did,
                    "state": "떴음" if ok else ("안 뜸" if not a.dry else "dry")})
    bad = [r for r in res if r.get("ok") is False]
    out = {"t": dt.datetime.now().isoformat(timespec="seconds"), "before": b.get("at"), "items": res, "bad": len(bad)}
    for r in res:
        print("%s %s — %s %s" % ("✓" if r.get("ok") else ("·" if "ok" not in r else "✗"), r.get("name") or r["id"], r.get("why") or r["state"], r.get("did") or ""))
    if a.dry:
        return 0
    _save(AFTER, out)
    os.replace(BEFORE, os.path.join(DIR, "last-before.json"))
    _log("after", bad=[r["id"] for r in bad], n=len(res))
    if bad:
        notify(c, "재시작 뒤 안 뜬 것 %d" % len(bad), " · ".join(r.get("name") or r["id"] for r in bad))
    elif c["notify_ok"]:
        notify(c, "자동 재시작 끝", "%d개 다 떴음" % len(res))
    return 1 if bad else 0


def cmd_plan(a):
    pl = _plist()
    for it in declarations():
        ok, why = check_item(it, pl)
        was = proc_match(it["was"], pl) > 0 if it.get("was") else None
        print("%s [%s] %s — 지금 %s(%s)%s%s" % ("✓" if ok else "✗", it["_src"], it.get("name") or it["id"], "됨" if ok else "안 됨", why,
                                             " · 띄움=%s" % it.get("when", "always"), "" if was is None else " · 떠 있음" if was else " · 안 떠 있음"))
    return 0


def cmd_status(a):
    c = cfg()
    print("설정: %s · %s 부터 %d분마다 · 마감 %s · 켜진 지 %d시간 미만이면 건너뜀 · 다시 세팅 %s · 알림 %s" % (
        "켬" if c["on"] else "끔", c["at"], c["retry_min"], c["deadline"], c["min_uptime_h"], "켬" if c["relaunch"] else "끔", "켬" if c["notify"] else "끔"))
    print("오늘:", json.dumps(_load(STATE, {}), ensure_ascii=False))
    try:
        with open(LOG, encoding="utf-8") as h:
            for ln in h.readlines()[-5:]:
                print(" ", ln.rstrip()[:200])
    except OSError:
        pass
    return 0


def task_xml(kind, c):
    """예약 작업 XML(사용자 대화형 · 관리자 불필요) — restart: 매일 at 부터 retry_min 마다 마감까지 · after: 이 사용자 로그온 1분 뒤"""
    py = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "pyw.exe")
    me = os.environ.get("USERDOMAIN", "") + "\\" + os.environ.get("USERNAME", "")
    wake = "false"
    if kind == "restart":
        wake = "true" if wake_pc() else "false"
        dur = (_hm(c["deadline"]) - _hm(c["at"])) % 1440
        trig = ("<CalendarTrigger><StartBoundary>2026-01-01T%s:00</StartBoundary><Repetition><Interval>PT%dM</Interval>"
                "<Duration>PT%dM</Duration></Repetition><ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger>") % (c["at"], c["retry_min"], dur + 1)
        args = '-3 "%s" tick' % os.path.join(HERE, "restart.py")
    else:
        trig = "<LogonTrigger><UserId>%s</UserId><Delay>PT1M</Delay></LogonTrigger>" % me
        args = '-3 "%s" after' % os.path.join(HERE, "restart.py")
    return ('<?xml version="1.0" encoding="UTF-16"?><Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
            "<Triggers>%s</Triggers><Principals><Principal id=\"Author\"><UserId>%s</UserId><LogonType>InteractiveToken</LogonType>"
            "<RunLevel>LeastPrivilege</RunLevel></Principal></Principals><Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>"
            "<DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>"
            "<ExecutionTimeLimit>PT30M</ExecutionTimeLimit><StartWhenAvailable>false</StartWhenAvailable><WakeToRun>%s</WakeToRun></Settings>"
            "<Actions Context=\"Author\"><Exec><Command>%s</Command><Arguments>%s</Arguments><WorkingDirectory>%s</WorkingDirectory></Exec></Actions></Task>"
            ) % (trig, me, wake, py, args.replace("&", "&amp;"), VAULT)


def wake_pc():
    """잠든 PC 를 그 시각에 깨울지 — 수집과 같은 기능 «PC 깨우기»(collect.wake_pc · collectlib.wake_pc · 배터리는 전원 구성표가 깨우기 타이머를 막음).
    켬이면 재시작 예약에 WakeToRun · 미루는 동안은 15분마다 다시 깨움(윈도가 약 2분 뒤 다시 재움). 못 읽으면 안 깨움."""
    try:
        sys.path.insert(0, HERE)
        import collectlib
        return bool(collectlib.wake_pc(HERE))
    except Exception:  # noqa: BLE001
        return False


def cmd_install(a):
    c = cfg()
    for name, kind in ((TASK, "restart"), (TASK_AFTER, "after")):
        x = task_xml(kind, c)
        if a.print:
            print("== %s\n%s" % (name, x))
            continue
        p = os.path.join(DIR, kind + ".xml")
        os.makedirs(DIR, exist_ok=True)
        with open(p, "w", encoding="utf-16") as h:
            h.write(x)
        r = subprocess.run(["schtasks", "/create", "/tn", name, "/xml", p, "/f"], capture_output=True, timeout=30, creationflags=NOWIN)
        print(name, "등록" if r.returncode == 0 else "실패 " + r.stderr.decode("cp949", "replace").strip()[:120])
    return 0


def cmd_remove(a):
    for name in (TASK, TASK_AFTER):
        r = subprocess.run(["schtasks", "/delete", "/tn", name, "/f"], capture_output=True, timeout=30, creationflags=NOWIN)
        print(name, "지움" if r.returncode == 0 else "없음")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="자동 재시작")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("check")
    p.add_argument("--json", action="store_true")
    p.add_argument("--fake")
    p = sp.add_parser("tick")
    p.add_argument("--dry", action="store_true")
    p.add_argument("--fake")
    p.add_argument("--now")
    p = sp.add_parser("after")
    p.add_argument("--dry", action="store_true")
    sp.add_parser("plan")
    sp.add_parser("status")
    p = sp.add_parser("install")
    p.add_argument("--print", action="store_true")
    sp.add_parser("remove")
    a = ap.parse_args(argv)
    return {"check": cmd_check, "tick": cmd_tick, "after": cmd_after, "plan": cmd_plan, "status": cmd_status,
            "install": cmd_install, "remove": cmd_remove}[a.cmd](a)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
