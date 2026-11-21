"""자체 절전 순수 부분·선언 시험 — 프로세스를 끄거나 윈도 설정을 바꾸거나 PC 를 재우지 않는다.
    py -3 test_self_sleep.py"""
import json
import os
import sys
import tempfile

T = tempfile.mkdtemp(prefix='self_sleep_test_')
os.environ['SELF_SLEEP_STATE'] = T
os.environ['SELF_SLEEP_DEVICE'] = os.path.join(T, 'device.json')
os.environ['SELF_SLEEP_OLD_CONFIG'] = os.path.join(T, 'old_gpu_guard.json')
with open(os.environ['SELF_SLEEP_OLD_CONFIG'], 'w', encoding='utf-8') as f:     # 이 PC 의 옛 gpu_guard 설정과 같은 꼴(11-13 사용자 «Steam 은 다시 안 켬»)
    f.write('{"relaunch": {"steam.exe": "never"}, "mode": "act"}')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import self_sleep as s  # noqa: E402
import dgpu  # noqa: E402

VAULT = s.VAULT
sys.path.insert(0, os.path.join(VAULT, '3_시스템'))
import options  # noqa: E402

s.battery_w = lambda: None      # 시험: 들어감·나옴 기록의 배터리 W(파워셸) 안 부름

res = []


def ok(name, cond, val=''):
    res.append(bool(cond))
    print(('통과' if cond else '실패'), name, val)


ON = {k: 'high' for k in s.LEVEL_IDS}
NOW = 1_000_000.0
B = lambda **k: {'lid_closed': False, 'display_off': False, 'on_battery': False, 'battery_lid_since': None, 'now': NOW, **k}  # noqa: E731

# ── 들어가는 때(want) ──
ok('W1 덮개 닫힘 + 화면 꺼짐 + 전원 = lid_ac', s.want(B(lid_closed=True, display_off=True), ON) == ('lid_ac', None))
ok('W2 덮개 닫힘 + 화면 꺼짐 + 배터리 = lid_dc', s.want(B(lid_closed=True, display_off=True, on_battery=True, battery_lid_since=NOW), ON)[0] == 'lid_dc')
ok('W3 클램셸(덮개 닫힘 · 바깥 화면 켜짐) = 안 들어감', s.want(B(lid_closed=True, display_off=False), ON) == (None, None))
ok('W4 덮개 열림 + 입력 없어 화면 꺼짐 = screen_off', s.want(B(display_off=True), ON)[0] == 'screen_off')
ok('W5 덮개 열림 + 화면 켜짐(쓰는 중·동영상) = 안 들어감', s.want(B(), ON) == (None, None))
ok('W6 칸 끔: lid_ac 끔이면 전원 덮개 닫아도 안 들어감', s.want(B(lid_closed=True, display_off=True), {**ON, 'power.lid_ac': 'off'})[0] is None)
ok('W7 칸 끔: lid_dc 끔이어도 lid_ac 는 그대로(칸이 따로)', s.want(B(lid_closed=True, display_off=True), {**ON, 'power.lid_dc': 'off'})[0] == 'lid_ac')
ok('W8 칸 끔: screen_off 끔이면 화면만 꺼져서는 안 들어감', s.want(B(display_off=True), {**ON, 'power.screen_off': 'off'})[0] is None)
# ── 배터리로 닫아 둔 뒤 ──
st29 = B(lid_closed=True, display_off=True, on_battery=True, battery_lid_since=NOW - 29 * 60)
st31 = B(lid_closed=True, display_off=True, on_battery=True, battery_lid_since=NOW - 31 * 60)
ok('T1 배터리 + 덮개 29분 = 아직 안 재움', s.want(st29, ON, 30)[1] is None)
ok('T2 배터리 + 덮개 31분 = 최대 절전', s.want(st31, ON, 30)[1] == 'hibernate')
ok('T3 재우는 꼴 절전(low) → sleep · 서버만 남김(off) → serve · 폰 서버 없으면 → hibernate', s.want(st31, {**ON, 'power.lid_dc_how': 'low'}, 30)[1] == 'sleep' and s.want(st31, {**ON, 'power.lid_dc_how': 'off'}, 30)[1] == 'serve' and s.want({**st31, 'phone_server': False}, {**ON, 'power.lid_dc_how': 'off'}, 30)[1] == 'hibernate')
ok('T4 «30분 뒤 재움» 끔 → 안 재움', s.want(st31, {**ON, 'power.lid_dc_then': 'off'}, 30)[1] is None)
ok('T5 전원 연결이면 오래 닫아도 안 재움(서버로 둠)', s.want(B(lid_closed=True, display_off=True, battery_lid_since=None), ON, 30)[1] is None)
ok('T6 lid_dc 끔이어도 «30분 뒤 재움»은 따로 돎', s.want(st31, {**ON, 'power.lid_dc': 'off'}, 30) == (None, 'hibernate'))

# ── 상태 알림 → 배터리+덮개 시작 시각 ──
x = s.Sleeper(s.config(), lv_fn=lambda: dict(ON), act=False)
x.tick = lambda: None
x.on_setting(s.ACDC, 1)
x.on_setting(s.LID, 0)
t0 = x.st['battery_lid_since']
x.on_setting(s.DISPLAY, 0)
ok('N1 배터리 → 덮개 닫힘만으로는 안 셈 · 화면까지 꺼지면 시작 시각이 잡힘', t0 is None and x.st['battery_lid_since'] is not None and x.st['display_off'])
x.on_setting(s.ACDC, 0)
ok('N2 전원을 꽂으면 시작 시각이 지워짐(다시 빼면 처음부터)', x.st['battery_lid_since'] is None)

# ── 들어감·나옴(act=False · 조명·미디어 없이) ──
y = s.Sleeper(s.config(), lv_fn=lambda: {**ON, 'power.logo_light': 'off', 'power.media': 'off', 'power.dgpu_apps': 'off'}, act=False)
y.gpu_guard_running = lambda: False
y.on_setting(s.LID, 0)
y.on_setting(s.DISPLAY, 0)
ok('E1 들어가면 active.json 신호', y.active == 'lid_ac' and os.path.exists(s.ACTIVE))
y.on_setting(s.LID, 1)
y.on_setting(s.DISPLAY, 1)
ok('E2 덮개 열고 화면 켜지면 나오고 신호 지움', y.active is None and not os.path.exists(s.ACTIVE))
evs = [json.loads(z)['ev'] for z in open(s.LOG, encoding='utf-8')]
ok('E3 기록 = enter·exit', evs[-2:] == ['enter', 'exit'], evs[-3:])

# ── 깨어 있음(11-20 사고: 무인으로 깬 PC 를 윈도가 2분 뒤 다시 재움) ──
ok('H1 전원 + awake_ac 켬 = 쥠', s.hold_wanted(B(), ON))
ok('H2 배터리 = 놓음(가방 속 · 배터리 규칙 그대로)', not s.hold_wanted(B(on_battery=True), ON, True))
AW = {**ON, 'power.awake_ac': 'off'}
ok('H3 awake_ac 끔 + 저절로 깬 뒤 = 쥠(resume_awake)', s.hold_wanted(B(), AW, True))
ok('H4 awake_ac 끔 + 보통 때 = 안 쥠', not s.hold_wanted(B(), AW, False))
ok('H5 둘 다 끔 = 저절로 깨도 안 쥠', not s.hold_wanted(B(), {**AW, 'power.resume_awake': 'off'}, True))
calls = []
z = s.Sleeper(s.config(), lv_fn=lambda: dict(AW), act=False)
z.set_awake = lambda on: calls.append(on) or True
z.tick = lambda: None
tickv = [1000]
s.last_input_tick = lambda: tickv[0]
z.on_power(s.PBT_APMSUSPEND)
z.on_power(s.PBT_APMRESUMEAUTOMATIC)
ok('H6 저절로 깸 알림 → 바로 쥠', z.hold and calls[-1] is True, calls)
tickv[0] = 2000
z.apply_hold()
ok('H7 사람이 만지면(입력 시각 바뀜) 놓음', not z.hold and calls[-1] is False, calls)
z.lv = dict(ON)
z.apply_hold()
z.on_setting(s.ACDC, 1)
z.apply_hold()
ok('H8 awake_ac 켬이어도 배터리로 바뀌면 놓음', not z.hold and calls[-1] is False, calls)
ev = [json.loads(q) for q in open(s.LOG, encoding='utf-8')]
ok('H9 기록 = suspend·resume_auto·awake', {'suspend', 'resume_auto', 'awake', 'resume_user'} <= {e['ev'] for e in ev})
import subprocess  # noqa: E402
s.set_awake(False)    # 위 E 시험의 Sleeper 가 이 스레드에서 쥔 것을 놓음
before = s.system_execution_state()
pr = subprocess.Popen([sys.executable, '-c', 'import sys,time; sys.path.insert(0, %r); import self_sleep as s; s.set_awake(True); time.sleep(4)' % HERE])
import time as _t  # noqa: E402
_t.sleep(2.5)
mid = s.system_execution_state()
pr.wait()
after = s.system_execution_state()
ok('H10 실제: 다른 프로세스가 쥐면 시스템 상태에 «시스템 필요» · 끝나면 전과 같음', bool(mid & 1) and (after & 1) == (before & 1),
   (hex(before), hex(mid), hex(after)))

# ── «배터리로 닫아 둔 뒤 재움» 셈(사용자 11-20: 충전기 꽂으려 45도 닫았다 열면 최대 절전이라 다시 켜야 했다) — 가짜 알림 차례 ──
class Clock:
    def __init__(self):
        self.t = 5_000_000.0

    def __call__(self):
        return self.t


def drive(steps, minutes=30):
    """steps = [('lid'|'disp'|'acdc'|'input'|'wait', 값)] → 재운 횟수. 알림 길(on_setting)과 순찰(tick)만 쓴다 · 재우기는 가짜."""
    clk, slept, inp = Clock(), [], [100]
    z = s.Sleeper(s.config(), lv_fn=lambda: {**ON, 'power.awake_ac': 'off', 'power.resume_awake': 'off',
                                              'power.logo_light': 'off', 'power.media': 'off', 'power.dgpu_apps': 'off'}, act=True)
    z.clock, z.input_tick = clk, (lambda: inp[0])
    z.set_awake = lambda on: True
    z.gpu_guard_running = lambda: False
    real = (s.suspend, s.then_minutes)
    s.suspend = lambda hib: slept.append(hib) or True
    s.then_minutes = lambda _l: float(minutes)
    try:
        z.on_setting(s.ACDC, 1)                 # 배터리에서 시작
        z.on_setting(s.LID, 1)
        z.on_setting(s.DISPLAY, 1)
        for k, v in steps:
            if k == 'wait':
                end = clk.t + v
                while clk.t < end:              # 15초 순찰
                    clk.t = min(end, clk.t + 15)
                    z.tick()
            elif k == 'input':
                inp[0] += 1
            else:
                z.on_setting({'lid': s.LID, 'disp': s.DISPLAY, 'acdc': s.ACDC}[k], v)
    finally:
        s.suspend, s.then_minutes = real
    return slept


CLOSE = [('lid', 0), ('disp', 0)]
OPEN = [('lid', 1), ('disp', 1)]
ok('K1 닫힘 → 10초 → 전원 연결 → 열림 → (40분 흘러도) = 안 재움', drive(CLOSE + [('wait', 10), ('acdc', 0)] + OPEN + [('wait', 40 * 60)]) == [])
ok('K2 닫힘 → 10초 → 열림 → 다시 닫힘 → 29분 = 안 재움(처음부터 다시 셈)',
   drive(CLOSE + [('wait', 10)] + OPEN + CLOSE + [('wait', 29 * 60)]) == [])
ok('K3 닫힘 → 20분 → 열림 → 닫힘 → 20분 = 안 재움(앞 20분을 버림)', drive(CLOSE + [('wait', 20 * 60)] + OPEN + CLOSE + [('wait', 20 * 60)]) == [])
ok('K4 닫힘 30분 이어짐 = 재움 한 번(최대 절전)', drive(CLOSE + [('wait', 31 * 60)]) == [True])
ok('K5 닫힌 채 20분에 사람 입력(바깥 키보드) → 20분 = 안 재움(처음부터 다시)', drive(CLOSE + [('wait', 20 * 60), ('input', 0), ('wait', 20 * 60)]) == [])
ok('K6 닫힌 채 바깥 화면이 켜짐(클램셸) → 40분 = 안 재움', drive(CLOSE + [('wait', 60), ('disp', 1), ('wait', 40 * 60)]) == [])
ok('K7 반쯤 닫혀 센서가 «닫힘»을 안 냄(화면만 꺼짐) → 40분 = 안 재움', drive([('disp', 0), ('wait', 40 * 60)]) == [])
ok('K8 기다리는 분 = 설정 값(10분으로 바꾸면 11분에 재움)', drive(CLOSE + [('wait', 11 * 60)], minutes=10) == [True]
   and drive(CLOSE + [('wait', 9 * 60)], minutes=10) == [])
ok('K9 기다리는 분 기본 = 선언 params 10(사용자 11-20 «A10분»)', s.then_minutes('high') == 10.0, s.then_minutes('high'))

# ── 외장 그래픽 판정(옮겨 온 gpu_guard 판단 그대로) ──
c = s.config()
P = lambda **k: {'name': 'steam.exe', 'exe': r'C:\Program Files (x86)\Steam\steam.exe', 'util': 0.0, 'io_kbs': 1.0, **k}  # noqa: E731
ok('G1 깨우기만 하는 앱 = 끔', dgpu.judge(P(), c)[0] == 'kill')
ok('G2 폰 환경·수집(서버 파이썬·Tailscale·Claude·node·크롬) = 안 끔',
   all(dgpu.judge(P(name=n, exe='C:\\x\\' + n), c)[0] == 'protect' for n in ('pythonw.exe', 'tailscaled.exe', 'Claude.exe', 'node.exe', 'chrome.exe')))
ok('G3 그래픽 일·받는 중 = 안 끔', dgpu.judge(P(util=30.0), c)[0] == 'work' and dgpu.judge(P(io_kbs=4096), c)[0] == 'download')
ok('G4 되살아남 기억은 memo 로(파일 전역 없음)', 'mem()' not in open(os.path.join(HERE, 'dgpu.py'), encoding='utf-8').read())

# ── 돌아오면 다시 켜기(옛 gpu_guard 규칙 그대로 · dgpu.relaunch_cmd + Sleeper.relaunch) ──
STEAM_EXE = r'C:\Program Files (x86)\Steam\steam.exe'
TRAY_EXE = r'C:\Tools\tray.exe'
GAME_EXE = r'D:\Games\game.exe'
runs = {STEAM_EXE.lower(): '"' + STEAM_EXE + '" -silent', TRAY_EXE.lower(): '"' + TRAY_EXE + '" --background'}
steam = STEAM_EXE
c0 = {**c, 'relaunch': {}}
ok('R1 시작 프로그램에 있는 상주형 = 등록된 명령 그대로', dgpu.relaunch_cmd('steam.exe', steam, c0, runs) == runs[steam.lower()])
ok('R2 직접 연 창 앱(시작 프로그램에 없음) = 다시 안 켬', dgpu.relaunch_cmd('game.exe', GAME_EXE, c0, runs) is None)
ok('R3 옛 gpu_guard 설정 steam.exe=never 를 이어받음 = 시작 프로그램에 있어도 안 켬',
   c['relaunch'].get('steam.exe') == 'never' and dgpu.relaunch_cmd('steam.exe', steam, c, runs) is None, c['relaunch'])
c2 = {**c, 'relaunch': {**c['relaunch'], 'game.exe': 'always'}}
ok('R4 설정 always = 시작 프로그램에 없어도 켬', dgpu.relaunch_cmd('game.exe', GAME_EXE, c2, runs) == '"' + GAME_EXE + '"')
with open(s.CONFIG, 'w', encoding='utf-8') as f:
    f.write('{"relaunch": {"steam.exe": "always"}}')
ok('R5 이 모듈 config.json 이 옛 값보다 앞섬', s.config()['relaunch'].get('steam.exe') == 'always')
os.remove(s.CONFIG)
popen = []
real_popen = s.subprocess.Popen
s.subprocess.Popen = lambda cmd, **k: popen.append(cmd)
try:
    w = s.Sleeper(s.config(), lv_fn=lambda: dict(ON), act=True)
    w.memo = {'killed': [{'name': 'steam.exe', 'cmd': dgpu.relaunch_cmd('steam.exe', steam, w.c, runs)},
                         {'name': 'tray.exe', 'cmd': dgpu.relaunch_cmd('tray.exe', TRAY_EXE, w.c, runs)}]}
    w.relaunch()
finally:
    s.subprocess.Popen = real_popen
ok('R6 나올 때: 끈 것 중 다시 켤 명령이 있는 것만 켬(Steam 안 켬 · tray 켬) · 목록 비움',
   popen == [runs[TRAY_EXE.lower()]] and w.memo['killed'] == [], popen)

# ── 효율 모드 후보 판단(칸 없음 · trial 만) ──
smp = [{'pid': 1, 'name': 'qemu.exe', 'exe': r'C:\x\qemu.exe', 'cpu': 50, 'prev_cpu': 40},
       {'pid': 2, 'name': 'claude.exe', 'exe': r'C:\x\claude.exe', 'cpu': 90, 'prev_cpu': 90},
       {'pid': 3, 'name': 'once.exe', 'exe': r'C:\x\once.exe', 'cpu': 50, 'prev_cpu': 0}]
ok('Q1 두 번 잇달아 넘은 비보호만', s.ecoqos_pick(smp, c) == [1])

# ── 선언(module.json) ──
mj = json.load(open(os.path.join(HERE, '..', 'module.json'), encoding='utf-8'))
opts = mj['contributes']['options']
ok('D1 칸 id = 대본이 읽는 id(빠짐·남음 없음)', {o['id'] for o in opts} == set(s.LEVEL_IDS), sorted({o['id'] for o in opts} ^ set(s.LEVEL_IDS)))
ok('D2 칸마다 켬/끔 둘 · 재우는 꼴만 셋(battery_keep · 배터리 낮춤에서 빠짐)', all((o['levels'] == ['high', 'off'] and set(o['labels']) == {'high', 'off'}) or (o['id'] == 'power.lid_dc_how' and o['levels'] == ['high', 'low', 'off'] and o.get('battery_keep') is True) for o in opts) and all(o.get('battery_keep') for o in opts if 'low' in o['levels']))
ok('D3 칸마다 default_why·cells(단계마다)', all(o.get('default_why') and set(o.get('cells', {})) == set(o['levels']) for o in opts))
ok('D4 needs·level_needs 이름은 probe 가 재는 이름', {n for o in opts for n in o.get('needs', []) + [x for v in (o.get('level_needs') or {}).values() for x in v]} <= {'lid', 'battery', 's4', 'dgpu_nvidia', 'media', 'logo_light', 'phone_server'})

# ── options: needs 거르기 ──
desk = {'lid': False, 'battery': False, 'dgpu_nvidia': False, 'media': True, 'logo_light': False, 's4': True}
shown = [o['id'] for o in opts if options.capable(o, desk)]
ok('C1 데스크톱(덮개·배터리·외장·조명 없음) = 깨어 있음 둘·화면 꺼짐·미디어만', shown == ['power.awake_ac', 'power.resume_awake', 'power.screen_off', 'power.media'], shown)
ok('C2 모르는 장치(아직 안 잼) = 보임', all(options.capable(o, {}) for o in opts))
lap = {'lid': True, 'battery': True, 'dgpu_nvidia': False, 'media': True, 'logo_light': False, 's4': False}
shown = [o['id'] for o in opts if options.capable(o, lap)]
ok('C3 외장·조명·최대 절전 없는 노트북 = 외장·조명 칸 없음 · 재우는 꼴은 있음(단계는 V1)', 'power.lid_dc_how' in shown and 'power.dgpu_apps' not in shown
   and 'power.logo_light' not in shown and 'power.lid_dc_then' in shown, shown)
ok('C4 decide: recommend default = high + default_why', options.decide({'notes': 100}, [options._norm(opts[0], 'self_sleep')])[0] == {opts[0]['id']: 'high'})

# ── 재우는 꼴 셋 중 하나(최대 절전 | 절전 | 서버만 남김 · 사용자 11-20) · 단계별 장치 조건 ──
how_decl = next(o for o in opts if o['id'] == 'power.lid_dc_how')
g = options._norm(how_decl, 'self_sleep', {'s4': False})
ok('V1 최대 절전 없는 기기 = 절전 단계 숨김 · high 이름이 «절전»', g['levels'] == ['high', 'off'] and g['labels']['high'] == '절전', (g['levels'], g['labels']))
g = options._norm(how_decl, 'self_sleep', {'phone_server': False, 's4': True})
ok('V2 폰 서버 없는 볼트 = «서버만 남김» 단계 숨김', g['levels'] == ['high', 'low'], g['levels'])
g = options._norm(how_decl, 'self_sleep', {})
ok('V3 모름 = 셋 다 · 이름 최대 절전·절전·서버만 남김', g['levels'] == ['high', 'low', 'off'] and [g['labels'][k] for k in g['levels']] == ['최대 절전', '절전', '서버만 남김'])
other = {'id': 'x.y', 'levels': ['high', 'low'], 'ready': True}
fs = [options._norm(how_decl, 'self_sleep', {}), options._norm(other, 'core', {})]
lv_bat = options.resolve({'schema': 1, 'battery': 'lower', 'levels': {}}, 'ok', fs, lambda: True)
ok('V4 battery_keep = «배터리일 때 낮춤»에서 빠짐(최대 절전이 절전으로 안 바뀜) · 다른 칸은 낮춤', lv_bat['power.lid_dc_how'] == 'high' and lv_bat['x.y'] == 'low', lv_bat)


# ── 서버만 남김 — 가짜 일꾼(끄기·프로세서·원격·배터리)로 차례 시험 ──
def serve_drive(steps, lv_extra=None, pct=80, server=True, minutes=10):
    clk, inp, calls = Clock(), [100], []
    st = {'procmax': 100, 'pct': pct}
    lvx = {**ON, 'power.awake_ac': 'off', 'power.resume_awake': 'off', 'power.logo_light': 'off', 'power.media': 'off',
           'power.dgpu_apps': 'off', 'power.serve_defer': 'off', 'power.lid_dc_how': 'off', **(lv_extra or {})}
    z = s.Sleeper(s.config(), lv_fn=lambda: dict(lvx), act=True)
    z.clock, z.input_tick = clk, (lambda: inp[0])
    z.set_awake = lambda on: True
    z.gpu_guard_running = lambda: False
    z.has_server = server

    def setpm(v):
        calls.append(('procmax', v))
        st['procmax'] = v
        return True
    z.ops = {'battery_pct': lambda: st['pct'], 'procmax_get': lambda: st['procmax'], 'procmax_set': setpm,
             'pause': lambda pid, on: calls.append(('pause', pid, on)) or True,
             'kill_tree': lambda pid, cr: calls.append(('kill', pid)) or True,
             'rc_procs': lambda: [] if ('kill', 900) in calls else [(900, 1.0)],
             'idle_sessions': lambda: [(901, '쉬는 세션'), (900, 'RC')],
             'busy_owners': lambda: set(), 'rc_open': lambda: calls.append(('rc_open',)) or True,
             'params': lambda: {'cpu_pct': 50, 'guard_pct': 25, 'guard_hours': 3.0}}
    slept = []
    real = (s.suspend, s.then_minutes)
    s.suspend = lambda hib: slept.append(hib) or True
    s.then_minutes = lambda _l: float(minutes)
    try:
        z.on_setting(s.ACDC, 1)
        z.on_setting(s.LID, 1)
        z.on_setting(s.DISPLAY, 1)
        for k, v in steps:
            if k == 'wait':
                end = clk.t + v
                while clk.t < end:
                    clk.t = min(end, clk.t + 15)
                    z.tick()
            elif k == 'input':
                inp[0] += 1
                z.tick()
            elif k == 'pct':
                st['pct'] = v
            else:
                z.on_setting({'lid': s.LID, 'disp': s.DISPLAY, 'acdc': s.ACDC}[k], v)
    finally:
        s.suspend, s.then_minutes = real
    return calls, slept, z, st


calls, slept, z, st = serve_drive(CLOSE + [('wait', 11 * 60)])
ok('SV0 서버만 남김 중 = 배터리여도 깨어 있음 쥠(윈도 배터리 유휴 절전 30분 막음) · 나오면 놓음', z.hold, z.hold)
ok('SV1 10분 뒤 서버만 남김: 원격 끔 · 쉬는 세션 닫음(원격은 두 번 안 셈) · 배터리 프로세서 100→50 · 안 재움',
   ('kill', 900) in calls and ('kill', 901) in calls and calls.count(('kill', 900)) == 1 and ('procmax', 50) in calls and slept == [] and z.serving,
   calls)
calls, slept, z, st = serve_drive(CLOSE + [('wait', 11 * 60)] + OPEN)
ok('SV2b 나오면(배터리) 깨어 있음 놓음', not z.hold)
ok('SV2 덮개 열면 바로 나옴: 프로세서 원래 값(100) · 원격 다시 켬 · 안 재움', st['procmax'] == 100 and ('rc_open',) in calls and not z.serving and slept == [], calls)
calls, slept, z, st = serve_drive(CLOSE + [('wait', 11 * 60), ('acdc', 0), ('wait', 60)])
ok('SV3 전원 연결 = 바로 나옴', st['procmax'] == 100 and not z.serving and slept == [])
calls, slept, z, st = serve_drive(CLOSE + [('wait', 11 * 60), ('input', 0)])
ok('SV4 사람 입력 = 바로 나옴', st['procmax'] == 100 and not z.serving)
calls, slept, z, st = serve_drive(CLOSE + [('wait', 11 * 60), ('pct', 24), ('wait', 30)])
ok('SV5 안전장치: 배터리 25% 아래 = 되돌린 뒤 진짜 최대 절전 한 번', slept == [True] and st['procmax'] == 100 and not z.serving, (slept, calls[-3:]))
calls, slept, z, st = serve_drive(CLOSE + [('wait', 11 * 60 + 3 * 3600 + 30)])
ok('SV6 안전장치: 서버만 남김 3시간 = 최대 절전', slept == [True])
calls, slept, z, st = serve_drive(CLOSE + [('wait', 11 * 60), ('pct', 10), ('wait', 60)], {'power.serve_guard': 'off'})
ok('SV7 안전장치 끔 = 배터리 10% 여도 안 재움', slept == [] and z.serving)
calls, slept, z, st = serve_drive(CLOSE + [('wait', 11 * 60)], {'power.serve_rc': 'off', 'power.serve_cpu': 'off'})
ok('SV8 칸 끔: 원격·세션·프로세서 그대로', not [c for c in calls if c[0] in ('kill', 'procmax')] and z.serving, calls)
calls, slept, z, st = serve_drive(CLOSE + [('wait', 11 * 60)], server=False)
ok('SV9 폰 서버 없는 볼트 = 서버만 남김 대신 최대 절전', slept == [True] and not z.serving)
calls, slept, z, st = serve_drive(CLOSE + [('wait', 11 * 60)], {'power.lid_dc_how': 'high'})
ok('SV10 재우는 꼴 최대 절전 = 최대 절전(서버만 남김 일 없음)', slept == [True] and not [c for c in calls if c[0] == 'kill'])
calls, slept, z, st = serve_drive(CLOSE + [('wait', 11 * 60)], {'power.lid_dc_how': 'low'})
ok('SV11 재우는 꼴 절전 = 절전', slept == [False])

# 감시가 서버만 남김 중에 꺼졌다 다시 뜸 → 프로세서 되돌림
m = s.mem()
m['procmax_prev'] = 100
s.save_mem(m)
got = []
ok('SV12 다시 뜰 때 남은 프로세서 상한을 되돌림', s.restore_stale(lambda v: got.append(v) or True) and got == [100] and 'procmax_prev' not in s.mem())

# 무거운 배경 일 멈춤 — 실제 시험 부하(이 시험이 띄운 파이썬 하나)를 멈췄다 되돌림
import subprocess as _sp  # noqa: E402
import psutil  # noqa: E402
burn = _sp.Popen([sys.executable, '-c', 'import time\nt=time.time()+60\nwhile time.time()<t: pass'])
try:
    zz = s.Sleeper(s.config(), lv_fn=lambda: dict(ON), act=True)
    zz.c['protect'] = [x for x in zz.c['protect'] if x not in ('python.exe', 'py.exe')]
    zz.ops = dict(s.SERVE_OPS, busy_owners=lambda: set())
    zz.serving = {'since': 0, 'rc': False, 'closed': [], 'paused': {}, 'cpu_prev': None, 'cpu_samples': {}}
    real_iter = psutil.process_iter
    psutil.process_iter = lambda attrs=None: [x for x in real_iter(attrs) if x.pid == burn.pid]   # 이 시험 부하만 보게
    try:
        for _ in range(3):
            zz.serve_defer_round()
            _t.sleep(1.5)
    finally:
        psutil.process_iter = real_iter
    paused = burn.pid in zz.serving['paused']
    pp = psutil.Process(burn.pid)
    pp.cpu_percent(None)
    _t.sleep(1.5)
    cpu_paused = pp.cpu_percent(None)
    zz.serve_exit(quiet=True)
    pp.cpu_percent(None)
    _t.sleep(1.5)
    cpu_back = pp.cpu_percent(None)
    ok('SV13 실제: CPU 먹는 배경 프로세스를 멈춤(≈0%) · 나오면 다시 돎', paused and cpu_paused < 5 and cpu_back > 50, (paused, cpu_paused, cpu_back))
finally:
    burn.kill()

# ── 옛 gpu_guard 대조(11-20 «완전히 상위호환이니까 대체») — 빠졌던 것 메움 ──
ok('J6 되살아나는 앱(설정에서 끌 것) = 안 끔', dgpu.judge(P(name='NVIDIA Overlay.exe', exe=r'C:\Program Files\NVIDIA Corporation\x.exe'), c, ['nvidia overlay.exe'])[0] == 'protect')
ok('J7 잴 수 없음·이름 모름·자기 자신 = 안 끔', dgpu.judge(P(util=None), c)[0] == 'protect' and dgpu.judge(P(name=None, exe=None), c)[0] == 'protect'
   and dgpu.judge(P(self=True), c)[0] == 'protect')
ok('J8 Windows 폴더 = 안 끔', dgpu.judge(P(name='ShellHost.exe', exe=r'C:\Windows\System32\ShellHost.exe'), c)[0] == 'protect')
killed, real_an, real_kill = [], dgpu.analyze, dgpu.kill
dgpu.analyze = lambda c_, memo=None: [{'pid': 1, 'name': 'steam.exe', 'exe': r'C:\x\steam.exe', 'util': 0.0, 'io_kbs': 0.0, 'verdict': 'kill', 'why': '깨우기만 함'}]
dgpu.kill = lambda r, c_, memo=None: killed.append(r['name']) or '창 닫기'
try:
    oz = s.Sleeper({**s.config(), 'dgpu_observe': True}, lv_fn=lambda: dict(ON), act=True)
    oz.active = 'lid_ac'
    oz.hunt(not oz.c.get('dgpu_observe'))
    ev = [json.loads(q) for q in open(s.LOG, encoding='utf-8')][-2:]
    ok('O1 관찰(config dgpu_observe) = 끄지 않고 «껐을 것»만 기록', killed == [] and ev[-1]['ev'] == 'would_kill', ev)
finally:
    dgpu.analyze, dgpu.kill = real_an, real_kill
prev_file = os.path.join(T, 'prev.json')
open(prev_file, 'w').write('{}')
lz = s.Sleeper({**s.config(), 'lights': {**s.config()['lights'], 'prev': prev_file}}, lv_fn=lambda: dict(ON), act=True)
lit = []
lz.lights = lambda mode: lit.append(mode)
lz.gpu_guard_running = lambda: False
lz.set_awake = lambda on: True
lz.on_setting(s.ACDC, 0)
ok('L1 알림을 다 받기 전엔 조명을 안 건드림', lit == [])
lz.on_setting(s.LID, 1)
lz.on_setting(s.DISPLAY, 1)
lz.tick()
ok('L2 덮개 닫힌 채 감시가 죽었다 뜸(꺼 둔 조명 남음) → 열린 상태면 첫 순찰에 한 번 되돌림', lit == ['restore'], lit)
with open(s.LOG, 'a', encoding='utf-8') as f:
    for e in ({'ev': 'enter', 'why': 'lid_ac'}, {'ev': 'wake', 'who': [{'name': 'steam.exe'}]}, {'ev': 'kill', 'name': 'steam.exe'},
              {'ev': 'pause', 'app': 'chrome'}, {'ev': 'serve', 'what': 'enter'}, {'ev': 'then_done', 'ok': True}):
        f.write(json.dumps({'t': s.now(), **e}, ensure_ascii=False) + '\n')
rp = s.report(1)
ok('P1 report = 들어감·깨운 앱·끈 것·멈춘 미디어·서버만 남김·재움 셈(옛 gpu_guard.report)', rp['killed'].get('steam.exe') == 1 and rp['woke_by'].get('steam.exe', 0) >= 1
   and rp['serve'] >= 1 and rp['slept'] >= 1 and rp['paused_media'].get('chrome') == 1, rp)
mj_actions = {a['id'] for a in mj['contributes']['actions']}
ok('P2 행위 = 상태·지금 값·다시 재기·전력·기록 보기', {'self_sleep.status', 'self_sleep.report', 'self_sleep.probe', 'self_sleep.now', 'self_sleep.measure'} <= mj_actions, mj_actions)
gpu = dgpu.find_dgpu()
ok('D5 외장 NVIDIA 찾음·상태 읽기(깨우지 않음 · 이 PC)', (gpu is None) or dgpu.dstate(gpu) in ('D0', 'D3'), (gpu and gpu[:22], gpu and dgpu.dstate(gpu)))

print('%d/%d' % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
