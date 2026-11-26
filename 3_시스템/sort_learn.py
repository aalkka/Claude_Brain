"""분류 엔진 sort 의 배우기 — S5 코드 규칙 자동 채택(그림자) · S7 ③ 낱말 통계 (범용 도구 셋 · 2026-11-18 · 설계 §3·§6 · Claude 0).

배울 자료(«보기») = 그 체계의 Claude 판정 — 판정자 claude·대화·사람, 또는 규칙 판정이지만 Claude 앞 대상(어댑터 pre)으로는 규칙이
  «모름»이던 것(수집글: 공지-들이기 n1 · 황금 g2~g4 는 Claude 추출 칸이 있어야 정해짐). ③ 자기 판정(판정자 통계)·«모르면»은 안 배운다.
  차례 = 어댑터 order(수집글 = 게시일·출처·글번호) · 없으면 판정 시각.

S5 — 체계 «자동채택»: "끔"(기본) | "그림자"(설계 §6 · 보스 11-18 «켜도 그림자 기록만 · 진짜 판정을 안 바꿈»)
  후보 = 그 체계 보기 ≥ 10 · 같은 자리(어댑터 place = 출처 id · 없으면 체계 «자리» · 홈) 안에서 «<칸>에 <낱말> 포함 → 갈래»가
         지지 ≥ 3 · 어긋남 0 · Claude 앞 칸만(어댑터 LEARN · 수집글 = 제목). 같은 글 묶음을 덮는 낱말은 가장 긴 것 하나.
  그림자 = 후보가 된 뒤 새로 들어온 보기 중 그 자리에서 걸린 것이 연달아 맞아야 «통과» — 10건 · 빼는 갈래(동작에 들이기·태그·알림·
         옮기기가 없음 = 비해당·아님·버림)는 20건. 통과 전 한 번 틀리면 «탈락» · 통과 뒤 틀리면 «은퇴»(설계 «자동 은퇴»).
         통과 = 대기열 한 줄(진짜로 켤지 사용자에게) + 체계 파일에 쓸 규칙 줄을 상태에 적어 둠(쓰지는 않음).
  처음 켠 run 은 지금까지 보기를 역사로만 씀(연속에 안 셈). 진짜 판정·체계 파일·수집 창 사건은 안 바꾼다.
  되돌리기 = `sort.py revert --system <체계> --rule <후보 id>` → «거부»(다시 후보로 안 올림). 체계 파일의 자동 규칙(거부 true)도 다시 안 올림.
  상태 = _index/sort/채택-<체계>.json · 장부 = _index/sort/채택.jsonl.

S7 — 체계 «사다리.통계»: false(기본 · 보스 11-18) | "그림자" | true(설계 §3)
  글자 2~4-gram TF-IDF(char_wb) + 로지스틱(C=20) — 측정 evalcls.py B 와 같은 꼴. 문턱 = 체계마다 시간 순 누적 검증(앞 i건으로 배워 i번째 ·
  처음 10건 뒤)에서 정밀도 98% 이상을 지키는 가장 큰 덮음의 신뢰값 · 보기가 바뀔 때만 다시 잼(다시 배우기는 많아야 40번 — 보기가 많으면 건너뜀).
  문턱을 못 찾으면 덮음 0(= 저절로 꺼진 셈). 켬 = 규칙이 «모름»인 대상 중 신뢰 ≥ 문턱만 정함(판정자 «통계» · 안 배움).
  그림자 = 정하지 않고 예측만 적어 두었다가 그 대상이 Claude 판정을 받으면 대조(맞음·틀림·모름 = 문턱 밑).
  다시 재기(설계 §3 · 대기열 한 줄 · 같은 줄은 열려 있는 동안 한 번): 보기 300건 넘음 · 사람 표시(살림·뺌·헛것·쓸모·사람 판정) 100건 ·
  ③ 덮음이 보기 100건 동안 안 늚.
  상태 = _index/sort/통계-<체계>.json(보기 글·문턱·덮음 내력·그림자 예측·대조) · 장부 = _index/sort/통계.jsonl.

15분 확인 길(11-18 보스): 공지 판정 다리는 py -3.11(sklearn 없음)로 돌아 그 안의 run 은 S5 만 하고 ③ 은 건너뜀. collect-tick.py 끝의
  `py -3 3_시스템/sort_learn.py tick` 이 판정은 안 쓰는(dry) run 으로 S5·S7 배우기 파일을 쓰고 S6(sort_inbox) 을 돌린다 — 엔진 상태·체계 파일·
  배우기 파일이 그대로면 건너뜀(_index/sort/배우기-틱.json «마지막» = 틱이 살아 있나).
"""
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter

import sort

DROP_KEEP = ('들이기', '태그', '알림', '옮기기')        # 이 동작이 하나도 없는 갈래 = 빼는 쪽(놓침이 비쌈 → 그림자 20건)
NEED, NEED_DROP = 10, 20
MIN_EXAMPLES, MIN_SUPPORT = 10, 3
PREC, START, MAX_FITS = 0.98, 10, 40
AGAIN_N, AGAIN_MARKS, AGAIN_FLAT = 300, 100, 100
MARKS = ('살림', '뺌', '헛것', '쓸모')
QUEUE = None                                            # 시험이 바꿈 · None = 엔진 INDEX 가 진짜 자리일 때만 진짜 대기열


def now_s():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def path(kind, sid):
    return os.path.join(sort.INDEX, f'{kind}-{sid}.json')


def load(p, empty):
    try:
        return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return json.loads(json.dumps(empty)) if empty is not None else None


def queue_path():
    if QUEUE:
        return QUEUE
    real = os.path.join(sort.SYS, '_index', 'sort')
    if os.path.normcase(os.path.abspath(sort.INDEX)) == os.path.normcase(os.path.abspath(real)):
        return os.path.join(sort.SYS, '_index', '수집-대기열.md')
    return os.path.join(sort.INDEX, '수집-대기열.md')            # 시험·사본 — 진짜 대기열을 안 건드림


def queue(text):
    if sort.SYS not in sys.path:
        sys.path.insert(0, sort.SYS)
    import collectlib
    return collectlib.queue_add('sort', text, who='Claude', once='line', path=queue_path())


def tok(s):
    """후보 낱말 — 측정 evalcls.py 와 같은 나눔(2자 이상 · 숫자만은 뺌)."""
    return [w for w in re.split(r'[^0-9A-Za-z가-힣]+', s or '') if len(w) >= 2 and not w.isdigit()]


def modes(s):
    lad = {**sort.LADDER, **(s.get('사다리') or {})}
    return s.get('자동채택', '끔') == '그림자', (lad['통계'] if lad['통계'] in ('그림자', True) else None)


# ───────── 보기(배울 자료) ─────────
def asked(s, ad, it, env, rec):
    who = rec.get('판정자')
    if who in sort.ASKED:
        return True
    if who != '규칙' or ad is None or not hasattr(ad, 'pre'):
        return False
    it2 = ad.pre(it)
    return '갈래' not in sort.rules_eval(s, {**env, '사실': it2['facts']}, it2)


def fields_of(ad, it):
    return {k: it['facts'][k] for k in getattr(ad, 'LEARN', ('제목',)) if isinstance(it['facts'].get(k), str)}


def text_of(ad, it):
    if ad is not None and hasattr(ad, 'text'):
        return ad.text(it)
    return '\n'.join(fields_of(ad, it).values())


def examples(sid, s, ad, decided):
    out = []
    for it, env, rec in decided:
        if rec.get('갈래') is None or not asked(s, ad, it, env, rec):
            continue
        when = [str(x) for x in ad.order(it)] if ad is not None and hasattr(ad, 'order') else [str(rec.get('시각') or '')]
        out.append({'id': it['id'], '갈래': rec['갈래'], '자리': sort.place_of(s, it), '칸': fields_of(ad, it), '글': text_of(ad, it),
                    '때': when, '열쇠': f'{rec.get("지문")}|{rec["갈래"]}'})
    out.sort(key=lambda e: (e['때'], e['id']))
    return out


def marks_of(decided):
    return sum(1 for it, _, rec in decided if rec.get('판정자') == '사람' or (it.get('facts') or {}).get('표시') in MARKS)


# ───────── S5 자동 채택(그림자) ─────────
def drop(s, g):
    acts = ((s.get('갈래') or {}).get(g) or {}).get('동작') or []
    return not any(k in a for a in acts for k in DROP_KEEP)


def cid(c):
    return 'c' + hashlib.sha1('|'.join((c['자리'], c['칸'], c['낱말'], c['갈래'])).encode('utf-8')).hexdigest()[:8]


def fires(c, e):
    return c['자리'] in ('*', e['자리']) and c['낱말'] in e['칸'].get(c['칸'], '')


def mine(exs, scoped=True):
    """후보 {id: {자리, 칸, 낱말, 갈래, 지지}} — 보기 ≥ 10 · 자리 안 지지 ≥ 3 · 어긋남 0 · 같은 글 묶음은 가장 긴 낱말. scoped=False = 자리 없이(측정 대조용)."""
    if len(exs) < MIN_EXAMPLES:
        return {}
    groups = {}
    for e in exs:
        groups.setdefault(e['자리'] if scoped else '*', []).append(e)
    out = {}
    for where, es in sorted(groups.items()):
        for field in sorted({k for e in es for k in e['칸']}):
            best = {}
            for w in sorted({w for e in es for w in tok(e['칸'].get(field, ''))}):
                hit = [e for e in es if w in e['칸'].get(field, '')]
                if len(hit) < MIN_SUPPORT or len({e['갈래'] for e in hit}) != 1:
                    continue
                key = tuple(sorted(e['id'] for e in hit))
                if key not in best or len(w) > len(best[key][0]):
                    best[key] = (w, hit[0]['갈래'])
            for key, (w, g) in best.items():
                c = {'자리': where, '칸': field, '낱말': w, '갈래': g, '지지': len(key)}
                out[cid(c)] = c
    return out


def refused(s, c):
    """체계 파일에서 되돌린 자동 규칙(거부 true)과 같은 후보면 다시 안 올림."""
    return any(r.get('거부') and r.get('갈래') == c['갈래'] and r.get('조건') == {'칸': c['칸'], '포함': c['낱말']} and r.get('자리') in (None, c['자리'])
               for r in s.get('규칙') or [])


def rule_line(c, day):
    """진짜로 켤 때 체계 파일에 쓸 줄(설계 §6 «만든이: 자동 … · 지지 … · 그림자 …») — 지금은 상태에 적어 두기만."""
    return {'id': 'a' + cid(c)[1:], '말': f'{c["칸"]}에 «{c["낱말"]}» 가 있으면 {c["갈래"]}', '만든이': f'자동 {day} · 지지 {c["지지"]} · 그림자 {c["연속"]}/{c["필요"]}',
            '자리': c['자리'], '조건': {'칸': c['칸'], '포함': c['낱말']}, '갈래': c['갈래'], '근거': f'자동 규칙 · {c["칸"]}에 «{c["낱말"]}»'}


def adopt_step(s, sid, st, exs, now, log, notify):
    """그림자 한 걸음 — 새 보기를 후보에 대 보고(맞음·탈락·통과·은퇴) → 본 것 갱신 → 새 후보 등록. st 를 고친다."""
    first = not st['본'] and not st['후보']
    new = [e for e in exs if st['본'].get(e['id']) != e['열쇠']]
    if not first:
        for e in new:
            for k in sorted(st['후보']):
                c = st['후보'][k]
                if c['상태'] not in ('그림자', '통과') or not fires(c, e):
                    continue
                good = c['갈래'] == e['갈래']
                row = {'시각': now, '체계': sid, '후보': k, '대상': e['id'], '자리': c['자리'], '낱말': c['낱말'], '갈래': c['갈래'], '판정': e['갈래']}
                if c['상태'] == '그림자' and good:
                    c['연속'] += 1
                    log.append({**row, '일': '맞음', '연속': c['연속']})
                    if c['연속'] >= c['필요']:
                        c['상태'], c['바뀜'], c['규칙줄'] = '통과', now, rule_line(c, now[5:10])
                        log.append({**row, '일': '통과', '연속': c['연속']})
                        notify.append(f'자동 채택 그림자 통과 — 체계 «{sid}» 자리 {c["자리"]} · {c["칸"]}에 «{c["낱말"]}» → {c["갈래"]} '
                                      f'({c["필요"]}건 연속) · 진짜로 켤지 사용자에게(`py -3 3_시스템/sort.py learn {sid}`)')
                elif c['상태'] == '그림자':
                    c['상태'], c['바뀜'], c['어긋남'] = '탈락', now, {'대상': e['id'], '갈래': e['갈래']}
                    log.append({**row, '일': '탈락', '연속': c['연속']})
                elif good:
                    c['통과 뒤 맞음'] = c.get('통과 뒤 맞음', 0) + 1
                else:
                    c['상태'], c['바뀜'], c['어긋남'] = '은퇴', now, {'대상': e['id'], '갈래': e['갈래']}
                    log.append({**row, '일': '은퇴', '연속': c['연속']})
    st['본'] = {e['id']: e['열쇠'] for e in exs}
    for k, c in mine(exs).items():
        old = st['후보'].get(k)
        if old:
            if old['상태'] in ('그림자', '통과'):
                old['지지'] = c['지지']
            continue
        if refused(s, c):
            continue
        st['후보'][k] = {**c, '필요': NEED_DROP if drop(s, c['갈래']) else NEED, '연속': 0, '상태': '그림자', '등록': now}
        log.append({'시각': now, '체계': sid, '후보': k, '일': '후보', '자리': c['자리'], '낱말': c['낱말'], '갈래': c['갈래'], '지지': c['지지']})
    return 0 if first else len(new)


def states(st):
    return dict(Counter(c['상태'] for c in st['후보'].values()))


def adopt(sid, s, exs, now, dry):
    p = path('채택', sid)
    st = load(p, {'본': {}, '후보': {}})
    log, notify = [], []
    n_new = adopt_step(s, sid, st, exs, now, log, notify)
    if not dry:
        sort.write_if_changed(p, st)
        sort.append_lines(os.path.join(sort.INDEX, '채택.jsonl'), log)
        for t in notify:
            queue(t)
    best = max((c['연속'] for c in st['후보'].values() if c['상태'] == '그림자'), default=0)
    return {'채택': {**states(st), '최고 연속': best, '새 보기': n_new}}


def reject(sid, k, now=None):
    """그림자 후보 «거부» — 다시 후보로 안 올림(판정은 원래 안 바뀜)."""
    now = now or now_s()
    p = path('채택', sid)
    st = load(p, None)
    if not st or k not in (st.get('후보') or {}):
        raise ValueError(f'{sid}: 규칙·그림자 후보 «{k}» 없음')
    c = st['후보'][k]
    c['상태'], c['바뀜'] = '거부', now
    sort.write_json(p, st)
    sort.append_lines(os.path.join(sort.INDEX, '채택.jsonl'), [{'시각': now, '체계': sid, '후보': k, '일': '거부', '자리': c['자리'], '낱말': c['낱말'], '갈래': c['갈래']}])
    return {'거부': k, '자리': c['자리'], '낱말': c['낱말'], '갈래': c['갈래']}


def replay_adopt(s, sid, exs, init=MIN_EXAMPLES):
    """그림자 흉내 — 처음 init 건을 역사로 켜고, 그 뒤 보기를 한 건씩 «새로 들어온 것»으로 흘린다(run 한 번에 한 건)."""
    st, log, notify = {'본': {}, '후보': {}}, [], []
    adopt_step(s, sid, st, exs[:init], (exs[init - 1]['때'][0] if len(exs) >= init else '') or '처음', log, notify)
    for i in range(init, len(exs)):
        adopt_step(s, sid, st, exs[:i + 1], exs[i]['때'][0] or f'#{i}', log, notify)
    return st, log


# ───────── S7 ③ 낱말 통계 ─────────
_sk, _models, _preds, _files = [], {}, {}, {}


def have_sklearn():
    """15분 확인은 py -3.11(sklearn 없음)로 돈다 — 그 프로세스에서는 ③ 을 건너뛰고 `sort_learn.py tick`(py -3)이 맡는다."""
    import importlib.util
    return importlib.util.find_spec('sklearn') is not None


def sk():
    if not _sk:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        _sk.append((TfidfVectorizer, LogisticRegression))
    return _sk[0]


def fit(texts, ys):
    if len(set(ys)) < 2:
        return None
    V, L = sk()
    v = V(analyzer='char_wb', ngram_range=(2, 4), sublinear_tf=True, min_df=1)
    return v, L(C=20, max_iter=300).fit(v.fit_transform(texts), ys)


def predict(m, text):
    v, c = m
    p = c.predict_proba(v.transform([text]))[0]
    k = int(p.argmax())
    return str(c.classes_[k]), float(p[k])


def prequential(texts, ys, start=START, step=None):
    """시간 순 누적 검증 — i번째를 앞 i건으로 배운 모델로(처음 start 건 뒤). step = 몇 건마다 다시 배우나(기본 = 다시 배우기 ≤ MAX_FITS)."""
    n = len(texts)
    step = step or max(1, -(-(n - start) // MAX_FITS))
    out, m = [], None
    for i in range(start, n):
        if (i - start) % step == 0:
            m = fit(texts[:i], ys[:i])
        out.append((i, *predict(m, texts[i])) if m else (i, None, 0))
    return out


def cover(res, ys, prec=PREC):
    """신뢰 높은 것부터 늘려 정밀도 ≥ prec 를 지키는 가장 큰 덮음 → (덮음, 판정 수, 정확도, 문턱) — evalcls.py cover 와 같은 셈."""
    R = sorted(((c, p, ys[i], i) for i, p, c in res if p is not None), key=lambda x: -x[0])
    best, err, j = (0, len(res), None, None), 0, 0
    while j < len(R):
        k = j
        while k + 1 < len(R) and abs(R[k + 1][0] - R[j][0]) < 1e-12:
            k += 1
        err += sum(1 for g in R[j:k + 1] if g[1] != g[2])
        n = k + 1
        if err <= (1 - prec) * n + 1e-9:
            best = (n, len(res), 1 - err / n, R[k][0])
        j = k + 1
    return best


def stats_file(sid):
    """통계 상태 — 파일이 바뀔 때만 다시 읽음(한 run 에 대상마다 묻는다)."""
    p = path('통계', sid)
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    if _files.get(p, (None,))[0] != mt:
        _files[p] = (mt, load(p, {}))
    return _files[p][1]


def model_of(sid):
    st = stats_file(sid)
    if st.get('문턱') is None or not st.get('보기'):
        return None
    got = _models.get(sid)
    if not got or got[0] != st['지문']:
        got = _models[sid] = (st['지문'], fit([x[2] for x in st['보기']], [x[1] for x in st['보기']]), st['문턱'])
    return got[1:] if got[1] else None


def stats_hook(s, item, env, fps, mode):
    """③ — 규칙이 «모름»인 대상. 켬: 신뢰 ≥ 문턱이면 갈래 · 그림자: 예측을 적어 두고 None. 지난 run 까지의 보기로 배운 모델(한 run 늦음)."""
    sid = s['id']
    st = stats_file(sid)
    old = (st.get('예측') or {}).get(item['id'])
    if mode == '그림자' and old and old.get('지문') == fps[0] and old.get('모델') == st.get('지문'):
        _preds.setdefault(sid, {})[item['id']] = old        # 같은 대상·같은 모델 — 다시 안 잼(15분마다 sklearn 을 읽지 않게)
        return None
    if not have_sklearn():
        return None
    got = model_of(sid)
    if not got:
        return None
    m, thr = got
    g, p = predict(m, text_of(sort.adapter((s.get('대상') or {}).get('종류')), item))
    ok = p >= thr
    if mode == '그림자':
        _preds.setdefault(sid, {})[item['id']] = {'갈래': g, 'p': round(p, 4), '문턱': round(thr, 4), '정함': ok, '지문': fps[0], '모델': st.get('지문')}
        return None
    return {'갈래': g, '근거': f'③ 낱말 통계 {p:.2f} ≥ 문턱 {thr:.2f}'} if ok else None


def stats_after(sid, s, exs, marks, now, dry):
    p = path('통계', sid)
    st = load(p, {})
    h = hashlib.sha1(sort.canon([[e['id'], e['갈래'], e['글']] for e in exs]).encode('utf-8')).hexdigest()
    if st.get('지문') != h:                                    # 보기가 바뀔 때만 다시 잼
        texts, ys = [e['글'] for e in exs], [e['갈래'] for e in exs]
        n, tot, acc, thr = cover(prequential(texts, ys), ys) if len(exs) > START else (0, 0, None, None)
        hist = st.get('내력') or []
        if not hist or len(exs) >= hist[-1][0] + AGAIN_FLAT:
            hist.append([len(exs), round(n / tot, 4) if tot else 0.0])
        st.update({'지문': h, '보기': [[e['id'], e['갈래'], e['글']] for e in exs], 'n': len(exs), '문턱': thr, '덮음': n, '잰 수': tot,
                   '정확': acc, '잰 때': now, '내력': hist})
    fresh = _preds.pop(sid, {})                              # 이번 run 에 규칙이 «모름»이던 대상(대기 + 대기 뺌 = 마감 지난 글)
    keep = set(sort.state(sid)['대기']) | set(fresh)
    preds = {**(st.get('예측') or {}), **fresh}
    done = {e['id']: e for e in exs}
    tally = dict(st.get('대조') or {'맞음': 0, '틀림': 0, '모름': 0})
    rows = []
    for tid in sorted(preds):
        e = done.get(tid)
        if e is None:
            continue
        pr = preds.pop(tid)
        k = ('맞음' if pr['갈래'] == e['갈래'] else '틀림') if pr['정함'] else '모름'
        tally[k] += 1
        rows.append({'시각': now, '체계': sid, '대상': tid, '일': k, '예측': pr['갈래'], 'p': pr['p'], '문턱': pr['문턱'], '판정': e['갈래']})
    st['예측'] = {k: v for k, v in preds.items() if k in keep}   # 대기 뺌 글도 남김 — 지우면 15분마다 다시 재느라 sklearn 을 읽는다
    st['대조'] = tally
    why = []
    if len(exs) > AGAIN_N:
        why.append(f'보기 {AGAIN_N}건 넘음')
    if marks >= AGAIN_MARKS:
        why.append(f'사람 표시 {AGAIN_MARKS}건')
    hist = st.get('내력') or []
    if len(hist) >= 2 and hist[-1][1] <= hist[-2][1]:
        why.append(f'덮음이 보기 {AGAIN_FLAT}건 동안 안 늚')
    if not dry:
        sort.write_if_changed(p, st)
        sort.append_lines(os.path.join(sort.INDEX, '통계.jsonl'), rows)
        for w in why:
            queue(f'③ 낱말 통계 다시 재기 — 체계 «{sid}» {w} · 이웃 판정(로컬 임베딩)까지 다시 잼(제작자 측정 대본 · 설계 §3)')
    return {'통계': {'보기': len(exs), '문턱': None if st.get('문턱') is None else round(st['문턱'], 4), '덮음': f'{st.get("덮음", 0)}/{st.get("잰 수", 0)}',
                   '대조': tally, '예측 대기': len(st['예측']), '다시 재기': why}}


# ───────── 엔진이 부름 ─────────
def after_system(sid, s, ad, decided, now, dry):
    """sort.run 이 체계 하나를 끝낸 뒤(판정은 이미 정해짐) — 켠 것만. 돌려줌 = 요약(run 의 돌려줌에는 안 들어감)."""
    adopt_on, stats_on = modes(s)
    exs = examples(sid, s, ad, decided)
    out = {'보기': len(exs)}
    if adopt_on:
        out.update(adopt(sid, s, exs, now, dry))
    if stats_on and not have_sklearn():
        out['통계'] = '건너뜀 — 이 파이썬에 sklearn 없음(sort_learn.py tick 이 py -3 으로 맡음)'
    elif stats_on:
        out.update(stats_after(sid, s, exs, marks_of(decided), now, dry))
    return out


# ───────── 15분 확인 길(collect-tick.py 가 py -3 으로 부름) ─────────
def tick(inbox=True):
    """배우기 틱 — ①판정은 안 쓰고(dry) 배우기만 쓰는 sort.run(엔진 상태·체계 파일이 바뀐 때만) ②받은함 그림자(S6 · 새 사람 이동이 있을 때만 sklearn).
    둘을 따로 감쌈. 돌려줌 = {돎, 줄[알릴 것]}. 수집 판정은 이미 끝난 뒤라 여기 실패는 수집에 안 닿는다."""
    out = {'돎': False, '줄': []}
    try:
        S = {k: s for k, s in sort.systems().items() if not s.get('_err') and s.get('켬', True) is not False}
        on = sorted(k for k, s in S.items() if sort.learn_on(s))
        files = lambda k: (os.path.join(sort.INDEX, k + '.json'), S[k]['_file'], path('채택', k), path('통계', k))  # noqa: E731
        mark = {k: [os.path.getmtime(f) if os.path.exists(f) else 0 for f in files(k)] for k in on}   # 돌기 전 표 — 배우기 파일이 바뀐 다음 틱도 한 번 더(새 모델로 대기 예측)
        mp = os.path.join(sort.INDEX, '배우기-틱.json')
        last = load(mp, {})
        if on and last.get('표') != json.loads(json.dumps(mark)):
            for k in on:
                ad = sort.adapter((S[k].get('대상') or {}).get('종류'))
                if ad is not None and hasattr(ad, 'prepare'):
                    ad.prepare()
            sort.run(None, dry=True, learn_dry=False)
            out['돎'] = True
            for k, v in sort.LEARNED.items():
                if '오류' in v:
                    out['줄'].append(f'배우기 {k} 오류 {v["오류"]}'[:300])
            last = {'표': mark, '돈 때': now_s()}
        sort.write_json(mp, {**last, '마지막': now_s()})          # 틱이 살아 있나(건너뛴 틱도 시각만 적음)
    except Exception as e:
        out['줄'].append(f'배우기 틱 예외 {e!r}'[:300])
    if inbox:
        try:
            import sort_inbox
            r = sort_inbox.shadow(peek=False)
            if r['줄']:
                out['줄'].append(f'받은함 그림자 — 새로 잰 사람 이동 {len(r["줄"])}(' + ' · '.join(x['결과'] for x in r['줄']) + f') · 연속 {r["연속"]} · 최고 {r["최고"]}')
        except Exception as e:
            out['줄'].append(f'받은함 그림자 예외 {e!r}'[:300])
    return out


if __name__ == '__main__':
    sys.modules.setdefault('sort_learn', sys.modules['__main__'])
    sys.stdout.reconfigure(encoding='utf-8')
    if sys.argv[1:] == ['tick']:
        print('\n'.join(tick()['줄']))
    else:
        sys.exit('py -3 3_시스템/sort_learn.py tick   # 15분 확인 길(collect-tick.py) — 보기·상태는 sort.py learn')


def status(sid):
    s = sort.systems().get(sid) or {}
    a, m = modes(s)
    out = {'자동채택': '그림자' if a else '끔', '통계': m or False}
    st = load(path('채택', sid), None)
    if st:
        out['후보'] = {k: {x: c.get(x) for x in ('상태', '자리', '칸', '낱말', '갈래', '지지', '연속', '필요')} for k, c in sorted(st['후보'].items())}
    ss = load(path('통계', sid), None)
    if ss:
        out['③'] = {k: ss.get(k) for k in ('n', '문턱', '덮음', '잰 수', '정확', '잰 때', '대조', '내력')}
    return out


def replay(sid, decided=None, stats_step=1):
    """지금 판정으로 S5 그림자 흉내 + ③ 시간 순 누적 검증 — 아무것도 안 씀(사용량 0). decided 를 안 주면 run(dry) 한 번."""
    s = sort.systems()[sid]
    ad = sort.adapter((s.get('대상') or {}).get('종류'))
    if decided is None:
        if ad is not None and hasattr(ad, 'prepare'):
            ad.prepare()
        sort.run(None, dry=True)
        decided = sort.DECIDED.get(sid) or []
    exs = examples(sid, s, ad, decided)
    st, log = replay_adopt(s, sid, exs)
    out = {'체계': sid, '판정': len(decided), '보기': len(exs), '갈래': dict(Counter(e['갈래'] for e in exs)),
           '자리 없이 후보': sorted((c['낱말'], c['갈래'], c['지지']) for c in mine(exs, scoped=False).values()),
           '자리 안 후보(끝)': sorted((c['자리'], c['낱말'], c['갈래'], c['지지']) for c in mine(exs).values()),
           '그림자': states(st), '일': dict(Counter(x['일'] for x in log)),
           '최고 연속': max((c['연속'] for c in st['후보'].values()), default=0),
           '통과': [(c['자리'], c['낱말'], c['갈래']) for c in st['후보'].values() if c['상태'] in ('통과', '은퇴')],
           '탈락 예': [(c['자리'], c['낱말'], c['갈래'], c['연속'], (c.get('어긋남') or {}).get('갈래')) for c in st['후보'].values() if c['상태'] == '탈락'][:6]}
    if len(exs) > START:
        texts, ys = [e['글'] for e in exs], [e['갈래'] for e in exs]
        n, tot, acc, thr = cover(prequential(texts, ys, step=stats_step), ys)
        out['③'] = {'덮음': f'{n}/{tot}', '정확': acc, '문턱': thr}
    return out


def replay_text(sid):
    return json.dumps(replay(sid), ensure_ascii=False, default=str)
