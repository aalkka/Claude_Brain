# -*- coding: utf-8 -*-
"""수집 관리 창의 자료 — 수집 설정·상태를 읽기만 해서 JSON 한 줄을 낸다. view 는 아무것도 쓰지 않는다.

  py -3 collect_desk.py view [--reason open|refresh]     # 화면 문이 부른다
  py -3 collect_desk.py view --practice [--acts JSON]    # 튜토리얼 연습 자료(E2) — 볼트를 안 읽고 안 쓴다 · acts = 쌓인 흉내 행위 [{id, args}]
  py -3 collect_desk.py set <출처 | mylms | *> <칸> <값>   # 아래는 사용자 동작 하나씩 — brain.py run collect_desk.* 로 불러 장부에 남긴다
  py -3 collect_desk.py fetch <출처 | mylms>              # 지금 받기 · 웹 = 그 자리에서 · mylms = 다음 15분 확인 때
  py -3 collect_desk.py judge <출처 | mylms>              # 판정(구독 사용량) · 누를 때만
  py -3 collect_desk.py item <출처> <글번호> <rescue|reject|restore|useless|useful>
  py -3 collect_desk.py reject <출처> <글번호> <낱말|낱말…> <메모>   # 거절 단추(11-09) — 제목에서 고른 낱말(| 로 이음)·메모 · 둘 다 빈칸이어도 됨
  py -3 collect_desk.py open <출처 | mylms | 후보 id>      # 사이트를 연다(화면은 sandbox 라 링크가 안 열린다)
  py -3 collect_desk.py contract <후보 id> <계약|안 함>    # 계약 = 대기열 한 줄 · 조리법은 Claude 가 탐색 뒤 쓴다
  py -3 collect_desk.py probe <주소>                       # 수집 추가(11-06 · 대화창 스킬 add·fix 가 부른다) — 한 쪽 탐색(피드 찾기·robots)
  py -3 collect_desk.py try <초안 id> [--view]             # 미리보기(저장 없음) — 초안 = 3_시스템/_index/collect/draft/<id>.json
  py -3 collect_desk.py add <초안 id>                      # 확정 = 초안 → 3_시스템/collect/<id>.json(사용자 «추가» 답 뒤 · 미리보기를 거친 그 초안만)
  py -3 collect_desk.py fix <초안 id>                      # 고침 = 구조 칸만 바꾼 초안 → 조리법 + 그 출처의 (Claude) 대기열 줄 닫기

출처 목록을 코드에 박지 않는다: 웹 = 3_시스템/collect/*.json · mylms = 3_시스템/lms/courses.json · 공휴일 = 2_지식/일정/공휴일.md · 후보 = 3_시스템/lms/candidates.json.
없으면 그 줄이 안 나온다(출처 0 인 배포판에서도 돈다). enabled·purpose·desk.json·collect.local.json 은 있으면 읽는다(없으면 켜짐·빈칸).
mylms 주소 = 확장 lms/manifest.json 의 host_permissions(코드에 학교를 박지 않는다).
쓰는 곳 = 조리법의 허용 칸 · collect.local.json(전체 스위치) · lms/desk.json(mylms) · 기능 단계 «아침 받기»(깨우기 — options.py · 예약은 lms-auto.py --wake-sync) · lms/courses.json · lms/candidates.json · 대기열 한 줄 + 엔진 호출. 임시 파일 뒤 교체 · 주소·정규식·가족·계약 문구는 안 고친다.
비밀번호를 다루지 않고 계약 없는 출처를 돌리는 길이 없다(받기·승인은 엔진의 계약·스위치 관문을 그대로 지난다).
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
SYS = os.path.join(VAULT, '3_시스템')
PLAN = os.path.join(VAULT, '2_지식', '일정')
ALARM_NOTE = '2_지식/일/외부뇌/알림-설정.md'
EVENTS = 8
ITEMS = 40
LATE_MIN_H = 24            # 하루 안 늦음은 PC 가 잠든 것일 수 있어 늦음으로 안 친다
LMS_LATE_H = 48            # 전 과목 20시간(신호 안 되면 12시간)의 두 배 넘게
LMS_SID = 'lms-post'       # notice-filter 의 LMS 글 출처 이름
BUSY_STALE = 30 * 60       # 받기·판정이 죽어 남은 표시를 이 뒤로는 안 믿는다(초)
NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
# 거절 창의 낱말 단추 — 제목 낱말 중 고르면 공지 거의 다를 막는 말·날짜는 안 띄운다(고른 낱말은 전 출처 제외어가 된다 · filter-learn)
COMMON = {'안내', '모집', '공고', '공지', '알림', '신청', '선발', '개최', '참여', '관련', '실시', '진행', '결과', '일정', '변경', '연장', '추가', '접수', '마감', '대상', '대상자', '학생', '학부', '학부생', '재학생'}


def title_words(title):
    out = []
    for w in re.findall(r'[가-힣A-Za-z0-9]{2,}', title or ''):
        if w not in COMMON and not re.fullmatch(r'제?\d+(?:년|학년도|학기|차|월|일|회|기|시|명)?', w) and w not in out:
            out.append(w)
    return out[:12]


def load(*p, default=None):
    try:
        with open(os.path.join(*p), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def read(*p):
    try:
        with open(os.path.join(*p), encoding='utf-8', errors='replace') as f:
            return f.read()
    except OSError:
        return ''


def fmt(t):
    return t.strftime('%m-%d %H:%M')


def words(rx):
    return [w for w in (rx or '').split('|') if w]


def where(it):
    """notice-filter.py notices() 와 같은 규칙."""
    if it.get('path'):
        return 'vault'
    if it.get('archived'):
        return 'arch'
    if it.get('stage'):
        return 'wait' if it.get('verdict') else 'pend'
    if it.get('verdict'):
        return 'ledger'
    return 'pend'


def note_of(it, sid, aid):
    """눌렀을 때 열 글 — 볼트 글 · 보관 칸 글 · 대기 칸 글(승인·거절 전에 읽는다). 장부 글은 본문이 없다."""
    idx = '3_시스템/_index/collect/'
    p = it.get('path') or (idx + 'archive/' + it['archived'] if it.get('archived') else '')
    if not p and it.get('stage'):
        p = f'{idx}stage/{sid}/{aid}.md'
    p = p.replace('\\', '/') if isinstance(p, str) and p.endswith('.md') else ''
    return p if p and os.path.exists(os.path.join(VAULT, *p.split('/'))) else ''


# ── 열린 수집 대기열 ──
QUEUE_LINE = re.compile(r'^- \[ \] (\d{4}-\d\d-\d\d \d\d:\d\d)\S* `([^`]*)` \(([^)]*)\) (.+)$')


def open_queue():
    out = []
    for line in read(SYS, '_index', '수집-대기열.md').splitlines():
        m = QUEUE_LINE.match(line)
        if m:
            out.append({'t': m.group(1)[5:], 'id': m.group(2), 'who': m.group(3), 's': m.group(4)[:80]})
    return out


# ── 알림 ──
def alarm_reader():
    try:
        sys.path.insert(0, SYS)
        import alarms
        s, problems = settings_of(alarms)
        return s, problems
    except Exception:
        return None, 0


def settings_of(alarms):
    r = alarms.load_settings()
    if isinstance(r, tuple):
        return r[0], len(r[1] or [])
    return r, 0


def alarm_of(cfg, name):
    if not name:
        return None
    if not cfg:
        return {'file': name, 'on': None}
    if not cfg.get('켬', True) or name not in cfg.get('파일', {}):
        return {'file': name, 'on': False}
    r = {**cfg.get('기본', {}), **cfg['파일'].get(name, {})}
    if r.get('끔'):
        return {'file': name, 'on': False}
    return {'file': name, 'on': True, 'days': r.get('며칠_전', []), 'at': r.get('시각', [])}


# ── 웹 출처 ──
LOG_LINE = re.compile(r'^(\d{4}-\d\d-\d\d) (\d\d:\d\d):\d\d (\S+): (.+)$')


def web_events():
    ev = {}
    for line in read(SYS, '_index', 'collect', 'web.log').splitlines():
        m = LOG_LINE.match(line)
        if not m:
            continue
        day, hm, sid, msg = m.groups()
        t = f'{day[5:]} {hm}'
        if msg.startswith(('목록', '표')):
            ev.setdefault(sid, []).append({'t': t, 's': msg.replace(' (첫 수집)', '')})
        elif msg.startswith('받음'):
            w = re.search(r'대기 칸 (\d+) · 제목 장부 (\d+)', msg)
            if w and (int(w.group(1)) or int(w.group(2))):
                ev.setdefault(sid, []).append({'t': t, 's': f'대기 {w.group(1)} · 거름 {w.group(2)}'})
        elif msg.startswith('판정 반영'):
            w = re.search(r'볼트에 들임 (\d+)', msg)
            ev.setdefault(sid, []).append({'t': t, 's': f'판정 · 볼트 {w.group(1) if w else 0}'})
    marks = load(SYS, '_index', 'collect', '평가.json', default={}) or {}
    for key, v in marks.items():
        if isinstance(v, dict) and ':' in key and v.get('at'):
            sid, aid = key.split(':', 1)
            ev.setdefault(sid, []).append({'t': v['at'][5:], 's': said(v.get('메모') or v.get('평가') or ''), 'me': True, 'aid': aid})
    return ev


# 단추 이름이 살리기·빼기에서 승인·거절로 바뀌기 전(11-09) 장부에 남은 낱말 — 기록은 그대로 두고 화면에서만 지금 이름으로
SAID_NOW = {'살림': '승인', '사용자 살림': '사용자 승인', '수집 창에서 뺌': '거절', '사용자: 수집 창에서 뺌': '사용자: 거절'}


def said(s):
    return SAID_NOW.get(s, s)


def titled(events, items):
    """사용자 표시 줄에 글 제목을 붙인다."""
    out = []
    for e in events:
        e = dict(e)
        t = (items.get(e.pop('aid', None)) or {}).get('title') if isinstance(items, dict) else None
        if t:
            e['s'] = f'{e["s"]} · {t.strip()[:24]}'
        out.append(e)
    return out


def busy_of(sid):
    p = busy_path(sid)
    try:
        if time.time() - os.path.getmtime(p) < BUSY_STALE:
            return read(p).strip() or '도는 중'
    except OSError:
        pass
    return ''


def web_source(path, events, queue, cfg, now):
    rc = load(path)
    if not isinstance(rc, dict) or not rc.get('id'):
        return None
    sid = rc['id']
    st = load(SYS, '_index', 'collect', sid + '.json', default={}) or {}
    items = st.get('items') or {}
    fam = rc.get('family')
    hours = float(rc.get('recheck_hours', 20))
    flt = rc.get('filter') or {}
    lst = rc.get('list') or rc.get('listing') or {}
    host = re.sub(r'^https?://(www\.)?', '', rc.get('page') or '').split('/')[0]
    last = dt.datetime.fromtimestamp(st['last_run']) if st.get('last_run') else None
    nxt = last + dt.timedelta(hours=hours) if last else None
    probs = [q for q in queue if q['id'] == sid]
    marks = load(SYS, '_index', 'collect', '평가.json', default={}) or {}
    s = {'id': sid, 'name': rc.get('name') or sid, 'host': host, 'url': rc.get('page') or '', 'busy': busy_of(sid), 'family': fam, 'purpose': rc.get('purpose') or '',
         'fix': any(q['who'] == 'Claude' for q in probs),       # 구조가 깨진 줄(Claude 몫)이 있으면 «고침» — 로그인·사용량 같은 사용자 줄은 아님
         'on': rc.get('enabled', True) is not False, 'hours': hours, 'hourWord': f'{hours:g}시간',
         'last': fmt(last) if last else '', 'next': fmt(nxt) if nxt and nxt > now else '곧',
         'late': bool(last and (now - last).total_seconds() / 3600 > max(hours * 2, LATE_MIN_H)),
         'pages': lst.get('pages'), 'att': rc.get('attachments') or None,
         'auto': flt.get('auto') is not False, 'keepDays': flt.get('keep_days', 90) if flt else None,
         'events': titled(sorted(events.get(sid, []), key=lambda e: e['t'], reverse=True)[:EVENTS], items),
         'problems': probs}
    if fam == 'calendar':
        cal = rc.get('calendar') or {}
        total = st.get('page1_rows') or 0
        kept = len(re.findall(r'^- ', read(PLAN, cal.get('output') or ''), re.M))
        s.update(group='일정', flow={'in': total, 'keep': kept}, skip=words(cal.get('skip')), keep=None, output=cal.get('output'), items=[], cnt=None)
    elif fam == 'listing':
        li = rc.get('listing') or {}
        total = st.get('page1_rows') or 0
        s.update(group='일정', flow={'in': total, 'keep': len(items)}, keep=words(li.get('keep')), skip=words(li.get('skip')), output=li.get('output'), cnt=None,
                 target=(li.get('need') or {}).get('target'),
                 items=[{'title': (v.get('title') or '').strip(), 'date': (v.get('apply') or '')[-16:-6], 'where': 'vault', 'why': '', 'note': ''} for v in items.values() if isinstance(v, dict)][:ITEMS])
    else:
        rows, cnt = [], {k: 0 for k in ('vault', 'pend', 'wait', 'ledger', 'arch')}
        for aid, it in items.items():
            if isinstance(it, dict):
                w = where(it)
                cnt[w] += 1
                rows.append({'id': aid, 'title': (it.get('title') or '').strip(), 'date': (it.get('date') or '')[:10], 'where': w, 'why': said(it.get('why') or '')[:70], 'note': note_of(it, sid, aid),
                             'mark': (marks.get(f'{sid}:{aid}') or {}).get('평가') or ''})
                if w == 'pend':
                    rows[-1]['words'] = title_words(it.get('title'))
        rows.sort(key=lambda x: x['date'], reverse=True)
        w = rc.get('words') or {}      # 낱말 관문(11-06) — 판정 층이 있으면 뺄 말 = 그 층의 title_skip, 없으면 words.skip · 남길 말 = words.keep
        s.update(group=rc.get('group') or ('공지' if flt else '구독'), cnt=cnt, skip=words(flt.get('title_skip') if flt else w.get('skip')),
                 keep=words(w.get('keep')) if not flt or w.get('keep') else None, output=flt.get('schedule'), items=rows)
    s['alarm'] = alarm_of(cfg, s.get('output'))
    return s


# ── mylms ──
def course_of(v):
    p = re.split(r'[\\/]', v.get('path') or '')
    return p[2] if len(p) > 2 else '?'


def mylms_url():
    """mylms 주소 — 확장 manifest(lms/manifest.json) host_permissions 첫 줄의 «https://호스트/»(수집 본체 통합 11-07). 없거나 못 읽거나 와일드카드면 빈칸."""
    man = load(SYS, 'lms', 'manifest.json', default={})
    hp = man.get('host_permissions') if isinstance(man, dict) else None
    m = re.match(r'^(https?://[^/*]+)/', hp[0]) if isinstance(hp, list) and hp and isinstance(hp[0], str) else None
    return m.group(1) + '/' if m else ''


def lms_source(queue, cfg, desk, now):
    courses = load(SYS, 'lms', 'courses.json')
    if not isinstance(courses, dict):
        return None
    man = load(SYS, '_index', 'lms', 'manifest.json', default={}) or {}
    its, fls, board = man.get('items') or {}, man.get('files') or {}, man.get('board') or {}
    posts, files = {}, {}
    for v in its.values():
        posts[course_of(v)] = posts.get(course_of(v), 0) + 1
    for v in fls.values():
        files[course_of(v)] = files.get(course_of(v), 0) + 1
    clist = [{'id': c, 'name': n, 'posts': posts.get(n, 0), 'files': files.get(n, 0), 'board': len(board.get(c, {})), 'on': True}
             for c, n in courses.items() if c.isdigit()]
    for c, why in (courses.get('_제외') or {}).items():
        clist.append({'id': c, 'name': re.sub(r'^\d{4}\s+', '', str(why).split(' — ')[0]), 'posts': 0, 'files': 0, 'board': 0, 'on': False})

    last_full = last_status = None
    have = ''
    for p in sorted(glob.glob(os.path.join(SYS, '_index', 'lms', 'runs', '*.json')), key=os.path.getmtime, reverse=True):
        d = load(p, default={}) or {}
        have = have or d.get('version') or ''          # 확장이 돌린 판 — 가장 최근 요약
        if d.get('kind') == 'run' and not last_full:
            last_full = d
        if d.get('kind') == 'status' and not last_status:
            last_status = d
        if last_full and last_status:
            break
    want = (load(SYS, 'lms', 'manifest.json', default={}) or {}).get('version') or ''

    ev = []
    for line in read(SYS, '_index', 'lms', 'auto.log').splitlines():
        m = re.match(r'^(\d{4}-\d\d-\d\d) (\d\d:\d\d):\d\d (.+)$', line)
        if not m:
            continue
        day, hm, msg = m.groups()
        t = f'{day[5:]} {hm}'
        if msg.startswith('lms-file'):
            w = re.search(r'새 글 (\d+).*파일 들임 (\d+)', msg)
            if w:
                ev.append({'t': t, 's': f'새 글 {w.group(1)} · 파일 {w.group(2)}'})
        elif '로그인 out' in msg:
            ev.append({'t': t, 's': '로그인 끊김', 'bad': True})
        elif '로그인 ok' in msg:
            ev.append({'t': t, 's': '로그인 됨', 'me': True})
        elif msg.startswith('깨우기: 크롬'):
            ev.append({'t': t, 's': '깨우기'})
    ev.reverse()
    last = dt.datetime.fromtimestamp(last_full['startedAt'] / 1000) if last_full and last_full.get('startedAt') else None
    web_ids = {os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(SYS, 'collect', '*.json'))} | {c.get('id') for c in cand_rows()}
    pend = load(SYS, '_index', 'lms', '마감-대기.json', default={}) or {}
    try:
        asked = dt.datetime.fromisoformat(desk.get('fetch_now') or '')
    except ValueError:
        asked = None
    url = mylms_url()
    return {'id': 'mylms', 'name': 'mylms', 'host': url.split('/')[2] if url else '', 'url': url, 'busy': busy_of('mylms'), 'pend': len(pend), 'ext': {'have': have, 'want': want},
            'fetchWait': bool(asked and (not last or asked > last)),     # 지금 받기를 눌렀고 그 뒤 받기가 아직 없음
            'family': 'lms', 'group': '강의', 'purpose': desk.get('purpose') or '',
            'on': desk.get('enabled', True) is not False, 'wakeOn': wake_chosen() == 'high', 'wake': '06:55',
            'hours': 0.25, 'hourWord': '15분', 'next': '15분마다', 'last': fmt(last) if last else '',
            'late': bool(last and (now - last).total_seconds() / 3600 > LMS_LATE_H),
            'login': (last_status or {}).get('login'),
            'loginAt': fmt(dt.datetime.fromtimestamp(last_status['at'] / 1000)) if last_status and last_status.get('at') else '',
            'courses': clist, 'events': ev[:EVENTS], 'items': [], 'cnt': None,
            'problems': [q for q in queue if q['id'] not in web_ids],
            'tot': {'posts': len(its), 'files': len(fls), 'board': sum(len(v) for v in board.values())},
            'alarm': alarm_of(cfg, 'LMS-마감.md')}


# ── 공휴일 ──
def holiday_source():
    text = read(PLAN, '공휴일.md')
    if not text:
        return None
    n = len(re.findall(r'"\d{4}-\d\d-\d\d"\s*:', text))
    p = os.path.join(PLAN, '공휴일.md')
    return {'id': 'holidays', 'name': '공휴일', 'host': 'calendar.google.com', 'family': 'ics', 'group': '일정', 'purpose': '', 'on': True, 'fixed': True,
            'hours': 720, 'hourWord': '30일', 'next': '주간 점검', 'last': dt.datetime.fromtimestamp(os.path.getmtime(p)).strftime('%m-%d'),
            'late': False, 'events': [], 'items': [], 'cnt': None, 'problems': [], 'flow': {'in': n, 'keep': n}, 'alarm': alarm_of(alarm_reader()[0], '공휴일.md')}


# ── 후보 ──
CAND = os.path.join(SYS, 'lms', 'candidates.json')


def cand_rows():
    d = load(CAND, default={}) or {}
    return [c for c in (d.get('candidates') or []) if isinstance(c, dict) and c.get('id')] if isinstance(d, dict) else []


def candidates():
    """아직 답이 «안 함» 이 아니고 조리법이 안 생긴 후보만 — 조리법이 생기면 그 출처 줄이 대신한다."""
    return [{k: c.get(k) or '' for k in ('id', 'name', 'host', 'measured', 'note', 'answer')} for c in cand_rows()
            if c.get('answer') != '안 함' and not os.path.exists(os.path.join(SYS, 'collect', c['id'] + '.json'))]


# ── 고치기 ──
REGEX_CH = re.compile(r'[\\()^$.*+?\[\]{}]')
DESK = os.path.join(SYS, 'lms', 'desk.json')                  # mylms 칸(enabled·wake·purpose·fetch_now)
SWITCH = os.path.join(SYS, 'collect.local.json')               # 전체 스위치(all_off·auto_judge) — 이 PC 의 결정 · git 밖
COURSES = os.path.join(SYS, 'lms', 'courses.json')
QUEUE = os.path.join(SYS, '_index', '수집-대기열.md')


def switches():
    """전체 스위치 — collect.local.json · 그 칸이 없으면 옛 자리 lms/desk.json 의 칸을 한 판 동안 읽는다(엔진과 같은 규칙 · 없음·깨짐 = 켜짐·자동 판정 끔)."""
    out = {}
    for p in (DESK, SWITCH):            # 뒤(새 자리)가 이긴다
        d = load(p)
        if isinstance(d, dict):
            out.update((k, d[k]) for k in ('all_off', 'auto_judge') if k in d)
    return out


class Refuse(Exception):
    pass


def save_json(path, d):
    tmp = os.path.join(os.path.dirname(path), '.' + os.path.basename(path) + '.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
        f.write('\n')
    for i in range(6):                  # 켜진 옵시디언이 쥐고 있을 때(ADR-034 WinError 5)
        try:
            return os.replace(tmp, path)
        except PermissionError:
            if i == 5:
                raise
            time.sleep(0.2)


def as_bool(v):
    if v not in ('true', 'false'):
        raise Refuse(f'true 나 false 여야 함: {v}')
    return v == 'true'


def as_num(v, lo, hi, kind):
    try:
        n = kind(v)
    except ValueError:
        raise Refuse(f'숫자여야 함: {v}')
    if not lo <= n <= hi:
        raise Refuse(f'{lo}~{hi} 여야 함: {v}')
    return n


def edit_words(holder, key, op, word, need_one=False):
    """낱말 칸 = 정규식 하나를 | 로 나눈 조각. 낱말은 글자 그대로 더하고 · 이미 정규식인 조각은 못 뺀다 · 순서는 그대로."""
    word = word.strip()
    if not word or len(word) > 40:
        raise Refuse('낱말은 1~40자')
    parts = [w for w in (holder.get(key) or '').split('|') if w]
    if op == '+':
        new = re.sub(r'([\\.^$*+?()\[\]{}|])', r'\\\1', word)
        if new not in parts:
            parts.append(new)
    else:
        if word not in parts:
            raise Refuse(f'없는 낱말: {word}')
        if REGEX_CH.search(word):
            raise Refuse(f'정규식 조각은 못 뺌: {word}')
        if need_one and len(parts) == 1:
            raise Refuse('남길 말은 하나는 있어야 함')     # 비면 엔진이 전부 남기거나 멈춘다
        parts.remove(word)
    joined = '|'.join(parts)
    try:
        re.compile(joined)
    except re.error as e:
        raise Refuse(f'정규식이 깨짐: {e}')
    if joined:
        holder[key] = joined
    else:
        holder.pop(key, None)           # 빈 글자는 모든 제목에 맞으니 칸을 없앤다


def reflect_known():
    """mylms 스위치·과목을 확장이 읽는 known.json 에 바로 반영(다음 15분 확인 때 읽힌다)."""
    r = subprocess.run([sys.executable, os.path.join(SYS, 'lms-auto.py'), '--known'], cwd=VAULT, capture_output=True, encoding='utf-8', errors='replace', creationflags=NO_WINDOW)
    if r.returncode:
        raise Refuse('known.json 반영 실패: ' + (r.stderr or r.stdout)[-200:])


def set_desk(sid, field, value):
    if sid == '*' and field in ('all_off', 'auto_judge'):      # 전체 스위치 = collect.local.json(auto_judge 기본 끔 · 없으면 끔) — 엔진이 다음 돌림부터 읽는다
        sw = load(SWITCH, default={})
        sw = sw if isinstance(sw, dict) else {}
        sw[field] = as_bool(value)
        save_json(SWITCH, sw)
        old = load(DESK, default={})
        if isinstance(old, dict) and field in old:             # 옛 자리의 같은 칸은 걷는다 — 새 파일을 지워도 옛 값이 되살아나지 않게
            old.pop(field)
            save_json(DESK, old)
    elif sid == 'mylms' and field == 'wake':                   # 깨우기 = 기능 단계 «아침 받기» 값 하나(11-07 사용자 «두 스위치 통일») — 켬 high · 끔 low
        set_wake_level(as_bool(value))
    else:
        d = load(DESK, default={}) or {}
        if sid == 'mylms' and field == 'enabled':
            d[field] = as_bool(value)
        elif sid == 'mylms' and field == 'purpose':
            d['purpose'] = value.strip()[:200]
        else:
            raise Refuse(f'못 고치는 칸: {sid} {field}')
        save_json(DESK, d)
    if field in ('enabled', 'all_off'):
        reflect_known()
    if field in ('enabled', 'all_off', 'wake'):                # 깨우기 예약도 같은 길로 — 전체 끔·mylms 끔이면 PC 를 안 깨운다(헛깨우기 막음)
        sync_wake()


def set_wake_level(on):
    """기능 단계 lms.wake 를 바꾼다(단계 탭과 같은 값 · 장부는 options 가) · desk.json 의 옛 wake 칸은 걷는다(이제 안 읽음)."""
    sys.path.insert(0, SYS)
    try:
        import options
        options.set_level('lms.wake', 'high' if on else 'low', via='collect_desk')
    except ImportError:
        raise Refuse('기능 단계 대본(options.py)이 없음')
    except Exception as e:      # options.OptErr — 선언 없음·고른 값 파일 깨짐
        raise Refuse(f'기능 단계를 못 바꿈: {e}')
    old = load(DESK, default={})
    if isinstance(old, dict) and 'wake' in old:
        old.pop('wake')
        save_json(DESK, old)


def wake_chosen():
    """깨우기 값 = 기능 단계 lms.wake 의 고른 값(배터리 규칙 전 · lms-auto.py wake_chosen 과 같은 규칙) — 못 읽으면 'high'."""
    try:
        sys.path.insert(0, SYS)
        import options
        local, st = options._load(options.local_path(None))
        return options.chosen(local, st, options.declarations(None, only='lms.wake')).get('lms.wake', 'high')
    except Exception:
        return 'high'


def sync_wake():
    """깨우기 예약을 지금 값대로 맞춘다(lms-auto.py --wake-sync → lms-tasks.ps1 -WakeOnly) — 대본이 없으면(배포판) 건너뜀."""
    p = os.path.join(SYS, 'lms-auto.py')
    if not os.path.exists(p):
        return
    r = subprocess.run([sys.executable, p, '--wake-sync'], cwd=VAULT, capture_output=True, encoding='utf-8', errors='replace', creationflags=NO_WINDOW)
    if r.returncode:
        raise Refuse('깨우기 예약 맞추기 실패(값은 바뀜): ' + (r.stderr or r.stdout)[-200:])


def set_course(value):
    c = load(COURSES)
    if not isinstance(c, dict):
        raise Refuse('courses.json 을 못 읽음')
    edit_courses(c, value)
    save_json(COURSES, c)
    reflect_known()


def edit_courses(c, value):
    """과목 넣고 빼기 — courses.json 내용(dict)만 고친다(연습 흉내도 같은 규칙 · E2)."""
    m = re.match(r'^(\d+)=(on|off)$', value)
    if not m:
        raise Refuse(f'과목 값 꼴: {value}')
    cid, to = m.groups()
    out = c.setdefault('_제외', {})
    if to == 'off':
        if cid not in c:
            raise Refuse(f'없는 과목: {cid}')
        out[cid] = f'{c.pop(cid)} — 수집 창에서 뺌 {dt.date.today().isoformat()}'
    else:
        if cid not in out:
            raise Refuse(f'뺀 적 없는 과목: {cid}')
        c[cid] = str(out.pop(cid)).split(' — ')[0]


def set_recipe(sid, field, value):
    path = os.path.join(SYS, 'collect', sid + '.json')
    rc = load(path)
    if not isinstance(rc, dict) or rc.get('id') != sid:
        raise Refuse(f'없는 출처: {sid}')
    edit_recipe(rc, field, value)
    save_json(path, rc)


def edit_recipe(rc, field, value):
    """조리법 칸 하나 — 조리법 내용(dict)만 고친다(연습 흉내도 같은 규칙 · E2)."""
    fam = rc.get('family')
    words_at = rc.get('calendar') if fam == 'calendar' else rc.get('listing') if fam == 'listing' else rc.get('filter')
    if field in ('skip+', 'skip-', 'keep+', 'keep-') and fam in ('regex', 'rss') and (field.startswith('keep') or not isinstance(words_at, dict)):
        words_at = rc.setdefault('words', {})       # 낱말 관문(11-06) — 남길 말은 언제나 여기 · 뺄 말은 판정 층이 없을 때 여기
    if field == 'purpose':
        rc['purpose'] = value.strip()[:200]
    elif field == 'enabled':
        rc.pop('enabled', None) if as_bool(value) else rc.__setitem__('enabled', False)
    elif field == 'hours':
        rc['recheck_hours'] = as_num(value, 1, 24, float)
    elif field == 'pages':
        at = rc.get('list') or rc.get('listing')
        if not isinstance(at, dict) or 'pages' not in at:
            raise Refuse('쪽 칸 없는 출처')
        at['pages'] = as_num(value, 1, 9, int)
    elif field in ('download', 'images'):
        if not isinstance(rc.get('attachments'), dict):
            raise Refuse('첨부 칸 없는 출처')
        rc['attachments'][field] = as_bool(value)
    elif field == 'auto':
        if not isinstance(rc.get('filter'), dict):
            raise Refuse('거르기 없는 출처')
        rc['filter']['auto'] = as_bool(value)
    elif field in ('skip+', 'skip-', 'keep+', 'keep-'):
        if not isinstance(words_at, dict):
            raise Refuse('낱말 칸 없는 출처')
        name, op = field[:-1], field[-1]
        if name == 'keep' and fam not in ('listing', 'regex', 'rss'):
            raise Refuse('남길 말 칸 없는 출처')
        key = 'title_skip' if words_at is rc.get('filter') else name
        edit_words(words_at, key, op, value, need_one=name == 'keep' and fam == 'listing')     # listing 은 keep 이 필수(엔진) · 낱말 관문의 keep 은 비면 다 남김
        if words_at is rc.get('words') and not words_at:
            rc.pop('words')
    else:
        raise Refuse(f'못 고치는 칸: {field}')


def set_value(sid, field, value):
    if field == 'course':
        if sid != 'mylms':
            raise Refuse('과목은 mylms 칸')
        return set_course(value)
    if sid in ('*', 'mylms'):
        return set_desk(sid, field, value)
    return set_recipe(sid, field, value)


# ── 받기·판정·글 하나 — 엔진을 부른다 ──
def busy_path(sid):
    return os.path.join(SYS, '_index', 'collect', f'desk-busy-{sid}.txt')     # 점 없는 이름 = 옵시디언이 보고 화면을 새로 그린다


class Busy:
    """lms-auto 와 같은 잠금으로 15분 예약과 같은 상태 파일을 동시에 안 쓴다 · 도는 동안 화면에 그 낱말이 보인다."""

    def __init__(self, sid, word):
        self.path, self.word, self.sid = busy_path(sid), word, sid

    def __enter__(self):
        import msvcrt
        state = os.environ.get('LMS_AUTO_STATE') or os.path.join(SYS, '_index', 'lms')
        os.makedirs(state, exist_ok=True)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = open(os.path.join(state, 'auto.lock'), 'a+')
        try:
            msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.f.close()
            raise Refuse('다른 수집이 도는 중')
        with open(self.path, 'w', encoding='utf-8') as f:
            f.write(self.word)
        return self

    def __exit__(self, *_):
        try:
            os.remove(self.path)
        except OSError:
            pass
        self.f.close()


def engine(*args):
    r = subprocess.run([sys.executable, os.path.join(SYS, args[0]), *args[1:]], cwd=VAULT, capture_output=True, encoding='utf-8', errors='replace', creationflags=NO_WINDOW,
                       env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    if r.returncode:
        raise Refuse((r.stderr or r.stdout or f'{args[0]} rc={r.returncode}').strip()[-200:])
    return r.stdout


def recipe_of(sid):
    rc = load(SYS, 'collect', sid + '.json')
    if not isinstance(rc, dict) or rc.get('id') != sid:
        raise Refuse(f'없는 출처: {sid}')
    return rc


def fetch(sid):
    """웹 = 그 자리에서 받는다(엔진의 계약·스위치 관문 그대로) · mylms = PC → 확장 길이 known.json 뿐이라 다음 15분 확인 때 돈다."""
    if switches().get('all_off') is True:
        raise Refuse('전체가 꺼져 있음')
    d = load(DESK, default={}) or {}
    if sid == 'mylms':
        if d.get('enabled') is False:
            raise Refuse('mylms 가 꺼져 있음')
        d['fetch_now'] = dt.datetime.now().isoformat(timespec='seconds')
        save_json(DESK, d)
        return reflect_known()
    if recipe_of(sid).get('enabled') is False:
        raise Refuse('꺼진 출처')
    with Busy(sid, '받는 중'):
        engine('web-collect.py', '--source', sid, '--force')


def judge_source(sid):
    """구독 사용량이 든다 — 누를 때만 · 그 출처만. 끈 출처는 판정 반영(settle)도 멈추므로 받지 않는다."""
    d = load(DESK, default={}) or {}
    if switches().get('all_off') is True or (sid == 'mylms' and d.get('enabled') is False) or (sid != 'mylms' and recipe_of(sid).get('enabled') is False):
        raise Refuse('꺼진 출처')
    with Busy(sid, '판정 중'):
        engine('notice-filter.py', 'extract', '--source', LMS_SID if sid == 'mylms' else sid)


def item(sid, aid, op):
    """글 하나 — 승인 rescue(판정 대기·대기 칸·장부 → 볼트) · 거절 reject(판정 대기 → 장부) · 되돌리기(보관 칸 → 볼트) · 헛것·쓸모 표시."""
    recipe_of(sid)
    if aid not in ((load(SYS, '_index', 'collect', sid + '.json', default={}) or {}).get('items') or {}):
        raise Refuse(f'없는 글: {aid}')
    with Busy(sid, {'rescue': '승인 중'}.get(op, '고치는 중')):
        if op == 'rescue':
            engine('web-collect.py', '--rescue', '--source', sid, '--id', aid)
        elif op == 'restore':
            engine('web-collect.py', '--restore', '--source', sid, '--id', aid)
        elif op == 'reject':      # 까닭 없는 거절(옛 꼴 · 창은 reject 를 부른다)
            engine('notice-filter.py', 'reject', aid, '--button')
            engine('notice-filter.py', 'judge')
        elif op in ('useless', 'useful'):
            engine('notice-filter.py', 'mark', aid, '헛것' if op == 'useless' else '쓸모')
            engine('notice-filter.py', 'judge')
        else:
            raise Refuse(f'모르는 동작: {op}')


def reject(sid, aid, picked, memo):
    """거절 단추(11-09) — 판정 대기 → 장부 · 까닭 = 제목에서 고른 낱말(되먹임이 제외어로) + 메모(대기열로 · 카드 조건 후보). 둘 다 빈칸이면 까닭 없이 뺀다."""
    recipe_of(sid)
    it = ((load(SYS, '_index', 'collect', sid + '.json', default={}) or {}).get('items') or {}).get(aid)
    if not isinstance(it, dict):
        raise Refuse(f'없는 글: {aid}')
    if where(it) != 'pend':
        raise Refuse('판정 대기 글만 거절')
    title = it.get('title') or ''
    picked = [w for w in dict.fromkeys(x.strip() for x in picked.split('|')) if w]
    if any(w not in title for w in picked):
        raise Refuse('제목에 없는 낱말')
    with Busy(sid, '고치는 중'):
        engine('notice-filter.py', 'reject', aid, '--button', *[f'--word={w}' for w in picked], f'--memo={memo.strip()[:200]}')
        engine('notice-filter.py', 'judge')


def open_site(sid):
    """사이트를 연다 — 열기만 한다(비밀번호를 다루지 않는다). mylms 는 확장이 있는 크롬으로."""
    if sid == 'mylms':
        url = mylms_url()
    elif os.path.exists(os.path.join(SYS, 'collect', sid + '.json')):
        url = recipe_of(sid).get('page') or ''
    else:
        url = next((c.get('url') or '' for c in cand_rows() if c['id'] == sid), '')
    if not re.match(r'^https?://', url):
        raise Refuse(f'주소 없음: {sid}')
    if os.environ.get('DESK_NO_OPEN'):              # 시험 — 창을 안 띄운다
        return print(url)
    if sid == 'mylms':
        try:
            import winreg
            subprocess.Popen([winreg.QueryValue(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe'), url], close_fds=True)
            return
        except (ImportError, OSError):
            pass
    webbrowser.open(url)


def contract(cid, answer):
    """사용자 클릭이 곧 승인 — 결과는 대기열 한 줄(조리법은 Claude 가 탐색 뒤 쓴다). 계약 없는 출처를 돌리는 길이 아니다."""
    if answer not in ('계약', '안 함'):
        raise Refuse(f'계약 또는 안 함: {answer}')
    d = load(CAND)
    row = next((c for c in cand_rows() if c['id'] == cid), None) if isinstance(d, dict) else None
    if not row:
        raise Refuse(f'없는 후보: {cid}')
    for c in d['candidates']:
        if c.get('id') == cid:
            c['answer'], c['at'] = answer, dt.date.today().isoformat()
    save_json(CAND, d)
    if answer == '계약':
        new = not os.path.exists(QUEUE)
        with open(QUEUE, 'a', encoding='utf-8', newline='\n') as f:
            if new:
                f.write('# 수집 대기열\n> lms-auto.py·web-collect.py 가 쌓는다. 고치면 줄 앞을 `- [x]` 로.\n\n')
            f.write(f'- [ ] {time.strftime("%Y-%m-%d %H:%M:%S")} `{cid}` (Claude) 수집 계약 승인(수집 창) — {row.get("name")} {row.get("url")} · 조리법을 탐색해 쓴다 · 근거 {row.get("note")}\n')


# ── 수집 추가·고침(11-06 · 대화창 스킬 collect_desk:add · fix 가 부른다) ──
DRAFT = os.path.join(SYS, '_index', 'collect', 'draft')
ID_RX = re.compile(r'[a-z0-9][a-z0-9-]{1,48}')
STRUCT = {'page', 'feed', 'list', 'view', 'date_field', 'family', 'explored', 'first_since'}   # 고침이 바꿀 수 있는 칸 = 구조뿐(목적·낱말·거르기·자리·주기·첨부·계약은 사용자 몫)


def engine_json(*args):
    out = engine('web-collect.py', *args).strip().splitlines()
    try:
        return json.loads(out[-1]) if out else {}
    except ValueError:
        raise Refuse('엔진 답을 못 읽음: ' + (out[-1] if out else '')[:160])


def probe_url(url, note=''):
    if not re.match(r'^https?://', url):
        raise Refuse(f'주소 꼴: {url}')
    r = engine_json('--probe', url, *(['--robots-note', note] if note else []))
    if r.get('problems'):
        rb = r.get('robots')
        raise Refuse((f'robots: {rb[0]} ({rb[1]}) · ' if rb else '') + ' · '.join(r['problems']))
    rb = r.get('robots') or ['모름', '']
    if r.get('waited'):
        print(f'같은 사이트를 1분 안에 다시 받지 않으려고 {r["waited"]}초 기다린 뒤 받음')
    print(f'{r["url"]} → {r["final"]} ({r["status"]} · {r["type"]} · {r["charset"]} · {r["bytes"] // 1024}KB)')
    print(f'제목: {r["title"] or "—"}')
    print(f'robots: {rb[0]} ({rb[1]})')
    print('피드: ' + (' · '.join(r['feeds']) or '없음') + (f' · 이 주소가 피드(글 {r["feed_rows"]})' if r['feed_rows'] else ''))
    if r.get('linked_feeds'):
        print('본문 링크의 피드 꼴 주소(안 받아 봄): ' + ' · '.join(r['linked_feeds']))
    if r.get('comment_feeds'):
        print('댓글 피드(글 목록 아님): ' + ' · '.join(r['comment_feeds']))
    print(f'대본 {r["scripts"]} · 보이는 글자 {r["text_chars"]}' + (' — 자바스크립트로 그리는 쪽 같음(1차 범위 밖)' if r['text_chars'] < 300 and r['scripts'] > 5 and not r['feed_rows'] else ''))
    print(f'원시: {r["saved"]}')


def draft_of(did):
    if not ID_RX.fullmatch(did):
        raise Refuse(f'초안 id 꼴: {did}')
    p = os.path.join(DRAFT, did + '.json')
    rc = load(p)
    if not isinstance(rc, dict):
        raise Refuse(f'초안 없음·깨짐: 3_시스템/_index/collect/draft/{did}.json')
    if rc.get('id') != did:
        raise Refuse('초안 안의 id 가 파일 이름과 다름')
    return p, rc


def try_draft(did, view):
    p, _ = draft_of(did)
    r = engine_json('--preview', p, *(['--view'] if view else []))
    rb = r.get('robots') or {}
    if r.get('waited'):
        print(f'같은 사이트를 1분 안에 다시 받지 않으려고 {r["waited"]}초 기다린 뒤 받음')
    if 'n' in r:
        print(f'목록 1쪽 {r["n"]}건 · 통과 {r["kept"]} · 거름 {r["n"] - r["kept"]}' + (f' · 이미 받은 글 {r["known"]}/{r["state"]}' if r.get('state') else ''))
    if rb:
        print('robots: ' + ' · '.join(f'{"목록" if k == "list" else "글"} {v[0]}({v[1]})' for k, v in rb.items()))
    # 줄 전부·제목 전체 — 11-06 끝까지 시험: 15줄·60자로 자르니 대화가 원시를 뒤지고 엔진을 직접 불러 같은 사이트를 다시 받았다
    rows = r.get('rows') or []
    for i, x in enumerate(rows[:60], 1):
        print(f'{i:>2}. {x["date"] or "—":10}  {x["title"][:200]}' + (f'   [거름: {x["gate"]}]' if x['gate'] else ''))
    if len(rows) > 60:
        print(f'… {len(rows) - 60}줄 더')
    v = r.get('view')
    if v:
        print(f'글 하나: {v["title"][:200]} · 본문 {v["body_chars"]}자 · 첨부 {len(v["attachments"])}')
        print('  ' + v['body_head'].replace('\n', ' ')[:160])
    if r.get('problems'):
        raise Refuse('문제: ' + ' · '.join(r['problems']))


def tried_ok(p, did, rc):
    t = load(DRAFT, did + '.tried.json', default={}) or {}
    if t.get('sha') != hashlib.sha1(open(p, 'rb').read()).hexdigest():
        # 결과에 안 닿는 칸(이름·목적·주기·자리·첫 날…)만 바뀌었으면 사이트를 다시 받지 않는다 — 꼴 검사(망 요청 0)만 다시
        # (11-06 끝까지 시험: 5단계에서 주기만 바꿨는데 확정이 막혀 같은 게시판을 다시 받았다)
        lint = engine_json('--lint', p)
        if lint.get('problems'):
            raise Refuse('초안 꼴: ' + ' · '.join(lint['problems']))
        if not t.get('res') or lint.get('res') != t['res']:
            raise Refuse('미리보기 뒤 초안이 바뀜 — 다시 미리보기(try)')
    if not t.get('ok'):
        raise Refuse('미리보기를 통과하지 못한 초안')
    if (rc.get('family') == 'regex' or rc.get('view')) and not t.get('view_ok'):
        raise Refuse('글 하나 미리보기(try --view) 전')
    blocked = [f'{"목록" if k == "list" else "글"} {v[0]}' for k, v in (t.get('robots') or {}).items() if v and v[0] != '허용']
    if blocked and not str(rc.get('robots_note') or '').strip():
        raise Refuse(f'robots {" · ".join(blocked)} — 사용자 결정을 초안 robots_note 에 적은 뒤')
    return t


def done_draft(did):
    for name in (did + '.json', did + '.tried.json'):
        try:
            os.remove(os.path.join(DRAFT, name))
        except OSError:
            pass


def add_source(did):
    """확정 — 사용자가 대화창에서 «추가»라고 답한 뒤에만 부른다. 미리보기를 거친 그 초안 그대로 조리법이 되고 다음 예약 돌림부터 돈다."""
    p, rc = draft_of(did)
    dst = os.path.join(SYS, 'collect', did + '.json')
    if os.path.exists(dst):
        raise Refuse(f'같은 id 의 출처가 이미 있음: {did}')
    if not str(rc.get('purpose') or '').strip():
        raise Refuse('목적(purpose) 없는 초안')
    t = tried_ok(p, did, rc)
    rb = (t.get('robots') or {}).get('list') or ['모름']
    note = str(rc.get('robots_note') or '').strip()
    rc['contract'] = (f'{dt.date.today().isoformat()} 사용자 수집 창 «수집 추가» 확정 · 목적 «{str(rc["purpose"]).strip()[:80]}» · robots {rb[0]}'
                      + (f'({note[:80]})' if note else '') + ' · 공개 페이지 · 받기만(GET)')
    rc.pop('enabled', None)
    save_json(dst, rc)
    done_draft(did)
    print(f'추가: 3_시스템/collect/{did}.json — 다음 예약 돌림(15분 안 · {rc.get("recheck_hours", 20)}시간마다)부터 돈다')


def close_queue(sid):
    """그 출처의 열린 (Claude) 대기열 줄을 닫는다 — 고친 구조 문제. 사용자 줄(로그인·사용량)은 그대로."""
    if not os.path.exists(QUEUE):
        return 0
    lines = read(QUEUE).splitlines()
    n = 0
    for i, ln in enumerate(lines):
        m = QUEUE_LINE.match(ln)
        if m and m.group(2) == sid and m.group(3) == 'Claude':
            lines[i] = '- [x]' + ln[5:]
            n += 1
    if n:
        tmp = QUEUE + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
            f.write('\n'.join(lines) + '\n')
        os.replace(tmp, QUEUE)
    return n


def fix_source(did):
    """고침 — 깨진 조리법의 구조 칸만 바꾼 초안(미리보기 통과)을 조리법으로. 목적·낱말·거르기·자리·주기·계약이 바뀌면 거절(그건 사용자 몫)."""
    p, new = draft_of(did)
    cur = recipe_of(did)
    changed = {k for k in set(cur) | set(new) if cur.get(k) != new.get(k)} - {'robots_note'}
    if not changed:
        raise Refuse('바뀐 칸 없음')
    if changed - STRUCT:
        raise Refuse('고침은 구조 칸만 — 바뀐 칸: ' + ', '.join(sorted(changed - STRUCT)))
    tried_ok(p, did, new)
    save_json(os.path.join(SYS, 'collect', did + '.json'), new)
    done_draft(did)
    print(f'고침: {", ".join(sorted(changed))} · 대기열 줄 닫음 {close_queue(did)}')


FIELD_WORD = {'enabled': '수집', 'wake': '깨우기', 'all_off': '전체 끔', 'auto_judge': '자동 판정', 'download': '첨부', 'images': '그림', 'auto': '자동 판정', 'purpose': '목적', 'hours': '주기', 'pages': '쪽',
              'skip+': '뺄 말 더함', 'skip-': '뺄 말 뺌', 'keep+': '남길 말 더함', 'keep-': '남길 말 뺌', 'course': '과목'}


def event_word(field, value):
    v = {'true': '켬', 'false': '끔'}.get(value, value)
    if field == 'all_off':
        return '전체 끔' if value == 'true' else '전체 켬'
    if field == 'course':
        return ('과목 뺌 ' if value.endswith('=off') else '과목 넣음 ') + value.split('=')[0]
    return f'{FIELD_WORD.get(field, field)} {v}'


def my_events():
    """수집 창에서 사용자가 한 일 — 장부(brain.py 가 적음)에서."""
    ev = {}
    for line in read(SYS, 'ledger', 'actions.jsonl').splitlines():
        if 'collect_desk.' not in line:
            continue
        try:
            e = json.loads(line)
            g = e['args']
            act = e.get('action')
            if e.get('code'):
                continue
            # 승인·거절·헛것·쓸모는 표시 장부(평가.json)가 제목과 함께 말한다
            s = (event_word(g['field'], g['value']) if act == 'collect_desk.set' else
                 '지금 받기' if act == 'collect_desk.fetch' else
                 '판정' if act == 'collect_desk.judge' else
                 '추가' if act == 'collect_desk.add' else
                 '고침' if act == 'collect_desk.fix' else
                 '되돌림' if act == 'collect_desk.item' and g.get('op') == 'restore' else '')
            if s:
                ev.setdefault(g.get('source') or g['id'], []).append({'t': e['ts'][5:16].replace('T', ' '), 's': s, 'me': True})
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
    return ev


def view(_reason='open'):
    now = dt.datetime.now()
    desk = load(SYS, 'lms', 'desk.json', default={}) or {}
    queue = open_queue()
    cfg, alarm_bad = alarm_reader()
    events = web_events()
    sources = []
    lms = lms_source(queue, cfg, desk, now)
    if lms:
        sources.append(lms)
    for p in sorted(glob.glob(os.path.join(SYS, 'collect', '*.json'))):
        s = web_source(p, events, queue, cfg, now)
        if s:
            sources.append(s)
    h = holiday_source()
    if h:
        sources.append(h)
    mine = my_events()
    for x in sources:
        if mine.get(x['id']):
            x['events'] = sorted(x['events'] + mine[x['id']], key=lambda e: e['t'], reverse=True)[:EVENTS]
    sw = switches()
    return {'now': fmt(now), 'allOff': sw.get('all_off') is True, 'autoJudge': sw.get('auto_judge') is True, 'alarmNote': ALARM_NOTE, 'alarmBad': alarm_bad, 'sources': sources, 'candidates': candidates()}


# ── 연습(튜토리얼 E2 · 11-08) — «연습: 모듈» 장 동안 수집 창이 그리는 자료 · 쓰기 흉내 ──
PRACTICE_ID = '연습-'      # 연습 자료 id 머리 — 진짜 id(ID_RX = 영문 소문자·숫자·-)와 겹칠 수 없다 · 진짜 쓰기 명령은 이 id 를 거부(main)


def practice_inputs(now):
    """연습 입력 — 진짜 view() 가 읽는 파일 꼴 그대로 {볼트 상대 경로: 값}. 정상(공지)·실패(구독)·로그인 끊김(LMS) 출처 셋 + 후보 하나 + 걸러진 글 몇."""
    ago = lambda h: now - dt.timedelta(hours=h)
    stamp = lambda h: f'{ago(h):%Y-%m-%d %H:%M:%S}'
    day = lambda h: f'{ago(h):%Y-%m-%d}'
    notice = {'id': '연습-공지', 'name': '학과 공지', 'family': 'regex', 'page': 'https://example.org/notice', 'recheck_hours': 6, 'list': {'pages': 2},
              'attachments': {'download': True, 'images': False, 'max_mb': 20}, 'purpose': '학과 공지에서 마감·행사',
              'filter': {'title_skip': '설문', 'keep_days': 90, 'auto': True, 'schedule': '학과-일정.md'}}   # «광고»는 8장이 칸에 채워 더하는 낱말 — 미리 있으면 Enter 뒤에 바뀌는 것이 안 보인다(11-09)
    items = {'n1': {'title': '2학기 장학금 신청 안내', 'date': day(5), 'path': '2_지식/연습/장학금.md'},
             'n2': {'title': '졸업 논문 제출 일정', 'date': day(30), 'path': '2_지식/연습/논문.md'},
             'n3': {'title': '학생회 설문 참여 부탁', 'date': day(8), 'verdict': '뺌', 'why': '제목에 «설문»'},
             'n4': {'title': '교내 식당 메뉴 안내', 'date': day(20), 'stage': 1, 'verdict': '뺌', 'why': '공부·마감과 상관없는 글'},
             'n5': {'title': '도서관 휴관 안내', 'date': day(50), 'stage': 1, 'verdict': '뺌', 'why': '날짜만 알리는 글'},
             'n6': {'title': '지난 학기 행사 사진', 'date': day(24 * 40), 'archived': '연습-사진.md'}}
    feed = {'id': '연습-구독', 'name': '기술 블로그', 'family': 'rss', 'feed': 'https://example.org/feed.xml', 'page': 'https://example.org/blog',
            'recheck_hours': 20, 'words': {'skip': '광고'}}
    return {
        '3_시스템/collect/연습-공지.json': notice,
        '3_시스템/_index/collect/연습-공지.json': {'last_run': ago(2).timestamp(), 'items': items},
        '3_시스템/collect/연습-구독.json': feed,
        '3_시스템/_index/collect/연습-구독.json': {'last_run': ago(26).timestamp(), 'items': {'f1': {'title': '새 판 출시 소식', 'date': day(30), 'path': '2_지식/연습/블로그.md'}}},
        '3_시스템/_index/collect/web.log': f'{stamp(2)} 연습-공지: 목록 20줄\n{stamp(2)} 연습-공지: 받음 대기 칸 2 · 제목 장부 1\n{stamp(26)} 연습-구독: 목록 0줄\n',
        '3_시스템/_index/수집-대기열.md': f'# 수집 대기열\n\n- [ ] {stamp(26)[:16]} `연습-구독` (Claude) 피드를 못 읽음 — 주소가 바뀐 것 같음\n',
        '3_시스템/lms/courses.json': {'101': '자료구조', '102': '전자기학', '_제외': {'103': '2026 체육 — 수집 창에서 뺌'}},
        '3_시스템/lms/desk.json': {'purpose': '강의 공지·과제 마감'},
        '3_시스템/lms/manifest.json': {'version': '1.0.0', 'host_permissions': ['https://lms.example.org/*']},
        '3_시스템/_index/lms/manifest.json': {'items': {'p1': {'path': '연습/lms/자료구조/1주차.md'}, 'p2': {'path': '연습/lms/전자기학/과제1.md'}},
                                              'files': {'q1': {'path': '연습/lms/자료구조/강의자료.pdf'}}, 'board': {}},
        '3_시스템/_index/lms/runs/run.json': {'kind': 'run', 'startedAt': int(ago(20).timestamp() * 1000), 'version': '1.0.0'},
        '3_시스템/_index/lms/runs/status.json': {'kind': 'status', 'at': int(ago(1).timestamp() * 1000), 'login': 'out', 'version': '1.0.0'},
        '3_시스템/_index/lms/auto.log': f'{stamp(20)} lms-file 새 글 2 · 파일 들임 1\n{stamp(1)} 로그인 out\n',
        '3_시스템/lms/candidates.json': {'candidates': [{'id': '연습-후보', 'name': '취업 박람회 소식', 'host': 'example.org', 'url': 'https://example.org/fair',
                                                       'measured': '목록 20줄 · 글마다 날짜 · 주 1~2번 새 글', 'note': '', 'answer': ''}]},
    }


def practice_act(F, act, now):
    """흉내 행위 하나 → 연습 입력(진짜 쓰기·엔진·사이트 0). 고침 규칙은 진짜와 같은 함수(edit_recipe·edit_courses·as_bool) ·
    진짜처럼 장부 줄을 남겨 «일어난 일»에 뜬다 · 진짜가 거부할 일은 같은 말로 거부(Refuse)."""
    aid, g = act.get('id'), act.get('args')
    if not isinstance(g, dict) or not all(isinstance(v, str) for v in g.values()):
        raise Refuse('인자 꼴')
    src = g.get('source', '')
    lms = src == PRACTICE_ID + 'mylms'
    rc = F.get(f'3_시스템/collect/{src}.json')
    st = F.get(f'3_시스템/_index/collect/{src}.json') or {}
    sw = F.setdefault('3_시스템/collect.local.json', {})
    desk = F['3_시스템/lms/desk.json']
    if aid == 'collect_desk.set':
        field, value = g.get('field', ''), g.get('value', '')
        if field == 'course':
            if not lms:
                raise Refuse('과목은 mylms 칸')
            edit_courses(F['3_시스템/lms/courses.json'], value)
        elif src == '*' and field in ('all_off', 'auto_judge'):
            sw[field] = as_bool(value)
        elif lms and field in ('enabled', 'wake'):
            desk[field] = as_bool(value)
        elif lms and field == 'purpose':
            desk['purpose'] = value.strip()[:200]
        elif isinstance(rc, dict):
            edit_recipe(rc, field, value)
        else:
            raise Refuse(f'없는 출처: {src}')
    elif aid == 'collect_desk.item':
        it = (st.get('items') or {}).get(g.get('id', ''))
        if not isinstance(rc, dict) or not isinstance(it, dict):
            raise Refuse(f'없는 글: {g.get("id")}')
        op = g.get('op')
        if op in ('rescue', 'restore'):
            for k in ('stage', 'verdict', 'why', 'archived'):
                it.pop(k, None)
            it['path'] = f'2_지식/연습/{g["id"]}.md'
        elif op == 'reject':
            it.pop('stage', None)
            it.update(verdict='뺌', why='사용자: 거절')
        elif op in ('useless', 'useful'):
            F.setdefault('3_시스템/_index/collect/평가.json', {})[f'{src}:{g["id"]}'] = {'평가': '헛것' if op == 'useless' else '쓸모', 'at': f'{now:%Y-%m-%d %H:%M}'}
        else:
            raise Refuse(f'모르는 동작: {op}')
    elif aid == 'collect_desk.reject':
        it = (st.get('items') or {}).get(g.get('id', ''))
        if not isinstance(rc, dict) or not isinstance(it, dict):
            raise Refuse(f'없는 글: {g.get("id")}')
        picked = [w for w in g.get('words', '').split('|') if w]
        if any(w not in (it.get('title') or '') for w in picked):
            raise Refuse('제목에 없는 낱말')
        it.pop('stage', None)
        said = ' · '.join([f'«{w}»' for w in picked] + ([g['memo'].strip()] if g.get('memo', '').strip() else []))
        it.update(verdict='뺌', why=f'사용자: {said or "거절"}')
    elif aid in ('collect_desk.fetch', 'collect_desk.judge'):
        if sw.get('all_off') is True or (lms and desk.get('enabled') is False) or (not lms and (not isinstance(rc, dict) or rc.get('enabled') is False)):
            raise Refuse('꺼진 출처')
        if lms:
            if aid == 'collect_desk.fetch':
                desk['fetch_now'] = now.isoformat(timespec='seconds')
        else:
            st['last_run'] = now.timestamp()
            n = 0
            for x in (st.get('items') or {}).values():
                if aid == 'collect_desk.judge' and isinstance(x, dict) and where(x) == 'pend':
                    x['path'] = '2_지식/연습/판정.md'
                    n += 1
            F['3_시스템/_index/collect/web.log'] += f'{now:%Y-%m-%d %H:%M:%S} {src}: ' + ('목록 20줄\n' if aid == 'collect_desk.fetch' else f'판정 반영 · 볼트에 들임 {n}\n')
    elif aid == 'collect_desk.contract':
        row = next((c for c in F['3_시스템/lms/candidates.json']['candidates'] if c.get('id') == g.get('id')), None)
        if g.get('answer') not in ('계약', '안 함') or not row:
            raise Refuse(f'계약 또는 안 함 · 있는 후보: {g.get("id")}')
        row.update(answer=g['answer'], at=now.date().isoformat())
        if g['answer'] == '계약':
            F['3_시스템/_index/수집-대기열.md'] += f'- [ ] {now:%Y-%m-%d %H:%M} `{row["id"]}` (Claude) 수집 계약 승인(수집 창) — {row["name"]}\n'
    elif aid == 'collect_desk.open':
        return              # 연습은 사이트를 열지 않는다
    else:
        raise Refuse(f'연습에 없는 행위: {aid}')
    rec = dict(g, source='mylms') if lms else g      # 장부 줄 = brain.py 가 적는 꼴(my_events 가 «일어난 일»로 그림)
    F['3_시스템/ledger/actions.jsonl'] = F.get('3_시스템/ledger/actions.jsonl', '') + json.dumps({'ts': now.isoformat(timespec='seconds'), 'action': aid, 'args': rec, 'code': 0}, ensure_ascii=False) + '\n'


def practice_view(acts_text):
    """튜토리얼 연습 자료(E2) — 연습 입력을 OS 임시 폴더에 쓰고 전역 자리를 그리로 옮겨 진짜 view() 를 그대로 돌린다(같은 자료 꼴 · 같은 그리기 코드).
    볼트는 읽지도 쓰지도 않고 바깥 프로그램(엔진·브라우저)도 부르지 않는다. 흉내 행위는 차례대로 입력에 반영 · 거부된 것 = practice.refused."""
    import tempfile
    try:
        acts = json.loads(acts_text or '[]')
    except ValueError:
        acts = []
    acts = acts[:200] if isinstance(acts, list) else []
    now = dt.datetime.now().replace(microsecond=0)
    F, refused = practice_inputs(now), []
    for a in acts:
        try:
            practice_act(F, a if isinstance(a, dict) else {}, now)
        except Refuse as e:
            refused.append(str(e))

    def nothing(*_a, **_k):
        raise Refuse('연습 — 바깥 프로그램을 부르지 않음')
    subprocess.run = subprocess.Popen = webbrowser.open = nothing
    desk = F['3_시스템/lms/desk.json']
    with tempfile.TemporaryDirectory(prefix='외부뇌-연습-') as root:
        for rel, v in F.items():
            p = os.path.join(root, *rel.split('/'))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8', newline='\n') as f:
                f.write(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
        sysd = os.path.join(root, '3_시스템')
        globals().update(VAULT=root, SYS=sysd, PLAN=os.path.join(root, '2_지식', '일정'), CAND=os.path.join(sysd, 'lms', 'candidates.json'),
                         DESK=os.path.join(sysd, 'lms', 'desk.json'), SWITCH=os.path.join(sysd, 'collect.local.json'), COURSES=os.path.join(sysd, 'lms', 'courses.json'),
                         QUEUE=os.path.join(sysd, '_index', '수집-대기열.md'), DRAFT=os.path.join(sysd, '_index', 'collect', 'draft'),
                         wake_chosen=lambda: 'low' if desk.get('wake') is False else 'high')
        out = view('practice')
    for s in out['sources']:
        if s.get('family') == 'lms':
            s['id'] = PRACTICE_ID + 'mylms'      # 진짜 mylms 와 겹치지 않게(화면은 family 로 가른다)
    out['practice'] = {'acts': len(acts), 'refused': refused}
    return out


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    v = sub.add_parser('view')
    v.add_argument('--reason', default='open')
    v.add_argument('--practice', action='store_true')     # 튜토리얼 연습 자료(E2)
    v.add_argument('--acts', default='[]')                 # 쌓인 흉내 행위(JSON 목록)
    w = sub.add_parser('set')
    w.add_argument('source')
    w.add_argument('field')
    w.add_argument('value')
    for name in ('fetch', 'judge', 'open'):
        sub.add_parser(name).add_argument('source')
    it = sub.add_parser('item')
    it.add_argument('source')
    it.add_argument('id')
    it.add_argument('op')
    rj = sub.add_parser('reject')
    rj.add_argument('source')
    rj.add_argument('id')
    rj.add_argument('words')
    rj.add_argument('memo')
    c = sub.add_parser('contract')
    c.add_argument('id')
    c.add_argument('answer')
    pr = sub.add_parser('probe')
    pr.add_argument('url')
    pr.add_argument('--robots-note', default='')
    t = sub.add_parser('try')
    t.add_argument('id')
    t.add_argument('--view', action='store_true')
    for name in ('add', 'fix'):
        sub.add_parser(name).add_argument('id')
    a = ap.parse_args()
    if a.cmd == 'view':
        return print(json.dumps(practice_view(a.acts) if a.practice else view(a.reason), ensure_ascii=False))
    if any(str(getattr(a, k, '') or '').startswith(PRACTICE_ID) for k in ('source', 'id')):
        print('연습 자료 id — 튜토리얼 연습 화면 밖에서는 안 씀', file=sys.stderr)
        sys.exit(2)
    try:
        if a.cmd == 'set':
            set_value(a.source, a.field, a.value)
        elif a.cmd == 'fetch':
            fetch(a.source)
        elif a.cmd == 'judge':
            judge_source(a.source)
        elif a.cmd == 'item':
            item(a.source, a.id, a.op)
        elif a.cmd == 'reject':
            reject(a.source, a.id, a.words, a.memo)
        elif a.cmd == 'open':
            open_site(a.source)
        elif a.cmd == 'contract':
            contract(a.id, a.answer)
        elif a.cmd == 'probe':
            probe_url(a.url, a.robots_note)
        elif a.cmd == 'try':
            try_draft(a.id, a.view)
        elif a.cmd == 'add':
            add_source(a.id)
        elif a.cmd == 'fix':
            fix_source(a.id)
    except Refuse as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
