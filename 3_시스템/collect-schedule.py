"""수집 시각 예약 엔진 — 출처마다 «외부뇌-수집 <id>» 윈도 예약을 수집 설정대로 맞추고, 그 예약이 부르면 받을 차례인 출처를 받는다(11-16).

  py -3 3_시스템/collect-schedule.py --sync [--dry] [--drop]   # 시각 예약을 수집 설정대로 + 15분 반영 예약이 없으면 만듦(수집 창이 시각·스위치를 바꿀 때 부름 · --drop = 모두 지움)
  py -3 3_시스템/collect-schedule.py --at <출처>               # (시각 예약이 부름) 그 출처를 받을 차례면 받기
  py -3 3_시스템/collect-schedule.py --list                    # 있어야 할 예약(이름·시각·깨우기·명령) — 시험·점검

출처 = 조리법 `3_시스템/collect/<id>.json`(켬 · 계약 있음 · `at` 있음) → 매일 그 시각 · 놓치면 깬 뒤 곧.
크롬이 필요한 출처(로그인 가족)는 «제공자»가 예약 줄과 받기를 맡는다 — 제공자 = 이 폴더의 `collect-browser.py`(조리법 `collect/browser/*.json` 이 있을 때만 · 없으면 그 출처는 없음 · 11-16 S4).
  제공자 약속: schedule_tasks() → {예약 이름: (시각들, 깨우기, 행위 인자, 설명)} · run_at(sid) → 받기 · at_sources() → 맡는 출처 id 목록.
PC 를 깨울지 = 수집 창 «잠든 PC»(collect.local.json wake_pc · 없으면 깨움). 시각이 없는 출처는 15분 반영이 recheck_hours 로 돌린다.
15분 반영 예약 «외부뇌-수집 반영»(brain.py run collect.tick · S7): 명령 줄이 같은 예약(이름 무관 · 옛 이름 포함)이 있으면 그것이 맡고 안 만든다 · 예약 목록을 못 읽으면 안 만든다(겹쳐 돌지 않게).
다른 볼트가 맡으면 안 건드림: 수집 예약이 가리키는 brain.py 가 다른 볼트에 아직 있으면 --sync 는 아무것도 안 바꾼다(시험·사본 볼트가 진짜 예약을 덮어쓰지 않게 · 11-17).
시험만: COLLECT_TEST_STATE(상태 폴더 · 예약을 안 건드리고 할 일을 tasks-sync.log 에) · COLLECT_TASK_DRY=1(예약을 안 건드리고 할 일만 적음).
"""
import argparse
import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

SYS = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(SYS)
sys.path.insert(0, SYS)
import collectlib as cl  # noqa: E402

TASK = '외부뇌-수집 '                                       # 예약 이름 머리 — 이 머리 밖 예약은 안 건드린다
TICK = TASK + '반영'                                       # 15분 반영 예약(S7 · 본체 길)
TICK_ACT = ['collect.tick']                                # 그 예약이 부르는 행위(시각 받기 `--at` 없는 것)
TEST_STATE = os.environ.get('COLLECT_TEST_STATE') or ''         # 시험 상태 폴더(있으면 예약을 안 건드림)
STATE = TEST_STATE or os.path.join(SYS, '_index', 'collect')  # 반영 기록·잠금 = 엔진 자리(S6 · 로그인 출처의 기록은 그 출처 상태 폴더)
LOG = os.path.join(STATE, 'tick.log') if not TEST_STATE else os.path.join(STATE, 'auto.log')
PY = sys.executable


def log(msg):
    cl.log_line(LOG, msg)
    print(msg)


def dry_default():
    return bool(TEST_STATE or os.environ.get('COLLECT_TASK_DRY'))


_prov = []


def provider():
    """로그인 가족 제공자(collect-browser.py) — 대본이나 조리법(collect/browser/*.json)이 없으면 None(그 출처의 예약이 없을 뿐 웹 예약은 돈다)."""
    if not _prov:
        p = os.path.join(SYS, 'collect-browser.py')
        m = None
        if os.path.isfile(p) and glob.glob(os.path.join(SYS, 'collect', 'browser', '*.json')):
            try:
                sp = importlib.util.spec_from_file_location('collect_browser_provider', p)
                m = importlib.util.module_from_spec(sp)
                sp.loader.exec_module(m)
            except Exception as e:                  # 제공자가 깨져도 웹 예약은 맞춘다
                log(f'시각 예약: 제공자 못 읽음 `{e!r}`')
                m = None
        _prov.append(m)
    return _prov[0]


def web_tasks(wake):
    out = {}
    for p in sorted(glob.glob(os.path.join(SYS, 'collect', '*.json'))):
        try:
            rc = json.load(open(p, encoding='utf-8'))
            at = cl.at_times(rc.get('at'))
        except (OSError, ValueError):
            continue
        if isinstance(rc, dict) and at and rc.get('id') and rc.get('enabled') is not False and (rc.get('contract') or '').strip():
            out[TASK + rc['id']] = (at, wake, ['collect.at', '--', '--at', rc['id']], f'{rc.get("name") or rc["id"]}(웹 받기)')
    return out


def desired_tasks():
    """시각 예약으로 있어야 할 것 — {예약 이름: (시각들, PC 깨우기, brain.py 행위 인자, 설명)}. 전체 끔이면 없음(헛돌림을 막음).
    깨우기는 S3 절전에서 · 전원 구성표 «절전 모드 해제 타이머 허용»이 켜진 전원에서만 통한다. 종료한 PC 는 못 깨우고 켠 뒤 한 번 돈다."""
    sw = cl.switches(SYS)
    if sw.get('all_off') is True:
        return {}
    wake = sw.get('wake_pc') is not False        # «잠든 PC» — 깨움 = 그 시각에 PC 를 깨움 · 깬 뒤 = 안 깨우고 깬 뒤 놓친 것 한 번(StartWhenAvailable)
    out = {}
    m = provider()
    if m is not None and hasattr(m, 'schedule_tasks'):
        out.update(m.schedule_tasks(wake))
    out.update(web_tasks(wake))
    return out


def task_xml(at, wake, act, desc):
    """예약 한 줄의 XML(schtasks /XML) — 매일 그 시각들 · 놓치면 곧 · 겹치면 새것 무시 · 40분 · 로그온한 사용자 권한(창이 사용자 화면에 뜬다 · 크롬은 최소화)."""
    from xml.sax.saxutils import escape
    now = time.time()
    trig = []
    for t in at:
        h, m = map(int, t.split(':'))
        lt = time.localtime(now)
        s = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
        if s <= now:                    # 시작점을 다음 그 시각으로 — 지난 시각을 «놓침»으로 보고 바로 도는 일을 막는다
            s = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday + 1, h, m, 0, 0, 0, -1))
        trig.append(f'<CalendarTrigger><StartBoundary>{time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(s))}</StartBoundary><Enabled>true</Enabled>'
                    '<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger>')
    pyw = shutil.which('pyw') or r'C:\Windows\pyw.exe'
    args = f'-3.11 "{os.path.join(SYS, "brain.py")}" run {act[0]} --by schedule' + ''.join(' ' + x for x in act[1:])
    return ('<?xml version="1.0" encoding="UTF-16"?>\n<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
            f'<RegistrationInfo><Description>{escape("외부뇌 수집 시각: " + desc + " · " + " ".join(at) + " · 수집 창이 맞춘다(collect-schedule.py --sync)")}</Description></RegistrationInfo>'
            f'<Triggers>{"".join(trig)}</Triggers>'
            '<Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>'
            '<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>'
            '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable>'
            f'<WakeToRun>{"true" if wake else "false"}</WakeToRun><ExecutionTimeLimit>PT40M</ExecutionTimeLimit><Priority>7</Priority>'
            '<IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings></Settings>'
            f'<Actions Context="Author"><Exec><Command>{escape(pyw)}</Command><Arguments>{escape(args)}</Arguments><WorkingDirectory>{escape(VAULT)}</WorkingDirectory></Exec></Actions></Task>')


def tick_xml():
    """15분 반영 예약의 XML — 지금 1분 뒤부터 15분마다 끝없이 · 놓치면 곧 · 겹치면 새것 무시 · 30분 · 배터리에서도 · PC 를 깨우지 않음."""
    from xml.sax.saxutils import escape
    start = time.strftime('%Y-%m-%dT%H:%M:%S', time.localtime(time.time() + 60))
    pyw = shutil.which('pyw') or r'C:\Windows\pyw.exe'
    args = f'-3.11 "{os.path.join(SYS, "brain.py")}" run {TICK_ACT[0]} --by schedule'
    return ('<?xml version="1.0" encoding="UTF-16"?>\n<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
            f'<RegistrationInfo><Description>{escape("외부뇌 수집 15분 반영: 확장이 내려받은 것을 볼트에 반영 · 웹 출처는 받을 차례만 · 수집 창이 맞춘다(collect-schedule.py --sync)")}</Description></RegistrationInfo>'
            f'<Triggers><TimeTrigger><Repetition><Interval>PT15M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>'
            f'<StartBoundary>{start}</StartBoundary><Enabled>true</Enabled></TimeTrigger></Triggers>'
            '<Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>'
            '<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>'
            '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable>'
            '<WakeToRun>false</WakeToRun><ExecutionTimeLimit>PT30M</ExecutionTimeLimit><Priority>7</Priority>'
            '<IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings></Settings>'
            f'<Actions Context="Author"><Exec><Command>{escape(pyw)}</Command><Arguments>{escape(args)}</Arguments><WorkingDirectory>{escape(VAULT)}</WorkingDirectory></Exec></Actions></Task>')


TICK_LINE = re.compile(r'^"[^"]*","\\([^"]+)",.*\brun ' + re.escape(TICK_ACT[0]) + r' --by schedule",')


def tick_owner(rows=None):
    """15분 반영을 맡은 예약 이름 — 명령 줄 끝이 `run collect.tick --by schedule`(시각 받기 `--at` 없음)인 예약 · 없으면 '' · 목록을 못 읽으면 None.
    줄 꼴로 읽는다 — schtasks /FO CSV 는 명령 줄 안의 따옴표를 겹치지 않아 CSV 로 읽으면 칸이 깨진다(11-16 실측).
    rows = schtasks /Query /FO CSV /V /NH 의 줄(시험이 넣음)."""
    if rows is None:
        rc, out = schtasks('/Query', '/FO', 'CSV', '/V', '/NH')
        if rc or not out.strip():
            return None
        rows = out.splitlines()
    names = sorted({m.group(1) for m in map(TICK_LINE.match, rows) if m})
    return (TICK if TICK in names else names[0]) if names else ''


OWNER_PY = re.compile(r'"([^"]+\\brain\.py)" run collect\.(?:tick|at)\b')


def foreign_owner(rows=None):
    """이 PC 의 수집 예약(15분 반영 · «외부뇌-수집 …»)이 가리키는 다른 볼트 — 그 볼트의 brain.py 가 아직 있을 때만 · 없으면 ''.
    시험·사본 볼트가 진짜 볼트의 예약을 제 경로로 덮어쓰지 않게 한다(11-17 실측: 격리 시험 사본이 --sync 해 예약 10개가 지워진 사본을 가리킴).
    사라진 사본을 가리키는 예약은 주인이 없다고 보고 이 볼트가 되찾는다. 목록을 못 읽으면 ''(막지 않음). rows = schtasks /Query /FO CSV /V /NH 의 줄(시험이 넣음)."""
    if rows is None:
        rc, out = schtasks('/Query', '/FO', 'CSV', '/V', '/NH')
        if rc or not out.strip():
            return ''
        rows = out.splitlines()
    me = os.path.normcase(os.path.abspath(VAULT))
    for ln in rows:
        n = re.match(r'^"[^"]*","\\([^"]+)",', ln)
        p = OWNER_PY.search(ln)
        if not (n and p and (n.group(1).startswith(TASK) or TICK_LINE.match(ln))):
            continue
        v = os.path.dirname(os.path.dirname(p.group(1)))
        if os.path.normcase(os.path.abspath(v)) != me and os.path.isfile(p.group(1)):
            return v
    return ''


def tick_ensure(done):
    """sync 끝에 — 15분 반영 예약이 없으면 «외부뇌-수집 반영»을 만든다(있으면 이름이 달라도 안 건드림 · 못 읽으면 안 만듦)."""
    own = tick_owner()
    if own != '':
        return 0
    xml = tick_xml()
    fd, tmp = tempfile.mkstemp(suffix='.xml')
    os.close(fd)
    try:
        with open(tmp, 'w', encoding='utf-16') as f:
            f.write(xml)
        r, out = schtasks('/Create', '/TN', TICK, '/XML', tmp, '/F')
    finally:
        os.remove(tmp)
    done.append(f'{TICK}: {"15분마다" if not r else "못 등록 " + out[-160:]}')
    return r


def schtasks(*args):
    r = subprocess.run(['schtasks', *args], capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=60)
    out = r.stdout + r.stderr
    for enc in ('utf-8', 'oem', 'mbcs'):
        try:
            return r.returncode, out.decode(enc).strip()
        except (UnicodeDecodeError, LookupError):
            pass
    return r.returncode, out.decode('utf-8', 'replace').strip()


def existing_tasks():
    """지금 있는 시각 예약 이름(«외부뇌-수집 …»만 · 뿌리 폴더). 제공자의 옛 예약은 이름 머리 밖이라 안 건드린다(보통 권한으로 못 지움 · 지우기는 사용자)."""
    rc, out = schtasks('/Query', '/FO', 'CSV', '/NH')
    names = set()
    for ln in out.splitlines():
        m = re.match(r'^"\\([^"\\]+)"', ln)
        if m and m.group(1).startswith(TASK):
            names.add(m.group(1))
    return names


def legacy_left():
    """제공자가 알리는 옛 예약(LEGACY_TASKS) 중 남은 것 — 맞추기 결과 줄에만 적는다."""
    m = provider()
    return [n for n in (getattr(m, 'LEGACY_TASKS', ()) if m is not None else ()) if schtasks('/Query', '/TN', n)[0] == 0]


def sync_tasks(dry=False, drop=False):
    """시각 예약을 수집 설정대로 맞춘다 — 있어야 할 것은 다시 등록(같은 이름 덮어씀), 없어야 할 «외부뇌-수집 …»은 지운다.
    15분 반영 예약은 없을 때만 만든다(drop = 그것도 지움 · 이름이 다른 옛 15분 예약은 안 건드림). 돌려줌 = (rc, 한 줄씩 한 일). dry = 할 일만 적음(시험)."""
    if not TEST_STATE:
        other = foreign_owner()
        if other:                       # 시험·사본 볼트 — 진짜 볼트의 예약을 안 건드린다(되찾기 = 그 볼트를 지우거나 그 볼트에서 --drop)
            return 0, f'시각 예약: 안 건드림 — 이 PC 의 수집 예약은 다른 볼트 «{other}» 가 맡음(여기 = «{VAULT}»)'
    want = {} if drop else desired_tasks()
    have = existing_tasks() if not dry or not TEST_STATE else set()
    done, rc = [], 0
    for name in sorted(have - set(want) - (set() if drop else {TICK})):
        if dry:
            done.append(f'시험: {name} 지움')
            continue
        r, out = schtasks('/Delete', '/TN', name, '/F')
        rc |= r
        done.append(f'{name}: {"지움" if not r else "못 지움 " + out[-120:]}')
    for name, (at, wake, act, desc) in sorted(want.items()):
        if dry:
            done.append(f'시험: {name} 등록({" ".join(at)} · 깨우기 {"켬" if wake else "끔"})')
            continue
        xml = task_xml(at, wake, act, desc)
        fd, tmp = tempfile.mkstemp(suffix='.xml')
        os.close(fd)
        try:
            with open(tmp, 'w', encoding='utf-16') as f:
                f.write(xml)
            r, out = schtasks('/Create', '/TN', name, '/XML', tmp, '/F')
        finally:
            os.remove(tmp)
        rc |= r
        done.append(f'{name}: {"매일 " + " ".join(at) + (" · 깨우기" if wake else "") if not r else "못 등록 " + out[-160:]}')
    if not done:
        done.append('시각 예약: 바꿀 것 없음' if want else '시각 예약: 없음')
    if not dry and not drop:
        rc |= tick_ensure(done)
    if not dry:
        done += [f'{n}: 옛 예약 남음 — 돌아도 건너뜀 · 지우기는 사용자(관리자 터미널 schtasks /Delete /TN "{n}" /F)' for n in legacy_left()]
    if dry and TEST_STATE:              # 시험 — 맞추기가 불렸는지·무엇을 했을지를 한 줄로 남긴다(_eval collect_core_check)
        os.makedirs(STATE, exist_ok=True)
        with open(os.path.join(STATE, 'tasks-sync.log'), 'a', encoding='utf-8', newline='\n') as f:
            f.write(' | '.join(done) + '\n')
    return rc, '\n'.join(done)


def lock_path():
    """15분 반영·시각 받기·수집 창·적용 대본이 같이 쓰는 잠금(엔진 자리 · S6)."""
    return os.path.join(STATE, 'tick.lock' if not TEST_STATE else 'auto.lock')


def run_at(sid):
    """시각 예약 «외부뇌-수집 <출처>»가 부른다. 제공자가 맡는 출처 = 제공자 · 웹 = 받을 차례면 받는다(web-collect --source --due · 15분 확인과 같은 잠금)."""
    m = provider()
    if m is not None and sid in (getattr(m, 'at_sources', lambda: ())() or ()):
        return m.run_at(sid)
    if cl.switches(SYS).get('all_off') is True:
        return print('받은 것: 웹 새 글 0 (전체 꺼짐)')
    held = cl.try_lock(lock_path())
    if not held:
        log(f'시각 {sid}: 다른 처리 중 — 15분 확인이 이어 받는다')
        return print('받은 것: 웹 새 글 0 (다른 처리 중)')
    try:
        r = subprocess.run([PY, os.path.join(SYS, 'web-collect.py'), '--source', sid, '--due'], cwd=VAULT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        rc, out = r.returncode, (r.stdout or '') + (r.stderr or '')
    finally:
        held.close()
    lines = [ln for ln in out.splitlines() if ln.startswith(sid + ':') or '대기열' in ln]
    log(f'시각 {sid}: web-collect rc={rc} ' + (' · '.join(lines)[:400] if lines else '받을 차례 아님(이미 받음)'))
    if rc and cl.queue_add('web', f'web-collect.py --source {sid} 실패 rc={rc}', once='line'):
        log(f'대기열 web: web-collect.py --source {sid} 실패 rc={rc}')
    got = sum(int(x) for x in re.findall(r'받음 (\d+)/', out))
    print(f'받은 것: 웹 새 글 {got}')


def main():
    ap = argparse.ArgumentParser(description='수집 시각 예약 엔진')
    ap.add_argument('--sync', action='store_true')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--drop', action='store_true')
    ap.add_argument('--at', metavar='출처')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    if a.list:
        print(json.dumps({k: [v[0], v[1], v[2], v[3]] for k, v in sorted(desired_tasks().items())}, ensure_ascii=False, indent=1))
        own = tick_owner()
        return print('15분 반영: ' + ('예약 목록 못 읽음' if own is None else f'«{own}»' if own else f'없음 — --sync 가 «{TICK}» 을 만든다'))
    if a.sync:
        rc, out = sync_tasks(dry=a.dry or dry_default(), drop=a.drop)
        print(out)
        sys.exit(rc)
    if a.at:
        return run_at(a.at)
    ap.print_help()


if __name__ == '__main__':
    main()
