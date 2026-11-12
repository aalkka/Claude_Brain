# -*- coding: utf-8 -*-
"""수집 시각 설정(11-11 · 수집 설정) — 출처마다 «주기 ↔ 시각»과 시각 예약 맞추기를 잰다. 망 요청 0 · 예약 안 건드림 · 볼트에 안 씀(임시 볼트).

  py -3 3_시스템/_eval/collect_at_check.py

① web-collect due() — 시각이 지났고 그 뒤 안 받았을 때만 · 정하기 전 시각은 안 따라잡음 · 실패 뒤 한 시간 · 시각 없으면 recheck_hours · 틀린 꼴은 주기로
② 수집 창 set — 출처 at·주기(주기를 고르면 시각을 걷음)·묶음(@공지·@강의)·mylms at · 꼴·개수 거절 · 바꿀 때마다 시각 예약 맞추기(시험이면 dry 한 줄)
③ 예약 꼴 — task_xml 이 XML 로 읽힘 · 매일 그 시각(다음 그 시각부터) · 깨우기 켬/끔 · 명령 줄 = brain.py run … --by schedule · 잠든 PC(wake_pc) 깨움/깬 뒤가 모든 예약에
④ lms-auto --at — 받을 차례 아니면 «받을 차례 아님» 기록만(GET 0) · 전체 끔이면 건너뜀
⑤ chrome_up — 프로필 lockfile 을 크롬처럼 쓰기 막음으로 쥐면 떠 있음 · 놓으면·없으면 꺼짐
"""
import ctypes
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location('ccc', os.path.join(HERE, 'collect_core_check.py'))
ccc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ccc)
res = []


def ok(name, cond, detail=''):
    res.append(bool(cond))
    print(('통과 ' if cond else '실패 ') + name + ('' if cond else f' — {detail}'))


def mod(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def due_cases(wc):
    t = time.localtime()
    at = lambda h, m=0, d=0: time.mktime((t.tm_year, t.tm_mon, t.tm_mday + d, h, m, 0, 0, 0, -1))
    now = at(10)
    rc = {'at': ['09:00'], 'at_since': at(9, d=-1)}
    ok('[due] 09:00 시각 · 10:00 · 마지막 08:00 = 받을 차례', wc.due(rc, {'last_run': at(8)}, now))
    ok('[due] 마지막 09:30(시각 뒤 받음) = 아님', not wc.due(rc, {'last_run': at(9, 30)}, now))
    ok('[due] 시각을 09:30 에 정함 = 오늘 09:00 은 안 따라잡음', not wc.due({'at': ['09:00'], 'at_since': at(9, 30)}, {'last_run': at(8)}, now))
    ok('[due] 09:10 실패(last_try) · 09:40 = 한 시간 안이라 아님 · 10:20 = 다시', not wc.due(rc, {'last_run': at(8), 'last_try': at(9, 10)}, at(9, 40))
       and wc.due(rc, {'last_run': at(8), 'last_try': at(9, 10)}, at(10, 20)))
    ok('[due] 08:00 · 아직 오늘 시각 전 = 어제 09:00 뒤 받았으면 아님', not wc.due(rc, {'last_run': at(9, 5, -1)}, at(8)))
    ok('[due] 시각 둘(09:00·18:00) · 19:00 · 마지막 09:05 = 받을 차례', wc.due({'at': ['09:00', '18:00']}, {'last_run': at(9, 5)}, at(19)))
    ok('[due] 시각 없음 · 6시간 주기 · 3시간 전 = 아님 · 7시간 전 = 차례', not wc.due({'recheck_hours': 6}, {'last_run': now - 3 * 3600}, now)
       and wc.due({'recheck_hours': 6}, {'last_run': now - 7 * 3600, 'last_try': now - 7 * 3600}, now))
    ok('[due] 틀린 꼴(9:00) = 주기로(20시간)', not wc.due({'at': ['9:00']}, {'last_run': now - 3600}, now) and wc.validate({'id': 'ab', 'at': ['9:00']}) and any('at' in b for b in wc.validate({'id': 'ab', 'at': ['9:00']})))


def desk_cases(root):
    tv, ts, env = ccc.temp_vault(root)
    log = os.path.join(root, 'lms-state', 'tasks-sync.log')
    rp = lambda i: os.path.join(ts, 'collect', i + '.json')
    for i, extra in (('ku-a', {'filter': {'title_skip': 'x'}}), ('ku-b', {'filter': {'title_skip': 'x'}}), ('ku-c', {}), ('ku-off', {'enabled': False, 'at': ['07:00']})):
        ccc.put(rp(i), {'id': i, 'name': i.upper(), 'family': 'regex', 'contract': '시험', 'page': 'https://example.org/' + i, 'recheck_hours': 12, **extra})
    run = lambda *a: subprocess.run([sys.executable, os.path.join(tv, '.claude', 'skills', 'collect_desk', 'scripts', 'collect_desk.py'), *a], cwd=tv, env=env,
                                    capture_output=True, encoding='utf-8', errors='replace', timeout=120)
    last = lambda: (ccc.read(log).strip().splitlines() or [''])[-1]
    view = lambda: {s['id']: s for s in json.loads(run('view').stdout.strip().splitlines()[-1])['sources']}
    r = run('set', 'ku-a', 'at', '9:00')
    a = ccc.load(rp('ku-a'))
    ok('[창] ku-a 시각 9:00 = 조리법 at [09:00]·at_since · 예약 맞추기 = mylms + ku-a(잠든 PC 기본 = 깨움) · 끈 출처는 예약 없음',
       r.returncode == 0 and a.get('at') == ['09:00'] and a.get('at_since') and '외부뇌-수집 ku-a 등록(09:00 · 깨우기 켬)' in last() and '외부뇌-수집 mylms 등록(06:55 · 깨우기 켬)' in last()
       and 'ku-off' not in last(), (r.returncode, r.stderr[-200:], a, last()))
    v = view()['ku-a']
    ok('[창] 보기 = 방법 web · 시각 꼴 · 다음 = 시각 · 줄 글 «09:00»', v['method'] == 'web' and v['mode'] == 'at' and v['at'] == ['09:00'] and v['hourWord'] == '09:00' and v['next'].endswith('09:00'), v)
    r = run('set', '*', 'wake_pc', 'false')
    sw = ccc.load(os.path.join(ts, 'collect.local.json')) or {}
    ok('[창] 잠든 PC «깬 뒤» = collect.local.json wake_pc false · 예약 mylms·ku-a 모두 깨우기 끔 · 보기 wakePc false',
       r.returncode == 0 and sw.get('wake_pc') is False and '외부뇌-수집 mylms 등록(06:55 · 깨우기 끔)' in last() and '외부뇌-수집 ku-a 등록(09:00 · 깨우기 끔)' in last()
       and json.loads(run('view').stdout.strip().splitlines()[-1])['wakePc'] is False, (r.stderr[-200:], sw, last()))
    r = run('set', '*', 'wake_pc', 'true')
    ok('[창] 잠든 PC «깨움» = 모두 깨우기 켬', r.returncode == 0 and '외부뇌-수집 ku-a 등록(09:00 · 깨우기 켬)' in last() and '외부뇌-수집 mylms 등록(06:55 · 깨우기 켬)' in last(), last())
    ccc.put(os.path.join(ts, 'collect.local.json'), None)
    r = run('set', 'ku-a', 'at', '18:30,09:00')
    ok('[창] 시각 둘 = 정렬 [09:00, 18:30]', r.returncode == 0 and ccc.load(rp('ku-a'))['at'] == ['09:00', '18:30'] and '(09:00 18:30 · 깨우기 켬)' in last(), (r.stderr[-200:], last()))
    n = len(ccc.read(log).splitlines())
    bad = [run('set', 'ku-a', 'at', v) for v in ('25:00', '9시', '01:00,02:00,03:00,04:00,05:00')]
    ok('[창] 틀린 시각·다섯 개 = 거절 · 조리법 그대로 · 맞추기 안 부름', all(b.returncode for b in bad) and ccc.load(rp('ku-a'))['at'] == ['09:00', '18:30'] and len(ccc.read(log).splitlines()) == n,
       [b.stderr[-80:] for b in bad])
    r = run('set', 'ku-a', 'hours', '6')
    a = ccc.load(rp('ku-a'))
    ok('[창] 주기 6 = 시각 걷음(at·at_since 없음) · 예약에서 빠짐', r.returncode == 0 and a.get('recheck_hours') == 6 and 'at' not in a and 'at_since' not in a and 'ku-a' not in last(), (a, last()))
    r = run('set', '@공지', 'at', '07:30')
    ok('[창] 묶음 @공지 시각 07:30 = 거르는 출처 둘(ku-a·ku-b)만 · 구독(ku-c) 그대로 · 맞추기 한 번',
       r.returncode == 0 and ccc.load(rp('ku-a')).get('at') == ['07:30'] and ccc.load(rp('ku-b')).get('at') == ['07:30'] and 'at' not in ccc.load(rp('ku-c'))
       and 'ku-a 등록(07:30' in last() and 'ku-b 등록(07:30' in last() and len(ccc.read(log).splitlines()) == n + 2, (r.stderr[-200:], last()))
    r = run('set', '@강의', 'at', '08:00,20:00')
    ok('[창] 묶음 @강의 = mylms 시각(desk.json at) · 예약 mylms 08:00 20:00 깨우기 켬', r.returncode == 0 and ccc.load(os.path.join(ts, 'lms', 'desk.json')).get('at') == ['08:00', '20:00']
       and '외부뇌-수집 mylms 등록(08:00 20:00 · 깨우기 켬)' in last() and view()['mylms']['at'] == ['08:00', '20:00'], (r.stderr[-200:], last()))
    r = run('set', 'mylms', 'at', '')
    ok('[창] mylms 시각 비움 = desk at [] · mylms 예약 없음(크롬을 안 띄움)', r.returncode == 0 and ccc.load(os.path.join(ts, 'lms', 'desk.json')).get('at') == [] and 'mylms' not in last(), last())
    r = run('set', '@없는묶음', 'at', '07:00')
    r2 = run('set', '@공지', 'enabled', 'false')
    ok('[창] 없는 묶음·묶음 스위치 = 거절', r.returncode and r2.returncode, (r.stderr[-80:], r2.stderr[-80:]))
    r = run('set', 'ku-b', 'enabled', 'false')
    ok('[창] 시각 있는 출처를 끔 = 예약에서 빠짐', r.returncode == 0 and 'ku-b' not in last() and 'ku-a 등록(07:30' in last(), last())

    # ④ --at — 받을 차례 아님 · 전체 끔
    la = os.path.join(ts, 'lms-auto.py')
    st = os.path.join(ts, '_index', 'collect', 'ku-a.json')
    ccc.put(st, {'last_run': time.time(), 'last_try': time.time(), 'items': {}})
    r = subprocess.run([sys.executable, la, '--at', 'ku-a'], cwd=tv, env=env, capture_output=True, encoding='utf-8', errors='replace', timeout=120)
    alog = ccc.read(os.path.join(root, 'lms-state', 'auto.log'))
    ok('[--at] 방금 받은 출처 = «받을 차례 아님» 기록 · 웹 새 글 0', r.returncode == 0 and '시각 ku-a: web-collect rc=0 받을 차례 아님' in alog and '웹 새 글 0' in r.stdout, (r.stdout[-200:], r.stderr[-200:], alog[-300:]))
    ccc.put(os.path.join(ts, 'collect.local.json'), {'all_off': True})
    r = subprocess.run([sys.executable, la, '--at', 'ku-a'], cwd=tv, env=env, capture_output=True, encoding='utf-8', errors='replace', timeout=120)
    r2 = subprocess.run([sys.executable, la, '--sync-tasks'], cwd=tv, env=env, capture_output=True, encoding='utf-8', errors='replace', timeout=120)
    ok('[--at] 전체 끔 = 건너뜀 · 맞추기 = 시각 예약 없음', '전체 꺼짐' in r.stdout and r2.stdout.strip() == '시각 예약: 없음', (r.stdout[-100:], r2.stdout[-200:]))
    ccc.put(os.path.join(ts, 'collect.local.json'), None)
    return mod('la', la)


def xml_cases(la):
    x = la.task_xml(['09:00', '21:30'], False, ['collect.lms', '--', '--at', 'ku-a'], '장학 & 학사 <시험>')
    ns = {'t': 'http://schemas.microsoft.com/windows/2004/02/mit/task'}
    try:
        root = ET.fromstring(x.split('\n', 1)[1])
    except ET.ParseError as e:
        return ok('[예약] XML 로 읽힘', False, e)
    st = [time.mktime(time.strptime(b.text, '%Y-%m-%dT%H:%M:%S')) for b in root.findall('.//t:CalendarTrigger/t:StartBoundary', ns)]
    args = root.find('.//t:Arguments', ns).text
    ok('[예약] XML · 시각 둘 = 매일 트리거 둘 · 시작점은 지금 뒤 하루 안 · 깨우기 끔 · 놓치면 곧',
       len(st) == 2 and all(0 < s - time.time() <= 86400 for s in st) and root.find('.//t:WakeToRun', ns).text == 'false'
       and root.find('.//t:StartWhenAvailable', ns).text == 'true' and all(root.find('.//t:DaysInterval', ns) is not None for _ in st), (st, x[:300]))
    ok('[예약] 명령 줄 = brain.py run collect.lms --by schedule -- --at ku-a · 설명 글 그대로(꺾쇠·& 이스케이프)',
       args.endswith('brain.py" run collect.lms --by schedule -- --at ku-a') and '장학 & 학사 <시험>' in root.find('.//t:Description', ns).text, args)
    ok('[예약] 깨우기 켬 = WakeToRun true', '<WakeToRun>true</WakeToRun>' in la.task_xml(['06:55'], True, ['collect.lms.wake'], 'mylms'))


def chrome_cases(la, root):
    prof = os.path.join(root, 'prof')
    os.makedirs(prof, exist_ok=True)
    lf = os.path.join(prof, 'lockfile')
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateFileW.restype = ctypes.c_void_p
    h = k32.CreateFileW(lf, 0x40000000, 0x1, None, 2, 0x80, None)     # GENERIC_WRITE · FILE_SHARE_READ · CREATE_ALWAYS — 크롬과 같은 쥐기
    held = la.chrome_up(prof)
    k32.CloseHandle(ctypes.c_void_p(h))
    left = la.chrome_up(prof)
    os.remove(lf)
    ok('[크롬] lockfile 을 쥐면 떠 있음 · 놓으면(파일 남음) 꺼짐 · 없으면 꺼짐', held and not left and not la.chrome_up(prof), (held, left))


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    due_cases(mod('wc', os.path.join(SYS, 'web-collect.py')))
    root = tempfile.mkdtemp(prefix='collect-at-')
    la = desk_cases(root)
    xml_cases(la)
    chrome_cases(la, root)
    print(f'\n{sum(res)}/{len(res)} 통과')
    return 0 if all(res) else 1


if __name__ == '__main__':
    sys.exit(main())
