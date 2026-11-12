"""알림 모듈 — 일정 줄과 수집 상태에서 폰이 울릴 목록을 만든다(LLM 0). 서버가 /v1/alarms 로 내준다.

  py -3 3_시스템/alarms.py [--days N]     # 앞으로 울릴 것을 시각 순으로(상태를 바꾸지 않는다)
  py -3 3_시스템/alarms.py --check        # 알림 설정에 틀린 칸이 있나
  py -3 3_시스템/alarms.py --report       # 폰이 보고한 늦음·놓침(_index/alarms/fired.jsonl)

무엇을 언제 울릴지는 사용자 설정 = 노트 [[알림-설정]] 의 json 블록(칸 설명은 그 노트). 요청 때마다 읽어 재시작 없이 반영한다.
틀린 값은 그 칸만 기본값으로 울리고, 틀린 칸을 «알림 설정 틀림» 한 번으로 알린다 — 잘못 고쳐 알림이 조용히 사라지면 안 된다.
바로 알릴 것 = 시각 예약이 아니라 폰이 당겨 올 때 울린다(지난 시각으로 받은 알람은 바로 울린다). 잘 시간이면 아침으로.
쓰는 곳은 _index/alarms 뿐이다(상태·보고 장부). 볼트 노트는 쓰지 않는다.
"""
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import schedule  # noqa: E402 — 일정 줄 문법은 한 곳

DEFAULTS = {
    '켬': True,
    '기본': {'며칠_전': [3, 1], '시각': ['20:00']},        # 사용자 11-05
    '파일': {'LMS-마감.md': {}, '내-일정.md': {}, '장학-마감.md': {}, '공지-마감.md': {'며칠_전': [1]}},     # 알림 설정 노트(11-05 사용자)와 같게 — 노트가 깨져도 공지 마감이 조용해지지 않게
    '과목': {},
    '글자': [],
    '잘_시간': {'부터': '23:00', '까지': '08:00'},
    '바로': {'막힘': True, '옮겨짐': True, '늦게_앎': True, '새_공지': True},     # 새 공지 = 사용자 승인 11-05
    '당겨_오기_분': 30,                                     # 폰이 몇 분마다 당겨 오나(사용자 합격선: «바로» 60분 이내)
}
PENDING = '(판정 대기)'
MAX_ITEMS = 400                         # 안드로이드는 앱당 알람 500개에서 예외를 낸다
EVENT_DAYS = 7                          # 폰이 이만큼 못 당기면 사건은 사라진다
NOTICE_DAYS = 7                         # 게시일이 이보다 오래된 공지는 새 공지로 안 친다(새 출처 첫 수집이 몰아 울리지 않게)
NOTICE_BUNDLE = 3                       # 한 번에 이보다 많으면 «새 공지 N건» 하나로
PROBE_AT = dt.time(3, 17)               # 재기: 폰이 깊이 잠들어 있을 때
PROBE_NIGHTS = 3                        # 며칠 PC 가 잠들어도 이어지게
WD = '월화수목금토일'
SETTINGS = os.path.join(os.path.dirname(HERE), '2_지식', '일', '외부뇌', '알림-설정.md')     # 일정 폴더 밖 — 폰에서도 고치게(일정 폴더는 폰 쓰기 금지)
STATE = os.path.join(HERE, '_index', 'alarms')
FIRED = os.path.join(STATE, 'fired.jsonl')
SEEN = os.path.join(STATE, 'seen.json')
QUEUE = os.path.join(HERE, '_index', '수집-대기열.md')
QUEUE_LINE = None                       # 사람 줄 «(호칭)» — 호칭은 프로필에서(blocked_lines 가 처음 부를 때 짓는다)
HHMM = re.compile(r'^([01]?\d|2[0-3]):([0-5]\d)$')
JSON_BLOCK = re.compile(r'^```json[ \t]*\r?\n(.*?)^```', re.M | re.S)
LOCK = threading.Lock()


# ───────── 설정 ─────────
def rule_of(raw, where, problems):
    """규칙 칸 하나 → 맞는 값만 담은 사전. 틀린 값은 빼고 문제에 적는다(위 단계 값이 그대로 쓰인다)."""
    out = {}
    if not isinstance(raw, dict):
        problems.append(f'{where}: {{}} 꼴이어야 함')
        return out
    for k, v in raw.items():
        if k == '며칠_전':
            if isinstance(v, list) and v and all(type(x) is int and 0 <= x <= 365 for x in v):
                out[k] = sorted(set(v), reverse=True)
            else:
                problems.append(f'{where}.며칠_전: 0~365 숫자 목록이어야 함 ({json.dumps(v, ensure_ascii=False)})')
        elif k == '시각':
            if isinstance(v, list) and v and all(isinstance(x, str) and HHMM.match(x) for x in v):
                out[k] = sorted({f'{int(x.split(":")[0]):02d}:{x.split(":")[1]}' for x in v})
            else:
                problems.append(f'{where}.시각: "20:00" 꼴의 목록이어야 함 ({json.dumps(v, ensure_ascii=False)})')
        elif k == '끔':
            if isinstance(v, bool):
                out[k] = v
            else:
                problems.append(f'{where}.끔: true 나 false 여야 함 ({json.dumps(v, ensure_ascii=False)})')
        elif k != '포함':
            problems.append(f'{where}.{k}: 모르는 칸')
    return out


def parse_settings(text):
    """노트 글 → (설정, 문제들). 없는 칸은 기본값, 틀린 칸은 기본값 + 문제."""
    problems = []
    s = json.loads(json.dumps(DEFAULTS))
    s['기본'] = dict(DEFAULTS['기본'])
    if text is None:
        return s, problems
    m = JSON_BLOCK.search(text)
    if not m:
        problems.append('json 블록을 못 찾음 — 전부 기본값')
        return s, problems
    try:
        raw = json.loads(m.group(1))
    except ValueError as e:
        problems.append(f'json 오류({e}) — 전부 기본값')
        return s, problems
    if not isinstance(raw, dict):
        problems.append('맨 바깥이 { } 가 아님 — 전부 기본값')
        return s, problems
    for k, v in raw.items():
        if k == '켬':
            if isinstance(v, bool):
                s[k] = v
            else:
                problems.append(f'켬: true 나 false 여야 함 ({json.dumps(v, ensure_ascii=False)})')
        elif k == '기본':
            s[k] = {**s[k], **{a: b for a, b in rule_of(v, '기본', problems).items() if a != '끔'}}
        elif k == '파일':
            files = {}
            if isinstance(v, dict) and v:
                for name, r in v.items():
                    name = name if name.endswith('.md') else name + '.md'
                    files[name] = rule_of(r, f'파일.{name}', problems)
                    if not os.path.exists(os.path.join(schedule.SCHED_DIR, name)):
                        problems.append(f'파일.{name}: 일정 폴더에 없는 파일')
                # 이름을 잘못 적어 울릴 파일이 하나도 없으면 조용히 다 꺼진다
                if not any(os.path.exists(os.path.join(schedule.SCHED_DIR, n)) and not r.get('끔') for n, r in files.items()):
                    if not all(r.get('끔') for r in files.values()):
                        problems.append('파일: 울릴 파일이 하나도 없음 — 기본 파일로 울림')
                        files = dict(DEFAULTS['파일'])
                s[k] = files
            else:
                problems.append('파일: 비었거나 { } 꼴이 아님 — 기본 파일로 울림(다 끄려면 «켬»)')
        elif k == '과목':
            if isinstance(v, dict):
                s[k] = {name: rule_of(r, f'과목.{name}', problems) for name, r in v.items()}
            else:
                problems.append('과목: { } 꼴이어야 함')
        elif k == '글자':
            if isinstance(v, list):
                rules = []
                for i, r in enumerate(v):
                    if isinstance(r, dict) and isinstance(r.get('포함'), str) and r['포함'].strip():
                        rules.append({'포함': r['포함'], **rule_of(r, f'글자[{i}]', problems)})
                    else:
                        problems.append(f'글자[{i}]: "포함" 글자가 있어야 함')
                s[k] = rules
            else:
                problems.append('글자: [ ] 꼴이어야 함')
        elif k == '잘_시간':
            if isinstance(v, dict):
                for a, b in v.items():
                    if a not in ('부터', '까지'):
                        problems.append(f'잘_시간.{a}: 모르는 칸')
                    elif isinstance(b, str) and HHMM.match(b):
                        s[k][a] = b
                    else:
                        problems.append(f'잘_시간.{a}: "23:00" 꼴이어야 함 ({json.dumps(b, ensure_ascii=False)})')
            else:
                problems.append('잘_시간: { } 꼴이어야 함')
        elif k == '바로':
            if isinstance(v, dict):
                for a, b in v.items():
                    if a not in DEFAULTS['바로']:
                        problems.append(f'바로.{a}: 모르는 칸')
                    elif isinstance(b, bool):
                        s[k][a] = b
                    else:
                        problems.append(f'바로.{a}: true 나 false 여야 함 ({json.dumps(b, ensure_ascii=False)})')
            else:
                problems.append('바로: { } 꼴이어야 함')
        elif k == '당겨_오기_분':
            if type(v) is int and 15 <= v <= 1440:     # 15분 = 안드로이드 주기 작업의 하한
                s[k] = v
            else:
                problems.append(f'당겨_오기_분: 15~1440 숫자여야 함 ({json.dumps(v, ensure_ascii=False)})')
        else:
            problems.append(f'{k}: 모르는 칸')
    return s, problems


def load_settings(path=None):
    path = path or SETTINGS
    try:
        with open(path, encoding='utf-8') as f:
            text = f.read()
    except OSError:
        text = None
    return parse_settings(text)


def rule_for(s, name, text):
    """기본 ← 파일 ← 과목 ← 글자 순으로 덮는다. 목록에 없는 파일은 꺼진 채 시작한다(글자 칸의 «끔: false» 로 그 줄만 켠다)."""
    r = {**s['기본'], '끔': name not in s['파일']}
    r.update(s['파일'].get(name, {}))
    r.update(s['과목'].get(text.split(' · ')[0], {}))
    for g in s['글자']:
        if g['포함'] in text:
            r.update({k: v for k, v in g.items() if k != '포함'})
    return r


# ───────── 시각 ─────────
def ms(t):
    return int(t.timestamp() * 1000)


def minutes(hhmm):
    h, m = hhmm.split(':')
    return int(h) * 60 + int(m)


def at_clock(day, hhmm, tz):
    h, m = hhmm.split(':')
    return dt.datetime(day.year, day.month, day.day, int(h), int(m), tzinfo=tz)


def awake(t, due, s):
    """잘 시간에 떨어진 울림은 아침으로. 아침이 마감에 너무 가까우면 잠들기 한 시간 전으로."""
    a, b = s['잘_시간']['부터'], s['잘_시간']['까지']
    f, to, m = minutes(a), minutes(b), t.hour * 60 + t.minute
    if f == to or not ((f <= m or m < to) if f > to else (f <= m < to)):
        return t
    wake_day = t.date() + dt.timedelta(days=1) if f > to and m >= f else t.date()
    morning = at_clock(wake_day, b, t.tzinfo)
    if due - morning >= dt.timedelta(hours=1):
        return morning
    start_day = t.date() - dt.timedelta(days=1) if f > to and m < to else t.date()
    return at_clock(start_day, a, t.tzinfo) - dt.timedelta(hours=1)


def ring_times(due, rule, s):
    """[(칸, 시각)] 이른 것부터. 규칙의 시각이 모두 마감 뒤면 마감 한 시간 전에라도 — 규칙 때문에 안 울리는 일은 없게."""
    out = []
    for n in rule['며칠_전']:
        for hhmm in rule['시각']:
            t = awake(at_clock(due.date() - dt.timedelta(days=n), hhmm, due.tzinfo), due, s)
            if t < due:
                out.append((f'd{n}-{hhmm.replace(":", "")}', t))
    return sorted(out, key=lambda x: x[1]) or [('last', due - dt.timedelta(hours=1))]


def date_text(due, timed):
    day = f'{due.month}-{due.day:02d} ({WD[due.weekday()]})'
    return f'{day} {due:%H:%M}' if timed else day


def head_text(t, due):
    n = (due.date() - t.date()).days
    return {0: '오늘', 1: '내일'}.get(n, f'{n}일 뒤')


# ───────── 줄과 사건 ─────────
def key_of(m):
    """같은 일정의 열쇠 — 날짜가 바뀌어도 같아야 «옮겨짐»을 안다. 손 줄은 내용으로."""
    return m.group(6) or 'h-' + hashlib.sha1(schedule.clean(m.group(5)).encode('utf-8')).hexdigest()[:12]


def lines_of(rows, s):
    """열린 줄 전부와 그 줄의 규칙. 꺼진 줄도 담는다 — 나중에 켜도 «새 일정»으로 몰아 울리지 않게."""
    out = []
    for f, _, _, m in rows:
        if not m or m.group(1) in 'xX':
            continue
        text = schedule.clean(m.group(5))
        if PENDING in text:
            continue
        try:
            d = dt.date.fromisoformat(m.group(2))
            h, mi = (int(x) for x in m.group(3).split(':')) if m.group(3) else (23, 59)
            due = dt.datetime(d.year, d.month, d.day, h, mi, tzinfo=schedule.KST)
        except ValueError:
            continue
        out.append({'key': key_of(m), 'date': m.group(2), 'due': due, 'timed': bool(m.group(3)), 'text': text, 'rule': rule_for(s, os.path.basename(f), text)})
    return out


def blocked_lines(path=None):
    """수집-대기열에서 사용자 손이 필요한 열린 줄 [(시각, 무엇)]."""
    path = path or QUEUE
    if not os.path.exists(path):
        return []
    global QUEUE_LINE
    if QUEUE_LINE is None:
        import roles
        QUEUE_LINE = re.compile(r'^- \[ \] (\S+ \S+) `[^`]*` \(' + re.escape(roles.me()) + r'\) (.+)$')
    with open(path, encoding='utf-8') as f:
        return [m.groups() for m in map(QUEUE_LINE.match, f.read().splitlines()) if m]


def heading(path):
    """글 md 의 머리줄(# 제목) — 못 읽으면 None."""
    try:
        with open(path, encoding='utf-8') as f:
            m = re.search(r'^# (.+)$', f.read(4000), re.M)
    except (OSError, UnicodeDecodeError):
        return None
    return m.group(1).strip() if m else None


def new_notices():
    """판정을 통과해 볼트에 든 공지 글(판정 층이 있는 조리법의 폴더) [(파일 이름, 제목, 게시일)]."""
    import roles
    out = []
    for p in glob.glob(os.path.join(HERE, 'collect', '*.json')):
        try:
            with open(p, encoding='utf-8') as f:
                rc = json.load(f)
            if not rc.get('filter') or not str(rc.get('folder', '')).startswith('@'):
                continue
            role, _, sub = rc['folder'][1:].partition('/')
            for a in glob.glob(os.path.join(roles.abs(role), sub, '*.md')):
                name = os.path.basename(a)[:-3]
                if re.match(r'\d{4}-\d{2}-\d{2} ', name) and not re.search(r' \(개정\d+\)$', name):     # «(개정N)» = 수정된 글의 새 판(web-collect revise) — 새 공지가 아니다(날짜가 바뀌었으면 «옮겨짐»이 울린다)
                    title = name[11:]
                    if '_' in title or len(title) >= 120:       # 파일 이름은 «/ : * ? …» 를 «_» 로 바꾸고 120자에서 자른다 — 원제는 글의 머리줄에(제목이 다르면 일정 줄과 «새 공지 ↔ 늦게 앎» 짝이 빗나간다)
                        title = heading(a) or title
                    out.append((name, title, name[:10]))
        except (OSError, ValueError, KeyError):
            continue
    return out


def refresh(st, lines, now, s, problems, queue, notices):
    """지난번과 견줘 «바로 알릴 것»을 사건으로 남긴다. 처음 한 번은 전부 본 것으로 친다(몰아 울리지 않게)."""
    first = 'known' not in st
    known = set(st.get('known', []))
    prev = st.get('current', {})
    now_ms = ms(now)
    far = now + dt.timedelta(days=30)
    cfg_id = 'ev-config-' + hashlib.sha1('\n'.join(problems).encode('utf-8')).hexdigest()[:12] if problems else ''
    events = [e for e in st.get('events', []) if now_ms - e['made'] < EVENT_DAYS * 86400000 and (not e['id'].startswith('ev-config-') or e['id'] == cfg_id)]
    on = s['바로']
    cur = {}
    for ln in lines:
        if ln['due'] > now:
            cur.setdefault(ln['key'], []).append(ln['date'])

    def add(kind, mark, title, text, due, wanted=True):
        if not first and mark not in known and wanted:
            events.append({'id': f'ev-{kind}-{hashlib.sha1(mark.encode("utf-8")).hexdigest()[:12]}', 'at': ms(awake(now, due, s)), 'title': title, 'text': text, 'made': now_ms})
        known.add(mark)

    # 공지 먼저 — 같은 글의 마감 줄이 함께 처음 보이면 공지 한 번만 울린다. 이름으로 표시해 파일을 옮겨도 다시 안 울린다.
    since = (now.date() - dt.timedelta(days=NOTICE_DAYS)).isoformat()
    fresh = [n for n in notices if f'n|{n[0]}' not in known and n[2] >= since] if on['새_공지'] and not first else []
    if len(fresh) > NOTICE_BUNDLE:
        add('notice', 'n|묶음|' + '|'.join(sorted(n[0] for n in fresh)), f'새 공지 {len(fresh)}건', fresh[0][1], far)
    else:
        for name, title, _ in fresh:
            add('notice', f'n|{name}', title, '새 공지', far)
    known.update(f'n|{n[0]}' for n in notices)
    fresh_titles = [re.sub(r'^\[[^\]]*\]\s*', '', n[1])[:50] for n in fresh]

    for ln in lines:
        if ln['due'] <= now:
            continue
        mark = f"{ln['key']}|{ln['date']}"
        ringing = not ln['rule'].get('끔')
        gone = [d for d in prev.get(ln['key'], []) if d not in cur[ln['key']]]
        if len(gone) == 1 and len(cur[ln['key']]) == 1:
            add('moved', mark, ln['text'], f"{gone[0][5:]} → {date_text(ln['due'], ln['timed'])}", ln['due'], ringing and on['옮겨짐'])
        elif ring_times(ln['due'], ln['rule'], s)[0][1] <= now:
            add('late', mark, ln['text'], date_text(ln['due'], ln['timed']), ln['due'], ringing and on['늦게_앎'] and not any(t in ln['text'] for t in fresh_titles))
        else:
            known.add(mark)
    said = set()                        # 출처 여럿이 같은 까닭(구독 아님·사용량 경고 등)을 대기열에 적어도 같은 말은 한 번만 — 폰에 같은 알림이 줄줄이 뜨지 않게
    for stamp, what in queue:
        add('blocked', f'q|{stamp}|{what}', '수집 막힘', what, far, on['막힘'] and what not in said)
        said.add(what)
    # 설정이 틀리면 첫 실행이어도 알린다(틀린 채 설치되는 경우)
    if problems and not any(e['id'] == cfg_id for e in events) and f'c|{cfg_id}' not in known:
        extra = f' 외 {len(problems) - 1}칸' if len(problems) > 1 else ''
        events.append({'id': cfg_id, 'at': ms(awake(now, far, s)), 'title': '알림 설정 틀림', 'text': f'{problems[0][:80]}{extra} · 그 칸만 기본값으로 울림', 'made': now_ms})
    if problems:
        known.add(f'c|{cfg_id}')
    today = now.date().isoformat()
    st['known'] = sorted(k for k in known if k[:2] in ('q|', 'n|', 'c|') or k.rsplit('|', 1)[-1] >= today)
    st['current'] = cur
    st['events'] = events


def probes(now, nights=PROBE_NIGHTS):
    """조용한 재기 — 소리도 화면도 없이 폰이 깨어 기록만 한다. 사람이 안 봐도 실제 폰이 재진다."""
    out = []
    for i in range(nights + 1):
        t = dt.datetime.combine(now.date() + dt.timedelta(days=i), PROBE_AT, now.tzinfo)
        if t > now:
            out.append({'id': f'probe-{t:%Y%m%d}', 'at': ms(t), 'title': '', 'text': '', 'probe': True})
    return out[:nights]


def quiet_of(s):
    """잘 시간 ["23:00", "08:00"] — 폰의 하트비트가 이때 깨어나지 않게 같이 보낸다(둘이 같으면 잘 시간 없음)."""
    return [s['잘_시간']['부터'], s['잘_시간']['까지']]


def build(cfg=None, now=None, days=92, rows=None, st=None, queue=None, settings=None, notices=None):
    """st 를 주면 사건을 갱신해 함께 낸다(서버). 없으면 시각 예약만(대조용). cfg = 서버 config 의 alarms(mode · probe)."""
    cfg = cfg or {}
    now = now or dt.datetime.now(schedule.KST)
    s, problems = load_settings() if settings is None else settings
    problems = list(problems)
    if not s['켬']:                     # 다 끔 = 빈 목록이라 폰도 다음 당기기에 지운다
        return {'v': 1, 'items': [], 'problems': problems, 'pull_minutes': s['당겨_오기_분'], 'quiet': quiet_of(s)}
    until = now + dt.timedelta(days=days)
    lines = lines_of(schedule.parse_all() if rows is None else rows, s)
    items = []
    if st is not None:
        refresh(st, lines, now, s, problems, blocked_lines() if queue is None else queue, (new_notices() if notices is None else notices))
        items += [{k: e[k] for k in ('id', 'at', 'title', 'text')} for e in st['events']]
    for ln in lines:
        if ln['rule'].get('끔'):
            continue
        for kind, t in ring_times(ln['due'], ln['rule'], s):
            if now < t <= until:
                items.append({'id': f"{ln['key']}@{ln['date']}@{kind}", 'at': ms(t), 'title': ln['text'], 'text': f"{head_text(t, ln['due'])} · {date_text(ln['due'], ln['timed'])}"})
    if cfg.get('probe', True):
        items += probes(now)
    if cfg.get('mode'):                 # 앱을 다시 설치하지 않고 예약 방식을 바꾼다(clock · idle)
        for a in items:
            a['mode'] = cfg['mode']
    items.sort(key=lambda a: (a['at'], a['id']))
    if len(items) > MAX_ITEMS:
        problems.append(f'울림이 {len(items)}개라 앞 {MAX_ITEMS}개만 예약함')
        items = items[:MAX_ITEMS]
    return {'v': 1, 'items': items, 'problems': problems, 'pull_minutes': s['당겨_오기_분'], 'quiet': quiet_of(s)}


# ───────── 저장 ─────────
def load_state():
    try:
        with open(SEEN, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(st):
    os.makedirs(STATE, exist_ok=True)
    tmp = SEEN + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(st, f, ensure_ascii=False)
    os.replace(tmp, SEEN)


def payload(cfg=None):
    """서버가 내줄 바이트와 ETag. 내용이 같으면 같은 태그라 폰이 304 를 받는다."""
    with LOCK:
        st = load_state()
        got = build(cfg, st=st)
        save_state(st)
    data = json.dumps(got, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return data, '"' + hashlib.sha1(data).hexdigest()[:16] + '"'


def fired(b):
    """폰이 보고한 «몇 초 늦게 울렸나»를 장부에."""
    rows = b.get('items') or []
    os.makedirs(STATE, exist_ok=True)
    with LOCK, open(FIRED, 'a', encoding='utf-8', newline='\n') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(',', ':')) + '\n')
    return {'ok': True, 'n': len(rows)}


def report():
    """늦음·놓침. 놓침 = 재기 날짜 사이에 빠진 날(그날 폰이 안 깼거나 아직 보고 전)."""
    rows = []
    if os.path.exists(FIRED):
        with open(FIRED, encoding='utf-8') as f:
            rows = [json.loads(ln) for ln in f if ln.strip()]
    if not rows:
        return print('보고 없음')
    timed = [r for r in rows if not r.get('id', '').startswith('ev-')]
    late = sorted(abs(r.get('late_ms') or 0) / 1000 for r in timed) or [0]
    print(f"시각 울림 {len(timed)}회 · 늦음 중앙값 {late[len(late) // 2]:.1f}초 · 최대 {late[-1]:.1f}초 · 60초 넘음 {sum(x > 60 for x in late)}회")
    now_ones = sorted((r.get('late_ms') or 0) / 60000 for r in rows if r.get('id', '').startswith('ev-'))
    if now_ones:
        print(f'바로 알림 {len(now_ones)}회 · 생긴 뒤 울리기까지 중앙값 {now_ones[len(now_ones) // 2]:.0f}분 · 최대 {now_ones[-1]:.0f}분')
    pr = [r for r in rows if r.get('id', '').startswith('probe-')]
    days = sorted(dt.date(int(r['id'][6:10]), int(r['id'][10:12]), int(r['id'][12:14])) for r in pr)
    if days:
        want = {days[0] + dt.timedelta(days=i) for i in range((days[-1] - days[0]).days + 1)}
        print(f'재기 {len(days)}일 · 깊은 절전에서 깸 {sum(bool(r.get("deep_idle")) for r in pr)}회 · 빠진 날 {sorted(str(d) for d in want - set(days))}')
    for r in rows[-5:]:
        print(r.get('id'), 'late', round((r.get('late_ms') or 0) / 1000, 1), 'deep_idle', r.get('deep_idle'), 'exempt', r.get('exempt'), 'bucket', r.get('bucket'))


def main():
    if '--report' in sys.argv:
        return report()
    if '--check' in sys.argv:
        problems = load_settings()[1]
        print('\n'.join(problems) or '틀린 칸 없음')
        return 1 if problems else 0
    days = int(sys.argv[sys.argv.index('--days') + 1]) if '--days' in sys.argv else 92
    for a in build(days=days)['items']:
        print(dt.datetime.fromtimestamp(a['at'] / 1000, schedule.KST).strftime('%m-%d %H:%M'), a['id'].rsplit('@', 1)[-1].ljust(10), a['title'][:60], '|', a['text'])
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
