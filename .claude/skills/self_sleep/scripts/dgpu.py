#!/usr/bin/env python3
"""외장 NVIDIA 그래픽을 깨우기만 하는 앱 찾기·끄기 — 자체 절전(self_sleep)의 «외장 그래픽 깨우는 앱 끄기» 일.
gpu_guard 0.2 의 범인 찾기를 옮겼다(설계·실측 = 2_지식/일/외부뇌/절전지킴이-작업기록 §1·§3). 기억(되살아남)은 memo 인자로 받는다.
외장 GPU 장치 전원 상태(D3/D0)는 cfgmgr32 로 읽으면 깨우지 않는다 · nvidia-smi 는 부를 때마다 깨우므로 이미 D0 일 때만 부른다."""
import ctypes
import os
import re
import subprocess
import time
import uuid
from ctypes import wintypes

NOWIN = 0x08000000
SMI = os.path.join(os.environ.get('SystemRoot', r'C:\Windows'), 'System32', 'nvidia-smi.exe')


# ───────── 외장 GPU 장치 상태(깨우지 않음) ─────────
class GUID(ctypes.Structure):
    _fields_ = [('a', ctypes.c_uint32), ('b', ctypes.c_uint16), ('c', ctypes.c_uint16), ('d', ctypes.c_ubyte * 8)]

    @classmethod
    def of(cls, s):
        u = uuid.UUID(s)
        g = cls(u.fields[0], u.fields[1], u.fields[2])
        for i, b in enumerate(u.bytes[8:]):
            g.d[i] = b
        return g

    def __eq__(self, o):
        return bytes(self) == bytes(o)


class DEVPROPKEY(ctypes.Structure):
    _fields_ = [('fmtid', GUID), ('pid', ctypes.c_uint32)]


_DEVPROP = 'a45c254e-df1c-4efd-8020-67d146a850e0'
KEY_POWER = DEVPROPKEY(GUID.of(_DEVPROP), 32)
KEY_CLASS = DEVPROPKEY(GUID.of(_DEVPROP), 9)


def _prop(inst, key):
    cfg = ctypes.WinDLL('cfgmgr32')
    dn = wintypes.DWORD()
    if cfg.CM_Locate_DevNodeW(ctypes.byref(dn), inst, 0) != 0:
        return None
    typ, size = wintypes.ULONG(), wintypes.ULONG(0)
    cfg.CM_Get_DevNode_PropertyW(dn, ctypes.byref(key), ctypes.byref(typ), None, ctypes.byref(size), 0)
    if not size.value:
        return None
    buf = (ctypes.c_ubyte * size.value)()
    if cfg.CM_Get_DevNode_PropertyW(dn, ctypes.byref(key), ctypes.byref(typ), buf, ctypes.byref(size), 0) != 0:
        return None
    return bytes(buf)


def find_dgpu():
    """PCI\\VEN_10DE 이고 장치 종류가 «Display» 인 첫 장치(외장 NVIDIA). 없으면 None."""
    cfg = ctypes.WinDLL('cfgmgr32')
    n = wintypes.ULONG()
    flt = 'PCI'
    if cfg.CM_Get_Device_ID_List_SizeW(ctypes.byref(n), flt, 0x1 | 0x100) != 0:   # FILTER_ENUMERATOR | FILTER_PRESENT
        return None
    buf = ctypes.create_unicode_buffer(n.value)
    cfg.CM_Get_Device_ID_ListW(flt, buf, n, 0x1 | 0x100)
    for inst in (x for x in buf[:n.value].split('\0') if x.upper().startswith('PCI\\VEN_10DE')):
        c = _prop(inst, KEY_CLASS)
        if c and c.decode('utf-16-le').rstrip('\0').lower() == 'display':
            return inst
    return None


def dstate(inst):
    b = _prop(inst, KEY_POWER)
    return f'D{int.from_bytes(b[4:8], "little") - 1}' if b and len(b) >= 8 else None


# ───────── 범인 찾기(이미 D0 일 때만) ─────────
SMI_ROW = re.compile(r'^\|\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(C\+G|C|G)\s+(.*?)\s+(?:N/A|\d+MiB)\s+\|$')


def smi_pids(text):
    """nvidia-smi 표의 프로세스 줄 → pid 목록."""
    return [int(m.group(1)) for m in (SMI_ROW.match(ln.strip()) for ln in text.splitlines()) if m]


def on_dgpu():
    try:
        out = subprocess.run([SMI], capture_output=True, timeout=20, creationflags=NOWIN).stdout.decode('utf-8', 'replace')
    except (OSError, subprocess.SubprocessError):
        return None
    return smi_pids(out)


def gpu_time():
    """pid → GPU 엔진 사용 시간(100ns · 엔진마다) — Windows GPU Engine 카운터(모든 어댑터)."""
    ps = "(Get-Counter -Counter '\\GPU Engine(*)\\Running Time' -ErrorAction SilentlyContinue).CounterSamples | ForEach-Object { $_.InstanceName + \"`t\" + $_.RawValue }"
    try:
        out = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, timeout=60, creationflags=NOWIN).stdout.decode('utf-8', 'replace')
    except (OSError, subprocess.SubprocessError):
        return {}
    r = {}
    for ln in out.splitlines():
        m = re.match(r'pid_(\d+)_(.+)\t(\d+)', ln.strip())
        if m:
            r[(int(m.group(1)), m.group(2))] = int(m.group(3))
    return r


def io_bytes(p):
    try:
        c = p.io_counters()
        return c.read_bytes + c.write_bytes + getattr(c, 'other_bytes', 0)
    except Exception:  # noqa: BLE001 — 권한 없음·끝남
        return None


def has_window(pid):
    u = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        p = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u.IsWindowVisible(h):
            found.append(h)
        return True
    u.EnumWindows(cb, 0)
    return found


def judge(p, c, respawn=()):
    """한 프로세스의 판정(순수) — p = {name, exe, util, io_kbs, self} → (kill|protect|work|download, 까닭)."""
    name = (p.get('name') or '').lower()
    exe = (p.get('exe') or '').lower().replace('/', '\\')
    if not name:
        return 'protect', '이름 모름'
    if p.get('self') or name in {x.lower() for x in c['protect']}:
        return 'protect', '보호 목록'
    if exe.startswith('c:\\windows\\'):
        return 'protect', 'Windows'
    if name in {x.lower() for x in respawn}:
        return 'protect', '되살아남(설정에서 끌 것)'
    if p.get('util') is None or p.get('io_kbs') is None:
        return 'protect', '잴 수 없음'
    if p['util'] >= c['util_max']:
        return 'work', f'그래픽 일 {p["util"]:.1f}%'
    if p['io_kbs'] >= c['io_kbs']:
        return 'download', f'받는 중 {p["io_kbs"]:.0f}KB/s'
    return 'kill', f'깨우기만 함(사용률 {p["util"]:.1f}% · 입출력 {p["io_kbs"]:.0f}KB/s)'


def analyze(c, watch_s=None, memo=None):
    """D0 일 때 — 외장 GPU 를 쓰는 프로세스를 watch_s 동안 재서 판정한다. 끝난 결과 목록을 돌려준다(끄지는 않음)."""
    import psutil
    pids = on_dgpu()
    if pids is None:
        return None
    me = {os.getpid(), os.getppid()}
    procs = {}
    for pid in pids:
        try:
            pr = psutil.Process(pid)
            procs[pid] = {'pid': pid, 'name': pr.name(), 'exe': pr.exe(), 'p': pr, 'io0': io_bytes(pr), 'self': pid in me}
        except Exception:  # noqa: BLE001
            procs[pid] = {'pid': pid, 'name': None, 'exe': None, 'p': None, 'io0': None, 'self': False}
    g0, t0 = gpu_time(), time.time()
    time.sleep(watch_s if watch_s is not None else c['watch_s'])
    g1, el = gpu_time(), max(time.time() - t0, 1e-3)
    respawn = (memo or {}).get('respawn', [])
    out = []
    for pid, x in procs.items():
        eng = [(g1[k] - g0.get(k, g1[k])) for k in g1 if k[0] == pid]
        x['util'] = round(max(eng) / (el * 1e7) * 100, 2) if eng else (0.0 if g0 or g1 else None)
        io1 = io_bytes(x['p']) if x['p'] else None
        x['io_kbs'] = round((io1 - x['io0']) / el / 1024, 1) if io1 is not None and x['io0'] is not None else None
        v, why = judge(x, c, respawn)
        out.append({'pid': pid, 'name': x['name'], 'exe': x['exe'], 'util': x['util'], 'io_kbs': x['io_kbs'], 'verdict': v, 'why': why})
    return out


# ───────── 끄기·다시 켜기 ─────────
def run_entries():
    """시작 프로그램(Run) 명령 — exe 경로(소문자) → 명령 줄."""
    import winreg
    r = {}
    for hive, path in ((winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run'),
                       (winreg.HKEY_LOCAL_MACHINE, r'Software\Microsoft\Windows\CurrentVersion\Run'),
                       (winreg.HKEY_LOCAL_MACHINE, r'Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Run')):
        try:
            with winreg.OpenKey(hive, path) as k:
                for i in range(winreg.QueryInfoKey(k)[1]):
                    _, cmd, _ = winreg.EnumValue(k, i)
                    m = re.match(r'\s*"([^"]+)"|\s*(\S+)', str(cmd))
                    if m:
                        r[(m.group(1) or m.group(2)).lower()] = str(cmd)
        except OSError:
            pass
    return r


def relaunch_cmd(name, exe, c, runs):
    """나올 때 다시 켤 명령(순수에 가깝게) — 설정 always/never · 없으면 시작 프로그램에 있을 때만(상주형)."""
    pol = c['relaunch'].get((name or '').lower())
    cmd = runs.get((exe or '').lower())
    if pol == 'never':
        return None
    if cmd:
        return cmd
    return f'"{exe}"' if pol == 'always' and exe else None


def kill(x, c, memo=None):
    """창 닫기 요청(또는 close_cmd) → grace_s → 강제. 되살아나면 respawn 에 적는다. 돌려줌 = 결과 글."""
    import psutil
    try:
        pr = psutil.Process(x['pid'])
    except psutil.Error:
        return '이미 꺼짐'
    name = (x['name'] or '').lower()
    how = '창 닫기'
    cc = c['close_cmd'].get(name)
    if cc:
        try:
            subprocess.Popen([a.replace('{exe}', x['exe']) for a in cc], creationflags=NOWIN)
            how = '종료 명령'
        except OSError:
            cc = None
    if not cc:
        for h in has_window(x['pid']):
            ctypes.windll.user32.PostMessageW(h, 0x0010, 0, 0)   # WM_CLOSE
    try:
        pr.wait(c['grace_s'])
    except psutil.TimeoutExpired:
        for ch in pr.children(recursive=True) + [pr]:
            try:
                ch.kill()
            except psutil.Error:
                pass
        how += ' → 강제'
    time.sleep(c['respawn_s'])
    back = [p.pid for p in psutil.process_iter(['name']) if (p.info['name'] or '').lower() == name]
    if back:
        if memo is not None:
            memo['respawn'] = sorted(set(memo.get('respawn', [])) | {name})
        return how + ' · 되살아남'
    return how
