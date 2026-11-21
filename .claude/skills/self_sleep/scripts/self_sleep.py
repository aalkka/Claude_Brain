#!/usr/bin/env python3
"""자체 절전 — 윈도를 재우지 않고(폰 환경 = 서버·Tailscale·RC·와이파이 유지) 아무도 안 볼 때 덜 먹게 한다.

  pyw -3 self_sleep.py run            늘 도는 감시(로그온 예약 작업이 띄움 · 하나만 뜬다)
  py  -3 self_sleep.py probe [--json] 이 기기에 무엇이 있나 재서 3_시스템/_index/device.json caps 에 씀(옵션 칸 숨김의 근거)
  py  -3 self_sleep.py status         지금 상태 · 칸마다 단계 · 최근 기록
  py  -3 self_sleep.py measure [--secs 30]   패키지 전력(RAPL)·CPU·배터리 방전·외장 GPU 상태를 잰다(읽기만)
  py  -3 self_sleep.py now            덮개·화면·전원 지금 값(감시와 같은 알림 길 · 아무것도 안 함)
  py  -3 self_sleep.py trial [--secs 20] [--load 4] [--ping URL]   후보 «효율 모드» 재기 — 시험 부하에만 걸고 전·뒤·되돌린 뒤 전력 · 서버 닿음

들어가는 때(칸마다 따로 · 모두 «화면 꺼짐»일 때만 — 클램셸로 쓰는 중이면 화면이 켜져 있어 안 들어감):
  power.lid_ac     덮개 닫힘 · 전원 연결          power.lid_dc   덮개 닫힘 · 배터리
  power.screen_off 덮개 열림 · 입력 없어 윈도가 화면을 끔(동영상을 보는 중이면 윈도가 화면을 안 끔)
  power.lid_dc_then 배터리 + 덮개 닫힘이 30분 이어지면 재움(켬/끔) · power.lid_dc_how 재우는 꼴(최대 절전 | 절전)
하는 일(칸마다 따로): power.dgpu_apps 외장 그래픽 깨우는 앱 끄기 · power.media 미디어 멈춤 · power.logo_light 로고 조명 끔
  (효율 모드 EcoQoS 는 칸이 없다 — 11-20 A/B/A 실측에서 패키지 전력 차이가 잡음 안이었고 밤 일꾼·에뮬레이터를 늦춘다 · `trial` 로 다시 잴 수 있음)
깨어 있음(칸마다 따로): power.awake_ac 전원 연결이면 늘 «시스템 필요»를 쥠(화면은 꺼짐) · power.resume_awake 타이머로 저절로 깨면
  사람이 오기 전까지 쥠 — 윈도는 저절로 깬 PC 를 입력 없으면 2분(UNATTENDSLEEP) 뒤 다시 재운다(11-20 사고 · _ref/incident-2026-11-20-…). 배터리면 놓음.
나올 때: 덮개 열림·화면 켜짐 → 조명 되돌림 · 끈 상주 앱 다시 켬. 들어가 있는 동안 _index/self_sleep/active.json 이 있다(다른 대본이 무거운 일을 미룰 때 읽는 신호).
절대 안 건드림: 네트워크·와이파이·Tailscale·서버·Claude(RC)·크롬(수집) — 보호 목록. 윈도 전원 설정도 안 바꾼다(바꾸는 것은 최대 절전·절전 «하기»뿐).
기기 고유 값(외장 GPU 장치·조명 작업 이름 등)은 재서 git 밖 _index 에만 둔다. 설계 = 2_지식/일/외부뇌/자체절전-설계."""
import argparse
import ctypes
import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.normpath(os.path.join(HERE, '..', '..', '..', '..'))
SYS = os.path.join(VAULT, '3_시스템')
STATE = os.environ.get('SELF_SLEEP_STATE') or os.path.join(SYS, '_index', 'self_sleep')
DEVICE = os.environ.get('SELF_SLEEP_DEVICE') or os.path.join(SYS, '_index', 'device.json')
CONFIG = os.path.join(STATE, 'config.json')
LOG = os.path.join(STATE, 'log.jsonl')
MEM = os.path.join(STATE, 'state.json')
ACTIVE = os.path.join(STATE, 'active.json')
NOWIN = 0x08000000
MEDIA_PS = os.path.join(HERE, 'media_pause.ps1')
IS_WIN = os.name == 'nt'

DEFAULT = {
    'poll_s': 15, 'watch_s': 30, 'backoff_s': 300,
    'util_max': 2.0, 'io_kbs': 256, 'grace_s': 10, 'respawn_s': 30,
    # 보호 목록 = 폰 환경·수집·윈도. 기기마다 더할 것은 config.json protect_add(git 밖)
    'protect': ['pythonw.exe', 'python.exe', 'py.exe', 'pyw.exe', 'tailscaled.exe', 'tailscale-ipn.exe', 'tailscale.exe',
                'chrome.exe', 'claude.exe', 'node.exe', 'obsidian.exe', 'dwm.exe', 'explorer.exe', 'csrss.exe', 'winlogon.exe',
                'svchost.exe', 'services.exe', 'lsass.exe', 'nvcontainer.exe', 'nvdisplay.container.exe', 'audiodg.exe', 'system',
                'powershell.exe', 'pwsh.exe', 'cmd.exe', 'bash.exe', 'git.exe', 'conhost.exe', 'openconsole.exe', 'windowsterminal.exe'],
    'protect_add': [],
    'close_cmd': {'steam.exe': ['{exe}', '-shutdown']},
    'relaunch': {},                 # 이름 → always | never (없으면 시작 프로그램에 있으면 다시 켬)
    'ecoqos_cpu': 10.0,
    'dgpu_observe': False,          # 참이면 외장 그래픽 깨우는 앱을 끄지 않고 «껐을 것»만 기록(옛 gpu_guard mode observe · 진단용 · 칸 없음)             # 한 코어 기준 % — 두 번 잇달아 넘으면 효율 모드
    'lights': {'off_task': '외부뇌 로고 조명 끔', 'restore_task': '외부뇌 로고 조명 되돌림',
               'prev': r'C:\Program Files\BrainLight\prev.json'},
}

# 옵션 칸 id — options.level("…") 을 글자 그대로 부른다(options.py check 가 이 글자로 대조한다)
LEVEL_IDS = ('power.lid_ac', 'power.lid_dc', 'power.screen_off', 'power.lid_dc_then', 'power.lid_dc_how',
             'power.dgpu_apps', 'power.media', 'power.logo_light', 'power.awake_ac', 'power.resume_awake',
             'power.serve_rc', 'power.serve_defer', 'power.serve_cpu', 'power.serve_guard')
# «낮음»(low) 단계를 쓰지 않는다 — options 의 «배터리일 때 낮춤»이 배터리에서 high→low 로 바꿔 절전 일을 오히려 줄이기 때문(켬/끔 칸 둘로 나눔)


# ───────── 설정·기록 ─────────
OLD_GPU_GUARD = os.environ.get('SELF_SLEEP_OLD_CONFIG') or os.path.join(SYS, '_index', 'gpu_guard', 'config.json')


def config():
    """기본값 ← 옛 gpu_guard 의 앱별 다시 켜기(relaunch · 예 steam.exe=never · 그 기기 사람 결정) ← 이 모듈 config.json.
    옛 값은 읽기만 한다(옮겨 쓰지 않음) — gpu_guard 를 지워도 self_sleep config.json 에 적어 두면 그대로."""
    c = json.loads(json.dumps(DEFAULT))
    old = _jload(OLD_GPU_GUARD, {})
    if isinstance(old, dict) and isinstance(old.get('relaunch'), dict):
        c['relaunch'].update({k.lower(): v for k, v in old['relaunch'].items() if isinstance(k, str) and v in ('always', 'never')})
    try:
        with open(CONFIG, encoding='utf-8') as f:
            u = json.load(f)
        for k, v in u.items():
            c[k] = {**c[k], **v} if isinstance(c.get(k), dict) and isinstance(v, dict) else v
    except (OSError, ValueError):
        pass
    c['protect'] = list(c['protect']) + [x for x in c.get('protect_add') or [] if isinstance(x, str)]
    return c


def now():
    return dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def log(ev, **kw):
    os.makedirs(STATE, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps({'t': now(), 'ev': ev, **kw}, ensure_ascii=False) + '\n')


def _jload(p, default):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _jsave(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def mem():
    m = _jload(MEM, {})
    return m if isinstance(m, dict) else {}


def save_mem(m):
    _jsave(MEM, m)


def levels():
    """칸마다 지금 단계 — options.level 이 어떤 오류도 high 로 돌려준다. options.py 가 없으면(이상한 볼트) 모두 high."""
    try:
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        import options
    except Exception:  # noqa: BLE001
        return {k: 'high' for k in LEVEL_IDS}
    return {
        'power.lid_ac': options.level("power.lid_ac"),
        'power.lid_dc': options.level("power.lid_dc"),
        'power.screen_off': options.level("power.screen_off"),
        'power.lid_dc_then': options.level("power.lid_dc_then"),
        'power.lid_dc_how': options.level("power.lid_dc_how"),
        'power.dgpu_apps': options.level("power.dgpu_apps"),
        'power.media': options.level("power.media"),
        'power.logo_light': options.level("power.logo_light"),
        'power.awake_ac': options.level("power.awake_ac"),
        'power.resume_awake': options.level("power.resume_awake"),
        'power.serve_rc': options.level("power.serve_rc"),
        'power.serve_defer': options.level("power.serve_defer"),
        'power.serve_cpu': options.level("power.serve_cpu"),
        'power.serve_guard': options.level("power.serve_guard"),
    }


def then_minutes(lvl):
    try:
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        import options
        p = options.params("power.lid_dc_then", lvl)
        return float(p.get('after_min', 10))
    except Exception:  # noqa: BLE001
        return 10.0


_ON = {'at': 0.0, 'v': True}


def module_on():
    """옵시디언 «모듈 끄기»(roles.module_on)를 따름 — 1분 기억(감시가 15초마다 부름)."""
    if time.time() - _ON['at'] < 60:
        return _ON['v']
    _ON['at'] = time.time()
    _ON['v'] = _module_on()
    return _ON['v']


def _module_on():
    try:
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        import roles
        return bool(roles.module_on('self_sleep'))
    except Exception:  # noqa: BLE001
        return True


# ───────── 판단(순수) ─────────
def want(st, lv, after_min=10.0):
    """지금 상태 → (들어갈 까닭 | None, 할 «다음 일» | None).
    st = {lid_closed, display_off, on_battery, battery_lid_since(초 · 배터리+덮개 닫힘이 시작된 때 · 없으면 None), now}
    모두 화면 꺼짐이 조건이다 — 덮개를 닫고 바깥 모니터로 쓰는 중(클램셸)이면 화면이 켜져 있어 안 들어간다."""
    if not st.get('display_off'):
        return None, None
    why = None
    if st.get('lid_closed'):
        key = 'power.lid_dc' if st.get('on_battery') else 'power.lid_ac'
        if lv.get(key) == 'high':
            why = 'lid_dc' if st.get('on_battery') else 'lid_ac'
    elif lv.get('power.screen_off') == 'high':
        why = 'screen_off'
    then = None
    since = st.get('battery_lid_since')
    if st.get('lid_closed') and st.get('on_battery') and lv.get('power.lid_dc_then') == 'high' and since is not None \
            and st['now'] - since >= after_min * 60:
        how = lv.get('power.lid_dc_how', 'high')       # 셋 중 하나(사용자 11-20) · 서버만 남김은 폰 서버가 있을 때만(없으면 최대 절전)
        then = 'sleep' if how == 'low' else 'serve' if how == 'off' and st.get('phone_server', True) else 'hibernate'
    return why, then


def hold_wanted(st, lv, resume_hold=False):
    """깨어 있음을 쥘까(순수) — 전원 연결일 때만. awake_ac 켬이면 늘 · resume_awake 켬이면 «무인으로 깬 뒤 사람이 오기 전»에만.
    배터리면 놓는다(가방 속 · 윈도 배터리 규칙과 «배터리로 닫아 둔 뒤 재움»을 그대로)."""
    if st.get('serving'):
        return True            # 서버만 남김 중 — 배터리여도 쥔다(아니면 윈도 배터리 유휴 절전 30분이 재움 · 안전장치가 끝냄)
    if st.get('on_battery'):
        return False
    return lv.get('power.awake_ac') == 'high' or (lv.get('power.resume_awake') == 'high' and bool(resume_hold))


ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001


def set_awake(on):
    """이 스레드의 실행 상태 — on = 시스템 필요(ES_SYSTEM_REQUIRED|ES_CONTINUOUS · 화면은 꺼져도 됨) · off = 놓음.
    윈도 유휴 절전과 «무인 깨어남 2분 뒤 다시 잠»(UNATTENDSLEEP)을 막는다. 사람이 고르는 절전(시작 메뉴·전원 단추·덮개 동작)과
    SetSuspendState 는 막지 않는다. 같은 스레드(감시 창 스레드)에서만 부른다 — 스레드가 끝나면 윈도가 저절로 놓는다."""
    k32 = ctypes.windll.kernel32
    k32.SetThreadExecutionState.restype = wintypes.DWORD
    k32.SetThreadExecutionState.argtypes = [wintypes.DWORD]
    return k32.SetThreadExecutionState(ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)) != 0


def system_execution_state():
    """윈도가 지금 받아 둔 실행 상태(모든 프로세스 합) — CallNtPowerInformation(SystemExecutionState) · 관리자 불필요 · 못 읽으면 None."""
    v = wintypes.ULONG()
    try:
        r = ctypes.WinDLL('powrprof').CallNtPowerInformation(16, None, 0, ctypes.byref(v), ctypes.sizeof(v))
    except OSError:
        return None
    return v.value if r == 0 else None


class LASTINPUT(ctypes.Structure):
    _fields_ = [('cb', wintypes.UINT), ('t', wintypes.DWORD)]


def last_input_tick():
    li = LASTINPUT(ctypes.sizeof(LASTINPUT), 0)
    ctypes.windll.user32.GetLastInputInfo(ctypes.byref(li))
    return li.t


def ecoqos_pick(samples, c, protect_pids=()):
    """효율 모드를 걸 프로세스(순수) — samples = [{pid, name, exe, cpu(한 코어 %), prev_cpu}] · 두 번 잇달아 넘은 것만."""
    prot = {x.lower() for x in c['protect']}
    out = []
    for s in samples:
        name = (s.get('name') or '').lower()
        exe = (s.get('exe') or '').lower().replace('/', '\\')
        if not name or name in prot or s.get('pid') in protect_pids or exe.startswith('c:\\windows\\') or not exe:
            continue
        if (s.get('cpu') or 0) >= c['ecoqos_cpu'] and (s.get('prev_cpu') or 0) >= c['ecoqos_cpu']:
            out.append(s['pid'])
    return out


# ───────── 이 기기 재기 ─────────
def power_caps():
    """SYSTEM_POWER_CAPABILITIES — 덮개·S3·S4·최대 절전 파일·현대 대기(AoAc)·배터리. 못 읽으면 {}."""
    if not IS_WIN:
        return {}
    buf = (ctypes.c_ubyte * 128)()
    try:
        r = ctypes.WinDLL('powrprof').CallNtPowerInformation(4, None, 0, buf, ctypes.sizeof(buf))   # SystemPowerCapabilities
    except OSError:
        return {}
    if r != 0:
        return {}
    b = bytes(buf)
    return {'lid': bool(b[2]), 's3': bool(b[5]), 's4': bool(b[6]), 'hiberfile': bool(b[8]), 'aoac': bool(b[20]),
            'battery': bool(b[30])}


def energy_meter():
    """RAPL 패키지 전력 카운터가 있나(관리자 없이 읽힘 · 인텔·일부 AMD)."""
    out = _ps("(Get-Counter -ListSet 'Energy Meter' -ErrorAction SilentlyContinue).PathsWithInstances -match '_pkg\\)\\\\Power$' | Select-Object -First 1")
    return bool(out.strip())


def lights_caps(c):
    """조명 — 지금 어댑터 = 레노버 WMI 로고(Lighting_ID 3·4). 칸이 보이는 근거 = 관리자 설치 조명 작업 둘이 있나(lights_setup.ps1 · 확실).
    하드웨어 읽기(LENOVO_LIGHTING_DATA)는 덧붙이는 정보 — 11-20 같은 PC 에서 02:17 엔 읽히고 03:5x 엔 «액세스 거부»였다 → 못 읽으면 적지 않음(모름)."""
    out = {'logo_light': task_exists(c['lights']['off_task']) and task_exists(c['lights']['restore_task'])}
    raw = _ps(r"try { Get-WmiObject -Namespace root\WMI -Class LENOVO_LIGHTING_DATA -ErrorAction Stop | "
              "Where-Object { $_.State_Type_Num -gt 0 } | ForEach-Object { $_.Lighting_Id }; 'ok' } catch { 'denied' }").split()
    if 'ok' in raw:
        have = {int(x) for x in raw if x.isdigit()}
        out['logo_light_hw'] = bool(have & {3, 4})
    return out


def probe(write=True):
    c = config()
    caps = dict(power_caps())
    try:
        sys.path.insert(0, HERE)
        import dgpu
        g = dgpu.find_dgpu() if IS_WIN else None
    except Exception:  # noqa: BLE001
        g = None
    caps['dgpu_nvidia'] = bool(g) and os.path.exists(dgpu.SMI)
    caps['phone_server'] = phone_server()
    caps['media'] = IS_WIN and sys.getwindowsversion().build >= 17763
    caps['ecoqos'] = IS_WIN and sys.getwindowsversion().build >= 22000
    caps['energy_meter'] = IS_WIN and energy_meter()
    caps.update(lights_caps(c) if IS_WIN else {'logo_light': False})
    out = {'at': now(), 'by': 'self_sleep', 'caps': caps}
    if write:
        d = _jload(DEVICE, {})
        d = d if isinstance(d, dict) else {}
        d.setdefault('schema', 1)
        merged = dict(d.get('caps') or {})
        merged.update(caps)
        d['caps'] = merged
        d['at'] = out['at']
        _jsave(DEVICE, d)
        # 기기 고유 값(장치 경로)은 git 밖 상태 폴더에만
        m = mem()
        m['dgpu_inst'] = g
        save_mem(m)
    return out


# ───────── 하는 일 ─────────
def _ps(cmd, timeout=30):
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-Command', cmd], capture_output=True, timeout=timeout, creationflags=NOWIN)
        return r.stdout.decode('utf-8', 'replace')
    except (OSError, subprocess.SubprocessError):
        return ''


def task_exists(name):
    try:
        return subprocess.run(['schtasks', '/Query', '/TN', name], capture_output=True, timeout=30, creationflags=NOWIN).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def run_task(name):
    try:
        return subprocess.run(['schtasks', '/Run', '/TN', name], capture_output=True, timeout=30, creationflags=NOWIN).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def mutex_exists(name):
    """다른 감시가 떠 있나(예 옛 gpu_guard = Local\\brain_gpu_guard) — 떠 있으면 겹치는 일을 그쪽에 맡긴다."""
    if not IS_WIN:
        return False
    h = ctypes.windll.kernel32.OpenMutexW(0x00100000, False, name)   # SYNCHRONIZE
    if h:
        ctypes.windll.kernel32.CloseHandle(h)
        return True
    return False


class PPT(ctypes.Structure):   # PROCESS_POWER_THROTTLING_STATE
    _fields_ = [('Version', wintypes.ULONG), ('ControlMask', wintypes.ULONG), ('StateMask', wintypes.ULONG)]


def set_ecoqos(pid, on):
    """그 프로세스에 효율 모드(EcoQoS · 실행 속도 낮춤)를 걸거나(on) 윈도 판단으로 되돌린다(off). 같은 사용자 프로세스만 된다."""
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = wintypes.HANDLE
    h = k32.OpenProcess(0x0200, False, pid)          # PROCESS_SET_INFORMATION
    if not h:
        return False
    try:
        st = PPT(1, 0x1, 0x1 if on else 0x0)          # PROCESS_POWER_THROTTLING_EXECUTION_SPEED
        if not on:
            st.ControlMask = 0                         # 되돌림 = 윈도가 정함
        k32.SetProcessInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        return bool(k32.SetProcessInformation(h, 4, ctypes.byref(st), ctypes.sizeof(st)))   # ProcessPowerThrottling
    finally:
        k32.CloseHandle(h)


class LUID_AND_ATTR(ctypes.Structure):    # LUID = DWORD + LONG(4바이트 맞춤 · 64비트 정수로 두면 자리가 어긋남)
    _fields_ = [('Low', wintypes.DWORD), ('High', wintypes.LONG), ('Attributes', wintypes.DWORD)]


class TOKEN_PRIVS(ctypes.Structure):
    _fields_ = [('Count', wintypes.DWORD), ('Privileges', LUID_AND_ATTR * 1)]


def shutdown_privilege():
    """SetSuspendState 는 SeShutdownPrivilege 가 «켜져» 있어야 한다(사용자 토큰에 있되 꺼져 있음) — 이 프로세스에서만 켠다. 켜졌으면 True."""
    a32, k32 = ctypes.WinDLL('advapi32', use_last_error=True), ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    a32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    tok = wintypes.HANDLE()
    if not a32.OpenProcessToken(k32.GetCurrentProcess(), 0x0020 | 0x0008, ctypes.byref(tok)):   # ADJUST_PRIVILEGES | QUERY
        return False
    try:
        la = LUID_AND_ATTR(0, 0, 0x2)                                                # SE_PRIVILEGE_ENABLED
        if not a32.LookupPrivilegeValueW(None, 'SeShutdownPrivilege', ctypes.byref(la)):   # LUID 가 앞 8바이트
            return False
        la.Attributes = 0x2
        tp = TOKEN_PRIVS(1, (LUID_AND_ATTR * 1)(la))
        ctypes.set_last_error(0)
        a32.AdjustTokenPrivileges.argtypes = [wintypes.HANDLE, wintypes.BOOL, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
        ok = a32.AdjustTokenPrivileges(tok, False, ctypes.byref(tp), 0, None, None)
        return bool(ok) and ctypes.get_last_error() == 0   # 1300 = 그 권한이 토큰에 없음
    finally:
        k32.CloseHandle(tok)


def suspend(hibernate):
    """최대 절전(hibernate=True) 또는 절전 — 윈도 설정은 바꾸지 않고 «한다»."""
    try:
        shutdown_privilege()
        return bool(ctypes.WinDLL('powrprof').SetSuspendState(bool(hibernate), False, False))
    except OSError:
        return False


# ───────── 재기(읽기만) ─────────
def battery_w():
    """배터리일 때 방전 W(BatteryStatus.DischargeRate · 전원 연결이면 None) — 들어감·나옴·끈 뒤 기록용(옛 gpu_guard 와 같은 칸)."""
    out = _ps("$b=Get-CimInstance -Namespace root\\wmi -ClassName BatteryStatus | Select-Object -First 1; if (-not $b.PowerOnline) { $b.DischargeRate }").strip()
    return round(int(out) / 1000, 1) if out.isdigit() else None


def sample(secs=10):
    """secs 초 동안 1초마다: 패키지 전력(W · RAPL) · CPU 이용률(%) · 배터리 방전(W · 배터리일 때) — 평균."""
    ps = ("$p=@('\\Energy Meter(*)\\Power','\\Processor Information(_Total)\\% Processor Utility');"
          "Get-Counter -Counter $p -SampleInterval 1 -MaxSamples {N} -ErrorAction SilentlyContinue | ForEach-Object {"
          " $s=$_.CounterSamples; $pk=($s | Where-Object { $_.Path -like '*_pkg)\\power' } | Select-Object -First 1).CookedValue;"
          " $u=($s | Where-Object { $_.Path -like '*processor utility' } | Select-Object -First 1).CookedValue; \"$pk`t$u\" }").replace('{N}', str(max(1, int(secs))))
    rows = []
    for ln in _ps(ps, timeout=secs + 40).splitlines():
        a = ln.strip().split('\t')
        try:
            rows.append((float(a[0]) / 1000 if a[0] else None, float(a[1])))
        except (ValueError, IndexError):
            pass
    pk = [r[0] for r in rows if r[0] is not None]
    cpu = [r[1] for r in rows]
    bat = _ps("$b=Get-CimInstance -Namespace root\\wmi -ClassName BatteryStatus | Select-Object -First 1; if (-not $b.PowerOnline) { $b.DischargeRate }").strip()
    return {'n': len(rows), 'pkg_w': round(sum(pk) / len(pk), 2) if pk else None, 'pkg_max_w': round(max(pk), 2) if pk else None,
            'cpu_pct': round(sum(cpu) / len(cpu), 1) if cpu else None,
            'battery_w': round(int(bat) / 1000, 1) if bat.isdigit() else None}


def measure(secs=30):
    out = {'at': now(), 'secs': secs}
    try:
        sys.path.insert(0, HERE)
        import dgpu
        g = dgpu.find_dgpu()
        out['dgpu'] = dgpu.dstate(g) if g else None
    except Exception:  # noqa: BLE001
        out['dgpu'] = None
    out.update(sample(secs))
    return out


# ───────── 서버만 남김(자체 최대 절전 · 사용자 11-20 «최대절전과 유사하지만 서버만 살리게») ─────────
# 배터리 + 덮개 닫힘이 «재움» 분 이어지고 «재우는 꼴» = 서버만 남김이면 윈도는 재우지 않고 폰 서버·Tailscale·와이파이만 남긴다.
# 칸마다 따로: serve_rc(원격·쉬는 세션 닫음) · serve_defer(무거운 배경 일 멈춤) · serve_cpu(배터리 프로세서 최대 상태 낮춤) ·
# serve_guard(배터리 %·시간을 넘으면 진짜 최대 절전). 덮개 열림·전원 연결·화면 켜짐·사람 입력이면 바로 나옴(되돌림).
SERVE_CPU_MIN = 10.0            # 한 코어 기준 % — 두 번 잇달아 넘는 배경 프로세스만 멈춤


def battery_pct():
    """배터리 % (GetSystemPowerStatus) · 모르면 None."""
    class SPS(ctypes.Structure):
        _fields_ = [('ac', ctypes.c_ubyte), ('flag', ctypes.c_ubyte), ('pct', ctypes.c_ubyte), ('sys', ctypes.c_ubyte),
                    ('life', ctypes.c_ulong), ('full', ctypes.c_ulong)]
    s = SPS()
    try:
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)) or s.pct == 255:
            return None
    except OSError:
        return None
    return int(s.pct)


def procmax_get():
    """배터리(DC) «최대 프로세서 상태» % — powercfg /q · 못 읽으면 None."""
    try:
        r = subprocess.run(['powercfg', '/q', 'SCHEME_CURRENT', 'SUB_PROCESSOR', 'PROCTHROTTLEMAX'], capture_output=True, timeout=15, creationflags=NOWIN)
    except (OSError, subprocess.SubprocessError):
        return None
    import re as _re
    v = _re.findall(rb'0x([0-9a-fA-F]{8})\s*$', r.stdout, _re.M)
    return int(v[-1], 16) if len(v) >= 2 else None        # 마지막 = DC 값


def procmax_set(pct):
    """배터리(DC) «최대 프로세서 상태»를 pct 로 — 관리자 불필요(11-20 같은 값 다시 쓰기 rc=0 실측) · 지금 구성표에 바로 적용."""
    try:
        a = subprocess.run(['powercfg', '/setdcvalueindex', 'SCHEME_CURRENT', 'SUB_PROCESSOR', 'PROCTHROTTLEMAX', str(int(pct))],
                           capture_output=True, timeout=15, creationflags=NOWIN)
        b = subprocess.run(['powercfg', '/setactive', 'SCHEME_CURRENT'], capture_output=True, timeout=15, creationflags=NOWIN)
        return a.returncode == 0 and b.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _ntdll(fn, pid):
    k32 = ctypes.windll.kernel32
    k32.OpenProcess.restype = wintypes.HANDLE
    h = k32.OpenProcess(0x0800, False, int(pid))          # PROCESS_SUSPEND_RESUME
    if not h:
        return False
    try:
        return getattr(ctypes.windll.ntdll, fn)(wintypes.HANDLE(h)) == 0
    finally:
        k32.CloseHandle(wintypes.HANDLE(h))


def proc_pause(pid, on):
    """프로세스 잠시 멈춤(on) · 다시 돌림(off) — NtSuspendProcess/NtResumeProcess · 같은 사용자 프로세스만."""
    return _ntdll('NtSuspendProcess' if on else 'NtResumeProcess', pid)


def _create_time(pid):
    try:
        import psutil
        return psutil.Process(pid).create_time()
    except Exception:  # noqa: BLE001
        return None


def kill_tree(pid, created=None):
    """pid 와 그 아래를 끔 — 시작 시각이 다르면(pid 다시 쓰임) 안 끔."""
    if created is not None and _create_time(pid) != created:
        return False
    try:
        return subprocess.run(['taskkill', '/T', '/F', '/PID', str(int(pid))], capture_output=True, timeout=30, creationflags=NOWIN).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def rc_procs():
    """이 PC 의 Claude 원격 제어(claude … remote-control) 프로세스 [(pid, 시작 시각)]."""
    try:
        import psutil
    except ImportError:
        return []
    out = []
    for p in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
        cmd = ' '.join(p.info.get('cmdline') or [])
        if (p.info.get('name') or '').lower() == 'claude.exe' and 'remote-control' in cmd:
            out.append((p.info['pid'], p.info.get('create_time')))
    return out


def idle_sessions():
    """일 없는 Claude 세션 [(pid, 이름)] — 주인 장부(own.sessions · ~/.claude/sessions) · own.py 가 없으면 []."""
    try:
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        import own
        ss = own.sessions()
    except Exception:  # noqa: BLE001
        return []
    return [(pid, (s.get('name') or '')[:30]) for pid, s in ss.items() if s.get('alive') and not s.get('busy')]


def busy_owner_pids():
    """일하는 Claude 세션 pid 들 — 그 아래 배경 일은 안 멈춘다."""
    try:
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        import own
        return {pid for pid, s in own.sessions().items() if s.get('alive') and s.get('busy')}
    except Exception:  # noqa: BLE001
        return set()


def rc_open():
    """원격 제어를 다시 켬 — 폰 서버에 POST /v1/rc(서버가 고정 명령으로 띄움 · 로그인 끊김이면 서버가 거절)."""
    import urllib.error
    import urllib.request
    st = os.path.join(SYS, '_index', 'server')
    try:
        tok = open(os.path.join(st, 'token'), encoding='utf-8').read().strip()
        port = int((_jload(os.path.join(st, 'config.json'), {}) or {}).get('port') or 8377)
    except (OSError, ValueError, TypeError):
        return False
    req = urllib.request.Request(f'http://127.0.0.1:{port}/v1/rc', data=b'{}', method='POST',
                                 headers={'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return bool(json.loads(r.read() or b'{}').get('ok'))
    except urllib.error.HTTPError as e:
        return 'http %d' % e.code
    except Exception:  # noqa: BLE001
        return False


def serve_params():
    try:
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        import options
        cpu = options.params("power.serve_cpu", "high")
        g = options.params("power.serve_guard", "high")
    except Exception:  # noqa: BLE001
        cpu, g = {}, {}
    return {'cpu_pct': int(cpu.get('pct', 50)), 'guard_pct': int(g.get('pct', 25)), 'guard_hours': float(g.get('hours', 3))}


def phone_server():
    """폰 서버가 이 볼트에 있나(mobility 모듈) — 없으면 «서버만 남김»은 뜻이 없어 최대 절전으로."""
    return os.path.isfile(os.path.join(VAULT, '.claude', 'skills', 'mobility', 'scripts', 'server.py'))


SERVE_OPS = {'battery_pct': battery_pct, 'procmax_get': procmax_get, 'procmax_set': procmax_set, 'pause': proc_pause,
             'kill_tree': kill_tree, 'rc_procs': rc_procs, 'idle_sessions': idle_sessions, 'busy_owners': busy_owner_pids,
             'rc_open': rc_open, 'params': serve_params}


# ───────── 감시 ─────────
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


LID = GUID.of('ba3e0f4d-b817-4094-a2d1-d56379e6a0f3')        # GUID_LIDSWITCH_STATE_CHANGE (0 닫힘)
DISPLAY = GUID.of('6fe69556-704a-47a0-8f24-c28d936fda47')    # GUID_CONSOLE_DISPLAY_STATE (0 꺼짐 · 1 켜짐 · 2 어둡게)
ACDC = GUID.of('5d3e9a59-e9d5-4b00-a6bd-ff34ff516548')       # GUID_ACDC_POWER_SOURCE (0 전원 · 1 배터리 · 2 UPS)
WM_POWERBROADCAST, PBT_SETTING, WM_TIMER = 0x0218, 0x8013, 0x0113
PBT_APMSUSPEND, PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC = 0x0004, 0x0007, 0x0012   # 잠듦 · 사람이 깨움 · 저절로 깸(타이머 등)


class PBS(ctypes.Structure):
    _fields_ = [('guid', GUID), ('len', wintypes.DWORD), ('data', ctypes.c_ubyte * 4)]


class Sleeper:
    def __init__(self, c, lv_fn=levels, act=True):
        self.c, self.lv_fn, self.act = c, lv_fn, act
        self.st = {'lid_closed': False, 'display_off': False, 'on_battery': False, 'battery_lid_since': None}
        self.active = None            # 들어간 까닭
        self.done_then = False
        self.busy = False
        self.next_ok = 0.0
        self.media = None
        self.media_at = 0.0
        self.eco = {}                 # pid → 걸어 둔 프로세스(이름 · 시작 시각)
        self.cpu_prev = {}
        self.killed = []
        self.memo = mem()
        self.gpu = self.memo.get('dgpu_inst')
        self.lv = {}
        self.stale_lights = True      # 첫 순찰에 한 번 — 들어가 있지 않은데 «꺼 둔 조명»이 남았으면 되돌림
        self.hold = False             # 깨어 있음을 쥐고 있나
        self.resume_hold = False      # 무인으로 깬 뒤 사람이 오기 전
        self.resume_input = None      # 그때의 마지막 입력 시각(바뀌면 사람이 옴)
        self.set_awake = set_awake
        self.clock = time.time        # 시험이 바꿈
        self.input_tick = (last_input_tick if IS_WIN else (lambda: 0))
        self.count_input = None
        self.serving = None
        self.ops = dict(SERVE_OPS)    # 시험이 바꿈
        self.has_server = phone_server()

    # 깨어 있음
    def apply_hold(self):
        if self.resume_hold and self.resume_input is not None and IS_WIN and last_input_tick() != self.resume_input:
            self.resume_hold = False          # 사람이 만짐 — 이제 보통 규칙
            log('resume_user')
        want_hold = module_on() and hold_wanted({**self.st, 'serving': bool(self.serving)}, self.lv, self.resume_hold)
        if want_hold != self.hold:
            ok = self.set_awake(want_hold)
            self.hold = want_hold
            log('awake', on=want_hold, ok=ok, why=('resume' if self.resume_hold and self.lv.get('power.awake_ac') != 'high' else 'ac')
                if want_hold else ('battery' if self.st.get('on_battery') else 'off'))

    def on_power(self, wp):
        """잠듦·깸 알림 — 원치 않은 잠을 기록하고, 저절로 깨면(타이머·수집 예약) 바로 깨어 있음을 다시 쥔다."""
        if wp == PBT_APMSUSPEND:
            log('suspend', on_battery=self.st.get('on_battery'), lid_closed=self.st.get('lid_closed'), hold=self.hold,
                ours=bool(self.done_then))
        elif wp == PBT_APMRESUMEAUTOMATIC:
            self.resume_hold = True
            self.resume_input = last_input_tick() if IS_WIN else None
            self.lv = self.lv_fn() if module_on() else self.lv
            self.hold = False                 # 다시 쥔다(잠든 사이 상태가 남았어도 한 번 더)
            log('resume_auto', on_battery=self.st.get('on_battery'))
            self.apply_hold()
        elif wp == PBT_APMRESUMESUSPEND:
            self.resume_hold = False
            log('resume_user')
            self.apply_hold()

    # 서버만 남김
    def serve_enter(self):
        lv, ops = self.lv, self.ops
        sv = {'since': self.clock(), 'rc': False, 'closed': [], 'paused': {}, 'cpu_prev': None, 'cpu_samples': {}}
        self.serving = sv
        if lv.get('power.serve_rc') == 'high':
            rc = ops['rc_procs']()
            rcs = {p for p, _ in rc}                 # 끄기 전에 — 원격이 세션 목록에도 있으면 두 번 끄지 않게
            for pid, created in rc:
                sv['rc'] = bool(ops['kill_tree'](pid, created)) or sv['rc']
            for pid, name in ops['idle_sessions']():
                if pid not in rcs and pid != os.getpid() and ops['kill_tree'](pid, None):
                    sv['closed'].append(name)
        if lv.get('power.serve_cpu') == 'high':
            prev = ops['procmax_get']()
            pct = ops['params']()['cpu_pct']
            if prev is not None and prev > pct and ops['procmax_set'](pct):
                sv['cpu_prev'] = prev
                m = mem()
                m['procmax_prev'] = prev          # 감시가 죽어도 다음 시작에 되돌림
                save_mem(m)
        self.apply_hold()                          # 배터리여도 깨어 있음을 쥠(윈도 유휴 절전이 서버를 재우지 않게)
        _jsave(ACTIVE, {'since': now(), 'why': 'serve'})
        log('serve', what='enter', rc_closed=sv['rc'], sessions_closed=sv['closed'], cpu=(sv['cpu_prev'], ops['params']()['cpu_pct'])
            if sv['cpu_prev'] is not None else None)

    def serve_tick(self):
        sv, lv, ops = self.serving, self.lv, self.ops
        if self.clock() - sv.get('w_at', sv['since']) >= 600:      # 10분마다 배터리 방전 W(실기 측정 · 서버만 남김의 값)
            sv['w_at'] = self.clock()
            log('serve', what='w', w=battery_w(), battery_pct=ops['battery_pct']())
        if lv.get('power.serve_defer') == 'high':
            self.serve_defer_round()
        if lv.get('power.serve_guard') == 'high':
            p = ops['params']()
            pct = ops['battery_pct']()
            hours = (self.clock() - sv['since']) / 3600
            if (pct is not None and pct <= p['guard_pct']) or hours >= p['guard_hours']:
                log('serve', what='guard', battery_pct=pct, hours=round(hours, 2))
                self.serve_exit(quiet=True)
                if self.act:
                    ok = suspend(power_caps().get('s4', True))
                    log('then_done', ok=ok, what='hibernate')
                return True
        return False

    def serve_defer_round(self):
        """CPU 를 두 번 잇달아 SERVE_CPU_MIN 넘게 먹는 배경 프로세스를 멈춤 — 보호 목록·윈도·일하는 세션 아래·이미 멈춘 것은 뺌."""
        try:
            import psutil
        except ImportError:
            return
        sv, ops = self.serving, self.ops
        busy = ops['busy_owners']()
        prot = {x.lower() for x in self.c['protect']} | {'claude.exe'}
        t = time.time()
        for p in psutil.process_iter(['pid', 'name', 'exe', 'cpu_times', 'create_time', 'ppid']):
            i = p.info
            pid = i['pid']
            if pid in sv['paused'] or pid == os.getpid() or not i.get('cpu_times'):
                continue
            name, exe = (i.get('name') or '').lower(), (i.get('exe') or '').lower()
            if not name or name in prot or not exe or exe.startswith('c:\\windows\\'):
                continue
            tot = i['cpu_times'].user + i['cpu_times'].system
            prev = sv['cpu_samples'].get(pid)
            sv['cpu_samples'][pid] = (tot, t, i.get('create_time'), prev[3] if prev else 0.0)
            if not prev or prev[2] != i.get('create_time'):
                continue
            core = (tot - prev[0]) / max(t - prev[1], 1e-3) * 100
            sv['cpu_samples'][pid] = (tot, t, i.get('create_time'), core)
            if core < SERVE_CPU_MIN or prev[3] < SERVE_CPU_MIN:
                continue
            try:
                anc = {a.pid for a in p.parents()}
            except Exception:  # noqa: BLE001
                anc = set()
            if anc & busy:
                continue
            if ops['pause'](pid, True):
                sv['paused'][pid] = (name, i.get('create_time'))
                log('serve', what='pause', name=name, pid=pid, core=round(core, 1))

    def serve_exit(self, quiet=False):
        sv, ops = self.serving, self.ops
        if not sv:
            return
        self.serving = None
        for pid, (name, created) in list(sv['paused'].items()):
            if _create_time(pid) == created:
                ops['pause'](pid, False)
        if sv['cpu_prev'] is not None:
            ok = ops['procmax_set'](sv['cpu_prev'])
            if ok:
                m = mem()
                m.pop('procmax_prev', None)
                save_mem(m)
        rc = ops['rc_open']() if sv['rc'] else None
        self.apply_hold()                          # 배터리면 놓음
        log('serve', what='exit', resumed=len(sv['paused']), cpu_back=sv['cpu_prev'], rc_open=rc, quiet=quiet)

    # 상태 알림
    def on_setting(self, guid, v):
        self.seen = getattr(self, 'seen', set()) | {'lid' if guid == LID else 'display' if guid == DISPLAY else 'acdc' if guid == ACDC else '?'}
        if guid == LID:
            self.st['lid_closed'] = v == 0
        elif guid == DISPLAY:
            self.st['display_off'] = v == 0
        elif guid == ACDC:
            self.st['on_battery'] = v != 0
        else:
            return
        self.count_check()
        self.tick()

    def count_check(self):
        """«배터리로 닫아 둔 뒤 재움»의 셈 — 덮개 닫힘 + 배터리 + 화면 꺼짐이 이어지는 동안만 센다.
        덮개 열림·전원 연결·화면 켜짐(바깥 모니터)·사람 입력 중 하나라도 오면 세던 시간을 버린다(사용자 11-20: 충전기를 꽂으려고
        45도쯤 닫았다 꽂고 다시 열면 최대 절전이라 다시 켜야 했다 — 그래서 윈도 덮개 동작을 «아무 것도 안 함»으로 둠).
        반쯤 닫혀 센서가 «닫힘»을 안 내면 아예 세지 않는다."""
        counting = self.st['lid_closed'] and self.st['on_battery'] and self.st['display_off']
        t = self.clock()
        if counting and self.st['battery_lid_since'] is None:
            self.st['battery_lid_since'] = t
            self.count_input = self.input_tick()
            log('count', what='start')
        elif counting and self.input_tick() != self.count_input:
            self.st['battery_lid_since'] = t           # 덮개 닫힌 채 사람이 만짐(바깥 키보드 등) — 처음부터 다시
            self.count_input = self.input_tick()
            self.done_then = False
            if self.serving:
                self.serve_exit()
            log('count', what='input')
        elif not counting and self.st['battery_lid_since'] is not None:
            self.st['battery_lid_since'] = None
            self.done_then = False
            if self.serving:
                self.serve_exit()                 # 덮개 열림·전원 연결·화면 켜짐 — 바로 나옴
            log('count', what='drop', lid_closed=self.st['lid_closed'], on_battery=self.st['on_battery'], display_off=self.st['display_off'])
        elif not counting:
            self.done_then = False

    def seen_all(self):
        """덮개·화면 알림을 받았나(등록하자마자 윈도가 지금 값을 보낸다) — 그 전엔 «들어가 있지 않음»을 믿지 않는다."""
        return {'lid', 'display'} <= getattr(self, 'seen', set())

    def gpu_guard_running(self):
        return mutex_exists('Local\\brain_gpu_guard')

    def tick(self):
        if not module_on():
            why, then = None, None
        else:
            self.lv = self.lv_fn()
            if self.st['battery_lid_since'] is not None:
                self.count_check()                 # 순찰마다 입력을 본다(알림이 없는 사이에도)
            why, then = want({**self.st, 'now': self.clock(), 'phone_server': self.has_server}, self.lv,
                             then_minutes('high'))
        self.apply_hold()
        if self.serving and not why:
            why = 'serve'                          # 서버만 남김 중에는 자체 절전 일(외장 그래픽 앱·미디어·조명)도 함께
        if why and not self.active:
            self.enter(why)
        elif not why and self.active:
            self.exit()
        if then and not self.done_then:
            self.done_then = True
            log('then', what=then, after_min=then_minutes('high'))
            if then == 'serve':
                if self.act:
                    self.serve_enter()
                return
            if self.act:
                if self.active:
                    self.exit(quiet=True)       # 재우기 전에 되돌림 — 깬 뒤에 조명·효율 모드가 남지 않게
                ok = suspend(then == 'hibernate' and power_caps().get('s4', True))
                log('then_done', ok=ok)
            return
        if self.stale_lights and self.seen_all():
            self.stale_lights = False
            if not self.active and os.path.exists(self.c['lights']['prev']) and not self.gpu_guard_running():
                log('stale', note='꺼 둔 로고 조명 되돌림')
                self.lights('restore')
        if self.serving and self.serve_tick():
            return
        if self.active:
            self.during()

    def enter(self, why):
        self.active = why
        lv = self.lv
        share = self.gpu_guard_running()
        _jsave(ACTIVE, {'since': now(), 'why': why})
        log('enter', why=why, lv=lv, gpu_guard=share, w=battery_w())
        if lv.get('power.logo_light') == 'high' and not share:
            self.lights('off')

    def exit(self, quiet=False):
        if self.serving:
            self.serve_exit(quiet=True)
        why, self.active = self.active, None
        self.media_stop()
        for pid in list(self.eco):
            set_ecoqos(pid, False)
        n = len(self.eco)
        self.eco.clear()
        if self.lv.get('power.logo_light') == 'high' and not self.gpu_guard_running():
            self.lights('restore')
        self.relaunch()
        try:
            os.remove(ACTIVE)
        except OSError:
            pass
        if not quiet:
            log('exit', was=why, w=battery_w())

    def lights(self, mode):
        L = self.c['lights']
        if not task_exists(L['off_task' if mode == 'off' else 'restore_task']):
            return
        if mode == 'restore' and not os.path.exists(L['prev']):
            return
        log('lights', mode=mode, ok=run_task(L['off_task' if mode == 'off' else 'restore_task']))

    def during(self):
        lv, share = self.lv, self.gpu_guard_running()
        if lv.get('power.media') == 'high' and not share:
            self.media_start()
        if lv.get('power.dgpu_apps') == 'high' and not share and self.gpu and not self.busy and time.time() >= self.next_ok:
            sys.path.insert(0, HERE)
            import dgpu
            if dgpu.dstate(self.gpu) == 'D0':
                self.busy = True
                threading.Thread(target=self.hunt, args=(not self.c.get('dgpu_observe'),), daemon=True).start()

    # 효율 모드
    def ecoqos_round(self, only=None):
        import psutil
        samples, cur = [], {}
        for p in psutil.process_iter(['pid', 'name', 'exe', 'cpu_times', 'create_time']):
            i = p.info
            if only is not None and i['pid'] not in only:
                continue
            ct = i.get('cpu_times')
            if ct is None:
                continue
            cur[i['pid']] = (ct.user + ct.system, time.time(), i.get('create_time'))
            prev = self.cpu_prev.get(i['pid'])
            if prev and prev[2] == i.get('create_time'):
                cpu = (cur[i['pid']][0] - prev[0]) / max(cur[i['pid']][1] - prev[1], 1e-3) * 100
                samples.append({'pid': i['pid'], 'name': i['name'], 'exe': i.get('exe'), 'cpu': cpu, 'prev_cpu': prev[3] if len(prev) > 3 else 0})
                cur[i['pid']] = cur[i['pid']] + (cpu,)
        self.cpu_prev = cur
        me = {os.getpid(), os.getppid()}
        for pid in ecoqos_pick(samples, self.c, me):
            if pid in self.eco:
                continue
            ok = set_ecoqos(pid, True)
            name = next((s['name'] for s in samples if s['pid'] == pid), '?')
            if ok:
                self.eco[pid] = name
            log('ecoqos', name=name, pid=pid, ok=ok)

    # 미디어 멈춤 — 들어가 있는 동안 media_pause.ps1 하나가 3초마다 «재생 중» 세션을 멈춘다(나오면 끔 · 다시 재생하지 않음)
    def media_start(self):
        if (self.media and self.media.poll() is None) or time.time() - self.media_at < 60:
            return
        self.media_at = time.time()
        try:
            self.media = subprocess.Popen(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', MEDIA_PS, '-Parent', str(os.getpid())],
                                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=NOWIN)
        except OSError as e:
            self.media = None
            return log('error', what=f'미디어 멈춤 못 띄움 {e!r}'[:200])
        threading.Thread(target=self.media_read, args=(self.media,), daemon=True).start()

    def media_read(self, p):
        for line in p.stdout:
            try:
                d = json.loads(line.decode('utf-8', 'replace'))
            except ValueError:
                continue
            if 'app' in d:
                log('pause', app=d['app'], ok=d.get('ok'))
            elif 'err' in d:
                log('error', what=f'미디어 멈춤 {d["err"]}'[:200])

    def media_stop(self):
        if self.media and self.media.poll() is None:
            self.media.terminate()
        self.media = None
        self.media_at = 0.0

    # 외장 그래픽 깨우는 앱
    def hunt(self, act):
        import dgpu
        try:
            res = dgpu.analyze(self.c, memo=self.memo)
            if res is None:
                return log('error', what='nvidia-smi 못 부름')
            log('wake', who=[{k: r[k] for k in ('name', 'util', 'io_kbs', 'verdict', 'why')} for r in res])
            acted = False
            for r in res:
                if r['verdict'] != 'kill' or not self.active:
                    continue
                if not (act and self.act):
                    log('would_kill', name=r['name'], why=r['why'])
                    continue
                how = dgpu.kill(r, self.c, memo=self.memo)
                acted = True
                cmd = dgpu.relaunch_cmd(r['name'], r['exe'], self.c, dgpu.run_entries())
                self.memo['killed'] = [k for k in self.memo.get('killed', []) if k['name'] != r['name']] + \
                    [{'name': r['name'], 'exe': r['exe'], 'cmd': cmd, 't': now()}]
                save_mem(self.memo)
                log('kill', name=r['name'], how=how, relaunch=bool(cmd))
            if acted:
                time.sleep(20)
                log('after', d=dgpu.dstate(self.gpu), w=battery_w())
            self.next_ok = time.time() + (0 if acted else self.c['backoff_s'])
        except Exception as e:  # noqa: BLE001 — 감시는 멈추지 않는다
            log('error', what=repr(e)[:200])
        finally:
            self.busy = False

    def relaunch(self):
        for k in self.memo.get('killed', []):
            if k.get('cmd') and self.act:
                try:
                    subprocess.Popen(k['cmd'], creationflags=NOWIN)
                    log('relaunch', name=k['name'], cmd=k['cmd'])
                except OSError as e:
                    log('error', what=f'다시 켜기 {k["name"]} {e!r}'[:200])
        self.memo['killed'] = []
        save_mem(self.memo)


def restore_stale(setter=None):
    """서버만 남김 중에 감시가 꺼졌으면(재시작·충돌) 배터리 프로세서 최대 상태를 되돌림 — 띄울 때마다."""
    m = mem()
    if m.get('procmax_prev') is None:
        return None
    ok = (setter or procmax_set)(m['procmax_prev'])
    log('stale', note='프로세서 최대 상태 되돌림', to=m['procmax_prev'], ok=ok)
    if ok:
        m.pop('procmax_prev', None)
        save_mem(m)
    return ok


def run():
    c = config()
    k32 = ctypes.windll.kernel32
    k32.CreateMutexW(None, False, 'Local\\brain_self_sleep')
    if k32.GetLastError() == 183:
        return print('이미 돎')
    probe()                                   # 기기가 바뀌었을 수 있다(외장 GPU·조명 작업) — 띄울 때마다 다시 잼
    # 지난번에 들어간 채 꺼졌으면(재시작·충돌) 신호를 지운다 — 효율 모드는 프로세스와 함께 사라지고 조명은 첫 «나옴»에서 되돌림
    restore_stale()
    if os.path.exists(ACTIVE):
        log('stale', note='들어간 채 꺼졌던 흔적 — 지움')
        try:
            os.remove(ACTIVE)
        except OSError:
            pass
    s = Sleeper(c)
    log('start', lv=levels(), gpu_guard=mutex_exists('Local\\brain_gpu_guard'))
    listen(s, c['poll_s'])


def listen(s, poll_s, seconds=None):
    """보이지 않는 창으로 덮개·화면·전원 알림을 받아 s.on_setting 에 넘기고 poll_s 마다 s.tick. seconds 를 주면 그만큼만(시험)."""
    k32 = ctypes.windll.kernel32
    u = ctypes.windll.user32
    cls = 'BrainSelfSleep%d' % (int(time.time() * 1000) % 100000)
    LRESULT = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    u.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    u.DefWindowProcW.restype = LRESULT

    def proc(h, msg, wp, lp):
        if msg == WM_POWERBROADCAST and wp == PBT_SETTING and lp:
            p = ctypes.cast(lp, ctypes.POINTER(PBS)).contents
            s.on_setting(p.guid, p.data[0])
            return 1
        if msg == WM_POWERBROADCAST and wp in (PBT_APMSUSPEND, PBT_APMRESUMESUSPEND, PBT_APMRESUMEAUTOMATIC):
            s.on_power(wp)
            return 1
        if msg == WM_TIMER:
            s.tick()
            return 0
        return u.DefWindowProcW(h, msg, wp, lp)
    wp = WNDPROC(proc)

    class WNDCLASS(ctypes.Structure):
        _fields_ = [('style', wintypes.UINT), ('proc', WNDPROC), ('cls', ctypes.c_int), ('wnd', ctypes.c_int), ('inst', wintypes.HINSTANCE),
                    ('icon', wintypes.HICON), ('cur', wintypes.HANDLE), ('bg', wintypes.HBRUSH), ('menu', wintypes.LPCWSTR), ('name', wintypes.LPCWSTR)]
    k32.GetModuleHandleW.restype = wintypes.HMODULE
    wc = WNDCLASS(0, wp, 0, 0, k32.GetModuleHandleW(None), None, None, None, None, cls)
    u.RegisterClassW(ctypes.byref(wc))
    u.CreateWindowExW.restype = wintypes.HWND
    u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    u.RegisterPowerSettingNotification.argtypes = [wintypes.HANDLE, ctypes.POINTER(GUID), wintypes.DWORD]
    u.RegisterPowerSettingNotification.restype = wintypes.HANDLE
    u.SetTimer.argtypes = [wintypes.HWND, ctypes.c_size_t, wintypes.UINT, wintypes.LPVOID]
    h = u.CreateWindowExW(0, cls, cls, 0, 0, 0, 0, 0, None, None, wc.inst, None)   # 보이지 않는 창(알림만)
    regs = [u.RegisterPowerSettingNotification(h, ctypes.byref(g), 0) for g in (LID, DISPLAY, ACDC)]   # 등록하자마자 윈도가 지금 값을 보낸다
    u.SetTimer(h, 1, int(poll_s * 1000), None)
    msg = wintypes.MSG()
    if seconds is None:
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))
        return
    end = time.time() + seconds
    while time.time() < end:                       # 시험 — seconds 동안만 메시지를 꺼내 처리
        while u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.05)
    u.UnregisterPowerSettingNotification.argtypes = [wintypes.HANDLE]
    for r in regs:
        u.UnregisterPowerSettingNotification(r)
    u.DestroyWindow(h)


def now_state(seconds=2.0):
    """지금 덮개·화면·전원 — 감시와 같은 알림 길로(등록하면 윈도가 지금 값을 보낸다). 들어가지도 아무것도 하지도 않는다."""
    s = Sleeper(config(), lv_fn=lambda: {}, act=False)
    s.tick = lambda: None
    listen(s, 60, seconds)
    out = {k: v for k, v in s.st.items() if k != 'battery_lid_since'}
    out['seen'] = sorted(getattr(s, 'seen', set()))
    return out


# ───────── 연습(drill) ─────────
def _burner(secs):
    return subprocess.Popen([sys.executable, '-c', 'import time\nt=time.time()+%d\nwhile time.time()<t: pass' % secs], creationflags=NOWIN)


def drill(secs=20, ping_url=None, load=1):
    """덮개를 닫지 않고 연습 — 시험 부하(한 코어를 태우는 파이썬) 하나를 띄워 «자체 절전 전»을 재고,
    감시와 같은 효율 모드 판단(ecoqos_round)을 그 부하에만 걸어 «자체 절전 뒤»를 잰다. 미디어·조명·앱 끄기는 안 한다(act=False).
    ping_url 을 주면 들어가 있는 동안 서버에 닿는지 본다."""
    import urllib.error
    import urllib.request
    c = config()
    c['protect'] = [x for x in c['protect'] if x not in ('python.exe', 'py.exe')]   # 시험 부하(python.exe)를 고를 수 있게 — 이 연습에서만
    out = {'at': now(), 'secs': secs}
    out['idle'] = sample(secs)
    bs = [_burner(secs * 4 + 40) for _ in range(max(1, load))]
    pids = {b.pid for b in bs}
    try:
        time.sleep(2)
        out['before'] = sample(secs)
        s = Sleeper(c, lv_fn=lambda: {k: 'high' for k in LEVEL_IDS}, act=False)
        s.lv = s.lv_fn()
        for _ in range(3):                         # 감시와 같은 판단 — 두 번 잇달아 넘어야 건다
            s.ecoqos_round(only=pids)
            time.sleep(3)
        out['ecoqos_set'] = len(s.eco)
        out['after'] = sample(secs)
        if ping_url:
            t0 = time.time()
            try:
                with urllib.request.urlopen(ping_url, timeout=10) as r:
                    out['ping'] = {'code': r.status, 'ms': round((time.time() - t0) * 1000)}
            except urllib.error.HTTPError as e:      # 401 등 = 서버까지 닿음(열쇠 없이 부름)
                out['ping'] = {'code': e.code, 'ms': round((time.time() - t0) * 1000)}
            except Exception as e:  # noqa: BLE001
                out['ping'] = {'err': repr(e)[:120]}
        for pid in list(s.eco):
            set_ecoqos(pid, False)
        out['undone'] = sample(secs)              # 되돌린 뒤 — 효과가 효율 모드 때문인지(되돌리면 다시 올라야)
    finally:
        for b in bs:
            b.kill()
    return out


# ───────── 보기 ─────────
def tail(n=12):
    try:
        with open(LOG, encoding='utf-8') as f:
            return [json.loads(x) for x in f.readlines()[-n:]]
    except (OSError, ValueError):
        return []


def report(days=3):
    """지난 days 일 — 들어감(까닭별)·외장 그래픽을 깨운 앱·끈 것·껐을 것·멈춘 미디어·서버만 남김·재움(옛 gpu_guard report)."""
    since = (dt.datetime.now() - dt.timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    out = {'days': days, 'enter': {}, 'woke_by': {}, 'killed': {}, 'would_kill': {}, 'paused_media': {}, 'serve': 0, 'slept': 0, 'suspend': 0}
    try:
        lines = open(LOG, encoding='utf-8').read().splitlines()
    except OSError:
        lines = []
    for ln in lines:
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        if e.get('t', '') < since:
            continue
        ev = e.get('ev')
        bump = lambda k, n: out[k].__setitem__(n, out[k].get(n, 0) + 1)  # noqa: E731
        if ev == 'enter':
            bump('enter', e.get('why') or '?')
        elif ev == 'wake':
            for w in e.get('who') or [{'name': '(모름)'}]:
                bump('woke_by', w.get('name') or '?')
        elif ev == 'kill':
            bump('killed', e.get('name') or '?')
        elif ev == 'would_kill':
            bump('would_kill', e.get('name') or '?')
        elif ev == 'pause':
            bump('paused_media', e.get('app') or '?')
        elif ev == 'serve' and e.get('what') == 'enter':
            out['serve'] += 1
        elif ev == 'then_done':
            out['slept'] += 1
        elif ev == 'suspend':
            out['suspend'] += 1
    return out


def status():
    es = system_execution_state()
    return {'active': _jload(ACTIVE, None), 'levels': levels(),
            'system_required_held': None if es is None else bool(es & ES_SYSTEM_REQUIRED), 'device': _jload(DEVICE, {}).get('caps'),
            'running': mutex_exists('Local\\brain_self_sleep'), 'gpu_guard_running': mutex_exists('Local\\brain_gpu_guard'),
            'recent': tail()}


def main():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8')
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(prog='self_sleep.py')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('run')
    p = sub.add_parser('probe')
    p.add_argument('--json', action='store_true')
    p.add_argument('--dry', action='store_true', help='device.json 에 쓰지 않음')
    sub.add_parser('status')
    rp = sub.add_parser('report')
    rp.add_argument('--days', type=int, default=3)
    sub.add_parser('now', help='덮개·화면·전원 지금 값(알림 2초 · 아무것도 안 함)')
    m = sub.add_parser('measure')
    m.add_argument('--secs', type=int, default=30)
    d = sub.add_parser('trial')
    d.add_argument('--secs', type=int, default=20)
    d.add_argument('--ping', default=None)
    d.add_argument('--load', type=int, default=1, help='시험 부하 수(한 코어씩)')
    a = ap.parse_args()
    if a.cmd == 'run':
        return run()
    if a.cmd == 'probe':
        r = probe(write=not a.dry)
        return print(json.dumps(r, ensure_ascii=False) if a.json else
                     '\n'.join('%s %s' % ('✓' if v else '·', k) for k, v in r['caps'].items()))
    if a.cmd == 'now':
        return print(json.dumps(now_state(), ensure_ascii=False))
    if a.cmd == 'report':
        return print(json.dumps(report(a.days), ensure_ascii=False, indent=1))
    if a.cmd == 'status':
        return print(json.dumps(status(), ensure_ascii=False, indent=1))
    if a.cmd == 'measure':
        return print(json.dumps(measure(a.secs), ensure_ascii=False))
    if a.cmd == 'trial':
        return print(json.dumps(drill(a.secs, a.ping, a.load), ensure_ascii=False))


if __name__ == '__main__':
    main()
