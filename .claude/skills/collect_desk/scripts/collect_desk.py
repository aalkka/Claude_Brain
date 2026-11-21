# -*- coding: utf-8 -*-
"""수집 관리 창의 자료 — 수집 설정·상태를 읽기만 해서 JSON 한 줄을 낸다. view 는 아무것도 쓰지 않는다.

  py -3 collect_desk.py view [--reason open|refresh]     # 화면 문이 부른다
  py -3 collect_desk.py view --practice [--acts JSON]    # 튜토리얼 연습 자료(E2) — 볼트를 안 읽고 안 쓴다 · acts = 쌓인 흉내 행위 [{id, args}]
  py -3 collect_desk.py set <출처 | *> <칸> <값>          # 아래는 사용자 동작 하나씩 — brain.py run collect_desk.* 로 불러 장부에 남긴다
  py -3 collect_desk.py fetch <출처>                      # 지금 받기 · 웹 = 그 자리에서 · 로그인 출처 = 다음 15분 확인 때
  py -3 collect_desk.py judge <출처>                      # 판정(구독 사용량) · 누를 때만 · 그 출처에 걸린 분류 체계 전부(sort.py judge --place · 끔·엔진 오류면 옛 추출)
  py -3 collect_desk.py sort <ack|revert|rule> <id>       # 분류 칸 단추(S4 · 초안 B) — 알림 확인·되돌리기 · 자동 규칙 되돌리기(<체계>/<규칙>)
  py -3 collect_desk.py item <출처> <글번호> <rescue|reject|restore|useless|useful>
  py -3 collect_desk.py reject <출처> <글번호> <낱말|낱말…> <메모>   # 거절 단추(11-09) — 제목에서 고른 낱말(| 로 이음)·메모 · 둘 다 빈칸이어도 됨
  py -3 collect_desk.py open <출처 | 후보 id>             # 사이트를 연다(화면은 sandbox 라 링크가 안 열린다)
  py -3 collect_desk.py contract <후보 id> <계약|안 함>    # 계약 = 대기열 한 줄 · 조리법은 Claude 가 탐색 뒤 쓴다
  py -3 collect_desk.py probe <주소>                       # 수집 추가(11-06 · 대화창 스킬 add·fix 가 부른다) — 한 쪽 탐색(피드 찾기·robots)
  py -3 collect_desk.py try <초안 id> [--view]             # 미리보기(저장 없음) — 초안 = 3_시스템/_index/collect/draft/<id>.json
  py -3 collect_desk.py add <초안 id>                      # 확정 = 초안 → 3_시스템/collect/<id>.json(사용자 «추가» 답 뒤 · 미리보기를 거친 그 초안만)
  py -3 collect_desk.py fix <초안 id>                      # 고침 = 구조 칸만 바꾼 초안 → 조리법 + 그 출처의 (Claude) 대기열 줄 닫기
  py -3 collect_desk.py new <browser|card|candidates> …   # 개인 파일 처음 만들기(S6 · 빈 틀 = 3_시스템/collect-examples) — 이미 있으면 안 덮음

출처 목록을 코드에 박지 않는다: 웹 = 3_시스템/collect/*.json · 로그인 출처 = 3_시스템/collect/browser/*.json(그 칸 units·settings·state·manifest 가 자리를 말한다) · 공휴일 = 2_지식/일정/공휴일.md · 후보 = 3_시스템/collect/candidates/candidates.json.
없으면 그 줄이 안 나온다(출처 0 인 배포판에서도 돈다). enabled·purpose·settings·collect.local.json 은 있으면 읽는다(없으면 켜짐·빈칸).
로그인 출처 주소 = 그 조리법 ext.host(코드에 학교를 박지 않는다 · S5).
쓰는 곳 = 조리법의 허용 칸 · collect.local.json(전체 스위치) · 로그인 출처 settings·units · 기능 단계 «로그인 출처 아침 받기»(깨우기 — options.py · 예약은 collect-schedule.py --sync) · 후보 · 대기열 한 줄 + 엔진 호출. 임시 파일 뒤 교체 · 주소·정규식·가족·계약 문구는 안 고친다.
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
sys.path.insert(0, SYS)
import roles  # noqa: E402 — 사용자 호칭(프로필) · 대본에 사람 이름을 박지 않는다
import collectlib as cl  # noqa: E402 — 수집 엔진 공통(스위치·잠금 · 11-16 S1)
ME = roles.me()
PLAN = os.path.join(VAULT, '2_지식', '일정')
ALARM_NOTE = '2_지식/modules/mobility/알림-설정.md'     # mobility 선언 자리(module.json) · 실제 자리는 alarm_note() 가 엔진에 묻는다(옮긴 자리도 따라감)
EVENTS = 8
ITEMS = 40
LATE_MIN_H = 24            # 하루 안 늦음은 PC 가 잠든 것일 수 있어 늦음으로 안 친다
BROWSER_LATE_H = 48        # 로그인 출처 — 전 단위 20시간(신호 안 되면 12시간)의 두 배 넘게
BROWSER_QUEUE = r'\d{8}-\d{4}|courses|signals|extension|orphan|tasks'   # 로그인 가족이 대기열에 쓰는 이름(+ 조리법 run_prefix) 만 그 출처 칸에 «실패»로 붙인다 — 막을 이름을 적던 옛 방식은 새 대본이 대기열에 쓸 때마다(11-11 filter-learn · 11-13 자격카드) 그 칸을 빨갛게 했다
WAKE_LEVEL = cl.CHROME       # 기능 «크롬 띄우기»(options.registry.json collect.chrome · 옛 collect.wake «로그인 출처 아침 받기» · 11-20 나눔)
WAKE_PC = cl.WAKE_PC         # 기능 «PC 깨우기»(collect.wake_pc · 모든 시각 수집 · 옛 collect.local.json wake_pc)
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
ALARMS = os.path.join(VAULT, '.claude', 'skills', 'mobility', 'scripts')    # 폰 알림 엔진 = mobility 모듈(11-16 · 이 PC 전용 · 배포판엔 없음)


def alarm_reader():
    """(설정, 문제 수) · 폰 알림 엔진이 없으면 (False, 0) — 칸을 안 그린다(폰이 없으면 울릴 곳이 없다)"""
    if not os.path.isfile(os.path.join(ALARMS, 'alarms.py')):
        return False, 0
    try:
        sys.path.insert(0, ALARMS)
        import alarms
        s, problems = settings_of(alarms)
        return s, problems
    except Exception:
        return None, 0


def alarm_note():
    """알림 설정 노트의 볼트 상대 자리 — 폰 알림 엔진이 찾은 자리(선언 자리 · 없으면 이름으로) · 엔진을 못 부르면 선언 자리"""
    try:
        import alarms
        return alarms.note_rel('alarm-settings')
    except Exception:
        return ALARM_NOTE


def settings_of(alarms):
    r = alarms.load_settings()
    if isinstance(r, tuple):
        return r[0], len(r[1] or [])
    return r, 0


def alarm_of(cfg, name):
    if not name or cfg is False:
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
SAID_NOW = {'살림': '승인', f'{ME} 살림': f'{ME} 승인', '수집 창에서 뺌': '거절', f'{ME}: 수집 창에서 뺌': f'{ME}: 거절'}


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
    at = at_list(rc.get('at'))
    nxt = next_at(at, now) if at else last + dt.timedelta(hours=hours) if last else None
    probs = [q for q in queue if q['id'] == sid]
    marks = load(SYS, '_index', 'collect', '평가.json', default={}) or {}
    s = {'id': sid, 'name': rc.get('name') or sid, 'host': host, 'url': rc.get('page') or '', 'busy': busy_of(sid), 'family': fam, 'purpose': rc.get('purpose') or '',
         'fix': any(q['who'] == 'Claude' for q in probs),       # 구조가 깨진 줄(Claude 몫)이 있으면 «고침» — 로그인·사용량 같은 사용자 줄은 아님
         'on': rc.get('enabled', True) is not False, 'hours': hours, 'hourWord': ' '.join(at) if at else f'{hours:g}시간',
         'method': 'web', 'at': at, 'mode': 'at' if at else 'every', 'rec': recommend(rc, {k: v for k, v in items.items() if isinstance(v, dict)}, now.date()),
         'bars': daily_posts({k: v for k, v in items.items() if isinstance(v, dict)}, now.date()) if fam in ('regex', 'rss') else None,
         'last': fmt(last) if last else '', 'next': fmt(nxt) if nxt and nxt > now else '곧',
         'late': bool(last and (now - last).total_seconds() / 3600 > max(24 if at else hours * 2, LATE_MIN_H)),
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
    s['_src'] = os.path.join(SYS, '_index', 'collect', sid + '.json')     # 판정 대기의 원천(엔진 상태) — sort 요약이 이보다 새것일 때만 sort 셈(view)
    return s


REC_TWICE = 0.5            # Claude 추천(11-12 사용자 «주기 시각 설정 가능 · 클로드의 추천을 받을 수 있도록») — 하루 글이 이만큼 넘으면 하루 두 번
REC_ONCE, REC_BOTH = ['18:00'], ['12:00', '18:00']
BROWSER_MORNING, BROWSER_EVENING = '06:55', '18:00'   # 로그인 출처 추천 — 아침 수업 전 · 낮 글이 반 넘으면 그날 저녁도(11-12 사용자 «바꿔»)


def browser_rec(its):
    """로그인 출처 추천 시각 — 크롬이 켜져 있으면 확장이 15분마다 지켜보니, 시각은 «크롬이 꺼져 있을 때 언제 열까»만 정한다.
    받은 글(노트 머리 posted_at · 한국 시각) 가운데 낮(7~18시) 글이 반 이상이면 06:55·18:00(그날 글을 그날 저녁에) · 아니면 06:55 · 글이 없으면 06:55.
    11-12 잰 값: 48편 · 0~7시 1 · 7~12시 15 · 12~18시 19 · 18~24시 13 → 06:55·18:00."""
    day = total = 0
    for v in its.values():
        try:
            with open(os.path.join(VAULT, v['path']), encoding='utf-8') as f:
                m = re.search(r'^posted_at: "([^"]+)"', f.read(1200), re.M)
            if not m:
                continue
            h = (dt.datetime.fromisoformat(m.group(1).replace('Z', '+00:00')) + dt.timedelta(hours=9)).hour
        except (OSError, KeyError, TypeError, ValueError):
            continue
        total += 1
        day += 7 <= h < 18
    return [BROWSER_MORNING, BROWSER_EVENING] if total and day * 2 >= total else [BROWSER_MORNING]


def daily_posts(items, today):
    """지난 30일 날마다 글 수(끝 = 오늘) — 받기 칸의 근거 막대 · 목록 첫 쪽에 보인 글만 세서 실제보다 적을 수 있다."""
    out = [0] * 30
    for v in items.values():
        try:
            k = (today - dt.date.fromisoformat(str(v.get('date') or '')[:10])).days
        except (ValueError, AttributeError):
            continue
        if 0 <= k < 30:
            out[29 - k] += 1
    return out


def recommend(rc, items, today):
    """Claude 추천 시각 — 조리법 rec_at(Claude 가 따로 정한 것)이 먼저 · 없으면 규칙: 일정·목록 = 하루 한 번 18:00 ·
    지난 30일(관찰이 짧으면 그 날 수) 하루 글 0.5편 이상 = 12:00·18:00 · 그 밑 = 18:00(학교 글은 낮 9~17시에 올라옴 · 11-12 잼)."""
    own = at_list(rc.get('rec_at'))
    if own:
        return own
    if rc.get('family') in ('calendar', 'listing'):
        return list(REC_ONCE)
    ds = []
    for v in items.values():
        try:
            ds.append(dt.date.fromisoformat(str(v.get('date') or '')[:10]))
        except (ValueError, AttributeError):
            pass
    if not ds:
        return list(REC_ONCE)
    days = max(1, min(30, (today - min(ds)).days + 1))
    n = sum(1 for d in ds if 0 <= (today - d).days < days)
    return list(REC_BOTH) if n / days >= REC_TWICE else list(REC_ONCE)


def at_list(v):
    """조리법·desk.json 의 시각 목록 — 틀린 꼴이면 빈 목록(엔진도 그 출처를 주기로 돌린다)."""
    try:
        return as_at(','.join(v)) if isinstance(v, list) else []
    except Refuse:
        return []


def browser_at(rc, desk):
    """로그인 출처가 크롬을 띄울 시각 — settings at · 칸이 없으면 조리법 at_default(collect-browser.Source.at 와 같은 규칙)."""
    return at_list(desk.get('at')) if 'at' in desk else at_list(rc.get('at_default'))


def next_at(at, now):
    """다음 시각(datetime) — 오늘 남은 첫 시각, 없으면 내일 첫 시각."""
    for t in at:
        h, m = map(int, t.split(':'))
        c = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if c > now:
            return c
    h, m = map(int, at[0].split(':'))
    return (now + dt.timedelta(days=1)).replace(hour=h, minute=m, second=0, microsecond=0)


# ── 일어난 일 상세(11-12 사용자 «일어난 일을 상세보기 · 지금 정보가 너무 부실») — 기록 셋(web.log·auto.log·장부)과 글마다 run 을 묶는다 · 읽기만 ──
HIST_N = 60
HIST_SHOW = 40              # 보기 자료에 싣는 출처마다 기록 줄 수(기록 칸)
WHO = {'at': '시각 예약', 'tick': '15분 확인', 'fetch': '지금 받기', 'judge': '판정', 'me': ME, 'claude': 'Claude', 'ext': '확장', 'wake': '크롬 띄우기'}


def _ts(day, hm):
    return dt.datetime.strptime(f'{day} {hm}', '%Y-%m-%d %H:%M')


def _run_at(r):
    """수집 번호 YYYYMMDD-HHMM → 때 · 꼴이 다르면(목록 가족의 옛 번호 등) None."""
    try:
        return dt.datetime.strptime(str(r)[:13], '%Y%m%d-%H%M')
    except ValueError:
        return None


_ONCE = {}


def _once(*p):
    """같은 실행 안에서 기록 파일을 한 번만 읽는다(보기 한 번에 출처마다 history)."""
    k = os.path.join(*p)
    if k not in _ONCE:
        _ONCE[k] = read(*p)
    return _ONCE[k]


def _ledger():
    if '_led' in _ONCE:
        return _ONCE['_led']
    out = []
    for line in _once(SYS, 'ledger', 'actions.jsonl').splitlines():
        try:
            e = json.loads(line)
            out.append((dt.datetime.fromisoformat(e['ts'][:19]), e))
        except (ValueError, KeyError, TypeError):
            pass
    _ONCE['_led'] = out
    return out


def _trigger(sid, t, led):
    """그 받기를 무엇이 돌렸나 — 장부에서 ±3분 안: 시각 예약(collect.tick·collect.at --at <sid> · 옛 장부 이름 포함) · 지금 받기(collect_desk.fetch) · 없으면 15분 확인."""
    for when, e in led:
        if abs((when - t).total_seconds()) > 180:
            continue
        if str(e.get('action') or '').startswith('collect.') and (e.get('rest') or [None, None])[-1] == sid:
            return 'at', e.get('seconds')
        if e.get('action') == 'collect_desk.fetch' and (e.get('args') or {}).get('source') == sid:
            return 'fetch', e.get('seconds')
    return 'tick', None


def _item(sid, aid, it):
    return {'id': aid, 'title': (it.get('title') or '').strip(), 'where': where(it), 'why': said(it.get('why') or it.get('verdict') or ''),
            'verdict': it.get('verdict') or '', 'files': len(it.get('files') or []), 'note': note_of(it, sid, aid)}


def web_history(sid, n=HIST_N):
    """웹 출처 기록 — 한 받기 = «목록» 줄부터 3분 안의 «받음·수정·첨부» 줄 + 그 run 의 글. 판정·보관·승인 줄은 따로. 내가 한 일(장부)도 함께. 새것이 위."""
    st = load(SYS, '_index', 'collect', sid + '.json', default={}) or {}
    items = {k: v for k, v in (st.get('items') or {}).items() if isinstance(v, dict)}
    by_run = {}
    for aid, it in items.items():
        by_run.setdefault(it.get('run') or '', []).append(_item(sid, aid, it))
    led = _ledger()
    out, cur = [], None
    for line in _once(SYS, '_index', 'collect', 'web.log').splitlines():
        m = LOG_LINE.match(line)
        if not m or m.group(3) != sid:
            continue
        day, hm, _, msg = m.groups()
        t = _ts(day, hm)
        if msg.startswith(('목록', '표')):
            who, secs = _trigger(sid, t, led)
            g = lambda rx: int(re.search(rx, msg).group(1)) if re.search(rx, msg) else 0
            cur = {'t': fmt(t), '_at': t, 'kind': 'run', 'who': who, 'secs': secs, 'ok': True, 'lines': [msg],
                   'nums': {'list': g(r'(\d+)건'), 'new': g(r'새 글 (\d+)'), 'changed': g(r'바뀐 글 (\d+)')}, 'items': []}
            runs = [r for r in by_run if (rt := _run_at(r)) and abs((rt - t).total_seconds()) <= 120]
            for r in runs:
                cur['items'] += by_run.pop(r)
            out.append(cur)
        elif cur and (t - cur['_at']).total_seconds() <= 180 and msg.startswith(('받음', '수정', '첨부')):
            cur['lines'].append(msg)
            w = re.search(r'대기 칸 (\d+) · 제목 장부 (\d+)', msg)
            if w:
                cur['nums'].update(wait=int(w.group(1)), ledger=int(w.group(2)))
            b = re.search(r'받음 (\d+)/(\d+)', msg)
            if b:
                cur['nums'].update(got=int(b.group(1)))
        elif msg.startswith(('판정 반영', '보관', '승인', '되돌림')):
            g = re.search(r'볼트에 들임 (\d+)', msg)
            out.append({'t': fmt(t), 'kind': 'judge' if msg.startswith('판정') else 'me', 'who': 'judge' if msg.startswith('판정') else 'me', 'ok': True,
                        'lines': [msg], 'nums': {'vault': int(g.group(1)) if g else 0}, 'items': []})
            cur = None
        elif re.search(r'실패|오류|예외', msg):
            out.append({'t': fmt(t), 'kind': 'fail', 'who': 'tick', 'ok': False, 'lines': [msg], 'nums': {}, 'items': []})
    for r in out:
        r['_at'] = r.get('_at') or dt.datetime.strptime(f"{dt.date.today().year}-{r['t']}", '%Y-%m-%d %H:%M')
    for when, e in led:                                  # 내가 한 일 — 설정·판정·글 단추
        a, g = e.get('action') or '', e.get('args') or {}
        if not a.startswith('collect_desk.') or g.get('source') != sid or a == 'collect_desk.fetch':
            continue
        s = (event_word(g['field'], g['value']) if a == 'collect_desk.set' and 'field' in g else
             '판정' if a == 'collect_desk.judge' else '거절' if a == 'collect_desk.reject' else
             {'rescue': '승인', 'restore': '되돌림', 'useless': '헛것', 'useful': '쓸모', 'reject': '거절'}.get(g.get('op'), '') if a == 'collect_desk.item' else '')
        if not s:
            continue
        it = items.get(g.get('id') or '')
        out.append({'t': fmt(when), '_at': when, 'kind': 'me', 'who': 'me' if e.get('by') in ('obsidian', 'user') else 'claude', 'ok': not e.get('code'), 'secs': e.get('seconds'),
                    'lines': [s], 'nums': {}, 'items': [_item(sid, g['id'], it)] if it else [], 'say': s})
    out.sort(key=lambda r: r['_at'], reverse=True)
    for r in out:
        r.pop('_at', None)
    return out[:n]


def browser_history(rc, n=HIST_N):
    """로그인 출처 기록 — 그 상태 폴더 auto.log 의 «수집 <run> (<왜>)»부터 그 run 의 파일화(조리법 filer)·요청 줄 + manifest 의 그 run 글·파일 · 로그인 끊김·되살아남 · 크롬 띄우기."""
    man = load(bpath(rc, 'manifest'), default={}) or {}
    filer = os.path.splitext(rc.get('filer') or '')[0] or '파일화'
    names = {}
    for kind, d in (('글', man.get('items') or {}), ('파일', man.get('files') or {})):
        for v in d.values():
            if isinstance(v, dict) and v.get('run'):
                p = re.split(r'[\\/]', v.get('path') or '')
                names.setdefault(v['run'], []).append({'title': os.path.splitext(p[-1])[0] if p else '', 'where': kind, 'why': course_of(v), 'note': (v.get('path') or '').replace('\\', '/') if str(v.get('path') or '').endswith('.md') else ''})
    out, cur = [], None
    for line in _once(bstate(rc), 'auto.log').splitlines():
        m = re.match(r'^(\d{4}-\d\d-\d\d) (\d\d:\d\d):\d\d (.+)$', line)
        if not m:
            continue
        day, hm, msg = m.groups()
        t = fmt(_ts(day, hm))
        r = re.match(r'수집 (\S+) \((\w+)\) 오류=(\S+) canvas=(\S+) board=(\S+)', msg)
        if r:
            run, why, err = r.group(1), r.group(2), r.group(3)
            cur = {'t': t, 'kind': 'run', 'who': 'ext', 'ok': err == 'None', 'lines': [msg], 'why': {'daily': '전 과목', 'signal': '바뀐 과목', 'now': '지금 받기'}.get(why, why),
                   'nums': {}, 'items': names.get(run, [])}
            out.append(cur)
        elif cur and msg.startswith((filer, '요청 GET', 'ingest', 'schedule')):
            cur['lines'].append(msg)
            w = re.search(r'새 글 (\S+) · 바뀐 글 (\S+) · 파일 들임 (\S+)', msg)
            if w:
                cur['nums'].update({k: int(v) for k, v in zip(('new', 'changed', 'files'), w.groups()) if v.isdigit()})
            q = re.search(r'요청 GET (\d+)', msg)
            if q:
                cur['nums']['get'] = int(q.group(1))
        elif '로그인 out' in msg or '로그인 ok' in msg:
            out.append({'t': t, 'kind': 'login', 'who': 'ext', 'ok': '로그인 ok' in msg, 'lines': [msg], 'nums': {}, 'items': []})
            cur = None
        elif msg.startswith('깨우기:'):
            out.append({'t': t, 'kind': 'wake', 'who': 'wake', 'ok': '못' not in msg and '없음' not in msg, 'lines': [msg[5:].strip()], 'nums': {}, 'items': []})
            cur = None
        elif re.match(r'대기열 (?!web|tasks|courses)\S+: ', msg) and 'web-collect' not in msg:      # 그 로그인 출처 대기열 줄만(웹·예약 줄은 그 출처 몫)
            out.append({'t': t, 'kind': 'fail', 'who': 'ext', 'ok': False, 'lines': [msg], 'nums': {}, 'items': []})
    out.reverse()
    return out[:n]


def sort_alert_rows(sid):
    """분류 알림(범용 도구 셋 S9 11-18) → «일어난 일» 줄(kind alert · who sort). 알림 도구는 mobility 몫(사용자 11-18 «알림도구를 mobility 주관으로») —
    mobility 가 켜져 있으면 알림 도구의 장부(_index/sort/알림.jsonl · mobility 가 씀 · 때 · 묶음 · 폰에 냈나 · 중복은 안 냄)를 그대로 그린다(옛 꼴 그대로).
    꺼졌거나 없으면 본체 넘김 장부(_index/sort/넘김.jsonl)의 알림 줄(분류가 정한 알림 · 자리·제목 칸)을 직접 읽는다 — 데스크톱에는 그래도 보인다.
    줄이 없으면 [] (그때 기록 칸은 옛것과 바이트 같음)."""
    _, ix = sort_dirs()
    out = _tool_alert_rows(ix, sid)
    have = {(r.pop('_k')) for r in out}
    if mobility_alerts():
        return out
    for ln in _once(ix, '넘김.jsonl').splitlines():
        try:
            e = json.loads(ln)
            if not isinstance(e, dict) or e.get('자리') != sid or not isinstance((e.get('동작') or {}).get('알림'), dict):
                continue
            t = dt.datetime.fromisoformat(str(e.get('시각'))[:19])
        except (ValueError, TypeError):
            continue
        if (e.get('체계'), e.get('대상'), e.get('갈래')) in have:
            continue
        al = e['동작']['알림']
        say = f'{e.get("체계") or ""} · {e.get("갈래") or ""}'
        out.append({'t': fmt(t), '_at': t, 'kind': 'alert', 'who': 'sort', 'ok': True, 'say': say[:60],
                    'lines': [x for x in (f'{say} · {e.get("제목") or e.get("대상") or ""}', f'때 {al.get("때") or "바로"}{" · 급함" if e.get("급함") else ""}',
                                         '폰 안 냄(알림 도구 = mobility · 꺼짐)') if x], 'nums': {}, 'items': []})
    return sorted(out, key=lambda r: r['_at'])


ALERT_TOOL = os.path.join(VAULT, '.claude', 'skills', 'mobility', 'scripts', 'alert.py')     # 알림 도구 = mobility 모듈(11-18)


def mobility_alerts():
    """알림 도구가 도는가 — mobility 대본이 있고 모듈이 켜짐(roles.module_on). 모르면 False(넘김 장부를 읽음)."""
    try:
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        import roles
        return os.path.isfile(ALERT_TOOL) and bool(roles.module_on('mobility'))
    except Exception:  # noqa: BLE001
        return False


def _tool_alert_rows(ix, sid):
    """알림 도구(mobility)가 낸 알림 줄 — 알림 장부 _index/sort/알림.jsonl 중 이 자리(출처) 줄 · 펼치면 글 · 때 · 폰에 냈나."""
    out = []
    for ln in _once(ix, '알림.jsonl').splitlines():
        try:
            e = json.loads(ln)
            if not isinstance(e, dict) or e.get('자리') != sid:
                continue
            t = dt.datetime.fromisoformat(str(e.get('시각'))[:19])
        except (ValueError, TypeError):
            continue
        k, m = (list(e.get('묶음') or []) + [1, 1])[:2]
        phone = '폰에 냄' if e.get('폰') is True else ('폰 못 냄 · ' + str(e.get('폰 못 냄') or e.get('폰'))) if e.get('폰 못 냄') else '폰 안 냄(mobility 꺼짐)'
        when = f'때 {e.get("때") or "바로"} · 울릴 때 {str(e.get("울릴 때") or "")[5:16].replace("T", " ")}'
        out.append({'t': fmt(t), '_at': t, 'kind': 'alert', 'who': 'sort', 'ok': True, 'say': str(e.get('제목') or '')[:60],
                    'lines': [x for x in (f'{e.get("제목") or ""} · {e.get("글") or ""}', f'{e.get("체계") or ""} · {e.get("갈래") or ""}{" · 급함" if e.get("급함") else ""}'
                                         + (f' · {k}/{m}' if m and m > 1 else ''), f'{when} · {phone}', e.get('링크') or '') if x],
                    'nums': {}, 'items': [], '_k': (e.get('체계'), e.get('대상'), e.get('갈래'))})
    return out


def history(sid, n=HIST_N):
    rc = browser(sid)
    rows = browser_history(rc, n) if rc else web_history(sid, n)
    al = sort_alert_rows(sid)
    if not al:
        return rows
    for r in rows:                                   # 기록 줄은 «MM-DD HH:MM» — 해를 붙여 알림 줄과 견줌(새것이 위)
        r['_at'] = dt.datetime.strptime(f"{dt.date.today().year}-{r['t']}", '%Y-%m-%d %H:%M')
    rows = sorted(rows + al, key=lambda r: r['_at'], reverse=True)[:n]
    for r in rows:
        r.pop('_at', None)
    return rows


# ── 로그인 출처(조리법 collect/browser/<id>.json · 개인 층) — 이름·자리는 조리법이 말한다(S6) ──
def browsers():
    """로그인 출처 조리법 — 단위 지도(units)가 있는 것만(단위 표가 있어야 줄이 생긴다 · 옛 규칙 그대로)."""
    return [rc for rc in cl.browser_recipes(SYS) if rc.get('units')]


def browser(sid):
    return next((rc for rc in browsers() if rc['id'] == sid), None)


def bpath(rc, key):
    """조리법 자리 칸 → 절대 경로(manifest 가 없으면 상태 폴더 안)."""
    if key == 'manifest' and not rc.get('manifest'):
        return os.path.join(bstate(rc), 'manifest.json')
    return cl.rpath(rc.get(key), SYS)


def bstate(rc):
    return cl.browser_state(rc, SYS)


def bsettings(rc):
    d = load(bpath(rc, 'settings'), default={}) if rc.get('settings') else {}
    return d if isinstance(d, dict) else {}


def course_of(v):
    p = re.split(r'[\\/]', v.get('path') or '')
    return p[2] if len(p) > 2 else '?'


def browser_url(rc):
    """로그인 출처 주소 — 조리법 ext.host 의 «https://호스트/»(S5 · 확장 manifest 엔 호스트가 없다 — 출처마다 허용). 없거나 와일드카드면 빈칸."""
    h = (rc.get('ext') or {}).get('host') if isinstance(rc, dict) and isinstance(rc.get('ext'), dict) else None
    m = re.match(r'^(https?://[^/*]+)/?$', h) if isinstance(h, str) else None
    return m.group(1) + '/' if m else ''


def browser_source(rc, queue, cfg, now):
    courses = load(bpath(rc, 'units'))
    if not isinstance(courses, dict):
        return None
    sid, desk = rc['id'], bsettings(rc)
    man = load(bpath(rc, 'manifest'), default={}) or {}
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
    for p in sorted(glob.glob(os.path.join(bstate(rc), 'runs', '*.json')), key=os.path.getmtime, reverse=True):
        d = load(p, default={}) or {}
        have = have or d.get('version') or ''          # 확장이 돌린 판 — 가장 최근 요약
        if d.get('kind') == 'run' and not last_full:
            last_full = d
        if d.get('kind') == 'status' and not last_status:
            last_status = d
        if last_full and last_status:
            break
    want = (load(SYS, 'collect-ext', 'manifest.json', default={}) or {}).get('version') or ''   # 확장 폴더 = 본체 collect-ext(S5)

    ev = []
    filer = os.path.splitext(rc.get('filer') or '')[0] or '파일화'
    for line in read(bstate(rc), 'auto.log').splitlines():
        m = re.match(r'^(\d{4}-\d\d-\d\d) (\d\d:\d\d):\d\d (.+)$', line)
        if not m:
            continue
        day, hm, msg = m.groups()
        t = f'{day[5:]} {hm}'
        if msg.startswith(filer):
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
    pp = (rc.get('posts') or {}).get('pending') if isinstance(rc.get('posts'), dict) else ''
    pend = (load(cl.rpath(pp, SYS), default={}) or {}) if pp else {}
    try:
        asked = dt.datetime.fromisoformat(desk.get('fetch_now') or '')
    except ValueError:
        asked = None
    url, at = browser_url(rc), browser_at(rc, desk)
    qrx = re.compile('(' + BROWSER_QUEUE + '|' + re.escape(rc.get('run_prefix') or sid + '-run-') + '.+)')
    return {'id': sid, 'name': sid, 'host': url.split('/')[2] if url else '', 'url': url, 'busy': busy_of(sid), 'pend': len(pend), 'ext': {'have': have, 'want': want},
            'fetchWait': bool(asked and (not last or asked > last)),     # 지금 받기를 눌렀고 그 뒤 받기가 아직 없음
            'family': 'browser', 'group': rc.get('group') or '강의', 'purpose': desk.get('purpose') or '',
            'on': desk.get('enabled', True) is not False, 'wakeOn': wake_chosen() == 'high', 'wake': ' '.join(at),
            'method': 'chrome', 'at': at, 'mode': 'at', 'rec': at_list(desk.get('rec_at')) or browser_rec(its), 'nextAt': fmt(next_at(at, now)) if at else '',
            'hours': 0.25, 'hourWord': '15분', 'next': '15분마다', 'last': fmt(last) if last else '',
            'late': bool(last and (now - last).total_seconds() / 3600 > BROWSER_LATE_H),
            'login': (last_status or {}).get('login'),
            'loginAt': fmt(dt.datetime.fromtimestamp(last_status['at'] / 1000)) if last_status and last_status.get('at') else '',
            'courses': clist, 'events': ev[:EVENTS], 'items': [], 'cnt': None,
            'problems': [q for q in queue if q['id'] not in web_ids and qrx.fullmatch(q['id'] or '')],
            'tot': {'posts': len(its), 'files': len(fls), 'board': sum(len(v) for v in board.values())},
            'alarm': alarm_of(cfg, rc.get('schedule') or ''), '_src': cl.rpath(pp, SYS) if pp else ''}


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
CAND = os.path.join(SYS, 'collect', 'candidates', 'candidates.json')     # 후보(Claude 가 조사해 적은 새 출처 · 개인 층 · 하위 폴더 = 웹 엔진의 collect/*.json 에 안 걸림 · S6)


def cand_rows():
    d = load(CAND, default={}) or {}
    return [c for c in (d.get('candidates') or []) if isinstance(c, dict) and c.get('id')] if isinstance(d, dict) else []


def candidates():
    """아직 답이 «안 함» 이 아니고 조리법이 안 생긴 후보만 — 조리법이 생기면 그 출처 줄이 대신한다."""
    return [{k: c.get(k) or '' for k in ('id', 'name', 'host', 'measured', 'note', 'answer')} for c in cand_rows()
            if c.get('answer') != '안 함' and not os.path.exists(os.path.join(SYS, 'collect', c['id'] + '.json'))]


# ── 고치기 ──
REGEX_CH = re.compile(r'[\\()^$.*+?\[\]{}]')
SWITCH = os.path.join(SYS, 'collect.local.json')               # 전체 스위치(all_off·auto_judge) — 이 PC 의 결정 · git 밖
QUEUE = os.path.join(SYS, '_index', '수집-대기열.md')


def switches():
    """전체 스위치 — collect.local.json(엔진과 같은 규칙 · 없음·깨짐 = 켜짐·자동 판정 끔)."""
    return cl.switches(SYS)


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


def reflect_known(sid=None):
    """로그인 출처 스위치·단위를 확장이 읽는 파일에 바로 반영(다음 15분 확인 때 읽힌다 · 로그인 가족 collect-browser.py --known)."""
    p = os.path.join(SYS, 'collect-browser.py')
    if not os.path.exists(p):
        return
    r = subprocess.run([sys.executable, p, '--known', *(['--source', sid] if sid else [])], cwd=VAULT, capture_output=True, encoding='utf-8', errors='replace', creationflags=NO_WINDOW)
    if r.returncode:
        raise Refuse('known.json 반영 실패: ' + (r.stderr or r.stdout)[-200:])


def set_desk(sid, field, value, sync=True):
    if sid == '*' and field == 'wake_pc':                       # PC 깨우기 = 기능 «PC 깨우기» 값 하나(단계 탭과 같은 값 · 11-20 나눔) — 켬 high · 끔 off · 옛 자리 칸은 걷는다
        set_option(WAKE_PC, as_bool(value))
        sw = load(SWITCH, default={})
        if isinstance(sw, dict) and 'wake_pc' in sw:
            sw.pop('wake_pc')
            save_json(SWITCH, sw)
    elif sid == '*' and field in ('all_off', 'auto_judge'):    # 전체 스위치 = collect.local.json(auto_judge 기본 끔) — 엔진이 다음 돌림부터 읽는다
        sw = load(SWITCH, default={})
        sw = sw if isinstance(sw, dict) else {}
        sw[field] = as_bool(value)
        save_json(SWITCH, sw)
    elif field == 'wake' and (sid == '*' or browser(sid)):    # 크롬 띄우기 = 기능 «크롬 띄우기» 값 하나(11-07 사용자 «두 스위치 통일») — 켬 high · 끔 off
        set_wake_level(as_bool(value), browser(sid))
    else:
        rc = browser(sid)
        if not rc or not rc.get('settings'):
            raise Refuse(f'못 고치는 칸: {sid} {field}')
        d = bsettings(rc)
        if field == 'enabled':
            d[field] = as_bool(value)
        elif field == 'purpose':
            d['purpose'] = value.strip()[:200]
        elif field == 'at':                                     # 크롬을 뒤에서 띄울 시각(빈 값 = 안 띄움 · 확장은 크롬이 떠 있는 동안 15분마다 그대로)
            set_at(d, value, keep_empty=True)
        else:
            raise Refuse(f'못 고치는 칸: {sid} {field}')
        save_json(bpath(rc, 'settings'), d)
    if field in ('enabled', 'all_off'):
        reflect_known(None if sid == '*' else sid)
    if sync and field in ('enabled', 'all_off', 'wake', 'at', 'wake_pc'):  # 시각 예약도 같은 길로 — 전체 끔·그 출처 끔이면 크롬을 안 띄우고 PC 를 안 깨운다(헛깨우기 막음)
        sync_wake()


def set_option(fid, on):
    """켬/끔 기능 하나를 바꾼다(단계 탭과 같은 값 · 장부는 options 가 · 옛 칸 값은 먼저 옮김)."""
    sys.path.insert(0, SYS)
    try:
        import options
        options.migrate(via='migrate:collect_desk')
        options.set_level(fid, 'high' if on else 'off', via='collect_desk')
    except ImportError:
        raise Refuse('기능 단계 대본(options.py)이 없음')
    except Exception as e:      # options.OptErr — 선언 없음·고른 값 파일 깨짐
        raise Refuse(f'기능 단계를 못 바꿈: {e}')


def set_wake_level(on, rc=None):
    """기능 «크롬 띄우기»를 바꾼다 · settings 의 옛 wake 칸은 걷는다(이제 안 읽음)."""
    set_option(WAKE_LEVEL, on)
    for r in ([rc] if rc else browsers()):
        old = bsettings(r)
        if 'wake' in old and r.get('settings'):
            old.pop('wake')
            save_json(bpath(r, 'settings'), old)


def wake_chosen():
    """크롬 띄우기 값 = 기능 «크롬 띄우기»의 고른 값(배터리 규칙 전 · collect-browser.Source.wake_level 과 같은 규칙) — 못 읽으면 'high'."""
    try:
        sys.path.insert(0, SYS)
        import options
        local, st = options._load(options.local_path(None))
        return options.chosen(local, st, options.declarations(None, only=WAKE_LEVEL)).get(WAKE_LEVEL, 'high')
    except Exception:
        return 'high'


def wake_pc_on():
    """PC 깨우기 값 — 기능 «PC 깨우기»(없으면 옛 collect.local.json wake_pc · 엔진 collectlib.wake_pc 와 같은 규칙)."""
    return cl.wake_pc(SYS)


def sync_wake():
    """시각 예약(«외부뇌-수집 …» · 제공자가 있으면 로그인 출처 깨우기 포함)을 지금 값대로 맞춘다(본체 엔진 collect-schedule.py --sync)."""
    p = os.path.join(SYS, 'collect-schedule.py')
    if not os.path.exists(p):
        return
    r = subprocess.run([sys.executable, p, '--sync'], cwd=VAULT, capture_output=True, encoding='utf-8', errors='replace', creationflags=NO_WINDOW)
    if r.returncode:
        raise Refuse('시각 예약 맞추기 실패(값은 바뀜): ' + (r.stderr or r.stdout)[-200:])


def set_course(sid, value):
    rc = browser(sid)
    c = load(bpath(rc, 'units')) if rc else None
    if not isinstance(c, dict):
        raise Refuse('단위 지도를 못 읽음')
    edit_courses(c, value)
    save_json(bpath(rc, 'units'), c)
    reflect_known(sid)


def edit_courses(c, value):
    """과목(단위) 넣고 빼기 — 단위 지도 내용(dict)만 고친다(연습 흉내도 같은 규칙 · E2)."""
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


def set_recipe(sid, field, value, sync=True):
    path = os.path.join(SYS, 'collect', sid + '.json')
    rc = load(path)
    if not isinstance(rc, dict) or rc.get('id') != sid:
        raise Refuse(f'없는 출처: {sid}')
    edit_recipe(rc, field, value)
    save_json(path, rc)
    if sync and field in ('at', 'enabled', 'hours'):            # 시각 예약 «외부뇌-수집 <id>» 가 따라간다(끈 출처·주기로 바꾼 출처는 예약도 없앰)
        sync_tasks()


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
    elif field == 'hours':                      # 주기를 고르면 시각은 걷는다(주기 ↔ 시각 둘 중 하나)
        rc['recheck_hours'] = as_num(value, 1, 24, float)
        rc.pop('at', None)
        rc.pop('at_since', None)
    elif field == 'at':
        set_at(rc, value)
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


AT_MAX = 4


def as_at(value):
    """«시각» 값 — 'HH:MM,HH:MM' (빈 글자 = 시각 없음 → 웹은 주기로 · 로그인 출처는 크롬을 안 띄움) · 하루 4개까지 · 정렬."""
    out = []
    for t in [x.strip() for x in str(value).replace(' ', ',').split(',') if x.strip()]:
        m = re.fullmatch(r'(\d{1,2}):(\d{2})', t)
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            raise Refuse(f'시각 꼴 HH:MM: {t}')
        t = f'{int(m.group(1)):02d}:{m.group(2)}'
        if t not in out:
            out.append(t)
    if len(out) > AT_MAX:
        raise Refuse(f'시각은 하루 {AT_MAX}개까지')
    return sorted(out)


def set_at(holder, value, keep_empty=False):
    """시각 칸을 dict 에 쓴다 — at_since = 정한 때(정하기 전 시각을 따라잡지 않게 · web-collect last_slot).
    빈 값: 조리법은 칸을 없앤다(= 주기로) · 로그인 출처(keep_empty)는 빈 목록을 남긴다(칸이 없으면 조리법 at_default 로 읽힌다)."""
    at = as_at(value)
    holder.pop('at_since', None)
    if at:
        holder['at'], holder['at_since'] = at, int(time.time())
    elif keep_empty:
        holder['at'] = []
    else:
        holder.pop('at', None)


def sync_tasks():
    """시각 예약(«외부뇌-수집 …»)을 지금 설정대로 맞춘다 — 본체 엔진 collect-schedule.py --sync."""
    sync_wake()


def group_ids(name):
    """묶음(강의·공지·구독·일정)에 든 출처 id — 화면 묶음과 같은 규칙(web_source group)."""
    ids = []
    for p in sorted(glob.glob(os.path.join(SYS, 'collect', '*.json'))):
        rc = load(p)
        if isinstance(rc, dict) and rc.get('id'):
            g = '일정' if rc.get('family') in ('calendar', 'listing') else rc.get('group') or ('공지' if rc.get('filter') else '구독')
            if g == name:
                ids.append(rc['id'])
    ids += [rc['id'] for rc in browsers() if (rc.get('group') or '강의') == name and isinstance(load(bpath(rc, 'units')), dict)]
    return ids


def set_value(sid, field, value):
    if field == 'course':
        if not browser(sid):
            raise Refuse('과목은 로그인 출처 칸')
        return set_course(sid, value)
    if sid.startswith('@'):                                     # 묶음 하나에 같은 값(시각·주기) — 출처마다 그대로 쓴다(묶음 값을 따로 두지 않음)
        if field not in ('at', 'hours'):
            raise Refuse(f'묶음에는 시각·주기만: {field}')
        ids = [i for i in group_ids(sid[1:]) if not (field == 'hours' and browser(i))]
        if not ids:
            raise Refuse(f'없는 묶음: {sid[1:]}')
        for i in ids:
            if browser(i):
                set_desk(i, field, value, sync=False)
            else:
                set_recipe(i, field, value, sync=False)
        return sync_tasks()
    if sid == '*' or browser(sid):
        return set_desk(sid, field, value)
    return set_recipe(sid, field, value)


# ── 받기·판정·글 하나 — 엔진을 부른다 ──
def busy_path(sid):
    return os.path.join(SYS, '_index', 'collect', f'desk-busy-{sid}.txt')     # 점 없는 이름 = 옵시디언이 보고 화면을 새로 그린다


class Busy:
    """15분 반영과 같은 잠금(엔진 자리)으로 15분 예약과 같은 상태 파일을 동시에 안 쓴다 · 도는 동안 화면에 그 낱말이 보인다."""

    def __init__(self, sid, word):
        self.path, self.word, self.sid = busy_path(sid), word, sid

    def __enter__(self):
        t = os.environ.get('COLLECT_TEST_STATE')                  # 시험 상태 폴더 — collect-schedule.lock_path 와 같은 규칙(S6)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.f = cl.try_lock(os.path.join(t, 'auto.lock') if t else os.path.join(SYS, '_index', 'collect', 'tick.lock'))
        if self.f is None:
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
    """웹 = 그 자리에서 받는다(엔진의 계약·스위치 관문 그대로) · 로그인 출처 = PC → 확장 길이 known 파일뿐이라 다음 15분 확인 때 돈다."""
    if switches().get('all_off') is True:
        raise Refuse('전체가 꺼져 있음')
    rc = browser(sid)
    if rc:
        d = bsettings(rc)
        if d.get('enabled') is False:
            raise Refuse(f'{sid} 가 꺼져 있음')
        d['fetch_now'] = dt.datetime.now().isoformat(timespec='seconds')
        save_json(bpath(rc, 'settings'), d)
        return reflect_known(sid)
    if recipe_of(sid).get('enabled') is False:
        raise Refuse('꺼진 출처')
    with Busy(sid, '받는 중'):
        engine('web-collect.py', '--source', sid, '--force')


def judge_source(sid):
    """구독 사용량이 든다 — 누를 때만 · 그 출처만. 끈 출처는 판정 반영(settle)도 멈추므로 받지 않는다."""
    rc = browser(sid)
    if switches().get('all_off') is True or (rc and bsettings(rc).get('enabled') is False) or (not rc and recipe_of(sid).get('enabled') is False):
        raise Refuse('꺼진 출처')
    post = ((rc.get('posts') or {}).get('sid') if isinstance(rc.get('posts'), dict) else '') if rc else sid    # 로그인 출처 = 그 «마감 불명» 글 칸(조리법 posts.sid)
    if not post:
        raise Refuse('판정할 글 칸이 없는 출처')
    with Busy(sid, '판정 중'):
        if sort_on() and os.path.exists(os.path.join(SYS, 'sort.py')):    # S4 — 그 자리에 걸린 체계 전부(한 대상 한 호출 · 꽁돈만 대기도) · 엔진 오류(3)면 옛 길
            r = subprocess.run([sys.executable, os.path.join(SYS, 'sort.py'), 'judge', '--place', sid, '--yes'], cwd=VAULT, capture_output=True,
                               encoding='utf-8', errors='replace', creationflags=NO_WINDOW, env=dict(os.environ, PYTHONIOENCODING='utf-8'))
            if r.returncode == 0:
                return
            if r.returncode != 3:
                raise Refuse((r.stderr or r.stdout or f'sort.py rc={r.returncode}').strip()[-200:])
        engine('notice-filter.py', 'extract', '--source', post)


def sort_act(op, ident):
    """분류 칸 단추(S4 · 초안 B) — ack <사건>(알림 «확인» · 그 체계가 걸린 출처 모두에서 닫힘) · revert <사건>(알림 «되돌리기») ·
    rule <체계>/<규칙>(규칙 줄 «되돌리기» · 자동 규칙만). 되돌린 뒤 공지 판정을 다시 그려(사용량 0) 판정표·일정이 따라온다."""
    if op not in ('ack', 'revert', 'rule'):
        raise Refuse(f'모르는 동작: {op}')
    with Busy('sort', '고치는 중'):
        if op == 'ack':
            engine('sort.py', 'ack', ident)
            return
        if op == 'revert':
            engine('sort.py', 'revert', ident)
        else:
            sid, _, rule = ident.partition('/')
            if not sid or not rule:
                raise Refuse('rule <체계>/<규칙>')
            engine('sort.py', 'revert', '--system', sid, '--rule', rule)
        engine('notice-filter.py', 'judge')


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
    """사이트를 연다 — 열기만 한다(비밀번호를 다루지 않는다). 로그인 출처는 확장이 있는 크롬으로."""
    rc = browser(sid)
    if rc:
        url = browser_url(rc)
    elif os.path.exists(os.path.join(SYS, 'collect', sid + '.json')):
        url = recipe_of(sid).get('page') or ''
    else:
        url = next((c.get('url') or '' for c in cand_rows() if c['id'] == sid), '')
    if not re.match(r'^https?://', url):
        raise Refuse(f'주소 없음: {sid}')
    if os.environ.get('DESK_NO_OPEN'):              # 시험 — 창을 안 띄운다
        return print(url)
    if rc:
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
                f.write(cl.QUEUE_HEAD)
            f.write(f'- [ ] {time.strftime("%Y-%m-%d %H:%M:%S")} `{cid}` (Claude) 수집 계약 승인(수집 창) — {row.get("name")} {row.get("url")} · 조리법을 탐색해 쓴다 · 근거 {row.get("note")}\n')


# ── 개인 파일 처음 만들기(S6 · 배포판에 안 실리는 개인 파일마다 «만드는 길») — 빈 틀 = 3_시스템/collect-examples · 이미 있으면 안 덮음 ──
EXAMPLES = os.path.join(SYS, 'collect-examples')
NEXT_BROWSER = """다음(사람 손 · 로그인은 사람):
  1. 크롬 chrome://extensions → 개발자 모드 → «압축해제된 확장 프로그램을 로드합니다» → 3_시스템/collect-ext
  2. 크롬 퍼즐 아이콘 → «외부뇌 로그인 수집기» → «{id} · {host} 허용» → 크롬이 묻는 창에서 «허용»
  3. 그 사이트에 늘 하던 대로 로그인 — 확장이 15분마다 받는다(크롬이 떠 있는 동안)
  4. 첫 받기 뒤 대기열 «단위 지도에 없는 수강 강좌 N개: [번호…]» → {units} 에 «번호: 폴더 이름»으로 더한다(꼴 = collect-examples/units.json)
  5. 시각 받기·아침 깨우기 = 수집 창 그 출처 칸(시각 예약은 수집 창이 맞춘다)"""


def new_personal(kind, rest):
    """kind = browser <id> <https://호스트> | card | candidates → 만든 파일(볼트 상대 경로) 목록. 이미 있으면 거부(덮어쓰지 않는다)."""
    made = []

    def put(path, data):
        if os.path.exists(path):
            raise Refuse(f'이미 있음(안 덮음): {os.path.relpath(path, VAULT)}')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if isinstance(data, str):
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(data)
        else:
            save_json(path, data)
        made.append(os.path.relpath(path, VAULT).replace('\\', '/'))

    if kind == 'browser':
        if len(rest) != 2 or not ID_RX.fullmatch(rest[0]) or not re.fullmatch(r'https://[a-z0-9.-]+(?::\d+)?', rest[1]):
            raise Refuse('new browser <id(영문 소문자·숫자·-)> <https://호스트>')
        sid, host = rest
        if any(rc['id'] == sid for rc in cl.browser_recipes(SYS)) or os.path.exists(os.path.join(SYS, 'collect', sid + '.json')):
            raise Refuse(f'이미 있는 출처: {sid}')
        rc = json.loads(open(os.path.join(EXAMPLES, 'browser.json'), encoding='utf-8').read().replace('{id}', sid).replace('{host}', host))
        rc['_'] = f'로그인 출처 조리법(개인 층) — {dt.date.today().isoformat()} collect_desk.py new browser 가 빈 틀(3_시스템/collect-examples/browser.json)에서 만듦 · 칸 뜻 = collect-browser.py 머리글'
        put(cl.rpath(rc['units'], SYS), {})
        put(cl.rpath(rc['settings'], SYS), {})
        put(os.path.join(SYS, *cl.BROWSER, sid + '.json'), rc)
        reflect_known(sid)
        print(NEXT_BROWSER.format(id=sid, host=host, units='3_시스템/' + rc['units']))
    elif kind == 'card':
        rel = roles.find_note('자격-카드') or roles.path('notes', '자격-카드.md')
        t = open(os.path.join(EXAMPLES, 'card-template.md'), encoding='utf-8').read()
        if t.startswith('---\n') and not re.search(r'^sensitive:\s*true\s*$', t.split('\n---', 1)[0], re.M):
            t = t.replace('---\n', '---\nsensitive: true\n', 1)    # 만든 카드만 민감(push 제외) — 빈 틀에 이 줄이 있으면 커밋 거름망이 틀을 git 밖으로 빼 배포판에 안 실린다(S7 11-17 잼)
        put(os.path.join(VAULT, *rel.split('/')), t)
        print('다음: 그 노트의 JSON 칸을 채운다(모르는 칸은 null) — 공지 필터가 다음 판정부터 읽는다')
    elif kind == 'candidates':
        put(CAND, {'candidates': []})
        print('다음: Claude 가 조사한 새 출처를 이 꼴(3_시스템/collect-examples/candidates.json)로 더한다 — 수집 창 «후보» 줄')
    else:
        raise Refuse('new browser <id> <https://호스트> | new card | new candidates')
    return made


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
        raise Refuse(f'robots {" · ".join(blocked)} — {ME} 결정을 초안 robots_note 에 적은 뒤')
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
    rc['contract'] = (f'{dt.date.today().isoformat()} {ME} 수집 창 «수집 추가» 확정 · 목적 «{str(rc["purpose"]).strip()[:80]}» · robots {rb[0]}'
                      + (f'({note[:80]})' if note else '') + ' · 공개 페이지 · 받기만(GET)')
    rc.pop('enabled', None)
    at = at_list(rc.get('at'))                  # 받기 시각 = Claude 가 정함(11-12 · 수집 추가 5단계) — 확정 때부터 센다(지난 시각을 따라잡지 않게)
    rc.pop('at_since', None)
    if at:
        rc['at'], rc['at_since'] = at, int(time.time())
    else:
        rc.pop('at', None)
    save_json(dst, rc)
    done_draft(did)
    if at:
        sync_tasks()                            # 시각 예약 «외부뇌-수집 <id>»
    when = f'매일 {" ".join(at)}(시각 예약 «외부뇌-수집 {did}»)' if at else f'{rc.get("recheck_hours", 20):g}시간마다(15분 확인)'
    print(f'추가: 3_시스템/collect/{did}.json — 받기 {when}')


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


FIELD_WORD = {'enabled': '수집', 'wake': '크롬 띄우기', 'all_off': '전체 끔', 'auto_judge': '자동 판정', 'download': '첨부', 'images': '그림', 'auto': '자동 판정', 'purpose': '목적', 'hours': '주기', 'pages': '쪽',
              'skip+': '뺄 말 더함', 'skip-': '뺄 말 뺌', 'keep+': '남길 말 더함', 'keep-': '남길 말 뺌', 'course': '과목'}


def event_word(field, value):
    v = {'true': '켬', 'false': '끔'}.get(value, value)
    if field == 'all_off':
        return '전체 끔' if value == 'true' else '전체 켬'
    if field == 'wake_pc':                                      # 잠든 PC(11-12) — 깨움 = 그 시각에 PC 를 깨움 · 깬 뒤 = 깬 뒤 놓친 것 한 번
        return 'PC 깨우기 켬' if value == 'true' else 'PC 깨우기 끔'
    if field == 'course':
        return ('과목 뺌 ' if value.endswith('=off') else '과목 넣음 ') + value.split('=')[0]
    if field == 'at':                                           # 시각(11-11) — 비우면 웹은 주기로 · 로그인 출처는 크롬 안 띄움
        return '시각 ' + (' '.join(x.strip() for x in value.split(',') if x.strip()) or '없음')
    if field == 'hours':
        return f'주기 {value}시간'
    return f'{FIELD_WORD.get(field, field)} {v}'


def my_events():
    """수집 창에서 사용자가 한 일 — 장부(brain.py 가 적음)에서."""
    ev, groups = {}, {}
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
            src = g.get('source') or g['id']
            if s and src.startswith('@'):                       # 묶음에 준 값(시각·주기) — 그 묶음 출처마다 «묶음 …» 한 줄
                if src not in groups:
                    groups[src] = group_ids(src[1:])
                for i in groups[src]:
                    ev.setdefault(i, []).append({'t': e['ts'][5:16].replace('T', ' '), 's': '묶음 ' + s, 'me': True})
            elif s:
                ev.setdefault(src, []).append({'t': e['ts'][5:16].replace('T', ' '), 's': s, 'me': True})
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
    return ev


MOA_SKIP = {'.git', '.obsidian', '.trash', '.claude', 'node_modules', '__pycache__'}


def moa_files():
    """볼트의 .moa 전부(이름 순) · 점 폴더 · 0_작업(초안·격리 사본) · 1_수집(원본 층) 밖 · 연습 때는 VAULT 가 임시 폴더라 빈 목록."""
    out = []
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [x for x in dirs if x not in MOA_SKIP and not x.startswith('.') and not (root == VAULT and x in ('0_작업', '1_수집'))]
        for f in files:
            if f.endswith('.moa'):
                out.append({'name': f[:-4], 'path': os.path.relpath(os.path.join(root, f), VAULT).replace('\\', '/')})
    return sorted(out, key=lambda x: (x['name'], x['path']))


def moa_links():
    """모아보기 바로가기(11-12 사용자 안 2 · 고른 출처 머리 줄 단추) — 출처 id → 그 출처를 모아 보는 .moa 목록.
    짝 = 3_시스템/gather/gather.py sources() 와 같다: .moa from.collect 의 sources 에 든 id · 또는 조리법 filter.label = label(filter 있는 조리법만).
    읽는 것 = 조리법·.moa 정의뿐(줄 셈 없음) · 여는 것은 화면이 open 으로(brain-base 가 형식 화면으로 엶)."""
    labels = {}
    for p in glob.glob(os.path.join(SYS, 'collect', '*.json')):
        rc = load(p)
        if isinstance(rc, dict) and rc.get('id') and rc.get('filter'):
            labels[rc['id']] = (rc.get('filter') or {}).get('label')
    out = {}
    for m in moa_files():
        try:
            d = json.load(open(os.path.join(VAULT, *m['path'].split('/')), encoding='utf-8'))
            src = (d.get('from') or {}).get('collect') or {}
            ids, label = src.get('sources'), src.get('label')
        except (OSError, ValueError, AttributeError):
            continue
        for sid, lab in labels.items():
            if (ids and sid in ids) or (label and lab == label):
                out.setdefault(sid, []).append(m)
    return out


# ── 분류 체계 칸(범용 도구 셋 S4 · 초안 B «규칙 칸 + 알림 줄» · 사용자 11-18) ──
# sort 가 쓴 것만 읽는다(엔진·어댑터를 안 부름): 자리 요약 _index/sort/자리.json · 사건 _index/sort/사건.jsonl · 체계 파일 3_시스템/sort/*.json.
# «판정 N» = 그 출처(자리)에 걸린 모든 체계의 판정 대기(한 대상 한 번) · 규칙 칸 = 걸린 체계의 켠 규칙 · 알림 줄 = 열린 사건(자동 채택·가격선 바뀜 …).
# 옛 길 = collect.local.json "sort": false — 그때·요약이 없을 때·요약이 엔진 상태보다 옛것일 때 «판정 N» 은 엔진 상태의 판정 대기(옛 셈).
SORT_SYS = SORT_IX = None          # 시험이 바꿔 끼움(없으면 SYS/sort · SYS/_index/sort — 연습 때는 임시 폴더라 체계 0)


def sort_dirs():
    return SORT_SYS or os.path.join(SYS, 'sort'), SORT_IX or os.path.join(SYS, '_index', 'sort')


def sort_on():
    return cl.switches(SYS, keys=('sort',)).get('sort') is not False


def sort_events(ix):
    rows, shut = {}, set()
    for ln in read(ix, '사건.jsonl').splitlines():
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        if isinstance(e, dict) and e.get('id'):
            (shut.add(e['id']) if '닫힘' in e else rows.__setitem__(e['id'], e))
    return [e for k, e in rows.items() if k not in shut]


def sort_desk():
    """{자리: {judge: n, at: 요약 시각(초), rules: [{id, name, rules: [{id, say, full, to, n, auto}]}], alerts: [{id, sys, text, kind, t, undo}]}} · 끔·요약 없음 = {}."""
    sdir, ix = sort_dirs()
    if not sort_on():
        return {}
    summ = load(ix, '자리.json')
    if not isinstance(summ, dict):
        return {}
    try:
        at = os.path.getmtime(os.path.join(ix, '자리.json'))
    except OSError:
        at = 0
    S = {}
    for p in sorted(glob.glob(os.path.join(sdir, '*.json'))):
        s = load(p)
        if isinstance(s, dict) and s.get('id') and s.get('켬', True) is not False:
            S[s['id']] = s
    per = {k: v for k, v in (summ.get('체계') or {}).items() if k in S}
    out = {}

    def slot(pl):
        return out.setdefault(pl, {'judge': 0, 'at': at, 'rules': [], 'alerts': []})
    for sid, pls in per.items():
        s = S[sid]
        for pl, c in pls.items():
            rs = []
            for r in s.get('규칙') or []:
                if r.get('켬') is False or not r.get('id'):
                    continue
                seen = (c.get('갈래') or {}).get(r['id']) or {}
                to = r.get('갈래') or ('·'.join(sorted(seen, key=lambda g: -seen[g])) if seen else '표' if '표' in r else '—')
                rs.append({'id': r['id'], 'say': r.get('짧게') or r.get('말') or r['id'], 'full': r.get('말') or '', 'to': to,
                           'n': (c.get('맞은') or {}).get(r['id'], 0), 'auto': str(r.get('만든이', '')).startswith('자동')})
            if rs:
                slot(pl)['rules'].append({'id': sid, 'name': s.get('이름') or sid, 'rules': rs})
    for pl, n in (summ.get('판정') or {}).items():
        slot(pl)['judge'] = n
    for e in sort_events(ix):
        sid = e.get('체계')
        if sid not in S:
            continue
        for pl in e.get('자리') or list((per.get(sid) or {}).keys()):
            slot(pl)['alerts'].append({'id': e['id'], 'sys': S[sid].get('이름') or sid, 'text': e.get('글') or '', 'kind': e.get('종류') or '',
                                       't': str(e.get('시각') or '')[5:16].replace('T', ' '), 'undo': bool(e.get('되돌리기'))})
    return out


def attach_sort(sources):
    """출처마다 sort 칸을 붙인다 — judge(«판정 N») · sort(규칙·알림). 원천(엔진 상태)이 요약보다 새것이면 «판정 N» 은 옛 셈."""
    try:
        sd = sort_desk()
    except Exception:            # 분류 칸이 못 떠도 창은 뜬다(옛 «판정 N»)
        sd = {}
    for x in sources:
        src = x.pop('_src', '')
        d = sd.get(x['id'])
        if not sd:
            continue
        try:
            fresh = not src or not os.path.exists(src) or os.path.getmtime(src) <= (d or {}).get('at', max((v['at'] for v in sd.values()), default=0)) + 1
        except OSError:
            fresh = False
        if fresh and (x.get('cnt') is not None or x.get('family') == 'browser'):
            x['judge'] = (d or {}).get('judge', 0)
        if d and (d['rules'] or d['alerts']):
            x['sort'] = {'rules': d['rules'], 'alerts': d['alerts']}


def view(_reason='open'):
    now = dt.datetime.now()
    queue = open_queue()
    cfg, alarm_bad = alarm_reader()
    events = web_events()
    sources = []
    for rc in browsers():
        b = browser_source(rc, queue, cfg, now)
        if b:
            sources.append(b)
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
    hist = {}
    for x in sources:
        if not x.get('fixed'):
            try:
                hist[x['id']] = history(x['id'], HIST_SHOW)
            except Exception:       # 기록 하나가 깨져도 창은 뜬다(옛 8줄로)
                pass
    try:
        links = moa_links()
    except OSError:                 # 바로가기가 못 떠도 창은 뜬다
        links = {}
    for x in sources:
        if links.get(x['id']):
            x['moa'] = links[x['id']]
    attach_sort(sources)
    return {'now': fmt(now), 'me': ME, 'hist': hist, 'allOff': sw.get('all_off') is True, 'autoJudge': sw.get('auto_judge') is True, 'wakePc': wake_pc_on(), 'alarmNote': alarm_note() if cfg is not False else ALARM_NOTE, 'alarmBad': alarm_bad, 'sources': sources, 'candidates': candidates()}


# ── 연습(튜토리얼 E2 · 11-08) — «연습: 모듈» 장 동안 수집 창이 그리는 자료 · 쓰기 흉내 ──
PRACTICE_ID = '연습-'      # 연습 자료 id 머리 — 진짜 id(ID_RX = 영문 소문자·숫자·-)와 겹칠 수 없다 · 진짜 쓰기 명령은 이 id 를 거부(main)


def practice_inputs(now):
    """연습 입력 — 진짜 view() 가 읽는 파일 꼴 그대로 {볼트 상대 경로: 값}. 정상(공지)·실패(구독)·로그인 끊김(로그인 출처) 셋 + 후보 하나 + 걸러진 글 몇."""
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
        '3_시스템/collect/browser/연습-강의/units.json': {'101': '자료구조', '102': '전자기학', '_제외': {'103': '2026 체육 — 수집 창에서 뺌'}},
        '3_시스템/collect/browser/연습-강의/settings.json': {'purpose': '강의 공지·과제 마감'},
        '3_시스템/collect-ext/manifest.json': {'version': '1.0.0'},
        '3_시스템/collect/browser/연습-강의.json': {'id': '연습-강의', 'family': 'browser', 'ext': {'host': 'https://school.example.org'}, 'filer': 'canvas-file.py', 'at_default': ['06:55'],
                                                 'units': 'collect/browser/연습-강의/units.json', 'settings': 'collect/browser/연습-강의/settings.json', 'state': '_index/연습-강의'},
        '3_시스템/_index/연습-강의/manifest.json': {'items': {'p1': {'path': '연습/강의/자료구조/1주차.md'}, 'p2': {'path': '연습/강의/전자기학/과제1.md'}},
                                               'files': {'q1': {'path': '연습/강의/자료구조/강의자료.pdf'}}, 'board': {}},
        '3_시스템/_index/연습-강의/runs/run.json': {'kind': 'run', 'startedAt': int(ago(20).timestamp() * 1000), 'version': '1.0.0'},
        '3_시스템/_index/연습-강의/runs/status.json': {'kind': 'status', 'at': int(ago(1).timestamp() * 1000), 'login': 'out', 'version': '1.0.0'},
        '3_시스템/_index/연습-강의/auto.log': f'{stamp(20)} canvas-file 새 글 2 · 파일 들임 1\n{stamp(1)} 로그인 out\n',
        '3_시스템/collect/candidates/candidates.json': {'candidates': [{'id': '연습-후보', 'name': '취업 박람회 소식', 'host': 'example.org', 'url': 'https://example.org/fair',
                                                       'measured': '목록 20줄 · 글마다 날짜 · 주 1~2번 새 글', 'note': '', 'answer': ''}]},
    }


def practice_act(F, act, now):
    """흉내 행위 하나 → 연습 입력(진짜 쓰기·엔진·사이트 0). 고침 규칙은 진짜와 같은 함수(edit_recipe·edit_courses·as_bool) ·
    진짜처럼 장부 줄을 남겨 «일어난 일»에 뜬다 · 진짜가 거부할 일은 같은 말로 거부(Refuse)."""
    aid, g = act.get('id'), act.get('args')
    if not isinstance(g, dict) or not all(isinstance(v, str) for v in g.values()):
        raise Refuse('인자 꼴')
    src = g.get('source', '')
    lms = src == '연습-강의'                                    # 연습 로그인 출처(조리법 3_시스템/collect/browser/연습-강의.json)
    rc = F.get(f'3_시스템/collect/{src}.json')
    st = F.get(f'3_시스템/_index/collect/{src}.json') or {}
    sw = F.setdefault('3_시스템/collect.local.json', {})
    desk = F.setdefault('3_시스템/collect/browser/연습-강의/settings.json', {})
    if aid == 'collect_desk.set':
        field, value = g.get('field', ''), g.get('value', '')
        if field == 'course':
            if not lms:
                raise Refuse('과목은 로그인 출처 칸')
            edit_courses(F['3_시스템/collect/browser/연습-강의/units.json'], value)
        elif src == '*' and field in ('all_off', 'auto_judge', 'wake_pc'):
            sw[field] = as_bool(value)
        elif lms and field in ('enabled', 'wake'):
            desk[field] = as_bool(value)
        elif lms and field == 'purpose':
            desk['purpose'] = value.strip()[:200]
        elif lms and field == 'at':
            set_at(desk, value, keep_empty=True)
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
            it.update(verdict='뺌', why=f'{ME}: 거절')
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
        it.update(verdict='뺌', why=f'{ME}: {said or "거절"}')
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
        row = next((c for c in F['3_시스템/collect/candidates/candidates.json']['candidates'] if c.get('id') == g.get('id')), None)
        if g.get('answer') not in ('계약', '안 함') or not row:
            raise Refuse(f'계약 또는 안 함 · 있는 후보: {g.get("id")}')
        row.update(answer=g['answer'], at=now.date().isoformat())
        if g['answer'] == '계약':
            F['3_시스템/_index/수집-대기열.md'] += f'- [ ] {now:%Y-%m-%d %H:%M} `{row["id"]}` (Claude) 수집 계약 승인(수집 창) — {row["name"]}\n'
    elif aid == 'collect_desk.open':
        return              # 연습은 사이트를 열지 않는다
    else:
        raise Refuse(f'연습에 없는 행위: {aid}')
    rec = g                                         # 장부 줄 = brain.py 가 적는 꼴(my_events 가 «일어난 일»로 그림)
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
    desk = F['3_시스템/collect/browser/연습-강의/settings.json']
    with tempfile.TemporaryDirectory(prefix='외부뇌-연습-') as root:
        for rel, v in F.items():
            p = os.path.join(root, *rel.split('/'))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8', newline='\n') as f:
                f.write(v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
        sysd = os.path.join(root, '3_시스템')
        globals().update(VAULT=root, SYS=sysd, PLAN=os.path.join(root, '2_지식', '일정'), CAND=os.path.join(sysd, 'collect', 'candidates', 'candidates.json'),
                         SWITCH=os.path.join(sysd, 'collect.local.json'),
                         QUEUE=os.path.join(sysd, '_index', '수집-대기열.md'), DRAFT=os.path.join(sysd, '_index', 'collect', 'draft'),
                         wake_chosen=lambda: 'low' if desk.get('wake') is False else 'high')
        out = view('practice')
    out['practice'] = {'acts': len(acts), 'refused': refused}
    out.pop('hist', None)               # 연습은 일어난 일 옛 8줄 그대로(기록 칸은 진짜 기록에만 · 11-12)
    return out


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    hs = sub.add_parser('history')                       # 일어난 일 상세(11-12) — 출처 하나의 기록 JSON
    hs.add_argument('source')
    hs.add_argument('--n', type=int, default=HIST_N)
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
    so = sub.add_parser('sort')                          # 분류 칸 단추(S4) — ack|revert <사건 id> · rule <체계>/<규칙>
    so.add_argument('op')
    so.add_argument('id')
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
    nw = sub.add_parser('new')                           # 개인 파일 처음 만들기(S6)
    nw.add_argument('kind', choices=['browser', 'card', 'candidates'])
    nw.add_argument('rest', nargs='*')
    a = ap.parse_args()
    if a.cmd == 'history':
        return print(json.dumps(history(a.source, a.n), ensure_ascii=False))
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
        elif a.cmd == 'sort':
            sort_act(a.op, a.id)
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
        elif a.cmd == 'new':
            print('만듦: ' + ' · '.join(new_personal(a.kind, a.rest)))
    except Refuse as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
