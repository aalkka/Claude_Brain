"""받은함 자리 그림자(S6 · 2026-11-18 · 설계 §10 · 사용자 11-18 03:2x «받은함에서 이동경로 추적하면 되잖아») — Claude 0 · 아무것도 안 옮김.

받은함에는 판정 단추도 Claude 판정도 없다. 배울 자료 = 이동 장부(fileops ops.jsonl)의 «받은함 → 놓인 자리» 짝:
  옵시디언 안 이동 = by obsidian(outside) · 탐색기 = follow.py 가 by user(outside) · 폰 = by phone · Claude = by claude · 대본 = by script:*.
  배움 = 사람(옵시디언·탐색기·폰) + Claude 이동 · 대본 이동은 뺌(script:inbox 자동 옮김 = 지금 판정기 자신) · 대조 = 사람 이동만.
  자리 = 옮긴 곳의 폴더(지우기 = «휴지통»). 글 = 항목 이름(장부에 남는 것만 — 언제 다시 세도 같은 값).
예측 = ③ 낱말 통계(sort_learn · 글자 2~4-gram TF-IDF + 로지스틱 · 문턱 = 시간 순 누적 검증 정밀도 98%). 그 항목이 받은함에 든 때(든 줄이 없으면
  나간 때) 앞의 장부만으로 배우고 문턱을 잰다 — 그때 돌렸어도 같은 값이라 부르는 때와 상관없는 그림자. 문턱 밑·배운 것 10건 이하 = «모름»
  (자동 옮기기라면 사용자에게 남길 것).
연속 = 시작(처음 돌린 때) 뒤 사람 이동을 시간 순으로: 맞음 +1 · 틀림 → 0 · 모름 = 그대로. 10 이 되면 대기열 한 줄(자동 옮기기를 켤지 사용자에게).
  켜는 코드는 없다 — 이 대본은 fileops 를 부르지 않고 받은함·장부에 쓰지 않는다(inbox.classify_one 자동 옮김은 그대로).
  py -3 3_시스템/sort_inbox.py              # 시작 뒤 대조·연속 + 지금 받은함 항목 예측(보기만) · 상태 _index/sort/받은함-그림자.json · 장부 받은함-그림자.jsonl
  py -3 3_시스템/sort_inbox.py --replay     # 장부 처음부터 다시 셈(아무것도 안 씀 · 측정)
"""
import argparse
import json
import os
import posixpath
import sys
import time

SYS = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(SYS)
if SYS not in sys.path:
    sys.path.insert(0, SYS)
import roles  # noqa: E402
import sort  # noqa: E402
import sort_learn as L  # noqa: E402

HUMAN = ('obsidian', 'user', 'phone')       # 사람이 옮긴 줄(옵시디언 · 탐색기 = follow.py · 폰)
LEARN_BY = HUMAN + ('claude',)
TRASH = '휴지통'
NEED = 10
IN_OPS = ('cp', 'mv', 'rename', 'restore')
OUT_OPS = ('mv', 'rename', 'rm')
LEDGER = os.path.join(VAULT, '3_시스템', 'ledger', 'ops.jsonl')     # = fileops.OPS


def read(path):
    rows = []
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if isinstance(r, dict) and r.get('ts'):
                    rows.append(r)
    except OSError:
        pass
    rows.sort(key=lambda r: r['ts'])
    return rows


def trips(rows, base):
    """받은함에서 나간 줄 → [{id, 이름, 듦, 나감, 누가, 자리}] (시간 순). 받은함 안 이름 바꿈은 든 때를 이어 받음."""
    base = base.rstrip('/') + '/'
    came, out = {}, []
    for r in rows:
        op, src, dst = r.get('op'), r.get('src') or '', r.get('dst') or ''
        if src.startswith(base) and op in OUT_OPS:
            if op != 'rm' and dst.startswith(base):
                came[dst] = came.pop(src, r['ts'])
                continue
            to = TRASH if op == 'rm' or dst.startswith('.trash/') else posixpath.dirname(dst)
            out.append({'id': r.get('id') or r['ts'], '이름': posixpath.basename(src), '듦': came.pop(src, None), '나감': r['ts'],
                        '누가': r.get('by') or '', '자리': to})
        elif dst.startswith(base) and op in IN_OPS:
            came[dst] = r['ts']
    return out


class Shadow:
    """시간 순 그림자 — 때 t 앞의 배움 줄만으로 모델·문턱(배운 수마다 한 번 · 앞부분이 같으니 수가 열쇠)."""
    def __init__(self, ts):
        self.learn = [t for t in ts if t['누가'] in LEARN_BY]
        self._m = {}

    def guess(self, name, t0):
        tr = [t for t in self.learn if t['나감'] < t0]
        k = len(tr)
        if k <= L.START:
            return None, 0.0, None, k
        if k not in self._m:
            texts, ys = [x['이름'] for x in tr], [x['자리'] for x in tr]
            self._m[k] = (L.cover(L.prequential(texts, ys), ys)[3], L.fit(texts, ys))
        thr, m = self._m[k]
        if m is None:
            return None, 0.0, thr, k
        g, p = L.predict(m, name)
        return g, p, thr, k


def judge_trip(sh, t):
    g, p, thr, k = sh.guess(t['이름'], t['듦'] or t['나감'])
    sure = g is not None and thr is not None and p >= thr
    return {'id': t['id'], '이름': t['이름'], '듦': t['듦'], '나감': t['나감'], '누가': t['누가'], '실제': t['자리'], '예측': g,
            'p': round(p, 4), '문턱': None if thr is None else round(thr, 4), '배운 수': k,
            '결과': ('맞음' if g == t['자리'] else '틀림') if sure else '모름'}


def streak(rows):
    cur = best = 0
    for r in rows:
        if r['결과'] == '맞음':
            cur += 1
        elif r['결과'] == '틀림':
            cur = 0
        best = max(best, cur)
    return cur, best


def inbox_now(inbox_dir):
    try:
        return sorted(p for p in os.listdir(inbox_dir) if not p.startswith(('.', '_')))
    except OSError:
        return []


def shadow(ledger=LEDGER, base=None, inbox_dir=None, index=None, now=None, replay=False, peek=True):
    """돌려줌 = 요약. replay = 처음부터 · 아무것도 안 씀. 아니면 상태·장부(그림자 것만)를 index 에 쓰고 10 연속이면 대기열 한 줄."""
    base = base or roles.path('inbox')
    inbox_dir = inbox_dir or roles.abs('inbox')
    index = index or sort.INDEX
    now = now or time.strftime('%Y-%m-%dT%H:%M:%S')
    sp, lp = os.path.join(index, '받은함-그림자.json'), os.path.join(index, '받은함-그림자.jsonl')
    st = {'시작': '', '본': {}, '통과': None} if replay else L.load(sp, {'시작': now, '본': {}, '통과': None})
    ts = trips(read(ledger), base)
    sh = Shadow(ts)
    new = []
    for t in ts:
        if t['누가'] in HUMAN and t['나감'] >= st['시작'] and t['id'] not in st['본']:
            st['본'][t['id']] = r = judge_trip(sh, t)
            new.append(r)
    seq = sorted(st['본'].values(), key=lambda r: r['나감'])
    st['연속'], st['최고'] = streak(seq)
    passed = st['연속'] >= NEED and not st.get('통과')
    if passed:
        st['통과'] = now
    if not replay:
        sort.write_if_changed(sp, st)
        sort.append_lines(lp, new)
        if passed:
            L.queue(f'받은함 자리 그림자 {NEED}건 연속 일치 — 사람이 옮길 자리를 ③ 이 맞힘 · 자동 옮기기를 켤지 사용자에게(`py -3 3_시스템/sort_inbox.py`)')
    cnt = {k: sum(1 for r in seq if r['결과'] == k) for k in ('맞음', '틀림', '모름')}
    now_items = []
    for name in inbox_now(inbox_dir) if peek else []:          # peek=False(15분 확인) = 새 사람 이동이 없으면 sklearn 을 안 읽음
        g, p, thr, k = sh.guess(name, '9999')
        now_items.append({'이름': name, '예측': g, 'p': round(p, 4), '문턱': None if thr is None else round(thr, 4),
                          '옮길 것': g is not None and thr is not None and p >= thr})
    return {'시작': st['시작'] or '(처음부터)', '배움 줄': len(sh.learn), '받은함에서 나간 줄': len(ts), '사람 대조': len(seq), **cnt,
            '연속': st['연속'], '최고': st['최고'], '통과': st.get('통과'), '새로 잰 것': len(new), '지금 받은함': now_items,
            '줄': seq if replay else new}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='받은함 자리 그림자 — 옮기지 않음')
    ap.add_argument('--replay', action='store_true', help='장부 처음부터 다시 셈(안 씀)')
    ap.add_argument('--quiet', action='store_true', help='15분 확인용 — 지금 받은함 예측 안 함 · 새로 잰 것이 있을 때만 한 줄')
    a = ap.parse_args()
    res = shadow(replay=a.replay, peek=not a.quiet)
    rows = res.pop('줄')
    if a.quiet:
        if rows:
            print(f'받은함 그림자 — 새로 잰 사람 이동 {len(rows)}(' + ' · '.join(r['결과'] for r in rows) + f') · 연속 {res["연속"]} · 최고 {res["최고"]}'
                  + (f' · 통과 {res["통과"]}' if res['통과'] else ''))
        return
    print(json.dumps(res, ensure_ascii=False))
    for r in rows:
        print(f'  {r["나감"][:16]} {r["누가"]:8} {r["결과"]} {r["이름"][:40]} → 실제 {r["실제"]} · 예측 {r["예측"]} {r["p"]} (문턱 {r["문턱"]} · 배운 {r["배운 수"]})')


if __name__ == '__main__':
    main()
