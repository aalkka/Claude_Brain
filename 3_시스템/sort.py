"""분류 엔진 sort — 대상 × 체계 → 갈래 하나 + 근거 + 판정자 (범용 도구 셋 S1 · 2026-11-18 · 설계 = 제작자 설계 노트(배포판에 없음) §2~§4).

분류는 결정만 한다. 태그·알림·들이기·장부는 판정 기록의 «동작»을 넘김 장부(넘김.jsonl)에 적어 넘기고 직접 하지 않는다.
체계 = 3_시스템/sort/<체계>.json(개인 층 · 배포판 빈 틀 = 3_시스템/sort-examples/) · 규칙마다 «말»(사용자 말 원문)과 기계 꼴이 같은 줄.
판정 사다리 ① 기억(같은 지문의 지난 판정) → ② 코드 규칙(차례로 · 처음 맞은 규칙 · 조건 · 표 · 등록 함수) →
          ③ 낱말 통계(갈고리만 · S7) → ④ Claude(갈고리만 · 판정 대기에 올림 · 부르지 않음 · S4).
장부 = 3_시스템/_index/sort/판정.jsonl(바뀐 판정만 덧붙임) · 지금 상태 = _index/sort/<체계>.json · 넘김 = _index/sort/넘김.jsonl.

조건 낱말(설계 §4): 잎 {"칸": <사실 경로 | @값 | @카드.<칸> | 체계.<id> | {"빼기": [a, b]}>, <낱말>: 값}
    낱말 = 같음 아님 안에 겹침 포함 맞음 초과 이상 미만 이하 사이 있음 모름 · 묶음 = 모두 하나라도 아님 늘 · 오른쪽 «@…» = 참조.
    칸이 사실에 없으면 그 잎은 «모름» → 규칙 단계 전체가 모름(다음 규칙으로 넘어가지 않는다 — 뒤의 «늘» 규칙이 잘못 걸리지 않게).
규칙 꼴: {"조건", "갈래", "근거"(틀 · {칸} {칸|기본} {칸:글자수} {겹침})} · {"표": {"점수", "가둠", "갈래"}} · {"함수": "모듈.이름"(+ 조건 = 문지기)}.
    함수 = f(대상, 환경) → None(다음 규칙) · {"모름": 까닭} · {"갈래", "근거", "세부"?, "급함"?}.

  py -3 3_시스템/sort.py check [--dir <폴더>]           # 체계 파일 검사(말·조건 낱말·참조·갈래·동작·함수·의존 고리)
  py -3 3_시스템/sort.py rules <체계>                   # 사람이 읽는 규칙 표 + 맞은 수
  py -3 3_시스템/sort.py run [--system <체계>…] [--dry]  # 사다리 ①② · ③④ 갈고리 · 사용량 0
  py -3 3_시스템/sort.py preview --dir <고친 체계 폴더 사본>   # 규칙 바꿈 재생 대조 — 지금 판정에서 갈래가 바뀌는 대상(쓰지 않음 · 적기 전에 보임)
  py -3 3_시스템/sort.py pending [--place <자리>]       # 판정 대기 — 자리별 수 · 자리를 주면 대상(한 대상 한 호출) · 예상 사용량(설계 §5 식)
  py -3 3_시스템/sort.py judge --place <자리> [--yes]   # 한 자리의 판정 단추(자리 = 수집글 출처 id · 홈) — 대상 종류의 옛 길로 넘김
                                                     #   (수집글 = notice-filter extract --source) · --yes 없으면 계획만 · 전역 단추 없음(사용자 11-18)
                                                     #   종료 0 = 됨 · 2 = 부른 길이 실패 · 3 = 부르기 전 엔진 오류(부르는 쪽이 옛 길로)
  py -3 3_시스템/sort.py events [--all]                 # 알림 줄 사건(자동 채택·가격선 바뀜 …) — 열린 것만 · --all = 닫힌 것도
  py -3 3_시스템/sort.py ack <사건 id>                   # 알림 «확인» — 그 체계가 걸린 자리 모두에서 닫힘
  py -3 3_시스템/sort.py revert <사건 id>                # 알림 «되돌리기» — 사건의 되돌리기(규칙 끔 · 값 되돌림)를 체계 파일에 · 다시 run
  py -3 3_시스템/sort.py revert --system <체계> --rule <규칙>   # 규칙 줄 «되돌리기» — 자동 규칙만(사람 규칙은 말로 고침)

S4(11-18 · 초안 B): run 이 자리 요약 _index/sort/자리.json(자리별 판정 대기 · 체계별 맞은 수)을 쓰고 수집 창이 읽는다 · 사건 = _index/sort/사건.jsonl
  (내는 쪽 = S5 자동 채택 · S2 가격선 — 아직 없음 · 꼴만) · 묶어 부르기 = 체계 «묶음»(1~6 · 기본 1 = 끔 · 한 호출 입력 12k 토큰 안).
S5·S7(11-18 · sort_learn.py): 체계 «자동채택»: "끔"(기본) | "그림자" — 코드 규칙 후보를 그림자로만 대 봄(진짜 판정·체계 파일을 안 바꿈) ·
  «사다리.통계»: false(기본 · 11-18 보스) | "그림자"(예측만 적고 나중 판정과 대조) | true(③ 이 정함). 둘 다 끄면 sort_learn 을 읽지도 않는다.
  py -3 3_시스템/sort.py learn [<체계>] [--replay]      # 배우기 상태(후보·연속·문턱·대조) · --replay = 지금 판정을 시간 순으로 다시 흘려 그림자 흉내(안 씀)
  py -3 3_시스템/sort.py revert --system <체계> --rule <후보 id>   # 그림자 후보 «거부»(다시 후보로 안 올림)
S8·S9(11-18): 넘김 장부를 읽는 동작 도구 = 태그 tag.py(겹쳐 보이기 읽기 tag.has · «노트에 쓰기» 켠 체계만 프론트매터 · tag.apply → answer) ·
  알림 = mobility 모듈 .claude/skills/mobility/scripts/alert.py(넘김의 알림 줄 → 때·중복 → 폰 · 11-18 «알림도구를 mobility 주관으로») — mobility 가 켜졌을 때만 부름 ·
  수집 창 «일어난 일»은 넘김의 알림 줄(자리·제목)을 직접 읽는다. answer(체계, 대상, 갈래, 판정자) = 사람·대화 Claude 판정 하나.
"""
import argparse
import copy
import hashlib
import importlib
import importlib.util
import inspect
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter

SYS = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(SYS)
SYSTEMS = os.path.join(SYS, 'sort')                 # 개인 층 체계 파일
EXAMPLES = os.path.join(SYS, 'sort-examples')       # 배포판 빈 틀
INDEX = os.path.join(SYS, '_index', 'sort')         # 장부·상태·넘김(볼트 지식층 밖)
_REAL_INDEX = INDEX                                 # 분류 직후 알림(ALERT_AFTER)은 이 자리일 때만 — 시험이 INDEX 를 임시로 바꾸면 안 부름(진짜 폰에 안 감)
ALERT_AFTER = True                                  # 11-18 즉시 알림: run 이 알림 동작을 넘기면 그 자리에서 알림 도구를 한 번(15분 확인을 기다리지 않음)
LAST_ALERT = None                                   # 마지막 분류 직후 알림 돌림의 결과(alert.run 요약 · 오류 글)
_RUN_ALERTS = [0]

ADAPTERS = {'수집글': 'sort_collect', '가격줄': 'sort_price'}   # 대상 종류 → 어댑터 모듈(3_시스템/<모듈>.py) · 가격줄 = S2(11-18 · 체계는 켬 false)
                                                     # 받은함(S6)은 체계가 아니라 장부 그림자(sort_inbox.py) — 어댑터 없음
LEAF = ('같음', '아님', '안에', '겹침', '포함', '맞음', '초과', '이상', '미만', '이하', '사이', '있음', '모름')
GROUP = ('모두', '하나라도', '아님', '늘')
ACTS = ('태그', '알림', '들이기', '장부', '옮기기')
WHEN = re.compile(r'^(바로|아침|묶음 \d\d:\d\d)$')
LADDER = {'기억': True, '규칙': True, '통계': False, 'claude': '버튼'}      # 체계 «사다리» 기본(설계 §3 · ③ 은 11-18 보스 «체계 칸 기본 끔»)
CLAUDE_MODES = ('버튼', '자동', '끔')
ADOPT_MODES = ('끔', '그림자')                       # S5 자동 채택 — 진짜 채택(체계 파일에 규칙)은 그림자 통과 뒤 사용자 결정
KEYS = ('id', '이름', '판', '켬', '끝', '설명', '대상', '특징', '값', '카드기본', '규칙', '갈래', '모르면', '사다리', '보기', '캘린더', '모델', '자리', '묶음',
        '자동채택', '노트에 쓰기')
NO_PRINT = ('자동채택', '노트에 쓰기')                # 규칙 지문에서 뺌 — 그림자 스위치·태그 자리(S8 tag.py)를 켜고 꺼도 규칙 판정 기억을 버리지 않게
BATCH_MAX, BATCH_IN = 6, 12000                        # 묶어 부르기 — 한 호출 최대 대상 수 · 입력 토큰 상한(설계 §5) · 체계 «묶음» 기본 1(끔 · 질 시험 전)
ASKED = ('claude', '대화', '사람')                    # ④ 판정 — 입력이 같으면 규칙을 고쳐도 다시 묻지 않는다(규칙 지문을 안 봄)
# 판정 버튼 예상(설계 §5 · 11-18 잰 값 · 공지 추출 캐시 76건 · sonnet --effort low): 입력 토큰 ≈ 고정 2,787 + 0.324 × 글자
FIXED_IN, PER_CHAR, OUT_EACH = 2787, 0.324, 370      # OUT_EACH = 공지 캐시 출력 중앙값 369(11-18) — 어댑터가 잰 값을 주면 그것
PRICE = {'sonnet': (2.0, 10.0), 'opus': (4.0, 20.0)}  # 100만 토큰당 $ 입력·출력(기억 «사용량 환산 무게» 11-11 가격표)
WEEK_PCT_USD = 14.1                                    # 주간 1% ≈ API 환산 $14.1(같은 기억 · 맞춤값이라 «≈»)


class _Missing:
    def __repr__(self):
        return '모름'


MISSING = _Missing()       # 사실에 없는 칸(값 None 과 다름)


def canon(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)


def num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def walk(d, path):
    cur = d
    for seg in path.split('.'):
        if isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            return MISSING
    return cur


# ───────── 체계 파일 ─────────
_systems = {}


def load_systems(d=None):
    d = d or SYSTEMS
    if d in _systems:
        return _systems[d]
    out = {}
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith('.json'):
            continue
        p = os.path.join(d, f)
        try:
            s = json.load(open(p, encoding='utf-8'))
            if not isinstance(s, dict):
                raise ValueError('JSON 객체가 아님')
        except ValueError as e:
            s = {'_err': f'못 읽음: {e}'}
        s['_file'] = p
        out[f[:-5]] = s
    _systems[d] = out
    return out


def systems():
    return load_systems(SYSTEMS)


def system_core(s):
    return {k: v for k, v in s.items() if not k.startswith('_')}


# ───────── 카드(@카드.<칸>) ─────────
_card = []


def card():
    """자격 카드 JSON — 없으면 빈 카드(@카드 참조는 «모름»)."""
    if not _card:
        try:
            sys.path.insert(0, SYS)
            import roles
            p = roles.find_note('자격-카드') or roles.path('notes', '자격-카드.md')
            t = open(os.path.join(VAULT, *p.split('/')), encoding='utf-8').read()
            _card.append(json.loads(re.search(r'```json\s*(\{.*?\})\s*```', t, re.S).group(1)))
        except Exception:
            _card.append({})
    return _card[0]


def set_card(d):
    _card[:] = [d]


def card_view(s):
    """카드 + 체계 «카드기본»(카드 칸이 없거나 빈 열쇠를 채움 · 카드가 이김 — 공지 필터 GOLD_DEFAULT 와 같은 얕은 합침)."""
    base = card()
    extra = s.get('카드기본') or {}
    if not extra:
        return base
    out = dict(base)
    for k, dv in extra.items():
        out[k] = {**dv, **(base.get(k) or {})} if isinstance(dv, dict) else base.get(k, dv)
    return out


# ───────── 조건 언어 ─────────
def value_of(spec, env):
    """체계 «값» 하나 — {"기본", "기간": [{"걸침": [a, b], "값"}], "걸침칸": [시작 칸, 끝 칸]} 이면 대상 기간에 걸친 값."""
    if not (isinstance(spec, dict) and '기본' in spec):
        return spec
    per = spec.get('기간') or []
    if per:
        span = [resolve(c, env) for c in spec.get('걸침칸') or []]
        if len(span) != 2 or any(x is MISSING for x in span):
            return MISSING
        for p in per:
            a, b = p['걸침']
            if str(span[0]) <= str(b) and str(span[1]) >= str(a):
                return p['값']
    return spec['기본']


def resolve(ref, env):
    if isinstance(ref, dict):
        if isinstance(ref.get('빼기'), list) and len(ref['빼기']) == 2:
            a, b = (resolve(x, env) for x in ref['빼기'])
            return a - b if num(a) and num(b) else MISSING
        return MISSING
    if not isinstance(ref, str):
        return ref
    if ref.startswith('@카드.'):
        return walk(env.get('카드') or {}, ref[4:])
    if ref.startswith('@'):
        vals = env.get('값') or {}
        return value_of(vals[ref[1:]], env) if ref[1:] in vals else MISSING
    if ref.startswith('체계.'):
        return (env.get('체계') or {}).get(ref[3:], MISSING)
    return walk(env.get('사실') or {}, ref)


def operand(x, env):
    if isinstance(x, dict) or (isinstance(x, str) and x.startswith('@')):
        return resolve(x, env)
    return x


def _test(op, v, x, bind):
    if op == '같음':
        return v == x
    if op == '아님':
        return v != x
    if op == '안에':
        return (v in x) if isinstance(x, (list, tuple, str)) else None
    if op == '겹침':
        if not isinstance(x, (list, tuple)):
            return None
        hit = []
        for i in (v if isinstance(v, list) else [v]):
            try:
                if i in x and i not in hit:
                    hit.append(i)
            except TypeError:
                pass
        bind['겹침'] = hit
        return bool(hit)
    if op == '포함':
        try:
            return x in v
        except TypeError:
            return False
    if op == '맞음':
        return re.search(str(x), v if isinstance(v, str) else canon(v)) is not None
    if op in ('초과', '이상', '미만', '이하', '사이'):
        lo_hi = x if op == '사이' else [x]
        if not (isinstance(lo_hi, (list, tuple)) and all((num(v) and num(y)) or (isinstance(v, str) and isinstance(y, str)) for y in lo_hi)):
            return None
        if op == '사이':
            return lo_hi[0] <= v <= lo_hi[1]
        return {'초과': v > x, '이상': v >= x, '미만': v < x, '이하': v <= x}[op]
    if op == '있음':
        return bool(v) == bool(x)
    raise ValueError(f'모르는 낱말 «{op}»')


def leaf(c, env, bind):
    v = resolve(c['칸'], env)
    out = True
    for op, x in c.items():
        if op == '칸':
            continue
        if op == '모름':
            r = (v is MISSING) == bool(x)
        elif v is MISSING:
            r = None
        else:
            x = operand(x, env)
            if op == '사이' and isinstance(x, list):            # ["@하한", "@상한"] — 끝마다 참조(11-18 · S2 요청)
                x = [operand(y, env) for y in x]
                x = MISSING if any(y is MISSING for y in x) else x
            r = None if x is MISSING else _test(op, v, x, bind)
        if r is False:
            return False
        if r is None:
            out = None
    return out


def cond(c, env, bind=None):
    """조건 → True · False · None(모름)."""
    bind = {} if bind is None else bind
    if '칸' in c:
        return leaf(c, env, bind)
    if '늘' in c:
        return bool(c['늘'])
    if '모두' in c:
        rs = [cond(x, env, bind) for x in c['모두']]
        return False if False in rs else (None if None in rs else True)
    if '하나라도' in c:
        rs = [cond(x, env, bind) for x in c['하나라도']]
        return True if True in rs else (None if None in rs else False)
    if '아님' in c:
        r = cond(c['아님'], env, bind)
        return None if r is None else not r
    raise ValueError(f'모르는 조건 {canon(c)[:80]}')


TPL = re.compile(r'\{([^{}|:]+)(?::(\d+))?(?:\|([^{}]*))?\}')


def fill(t, env, bind):
    """근거 틀 — {칸} · {칸|기본}(값이 비면) · {칸:30}(앞 30자) · {겹침}(겹침 낱말이 찾은 것 · 로 이음)."""
    def one(m):
        name, cut, dflt = m.group(1).strip(), m.group(2), m.group(3)
        v = bind[name] if name in bind else resolve(name, env)
        if v is MISSING or v in (None, '', [], {}):
            v = dflt if dflt is not None else ''
        if isinstance(v, list):
            v = '·'.join(map(str, v))
        s = str(v)
        return s[:int(cut)] if cut else s
    return TPL.sub(one, t)


def ref_label(r):
    return '−'.join(map(ref_label, r['빼기'])) if isinstance(r, dict) and '빼기' in r else str(r)


def table(t, env):
    """표 규칙 → (갈래 | None, 근거). 단계 = [[문턱, 점수]…] 오름차순 · 값 이상인 마지막 문턱 · 더하기 = {값: 점수}."""
    score, parts = 0, []
    for p in t['점수']:
        v = resolve(p['칸'], env)
        name = ref_label(p['칸'])
        if v is MISSING:
            return None, f'{name} 모름'
        if '단계' in p:
            add = None
            for thr, step in p['단계']:
                if num(v) and v >= thr:
                    add = step
            if add is None:
                return None, f'{name}={v} 단계 밖'
        else:
            key = v if isinstance(v, str) else canon(v)
            if key not in p['더하기']:
                return None, f'{name}={v} 표에 없음'
            add = p['더하기'][key]
        score += add
        parts.append(f'{name}={v}→{add:+d}')
    lo, hi = t.get('가둠') or [score, score]
    score = max(lo, min(hi, score))
    g = (t.get('갈래') or {}).get(str(score))
    why = '표 ' + ' · '.join(parts) + f' = {score}'
    return (g, why) if g else (None, why + ' 갈래 없음')


# ───────── 등록 함수 ─────────
_funcs = {}


def func(name):
    if name not in _funcs:
        mod, _, attr = name.rpartition('.')
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        try:
            m = sys.modules.get(mod) or importlib.import_module(mod)
        except ImportError:
            p = os.path.join(SYS, mod.replace('_', '-') + '.py')         # notice_filter → notice-filter.py(이름에 - 가 있는 대본)
            spec = importlib.util.spec_from_file_location(mod, p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
        _funcs[name] = getattr(m, attr)
    return _funcs[name]


def func_files(fn):
    return [inspect.getfile(fn)] + list(getattr(fn, 'files', []))


def file_hash(p):
    try:
        return hashlib.sha1(open(p, 'rb').read()).hexdigest()
    except OSError:
        return '없음'


# ───────── 사다리 ─────────
def fingerprint(s, item, env):
    """(입력 지문, 규칙 지문). 입력 = 판 + 사실 + 앞 체계 갈래 + 카드(쓰면). 규칙 = 체계 파일 전체 + 등록 함수 대본."""
    core = {k: v for k, v in system_core(s).items() if k not in NO_PRINT}
    uses_card = '@카드' in canon(core) or any('함수' in r for r in s.get('규칙') or [])
    h = hashlib.sha1(canon([s.get('판', 1), item['facts'], env.get('체계') or {}, card_view(s) if uses_card else None]).encode('utf-8'))
    files = sorted({f for r in s.get('규칙') or [] if '함수' in r for f in func_files(func(r['함수']))})
    r = hashlib.sha1(canon([core, [file_hash(f) for f in files]]).encode('utf-8'))
    return 'sha1:' + h.hexdigest(), 'sha1:' + r.hexdigest()


def rules_eval(s, env, item):
    for r in s.get('규칙') or []:
        if r.get('켬') is False:
            continue
        bind = {}
        if '조건' in r:
            ok = cond(r['조건'], env, bind)
            if ok is None:
                return {'모름': f'{r["id"]} 조건에 모르는 칸'}
            if not ok:
                continue
            if '표' not in r and '함수' not in r:
                return {'갈래': r['갈래'], '근거': fill(r.get('근거') or r.get('말') or '', env, bind), '규칙': r['id']}
        if '표' in r:
            g, why = table(r['표'], env)
            return {'모름': f'{r["id"]} {why}'} if g is None else {'갈래': g, '근거': why, '규칙': r['id']}
        if '함수' in r:
            out = func(r['함수'])(item, env)
            if out is None:
                continue
            if '모름' in out:
                return {'모름': f'{r["id"]} {out["모름"]}'}
            return {**out, '규칙': r['id']}
    return {'모름': '맞는 규칙 없음'}


def stats_hook(s, item, env, fps=None, mode=True):
    """③ 낱말 통계(S7 — 글자 2~4-gram TF-IDF + 로지스틱 · 정밀도 98% 문턱 안만 · sort_learn). 켬이면 정한 것 · 그림자면 늘 None(예측은 적어 둠)."""
    import sort_learn
    return sort_learn.stats_hook(s, item, env, fps or ('', ''), mode)


def learn_on(s):
    lad = {**LADDER, **(s.get('사다리') or {})}
    return s.get('자동채택', '끔') == '그림자' or lad['통계'] in ('그림자', True)


def record(s, item, out, who, fps, now):
    g = out['갈래']
    acts = copy.deepcopy(((s.get('갈래') or {}).get(g) or {}).get('동작') or [])
    urgent = next((a['알림'].get('급함') for a in acts if isinstance(a.get('알림'), dict) and isinstance(a['알림'].get('급함'), bool)), None)
    if isinstance(out.get('급함'), bool):
        urgent = out['급함']
    rec = {'대상': item['id'], '체계': s['id'], '판': s.get('판', 1), '갈래': g, '판정자': who, '규칙': out.get('규칙'),
           '근거': out.get('근거', ''), '급함': urgent, '동작': acts, '시각': now, '지문': fps[0], '규칙지문': fps[1]}
    if '세부' in out:
        rec['세부'] = out['세부']
    return rec


def decide(s, item, env, prev, now):
    """한 대상 → ('memory' | 'rule' | 'stats' | 'unknown', 기록) 또는 ('pending', 대기 줄)."""
    lad = {**LADDER, **(s.get('사다리') or {})}
    fps = fingerprint(s, item, env)
    if lad['기억'] and prev and prev.get('지문') == fps[0] and (prev.get('판정자') in ASKED or prev.get('규칙지문') == fps[1]):
        return 'memory', prev
    out = rules_eval(s, env, item) if lad['규칙'] else {'모름': '규칙 단계 꺼짐'}
    if '갈래' in out:
        return 'rule', record(s, item, out, '규칙', fps, now)
    if lad['통계'] in ('그림자', True):
        hit = stats_hook(s, item, env, fps, lad['통계'])
        if hit and lad['통계'] is True:
            return 'stats', record(s, item, hit, '통계', fps, now)
    if lad['claude'] in ('버튼', '자동'):
        return 'pending', {'까닭': out['모름'], '특징': (s.get('특징') or {}).get('claude'), '글자': item.get('글자', 0), '지문': fps[0], '시각': now}
    return 'unknown', record(s, item, {'갈래': s['모르면'], '근거': out['모름'], '규칙': None}, '모르면', fps, now)


# ───────── 상태·장부·넘김 ─────────
_state = {}


def state(sid):
    if sid not in _state:
        p = os.path.join(INDEX, sid + '.json')
        _state[sid] = json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {'items': {}, '대기': {}}
    return _state[sid]


def state_item(sid, tid):
    return state(sid)['items'].get(tid)


def reset():
    """메모리 캐시를 비운다(시험 · INDEX·SYSTEMS 를 바꾼 뒤)."""
    _state.clear()
    _systems.clear()
    _funcs.clear()


def write_json(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(p + '.tmp', p)


def append_lines(p, rows):
    if rows:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'a', encoding='utf-8', newline='\n') as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)


def tags(rec):
    return [a['태그'] for a in (rec or {}).get('동작') or [] if '태그' in a]


def handoff(prev, new, now):
    """동작 넘김(«지금 판정에 맞추기» · 멱등) — 태그는 붙임·뗌 차이만 · 그 밖 동작은 갈래가 바뀔 때만(중복 알림 막기는 알림 도구 몫)."""
    rec = new or prev
    base = {'시각': now, '대상': rec['대상'], '체계': rec['체계']}
    pt, nt = tags(prev), tags(new)
    ev = [{**base, '동작': {'떼기': t}} for t in pt if t not in nt] + [{**base, '동작': {'태그': t}} for t in nt if t not in pt]
    if new and (not prev or prev.get('갈래') != new['갈래']):
        ev += [{**base, '갈래': new['갈래'], '급함': new.get('급함'), '동작': a} for a in new['동작'] if '태그' not in a]
    return ev


def handoffs(pos=0, from_start=False):
    """넘김 장부를 읽는 동작 도구(tag.py · alert.py)의 한 길 — 커서(바이트) 뒤의 끝난 줄만 → (줄 목록, 새 커서).
    장부가 커서보다 짧아졌으면(새로 만듦) 처음부터. 쓰다 만 마지막 줄은 다음 번에."""
    p = os.path.join(INDEX, '넘김.jsonl')
    try:
        size = os.path.getsize(p)
    except OSError:
        return [], 0
    pos = 0 if from_start or not isinstance(pos, int) or pos > size else pos
    with open(p, 'rb') as f:
        f.seek(pos)
        data = f.read()
    end = data.rfind(b'\n') + 1
    rows = []
    for ln in data[:end].splitlines():
        try:
            e = json.loads(ln.decode('utf-8'))
        except ValueError:
            continue
        if isinstance(e, dict) and e.get('체계') and e.get('대상') and isinstance(e.get('동작'), dict):
            rows.append(e)
    return rows, pos + end


def ledger_line(rec):
    return {k: v for k, v in rec.items() if k not in ('세부', '규칙지문')}


def changed(prev, new):
    return not prev or any(prev.get(k) != new.get(k) for k in ('갈래', '근거', '규칙', '판정자'))


def tag_of(tid, tag):
    """옛 이름 — 태그 도구 tag.has 로 넘김(S8 · 11-18 · 겹쳐 보이기 읽기는 태그 도구 한 곳)."""
    if SYS not in sys.path:
        sys.path.insert(0, SYS)
    import tag as _tag
    return _tag.has(tid, tag)


# ───────── 어댑터 ─────────
_adapters = {}


def register_adapter(kind, obj):
    _adapters[kind] = obj


def adapter(kind):
    if kind not in _adapters:
        if kind not in ADAPTERS:
            return None
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        _adapters[kind] = importlib.import_module(ADAPTERS[kind])
    return _adapters[kind]


def deps_of(s):
    return dict((s.get('대상') or {}).get('체계') or {})


def topo(S):
    """의존(대상.체계) 한 겹 순서 · 고리에 걸린 체계는 빠진다(check 가 막음)."""
    order, left = [], {k: set(deps_of(s)) & set(S) for k, s in S.items()}
    while True:
        ready = sorted(k for k, d in left.items() if not d)
        if not ready:
            return order, sorted(left)
        for k in ready:
            order.append(k)
            del left[k]
        for d in left.values():
            d.difference_update(ready)


def _lock():
    """run 겹침 막기(15분 확인 · 정리 · 모아보기가 한꺼번에 돌 때) — 쥐면 열린 파일 · 남이 쥐고 있으면 None(그 회차는 셈만 하고 안 씀)."""
    os.makedirs(INDEX, exist_ok=True)
    f = open(os.path.join(INDEX, 'run.lock'), 'a+')
    try:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return f
    except OSError:
        f.close()
        return None


def write_if_changed(p, d):
    try:
        if canon(json.load(open(p, encoding='utf-8'))) == canon(d):
            return False
    except (OSError, ValueError):
        pass
    write_json(p, d)
    return True


PLACES = '자리.json'       # 자리 요약 — 수집 창 «판정 N»·규칙 칸이 읽는다(엔진·어댑터를 안 부르고)
DECIDED, LEARNED = {}, {}  # 마지막 run 의 체계별 (대상, 환경, 판정) · 배우기 요약(run 의 돌려줌에는 안 넣음 — 골든·수집 창이 보는 꼴 그대로)


def write_places(per, now):
    """자리 요약 = {"체계": {체계: {자리: {대기, 판정, 맞은{규칙: n}, 갈래{규칙: {갈래: n}}}}}, "판정": {자리: 대상 수}}. 이번에 돈 체계만 바꿔 끼운다."""
    p = os.path.join(INDEX, PLACES)
    try:
        old = json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError):
        old = {}
    live = set(systems())
    body = {k: v for k, v in (old.get('체계') or {}).items() if k in live and k not in per}
    body.update(per)
    d = {'체계': body, '판정': places()}
    if canon({k: v for k, v in old.items() if k != '시각'}) != canon(d):
        write_json(p, {'시각': now, **d})
    else:
        os.utime(p)                        # 내용은 같아도 «지금 것» 표시(수집 창이 엔진 상태보다 새것인지 본다)


def preview(d):
    """규칙 바꿈 재생 대조(설계 §4 · Gmail «이 검색으로 필터 만들기» 자리 · S8 11-18) — 고친 체계 폴더 d(사본)로 run 을 쓰지 않고 돌려
    지금 판정에서 갈래가 바뀌는 대상 [{체계, 대상, 전, 후, 근거}] 을 낸다. 장부·상태·넘김·배우기 파일을 안 쓴다(dry · 배우기 안 돎).
    대상 어댑터의 prepare()(수집글 = 카드를 공지 필터 것과 같게)를 먼저 부른다 — 다리와 같은 지문이라 «바뀌지 않은 것»이 기억으로 남는다."""
    global SYSTEMS
    real, d = SYSTEMS, os.path.abspath(d)
    reset()
    before = {}
    for sid in set(load_systems(real)) | set(load_systems(d)):
        try:
            before[sid] = {k: r for k, r in json.load(open(os.path.join(INDEX, sid + '.json'), encoding='utf-8'))['items'].items()}
        except (OSError, ValueError, KeyError, TypeError):
            before[sid] = {}
    SYSTEMS = d
    try:
        reset()
        for kind in sorted({(s.get('대상') or {}).get('종류') for s in systems().values() if not s.get('_err')} - {None}):
            ad = adapter(kind)
            if ad is not None and hasattr(ad, 'prepare'):
                ad.prepare()
        run(dry=True, learn=False)
        out = []
        for sid in sorted(before):
            after = state(sid)['items'] if sid in systems() else {}
            for tid in sorted(set(before[sid]) | set(after)):
                a, b = before[sid].get(tid), after.get(tid)
                if (a or {}).get('갈래') != (b or {}).get('갈래'):
                    out.append({'체계': sid, '대상': tid, '전': (a or {}).get('갈래'), '후': (b or {}).get('갈래'), '근거': (b or {}).get('근거', '')})
        return out
    finally:
        SYSTEMS = real
        reset()


def run(only=None, dry=False, now=None, learn_dry=None, answers=None, learn=True):
    """사다리 ①②(③ 갈고리) 를 켠 체계 전부에 · ④ 는 판정 대기에 올림 · 바뀐 판정만 장부 · 동작은 넘김 장부로. 돌려줌 = 체계별 수.
    다른 run 이 쓰는 중이면(잠금) 이 회차는 메모리에만 — 다리(sort_collect)는 메모리 상태를 읽으니 출력은 같다.
    learn_dry = 배우기(S5·S7 그림자 파일)만 따로 — sort_learn.tick 은 dry=True · learn_dry=False(판정은 안 쓰고 배우기만 씀).
    answers = {(체계, 대상): {갈래, 근거, 판정자}} — 사다리 대신 이 판정(answer · 잠금을 못 쥐면 안 돌림: 메모리에만 적으면 사라지니까)."""
    now = now or time.strftime('%Y-%m-%dT%H:%M:%S')
    lock = None if dry else _lock()
    try:
        if answers and lock is None:
            raise RuntimeError('다른 분류 run 이 쓰는 중 — 잠시 뒤 다시')
        d = dry or lock is None
        _RUN_ALERTS[0] = 0
        out = _run(only, d, now, d if learn_dry is None else learn_dry, answers, learn)
    finally:
        if lock:
            lock.close()
    if not d and _RUN_ALERTS[0]:
        alert_now()
    return out


ALERT_TOOL = os.path.join(VAULT, '.claude', 'skills', 'mobility', 'scripts', 'alert.py')     # 알림 도구 = mobility 모듈 몫(사용자 11-18 «알림도구를 mobility 주관으로»)


def alert_tool():
    """mobility 알림 도구 모듈 — 대본이 없거나 mobility 가 꺼졌으면 None(본체는 판정·넘김까지 · 수집 창은 넘김을 직접 읽음). 한 번 읽어 둔다."""
    if not os.path.isfile(ALERT_TOOL):
        return None
    try:
        import roles
        if not roles.module_on('mobility'):
            return None
    except Exception:  # noqa: BLE001 — 모듈 목록을 못 읽으면 안 부름
        return None
    m = sys.modules.get('alert')
    if m is not None and os.path.normcase(os.path.abspath(getattr(m, '__file__', '') or '')) == os.path.normcase(os.path.abspath(ALERT_TOOL)):
        return m
    spec = importlib.util.spec_from_file_location('alert', ALERT_TOOL)
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault('sort', sys.modules[__name__])        # 알림 도구의 import sort 가 이 모듈을 받게
    sys.modules['alert'] = m
    spec.loader.exec_module(m)
    return m


def alert_now():
    """분류가 알림 동작을 넘긴 그 자리에서 알림 도구(mobility alert.py run)를 한 번 — 15분 확인(collect-tick act_tick)을 기다리지 않는다(11-18 즉시 알림).
    진짜 장부 자리(_REAL_INDEX)일 때만 · mobility 가 켜졌을 때만(없으면 조용히 건너뜀) · BRAIN_SORT_NO_ALERT 가 있으면 안 부름.
    실패해도 분류는 그대로(다음 확인이 같은 줄을 읽음 · 알림 도구 커서)."""
    global LAST_ALERT
    if not ALERT_AFTER or os.environ.get('BRAIN_SORT_NO_ALERT') or os.path.normcase(os.path.abspath(INDEX)) != os.path.normcase(os.path.abspath(_REAL_INDEX)):
        return None
    try:
        tool = alert_tool()
        if tool is None:
            return None
        LAST_ALERT = tool.run()
    except Exception as e:  # noqa: BLE001 — 알림이 분류를 멈추지 않게
        LAST_ALERT = {'오류': f'{type(e).__name__}: {e}'[:200]}
    return LAST_ALERT


ANSWERED = []              # 마지막 run 이 적은 answers 열쇠 — 대상 밖이면 비어 있다(answer 가 알린다)


def answer(sid, tid, branch, who='사람', why='', now=None):
    """사람·대화 Claude 의 판정 하나를 적는다(설계 §11 sort.answer · 태그 도구 tag.apply «이거 꽁돈»이 부름 · S8 11-18).
    그 체계와 그것에 기대는 체계만 run 한 번 — 대상 칸·앞 체계·장부·넘김은 사다리 판정과 같은 길. 판정자 = who(사람 · 대화 · claude) 라
    입력(사실·앞 체계 갈래·카드)이 같은 동안 ① 기억이 이 판정을 지킨다(규칙을 고쳐도 안 바뀜 · 입력이 바뀌면 사다리가 다시 정함).
    없는 체계·갈래·꺼진 체계·대상 밖이면 ValueError. 돌려줌 = run 요약."""
    s = systems().get(sid)
    if not s or s.get('_err'):
        raise ValueError(f'없는 체계: {sid}')
    if s.get('켬', True) is False:
        raise ValueError(f'{sid} 는 꺼진 체계(켬 false)')
    if branch not in (s.get('갈래') or {}):
        raise ValueError(f'{sid}: 없는 갈래 «{branch}» — {" · ".join(s.get("갈래") or {})}')
    if who not in ASKED:
        raise ValueError(f'판정자 는 {"·".join(ASKED)}')
    ad = adapter((s.get('대상') or {}).get('종류'))
    if ad is None:
        raise ValueError(f'{sid}: 대상 종류 «{(s.get("대상") or {}).get("종류")}» 어댑터 없음')
    if hasattr(ad, 'prepare'):
        ad.prepare()                               # 수집글 = 카드를 공지 필터 것과 같게(다리와 같은 지문)
    only, grew = {sid}, True
    while grew:                                    # 이 체계에 기대는 체계(꽁돈 ← 공지-들이기 꼴)도 함께
        more = {k for k, x in systems().items() if not x.get('_err') and set(deps_of(x)) & only} - only
        only |= more
        grew = bool(more)
    out = run(sorted(only), now=now, answers={(sid, tid): {'갈래': branch, '근거': why or f'{who} 판정', '판정자': who}})
    if (sid, tid) not in ANSWERED:
        raise ValueError(f'{sid}: 대상 밖 — {tid} (대상 칸·앞 체계 갈래가 이 체계 대상이 아님 · 또는 그런 대상 없음)')
    return out


def _run(only, dry, now, learn_dry=None, answers=None, learn=True):
    learn_dry = dry if learn_dry is None else learn_dry
    S = {k: s for k, s in systems().items() if not s.get('_err') and s.get('켬', True) is not False}
    order, cyc = topo(S)
    DECIDED.clear()
    LEARNED.clear()
    ANSWERED.clear()
    items_by_kind, summary, ledger, outbox, per = {}, {}, [], [], {}
    for sid in order:
        if only and sid not in only:
            continue
        s = S[sid]
        tgt = s.get('대상') or {}
        ad = adapter(tgt.get('종류'))
        cnt = Counter()
        if ad is None:
            summary[sid] = {'어댑터 없음': tgt.get('종류')}
            continue
        if tgt['종류'] not in items_by_kind:
            items_by_kind[tgt['종류']] = list(ad.items())
        st = state(sid)
        old, new, pend = st['items'], {}, {}
        here = per.setdefault(sid, {})
        dec = DECIDED[sid] = []                        # (대상, 환경, 판정) — 배우기(S5·S7)와 재생이 읽는다
        rest = {k: v for k, v in tgt.items() if k not in ('종류', '체계')}
        for it in items_by_kind[tgt['종류']]:
            deps, inside = {}, True
            for dep, allow in deps_of(s).items():
                rec = state(dep)['items'].get(it['id'])
                if not rec:
                    inside = None if it['id'] in state(dep)['대기'] else False
                    break
                deps[dep] = rec['갈래']
                if rec['갈래'] not in allow:
                    inside = False
                    break
            if inside and rest and not ad.match(it, rest):
                inside = False
            if not inside:
                cnt['대상 밖' if inside is False else '앞 체계 대기'] += 1
                continue
            env = {'사실': it['facts'], '값': s.get('값') or {}, '카드': card_view(s), '체계': deps}
            ans = (answers or {}).get((sid, it['id']))
            if ans:                                    # answer — 사람·대화 Claude 판정(사다리 대신 · 지문은 사다리와 같게 = 다음 run 의 ① 기억)
                kind = 'asked'
                out = record(s, it, {'갈래': ans['갈래'], '근거': ans['근거'], '규칙': None}, ans['판정자'], fingerprint(s, it, env), now)
                ANSWERED.append((sid, it['id']))
            else:
                kind, out = decide(s, it, env, old.get(it['id']), now)
            if kind == 'pending':
                if getattr(ad, 'skip_pending', None) and ad.skip_pending(it):
                    cnt['대기 뺌'] += 1
                else:
                    was = st['대기'].get(it['id']) or {}
                    if was.get('지문') == out['지문'] and was.get('시각'):
                        out['시각'] = was['시각']     # 같은 대기는 처음 올린 때 그대로(11-18 · 15분마다 상태 파일을 다시 쓰지 않게)
                    pend[it['id']] = {**out, '자리': place_of(s, it)}
                    here.setdefault(pend[it['id']]['자리'], {'대기': 0, '판정': 0, '맞은': {}, '갈래': {}})['대기'] += 1
                    cnt['대기'] += 1
                continue
            new[it['id']] = out
            dec.append((it, env, out))
            h = here.setdefault(place_of(s, it), {'대기': 0, '판정': 0, '맞은': {}, '갈래': {}})
            h['판정'] += 1
            rk = out.get('규칙') or '모르면'
            h['맞은'][rk] = h['맞은'].get(rk, 0) + 1
            h['갈래'].setdefault(rk, {})[out['갈래']] = h['갈래'].get(rk, {}).get(out['갈래'], 0) + 1
            cnt[{'memory': '기억', 'rule': '규칙', 'stats': '통계', 'unknown': '모르면', 'asked': '답'}[kind]] += 1
            if kind != 'memory' and changed(old.get(it['id']), out):
                ledger.append(ledger_line(out))
                hs = handoff(old.get(it['id']), out, now)
                for h in hs:                               # 알림 줄엔 자리·제목 — 수집 창 «일어난 일»이 넘김을 직접 읽는다(알림 도구 = mobility · 없어도 보임)
                    if isinstance(h['동작'].get('알림'), dict):
                        h['자리'] = place_of(s, it)
                        tt = (it.get('facts') or {}).get('제목')
                        if tt:
                            h['제목'] = str(tt)[:120]
                outbox += hs
                cnt['바뀜'] += 1
        for gone in sorted(set(old) - set(new)):      # 대상 밖·대기로 돌아감 — 붙인 동작을 뗀다
            outbox += handoff(old[gone], None, now)
            ledger.append({'대상': gone, '체계': sid, '판': s.get('판', 1), '갈래': None, '판정자': '엔진',
                           '근거': '대기로' if gone in pend else '대상 밖', '시각': now})
            cnt['빠짐'] += 1
        st['items'], st['대기'] = new, pend
        if not dry:
            write_if_changed(os.path.join(INDEX, sid + '.json'), st)
        summary[sid] = dict(cnt)
        if learn and learn_on(s):                      # S5·S7 그림자 — 판정은 이미 끝남 · 오류여도 run 은 그대로(수집이 옛 길로 떨어지지 않게) · preview 는 안 돎
            try:
                import sort_learn
                LEARNED[sid] = sort_learn.after_system(sid, s, ad, dec, now, learn_dry)
            except Exception as e:
                LEARNED[sid] = {'오류': f'{type(e).__name__}: {e}'}
    for k in cyc:
        summary[k] = {'고리': True}
    if not dry:
        append_lines(os.path.join(INDEX, '판정.jsonl'), ledger)
        append_lines(os.path.join(INDEX, '넘김.jsonl'), outbox)
        _RUN_ALERTS[0] = sum(1 for e in outbox if isinstance(e.get('동작', {}).get('알림'), dict))
        write_places({k: v for k, v in per.items() if k in summary and '어댑터 없음' not in summary[k]}, now)
    return summary


# ───────── 판정 대기 · 버튼 ─────────
# 판정은 그 분류를 쓰는 «자리»에서 한다(사용자 11-18 03:0x) — 수집 창 = 출처마다 «판정 N»(그 출처 대상에 걸린 체계를 한 번에) ·
# 자리가 애매한 체계 = 홈 «분류» 칸. 전역 «모든 체계 한 번에» 단추는 없다. 자리 = 어댑터 place(대상)(수집글 = 출처 id) · 없으면 체계 «자리» · 기본 «홈».
def place_of(s, item):
    ad = adapter((s.get('대상') or {}).get('종류'))
    p = ad.place(item) if ad is not None and hasattr(ad, 'place') else None
    return p or s.get('자리') or '홈'


def pending(place=None):
    """판정 대기 — {대상: {자리, 체계, 특징, 글자, 종류, 모델}} · 한 대상에 체계가 여럿이어도 한 줄(= 한 호출) · place 를 주면 그 자리만."""
    rows = {}
    for sid, s in systems().items():
        if s.get('_err'):
            continue
        for tid, p in state(sid)['대기'].items():
            where = p.get('자리') or s.get('자리') or '홈'
            if place and where != place:
                continue
            r = rows.setdefault(tid, {'자리': where, '체계': [], '특징': [], '글자': p.get('글자', 0), '종류': (s.get('대상') or {}).get('종류'),
                                      '모델': s.get('모델') or 'sonnet'})
            r['체계'].append(sid)
            if p.get('특징') and p['특징'] not in r['특징']:
                r['특징'].append(p['특징'])
    return rows


def places():
    """자리별 판정 대기 수 — 수집 창 출처 줄의 «판정 N» · 홈 «분류» 칸이 읽는다."""
    return dict(Counter(r['자리'] for r in pending().values()))


def batch_of(r):
    """한 대상의 묶음 크기 — 걸린 체계 «묶음» 중 가장 작은 것(1 = 끔 · 기본)."""
    S = systems()
    b = [(S.get(x) or {}).get('묶음') for x in r['체계']]
    b = [x for x in b if isinstance(x, int) and not isinstance(x, bool)] or [1]
    return max(1, min([BATCH_MAX] + b))


def chunks(rs, b):
    """묶음 나누기 — 차례대로 b 건까지 · 입력 BATCH_IN 토큰까지(한 건은 늘 들어감)."""
    out, cur, tok = [], [], FIXED_IN
    for r in rs:
        t = PER_CHAR * r['글자']
        if cur and (len(cur) >= b or tok + t > BATCH_IN):
            out.append(cur)
            cur, tok = [], FIXED_IN
        cur.append(r)
        tok += t
    return out + ([cur] if cur else [])


def estimate(rows):
    """설계 §5 식 — 호출 수 × 고정분 + Σ글자 × 0.324 (입력) · 출력 = 대상 수 × 잰 중앙값 → 가격표 → 주간 %(≈). 묶으면 고정분을 나눠 냄."""
    groups = {}
    for r in rows.values():
        groups.setdefault((r['종류'], r['모델'], batch_of(r)), []).append(r)
    tin = tout = calls = 0
    usd = 0.0
    for (kind, model, b), rs in groups.items():
        ad = adapter(kind)
        f = getattr(ad, 'out_each', None) if ad else None

        def out_of(r):                            # 어댑터가 특징별 잰 값을 주면 그것(꽁돈 칸 글은 출력이 약 3배)
            try:
                return (f(r.get('특징') or ()) if f else None) or OUT_EACH
            except TypeError:
                return f() or OUT_EACH
        pi, po = PRICE.get(model, PRICE['sonnet'])
        for c in chunks(rs, b):
            i = FIXED_IN + sum(PER_CHAR * r['글자'] for r in c)
            o = sum(out_of(r) for r in c)
            calls += 1
            tin += i
            tout += o
            usd += (i * pi + o * po) / 1e6
    return {'건수': len(rows), '호출': calls, '입력': round(tin), '출력': round(tout), '$': round(usd, 4), '주간%': round(usd / WEEK_PCT_USD, 3)}


def judge(place, yes=False):
    """한 자리의 판정 단추 — 그 자리 대상에 걸린 체계를 한 번에(한 대상 한 호출 · 묶어 부르기도 이 자리 안에서만).
    돌려줌 = 종료 값 — 0 됨 · 2 부른 길 실패 · 3 부르기 전 엔진 오류(수집 창은 옛 길로 떨어진다 · 사용량 0)."""
    try:
        run()                                    # 대기를 지금 것으로(받은 뒤 아직 판정 안 돈 글)
        rows = pending(place)
        est = estimate(rows)
        plan = []
        for kind in sorted({r['종류'] for r in rows.values()}):
            ad = adapter(kind)
            mine = {k: r for k, r in rows.items() if r['종류'] == kind}
            b = min(batch_of(r) for r in mine.values())
            plan += ad.judge_cmds(place, mine, batch=b) if ad and hasattr(ad, 'judge_cmds') else []
    except Exception as e:
        print(f'분류 엔진 오류(부르기 전 · 사용량 0): {type(e).__name__}: {e}', file=sys.stderr)
        return 3
    print(f'{place} 판정 대기 {est["건수"]}건 · 호출 {est["호출"]} · 예상 입력 {est["입력"]:,} · 출력 {est["출력"]:,} 토큰 · 환산 ${est["$"]} · 주간 ≈{est["주간%"]}%')
    for argv in plan:
        print('  ' + ' '.join(argv))
    if not yes:
        print('계획만 — 부르려면 --yes(사용량이 든다)')
        return 0
    bad = 0
    for argv in plan:
        sys.stdout.flush()
        bad += subprocess.run(argv, cwd=VAULT).returncode != 0
    try:
        reset()                                   # 부른 길(추출 → 정리)이 장부를 이미 고쳤다 — 메모리 상태로 덮지 않게
        print(json.dumps(run(), ensure_ascii=False))
    except Exception as e:
        print(f'판정 뒤 run 오류: {type(e).__name__}: {e}', file=sys.stderr)
    return 2 if bad else 0


# ───────── 사건(알림 줄) ─────────
# 사건 = 수집 창 알림 줄에 뜰 일(자동 채택 · 가격선 바뀜 …) · 내는 쪽은 S5(채택)·S2(가격선) — 이 파일은 꼴과 읽기·닫기·되돌리기만.
# 한 줄 = {"id", "시각", "체계", "종류", "글", "되돌리기"?: {"규칙": id} | {"값": 이름, "전": 옛 값, "후": 새 값}, "자리"?: [자리…]}
# 닫는 줄 = {"id", "닫힘": "확인" | "되돌림", "시각"} — 덧붙이기만(장부). 자리를 안 적으면 그 체계가 걸린 자리 모두에 뜬다.
EVENTS = '사건.jsonl'


def event_add(sid, kind, text, undo=None, where=None, now=None):
    now = now or time.strftime('%Y-%m-%dT%H:%M:%S')
    eid = hashlib.sha1(canon([now, sid, kind, text, undo]).encode('utf-8')).hexdigest()[:10]
    row = {'id': eid, '시각': now, '체계': sid, '종류': kind, '글': text}
    if undo:
        row['되돌리기'] = undo
    if where:
        row['자리'] = list(where)
    append_lines(os.path.join(INDEX, EVENTS), [row])
    return eid


def events(open_only=True):
    rows, shut = {}, {}
    try:
        for ln in open(os.path.join(INDEX, EVENTS), encoding='utf-8'):
            try:
                e = json.loads(ln)
            except ValueError:
                continue
            if not isinstance(e, dict) or not e.get('id'):
                continue
            if '닫힘' in e:
                shut[e['id']] = e
            else:
                rows[e['id']] = e
    except OSError:
        pass
    out = [{**e, **({'닫힘': shut[k]['닫힘']} if k in shut else {})} for k, e in rows.items()]
    return [e for e in out if '닫힘' not in e] if open_only else out


def _close(eid, how, now, more=None):
    append_lines(os.path.join(INDEX, EVENTS), [{'id': eid, '닫힘': how, '시각': now or time.strftime('%Y-%m-%dT%H:%M:%S'), **(more or {})}])


def ack(eid, now=None):
    if not any(e['id'] == eid for e in events()):
        raise ValueError(f'열린 사건 없음: {eid}')
    _close(eid, '확인', now)


def dump_system(s):
    """체계 파일 꼴 — 칸마다 한 줄 · 규칙은 한 줄에 하나(사람이 읽고 고치는 원본이라 들여쓴 JSON 대신)."""
    L = []
    for k, v in system_core(s).items():
        key = json.dumps(k, ensure_ascii=False)
        if k == '규칙' and isinstance(v, list):
            L.append(f'{key}: [\n' + ',\n'.join('  ' + json.dumps(r, ensure_ascii=False) for r in v) + ']')
        else:
            L.append(f'{key}: {json.dumps(v, ensure_ascii=False)}')
    return '{' + ',\n '.join(L) + '}\n'


def undo_apply(sid, undo):
    """되돌리기 하나를 체계 파일에 — 규칙 끔(+ 거부: 다시 후보로 안 올림 · 자동 규칙만) · 값 되돌림(지금 값이 «후»일 때만)."""
    p = os.path.join(SYSTEMS, sid + '.json')
    s = json.load(open(p, encoding='utf-8'))
    if '규칙' in undo:
        r = next((x for x in s.get('규칙') or [] if x.get('id') == undo['규칙']), None)
        if r is None:
            raise ValueError(f'{sid}: 규칙 {undo["규칙"]} 없음')
        if not str(r.get('만든이', '')).startswith('자동'):
            raise ValueError(f'{sid}: {r["id"]} 는 사람이 만든 규칙 — 말로 고침')
        r['켬'], r['거부'] = False, True
        what = {'규칙': r['id']}
    elif '값' in undo:
        vals = s.setdefault('값', {})
        if '후' in undo and canon(vals.get(undo['값'])) != canon(undo['후']):
            raise ValueError(f'{sid}: 값 {undo["값"]} 이 그 뒤 바뀜 — 되돌리지 않음')
        vals[undo['값']] = undo['전']
        what = {'값': undo['값']}
    else:
        raise ValueError(f'모르는 되돌리기 {canon(undo)[:60]}')
    with open(p + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        f.write(dump_system(s))
    os.replace(p + '.tmp', p)
    reset()
    return what


def revert(eid=None, sid=None, rule=None, now=None, rerun=True):
    """알림 줄·규칙 줄 «되돌리기» — 1누름. 사건이면 그 사건의 되돌리기 · 규칙이면 그 자동 규칙 끔(그 규칙을 낸 열린 사건도 닫음)."""
    if eid:
        e = next((x for x in events() if x['id'] == eid), None)
        if e is None or not e.get('되돌리기'):
            raise ValueError(f'되돌릴 열린 사건 없음: {eid}')
        sid, undo = e['체계'], e['되돌리기']
        hit = [e]
    else:
        undo = {'규칙': rule}
        hit = [x for x in events() if x.get('체계') == sid and (x.get('되돌리기') or {}).get('규칙') == rule]
        s = systems().get(sid) or {}
        if not any(r.get('id') == rule for r in s.get('규칙') or []):
            import sort_learn                      # 체계 파일에 없는 id = S5 그림자 후보 → 거부(다시 후보로 안 올림 · 판정은 그대로)
            return sort_learn.reject(sid, rule, now)
    what = undo_apply(sid, undo)
    for x in hit:
        _close(x['id'], '되돌림', now, {'체계': sid, '되돌린 것': what})
    if not hit:
        _close('규칙:' + sid + '/' + str(rule), '되돌림', now, {'체계': sid, '되돌린 것': what})
    return run() if rerun else None


# ───────── 검사 ─────────
def bad_ref(r, s, deps, where):
    if isinstance(r, dict):
        if isinstance(r.get('빼기'), list) and len(r['빼기']) == 2:
            return [e for x in r['빼기'] for e in bad_ref(x, s, deps, where)]
        return [f'{where}: 칸 객체는 {{"빼기": [a, b]}} 만']
    if isinstance(r, str):
        if r.startswith('@') and not r.startswith('@카드.') and r[1:] not in (s.get('값') or {}):
            return [f'{where}: 없는 값 «{r}»']
        if r.startswith('체계.') and r[3:] not in deps:
            return [f'{where}: «{r}» 는 대상.체계 에 없는 체계']
    return []


def bad_cond(c, s, deps, where):
    if not isinstance(c, dict) or not c:
        return [f'{where}: 조건은 객체']
    if '칸' in c:
        ops = [k for k in c if k != '칸']
        out = [] if ops else [f'{where}: 낱말 없음']
        out += [f'{where}: 모르는 낱말 «{k}»' for k in ops if k not in LEAF]
        out += bad_ref(c['칸'], s, deps, where)
        for k in ops:
            x = c[k]
            if isinstance(x, (str, dict)) and (isinstance(x, dict) or x.startswith('@')):
                out += bad_ref(x, s, deps, where)
            if k == '맞음':
                try:
                    re.compile(str(x))
                except re.error as e:
                    out.append(f'{where}: 정규식 오류 {e}')
            if k == '사이':
                if isinstance(x, list) and len(x) == 2:
                    out += [e for y in x if isinstance(y, str) and y.startswith('@') for e in bad_ref(y, s, deps, where)]
                elif not (isinstance(x, str) and x.startswith('@')):
                    out.append(f'{where}: 사이는 [작은, 큰] · "@값"([작은, 큰]) · ["@값", "@값"]')
            if k in ('안에', '겹침') and not (isinstance(x, list) or (isinstance(x, str) and x.startswith('@'))):
                out.append(f'{where}: {k} 는 목록 또는 @참조')
        return out
    if len(c) != 1 or next(iter(c)) not in GROUP:
        return [f'{where}: 묶음은 {"·".join(GROUP)} 중 하나만']
    k, x = next(iter(c.items()))
    if k in ('모두', '하나라도'):
        if not isinstance(x, list) or not x:
            return [f'{where}: {k} 는 조건 목록']
        return [e for i, y in enumerate(x) for e in bad_cond(y, s, deps, f'{where}.{k}[{i}]')]
    if k == '아님':
        return bad_cond(x, s, deps, f'{where}.아님')
    return [] if x is True else [f'{where}: 늘 은 true 만']


def bad_table(t, s, deps, where, branches):
    out = []
    parts = t.get('점수')
    if not isinstance(parts, list) or not parts:
        return [f'{where}: 표.점수 는 목록']
    for i, p in enumerate(parts):
        w = f'{where}.점수[{i}]'
        if not isinstance(p, dict) or '칸' not in p or ('단계' in p) == ('더하기' in p):
            out.append(f'{w}: 칸 + 단계 또는 더하기 하나')
            continue
        out += bad_ref(p['칸'], s, deps, w)
        if '단계' in p:
            st = p['단계']
            if not (isinstance(st, list) and st and all(isinstance(x, list) and len(x) == 2 and num(x[0]) and isinstance(x[1], int) for x in st)):
                out.append(f'{w}: 단계는 [[문턱, 점수]…]')
            elif [x[0] for x in st] != sorted(x[0] for x in st):
                out.append(f'{w}: 단계 문턱은 오름차순')
        elif not (isinstance(p['더하기'], dict) and all(isinstance(v, int) for v in p['더하기'].values())):
            out.append(f'{w}: 더하기는 {{값: 정수}}')
    g = t.get('갈래')
    if not isinstance(g, dict) or not g:
        out.append(f'{where}: 표.갈래 없음')
    else:
        out += [f'{where}: 표.갈래 «{v}» 가 체계 갈래에 없음' for v in g.values() if v not in branches]
    lim = t.get('가둠')
    if lim is not None and not (isinstance(lim, list) and len(lim) == 2 and all(isinstance(x, int) for x in lim)):
        out.append(f'{where}: 가둠은 [작은, 큰]')
    return out


def check_one(sid, s, S):
    E, W = [], []
    if s.get('_err'):
        return [s['_err']], W
    if s.get('id') != sid:
        E.append(f'id «{s.get("id")}» 가 파일 이름과 다름')
    if not isinstance(s.get('판'), int):
        E.append('판(정수) 없음')
    W += [f'모르는 칸 «{k}»' for k in s if not k.startswith('_') and k not in KEYS]
    br = s.get('갈래')
    if not isinstance(br, dict) or not br:
        E.append('갈래 없음')
        br = {}
    for name, b in br.items():
        acts = (b or {}).get('동작')
        if not isinstance(acts, list):
            E.append(f'갈래 «{name}»: 동작은 목록')
            continue
        for a in acts:
            if not isinstance(a, dict) or len(a) != 1 or next(iter(a)) not in ACTS:
                E.append(f'갈래 «{name}»: 동작은 {"·".join(ACTS)} 중 하나씩 — {canon(a)[:60]}')
            elif '알림' in a:
                al = a['알림']
                if not isinstance(al, dict) or not WHEN.match(str(al.get('때', ''))):
                    E.append(f'갈래 «{name}»: 알림.때 는 바로 · 아침 · 묶음 HH:MM')
                elif al.get('급함') not in (True, False, 'claude', None):
                    E.append(f'갈래 «{name}»: 알림.급함 은 true · false · "claude"')
            elif '태그' in a and not (isinstance(a['태그'], str) and a['태그'].strip()):
                E.append(f'갈래 «{name}»: 태그 이름 없음')
    if s.get('모르면') not in br:
        E.append(f'모르면 «{s.get("모르면")}» 이 갈래에 없음')
    if '묶음' in s and not (isinstance(s['묶음'], int) and not isinstance(s['묶음'], bool) and 1 <= s['묶음'] <= BATCH_MAX):
        E.append(f'묶음 은 1~{BATCH_MAX} 정수(1 = 끔)')
    lad = s.get('사다리') or {}
    E += [f'사다리: 모르는 단계 «{k}»' for k in lad if k not in LADDER]
    if lad.get('claude', '버튼') not in CLAUDE_MODES:
        E.append(f'사다리.claude 는 {"·".join(CLAUDE_MODES)}')
    v = lad.get('통계', False)
    if not (v is False or v is True or v == '그림자'):
        E.append('사다리.통계 는 false · "그림자" · true')
    if s.get('자동채택', '끔') not in ADOPT_MODES:
        E.append(f'자동채택 은 {"·".join(ADOPT_MODES)}(진짜 채택은 그림자 통과 뒤 사용자 결정 — 아직 없음)')
    if '노트에 쓰기' in s and not isinstance(s['노트에 쓰기'], bool):
        E.append('노트에 쓰기 는 true · false(태그를 0_작업·2_지식 노트 프론트매터에도 · 기본 끔 — tag.py)')
    tgt = s.get('대상')
    if not isinstance(tgt, dict) or not tgt.get('종류'):
        E.append('대상.종류 없음')
        tgt = {}
    elif tgt['종류'] not in ADAPTERS and tgt['종류'] not in _adapters:
        W.append(f'대상 종류 «{tgt["종류"]}» 어댑터 없음 — 돌릴 수 없음(검사만)')
    deps = deps_of(s)
    for dep, allow in deps.items():
        if dep not in S:
            E.append(f'대상.체계: 없는 체계 «{dep}»')
        elif not isinstance(allow, list) or any(a not in (S[dep].get('갈래') or {}) for a in allow):
            E.append(f'대상.체계 «{dep}»: 그 체계에 없는 갈래 {allow}')
    rules = s.get('규칙')
    if not isinstance(rules, list) or not rules:
        E.append('규칙 없음')
        rules = []
    ids = Counter(r.get('id') for r in rules if isinstance(r, dict))
    E += [f'규칙 id «{k}» 가 {c}번' for k, c in ids.items() if c > 1]
    for i, r in enumerate(rules):
        where = f'규칙 {r.get("id") or i}' if isinstance(r, dict) else f'규칙 {i}'
        if not isinstance(r, dict) or not r.get('id'):
            E.append(f'{where}: id 없음')
            continue
        if not (isinstance(r.get('말'), str) and r['말'].strip()):
            E.append(f'{where}: «말»(원문) 없음')
        if not isinstance(r.get('만든이'), str):
            W.append(f'{where}: 만든이 없음')
        forms = [k for k in ('표', '함수') if k in r]
        if len(forms) > 1 or (not forms and not ('조건' in r and '갈래' in r)):
            E.append(f'{where}: 꼴은 조건+갈래 · 표 · 함수 중 하나')
        if '조건' in r:
            E += bad_cond(r['조건'], s, deps, where)
        if '갈래' in r and r['갈래'] not in br:
            E.append(f'{where}: 갈래 «{r["갈래"]}» 가 없음')
        if '표' in r:
            E += bad_table(r['표'], s, deps, where, br) if isinstance(r['표'], dict) else [f'{where}: 표는 객체']
        if '함수' in r:
            try:
                f = func(r['함수'])
                if not callable(f):
                    raise TypeError('부를 수 없음')
            except Exception as e:
                E.append(f'{where}: 함수 «{r["함수"]}» 못 찾음 — {type(e).__name__}: {e}')
    return E, W


def check(d=None):
    """{체계: (오류, 경고)} — 고리도 오류."""
    S = load_systems(d)
    res = {sid: check_one(sid, s, S) for sid, s in S.items()}
    _, cyc = topo({k: s for k, s in S.items() if not s.get('_err')})
    for k in cyc:
        res[k][0].append('대상.체계 의존이 고리를 이룸')
    return res


# ───────── 사람이 읽는 꼴 ─────────
def human_rules(sid):
    s = systems()[sid]
    hits = Counter(r.get('규칙') for r in state(sid)['items'].values())
    L = [f'# {s.get("이름") or sid} (판 {s.get("판")})', '', '| # | 말 | → 갈래 | 만든이 | 맞은 수 |', '|---|---|---|---|---|']
    for r in s.get('규칙') or []:
        to = r.get('갈래') or ('표' if '표' in r else f'함수 {r.get("함수")}')
        L.append(f'| {r["id"]}{"" if r.get("켬", True) else " (끔)"} | {r.get("말", "")} | {to} | {r.get("만든이", "")} | {hits.get(r["id"], 0)} |')
    L.append(f'- 대상: {canon(s.get("대상"))} · 모르면: {s.get("모르면")} · 대기 {len(state(sid)["대기"])}')
    return '\n'.join(L)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['check', 'rules', 'run', 'pending', 'judge', 'events', 'ack', 'revert', 'learn', 'preview'])
    ap.add_argument('--replay', action='store_true', help='learn: 지금 판정을 시간 순으로 다시 흘려 S5 그림자 흉내 + ③ 시간 순 누적 검증(안 씀)')
    ap.add_argument('name', nargs='?')
    ap.add_argument('--all', action='store_true', help='events: 닫힌 것도')
    ap.add_argument('--rule', help='revert: 이 자동 규칙(--system 과 함께)')
    ap.add_argument('--dir', help='check · preview: 체계 폴더(기본 3_시스템/sort · preview 는 고친 사본 필수)')
    ap.add_argument('--system', action='append', help='run: 이 체계만(여럿)')
    ap.add_argument('--dry', action='store_true', help='run: 쓰지 않음')
    ap.add_argument('--yes', action='store_true', help='judge: 실제로 부름(사용량)')
    ap.add_argument('--place', help='pending·judge: 자리(수집글 = 출처 id · 홈 분류 = 홈) · pending 에 없으면 자리별 수')
    a = ap.parse_args()
    if a.cmd == 'check':
        d = os.path.abspath(a.dir) if a.dir else SYSTEMS
        res = check(d)
        bad = 0
        for sid, (E, W) in sorted(res.items()):
            print(f'{"통과" if not E else "오류"} {sid}' + ''.join(f'\n  ✗ {e}' for e in E) + ''.join(f'\n  · {w}' for w in W))
            bad += bool(E)
        print(f'체계 {len(res)} · 오류 {bad}')
        sys.exit(1 if bad or not res else 0)
    elif a.cmd == 'preview':
        if not a.dir:
            sys.exit('preview --dir <고친 체계 폴더 사본>')
        rows = preview(a.dir)
        print(json.dumps({'바뀜': len(rows), '체계별': dict(Counter(r['체계'] for r in rows))}, ensure_ascii=False))
        for r in rows:
            print(f'  {r["체계"]} · {r["대상"]} · {r["전"]} → {r["후"]} · {r["근거"][:80]}')
    elif a.cmd == 'rules':
        if a.name not in systems():
            sys.exit(f'체계: {" ".join(systems())}')
        print(human_rules(a.name))
    elif a.cmd == 'run':
        print(json.dumps(run(a.system, a.dry), ensure_ascii=False, indent=1))
        if LEARNED:
            print('배우기 ' + json.dumps(LEARNED, ensure_ascii=False))
    elif a.cmd == 'learn':
        import sort_learn
        names = [a.name] if a.name else [k for k, s in systems().items() if not s.get('_err')]
        if a.replay:
            for sid in names:
                print(sort_learn.replay_text(sid))
        else:
            print(json.dumps({sid: sort_learn.status(sid) for sid in names}, ensure_ascii=False, indent=1))
    elif a.cmd == 'pending':
        if not a.place:
            print(json.dumps(places(), ensure_ascii=False))
            return
        rows = pending(a.place)
        print(json.dumps(estimate(rows), ensure_ascii=False))
        for tid, r in rows.items():
            print(f'  {tid} · {"·".join(r["체계"])} · 특징 {"·".join(r["특징"])} · 글자 {r["글자"]}')
    elif a.cmd == 'judge':
        if not a.place:
            sys.exit(f'judge --place <자리> — 자리: {" ".join(places()) or "(대기 없음)"}')
        sys.exit(judge(a.place, a.yes))
    elif a.cmd == 'events':
        print(json.dumps(events(not a.all), ensure_ascii=False, indent=1))
    elif a.cmd in ('ack', 'revert'):
        try:
            if a.cmd == 'ack':
                ack(a.name)
            elif a.rule:
                print(json.dumps(revert(sid=(a.system or [None])[0], rule=a.rule), ensure_ascii=False))
            else:
                print(json.dumps(revert(a.name), ensure_ascii=False))
        except (ValueError, OSError) as e:
            sys.exit(f'{a.cmd}: {e}')


if __name__ == '__main__':
    sys.modules.setdefault('sort', sys.modules['__main__'])    # 어댑터가 import sort 해도 같은 모듈
    main()
