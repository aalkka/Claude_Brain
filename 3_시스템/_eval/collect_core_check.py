# -*- coding: utf-8 -*-
"""수집 본체 통합 검사(11-07 · 2단계부터) — module.json 이 맡던 약속을 코어 선언이 대신하는지 잰다. 망 요청 0 · 볼트에 안 씀(임시 볼트만).

  py -3 3_시스템/_eval/collect_core_check.py

① views.json 꼴 — 수집 화면 선언 하나 · html·data 대본이 볼트 안 · 대화 입구 = /collect_desk: · contract(touches·reads·forbids)
② 모듈 아님(4단계 뒤) — module.json 없음 · 모듈 목록에 없음 · 명령 이름 그대로 · 장 = 코어 8장(머리 «화면:»·«옛 id:») · 설명서 = 코어 자리 · 모듈 자리 장·설명서·옛 사본 없음
③ 행위 — collect_desk.* 10 이 코어 actions.json 에 한 번씩 · brain.py 가 겹침 없이 읽음 · 화면·스킬이 부르는 id 가 다 있음
   · 예약·홈이 부르는 collect.lms·collect.lms.wake·collect.web 이 코어에 그대로
④ 1_수집 — collect_desk.py·화면에 1_수집 글자 0 · contract·watch 가 1_수집 에 안 닿고 forbids 에 1_수집/**
⑤ 전체 스위치(switch_cases) — 엔진 셋(web-collect·lms-auto·filter-learn)과 창 대본이 같은 규칙 · 창 set 이 새 자리에 쓰고 옛 자리 같은 칸을 걷음
⑥ mylms 주소 — collect_desk.py 에 학교 주소·MYLMS_URL 0 · 확장 manifest host_permissions 에서 · 없음·와일드카드 = 빈칸·열기 거절
⑦ git 밖 — collect.local.json 이 .gitignore 로 빠짐
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)
VAULT = os.path.dirname(SYS)
MOD = os.path.join(VAULT, '.claude', 'skills', 'collect_desk')
DESK_PY = os.path.join(MOD, 'scripts', 'collect_desk.py')
OWNER = 'collect_desk'
IDS = [OWNER + '.' + x for x in ('set', 'fetch', 'judge', 'item', 'open', 'contract', 'probe', 'try', 'add', 'fix')]
KEEP = ('collect.lms', 'collect.lms.wake', 'collect.web')     # 예약(lms-tasks.ps1)·홈 «수집» 칸이 부르는 id — 바뀌면 15분 확인·아침 깨우기가 선다
SWITCH = '3_시스템/collect.local.json'
res = []


def ok(name, cond, detail=''):
    res.append(bool(cond))
    print(('통과 ' if cond else '실패 ') + name + ('' if cond else f' — {detail}'[:400]), flush=True)


def load(p):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def read(p):
    try:
        with open(p, encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return ''


def in_vault(p):
    """볼트 안 대본 — .claude/skills/ 또는 3_시스템/ 아래 · .. 없음 · 파일 있음"""
    return (isinstance(p, str) and p.startswith(('.claude/skills/', '3_시스템/')) and '..' not in p.split('/')
            and os.path.isfile(os.path.join(VAULT, *p.split('/'))))


def module_of(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def probe(tv):
    """(따로 프로세스) 임시 볼트의 네 대본이 지금 파일에서 읽는 전체 스위치 — JSON 한 줄"""
    ts = os.path.join(tv, '3_시스템')
    out = {}
    for name in ('web-collect', 'lms-auto', 'filter-learn'):
        m = module_of(name.replace('-', '_'), os.path.join(ts, name + '.py'))
        sw = m.switches()
        out[name] = [sw.get('all_off') is True, sw.get('auto_judge') is True]
        if name == 'web-collect':
            out['auto_on'] = m.auto_on({'id': 't', 'filter': {'card': 'x'}})
        if name == 'lms-auto':
            out['paused'] = m.write_known()['paused']
    cd = module_of('collect_desk', os.path.join(tv, '.claude', 'skills', 'collect_desk', 'scripts', 'collect_desk.py'))
    sw = cd.switches()
    out['collect_desk'] = [sw.get('all_off') is True, sw.get('auto_judge') is True]
    v = cd.view()
    out['view'] = [v['allOff'], v['autoJudge']]
    print(json.dumps(out, ensure_ascii=False))


def main():
    # ── ① views.json ──
    views = load(os.path.join(SYS, 'views.json'))
    ok('views.json 읽힘 · views 목록', isinstance(views, dict) and isinstance(views.get('views'), list), views)
    mine = [v for v in (views or {}).get('views') or [] if isinstance(v, dict) and v.get('owner') == OWNER]
    ok('수집 화면 선언 = 하나(owner collect_desk · id desk)', len(mine) == 1 and mine[0].get('id') == 'desk', [(v.get('owner'), v.get('id')) for v in mine])
    v = mine[0] if mine else {}
    ok('이름·아이콘 = 수집·inbox(리본·명령·잎 상태 그대로)', v.get('name') == '수집' and v.get('icon') == 'inbox', (v.get('name'), v.get('icon')))
    ok('html = 볼트 안 화면 파일', in_vault(v.get('html')), v.get('html'))
    data = v.get('data') or []
    ok('data = {py} · 볼트 안 대본 · view', isinstance(data, list) and data[:1] == ['{py}'] and len(data) > 2 and in_vault(data[1]) and data[2] == 'view', data)
    chat = v.get('chat') or []
    ok('대화 입구 add·fix = /collect_desk: 접두 · 묻는 말 있음',
       sorted(c.get('id') for c in chat if isinstance(c, dict)) == ['add', 'fix']
       and all(isinstance(c, dict) and str(c.get('send', '')).startswith('/' + OWNER + ':') and isinstance(c.get('ask'), str) for c in chat), chat)
    con = v.get('contract') if isinstance(v.get('contract'), dict) else {}
    ok('contract = touches·reads·forbids 글자 목록', all(isinstance(con.get(k), list) and all(isinstance(x, str) for x in con[k]) for k in ('touches', 'reads', 'forbids')), con)
    watch = v.get('watch') if isinstance(v.get('watch'), list) else []
    ok('새 스위치 자리가 watch·touches 에 듦', SWITCH in watch and SWITCH in (con.get('touches') or []), (watch, con.get('touches')))

    # ── ② 모듈 아님(4단계 뒤 · 11-08) — 화면·행위·장·설명서가 다 코어 자리 · 대화 명령 이름은 .claude-plugin 이 그대로 낸다 ──
    sys.path.insert(0, SYS)
    import roles  # noqa: E402 — 모듈 = module.json 있는 폴더(brain.py·건강·홈 모듈 스위치가 쓰는 목록)
    ok('module.json 없음 = 모듈 아님(홈 모듈 스위치·모듈 끄기 대상 밖 · 늘 있음)', not os.path.exists(os.path.join(MOD, 'module.json')), '있음 — 4단계 전이거나 되돌림')
    mods = [m['id'] for m in roles.modules(on_only=False)]
    ok('모듈 목록(꺼진 것 포함)에 collect_desk 없음', OWNER not in mods, mods)
    ok('대화 명령 이름 그대로(.claude-plugin name = collect_desk → /collect_desk:add·fix)', (load(os.path.join(MOD, '.claude-plugin', 'plugin.json')) or {}).get('name') == OWNER)
    tt = os.path.join(SYS, 'tutorial')
    head = lambda p: (read(p).split('\n---', 1)[0] if read(p).startswith('---') else '')
    h8 = head(os.path.join(tt, '8-수집.md'))
    ok('튜토리얼 장 = 코어 8장(머리 장: 8 · 화면: collect_desk · 옛 id: collect_desk:1-수집)',
       all(re.search(r'(?m)^' + re.escape(k) + r'\s*$', h8) for k in ('장: 8', '화면: ' + OWNER, '옛 id: ' + OWNER + ':1-수집')), h8[:200])
    nos = [m.group(1) for p in sorted(__import__('glob').glob(os.path.join(tt, '*.md'))) for m in [re.search(r'(?m)^장:\s*(\d+)\s*$', head(p))] if m]
    ok(f'코어 장 번호 겹침 없음({len(nos)}장)', len(nos) == len(set(nos)), nos)
    ok('설명서 = 코어 자리(3_시스템/설명서/설명서-수집.md)', os.path.isfile(os.path.join(SYS, '설명서', '설명서-수집.md')))
    left = (__import__('glob').glob(os.path.join(MOD, 'tutorial', '*.md')) + __import__('glob').glob(os.path.join(MOD, 'manual', '*.md'))
            + [p for p in (os.path.join(SYS, '설명서', '_index', '설명서-collect_desk.md'),) if os.path.exists(p)])
    ok('모듈 자리 장·설명서·옛 사본 없음(두 번 보임 막음 · 빈 폴더는 남아도 됨 · 사본은 brain.py modules --sync 가 치움)', not left, left)

    # ── ③ 행위 ──
    core = load(os.path.join(SYS, 'actions.json')) or {}
    core_acts = [a for a in core.get('actions') or [] if isinstance(a, dict)]
    mine_acts = [a for a in core_acts if str(a.get('id', '')).startswith(OWNER + '.')]
    decl = [a['id'] for a in mine_acts]
    ok(f'행위 {len(IDS)} 이 코어 actions.json 에 한 번씩', sorted(decl) == sorted(IDS),
       (sorted(set(decl) ^ set(IDS)), sorted({x for x in decl if decl.count(x) > 1})))
    bad = [a['id'] for a in mine_acts if not (isinstance(a.get('run'), list) and a['run'][:1] == ['{py}'] and len(a['run']) > 1 and in_vault(a['run'][1]))]
    ok('행위마다 run = {py} · 볼트 안 대본', not bad, bad)
    import brain  # noqa: E402 — 코어 행위 읽기(코어 먼저 · 켜진 모듈 뒤)
    acts, problems = brain.load_actions()
    got = {a['id']: o for a, o in acts}
    mine_p = [p for p in problems if 'collect' in p]
    ok('brain.py 가 collect_desk.* 10 을 읽음 · 수집 행위 문제 0', all(i in got for i in IDS) and not mine_p, ([i for i in IDS if i not in got], mine_p))
    ok('예약·홈이 부르는 id 그대로(collect.lms · collect.lms.wake · collect.web = 코어)', all(got.get(i) == 'core' for i in KEEP), {i: got.get(i) for i in KEEP})
    ps = os.path.join(SYS, 'lms-tasks.ps1')
    if os.path.exists(ps):
        used = set(re.findall(r'\brun (collect\.[a-z.]+)', read(ps)))
        ok('예약 명령 줄(lms-tasks.ps1)이 부르는 id 가 코어에 있음', {'collect.lms', 'collect.lms.wake'} <= used and all(got.get(i) == 'core' for i in used), used)
    else:
        print('  (lms-tasks.ps1 없음 — 이 예약이 없는 판 · 건너뜀)')
    txt = read(os.path.join(MOD, 'view', 'index.html')) + ''.join(read(p) for p in sorted(__import__('glob').glob(os.path.join(MOD, 'skills', '*', 'SKILL.md'))))
    called = set(re.findall(r'\b' + OWNER + r'\.(?!py\b)([a-z]+)', txt))
    ok('화면·스킬이 부르는 행위 id 가 다 선언됨', called and {OWNER + '.' + x for x in called} <= set(IDS), sorted(called))

    # ── ④ 1_수집 ──
    for name, p in (('collect_desk.py', DESK_PY), ('화면 index.html', os.path.join(MOD, 'view', 'index.html'))):
        t = read(p)
        ok(f'{name} 에 1_수집 글자 0', t and '1_수집' not in t, p)
    reach = [x for x in (con.get('touches') or []) + (con.get('reads') or []) + watch if x.startswith('1_수집')]
    ok('contract·watch 가 1_수집 에 안 닿음 · forbids 에 1_수집/**', '1_수집/**' in (con.get('forbids') or []) and not reach, (reach, con.get('forbids')))

    # ── ⑤ 전체 스위치 ──
    root = tempfile.mkdtemp(prefix='collect-core-')
    try:
        switch_cases(root)
        mylms_url(root)
        wake_cases(root)
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # ── ⑦ git 밖 ──
    try:
        r = subprocess.run(['git', '-C', VAULT, 'check-ignore', '-q', SWITCH], capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        ok('collect.local.json = git 밖(.gitignore)', r.returncode == 0, r.returncode)
    except OSError as e:
        print(f'  (git 없음 — 건너뜀 · {e})')

    n = sum(res)
    print(f'\n{n}/{len(res)} 통과')
    return 0 if n == len(res) else 1


def temp_vault(root):
    tv = os.path.join(root, 'vault')
    ts = os.path.join(tv, '3_시스템')
    for d in ('lms', 'collect', os.path.join('_index', 'lms'), os.path.join('_index', 'collect')):
        os.makedirs(os.path.join(ts, d), exist_ok=True)
    for f in ('web-collect.py', 'lms-auto.py', 'filter-learn.py', 'notice-filter.py', 'fileops.py', 'roles.py', 'roles.json', 'claude_bin.py', 'schedule.py',
              'options.py', 'options.registry.json'):    # lms-tasks.ps1 은 옮기지 않는다 — 예약은 PC 전체 것이라 시험 볼트에서 진짜 대본이 돌면 안 된다
        if os.path.exists(os.path.join(SYS, f)):
            shutil.copy2(os.path.join(SYS, f), ts)
    tm = os.path.join(tv, '.claude', 'skills', 'collect_desk', 'scripts')
    os.makedirs(tm, exist_ok=True)
    shutil.copy2(DESK_PY, tm)
    with open(os.path.join(ts, 'lms', 'courses.json'), 'w', encoding='utf-8') as f:
        json.dump({}, f)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', FILEOPS_NO_OBSIDIAN='1', LMS_AUTO_STATE=os.path.join(root, 'lms-state'), DESK_NO_OPEN='1')
    return tv, ts, env


def put(p, d):
    if d is None:
        if os.path.exists(p):
            os.remove(p)
        return
    with open(p, 'w', encoding='utf-8') as f:
        f.write(d if isinstance(d, str) else json.dumps(d))


def switch_cases(root):
    tv, ts, env = temp_vault(root)
    new, old = os.path.join(ts, 'collect.local.json'), os.path.join(ts, 'lms', 'desk.json')
    cases = [('없음', None, None, (False, False)),
             ('false', {'all_off': False, 'auto_judge': False}, None, (False, False)),
             ('깨짐', '{깨진', None, (False, False)),
             ('켬', {'all_off': True, 'auto_judge': True}, None, (True, True)),
             ('옛 자리만(한 판 동안 읽음)', None, {'all_off': True, 'auto_judge': True}, (True, True)),
             ('새 자리 우선(false 가 옛 자리 true 를 이김)', {'all_off': False, 'auto_judge': False}, {'all_off': True, 'auto_judge': True}, (False, False)),
             ('새 자리 깨짐 + 옛 자리 = 옛 자리', '{깨진', {'all_off': True}, (True, False)),
             ('칸마다 따로(새 자리 auto_judge · 옛 자리 all_off)', {'auto_judge': True}, {'all_off': True}, (True, True)),
             ('값 꼴 = true 일 때만(글자 "true"·1 은 끔)', {'all_off': 'true', 'auto_judge': 1}, None, (False, False)),
             ('옛 자리 mylms 칸만(enabled·wake) = 전체 스위치 아님', None, {'enabled': True, 'wake': False}, (False, False))]
    for name, n, o, (want_off, want_judge) in cases:
        put(new, n)
        put(old, o)
        r = subprocess.run([sys.executable, os.path.abspath(__file__), '--probe', tv], cwd=tv, env=env, capture_output=True, encoding='utf-8', errors='replace', timeout=120)
        try:
            got = json.loads(r.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            ok(f'[스위치 {name}] 읽기', False, (r.returncode, r.stdout[-200:], r.stderr[-300:]))
            continue
        want = [want_off, want_judge]
        same = all(got[k] == want for k in ('web-collect', 'lms-auto', 'filter-learn', 'collect_desk', 'view'))
        ok(f'[스위치 {name}] 엔진 셋·창 대본·화면 = 전체 끔 {want_off} · 자동 판정 {want_judge} · known paused · 자동 판정 대상',
           same and got['auto_on'] is want_judge and got['paused'] is want_off, got)
    put(new, None)
    put(old, None)

    # 창 set — 새 자리에 쓰고 옛 자리 같은 칸은 걷는다 · mylms 칸(enabled·wake)은 옛 자리 그대로(정할 것 2 전)
    dk = lambda *a: subprocess.run([sys.executable, os.path.join(tv, '.claude', 'skills', 'collect_desk', 'scripts', 'collect_desk.py'), *a],
                                   cwd=tv, env=env, capture_output=True, encoding='utf-8', errors='replace', timeout=120)
    known = lambda: (load(os.path.join(ts, 'lms', 'known.json')) or {}).get('paused')
    r = dk('set', '*', 'all_off', 'true')
    ok('창 set * all_off true = 새 자리에만 · 옛 자리 안 생김 · known paused', r.returncode == 0 and load(new) == {'all_off': True} and not os.path.exists(old) and known() is True,
       (r.returncode, r.stderr[-200:], load(new), os.path.exists(old), known()))
    r = dk('set', '*', 'auto_judge', 'true')
    ok('창 set * auto_judge true = 새 자리 칸 더함', r.returncode == 0 and load(new) == {'all_off': True, 'auto_judge': True}, (r.returncode, r.stderr[-200:], load(new)))
    put(old, {'all_off': True, 'auto_judge': True, 'enabled': False, 'wake': False})
    r = dk('set', '*', 'all_off', 'false')
    ok('창 set * all_off false = 새 자리 false · 옛 자리 all_off 만 걷음', r.returncode == 0 and load(new) == {'all_off': False, 'auto_judge': True}
       and load(old) == {'auto_judge': True, 'enabled': False, 'wake': False}, (r.returncode, r.stderr[-200:], load(new), load(old)))
    r = dk('set', '*', 'auto_judge', 'false')
    ok('창 set * auto_judge false = 옛 자리에 mylms 칸만 남음', r.returncode == 0 and load(old) == {'enabled': False, 'wake': False}
       and load(new) == {'all_off': False, 'auto_judge': False}, (r.returncode, r.stderr[-200:], load(new), load(old)))
    r = dk('set', 'mylms', 'wake', 'true')
    ok('창 set mylms wake = 기능 단계로(desk.json 에 안 씀 · 깨우기 통일) · 전체 스위치 안 건드림', r.returncode == 0 and load(old) == {'enabled': False}
       and load(new) == {'all_off': False, 'auto_judge': False}, (r.returncode, r.stderr[-200:], load(new), load(old)))
    before = (read(new), read(old))
    for args in (('*', 'all_off', '켬'), ('*', 'wake', 'false')):
        r = dk('set', *args)
        ok(f'창 set {" ".join(args)} = 거절 · 파일 그대로', r.returncode == 2 and (read(new), read(old)) == before, (r.returncode, r.stderr[-200:]))
    put(new, None)
    put(old, None)


def mylms_url(root):
    src = read(DESK_PY)
    ok('collect_desk.py 에 학교 주소·MYLMS_URL 0', src and 'MYLMS_URL' not in src and not re.search(r'https?://[a-z0-9.-]*\.ac\.kr', src), re.findall(r'https?://[^\s\'"]+', src)[:3])
    tv, ts, env = os.path.join(root, 'vault'), os.path.join(root, 'vault', '3_시스템'), dict(os.environ, PYTHONIOENCODING='utf-8', DESK_NO_OPEN='1', FILEOPS_NO_OBSIDIAN='1')
    man = os.path.join(ts, 'lms', 'manifest.json')
    dk = lambda *a: subprocess.run([sys.executable, os.path.join(tv, '.claude', 'skills', 'collect_desk', 'scripts', 'collect_desk.py'), *a],
                                   cwd=tv, env=env, capture_output=True, encoding='utf-8', errors='replace', timeout=120)

    def row():
        r = dk('view')
        try:
            s = next(x for x in json.loads(r.stdout.strip().splitlines()[-1])['sources'] if x['id'] == 'mylms')
            return s['url'], s['host']
        except (ValueError, IndexError, StopIteration, KeyError):
            return ('읽기 실패', r.stderr[-200:])
    for name, m, url in (('host_permissions 첫 줄', {'host_permissions': ['https://lms.example.edu/*', 'https://other.example.edu/*']}, 'https://lms.example.edu/'),
                         ('manifest 없음', None, ''), ('와일드카드 호스트', {'host_permissions': ['https://*.example.edu/*']}, ''),
                         ('host_permissions 꼴 틀림', {'host_permissions': 'https://lms.example.edu/*'}, '')):
        put(man, m)
        u, h = row()
        o = dk('open', 'mylms')
        opened = o.returncode == 0 and o.stdout.strip() == url if url else o.returncode == 2 and '주소 없음' in o.stderr
        ok(f'mylms 주소 · {name} = «{url or "빈칸"}» · 사이트 열기 {"그 주소" if url else "거절"}', u == url and h == (url.split('/')[2] if url else '') and opened,
           (u, h, o.returncode, o.stdout[-100:], o.stderr[-100:]))
    real = load(os.path.join(SYS, 'lms', 'manifest.json'))
    if isinstance(real, dict):
        put(man, real)
        u, h = row()
        ok('진짜 확장 manifest = https 주소 하나(호스트가 host_permissions 에 있음)', u.startswith('https://') and u.endswith('/') and h and any(h in p for p in real.get('host_permissions') or []), (u, h))
    put(man, None)


FAKE_TASKS = """param([switch]$Remove, [switch]$WakeOnly, [switch]$DryRun)
$s = (& py -3 (Join-Path $PSScriptRoot 'lms-auto.py') --wake-state 2>$null | Select-Object -Last 1)
Add-Content -Path (Join-Path $PSScriptRoot 'tasks-calls.log') -Value ("WakeOnly={0} DryRun={1} state={2}" -f $WakeOnly, $DryRun, $s)
"""
STUB = """function Register-ScheduledTask {{ Add-Content -Path '{log}' -Value ('등록 ' + ($args -join ' ')) }}
function Unregister-ScheduledTask {{ Add-Content -Path '{log}' -Value ('지움 ' + ($args -join ' ')) }}
function Get-ScheduledTask {{ $null }}
function Get-ScheduledTaskInfo {{ $null }}
& '{ps}' -WakeOnly -DryRun
"""


def wake_cases(root):
    """깨우기 통일(11-07 사용자 «두 스위치 통일») — 값은 기능 단계 lms.wake 하나 · 수집 창 깨우기·전체 끔·mylms 끔이 같은 예약 맞추기 길을 부름 · desk.json wake 는 안 읽음."""
    tv, ts = os.path.join(root, 'vault'), os.path.join(root, 'vault', '3_시스템')
    env = dict(os.environ, PYTHONIOENCODING='utf-8', FILEOPS_NO_OBSIDIAN='1', LMS_AUTO_STATE=os.path.join(root, 'lms-state'), DESK_NO_OPEN='1')
    new, old, opt = os.path.join(ts, 'collect.local.json'), os.path.join(ts, 'lms', 'desk.json'), os.path.join(ts, 'options.local.json')
    calls = os.path.join(ts, 'tasks-calls.log')
    with open(os.path.join(ts, 'lms-tasks.ps1'), 'w', encoding='utf-8-sig') as f:     # 가짜 예약 대본 — 불린 인자와 그때 값만 적는다
        f.write(FAKE_TASKS)
    for p in (new, old, opt, calls):
        put(p, None)
    run = lambda *a: subprocess.run([sys.executable, *a], cwd=tv, env=env, capture_output=True, encoding='utf-8', errors='replace', timeout=120)
    dk = lambda *a: run(os.path.join(tv, '.claude', 'skills', 'collect_desk', 'scripts', 'collect_desk.py'), *a)
    state = lambda: run(os.path.join(ts, 'lms-auto.py'), '--wake-state').stdout.strip()
    level = lambda: ((load(opt) or {}).get('levels') or {}).get('lms.wake')
    last = lambda: (read(calls).strip().splitlines() or [''])[-1]
    wake_on = lambda: next((x.get('wakeOn') for x in json.loads(dk('view').stdout.strip().splitlines()[-1])['sources'] if x['id'] == 'mylms'), None)

    ok('[깨우기] 처음 = 기능 단계 없음 → 켬(on) · 수집 창 스위치 켬', state() == 'on' and wake_on() is True, (state(), wake_on()))
    put(old, {'wake': False})
    ok('[깨우기] desk.json 옛 wake 칸은 안 읽음(값은 기능 단계 하나)', state() == 'on' and wake_on() is True, (state(), wake_on()))
    r = dk('set', 'mylms', 'wake', 'false')
    ok('[깨우기] 창에서 끔 = 기능 단계 low · 옛 칸 걷음 · 예약 맞추기(-WakeOnly -DryRun) 한 번 · off level_low',
       r.returncode == 0 and level() == 'low' and load(old) == {} and last() == 'WakeOnly=True DryRun=True state=off level_low' and wake_on() is False and state() == 'off level_low',
       (r.returncode, r.stderr[-200:], level(), load(old), last(), wake_on()))
    r = dk('set', 'mylms', 'wake', 'true')
    ok('[깨우기] 창에서 켬 = 기능 단계 high · 예약 맞추기 · on', r.returncode == 0 and level() == 'high' and last().endswith('state=on') and wake_on() is True,
       (r.returncode, r.stderr[-200:], level(), last()))
    n0 = len(read(calls).splitlines())
    r = dk('set', '*', 'all_off', 'true')
    ok('[깨우기] 전체 끔 = 같은 길로 예약 맞추기 · off all_off(헛깨우기 막음) · 고른 단계는 그대로', r.returncode == 0 and last().endswith('state=off all_off') and level() == 'high',
       (r.returncode, r.stderr[-200:], last(), level()))
    r = dk('set', '*', 'all_off', 'false')
    ok('[깨우기] 전체 켬 = 예약 다시 맞춤 · on', r.returncode == 0 and last().endswith('state=on'), (r.returncode, last()))
    r = dk('set', 'mylms', 'enabled', 'false')
    ok('[깨우기] mylms 끔 = 예약 맞추기 · off source_off', r.returncode == 0 and last().endswith('state=off source_off'), (r.returncode, last()))
    r = dk('set', 'mylms', 'enabled', 'true')
    r2 = dk('set', '*', 'auto_judge', 'true')
    ok('[깨우기] mylms 켬 = on · 자동 판정은 예약을 안 건드림', r.returncode == 0 and r2.returncode == 0 and last().endswith('state=on') and len(read(calls).splitlines()) == n0 + 4,
       (r.returncode, r2.returncode, last(), len(read(calls).splitlines()) - n0))
    put(new, {'all_off': True})
    call = ("import importlib.util as u,sys;s=u.spec_from_file_location('la',r'%s');m=u.module_from_spec(s);s.loader.exec_module(m);"
            "m.hold_awake=lambda:print('HOLD');sys.argv=['x','--wake'];m.main()") % os.path.join(ts, 'lms-auto.py')
    r = run('-c', call)
    ok('[깨우기] 꺼진 날 아침 깨우기 = 크롬 안 띄움 · 예약을 값대로 맞춤(다음 날부터 안 깨움)', 'HOLD' not in r.stdout and last().endswith('state=off all_off'), (r.stdout[-200:], last()))
    put(new, None)
    put(old, None)
    put(calls, None)
    os.remove(os.path.join(ts, 'lms-tasks.ps1'))

    # 진짜 lms-tasks.ps1 — 시험 볼트에 다른 이름으로 두고 -DryRun + 예약 명령 대체 함수(두 겹)로만 돌린다. 예약은 PC 전체 것이라 진짜로 불리면 안 된다.
    real = os.path.join(SYS, 'lms-tasks.ps1')
    if not os.path.exists(real):
        return print('  (lms-tasks.ps1 없음 — 진짜 예약 대본 시험 건너뜀)')
    src = read(real)
    i_gate, i_wake, i_tick = src.find('if ($DryRun) { exit 0 }'), src.find('Register-ScheduledTask -TaskName $names[0]'), src.find('Register-ScheduledTask -TaskName $names[1]')
    guarded = (src.count('Unregister-ScheduledTask') == 1 and 'if ($DryRun) { Write-Output "시험: $n 지움"; return }' in src     # 지우기는 Drop-Task 한 곳뿐
               and 0 < src.find('if ($DryRun) { Write-Output "시험: $($names[0]) 등록') < i_wake < i_gate < i_tick and src.count('Register-ScheduledTask -TaskName') == 2)
    ok('진짜 lms-tasks.ps1 — 지우기는 Drop-Task(시험이면 안 지움) · 시험이면 15분 등록 전에 끝남', guarded, '대본 꼴이 바뀜 — 시험을 다시 볼 것')
    if not guarded:
        return
    ps = os.path.join(ts, 'lms-tasks-시험.ps1')
    shutil.copy2(real, ps)
    stub_log = os.path.join(root, 'stub.log')
    wrap = os.path.join(root, 'wrap.ps1')
    for name, sw, want in (('켬', None, '등록'), ('전체 끔', {'all_off': True}, '지움')):
        put(new, sw)
        put(stub_log, None)
        with open(wrap, 'w', encoding='utf-8-sig') as f:
            f.write(STUB.format(log=stub_log, ps=ps))
        r = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', wrap], cwd=tv, env=env,
                           capture_output=True, encoding='utf-8', errors='replace', timeout=120, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        out = r.stdout
        ok(f'진짜 lms-tasks.ps1 -WakeOnly -DryRun · {name} = «시험: … {want}» · 예약 명령 0회', r.returncode == 0 and f'시험: 외부뇌 LMS 깨우기 {want}' in out and not os.path.exists(stub_log)
           and '반영' not in out, (r.returncode, out[-300:], r.stderr[-200:], read(stub_log)))
    put(new, None)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) > 2 and sys.argv[1] == '--probe':
        probe(sys.argv[2])
        sys.exit(0)
    sys.exit(main())
