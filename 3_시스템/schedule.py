"""일정 생성기 — LMS 원시 JSON(과제 due_at · 게시판·공지 글 속 마감) -> 2_지식/일정/LMS-마감.md.

결정적(LLM 0). 1_수집 은 읽기만 한다. 형식 -> [[외부뇌-일정-형식]]
  py -3 3_시스템/schedule.py build          # LMS-마감.md 다시 쓰기(체크 보존 · 내용 같으면 안 씀)
  py -3 3_시스템/schedule.py check          # 일정 파일의 «- [ ]» 줄 중 형식에 안 맞는 줄 보고
  py -3 3_시스템/schedule.py week [N]       # 오늘부터 N일(기본 7) 열린 일정 — 세션 시작 주입과 같은 결과인지 대조용
세션 시작 주입은 3_시스템/hooks/session-start.ps1 이 파이썬 없이 같은 정규식으로 한다(+160ms 회피).
"""
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LMS_DIR = os.path.join(VAULT, '1_수집', '_lms')
COURSES = os.path.join(VAULT, '3_시스템', 'lms', 'courses.json')
MANIFEST = os.path.join(VAULT, '3_시스템', '_index', 'lms', 'manifest.json')
PENDING = os.path.join(VAULT, '3_시스템', '_index', 'lms', '마감-대기.json')   # 날짜는 있는데 마감인지 불명확한 글 — notice-filter.py 단추가 뽑는다
JUDGED = os.path.join(VAULT, '3_시스템', '_index', 'collect', '조건')          # 그 단추의 결과(lms-post-<글번호>.json)
SCHED_DIR = os.path.join(VAULT, '2_지식', '일정')
OUT = os.path.join(SCHED_DIR, 'LMS-마감.md')

KST = timezone(timedelta(hours=9))  # 한국은 서머타임이 없다 — tzdata 없이 고정 +9
WD = '월화수목금토일'

# 한 줄 = 한 일정. session-start.ps1 의 $rx 와 같은 문법(바꾸면 둘 다).
LINE = re.compile(
    r'^\s*- \[([ xX])\] (\d{4}-\d{2}-\d{2})'
    r'(?: \(\S{1,3}\))?'
    r'(?: (\d{1,2}:\d{2})(?:~(\d{1,2}:\d{2}))?)?'
    r' (.+?)(?: \^([A-Za-z0-9-]+))?\s*$')
TASK = re.compile(r'^\s*- \[[ xX]\] ')


def load_json(p, default):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def src_link(path):
    """원천 md 로 가는 링크. 위키링크가 깨지는 글자(# | ^ [ ])가 있으면 마크다운 링크로."""
    p = path.replace('\\', '/')
    if p.endswith('.md'):
        p = p[:-3]
    if not re.search(r'[#|^\[\]]', p):
        return f'[[{p}|원본]]'
    enc = {' ': '%20', '#': '%23', '(': '%28', ')': '%29', '[': '%5B', ']': '%5D', '|': '%7C', '^': '%5E'}
    return '[원본](' + ''.join(enc.get(c, c) for c in p) + '.md)'


def collect():
    """모든 canvas 원시 JSON 에서 과제를 모은다. 같은 과제는 늦게 수집한 쪽이 이긴다.
    과목마다 가장 늦게 «제대로 받은» 목록에 없는 과제는 LMS 에서 지워진 것이라 뺀다."""
    by_id, latest = {}, {}
    sources = []
    for f in sorted(glob.glob(os.path.join(LMS_DIR, 'lms-canvas-*.json'))):
        d = load_json(f, None)
        if not d:
            continue
        at = d.get('capturedAt', '')
        sources.append((at, os.path.basename(f)))
        for c in d.get('courses', []):
            cid = c.get('id')
            cname = (c.get('course') or {}).get('name', str(cid))
            st, listed = (c.get('status') or {}).get('assignments'), c.get('assignments', [])
            # 제대로 받음 = 상태 200(11-05 부터 적힘) · 옛 수집은 상태가 없어 목록이 비지 않았을 때만(요청 실패도 빈 목록으로 남았다)
            if (st == 200 or (st is None and listed)) and at >= latest.get(cid, ('',))[0]:
                latest[cid] = (at, {a.get('id') for a in listed})
            for a in c.get('assignments', []):
                aid = a.get('id')
                if aid is None:
                    continue
                prev = by_id.get(aid)
                if prev and prev[0] > at:
                    continue
                by_id[aid] = (at, cid, cname, a)
    gone = [aid for aid, (_, cid, _n, _a) in by_id.items() if cid in latest and aid not in latest[cid][1]]
    for aid in gone:
        del by_id[aid]
    return by_id, sources


# ───────── 게시판·공지 글 속 마감 — 과제 칸에 없는 마감(11-03 검토 · LLM 0) ─────────
MON = {m: i + 1 for i, m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split())}
# 점·빗금 꼴은 문제 번호(2.13)와 헷갈리므로 요일·시각·«까지»가 붙을 때만 날짜로 본다
DATE = re.compile(
    r'(?<![\d.])(?:'
    r'(?:(?P<y1>20\d\d)\s*년\s*)?(?P<m1>\d{1,2})\s*월\s*(?P<d1>\d{1,2})\s*일?'
    r'|(?P<y2>20\d\d)\s*[./-]\s*(?P<m2>\d{1,2})\s*[./-]\s*(?P<d2>\d{1,2})\.?'
    r'|(?P<m3>\d{1,2})\s*[/.-]\s*(?P<d3>\d{1,2})(?=\s*(?:\(\S{1,3}\)|까지|마감|\d{1,2}:\d{2}|오전|오후))'
    r'|(?P<mn>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?P<d4>\d{1,2})(?:st|nd|rd|th)?\b(?:,?\s*(?P<y4>20\d\d))?'
    r')(?:\s*\(\S{1,3}\))?', re.I)
TIME = re.compile(r'\s*,?\s*(?:(?P<ap>오전|오후|밤|저녁|낮|새벽|am|pm)\s*)?(?:(?P<h>\d{1,2})\s*(?::\s*(?P<mi>\d{2})|시(?:\s*(?P<mk>\d{1,2})\s*분|\s*(?P<half>반))?)|(?P<mid>자정))(?:\s*(?P<ap2>am|pm)\b)?', re.I)
TIME_BEFORE = re.compile(r'(?P<h>\d{1,2})\s*:\s*(?P<mi>\d{2})\s*(?P<ap2>am|pm)?\s*(?:on|,)?\s*$', re.I)
TAIL = re.compile(r'\s*\)?\s*(?:까지|마감)')
LABEL = re.compile(r'마감|기한|제출일|\bdue\b|deadline|\bby\b|\buntil\b', re.I)
LATE = re.compile(r'추가\s*제출|지각\s*제출|\blate\b', re.I)       # 늦게 낼 때의 기한은 마감이 아니다
HINT = re.compile(r'제출|마감|기한|까지|신청|접수|\bdue\b|deadline|submit|\bby\b|\buntil\b', re.I)


def clock(m):
    """TIME·TIME_BEFORE 의 맞춤 → 'HH:MM' 또는 None(말이 안 되는 시각)."""
    g = m.groupdict()
    if g.get('mid'):
        return '23:59'                  # 그날 자정까지 = 그날 끝
    h = int(g['h'])
    mi = int(g.get('mi') or g.get('mk') or 0) + (30 if g.get('half') else 0)
    ap = (g.get('ap') or g.get('ap2') or '').lower()
    if ap in ('오후', '저녁', '밤', 'pm') and h < 12:
        h += 12
    if ap in ('오전', '새벽', 'am') and h == 12:
        h = 0
    if h == 24 and mi == 0:
        return '23:59'
    return f'{h:02d}:{mi:02d}' if h < 24 and mi < 60 else None


def find_dates(line, posted):
    """한 줄의 날짜들 → [(date, 'HH:MM'|None, 마감 표현이 뚜렷한가)]. 해가 없으면 올린 해 — 올린 날보다 두 달 넘게 앞이면 다음 해."""
    out = []
    for m in DATE.finditer(line):
        g = m.groupdict()
        mon = int(g['m1'] or g['m2'] or g['m3'] or MON.get((g['mn'] or '').lower()[:3], 0))
        day = int(g['d1'] or g['d2'] or g['d3'] or g['d4'])
        year = int(g['y1'] or g['y2'] or g['y4'] or posted.year)
        try:
            d = datetime(year, mon, day).date()
            if not (g['y1'] or g['y2'] or g['y4']) and d < posted - timedelta(days=60):
                d = datetime(year + 1, mon, day).date()
        except ValueError:
            continue
        end = m.end()
        tm = TIME.match(line, end)
        hm = clock(tm) if tm else None
        if tm and hm:
            end = tm.end()
        else:
            tb = TIME_BEFORE.search(line[:m.start()])
            hm = clock(tb) if tb else None
        clear = bool(TAIL.match(line, end)) or bool(LABEL.search(line[max(0, m.start() - 30):m.start()]))
        out.append((d, hm, clear))
    return out


def post_deadline(title, text, posted):
    """글 하나 → (뚜렷한 마감 (date, hm) | None, 뚜렷한 날짜 전부, 불명확한 날짜 전부). 문서 차례로 첫 뚜렷한 마감(추가 제출 줄은 뺀다)."""
    first, clears, vague = None, [], []
    for ln in [title] + (text or '').splitlines():
        if not ln.strip():
            continue
        for d, hm, clear in find_dates(ln, posted):
            if clear:
                clears.append(d)
                if first is None and not LATE.search(ln):
                    first = (d, hm)
            elif HINT.search(ln):
                vague.append(d)
    return first, clears, vague


def board_posts():
    """게시판 원시 JSON → 글 번호마다 가장 늦게 받은 판(수정된 글은 뒤 판이 이긴다). 글 목록(live)을 통째로 받은 판이 있으면 거기 없는 글은 지워진 글이다."""
    posts, live = {}, {}
    for f in sorted(glob.glob(os.path.join(LMS_DIR, 'lms-board-*.json'))):
        d = load_json(f, None)
        if not d:
            continue
        at = d.get('capturedAt', '')
        for b in d.get('boards', []):
            name = b.get('name', '')
            if b.get('skipped') or '\n' in name or len(name) > 40:
                continue
            if b.get('live_whole') and b.get('path') and at >= live.get(b['path'], ('',))[0]:
                live[b['path']] = (at, {str(x.get('id')) for x in b.get('live') or []})
            for p in b.get('posts', []):
                m = re.search(r'^(.*)/posts/(\d+)', p.get('path') or '')
                if p.get('error') or not m:
                    continue
                if m.group(2) not in posts or posts[m.group(2)]['at'] <= at:
                    posts[m.group(2)] = {'at': at, 'course': d.get('course'), 'post': p, 'board': m.group(1)}
    return {k: v for k, v in posts.items() if not (v['board'] in live and k not in live[v['board']][1])}


def announcements():
    """Canvas 공지 — 글 번호마다 가장 늦게 받은 판."""
    out = {}
    for f in sorted(glob.glob(os.path.join(LMS_DIR, 'lms-canvas-*.json'))):
        d = load_json(f, None)
        if not d:
            continue
        at = d.get('capturedAt', '')
        for c in d.get('courses', []):
            for x in c.get('announcements', []):
                if x.get('id') is not None and (x['id'] not in out or out[x['id']][0] <= at):
                    out[x['id']] = (at, c.get('id'), x)
    return out


def lecture_rows(courses, man, today):
    """LearningX 대체 강의 등(탐침 xn_probe.lectures · lms-file 이 적음) → 일정 줄. 추적하는 항목의 지나지 않은 기한만 쓴다(지난 줄·선택형은 lms-file 이 안 적거나 여기서 뺀다).
    완료·출석이면 [x]. 탐침이 낡아 완료를 못 받았어도 줄은 쓴다 — 놓치는 쪽보다 한 번 더 울리는 쪽이 싸다. 한 번 [x] 가 된 줄은 build 가 이어 받는다."""
    rows = []
    for cid, p in (man.get('xn_probe') or {}).items():
        course = courses.get(str(cid), str(cid))
        for x in p.get('lectures') or []:
            try:
                due = datetime.strptime(x['due'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).astimezone(KST)
            except (KeyError, ValueError, TypeError):
                continue
            if due.date() < today:
                continue
            name = ' '.join(str(x.get('title', '')).split())
            link = ((man.get('items') or {}).get(f'modi:{x.get("id")}') or {}).get('path')   # LearningX 항목 번호 = Canvas 모듈 항목 번호
            tail = f' {src_link(link)}' if link else ''
            chk = 'x' if x.get('done') else ' '
            rows.append((due, course, name, f'- [{chk}] {due:%Y-%m-%d} ({WD[due.weekday()]}) {due:%H:%M} {course} · {name} 마감(대체 강의){tail} ^lms-xn-{x.get("id")}'))
    return rows


def post_rows(by_id, courses, man, today):
    """게시판·공지 글 → 일정 줄. 과제 칸과 같은 날이면 그 과제의 안내글이라 뺀다 · 지난 마감은 뺀다(메일 제출은 낸 줄 몰라 영영 열린 채 남는다).
    날짜는 있는데 마감인지 불명확한 글은 PENDING 에 적는다 — notice-filter.py 단추(사용량)가 뽑으면 다음 생성 때 줄이 된다."""
    due_days = {}
    for _at, cid, _name, a in by_id.values():
        if a.get('due_at'):
            d = datetime.strptime(a['due_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).astimezone(KST).date()
            due_days.setdefault(cid, set()).add(d)
    items = []
    for pid, v in board_posts().items():
        p, cid = v['post'], v['course']
        raw = str(p.get('list_date') or '')[:10] or v['at'][:10]
        link = (((man.get('board') or {}).get(str(cid)) or {}).get(p.get('key')) or {}).get('md')
        if not link:                    # 첨부 있는 글의 본문은 첨부 옆 짝메모에 있다
            for name in p.get('attachments') or []:
                f = (man.get('files') or {}).get(f'board:{cid}:{p.get("path")}:{name}')
                if f:
                    link = os.path.splitext(f['path'])[0] + '.md'
                    break
        items.append((f'lms-post-{pid}', pid, cid, p.get('title', ''), p.get('text', ''), raw, link))
    for aid, (at, cid, x) in announcements().items():
        items.append((f'lms-ann-{aid}', f'ann{aid}', cid, x.get('title', ''), x.get('_text', ''), (x.get('posted_at') or at)[:10],
                      ((man.get('items') or {}).get(f'ann:{aid}') or {}).get('path')))
    rows, pending = [], {}
    for bid, pid, cid, title, text, raw, link in items:
        try:
            posted = datetime.strptime(raw, '%Y-%m-%d').date()
        except ValueError:
            continue
        name = ' '.join(str(title).split())
        course = courses.get(str(cid), str(cid))
        first, clears, vague = post_deadline(name, text, posted)
        tag, hm = '마감(글)', None
        if first:
            due, hm = first
            if set(clears) & due_days.get(cid, set()):
                continue
        else:
            j = load_json(os.path.join(JUDGED, f'lms-post-{pid}.json'), None)
            if j is None:
                if link and [d for d in vague if d >= today]:
                    pending[str(pid)] = {'course': course, 'title': name, 'date': raw, 'path': link}
                continue
            try:
                due = datetime.strptime(str(j.get('마감')), '%Y-%m-%d').date()
            except ValueError:
                continue
            if due in due_days.get(cid, set()):
                continue
            tag = '마감(글 · 확인 필요)'
        if due < today:
            continue
        tail = f' {src_link(link)}' if link else ''
        when = f'{due:%Y-%m-%d} ({WD[due.weekday()]})' + (f' {hm}' if hm else '')
        rows.append((datetime(due.year, due.month, due.day, *(map(int, (hm or '23:59').split(':')))).replace(tzinfo=KST), course, name,
                     f'- [ ] {when} {course} · {name} {tag}{tail} ^{bid}'))
    return rows, pending


def build():
    courses = load_json(COURSES, {})
    man = load_json(MANIFEST, {})
    items = man.get('items', {})
    by_id, sources = collect()
    if not by_id:
        print('LMS 원시 JSON 에 과제 없음 — 쓰지 않음')
        return 1

    # 기존 파일의 체크 상태(블록 id 기준) — 사람이 남긴 «- [x]» 는 다시 써도 남는다
    done, created = set(), datetime.now(KST).strftime('%Y-%m-%d')
    if os.path.exists(OUT):
        with open(OUT, encoding='utf-8') as f:
            old = f.read()
        for ln in old.splitlines():
            m = LINE.match(ln)
            if m and m.group(1) in 'xX' and m.group(6):
                done.add(m.group(6))
        m = re.search(r'^created: (\S+)', old, re.M)
        if m:
            created = m.group(1)
    else:
        old = ''

    rows, skipped = [], 0
    for aid, (_, cid, cname, a) in by_id.items():
        if not a.get('due_at') or a.get('published') is False:
            skipped += 1
            continue
        due = datetime.strptime(a['due_at'], '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc).astimezone(KST)
        course = courses.get(str(cid), cname)
        bid = f'lms-asg-{aid}'
        sub = a.get('submission') or {}  # include[]=submission 으로 받은 «내 제출»(10-26부터 수집)
        chk = 'x' if bid in done or sub.get('submitted_at') or sub.get('workflow_state') in ('submitted', 'graded') else ' '
        name = ' '.join(str(a.get('name', '')).split())
        link = items.get(f'asg:{aid}', {}).get('path')
        tail = f' {src_link(link)}' if link else ''
        line = (f'- [{chk}] {due:%Y-%m-%d} ({WD[due.weekday()]}) {due:%H:%M} '
                f'{course} · {name} 마감{tail} ^{bid}')
        rows.append((due, course, name, line))
    extra, pending = post_rows(by_id, courses, man, datetime.now(KST).date())
    rows += [(due, course, name, line.replace('- [ ]', '- [x]', 1) if line.rsplit('^', 1)[1] in done else line) for due, course, name, line in extra]
    rows += [(due, course, name, line.replace('- [ ]', '- [x]', 1) if line.rsplit('^', 1)[1] in done else line) for due, course, name, line in lecture_rows(courses, man, datetime.now(KST).date())]
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    if pending or os.path.exists(PENDING):
        with open(PENDING + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
            json.dump(pending, f, ensure_ascii=False, indent=1)
        os.replace(PENDING + '.tmp', PENDING)

    newest = max(sources)[1] if sources else '?'
    head = [
        '---',
        'type: episodic',
        'title: LMS 마감',
        f'created: {created}',
        f'updated: {datetime.now(KST):%Y-%m-%d}',
        'tags: [일정, LMS, 생성파일]',
        'links: ["[[외부뇌-일정-형식]]", "[[내-일정]]"]',
        'status: active',
        'source: claude',
        '---',
        '# LMS 마감 (생성 파일)',
        '',
        '> `3_시스템/schedule.py build` 가 LMS 원시 JSON 에서 통째로 다시 쓴다. **체크(`- [x]`)만 남고 다른 손질은 사라진다** — 고칠 것·더할 것은 [[내-일정]]에. 형식 → [[외부뇌-일정-형식]]',
        f'> 원천 = `1_수집/_lms/lms-canvas-*.json` {len(sources)}개(최신 `{newest}`) · 시각 = 한국 시각(원천 UTC → +9) · 제출한 과제는 `[x]`(10-26 이후 수집분부터 `include[]=submission`) · `마감(글)` = 과제 칸에 없고 게시판·공지 글에만 있는 마감(결정적 추출 · 지난 줄은 뺀다).',
    ]
    body, month = [], None
    for due, _, _, line in rows:
        ym = f'{due:%Y-%m}'
        if ym != month:
            body += ['', f'## {ym}']
            month = ym
        body.append(line)
    text = '\n'.join(head + body) + '\n'

    def strip_updated(s):
        return re.sub(r'^updated: .*$', '', s, count=1, flags=re.M)

    if old and strip_updated(old) == strip_updated(text):
        print(f'바뀐 것 없음 — 과제 {len(rows)} · 체크 {len(done)} · 마감 없음 {skipped}')
        return 0
    os.makedirs(SCHED_DIR, exist_ok=True)
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, OUT)
    print(f'씀 {os.path.relpath(OUT, VAULT)} — 과제 {len(rows)} · 체크 보존 {len(done)} · 마감 없음 {skipped}')
    return 0


def write_generated(name, title, src, lines):
    """생성 파일 하나를 쓴다(수집 출처마다 파일 하나 · 형식 §1) — 체크는 블록 id 로 이어 받고, 내용이 같으면 안 쓴다."""
    path = os.path.join(SCHED_DIR, name)
    today = datetime.now(KST).strftime('%Y-%m-%d')
    done, created, old = set(), today, ''
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            old = f.read()
        for ln in old.splitlines():
            m = LINE.match(ln)
            if m and m.group(1) in 'xX' and m.group(6):
                done.add(m.group(6))
        m = re.search(r'^created: (\S+)', old, re.M)
        created = m.group(1) if m else today
    body, month = [], None
    for ln in lines:
        m = LINE.match(ln)
        if not m:
            raise ValueError(f'일정 줄 형식 아님: {ln}')
        if m.group(2)[:7] != month:
            month = m.group(2)[:7]
            body += ['', f'## {month}']
        body.append(ln.replace('- [ ]', '- [x]', 1) if m.group(6) in done else ln)
    head = ['---', 'type: episodic', f'title: {title}', f'created: {created}', f'updated: {today}', f'tags: [일정, {title}, 생성파일]',
            'links: ["[[외부뇌-일정-형식]]", "[[내-일정]]"]', 'status: active', 'source: claude', '---', f'# {title} (생성 파일)', '',
            f'> `3_시스템/web-collect.py` 가 [출처]({src})에서 통째로 다시 쓴다. **체크(`- [x]`)만 남고 다른 손질은 사라진다** — 고칠 것·더할 것은 [[내-일정]]에.']
    text = '\n'.join(head + body) + '\n'
    strip = lambda s: re.sub(r'^updated: .*$', '', s, count=1, flags=re.M)
    if old and strip(old) == strip(text):
        return f'바뀐 것 없음 — {name} {len(lines)}줄'
    os.makedirs(SCHED_DIR, exist_ok=True)
    with open(path + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(path + '.tmp', path)
    return f'씀 {name} {len(lines)}줄 · 체크 보존 {len(done)}'


def parse_all():
    """일정 파일 전부의 줄을 (파일, 줄번호, 원문, match|None) 로."""
    out = []
    for f in sorted(glob.glob(os.path.join(SCHED_DIR, '*.md'))):
        with open(f, encoding='utf-8') as fh:
            for i, ln in enumerate(fh.read().splitlines(), 1):
                if TASK.match(ln):
                    out.append((f, i, ln, LINE.match(ln)))
    return out


def check():
    bad = 0
    for f, i, ln, m in parse_all():
        err = None
        if not m:
            err = '형식 아님'
        else:
            try:
                datetime.strptime(m.group(2), '%Y-%m-%d')
                for t in (m.group(3), m.group(4)):
                    if t:
                        datetime.strptime(t, '%H:%M')
            except ValueError:
                err = '없는 날짜·시각'
        if err:
            bad += 1
            print(f'{os.path.basename(f)}:{i} {err}: {ln.strip()[:120]}')
    print(f'형식 오류 {bad}')
    return 1 if bad else 0


def clean(text):
    text = re.sub(r'\[\[[^\]]*\|원본\]\]|\[원본\]\([^)]*\)', '', text)
    text = re.sub(r'\[\[[^\]|]*\|([^\]]*)\]\]', r'\1', text)
    text = re.sub(r'\[\[([^\]]*)\]\]', r'\1', text)
    return ' '.join(text.split())


def week(days=7):
    """session-start.ps1 1.6절과 같은 출력(묶기 3건 이상 · 최대 8줄 · 없으면 «다음:»)."""
    today = datetime.now(KST).date()
    end = today + timedelta(days=days)
    rows = []
    for _, _, _, m in parse_all():
        if not m or m.group(1) != ' ':
            continue
        try:
            d = datetime.strptime(m.group(2), '%Y-%m-%d').date()
        except ValueError:
            continue
        if d >= today:
            t = m.group(3).zfill(5) + (f'~{m.group(4)}' if m.group(4) else '') if m.group(3) else ''
            rows.append((d, t, clean(m.group(5))))
    rows.sort()

    def fmt(d, t):
        return f'- {d:%m-%d} ({WD[d.weekday()]})' + (f' {t}' if t else '') + ' '

    near = [r for r in rows if r[0] <= end]
    out, groups = [], {}
    for d, t, txt in near:
        groups.setdefault((d, t, txt.split(' · ', 1)[0]), []).append(txt)
    for (d, t, _), txts in groups.items():
        if len(txts) >= 3:
            out.append(fmt(d, t) + f'{txts[0]} 외 {len(txts) - 1}건')
        else:
            out += [fmt(d, t) + x for x in txts]
    if out:
        print('\n'.join(out[:8]))
    elif rows:
        print('7일 안 없음 · 다음: ' + (fmt(rows[0][0], rows[0][1]) + rows[0][2])[2:])
    else:
        print('(열린 일정 없음)')
    return 0


if __name__ == '__main__':
    if os.environ.get('SCHEDULE_DIR'):  # 시험용 — 일정 폴더만 바꿔 읽는다(build 는 쓰지 않음)
        SCHED_DIR = os.environ['SCHEDULE_DIR']
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'build'
    if cmd == 'build':
        sys.exit(build())
    if cmd == 'check':
        sys.exit(check())
    if cmd == 'week':
        sys.exit(week(int(sys.argv[2]) if len(sys.argv) > 2 else 7))
    print(__doc__)
    sys.exit(2)
