"""일정 생성기 — LMS 원시 JSON(과제 due_at) -> 2_지식/일정/LMS-마감.md.

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
    """모든 canvas 원시 JSON 에서 과제를 모은다. 같은 과제는 늦게 수집한 쪽이 이긴다."""
    by_id = {}
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
            for a in c.get('assignments', []):
                aid = a.get('id')
                if aid is None:
                    continue
                prev = by_id.get(aid)
                if prev and prev[0] > at:
                    continue
                by_id[aid] = (at, cid, cname, a)
    return by_id, sources


def build():
    courses = load_json(COURSES, {})
    items = load_json(MANIFEST, {}).get('items', {})
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
    rows.sort(key=lambda r: (r[0], r[1], r[2]))

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
        f'> 원천 = `1_수집/_lms/lms-canvas-*.json` {len(sources)}개(최신 `{newest}`) · 시각 = 한국 시각(원천 UTC → +9) · 제출한 과제는 `[x]`(10-26 이후 수집분부터 `include[]=submission`).',
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
