"""범용 수집 엔진 — 수집 계약을 맺은 공개 웹 출처를 결정적으로 다시 받는다(LLM 0 · GET 만). 큰 그림 3·8단계.

흐름(큰 그림 §10): 수집 계약(출처마다 사용자 승인 1회) → 탐색 1회(Claude) → 조리법 = 3_시스템/collect/<id>.json
→ 결정적 재생(이 파일) → 검증기 → 실패는 수집 대기열(3_시스템/_index/수집-대기열.md) → Claude 보수(구조 변경만).
범용: 출처마다 다른 것은 **조리법 데이터**(주소·쪽·정규식), 같은 것은 **엔진**(받기·저장·첨부·검사·색인·검증). 엔진에 사이트 전용 코드를 두지 않는다.
  가족 regex — 목록(줄 나누기 + 칸별 정규식)·글(제목·본문·메타·첨부 정규식)을 조리법에 적는다. HTML 게시판 대부분.
  가족 rss   — RSS 2.0·Atom 피드 주소만. 본문은 피드 것 또는 view 정규식으로 글을 받아서.
  가족 calendar — 일정표 한 쪽(달·날짜·글자 정규식) → 일정 파일 하나(2_지식/일정/). 글을 받지 않는다.
  가족 listing  — 목록 카드(칸별 정규식 · keep·skip 로 고르기) → 일정 파일 하나. 글을 받지 않는다.
층: L0 원시 응답 = 1_수집/.web/<id>/<글번호>.html(점 폴더 = 색인·옵시디언 제외 · git 제외)
    L1 원본 = 조리법 folder 의 md(보이는 글자 그대로 · 시각·작성자도 출처 값 그대로) + 첨부 = 같은 이름 폴더(<글 md 이름>/)
    L2 색인 = ingest(첨부·그림 글자 · OCR) · L3 지식 = 수요가 있을 때.
받기만: 네트워크 함수는 GET 하나뿐이다(요청 본문을 보내는 길 자체가 없다). 첨부는 격리 → lms-intake 검사 → 통과만 들인다.

  py -3 3_시스템/web-collect.py                        # 모든 조리법(20시간 안에 돌았으면 건너뜀)
  py -3 3_시스템/web-collect.py --force                # 시간 무시
  py -3 3_시스템/web-collect.py --source <id> --dry    # 무엇을 받을지만(아무것도 안 씀)
  py -3 3_시스템/web-collect.py --source <id> --check  # 조리법 검증: 받은 글 몇 편을 다시 읽어 제목·날짜가 그대로 나오는지
  py -3 3_시스템/web-collect.py --source <id> --backfill  # 이미 받은 글의 첨부·그림만 받기
  py -3 3_시스템/web-collect.py --settle               # 거르는 출처: 판정이 난 대기 글을 볼트로 들이거나 장부로(notice-filter extract 가 끝에 부른다)
  py -3 3_시스템/web-collect.py --archive [--dry]      # 거르는 출처: 지금 엔진이면 들이지 않았을 볼트 글 → 보관 칸(지우지 않음)
  py -3 3_시스템/web-collect.py --restore [--id <글번호>] # 보관 칸 → 볼트 되돌리기
  py -3 3_시스템/web-collect.py --expire [--dry]       # 보존 일정표 «웹공지»: 마감 + 날이 지난 볼트 글 → 휴지통(보통 실행 때도 함께 돈다)
  py -3 3_시스템/web-collect.py --probe <주소>          # 수집 추가 탐색(11-06): 한 쪽 원시 → _index/collect/draft/probe/ · 피드 찾기·robots 요약 JSON
  py -3 3_시스템/web-collect.py --preview <조리법.json> [--view]  # 미리보기(저장 없음): 목록 1쪽 + 관문 결과 JSON(초안이면 <id>.tried.json 표시)
  py -3 3_시스템/web-collect.py --lint <조리법.json>    # 꼴 검사만(망 요청 0) + 미리보기 결과 지문 — 확정이 «결과에 안 닿는 칸만 바뀌었나»를 본다
    탐색·미리보기는 같은 사이트를 1분 안에 다시 받지 않는다(남은 만큼 기다림 · draft/hits.json · COLLECT_SITE_GAP 초 · 11-06 끝까지 시험).
낱말 관문(11-06): 조리법 words.keep·words.skip(정규식 조각 | · 대소문자 무시) — 판정 층(filter)이 없는 출처도 제목만으로 고른다(걸리면 장부 한 줄 · 살리기 가능).
수정된 글(11-06): 목록 줄의 제목·게시일이 지난번(상태 row_title·row_date)과 다르면 그 글만 다시 받는다(요청 +1/건 · 한 번에 MAX_CHANGED 넘게 바뀌면 화면 변화로 보고 안 받음).
    원본 불변 — 볼트에 든 글은 새 파일 «<날짜> <제목> (개정N).md»(옛 md 는 그대로) · 대기 칸 글은 옛 판을 _index/collect/rev 로 옮기고 새 판을 둠 · L0 는 <글번호>.rev<N>.html.
    본문·제목·게시일이 그대로면 아무것도 안 씀. 추출 캐시는 지우지 않고 reextract 표시만(다시 뽑을 때까지 옛 일정 줄이 유지된다 — 지우면 켜짐이 아닐 때 일정이 사라진다). 본문만 고친 글은 목록에 안 보여 못 잡는다(공백).
자동 추출: 수집 전체 스위치 «자동 판정»(collect.local.json auto_judge · 없으면 끔 · 11-06 사용자)이 켜졌을 때만 — 켜지면 조리법 filter.auto 가 없는 출처도 켜진 것으로 치고
    filter.auto: false 인 출처만 뺀다(스위치가 꺼져 있으면 조리법 true 여도 안 함) · auto_max(기본 10) · 구독 아님·사용량 경고면 멈춤. 대기 칸 비해당 기한 = filter.keep_days(기본 90).
수집 계약: 조리법 `contract` 가 비어 있으면 돌지 않는다(계약 없는 수집을 구조로 막는다 · 10-29).
저장 전 거르기(10-29 · 수집은 선별): 조리법에 `filter` 가 있으면 ①글을 받기 전 제목 관문(notice-filter gate · LLM 0) ②받은 글은
    대기 칸(_index/collect/stage — 볼트 지식층 밖 · git 제외)에 ③판정이 나면 settle: 남길 것(해당·확인 필요·관심)만 L0·L1·첨부·색인으로
    볼트에 들이고, 비해당은 대기 칸에 둔 채 장부 한 줄, 지남은 지운다. 첨부는 들일 때 받는다(추출은 본문 먼저 — 토큰).
"""
import argparse
import datetime
import email.utils
import glob
import hashlib
import html
import html.parser
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SYS = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(SYS)
sys.path.insert(0, SYS)
import fileops  # noqa: E402 — 볼트에 들이는 첨부는 장부에(볼트 개혁 R6.3 · by script:web-collect)
import roles  # noqa: E402 — 조리법의 넣을 자리 «@역할/하위»(볼트 개혁 R9)
RECIPES = os.path.join(SYS, 'collect')
STATE_DIR = os.path.join(SYS, '_index', 'collect')
QUEUE = os.path.join(SYS, '_index', '수집-대기열.md')
LOG = os.path.join(STATE_DIR, 'web.log')
RAW = os.path.join(VAULT, '1_수집', '.web')
STAGE = os.path.join(STATE_DIR, 'stage')     # 거르는 출처의 대기 칸 — <id>/<글번호>.{md,html,body.html}
REV = os.path.join(STATE_DIR, 'rev')         # 수정되기 전 대기 칸 판 — <id>/<글번호>.<돌림>.{md,html,body.html}(지우지 않음)
MAX_CHANGED = 20    # 한 번에 이만큼 넘게 목록 줄이 바뀌면 글 수정이 아니라 화면 구조 변화로 본다
ARCH = os.path.join(STATE_DIR, 'archive')    # 보관 칸 — 볼트에 들였다가 빼낸 글(볼트와 같은 상대 경로 · 첨부·색인째 · 자동으로 지우지 않음)
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36 BrainCollector/0.2'
GAP = 1.0           # 요청 사이 최소 간격(초) — 상대 서버에 부담 주지 않게
_last = [0.0]
ATT_EXT = {'.pdf', '.hwp', '.hwpx', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.jpg', '.jpeg', '.png', '.gif', '.zip', '.txt'}
CT_EXT = {'image/jpeg': '.jpg', 'image/png': '.png', 'image/gif': '.gif', 'application/pdf': '.pdf'}


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def log(msg):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOG, 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'{now()} {msg}\n')
    print(msg)


def queue(src, what, who='Claude'):
    new = not os.path.exists(QUEUE)
    os.makedirs(os.path.dirname(QUEUE), exist_ok=True)
    if not new:                 # 열린 같은 줄이 있으면 또 쓰지 않는다 — lms-auto 가 15분마다 부른다
        with open(QUEUE, encoding='utf-8') as f:
            if any(ln.startswith('- [ ] ') and ln.endswith(f'`{src}` ({who}) {what}') for ln in f.read().splitlines()):
                return
    with open(QUEUE, 'a', encoding='utf-8', newline='\n') as f:
        if new:
            f.write('# 수집 대기열\n> lms-auto.py·web-collect.py 가 쌓는다. 고치면 줄 앞을 `- [x]` 로.\n\n')
        f.write(f'- [ ] {now()} `{src}` ({who}) {what}\n')
    log(f'대기열 {src}: {what}')


# ───────── 네트워크: GET 하나뿐 ─────────
def _open(url):
    wait = GAP - (time.time() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ko'}, method='GET')
    _last[0] = time.time()
    return urllib.request.urlopen(req, timeout=30)


def get(url):
    with _open(url) as r:
        raw = r.read()
        cs = r.headers.get_content_charset() or 'utf-8'
    _last[0] = time.time()
    return raw.decode(cs, 'replace')


def get_bytes(url, max_bytes):
    """첨부용 — (바이트, Content-Type, Content-Disposition). 상한을 넘으면 ValueError."""
    with _open(url) as r:
        data = r.read(max_bytes + 1)
        ct = (r.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        cd = r.headers.get('Content-Disposition') or ''
    _last[0] = time.time()
    if len(data) > max_bytes:
        raise ValueError(f'{max_bytes // 2**20}MB 넘음')
    return data, ct, cd


# ───────── HTML → 보이는 글자(표준 라이브러리만) ─────────
BLOCK = {'p', 'div', 'li', 'ul', 'ol', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'tr', 'table', 'blockquote', 'pre', 'section', 'article'}


class Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.skip, self.imgs, self.links, self._a = [], 0, [], [], None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script', 'style'):
            self.skip += 1
        elif tag == 'br':
            self.out.append('\n')
        elif tag in BLOCK:
            self.out.append('\n')
        elif tag in ('td', 'th'):
            self.out.append('\t')
        elif tag == 'img' and a.get('src'):
            self.imgs.append((a.get('alt') or '', a['src']))
        elif tag == 'a' and a.get('href'):
            self._a = [a['href'], '']

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK:
            self.out.append('\n')
        elif tag == 'a' and self._a:
            self.links.append((self._a[1].strip(), self._a[0]))
            self._a = None

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)
            if self._a:
                self._a[1] += d

    def text(self):
        s = ''.join(self.out).replace('\xa0', ' ')
        s = re.sub(r'[ \t]+\n', '\n', s)
        return re.sub(r'\n{3,}', '\n\n', s).strip()


def to_text(fragment):
    p = Text()
    p.feed(fragment or '')
    p.close()
    return p


def strip_tags(s):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', s or '')).split())


def rx(pattern, s, default=''):
    m = re.search(pattern, s or '', re.S) if pattern else None
    return m.group(1) if m else default


# ───────── 가족 regex — 조리법 데이터만으로 ─────────
def regex_list(rc, page):
    L = rc['list']
    rows = []
    for row in re.findall(L.get('row', r'<tr[^>]*>(.*?)</tr>'), page, re.S):
        it = {k: (rx(p, row).strip() if k == 'id' else strip_tags(rx(p, row))) for k, p in L['fields'].items()}
        if it.get('id'):
            if L.get('url'):            # 글 주소를 줄에서 바로 뽑는 출처(href) — 상대 주소는 목록 주소 기준
                it['url'] = urllib.parse.urljoin(rc['list']['page_url'].format(page=1), html.unescape(rx(L['url'], row)))
            rows.append(it)
    return rows


def regex_view(rc, page, url):
    V = rc['view']
    blk = rx(V['block'], page, page) if V.get('block') else page
    meta = {k: strip_tags(rx(p, blk)) for k, p in (V.get('meta') or {}).items()}
    atts = []
    A = V.get('attachments')
    if A:
        ablk = rx(A['block'], blk) if A.get('block') else blk
        for m in re.finditer(A['item'], ablk, re.S):
            atts.append((strip_tags(m.group('name')), urllib.parse.urljoin(url, html.unescape(m.group('url')))))
    return {'title': strip_tags(rx(V['title'], blk)), 'meta': {k: v for k, v in meta.items() if v},
            'body_html': rx(V['body'], blk), 'attachments': atts}


# ───────── 가족 rss — RSS 2.0 · Atom ─────────
ATOM = '{http://www.w3.org/2005/Atom}'


def iso(s):
    """출처 날짜 꼴(2026.10.19) → 파일 이름·상태용 ISO. 글 머리의 등록일자는 출처 값 그대로 둔다."""
    return re.sub(r'^(\d{4})\.(\d{2})\.(\d{2})$', r'\1-\2-\3', (s or '').strip())


def _date(s):
    s = (s or '').strip()
    if re.match(r'\d{4}-\d{2}-\d{2}', s):
        return s[:10]
    try:
        return email.utils.parsedate_to_datetime(s).strftime('%Y-%m-%d')
    except (TypeError, ValueError):
        return ''


def rss_list(rc, page):
    root = ET.fromstring(page.encode('utf-8') if isinstance(page, str) else page)
    rows = []
    for it in root.iter():
        tag = it.tag.split('}')[-1]
        if tag not in ('item', 'entry'):
            continue
        t = lambda name: (it.findtext(name) or it.findtext(ATOM + name) or '').strip()
        link = t('link')
        if not link:
            le = it.find(ATOM + 'link')
            link = le.get('href', '') if le is not None else ''
        guid = t('guid') or t('id') or link
        body = (it.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or t('description') or t('content') or t('summary')
                or (it.findtext('.//{http://search.yahoo.com/mrss/}description') or '').strip())     # Media RSS(유튜브 채널 피드 등) — 본문이 media:group 안에만 있다
        encl = [(os.path.basename(urllib.parse.urlparse(e.get('url', '')).path) or 'enclosure', e.get('url', ''))
                for e in it.findall('enclosure') if e.get('url')]
        rows.append({'id': hashlib.sha1(guid.encode('utf-8')).hexdigest()[:16], 'title': strip_tags(t('title')),
                     'date': _date(t('pubDate') or t('published') or t('updated') or t('date')), 'url': link,
                     '_body': body, '_att': encl})
    return rows


def rss_view(rc, page, url):
    return regex_view(rc, page, url) if rc.get('view') else None


FAMILIES = {'regex': (regex_list, regex_view), 'rss': (rss_list, rss_view)}


# ───────── 가족 calendar — 일정표 한 쪽 → 일정 파일(글을 받지 않는다 · 조리법 calendar 칸이 정규식) ─────────
WD = '월화수목금토일'


def calendar_rows(rc, page):
    """[(시작, 끝|None, 글자)] — 표의 달 칸은 여러 줄을 묶으니 앞 값을 잇고, 달이 줄면 다음 해다(2학기 표의 1·2월).
    출처가 준 요일과 계산한 요일이 어긋나면 ValueError — 연도·구조가 바뀐 것이라 틀린 날짜를 쓰지 않는다."""
    C = rc['calendar']
    year = int(rx(C['year'], page))
    blk = rx(C['block'], page) if C.get('block') else page
    out, month = [], None

    def day(y, m, d, wd):
        v = datetime.date(y, m, d)
        if WD[v.weekday()] != wd:
            raise ValueError(f'요일 어긋남: {y}-{m}-{d} 는 {WD[v.weekday()]}요일인데 표는 {wd}')
        return v

    for row in re.findall(C['row'], blk, re.S):
        m = rx(C['month'], row)
        if m:
            year += 1 if month and int(m) < month else 0
            month = int(m)
        when, what = strip_tags(rx(C['when'], row)), strip_tags(rx(C['what'], row))
        if not when or not what:
            continue
        w = re.fullmatch(r'(\d{1,2})\((\S)\)(?:\s*~\s*(?:(\d{1,2})월\s*)?(\d{1,2})\((\S)\))?', when)
        if not w or not month:
            raise ValueError(f'날짜 꼴 모름: {when!r}')
        a = day(year, month, int(w[1]), w[2])
        b = None
        if w[4]:
            m2 = int(w[3]) if w[3] else (month if int(w[4]) >= int(w[1]) else month % 12 + 1)   # 끝 날이 시작보다 작으면 다음 달
            b = day(year + (1 if m2 < month else 0), m2, int(w[4]), w[5])
        out.append((a, b, what))
    return out


def calendar_lines(rc, rows):
    """일정 줄(형식 = 외부뇌-일정-형식). 기간은 시작·끝 두 줄 — 줄 문법을 바꾸지 않고 세 구현(schedule·세션 시작·캘린더)이 그대로 읽는다."""
    C = rc['calendar']
    skip = re.compile(C['skip']) if C.get('skip') else None
    fmt = lambda d: f'{d:%Y-%m-%d} ({WD[d.weekday()]})'
    src = f' [원본]({rc["page"]})'
    today = datetime.date.today()
    out = []
    for a, b, what in rows:
        if skip and skip.search(what):
            continue
        bid = 'cal-' + hashlib.sha1(f'{rc["id"]}|{a:%Y-%m}|{what}'.encode('utf-8')).hexdigest()[:10]
        label = C.get('label', rc['name'])
        if b:
            out.append((a, f'- [ ] {fmt(a)} {label} · {what} 시작(~{b:%m-%d} ({WD[b.weekday()]})){src} ^{bid}-s'))
            out.append((b, f'- [ ] {fmt(b)} {label} · {what} 끝{src} ^{bid}-e'))
        else:
            out.append((a, f'- [ ] {fmt(a)} {label} · {what}{src} ^{bid}'))
    out = sorted((x for x in out if x[0] >= today), key=lambda x: x[0])     # 지난 줄은 빼서 «안 한 일»로 남지 않게 — 표 전체는 L0 에
    return [ln for _, ln in out]


def run_calendar(rc, run, dry):
    sp, st = load_state(rc)
    page = get(rc['page'])
    rows = calendar_rows(rc, page)          # 어긋나면 ValueError → main 이 대기열로
    if not rows:
        queue(rc['id'], f'검증: 일정표 0줄(지난번 {st.get("page1_rows")}줄) — 화면 구조 변화 의심')
        return 0
    lines = calendar_lines(rc, rows)
    log(f'{rc["id"]}: 표 {len(rows)}줄 → 일정 {len(lines)}줄')
    if dry:
        for ln in lines:
            print('  ', ln)
        return 0
    h = hashlib.sha1(page.encode('utf-8')).hexdigest()[:16]
    if st.get('hash') != h:
        keep_raw(rc, time.strftime('%Y%m%d'), page)     # L0 — 표가 바뀐 날만
    import schedule                                     # 일정 파일 쓰기(체크 보존 · 내용 같으면 안 씀)는 생성기들 공통
    print(schedule.write_generated(rc['calendar']['output'], rc['name'], rc['page'], lines))
    st.update(hash=h, page1_rows=len(rows), last_run=time.time())
    save_state(sp, st)
    return 0


# ───────── L1 원본 md ─────────
def safe(s, n=120):
    s = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', s or '').strip(' .')
    return s[:n] or '제목없음'


def y(v):
    return json.dumps(v, ensure_ascii=False)


def write_new(path, text):
    b, e = os.path.splitext(path)
    k = 2
    while os.path.exists(path):
        path = f'{b} ({k}){e}'
        k += 1
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    return path


def render(rc, run, url, row, v):
    p = to_text(v['body_html'])
    lst = {k: row[k] for k in row if not k.startswith('_') and k not in ('url',)}
    front = {'created': time.strftime('%Y-%m-%d'), 'source': '수집', '출처': rc['name'],  # source = user|claude|수집(10-30) · 어디서 = 출처 칸 '출처_id': rc['id'], 'url': url,
             '목록': lst, **v['meta'], '수집': run}
    lines = ['---'] + [f'{k}: {y(val)}' for k, val in front.items() if val not in (None, '', {}, [])] + ['---', f'# {v["title"] or row.get("title", "")}', '', p.text()]
    if v['attachments']:
        lines += ['', '## 첨부', *[f'- {n} — {u}' for n, u in v['attachments']]]
    if p.imgs:
        lines += ['', '## 그림', *[f'- {a or "(설명 없음)"} — {s}' for a, s in p.imgs]]
    if p.links:
        lines += ['', '## 원문 링크', *[f'- {t} — {h}' for t, h in p.links]]
    return '\n'.join(lines).rstrip() + '\n'


# ───────── 첨부·본문 그림 — 엔진 단계(모든 가족 공통) ─────────
_intake = []


def intake():
    if not _intake:
        spec = importlib.util.spec_from_file_location('lms_intake', os.path.join(SYS, 'lms-intake.py'))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _intake.append(m)
    return _intake[0]


_hashes = []


def vault_hashes():
    if not _hashes:
        _hashes.append(intake().vault_hashes())
    return _hashes[0]


def att_name(name, ct, cd, url, k):
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.I) or re.search(r'filename="?([^";]+)', cd, re.I)
    cand = name or (urllib.parse.unquote(m.group(1)) if m else '') or os.path.basename(urllib.parse.urlparse(url).path)
    cand = safe(html.unescape(cand), 150)
    if not os.path.splitext(cand)[1] and ct in CT_EXT:
        cand += CT_EXT[ct]
    return cand or f'첨부{k}'


def take_attachments(rc, run, post_md, v):
    """첨부(+ 조리법이 켜면 본문 그림)를 받아 격리 → 검사 → <글 md 이름>/ 폴더로. 결과 목록을 돌려준다."""
    A = rc.get('attachments') or {}
    if not A.get('download'):
        return []
    max_b = int(A.get('max_mb', 20)) * 2**20
    exts = {e.lower() for e in A.get('ext', [])} or ATT_EXT
    items = list(v['attachments'])
    if A.get('images'):
        items += [(alt, src) for alt, src in to_text(v['body_html']).imgs if src.startswith('http')]
    dest = os.path.splitext(post_md)[0]
    q = os.path.join(tempfile.gettempdir(), 'web-quarantine', run)
    os.makedirs(q, exist_ok=True)
    out = []
    for k, (name, url) in enumerate(items, 1):
        rec = {'name': name, 'url': url}
        try:
            data, ct, cd = get_bytes(url, max_b)
        except Exception as e:
            rec['error'] = repr(e)[:120]
            out.append(rec)
            continue
        fn = att_name(name, ct, cd, url, k)
        ext = os.path.splitext(fn)[1].lower()
        rec['file'] = fn
        # 파일 대신 HTML 이 오면 권한 안내·만료 페이지다(10-27 고려대 포털 «Access is denied» 10건) — 격리가 아니라 «권한 없음»
        if ext not in ('.html', '.htm', '.txt') and (ct == 'text/html' or re.match(rb'\s*(<!doctype|<html|<link|<script|<meta)', data[:200], re.I)):
            rec['denied'] = 'HTML 응답(로그인 필요·권한 없음 의심)'
            out.append(rec)
            continue
        if ext not in exts:
            rec['skip'] = f'형식 {ext or "없음"}'
            out.append(rec)
            continue
        qp = os.path.join(q, f'{k}-{fn}')
        with open(qp, 'wb') as f:
            f.write(data)
        it = intake()
        problems = []
        if ext in it.EXEC_EXT:
            problems.append('실행 파일')
        if ext in it.MAGIC and not any(data.startswith(m) for m in it.MAGIC[ext]):
            problems.append('형식 불일치')
        if ext == '.pdf' and it.pdf_risks(data).get('risky'):
            problems.append('PDF 위험 요소')
        if data.startswith(b'PK\x03\x04'):
            z = it.zip_risks(qp)
            if z.get('exec') or z.get('traversal') or z.get('bad_zip') or z.get('macro'):
                problems.append('압축·매크로 위험')
        dv = it.defender(qp)
        if dv == 'THREAT':
            problems.append('Defender 위협')
        sha = it.sha256(qp)
        rec['sha'] = sha[:16]
        if problems:
            rec['quarantined'] = problems
            queue(rc['id'], f'첨부 격리 {fn} — {problems} ({qp})', '사용자·Claude')
            out.append(rec)
            continue
        if sha in vault_hashes():
            rec['dup'] = vault_hashes()[sha]
            os.remove(qp)
            out.append(rec)
            continue
        os.makedirs(dest, exist_ok=True)
        target = os.path.join(dest, fn)
        b, e = os.path.splitext(target)
        n = 2
        while os.path.exists(target):
            target = f'{b} ({n}){e}'
            n += 1
        fileops.intake(qp, target, "웹 수집 첨부 " + rc['id'], "script:web-collect")
        vault_hashes()[sha] = os.path.relpath(target, VAULT)
        rec['path'] = os.path.relpath(target, VAULT)
        out.append(rec)
    return out


def ingest(folders):
    """L2 색인 — ingest.py 의 정식 실행은 `py -3`(pypdfium2·olefile 있음). 3.11 로 돌리면 PDF·hwp 색인이 «추출 실패»로
    써진다(incident-2026-10-25 · 10-27 같은 실수 재발)."""
    folders = sorted({f for f in folders if os.path.isdir(f)})
    if not folders:
        return
    py = ['py', '-3'] if shutil.which('py') else [sys.executable]
    p = subprocess.run(py + [os.path.join(SYS, 'ingest.py'), *folders], cwd=VAULT, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    tail = ' '.join((p.stdout or '').split())[-200:]
    log(f'ingest rc={p.returncode} {tail}')
    if p.returncode:
        queue('ingest', f'ingest.py 실패 rc={p.returncode} · {(p.stderr or "")[-200:]}')


# ───────── 저장 전 거르기 — 거르는 출처(조리법 filter)만 ─────────
_nf = []


def filt():
    """판정 층 notice-filter.py — 부르는 방향은 엔진 → 필터 하나뿐(필터는 settle 을 실행만 시킨다)."""
    if not _nf:
        spec = importlib.util.spec_from_file_location('notice_filter', os.path.join(SYS, 'notice-filter.py'))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _nf.append(m)
    return _nf[0]


def keep_raw(rc, aid, raw, rev=1):
    """L0 원시 — 개정(rev > 1)은 <글번호>.rev<N>.html 로 옆에 둔다(옛 판을 덮어쓰지 않는다)."""
    if raw:
        os.makedirs(os.path.join(RAW, rc['id']), exist_ok=True)
        with open(os.path.join(RAW, rc['id'], aid + (f'.rev{rev}' if rev > 1 else '') + '.html'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(raw)


def stage_paths(rc, aid):
    return {k: os.path.join(STAGE, rc['id'], f'{aid}.{k}') for k in ('md', 'html', 'body.html')}


def stage_put(rc, aid, raw, v, text):
    os.makedirs(os.path.join(STAGE, rc['id']), exist_ok=True)
    for k, s in zip(('md', 'html', 'body.html'), (text, raw, v['body_html'])):
        with open(stage_paths(rc, aid)[k], 'w', encoding='utf-8', newline='\n') as f:
            f.write(s or '')


def age_days(run):
    try:
        return (time.time() - time.mktime(time.strptime((run or '')[:8], '%Y%m%d'))) / 86400
    except ValueError:
        return 0


def arch_paths(rc, aid, rel_md):
    """볼트에 든 글 하나가 차지한 자리(볼트 상대 경로) — 글 md · 첨부 폴더 · 첨부 색인 폴더 · L0 원시."""
    stem = os.path.splitext(rel_md)[0]
    return [rel_md, stem, os.path.join('1_수집', '_색인', os.path.relpath(stem, '1_수집')), os.path.join('1_수집', '.web', rc['id'], aid + '.html')]


def move_all(pairs):
    """[(출발, 도착)] 중 있는 것을 옮긴다. 도착지에 하나라도 이미 있으면 아무것도 옮기지 않고 False(덮어쓰기 금지)."""
    todo = [(a, b) for a, b in pairs if os.path.exists(a)]
    if any(os.path.exists(b) for _, b in todo):
        return False
    for a, b in todo:
        os.makedirs(os.path.dirname(b), exist_ok=True)
        shutil.move(a, b)
    return True


def archive(rc, run, dry=False):
    """볼트에 든 글 중 «지금 엔진이었다면 들이지 않았을 것»(판정 비해당 · 받기 전에 이미 마감이 지난 것)을 보관 칸으로 옮긴다.
    받은 뒤에 마감이 지난 남길 것은 볼트에 둔다. 지우지 않는다 — 첨부는 git 밖이라 지우면 되살릴 수 없다. 되돌리기 = --restore."""
    nf = filt()
    sp, st = load_state(rc)
    j = nf.judged(rc['id'])
    marks = nf.load_marks()
    n = 0
    for aid, it in st['items'].items():
        if not it.get('path') or aid not in j or marks.get(f'{rc["id"]}:{aid}', {}).get('평가') == '쓸모':     # 쓸모 = 사용자가 남기라고 한 글
            continue
        v, why, dl = j[aid]
        r = it.get('run') or ''
        late = bool(dl and len(r) >= 8 and dl < f'{r[:4]}-{r[4:6]}-{r[6:8]}')
        if v in nf.KEEP and not late:
            continue
        if dry:
            print(f'  보관 칸으로: {v}{" · 받기 전 마감 " + dl if late else ""} · {it["title"][:50]}')
        elif move_all([(os.path.join(VAULT, x), os.path.join(ARCH, x)) for x in arch_paths(rc, aid, it['path'])]):
            it['archived'] = it.pop('path')
            it['verdict'], it['why'] = ('지남', f'받기 전 마감 {dl}') if late else (v, why)
            it['archived_run'] = run
        else:
            queue(rc['id'], f'보관 칸에 같은 이름이 있어 옮기지 않음 {it["path"]}')
            continue
        n += 1
    if not dry:
        save_state(sp, st)
    log(f'{rc["id"]}: 보관 칸으로 {"옮길 것" if dry else "옮김"} {n}')
    return n


def restore_item(rc, aid, it):
    if not any(os.path.exists(os.path.join(ARCH, x)) for x in arch_paths(rc, aid, it['archived'])):
        return False                    # 보관 칸에서 이미 지운 글(정리 후보 승인) — 없는 자리를 볼트 글로 적지 않는다
    if not move_all([(os.path.join(ARCH, x), os.path.join(VAULT, x)) for x in arch_paths(rc, aid, it['archived'])]):
        queue(rc['id'], f'볼트에 같은 이름이 있어 되돌리지 않음 {it["archived"]}')
        return False
    it['path'] = it.pop('archived')
    it.pop('archived_run', None)
    return True


def restore(rc, aid=None):
    """보관 칸 → 볼트(같은 자리로). aid 를 주면 그 글만(끝자리만 줘도 된다)."""
    sp, st = load_state(rc)
    n = sum(restore_item(rc, k, it) for k, it in st['items'].items() if it.get('archived') and (not aid or k.endswith(aid)))
    save_state(sp, st)
    log(f'{rc["id"]}: 보관 칸에서 되돌림 {n}')


def rescue(rc, aid, run):
    """사용자가 살린 글(수집 창) — 대기 칸 글은 그대로 볼트로, 장부 글은 본문을 안 받았으니 지금 받아 들인다.
    «쓸모» 표시를 남겨 판정(judge_one)·보존(expire)·보관(archive)이 되돌리지 않는다. 추출이 없던 글의 마감은 다음 판정 때 잡힌다."""
    nf = filt()
    sp, st = load_state(rc)
    it = st['items'].get(aid)
    if not it or it.get('path') or it.get('archived'):
        sys.exit(f'{rc["id"]}: 살릴 글이 아님 {aid}')
    P = stage_paths(rc, aid)
    if os.path.exists(P['md']):
        read = lambda k: open(P[k], encoding='utf-8').read() if os.path.exists(P[k]) else ''
        date, text, raw = it.get('date') or '', read('md'), read('html')
        v = {'attachments': [tuple(x) for x in it.get('v_att') or []], 'body_html': read('body.html')}
    else:
        row = {'id': aid, 'date': it.get('date') or '', 'title': it.get('title') or '', **({'url': it['url']} if it.get('url') else {})}
        try:
            if rc.get('family') == 'rss' and not rc.get('view'):     # 피드 본문만 쓰는 출처 — 장부 글은 본문을 안 받아 뒀으니 피드를 다시 읽는다
                row = next((r for r in rss_list(rc, get(rc['feed'])) if r['id'] == aid), None) or sys.exit(f'{rc["id"]}: 피드에서 사라진 글 {aid}')
            url, raw, v = fetch_view(rc, row)
        except Exception as e:
            sys.exit(f'{rc["id"]}: 글 받기 실패 {aid} `{e!r}`'[:300])
        if not v['title'] or not (v['body_html'] or '').strip():
            sys.exit(f'{rc["id"]}: 글 {aid} 제목·본문 못 찾음')
        date = iso(v['meta'].get(rc.get('date_field', '등록일자')) or row['date'] or time.strftime('%Y-%m-%d'))
        text = render(rc, run, url, row, v)
        it.update(date=date, title=v['title'], url=url, hash=hashlib.sha1((v['body_html'] or '').encode('utf-8')).hexdigest()[:16], attachments=len(v['attachments']))
    p = write_new(os.path.join(VAULT, folder_of(rc), f'{safe(date, 10)} {safe(it["title"])}.md'), text)
    keep_raw(rc, aid, raw)
    it['files'] = take_attachments(rc, run, p, v)
    it['path'] = os.path.relpath(p, VAULT)
    it['verdict'], it['why'] = '관심', '사용자 살림'
    it.pop('stage', None)
    it.pop('v_att', None)
    save_state(sp, st)
    for f in P.values():
        if os.path.exists(f):
            os.remove(f)
    marks = nf.load_marks()
    marks[f'{rc["id"]}:{aid}'] = {'평가': '쓸모', '메모': '살림', 'at': time.strftime('%Y-%m-%d %H:%M')}
    nf.save_marks(marks)
    log(f'{rc["id"]}: 살림 {aid} → {it["path"]}')
    if any(x.get('path') for x in it['files']):
        ingest({os.path.join(VAULT, folder_of(rc))})


def prune_index():
    """글을 지운 뒤 첨부 색인 고아 정리 — ingest 는 전체를 돌 때만 지운다(그림 읽기 없음 · 정식 실행 = py -3)."""
    script = os.path.join(SYS, 'ingest.py')
    if not os.path.isfile(script):
        return
    py = ['py', '-3'] if shutil.which('py') else [sys.executable]
    p = subprocess.run(py + [script, '--prune'], cwd=VAULT, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    log(f'ingest --prune rc={p.returncode} {" ".join((p.stdout or "").split())[-200:]}')


def expire(rc, run, dry=False):
    """웹 공지 보존(보존 일정표 «웹공지» · ADR-029) — 마감 + 날이 지난 볼트 글을 휴지통으로(글 md · 첨부 폴더 · L0 원시 · 장부에 남고 되살릴 수 있다).
    두는 것: 마감을 모르는 글 · 사용자가 «쓸모» 표시한 글 · 노트가 가리키는 글(생성되는 일정 파일은 빼고 센다) · 표의 처리가 «자동 휴지통»이 아닐 때. LLM 0."""
    days = roles.retention('웹공지')
    if not rc.get('filter') or days is None or roles.retention_how('웹공지') != '자동 휴지통':
        return 0
    nf = filt()
    sp, st = load_state(rc)
    j = nf.judged(rc['id'])
    marks = nf.load_marks()
    today = datetime.date.today()
    ctx = fileops.Ctx(VAULT, by='script:web-collect', dry=dry)
    sched = roles.path('schedule') + '/'
    n, kept, bulky = 0, 0, False
    for aid, it in st['items'].items():
        dl = (j.get(aid) or (None, None, None))[2]
        if not it.get('path') or not dl or dl == '0000-00-00':
            continue
        if datetime.date.fromisoformat(dl) + datetime.timedelta(days=days) >= today:
            continue
        rel = it['path'].replace('\\', '/')
        stem = os.path.splitext(rel)[0]
        a_stem = os.path.join(VAULT, *stem.split('/'))
        inside = [ctx.rel(f) for f in fileops.files_under(a_stem)] if os.path.isdir(a_stem) else []
        refs = [f for f, _ in fileops.rewrite_links(ctx, fileops.Moves([(o, o + '.~gone') for o in [rel] + inside]), dry=True)
                if f != rel and not f.startswith(sched)]
        if marks.get(f'{rc["id"]}:{aid}', {}).get('평가') == '쓸모' or refs:
            kept += 1
            log(f'{rc["id"]}: 보존 지났지만 둠 {rel}' + (f' — {refs[0]} 가 가리킴' if refs else ' — 쓸모 표시'))
            continue
        why = f'웹 공지 보존 — 마감 {dl} + {days}일'
        if dry:
            print(f'  휴지통으로: 마감 {dl} · {it["title"][:60]}')
            n += 1
            continue
        try:
            olds = [x['path'].replace('\\', '/') for x in it.get('revs') or [] if x.get('path')]     # 옛 판도 같은 보존으로(원본은 지금 판과 함께 간다)
            raws = [os.path.relpath(f, VAULT).replace('\\', '/') for pat in ('.html', '.rev*.html') for f in glob.glob(os.path.join(glob.escape(RAW), glob.escape(rc['id']), glob.escape(aid) + pat))]
            for r in dict.fromkeys([rel, stem, *olds, *[os.path.splitext(o)[0] for o in olds], *raws]):
                a = os.path.join(VAULT, *r.split('/'))
                if os.path.exists(a):
                    fileops.op_rm(ctx, r, why, count=fileops.describe(a).get('n'), user_asked=True, quiet=True)
        except fileops.Stop as e:       # 잠긴 파일 — 다음 번에 다시(이미 간 것은 장부에)
            queue(rc['id'], f'보존 — 못 지움 {rel} `{e}`'[:300])
            continue
        bulky = bulky or bool(inside)
        it['expired'] = it.pop('path')
        it['verdict'], it['why'] = '지남', why
        it['expired_run'] = run
        n += 1
    if not dry:
        save_state(sp, st)
        if ctx.events:
            fileops.write_view(ctx)
        if bulky:
            prune_index()
    if n or kept:
        log(f'{rc["id"]}: 보존 — 휴지통 {"대상 " if dry else ""}{n} · 둠 {kept}')
    return n


def auto_on(rc):
    """자동 판정을 이 출처에 하나? 전체 스위치(collect.local.json auto_judge)가 true 일 때만 · 그때 조리법 filter.auto 가 false 인 출처만 뺀다. 못 읽으면 끔(사용량은 누를 때만이 원칙)."""
    return bool(rc.get('filter')) and switches().get('auto_judge') is True and (rc['filter'].get('auto') is not False)


def auto_extract(rc, run):
    """자동 판정이 켜진 출처(auto_on) 한 곳. 하나씩 뽑다 사용량 경고면 멈추고 대기열에 한 줄."""
    nf = filt()
    try:
        tot = nf.extract(int(rc['filter'].get('auto_max', 10)), sid=rc['id'], settle=False, stop_on_warning=True)
    except SystemExit as e:
        queue(rc['id'], f'자동 추출 안 함 — {e}', '사용자')
        return
    if tot.get('warning'):
        queue(rc['id'], f'자동 추출 멈춤 — 사용량 경고 {str(tot["warning"])[:120]}', '사용자')
    if tot.get('ok'):
        settle(rc, run)


def settle(rc, run):
    """판정이 난 대기 글만 옮긴다(LLM 0 · 요청은 첨부 받기뿐). 남길 것(KEEP) = 볼트로(L0·L1·첨부·색인) · 비해당 = 대기 칸에 둔 채
    장부 한 줄(카드가 바뀌면 다시 판정되어 들어올 수 있다 · 조리법 filter.keep_days(기본 90일) 뒤 지움) · 지남 = 대기 칸에서도 지운다.
    추출 전 글은 그대로. 보관 칸 글이 남길 것으로 바뀌면(카드 변경) 볼트로 되돌린다."""
    nf = filt()
    sp, st = load_state(rc)
    verdicts = nf.verdicts(rc['id'])
    keep = int((rc.get('filter') or {}).get('keep_days') or roles.retention('웹대기칸') or 90)  # 조리법 > 보존 일정표
    took, dropped, expired, back, folders = 0, 0, 0, 0, set()
    for aid, it in st['items'].items():
        if it.get('archived') and aid in verdicts and verdicts[aid][0] in nf.KEEP:
            if restore_item(rc, aid, it):
                it['verdict'], it['why'] = verdicts[aid]
                back += 1
            continue
        if not it.get('stage') or aid not in verdicts:
            continue
        it['verdict'], it['why'] = verdicts[aid]
        P = stage_paths(rc, aid)
        read = lambda k: open(P[k], encoding='utf-8').read() if os.path.exists(P[k]) else ''
        if it['verdict'] in nf.KEEP:
            rev = it.get('rev') or 1
            p = write_new(os.path.join(VAULT, folder_of(rc), f'{safe(it["date"], 10)} {safe(it["title"])}{f" (개정{rev})" if rev > 1 else ""}.md'), read('md'))
            keep_raw(rc, aid, read('html'), rev)
            it['files'] = take_attachments(rc, run, p, {'attachments': [tuple(x) for x in it.get('v_att') or []], 'body_html': read('body.html')})
            if any(x.get('path') for x in it['files']):
                folders.add(os.path.join(VAULT, folder_of(rc)))
            it['path'] = os.path.relpath(p, VAULT)
            took += 1
        elif it['verdict'] == '지남':
            dropped += 1
        elif age_days(it.get('run')) > keep:
            expired += 1                # 비해당이 기한을 넘김 — 대기 칸에서 지운다(장부 줄은 상태에 남는다)
        else:
            continue                    # 비해당 — 대기 칸에 둔다
        for f in P.values():
            if os.path.exists(f):
                os.remove(f)
        it.pop('stage', None)
        it.pop('v_att', None)
    save_state(sp, st)
    if took or dropped or expired or back:
        log(f'{rc["id"]}: 판정 반영 — 볼트에 들임 {took} · 지남으로 지움 {dropped} · 기한 지나 지움 {expired} · 보관 칸에서 되돌림 {back}')
    ingest(folders)
    return took


# ───────── 재생 ─────────
def list_url(rc, page):
    if rc.get('family') == 'rss':
        return rc['feed']
    return rc['list']['page_url'].format(page=page)


def view_url(rc, row):
    return row.get('url') or rc['view']['url'].format(id=row['id'])


def fetch_view(rc, row):
    """(글 주소, L0 원시, 글 dict) — rss 가 view 정규식이 없으면 피드 본문을 그대로 쓴다."""
    fam = FAMILIES[rc['family']]
    if rc['family'] == 'rss' and not rc.get('view'):
        v = {'title': row['title'], 'meta': {'게시일': row['date']} if row['date'] else {}, 'body_html': row.get('_body', ''),
             'attachments': row.get('_att', [])}
        return row.get('url', ''), row.get('_body', ''), v
    url = view_url(rc, row)
    page = get(url)
    return url, page, fam[1](rc, page, url)


def folder_of(rc):
    """조리법의 넣을 자리 — «@역할/하위» 는 roles.json 으로 푼다(구조를 옮겨도 조리법을 고치지 않게 · R9). 글자 그대로도 받는다."""
    f = rc['folder']
    if f.startswith('@'):
        role, _, rest = f[1:].partition('/')
        return roles.path(role, rest)
    return f


def load_state(rc):
    sp = os.path.join(STATE_DIR, rc['id'] + '.json')
    st = json.load(open(sp, encoding='utf-8')) if os.path.exists(sp) else {'items': {}, 'page1_rows': None}
    return sp, st


def save_state(sp, st):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(sp + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(sp + '.tmp', sp)


# ───────── 가족 listing — 목록 카드만으로 일정 줄(글을 받지 않는다) · 조리법 listing 칸이 정규식 · 고르기(keep·skip)도 데이터 ─────────
def listing_rows(rc, page):
    L = rc['listing']
    rows = []
    for row in re.findall(L['row'], page, re.S):
        it = {k: strip_tags(rx(p, row)) for k, p in L['fields'].items()}
        if it.get('id') and it.get('title'):
            rows.append(it)
    return rows


def run_listing(rc, run, dry):
    L = rc['listing']
    sp, st = load_state(rc)
    keep, skip = re.compile(L['keep']), re.compile(L['skip']) if L.get('skip') else None
    seen, kept = 0, []
    for n in range(1, int(L.get('pages', 1)) + 1):
        rows = listing_rows(rc, get(L['page_url'].format(page=n)))
        if n == 1 and not rows:
            queue(rc['id'], f'검증: 목록 0건(지난번 {st.get("page1_rows")}건) — 화면 구조 변화 의심')
            return 0
        seen += len(rows)
        for it in rows:
            hay = ' '.join(it.get(k, '') for k in L.get('match', ['title']))
            if all(v in it.get(k, '') for k, v in (L.get('need') or {}).items()) and keep.search(hay) and not (skip and skip.search(hay)):
                kept.append(it)
    log(f'{rc["id"]}: 목록 {seen}건 · 고름 {len(kept)}')
    items = st.get('items') or {}
    for it in kept:
        items[it['id']] = it                # 목록에서 밀려나도 마감 전까지 남긴다
    lines, today = [], datetime.date.today()
    for it in items.values():
        m = re.search(L['due'], it.get(L['due_field'], ''))
        if not m:
            continue
        d = datetime.date(int(m[1]), int(m[2]), int(m[3]))
        if d < today:
            continue
        bid = 'lst-' + hashlib.sha1(f'{rc["id"]}|{it["id"]}'.encode('utf-8')).hexdigest()[:10]
        lines.append((d, m[4], f'- [ ] {d:%Y-%m-%d} ({WD[d.weekday()]}) {m[4]} {L["label"]} · {L["line"].format(**it)} [원본]({rc["page"]}) ^{bid}'))
    lines.sort(key=lambda x: (x[0], x[1]))
    lines = [x[2] for x in lines]
    if dry:
        for ln in lines:
            print('  ', ln[:170])
        return 0
    import schedule
    print(schedule.write_generated(L['output'], rc['name'], rc['page'], lines))
    st.update(items=items, page1_rows=seen, last_run=time.time())
    save_state(sp, st)
    return 0


# ───────── 수정된 글 — 목록 줄(제목·게시일)이 바뀐 것만(원본 불변 · 새 파일) ─────────
def row_sig(r):
    return {'row_title': r.get('title') or '', 'row_date': iso(r.get('date'))}


def row_changed(it, r):
    """상태에 적어 둔 줄 값과 다른가. 줄 값이 없는 옛 항목은 지금 줄을 처음 본 것으로 적고 «안 바뀜» — 한꺼번에 다시 받지 않게."""
    sig = row_sig(r)
    if 'row_title' not in it:
        it.update(sig)
        return False
    return (it['row_title'], it.get('row_date')) != (sig['row_title'], sig['row_date'])


def revise(rc, run, st, r, nf):
    """줄이 바뀐 글 하나를 다시 받아 반영한다 → (결과, 색인할 폴더들). 결과 = 같음(줄만 달랐다) · 개정(새 판) · 관문(장부 글이 그대로 관문에 걸림) · 둠(건드리지 않음) · 실패(다음에 다시).
    새 판 = 볼트 글은 새 파일(옛 md·첨부·L0 그대로) · 대기 칸 글은 옛 판을 REV 로 · 보관 칸 글은 옛 판을 둔 채 새 판을 대기 칸에. 추출 캐시는 그대로 두고 reextract 표시만."""
    aid = r['id']
    old = st['items'][aid]
    sig = row_sig(r)
    folders = set()
    where = 'path' if old.get('path') else 'archived' if old.get('archived') else 'stage' if old.get('stage') else ''
    if old.get('expired') or (where == 'path' and not os.path.exists(os.path.join(VAULT, old['path']))):    # 보존으로 지난 글 · 사용자가 치운 글 — 되살리지 않는다
        old.update(sig)
        return '둠', folders
    g = words_gate(rc, r) or (nf.gate(rc, r) if nf else None)
    if g and where:                     # 이미 든 글이 이제 제목 관문에 걸려도(예: «마감» 표시) 건드리지 않는다
        old.update(sig)
        return '둠', folders
    if g:                               # 장부 글이 그대로 걸림 — 새 제목·근거만
        old.update(sig, title=r.get('title') or '', verdict=g[0], why=g[1])
        return '관문', folders
    try:
        url, raw, v = fetch_view(rc, r)
    except Exception as e:
        queue(rc['id'], f'글 다시 받기 실패 {aid} `{e!r}`'[:300])
        return '실패', folders
    if not v['title'] or not (v['body_html'] or '').strip():
        queue(rc['id'], f'검증: 글 {aid} 다시 받았는데 제목·본문 못 찾음 — 글 화면 구조 변화 의심')
        return '실패', folders
    date = iso(v['meta'].get(rc.get('date_field', '등록일자')) or r.get('date') or time.strftime('%Y-%m-%d'))
    h = hashlib.sha1((v['body_html'] or '').encode('utf-8')).hexdigest()[:16]
    if where and old.get('hash') == h and old.get('title') == v['title'] and old.get('date') == date:
        old.update(sig)                 # 줄만 달랐다(댓글 수 따위) — 아무것도 안 쓴다
        return '같음', folders
    rev = (old.get('rev') or 1) + 1
    item = {'date': date, 'title': v['title'], 'url': url, 'hash': h, 'run': run, 'attachments': len(v['attachments']), **sig}
    if where:
        item['rev'] = rev
        item['revs'] = list(old.get('revs') or []) + [{'rev': old.get('rev') or 1, where: old.get(where) or '', 'run': old.get('run')}]
        if nf:
            item['reextract'] = True
        for k in ('verdict', 'why'):
            if old.get(k):
                item[k] = old[k]
    if nf and where != 'path':          # 판정을 거치는 자리 — 대기 칸에(옛 대기 칸 판은 REV 로)
        if where == 'stage':
            for k, f in stage_paths(rc, aid).items():
                if os.path.exists(f):
                    os.makedirs(os.path.join(REV, rc['id']), exist_ok=True)
                    shutil.move(f, os.path.join(REV, rc['id'], f'{aid}.{run}.{k}'))
        stage_put(rc, aid, raw, v, render(rc, run, url, r, v))
        item.update(stage=True, v_att=v['attachments'])
        item.pop('verdict', None)
        item.pop('why', None)
    else:                               # 볼트에 곧바로 — 새 파일(옛 글은 그대로)
        tail = f' (개정{rev})' if where else ''
        p = write_new(os.path.join(VAULT, folder_of(rc), f'{safe(date, 10)} {safe(v["title"])}{tail}.md'), render(rc, run, url, r, v))
        keep_raw(rc, aid, raw, rev if where else 1)
        item['files'] = take_attachments(rc, run, p, v)
        item['path'] = os.path.relpath(p, VAULT)
        if any(x.get('path') for x in item['files']):
            folders.add(os.path.join(VAULT, folder_of(rc)))
    st['items'][aid] = item
    return '개정' if where else '관문 통과', folders


def run_source(rc, run, dry):
    if rc.get('family') == 'calendar':
        return run_calendar(rc, run, dry)
    if rc.get('family') == 'listing':
        return run_listing(rc, run, dry)
    fam = FAMILIES.get(rc.get('family'))
    if not fam:
        queue(rc['id'], f'모르는 가족 `{rc.get("family")}`')
        return
    sp, st = load_state(rc)
    first = not st['items']
    todo, changed, seen_rows = [], [], 0
    pages = 1 if rc['family'] == 'rss' else int(rc['list'].get('pages', 3))
    for page in range(1, pages + 1):
        try:
            rows = fam[0](rc, get(list_url(rc, page)))
        except OSError as e:
            if isinstance(e, urllib.error.HTTPError):
                queue(rc['id'], f'목록 {page}쪽 받기 실패 `{e!r}`'[:300])
            else:
                log(f'{rc["id"]}: 목록 {page}쪽 망 오류 — 다음에 다시 `{e!r}`'[:300])   # 깬 직후 등
            break
        except Exception as e:
            queue(rc['id'], f'목록 {page}쪽 읽기 실패 `{e!r}`'[:300])
            break
        if page == 1:
            seen_rows = len(rows)
            if not rows:
                queue(rc['id'], f'검증: 목록 1쪽 0건(지난번 {st.get("page1_rows")}건) — 화면 구조 변화 의심')
                break
            blank = sum(1 for r in rows if not (r.get('title') or '').strip())
            if blank * 2 > len(rows):       # 번호는 잡히는데 제목이 비면 «제목이 바뀐 글»로 잘못 읽고 조용히 넘어간다(11-06 시험에서 찾음)
                queue(rc['id'], f'검증: 목록 1쪽 {len(rows)}건 중 제목 못 찾음 {blank} — 화면 구조 변화 의심')
                seen_rows = 0
                break
        new, ids = [], {t['id'] for t in todo}      # 같은 쪽 안 중복(고정 글이 일반 줄에도 있는 게시판)도 한 번만 받는다
        for r in rows:
            if r['id'] not in st['items'] and r['id'] not in ids:
                ids.add(r['id'])
                new.append(r)
            elif r['id'] in st['items'] and row_changed(st['items'][r['id']], r) and all(c['id'] != r['id'] for c in changed):
                changed.append(r)
        if first:       # 첫 수집은 1쪽 전부(고정 공지 포함) + 그 뒤로는 first_since 이후만 · 피드는 고정 글이 없고 한 쪽이 전부라 first_since 를 모두에(11-06 — 몇 달 치를 한꺼번에 들이지 않게)
            new = [r for r in new if (page == 1 and rc['family'] != 'rss') or iso(r.get('date') or '') >= iso(rc.get('first_since', '0000'))]
        todo += new
        if not new and (page > 1 or not first):     # 수집 신호: 1쪽에 새 글이 없으면 거기서 끝 — 요청 1번
            break
    log(f'{rc["id"]}: 목록 1쪽 {seen_rows}건 · 새 글 {len(todo)}' + (f' · 줄이 바뀐 글 {len(changed)}' if changed else '') + (' (첫 수집)' if first else ''))
    if dry:
        for r in todo:
            print('  ', r.get('date'), r.get('title', '')[:70])
        for r in changed:
            print('   (바뀜)', r.get('date'), r.get('title', '')[:70])
        return
    nf = filt() if rc.get('filter') else None      # 거르는 출처 — 판정 전에는 볼트에 넣지 않는다(수집은 선별)
    got, staged, gated, folders = 0, 0, 0, set()
    for r in reversed(todo):            # 오래된 것부터 — 중간에 멈춰도 다음에 이어진다
        g = words_gate(rc, r) or (nf.gate(rc, r) if nf else None)     # 제목만으로(LLM 0) — 걸리면 글을 받지도 않는다
        if g:
            st['items'][r['id']] = {'date': iso(r.get('date')), 'title': r.get('title') or '', 'run': run, 'verdict': g[0], 'why': g[1],
                                    'url': r.get('url') or (view_url(rc, r) if rc.get('view') else ''), **row_sig(r)}
            gated += 1
            continue
        try:
            url, raw, v = fetch_view(rc, r)
        except Exception as e:
            queue(rc['id'], f'글 받기 실패 {r["id"]} `{e!r}`'[:300])
            continue
        if not v['title'] or not (v['body_html'] or '').strip():
            queue(rc['id'], f'검증: 글 {r["id"]} 제목·본문 못 찾음 — 글 화면 구조 변화 의심')
            continue
        date = iso(v['meta'].get(rc.get('date_field', '등록일자')) or r.get('date') or time.strftime('%Y-%m-%d'))
        item = {'date': date, 'title': v['title'], 'url': url, 'hash': hashlib.sha1((v['body_html'] or '').encode('utf-8')).hexdigest()[:16],
                'run': run, 'attachments': len(v['attachments']), **row_sig(r)}
        if nf:
            stage_put(rc, r['id'], raw, v, render(rc, run, url, r, v))
            st['items'][r['id']] = {**item, 'stage': True, 'v_att': v['attachments']}
            staged += 1
            continue
        keep_raw(rc, r['id'], raw)
        p = write_new(os.path.join(VAULT, folder_of(rc), f'{safe(date, 10)} {safe(v["title"])}.md'), render(rc, run, url, r, v))
        files = take_attachments(rc, run, p, v)
        if any(x.get('path') for x in files):
            folders.add(os.path.join(VAULT, folder_of(rc)))
        st['items'][r['id']] = {**item, 'path': os.path.relpath(p, VAULT), 'files': files}
        got += 1
    if changed:
        if len(changed) > MAX_CHANGED:      # 글 수정이 이만큼 한꺼번에 일어나지 않는다 — 화면이 바뀐 것. 줄 값만 새로 적고 다시 받지 않는다
            queue(rc['id'], f'검증: 목록 줄 {len(changed)}건이 한꺼번에 바뀜 — 화면 구조 변화 의심(글은 다시 안 받음)')
            for r in changed:
                st['items'][r['id']].update(row_sig(r))
        else:
            tally = {}
            for r in reversed(changed):
                k, fs = revise(rc, run, st, r, nf)
                tally[k] = tally.get(k, 0) + 1
                folders |= fs
            log(f'{rc["id"]}: 수정 반영 — ' + ' · '.join(f'{k} {n}' for k, n in sorted(tally.items())))
    st['page1_rows'] = seen_rows or st.get('page1_rows')
    if seen_rows:               # 목록을 실제로 읽었을 때만 — 깬 직후 망이 없으면 간격을 날리지 않는다
        st['last_run'] = time.time()
    save_state(sp, st)
    log(f'{rc["id"]}: 받음 {got}/{len(todo)} → {folder_of(rc)}' + (f' · 대기 칸 {staged} · 제목 장부 {gated}' if nf or gated else ''))
    ingest(folders)
    if nf:
        got += settle(rc, run)          # 캐시가 이미 있는 글(카드 변경 등)만 — 새 글은 추출(단추) 뒤에
    return got


def backfill(rc, run):
    """이미 받은 글의 첨부·그림만 — L0 원시 html 을 다시 읽어(서버에 글을 다시 묻지 않음) 첨부 주소를 얻는다."""
    sp, st = load_state(rc)
    fam = FAMILIES[rc['family']]
    n, folders = 0, set()
    for aid, it in st['items'].items():
        if it.get('files') is not None and 'files' in it and it.get('backfilled'):
            continue
        rawp = os.path.join(RAW, rc['id'], aid + '.html')
        if not os.path.exists(rawp):
            continue
        page = open(rawp, encoding='utf-8').read()
        url = rc['view']['url'].format(id=aid) if rc.get('view') else ''
        v = fam[1](rc, page, url) if fam[1] else None
        if not v:
            continue
        it['files'] = take_attachments(rc, run, os.path.join(VAULT, it['path']), v)
        it['backfilled'] = run
        if any(x.get('path') for x in it['files']):
            folders.add(os.path.join(VAULT, folder_of(rc)))
        n += 1
        save_state(sp, st)
    took = sum(1 for it in st['items'].values() for x in it.get('files') or [] if x.get('path'))
    log(f'{rc["id"]}: 첨부 되채우기 글 {n} · 들인 파일 누적 {took}')
    ingest(folders)


def check(rc, k=3):
    """조리법 검증 — 받아 둔 L0 원시로 목록·글 파서를 다시 돌려 상태의 제목·날짜와 맞는지(네트워크는 목록 1쪽만)."""
    sp, st = load_state(rc)
    fam = FAMILIES[rc['family']]
    rows = fam[0](rc, get(list_url(rc, 1)))
    known = [r for r in rows if r['id'] in st['items']]
    print(f'목록 1쪽 {len(rows)}건 · 상태에 있는 글 {len(known)}건')
    bad = 0
    for aid in list(st['items'])[:k] + list(st['items'])[-k:]:
        rawp = os.path.join(RAW, rc['id'], aid + '.html')
        if not os.path.exists(rawp) or not fam[1]:
            continue
        v = fam[1](rc, open(rawp, encoding='utf-8').read(), rc['view']['url'].format(id=aid))
        it = st['items'][aid]
        ok = v['title'] == it['title'] and v['meta'].get(rc.get('date_field', '등록일자'), it['date']) == it['date']
        bad += not ok
        print(f'  {"OK " if ok else "다름"} {it["date"]} {it["title"][:50]} | 첨부 {len(v["attachments"])}')
    print(f'불일치 {bad}')
    return bad


def words_gate(rc, row):
    """낱말 관문(제목만 · LLM 0 · 요청 0 · 11-06 수집 추가) → (비해당, 근거) 또는 None. 조리법 words.skip 에 걸리거나 words.keep 이 있는데 안 맞으면
    글을 받지 않고 장부 한 줄만(수집 창에서 살릴 수 있다). 판정 층(filter)과 따로다 — 판정 층이 없는 출처(블로그·유튜브 등)도 이것으로 고른다.
    값 = 정규식 조각을 | 로 이은 것(수집 창 칩) · 대소문자 무시."""
    w = rc.get('words') or {}
    t = row.get('title') or ''
    m = re.search(w['skip'], t, re.I) if w.get('skip') else None
    if m:
        return '비해당', f'뺄 말 «{m.group(0)}»'
    if w.get('keep') and not re.search(w['keep'], t, re.I):
        return '비해당', '남길 말 없음'
    return None


# ───────── 수집 추가(11-06) — 탐색·미리보기: 글을 받아 두지 않는다(robots 답만 하루 캐시) ─────────
DRAFT = os.path.join(STATE_DIR, 'draft')     # 조리법 초안 <id>.json · 미리보기 표시 <id>.tried.json · 탐색 원시 probe/ · robots 캐시 robots/ — RECIPES 밖이라 확정 전에는 돌지 않는다
ROBOTS_TTL = 86400
BOT = 'BrainCollector'                      # UA 의 이름 조각 — robots.txt 의 User-agent 대조용
SITE_GAP = float(os.environ.get('COLLECT_SITE_GAP', 60))    # 탐색·미리보기는 같은 사이트를 이 간격(초) 안에 다시 받지 않는다 — 남은 만큼 기다렸다 받음(시험은 0)
HITS = os.path.join(DRAFT, 'hits.json')     # 사이트별 마지막 탐색·미리보기 시각(프로세스를 건너 지킨다)
FREE = ('name', 'purpose', 'recheck_hours', 'folder', 'first_since', 'explored', 'robots_note', 'group')   # 미리보기 결과에 안 닿는 칸


def site_wait(url):
    """탐색·미리보기 앞 — 같은 사이트를 1분 안에 거듭 받지 않게 남은 만큼 기다린다. 기다린 초를 돌려준다.
    11-06 끝까지 시험: 대화가 엔진을 직접 불러 43초 만에 같은 게시판을 다시 받았다 — 스킬 문구만으로는 못 지킨다."""
    host = urllib.parse.urlparse(url).netloc.lower()
    try:
        last = float(json.load(open(HITS, encoding='utf-8')).get(host, 0))
    except (OSError, ValueError, TypeError, AttributeError):
        last = 0.0
    wait = min(SITE_GAP, last + SITE_GAP - time.time())
    if wait > 0:
        time.sleep(wait)
    return max(0, round(wait))


def site_mark(url):
    """탐색·미리보기 끝 — 그 사이트를 받은 때를 적는다(하루 지난 것은 지움)."""
    try:
        hits = json.load(open(HITS, encoding='utf-8'))
    except (OSError, ValueError):
        hits = {}
    t = time.time()
    hits = {h: v for h, v in (hits.items() if isinstance(hits, dict) else ()) if isinstance(v, (int, float)) and t - v < 86400}
    hits[urllib.parse.urlparse(url).netloc.lower()] = t
    os.makedirs(DRAFT, exist_ok=True)
    with open(HITS + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(hits, f)
    os.replace(HITS + '.tmp', HITS)


def res_sha(rc):
    """미리보기 결과를 정하는 칸의 지문 = FREE 를 뺀 나머지 전부(모르는 칸은 넣는다).
    확정은 이것이 미리보기 때와 같으면 다시 받지 않는다 — 11-06 끝까지 시험에서 주기만 바꿔도 확정이 막혀 사이트를 다시 받았다."""
    return hashlib.sha1(json.dumps({k: v for k, v in rc.items() if k not in FREE}, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def robots(url):
    """(허용|막힘|모름, 근거) — 사이트의 robots.txt 를 하루 캐시(사이트당 요청 1번). 없으면(404·410) 허용 · 401·403·5xx·망 오류는 모름(사람이 정한다)."""
    import urllib.robotparser
    u = urllib.parse.urlparse(url)
    cp = os.path.join(DRAFT, 'robots', re.sub(r'[^a-z0-9.-]', '_', u.netloc.lower()) + '.txt')
    if os.path.exists(cp) and time.time() - os.path.getmtime(cp) < ROBOTS_TTL:
        txt = open(cp, encoding='utf-8').read()
    else:
        try:
            txt = get(f'{u.scheme}://{u.netloc}/robots.txt')
        except urllib.error.HTTPError as e:
            if e.code not in (404, 410):
                return '모름', f'robots.txt HTTP {e.code}'
            txt = ''
        except Exception as e:
            return '모름', f'robots.txt 못 받음 {type(e).__name__}'
        os.makedirs(os.path.dirname(cp), exist_ok=True)
        with open(cp, 'w', encoding='utf-8', newline='\n') as f:
            f.write(txt)
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(txt.splitlines())
    ok = rp.can_fetch(BOT, url)
    return ('허용' if ok else '막힘'), ('robots.txt 없음' if not txt.strip() else f'robots.txt {"허용" if ok else "Disallow"} {u.path or "/"}')


def probe(url, note=''):
    """탐색 한 쪽(Claude 가 조리법을 쓰려고 읽는다) — 원시를 draft/probe 에 두고 요약 dict. 요청 = 그 쪽 1 + robots(하루 1).
    피드 찾기(<link rel=alternate type=rss|atom> · 댓글 피드는 따로 · 본문 링크의 피드 꼴 주소는 후보로) · 피드 자체인가 · 대본 수·보이는 글자 수(자바스크립트로 그리는 쪽이면 글자가 거의 없다 = 1차 범위 밖).
    robots 가 막은 쪽은 받지 않는다 — 사용자가 넣기로 정했으면 그 결정(note)을 받아 그때만."""
    t0, waited = time.time(), site_wait(url)
    try:
        rb = robots(url)
        if rb[0] == '막힘' and not note.strip():
            return {'url': url, 'robots': rb, 'problems': [f'robots 막힘({rb[1]}) — 받지 않음 · 넣을지는 사용자가 정한다']}
        with _open(url) as r:
            raw = r.read(8 * 2**20 + 1)
            status, final, ctype, cs = r.status, r.geturl(), r.headers.get('Content-Type') or '', r.headers.get_content_charset()
        _last[0] = time.time()
    finally:
        if _last[0] > t0:       # 실제로 받았을 때만(robots 캐시로 멈추면 안 적음)
            site_mark(url)
    if not cs:
        m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', raw[:4096], re.I) or re.search(rb'<\?xml[^>]+encoding=["\']([\w-]+)', raw[:200], re.I)
        cs = m.group(1).decode('ascii') if m else 'utf-8'
    page = raw.decode(cs, 'replace')
    host = urllib.parse.urlparse(final).netloc
    p = os.path.join(DRAFT, 'probe', f'{re.sub(r"[^A-Za-z0-9.-]", "_", host)}-{hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]}.html')
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(page)
    feeds, comments, linked = [], [], []
    for tag in re.findall(r'<link\b[^>]*>', page, re.I):
        if re.search(r'rel=["\']?alternate', tag, re.I) and re.search(r'type=["\']?application/(?:rss|atom)\+xml', tag, re.I):
            href = re.search(r'href=["\']([^"\']+)', tag, re.I)
            if href:
                # 글 하나·분류 쪽은 머리에 «댓글 피드»만 걸어 두기도 한다(워드프레스) — 따로 알리고 본 피드 뒤로
                title = re.search(r'title=["\']([^"\']*)', tag, re.I)
                (comments if title and re.search(r'comment|댓글', html.unescape(title.group(1)), re.I) else feeds).append(
                    urllib.parse.urljoin(final, html.unescape(href.group(1))))
    # 머리에 안 건 피드를 본문 링크로만 두는 쪽 — 주소 꼴(…/feed · /rss · .xml · ?feed=rss2)로 후보만(받지 않음 · 같은 사이트 먼저)
    for href in re.findall(r'<a\b[^>]*?href=["\']([^"\'#]+)', page, re.I):
        u = urllib.parse.urljoin(final, html.unescape(href))
        pu = urllib.parse.urlparse(u)
        if pu.scheme in ('http', 'https') and (re.search(r'/(?:feed|rss|atom)/?$|\.(?:rss|atom|xml)$', pu.path, re.I) or re.search(r'(?:^|&)feed=(?:rss2?|atom)\b', pu.query, re.I)):
            linked.append(u)
    linked.sort(key=lambda u: urllib.parse.urlparse(u).netloc != host)
    try:
        rows = rss_list({}, page)
    except Exception:
        rows = []
    return {'url': url, 'final': final, 'status': status, 'type': ctype.split(';')[0].strip(), 'charset': cs, 'bytes': len(raw),
            'saved': os.path.relpath(p, VAULT).replace('\\', '/'), 'title': strip_tags(rx(r'<title[^>]*>(.*?)</title>', page))[:120],
            'feeds': list(dict.fromkeys(feeds))[:8], 'linked_feeds': [u for u in dict.fromkeys(linked) if u not in feeds and u not in comments][:8],
            'comment_feeds': list(dict.fromkeys(comments))[:4], 'feed_rows': len(rows), 'scripts': len(re.findall(r'<script\b', page, re.I)),
            'text_chars': len(to_text(page).text()), 'robots': rb, 'waited': waited}


def patterns(rc):
    """조리법 안의 정규식 전부 [(자리, 글)] — 미리보기·확정이 컴파일만 해 본다."""
    out = []
    for key in ('list', 'view'):
        for k, v in (rc.get(key) or {}).items():
            if isinstance(v, str) and k not in ('page_url', 'url') or (key == 'list' and k == 'url'):
                out.append((f'{key}.{k}', v))
            elif isinstance(v, dict):
                out += [(f'{key}.{k}.{kk}', vv) for kk, vv in v.items() if isinstance(vv, str)]
    out += [(f'words.{k}', v) for k, v in (rc.get('words') or {}).items() if isinstance(v, str)]
    if (rc.get('filter') or {}).get('title_skip'):
        out.append(('filter.title_skip', rc['filter']['title_skip']))
    return out


def validate(rc):
    """조리법 꼴 검사(망 요청 0) → 문제 글 목록(비면 통과). 1차 범위 = regex(게시판 목록)·rss(RSS·Atom·유튜브 채널 피드)."""
    bad = []
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,48}', str(rc.get('id') or '')):
        bad.append('id = 영문 소문자·숫자·- 2~49자')
    if not str(rc.get('name') or '').strip():
        bad.append('name 없음')
    fam = rc.get('family')
    if fam not in ('regex', 'rss'):
        bad.append(f'가족 {fam!r} — 수집 추가는 regex·rss')
    if not re.match(r'^https?://', str(rc.get('page') or '')):
        bad.append('page 주소 없음')
    if fam == 'rss' and not re.match(r'^https?://', str(rc.get('feed') or '')):
        bad.append('feed 주소 없음')
    if fam == 'regex':
        L, V = rc.get('list') or {}, rc.get('view') or {}
        if '{page}' not in str(L.get('page_url') or ''):
            bad.append('list.page_url 에 {page} 없음')
        if not all((L.get('fields') or {}).get(k) for k in ('id', 'title')):
            bad.append('list.fields 에 id·title 없음')
        if not (V.get('url') or L.get('url')):
            bad.append('글 주소(view.url 또는 list.url) 없음')
        if not (V.get('title') and V.get('body')):
            bad.append('view.title·view.body 없음')
    for where, p in patterns(rc):
        try:
            re.compile(p)
        except re.error as e:
            bad.append(f'정규식 깨짐 {where}: {e}')
    try:
        folder_of(rc)
    except Exception as e:
        bad.append(f'folder 못 풂 {rc.get("folder")!r}: {e}')
    h = rc.get('recheck_hours', 20)
    if not isinstance(h, (int, float)) or not 1 <= h <= 24:
        bad.append('recheck_hours = 1~24')
    return bad


def preview(path, view=False):
    """미리보기(저장 없음) — 목록 1쪽만 받아 최근 글과 관문(낱말·제목 거르기) 결과를 보인다 · view = 첫 통과 글 하나를 받아 제목·본문이 잡히는지.
    요청 = 목록 1 (+ 글 1) + robots(하루 1). 초안(draft/<id>.json)이면 <id>.tried.json 에 결과 요약을 남긴다(확정·고침이 «미리보기를 거쳤나»를 본다)."""
    raw_rc = open(path, 'rb').read()
    rc = json.loads(raw_rc.decode('utf-8'))
    out = {'id': rc.get('id'), 'problems': validate(rc), 'robots': {}}
    note = str(rc.get('robots_note') or '').strip()     # robots 가 막은 쪽은 사용자 결정이 초안에 있을 때만 받는다
    t0, lu = time.time(), None
    try:
        if not out['problems']:
            lu = list_url(rc, 1)
            out['waited'] = site_wait(lu)
            out['robots']['list'] = robots(lu)
            if out['robots']['list'][0] == '막힘' and not note:
                out['problems'].append('robots 막힘 — 받지 않음 · 넣을지는 사용자가 정한다(초안 robots_note)')
                raise StopIteration
            rows = FAMILIES[rc['family']][0](rc, get(lu))
            sp = os.path.join(STATE_DIR, rc['id'] + '.json')      # 고침이면 지금 상태와 견준다 — 글 번호 꼴이 바뀌면 전부 새 글로 받힌다
            known = set((json.load(open(sp, encoding='utf-8')).get('items') or {}) if os.path.exists(sp) else ())
            try:
                nf = filt() if rc.get('filter') else None
            except Exception:
                nf = None
            shown = []
            for r in rows:
                g = words_gate(rc, r)
                if not g and rc.get('filter'):
                    try:
                        g = nf.gate(rc, r) if nf else None
                    except Exception:
                        g = None
                    if not g and rc['filter'].get('title_skip') and re.search(rc['filter']['title_skip'], r.get('title') or ''):
                        g = ('비해당', '제목 관심 밖')
                shown.append({'id': r['id'], 'date': iso(r.get('date')), 'title': r.get('title') or '', 'gate': g[1] if g else '', 'known': r['id'] in known,
                              'url': r.get('url') or (view_url(rc, r) if (rc.get('view') or {}).get('url') else '')})
            out.update(n=len(rows), kept=sum(1 for x in shown if not x['gate']), known=sum(x['known'] for x in shown), state=len(known), rows=shown)
            if not rows:
                out['problems'].append('목록 0건 — 줄·칸 정규식이 안 맞음')
            elif sum(1 for x in shown if not x['title'].strip()) * 2 > len(shown):
                out['problems'].append('목록 줄 제목을 반 넘게 못 찾음 — title 정규식')
            elif known and not out['known'] and len(known) >= 3:
                out['problems'].append(f'상태 글 {len(known)}건과 하나도 안 겹침 — 글 번호 꼴이 바뀌면 전부 새 글로 다시 받힌다')
            first = next((r for r, x in zip(rows, shown) if not x['gate']), rows[0] if rows else None)     # 다 걸려도 글 쪽 구조는 잰다
            if view and first:
                if rc['family'] == 'regex' or rc.get('view'):     # 글 쪽을 실제로 받을 때만(피드 본문만 쓰면 요청이 없다)
                    out['robots']['view'] = robots(view_url(rc, first))
                    if out['robots']['view'][0] == '막힘' and not note:
                        out['problems'].append('글 쪽 robots 막힘 — 받지 않음 · 넣을지는 사용자가 정한다(초안 robots_note)')
                        raise StopIteration
                url, _, v = fetch_view(rc, first)
                body = to_text(v['body_html'] or '').text()
                out['view'] = {'url': url, 'title': v['title'], 'meta': v['meta'], 'body_chars': len(body), 'body_head': body[:240],
                               'attachments': [n for n, _ in v['attachments']][:8]}
                if not v['title'] or not body.strip():
                    out['problems'].append('글 제목·본문을 못 찾음 — view 정규식')
    except StopIteration:
        pass
    except urllib.error.HTTPError as e:
        out['problems'].append(f'받기 실패 HTTP {e.code}')
    except OSError as e:
        out['problems'].append(f'망 오류 {e!r}'[:200])
    except Exception as e:
        out['problems'].append(f'읽기 실패 {e!r}'[:200])
    if lu and _last[0] > t0:
        site_mark(lu)
    if os.path.dirname(os.path.abspath(path)) == os.path.abspath(DRAFT):
        # 글 쪽 확인은 구조(주소·정규식)에 매인다 — 낱말만 고친 뒤 목록만 다시 봐도 앞서 잰 글 확인이 그대로 산다(같은 사이트를 거듭 두드리지 않게)
        tp = os.path.join(DRAFT, f'{rc.get("id")}.tried.json')
        struct = hashlib.sha1(json.dumps({k: rc.get(k) for k in ('family', 'page', 'feed', 'list', 'view', 'date_field')}, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
        try:
            prev = json.load(open(tp, encoding='utf-8'))
        except (OSError, ValueError):
            prev = {}
        view_ok = bool(out.get('view')) and not any(p.startswith('글 제목') for p in out['problems']) or (not view and prev.get('struct') == struct and prev.get('view_ok') is True)
        robots_seen = {**(prev.get('robots') or {}), **out['robots']} if prev.get('struct') == struct else out['robots']
        with open(tp, 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'sha': hashlib.sha1(raw_rc).hexdigest(), 'res': res_sha(rc), 'struct': struct, 'at': now(), 'ok': not out['problems'] and bool(out.get('n')),
                       'view_ok': view_ok, 'n': out.get('n'), 'kept': out.get('kept'), 'robots': robots_seen}, f, ensure_ascii=False)
    return out


def switches():
    """수집 전체 스위치 all_off·auto_judge — 3_시스템/collect.local.json(이 PC 의 결정 · git 밖 · 수집 본체 통합 11-07).
    그 칸이 없으면 옛 자리 lms/desk.json 의 칸을 한 판 동안 읽는다. 둘 다 없거나 못 읽으면 수집 켜짐·자동 판정 끔(값은 true 일 때만 켬)."""
    out = {}
    for p in (os.path.join(SYS, 'lms', 'desk.json'), os.path.join(SYS, 'collect.local.json')):    # 뒤(새 자리)가 이긴다
        try:
            d = json.load(open(p, encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict):
            out.update((k, d[k]) for k in ('all_off', 'auto_judge') if k in d)
    return out


def learn():
    """되먹임(filter-learn.py · LLM 0) — 뺀 글·살린 글·손 노트·카드를 제목 규칙으로 잇는다. 판정 전에 돌아 같은 판에 반영된다.
    따로 프로세스라 실패해도 수집과 판정은 선다."""
    fp = os.path.join(SYS, 'filter-learn.py')
    if not os.path.exists(fp):
        return
    py = ['py', '-3'] if shutil.which('py') else [sys.executable]
    try:
        p = subprocess.run(py + [fp, 'run'], cwd=VAULT, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except (OSError, subprocess.SubprocessError) as e:
        return log(f'되먹임 못 돎 `{e!r}`'[:200])
    if p.returncode:
        log(f'되먹임 실패 rc={p.returncode} {(p.stderr or "")[-160:]}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--backfill', action='store_true')
    ap.add_argument('--settle', action='store_true')
    ap.add_argument('--archive', action='store_true', help='거르는 출처: 지금 엔진이면 들이지 않았을 볼트 글을 보관 칸으로(--dry = 목록만)')
    ap.add_argument('--restore', action='store_true', help='보관 칸 → 볼트(--id 로 한 글만)')
    ap.add_argument('--expire', action='store_true', help='보존 일정표 «웹공지»: 마감 + 날이 지난 볼트 글 → 휴지통')
    ap.add_argument('--rescue', action='store_true', help='사용자가 살린 글 → 볼트(--source · --id 필수 · 수집 창이 부른다)')
    ap.add_argument('--id')
    ap.add_argument('--probe', metavar='URL', help='수집 추가 탐색: 한 쪽을 받아 draft/probe 에 두고 요약 JSON(피드 찾기·robots)')
    ap.add_argument('--preview', metavar='조리법.json', help='미리보기(저장 없음): 목록 1쪽 + 관문 결과 JSON · --view = 첫 글 하나도')
    ap.add_argument('--view', action='store_true')
    ap.add_argument('--robots-note', default='', help='--probe: robots 가 막은 쪽을 사용자가 넣기로 정했을 때 그 결정 한 줄')
    ap.add_argument('--lint', metavar='조리법.json', help='꼴 검사만(망 요청 0): 문제 목록 + 미리보기 결과 지문 JSON — 확정·고침이 부른다')
    a = ap.parse_args()
    if a.lint:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        rc = json.load(open(a.lint, encoding='utf-8'))
        return print(json.dumps({'problems': validate(rc), 'res': res_sha(rc)}, ensure_ascii=False))
    if a.probe or a.preview:            # 사람이 부른 탐색 — 전체 끔·계약 관문 앞(아무것도 받아 두지 않는다)
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        try:
            r = probe(a.probe, a.robots_note) if a.probe else preview(a.preview, a.view)
        except urllib.error.HTTPError as e:
            r = {'url': a.probe, 'problems': [f'받기 실패 HTTP {e.code}']}
        except (OSError, ValueError) as e:
            r = {'url': a.probe or a.preview, 'problems': [f'{type(e).__name__}: {e}'[:200]]}
        return print(json.dumps(r, ensure_ascii=False))
    if a.rescue and not (a.source and a.id):
        ap.error('--rescue 는 --source 와 --id 를 함께')
    if switches().get('all_off') is True and not (a.check or a.archive or a.restore or a.dry):     # 전체 끔 — 점검·볼트 안 정리·미리 보기는 사람이 부른 것
        return print('전체 꺼짐 — 건너뜀')
    run = time.strftime('%Y%m%d-%H%M')
    judged = False
    for rp in sorted(glob.glob(os.path.join(RECIPES, '*.json'))):
        rc = json.load(open(rp, encoding='utf-8'))
        if a.source and rc['id'] != a.source:
            continue
        if rc.get('family') in ('calendar', 'listing') and (a.check or a.backfill or a.settle or a.archive or a.restore or a.expire):
            if a.check:
                run_source(rc, run, True)
            continue
        if a.check:
            check(rc)
            continue
        if a.archive or a.restore:      # 볼트 안 정리 — 받기가 없으니 계약 관문 앞
            if rc.get('filter'):
                archive(rc, run, a.dry) if a.archive else restore(rc, a.id)
                judged = judged or not a.dry
            continue
        if rc.get('enabled') is False and not a.dry:    # 끈 출처 = 받기·보존·판정 반영을 모두 멈춘다(--source·--force 로 불러도 · 사용자 11-05)
            print(f'{rc.get("id")}: 꺼짐 — 건너뜀')
            continue
        if a.expire:                    # 받기가 없으니 계약 관문 앞
            judged = bool(expire(rc, run, a.dry)) and not a.dry or judged
            continue
        if not (rc.get('contract') or '').strip() and not a.dry:
            print(f'{rc.get("id")}: 수집 계약 없음 — 건너뜀')
            continue
        if a.rescue:                    # 글을 받을 수 있으니 스위치·계약 관문 뒤
            rescue(rc, a.id, run)
            judged = True
            continue
        if a.backfill:
            backfill(rc, run)
            continue
        if a.settle:
            if rc.get('filter'):
                settle(rc, run)
                judged = True
            continue
        try:
            judged = bool(expire(rc, run, a.dry)) and not a.dry or judged   # 보존 — 받기를 건너뛰는 날에도
        except Exception as e:      # 보존 하나가 받기를 세우지 않게
            queue(rc['id'], f'보존 예외 `{e!r}`'[:300])
        sp = os.path.join(STATE_DIR, rc['id'] + '.json')
        if not (a.force or a.dry or a.source) and os.path.exists(sp):
            d = json.load(open(sp, encoding='utf-8'))
            if time.time() - (d.get('last_run') or 0) < float(rc.get('recheck_hours', 20)) * 3600:     # 조리법 recheck_hours(기본 20) — lms-auto 가 15분마다 부른다
                continue
            if time.time() - (d.get('last_try') or 0) < 3600:       # 실패했으면 15분마다 두드리지 않고 한 시간 뒤
                continue
        if not a.dry:
            _, st0 = load_state(rc)
            st0['last_try'] = time.time()
            save_state(sp, st0)
        try:
            run_source(rc, run, a.dry)
            judged |= bool(rc.get('filter')) and not a.dry
            if auto_on(rc) and not a.dry:
                auto_extract(rc, run)
        except OSError as e:
            if isinstance(e, urllib.error.HTTPError):
                queue(rc['id'], f'받기 실패 `{e!r}`'[:300])
            else:
                log(f'{rc["id"]}: 망 오류 — 한 시간 뒤 다시 `{e!r}`'[:300])
        except Exception as e:
            queue(rc['id'], f'web-collect 예외 `{e!r}`'[:300])
    if judged:                          # 판정표·일정 파일 다시 쓰기(캐시만 · LLM 0) — 아침 반영에 필터를 잇는다
        learn()
        try:
            c = filt().judge(quiet=True)
            log('판정 갱신 — ' + ' · '.join(f'{k[0].rsplit("-", 1)[-1]} {k[1]} {n}' for k, n in sorted(c.items())))
        except Exception as e:
            queue('notice-filter', f'judge 예외 `{e!r}`'[:300])


if __name__ == '__main__':
    main()
