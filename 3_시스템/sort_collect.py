"""sort 의 «수집글» 대상 어댑터(범용 도구 셋 S3 · 2026-11-18) — 공지 필터(notice-filter.py)의 글·추출 캐시를 사실로 준다.

  사실: 제목 · 출처 · 날짜 · 자리 · 조리법(filter) · 본문지문 · 표시(헛것·쓸모) · 특징.notice(Claude 추출 캐시 그대로) ·
        꽁돈 칸(지급.형태·지급.근거 · 의무.종류 · 소득심사.반영) — 캐시에 «지급» 칸이 있을 때만(없으면 꽁돈 규칙이 «모름» → ④ 대기).
        지급.형태 는 근거 인용이 원문에 글자 그대로 있을 때만 그 값 · 없으면 «모름»(공지 필터 ② 근거 검사 그대로).
  등록 함수: judge = notice-filter judge_one 감싸기(체계 공지-들이기 · 세부 = 조건별 판정 그대로 넘김).
  자리(판정 단추): 출처 id(로그인 출처 글 칸은 그 조리법 id) — 수집 창 출처 줄의 «판정 N».
  옛 출력 다리(겹쳐 보이기): judge_one_from_ledger · gold_from_ledger — 판정표·일정 줄·수집 창 한 줄·moa 가 판정 장부에서 읽게.
    꽁돈 태그는 태그 도구(tag.has · S8 11-18)를 거친다 · 사람 태그(tag.apply) 뒤 다시 그리기 = refresh()(notice-filter judge).

잇기(S4 · 11-18): notice-filter.py bridge() 가 판정 전에 bridge() 를 한 번 부른다(sort.run + 다리 끼우기) · 스위치
  collect.local.json "sort": false = 옛 길 · sort 오류 = 그 회차 옛 길(notice-filter 가 받음). 다리는 장부에 없는 글·읽기 오류면 옛 함수로.
  골든 = _eval/sort_notice_golden.py(사본 위 · 이은 길 그대로).
"""
import copy
import hashlib
import importlib.util
import json
import os
import sys
from datetime import date

SYS = os.path.dirname(os.path.abspath(__file__))
if SYS not in sys.path:
    sys.path.insert(0, SYS)                      # sort · tag(겹쳐 보이기 읽기)
NF_PATH = os.path.join(SYS, 'notice-filter.py')
SYS_NOTICE, SYS_GOLD, TAG_GOLD = '공지-들이기', '꽁돈', '꽁돈'      # 옛 출력 다리가 읽는 체계·태그
_nf, _orig, MISSES, _pm = [], {}, [], []


def nf():
    if not _nf:
        spec = importlib.util.spec_from_file_location('notice_filter', NF_PATH)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _nf.append(m)
    return _nf[0]


def use(m):
    """공지 필터 모듈을 바꿔 끼움(사본 시험 — 자리를 임시 폴더로 돌린 모듈)."""
    _nf[:] = [m]
    _orig.clear()
    _pm.clear()


def orig(name):
    return _orig.get(name) or getattr(nf(), name)


def sha(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()


def _id(n):
    return f'collect:{n["sid"]}:{n["id"]}'


def items():
    m = nf()
    marks = m.load_marks()
    for n in m.notices():
        cp = m.cpath(n)
        d = json.load(open(cp, encoding='utf-8')) if os.path.exists(cp) else None
        f = {'제목': n['title'], '출처': n['sid'], '날짜': n['date'], '자리': n['where'], '조리법': n['rc'].get('filter') or {},
             '본문지문': sha(n['text'] + json.dumps(n['att'], ensure_ascii=False) + n.get('hint', '')),
             '표시': (marks.get(f'{n["sid"]}:{n["id"]}') or {}).get('평가')}
        if d is not None:
            f['특징'] = {'notice': d}
            if '지급' in d:
                strong, weak = m.src_text(n)
                seen = lambda q: bool(m.norm(q)) and (m.norm(q) in strong or m.norm(q) in weak)  # noqa: E731
                pay = d.get('지급') or {}
                f['지급'] = {'형태': pay.get('형태') if seen(pay.get('근거')) else '모름', '근거': pay.get('근거')}
                f['의무'] = {'종류': [o.get('종류') for o in d.get('의무') or []]}
                f['소득심사'] = {'반영': (d.get('소득심사') or {}).get('반영')}
        size = len(n['title']) + min(len(n['text']), 9000) + sum(len(t) for _, t in n['att'])
        yield {'id': _id(n), 'facts': f, 'raw': {'n': n, 'd': d}, '글자': size}


# ───────── 배우기(S5·S7 · sort_learn) ─────────
CLAUDE_FACTS = ('특징', '지급', '의무', '소득심사')     # Claude 추출이 있어야 생기는 칸 — 나머지(제목·출처·날짜·자리·조리법·표시)는 수집 때 이미 있음
LEARN = ('제목',)                                       # S5 후보 규칙이 볼 Claude 앞 글 칸(설계 §6 «제목만»)


def pre(item):
    """Claude 앞 대상 — 추출 칸을 뺀 사실 + 캐시 없음(judge 는 «모름»). 이것으로 못 정하던 판정 = «Claude 판정»(배울 자료)."""
    return {**item, 'facts': {k: v for k, v in item['facts'].items() if k not in CLAUDE_FACTS}, 'raw': {**item['raw'], 'd': None}}


def prepare():
    """엔진이 bridge 없이 이 어댑터를 돌릴 때(배우기 재생) — 카드를 공지 필터 것과 같게(bridge 와 같음)."""
    import sort
    sort.set_card(nf().card())


def text(item):
    """③ 낱말 통계의 글 = 제목 + 본문 앞 600자(측정 evalcls.py 와 같은 꼴)."""
    import re
    n = item['raw']['n']
    return (n['title'] or '') + '\n' + re.sub(r'\s+', ' ', n.get('text') or '')[:600]


def order(item):
    """시간 순 = 게시일 · 출처 · 글번호(측정 build.py 와 같은 차례)."""
    n = item['raw']['n']
    return (n.get('date') or '', n['sid'], str(n['id']))


def match(item, spec):
    """대상 칸 — 출처칸 = 조리법 경로(예 filter.gold) · 참 = 모든 글 · 글자 = 제목 정규식(공지 필터 gold_on 과 같음)."""
    import re
    n = item['raw']['n']
    for k, v in spec.items():
        if k == '출처칸':
            cur = n['rc']
            for seg in v.split('.'):
                cur = cur.get(seg) if isinstance(cur, dict) else None
            if not (cur is True or (isinstance(cur, str) and re.search(cur, n['title']))):
                return False
        elif k == '출처':
            if n['sid'] not in v:
                return False
        else:
            return False                 # 모르는 대상 칸 — 안 맞음(빼지 않는 쪽이 아니라 «판정 안 함» 쪽)
    return True


def skip_pending(item):
    """마감이 지난 글은 판정 대기에 안 올린다(옛 extract 와 같음 · 뽑아도 «지남»)."""
    n, d = item['raw']['n'], item['raw']['d']
    dl = nf().deadline(n, d or {})
    return bool(dl) and dl < date.today().isoformat()


def _posts_map():
    """로그인 출처 글 칸 sid → 그 조리법 id(판정 자리) — 한 번 읽어 둠(run 한 번에 대상마다 묻는다)."""
    if not _pm:
        m = nf()
        try:
            _pm.append({(rc.get('posts') or {}).get('sid'): rc['id'] for rc in m.cl.browser_recipes(SYS) if isinstance(rc.get('posts'), dict)})
        except Exception:
            _pm.append({})
    return _pm[0]


def place(item):
    sid = item['raw']['n']['sid']
    return _posts_map().get(sid, sid)


_outs = {}


def out_each(feats=()):
    """출력 토큰 중앙값 — 추출 캐시의 잰 값(없으면 None → 엔진 기본). 꽁돈 칸을 뽑는 글(feats 에 notice.gold)은 꽁돈 칸 캐시끼리 —
    11-18 묶음 시험: 꽁돈 칸 글 출력 ≈ 1,000 토큰 · 전체 중앙값 369 로 재면 예상이 2.7배 낮았다."""
    key = 'notice.gold' in (feats or ())
    if key not in _outs:
        m = nf()
        outs = []
        for f in os.listdir(m.CACHE) if os.path.isdir(m.CACHE) else []:
            if f.endswith('.json'):
                d = json.load(open(os.path.join(m.CACHE, f), encoding='utf-8'))
                if ('지급' in d) == key and (d.get('_tokens') or {}).get('out'):
                    outs.append(d['_tokens']['out'])
        outs.sort()
        _outs[key] = outs[len(outs) // 2] if outs else None
    return _outs[key]


def judge_cmds(where, rows, batch=1):
    """한 자리(출처)의 ④ = 옛 추출 단추 그대로(자격+꽁돈 칸을 한 지시문으로). 캐시가 있는데 특징이 모자란 글은 --again.
    batch > 1 = 묶어 부르기(같은 지시문 글을 한 호출에 · 체계 «묶음» · 기본 1 = 한 글 한 호출)."""
    src = {v: k for k, v in _posts_map().items()}.get(where, where)
    again = [tid.split(':', 2)[2] for tid, r in rows.items() if 'notice.자격' not in r['특징']]
    return [[sys.executable, NF_PATH, 'extract', '--source', src] + (['--again', *again] if again else []) + (['--batch', str(batch)] if batch > 1 else [])]


# ───────── 등록 함수 ─────────
def judge(item, env):
    """체계 공지-들이기 — notice-filter judge_one 그대로(빼도 된다는 근거가 있을 때만 뺀다). 캐시가 없으면 «모름» → ④(추출)."""
    n, d = item['raw']['n'], item['raw']['d']
    if d is None:
        return {'모름': '추출 전(조건 캐시 없음)'}
    m = nf()
    v, res = orig('judge_one')(n, copy.deepcopy(d), m.card())
    why = ' · '.join(dict.fromkeys(x[1] for x in res if x[0] in ('불충족', '모름', '관심')))[:160]
    return {'갈래': v, '근거': why, '세부': [list(x) for x in res]}


judge.files = [NF_PATH]          # 규칙 지문 — 공지 필터 대본이 바뀌면 기억을 안 씀


# ───────── 옛 출력 다리(겹쳐 보이기) ─────────
def judge_one_from_ledger(n, d, me):
    """판정 읽기 — 장부에 없는 글(이번 run 뒤에 뽑힘 등)·읽기 오류는 옛 judge_one(빗나감 = MISSES)."""
    try:
        import sort
        rec = sort.state_item(SYS_NOTICE, _id(n))
        if rec and rec.get('갈래') is not None and '세부' in rec:
            return rec['갈래'], [tuple(x) for x in rec['세부']]
    except Exception:
        pass
    MISSES.append(_id(n))
    return orig('judge_one')(n, d, me)


def gold_from_ledger(n, d, me, v):
    """꽁돈 태그 읽기(겹쳐 보이기 — 태그 도구 tag.has · S8 11-18) — 보이는 판정(v)이 꽁돈 체계의 대상 갈래일 때만(판정표의 «· 마감 지남» 줄은 안 붙임 = 옛 gold 와 같음).
    공지-들이기가 아직 못 본 글·읽기 오류는 옛 gold(판정 읽기와 같은 길로)."""
    try:
        import sort
        if not sort.state_item(SYS_NOTICE, _id(n)):
            return orig('gold')(n, d, me, v)
        allow = ((sort.systems().get(SYS_GOLD) or {}).get('대상') or {}).get('체계', {}).get(SYS_NOTICE) or []
        if v not in allow:
            return None, ''
        import tag
        return tag.has(_id(n), TAG_GOLD)
    except Exception:
        MISSES.append(_id(n))
        return orig('gold')(n, d, me, v)


def refresh():
    """태그 도구가 사람 태그(tag.apply «이거 꽁돈»)를 적은 뒤 겹쳐 보이기를 다시 그림 — notice-filter judge(판정표·일정 줄·세션 줄 · LLM 0 · 15분 확인과 같은 길).
    수집 창 한 줄은 다음 받기 정리(settle) 때 · 모아보기는 열 때 지금 판정을 읽는다."""
    import subprocess
    r = subprocess.run([sys.executable, NF_PATH, 'judge'], cwd=os.path.dirname(SYS), capture_output=True, text=True, encoding='utf-8',
                       errors='replace', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    return f'notice-filter judge rc={r.returncode}'


def install(m, old=None):
    """공지 필터 모듈의 판정·꽁돈을 판정 장부 읽기로 바꿔 끼운다. old = 옛 함수 {judge_one, gold}(주면 그것 · 두 번 끼워도 다리가 다리를 안 부름)."""
    use(m)
    if old:
        _orig.update(old)
    elif m.judge_one is not judge_one_from_ledger:
        _orig['judge_one'], _orig['gold'] = m.judge_one, m.gold
    m.judge_one, m.gold = judge_one_from_ledger, gold_from_ledger


def bridge(m, old):
    """notice-filter 잇기(S4) — 끼우고 수집글 체계를 sort.run 한 번. 오류는 부르는 쪽이 받아 옛 길로(수집은 안 멈춤). 돌려줌 = run 요약."""
    import sort
    install(m, old)
    sort.set_card(m.card())
    ids = [k for k, s in sort.systems().items() if not s.get('_err') and (s.get('대상') or {}).get('종류') == '수집글']
    return sort.run(ids)
