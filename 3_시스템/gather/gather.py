"""모아보기 — 파일 형식 «.moa» 하나 = 수집된 것을 한 화면에 모아 보는 정의(11-11 사용자 «본체의 기능 · 리본 없이 ·
클로드가 언제든 만들 수 있는 새로운 형식» · 모아보기 파일은 필요한 자리마다).

옵시디언에서 .moa 를 열면 brain-base 가 이 대본(view)을 불러 화면(view.html)에 그린다 — 3_시스템/views.json «formats».
보기는 LLM·구독 0: 수집 엔진 상태(3_시스템/_index/collect/<출처>.json)와 공지 필터(3_시스템/notice-filter.py)의 캐시 판정만 읽는다.
아무것도 쓰지 않는다.

  py -3 3_시스템/gather/gather.py sources              # 수집 출처(id · label · 볼트·대기 수) — 새 .moa 의 from 을 고를 때
  py -3 3_시스템/gather/gather.py check <파일.moa>      # 정의 검사 + 건수 대조(전부 = 보임 + 거름)
  py -3 3_시스템/gather/gather.py rows <파일.moa> [--all]  # 줄 JSON(--all = 거른 것도)
  py -3 3_시스템/gather/gather.py list                 # 볼트의 .moa 전부와 건수
  py -3 3_시스템/gather/gather.py view --file <볼트 경로>  # 화면 자료(마지막 줄 JSON · brain-base 가 부름)
공통: --today YYYY-MM-DD (시험용 · 없으면 오늘)

.moa 꼴(JSON · 칸 이름은 COLS):
  {"from": {"collect": {"label": "장학"}},       # 수집 출처 — label(조리법 filter.label) 또는 sources(출처 id 목록) · title = 제목 정규식(선택)
   "columns": ["꽁돈", "제목", "마감", "금액", "지급", "의무"],
   "sort": ["마감"],                             # 칸 이름 · 앞에 - 면 거꾸로 · 값 없음은 맨 뒤
   "hide": {"past": true, "verdict": ["비해당"]},  # 지난 것 · 판정(verdict 기본 = 비해당 · [] 면 다 보임)
   "strip": "^\\[[^\\]]*\\]\\s*",                # 보일 제목에서 뺄 글(선택)
   "widths": {"제목": 320, "마감": 120}}          # 칸 너비 px(선택 · 화면에서 머리 칸 끝을 끌면 생김 · 두 번 누르면 지움 · 40~2000)
  이름 = 파일 이름.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)
VAULT = os.path.dirname(SYS)
FILTER = os.path.join(SYS, 'notice-filter.py')
EXT = '.moa'
SKIP_DIRS = {'.git', '.obsidian', '.trash', '.claude', 'node_modules', '__pycache__'}

# 칸 — 이름 → (머리 글, 꼴)
COLS = {
    '꽁돈': ('', 'gold'),
    '제목': ('제목', 'title'),
    '마감': ('마감', 'date'),
    '금액': ('금액', 'text'),
    '지급': ('지급', 'text'),
    '의무': ('의무', 'list'),
    '판정': ('판정', 'text'),
    '출처': ('출처', 'text'),
    '날짜': ('올린 날', 'text'),
    '요약': ('요약', 'text'),
}

_nf = []


def nf():
    """공지 필터(이름에 - 가 있어 import 문으로 못 부른다) — 판정 함수만 쓴다(추출·쓰기는 안 부름)."""
    if not _nf:
        spec = importlib.util.spec_from_file_location('notice_filter', FILTER)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _nf.append(m)
    return _nf[0]


def load(rel):
    """정의 하나 — 볼트 경로 또는 절대 경로 · 깨지면 _err."""
    p = rel if os.path.isabs(rel) else os.path.join(VAULT, *rel.replace('\\', '/').split('/'))
    key = os.path.relpath(p, VAULT).replace('\\', '/')
    name = os.path.splitext(os.path.basename(p))[0]
    try:
        d = json.load(open(p, encoding='utf-8'))
        if not isinstance(d, dict):
            raise ValueError('JSON 객체가 아님')
    except Exception as e:
        return {'_key': key, 'name': name, '_err': f'정의를 못 읽음: {e}'}
    d['_key'], d['name'] = key, name
    return d


def everywhere():
    """볼트의 .moa 전부(이름 순) — 점 폴더·휴지통 밖."""
    out = []
    for root, dirs, files in os.walk(VAULT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS and not x.startswith('.')]
        out += [os.path.join(root, f) for f in files if f.endswith(EXT)]
    return sorted(out)


def sources(d):
    src = (d.get('from') or {}).get('collect') or {}
    ids, label = src.get('sources'), src.get('label')
    return [rc for rc in nf().recipes() if (ids and rc['id'] in ids) or (label and (rc.get('filter') or {}).get('label') == label)]


RULES = ('title', 'source', 'prop', 'extract', 'value', 'text', 'mine')


def mine_options(rules):
    """사람 입력 칸(«mine»: 값 목록)이면 그 목록 · 아니면 None."""
    for rule in rules if isinstance(rules, list) else [rules]:
        if isinstance(rule, dict) and isinstance(rule.get('mine'), list):
            return [str(x) for x in rule['mine']]
    return None


def show(v):
    """판정 캐시 값 → 읽는 글(목록 = ·, 사전 = «열쇠 값»)."""
    if isinstance(v, list):
        return '·'.join(show(x) for x in v)
    if isinstance(v, dict):
        return ' '.join(f'{k} {show(x)}' for k, x in v.items())
    return '' if v is None else str(v)


def front(path):
    """원문 md 속성 칸(앞 4KB · `열쇠: 값` 한 줄 꼴만) → dict."""
    try:
        head = open(path, encoding='utf-8', errors='replace').read(4096)
    except OSError:
        return {}
    m = re.match(r'---\r?\n(.*?)\r?\n---', head, re.S)
    out = {}
    for ln in (m.group(1).splitlines() if m else []):
        k, sep, v = ln.partition(':')
        if sep and k and not k.startswith(' '):
            out[k.strip()] = v.strip().strip('"\'')
    return out


def field_value(rules, row, n, c, rc, mine=None):
    """Claude 가 정의한 칸(.moa «fields») — 규칙을 차례로 해 보고 처음 나온 값.
    title = 제목 정규식(묶음 1 · 없으면 맞은 글) · source = 출처 이름(dict 면 바꿔 부름) · prop = 원문 속성 ·
    extract = 판정 캐시 칸(금액·요약 등) · value = 줄 id → 값(Claude 가 읽고 채움) · text = 고정 값 ·
    mine = 사람 입력 칸(값 목록 · 사람이 화면에서 고른 값 = .moa «mine»[칸][줄 id] · brain-base 가 씀)."""
    for rule in rules if isinstance(rules, list) else [rules]:
        v = None
        if 'mine' in rule:
            v = (mine or {}).get(row['id'])
        elif 'title' in rule:
            m = re.search(rule['title'], n['title'])
            v = (m.group(1) if m.groups() else m.group(0)) if m else None
        elif 'source' in rule:
            name = rc.get('name') or rc['id']
            v = rule['source'].get(name, rule['source'].get(rc['id'])) if isinstance(rule['source'], dict) else name
        elif 'prop' in rule:
            v = front(n['path']).get(rule['prop'])
        elif 'extract' in rule:
            v = (c or {}).get(rule['extract'])
        elif 'value' in rule:
            v = (rule['value'] or {}).get(row['id'])
        elif 'text' in rule:
            v = rule['text']
        if v not in (None, '', [], {}):
            return v if isinstance(v, (str, int, float, bool, list)) else json.dumps(v, ensure_ascii=False)
    return None


def names(d):
    """쓸 수 있는 칸 이름 — 기본 칸 + 이 정의의 fields."""
    return list(COLS) + [k for k in (d.get('fields') or {}) if k not in COLS]


def problems(d):
    """정의 검사 — 고칠 말 목록(빈 목록 = 됨)."""
    if d.get('_err'):
        return [d['_err']]
    bad = []
    src = (d.get('from') or {}).get('collect')
    if not isinstance(src, dict) or not (src.get('label') or src.get('sources')):
        bad.append('from.collect 에 label 또는 sources 가 필요')
    for k, rules in (d.get('fields') or {}).items():
        for rule in rules if isinstance(rules, list) else [rules]:
            if not isinstance(rule, dict) or len(rule) != 1 or next(iter(rule)) not in RULES:
                bad.append(f'칸 «{k}» 규칙은 {{{"|".join(RULES)}: …}} 하나씩')
            elif 'mine' in rule and not (isinstance(rule['mine'], list) and rule['mine'] and all(isinstance(x, str) and 0 < len(x) <= 20 for x in rule['mine'])):
                bad.append(f'칸 «{k}» mine 은 값 목록(글 20자 이하)')
            elif 'title' in rule:
                try:
                    re.compile(rule['title'])
                except re.error as e:
                    bad.append(f'칸 «{k}» 정규식 오류: {e}')
    ok = names(d)
    for c in d.get('columns') or []:
        if c not in ok:
            bad.append(f'모르는 칸 «{c}» — 칸: {" ".join(ok)}')
    for s in (d.get('sort') or []) + (d.get('filters') or []):
        if s.lstrip('-') not in ok:
            bad.append(f'정렬·필터에 모르는 칸 «{s}»')
    for k, pat in (('from.collect.title', (src or {}).get('title') if isinstance(src, dict) else None), ('strip', d.get('strip'))):
        if pat:
            try:
                re.compile(pat)
            except re.error as e:
                bad.append(f'{k} 정규식 오류: {e}')
    if not bad and not sources(d):
        bad.append('맞는 수집 출처가 없음 — gather.py sources 로 label·id 확인')
    return bad


def rows(d, today):
    """정의 → 줄 전부(거르기 전). 자리 = 볼트 글 + 대기 칸 글 · 보관 칸·장부 줄은 수집이 이미 뺀 것이라 없다."""
    m = nf()
    me = m.card()
    src = (d.get('from') or {}).get('collect') or {}
    tpat, strip = src.get('title'), d.get('strip')
    out = []
    for rc in sources(d):
        state = m.state_items(rc)
        sched = (rc.get('filter') or {}).get('schedule')
        for n in m.notices(rc['id']):
            if n['where'] == '보관 칸' or (tpat and not re.search(tpat, n['title'])):
                continue
            cp = m.cpath(n)
            c = json.load(open(cp, encoding='utf-8')) if os.path.exists(cp) else None
            res = []
            if c is not None:
                v, res = m.judge_one(n, c, me)
                g = m.gold(n, c, me, v)[0]
                dl = m.deadline(n, c)
                strong, weak = m.src_text(n)
                seen = lambda q: bool(m.norm(q or '')) and (m.norm(q) in strong or m.norm(q) in weak)  # noqa: E731
                pay = c.get('지급') or {}
                # None = 지급 칸 없이 뽑힌 글 · null = 돈 주는 공고가 아님 · 근거가 원문에 없으면 모름(꽁돈 판정과 같음)
                form = None if '지급' not in c else '없음' if c['지급'] is None else pay.get('형태') if seen(pay.get('근거')) else '모름'
                duty = list(dict.fromkeys(o.get('종류') for o in c.get('의무') or [] if o.get('종류') and o.get('종류') != '기타'))
            else:   # 아직 안 뽑은 글(대기 칸) — 제목 마감만 · 엔진이 적은 판정이 있으면 그것
                v = state.get(n['id'], {}).get('verdict') or '판정 대기'
                g, form, duty = None, None, []
                dl = m.title_deadline(rc, n['title'], n['date'])
            title = re.sub(strip, '', n['title']).strip() if strip else n['title']
            if n['where'] == '볼트':
                where = {'note': os.path.relpath(n['path'], VAULT).replace('\\', '/')}
            else:       # 볼트 밖 글 = 일정 줄([원문] 링크가 있는 곳)
                where = {'url': n['url'], **({'line': {'note': f'2_지식/일정/{sched}', 'find': f'^sch-{n["id"]}'}} if sched else {})}
            dn = None if not dl or dl == '0000-00-00' else (date.fromisoformat(dl) - today).days
            row = {
                'id': f'{rc["id"]}:{n["id"]}', '제목': title or n['title'], '출처': rc.get('name') or rc['id'], '날짜': n['date'],
                'open': where, '판정': v, '마감': None if dl == '0000-00-00' else dl, 'D': dn,
                '지남': bool(dl) and (dl == '0000-00-00' or dn < 0),
                '금액': (c or {}).get('금액'), '지급': form, '의무': duty, '꽁돈': g, '요약': (c or {}).get('요약'),
            }
            for k, rules in (d.get('fields') or {}).items():
                if k not in COLS:
                    row[k] = field_value(rules, row, n, c, rc, ((d.get('mine') or {}).get(k)))
            cc = c or {}
            row['세부'] = {   # 줄을 누르면 화면 안에서 펼치는 것 — 판정 캐시의 원문 인용 그대로(LLM 0)
                '요약': cc.get('요약'),
                '조건': [{'축': x[2].get('축'), '값': show(x[2].get('값')), '근거': x[2].get('근거'), '결과': x[0]}
                       for x in res if isinstance(x[2], dict) and x[2].get('축')],
                '지급': {'형태': form, '근거': (cc.get('지급') or {}).get('근거')} if form else None,
                '의무': [{'종류': o.get('종류'), '근거': o.get('근거')} for o in cc.get('의무') or []],
                '소득심사': (cc.get('소득심사') or {}).get('근거'),
                '첨부에만': bool(cc.get('첨부에만')),
                '자리': n['where'],
            }
            out.append(row)
    return out


def hidden(d, r):
    h = d.get('hide') or {}
    if h.get('past') and r['지남']:
        return '지남'
    if r['판정'] in h.get('verdict', ['비해당']):
        return r['판정']
    return None


def ordered(d, rs):
    for k in reversed(d.get('sort') or ['마감']):
        name, rev = k.lstrip('-'), k.startswith('-')
        has = [r for r in rs if r.get(name) not in (None, '', [])]
        has.sort(key=lambda r: str(int(r[name])) if isinstance(r[name], bool) else str(r[name]), reverse=rev)
        rs = has + [r for r in rs if r.get(name) in (None, '', [])]     # 값 없음은 늘 맨 뒤
    return rs


def build(d, today, keep_all=False):
    """화면 하나의 자료 — 보일 줄 · 거른 줄(«지난 것»을 누르면) · 수."""
    base = {'key': d['_key'], 'name': d.get('name'), 'today': today.isoformat()}
    bad = problems(d)
    if bad:
        return {**base, 'error': bad, 'columns': [], 'rows': [], 'gone': [], 'total': 0, 'hidden': {}}
    allr = rows(d, today)
    shown = [r for r in allr if keep_all or not hidden(d, r)]
    gone = [] if keep_all else [r for r in allr if hidden(d, r)]
    count = {}
    for r in gone:
        count[hidden(d, r)] = count.get(hidden(d, r), 0) + 1
    ok = names(d)
    cols = [c for c in d.get('columns') or ['제목', '마감'] if c in ok]
    fields = d.get('fields') or {}

    def head(c):
        if c in COLS:
            return {'id': c, 'head': COLS[c][0], 'kind': COLS[c][1]}
        opts = mine_options(fields.get(c))
        return {'id': c, 'head': c, 'kind': 'mine', 'options': opts} if opts else {'id': c, 'head': c, 'kind': 'text'}
    w = d.get('widths') if isinstance(d.get('widths'), dict) else {}
    widths = {c: int(w[c]) for c in cols if isinstance(w.get(c), (int, float)) and not isinstance(w.get(c), bool) and 40 <= w[c] <= 2000}
    return {**base, 'columns': [head(c) for c in cols], 'filters': [f for f in d.get('filters') or [] if f in ok],
            'sort': d.get('sort') or ['마감'], 'widths': widths,
            'rows': ordered(d, shown), 'gone': ordered(d, gone)[::-1][:50], 'total': len(allr), 'hidden': count}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['sources', 'check', 'rows', 'list', 'view'])
    ap.add_argument('path', nargs='?')
    ap.add_argument('--file')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--today')
    a = ap.parse_args()
    today = date.fromisoformat(a.today) if a.today else date.today()
    target = a.file or a.path
    if a.cmd == 'sources':
        for rc in nf().recipes():
            st = nf().state_items(rc)
            f = rc.get('filter') or {}
            vault = sum(1 for x in st.values() if x.get('path'))
            stage = sum(1 for x in st.values() if x.get('stage') and not x.get('path'))
            print(f'{rc["id"]}\t{rc.get("name")}\tlabel={f.get("label")}\tkind={f.get("kind")}\t볼트 {vault} · 대기 {stage}')
    elif a.cmd == 'list':
        for p in everywhere():
            b = build(load(p), today)
            print(f'{b["key"]}\t보임 {len(b["rows"])} · 전부 {b["total"]}' + (f'\t오류 {b["error"]}' if b.get('error') else ''))
    elif not target:
        sys.exit(f'{a.cmd}: .moa 파일을 주십시오')
    elif a.cmd == 'view':
        print(json.dumps(build(load(target), today), ensure_ascii=False))
    elif a.cmd == 'rows':
        print(json.dumps(build(load(target), today, keep_all=a.all), ensure_ascii=False, indent=1))
    elif a.cmd == 'check':
        d = load(target)
        bad = problems(d)
        if bad:
            print(json.dumps({'ok': False, 'problems': bad}, ensure_ascii=False))
            sys.exit(1)
        b = build(d, today)
        print(json.dumps({'ok': len(b['rows']) + sum(b['hidden'].values()) == b['total'], 'name': b['name'], 'shown': len(b['rows']),
                          'hidden': b['hidden'], 'total': b['total'], 'sources': [rc['id'] for rc in sources(d)]}, ensure_ascii=False))


if __name__ == '__main__':
    main()
