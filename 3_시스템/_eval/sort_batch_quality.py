"""묶어 부르기 질 시험(S4 · 2026-11-18 · 설계 §5) — 판정이 이미 있는 공지(추출 캐시)를 묶음(≤6건/호출)으로 다시 뽑아 옛 1건 판정과 칸마다 대조.
사용량이 든다(claude -p · sonnet 별칭 · --effort low · claude_bin 경유) — 사용자 허가(11-18 03:5x) 상한 = 대상 20건 · 환산 $0.17 · 넘으면 멈춤.
캐시·볼트에 안 쓴다(결과는 --out JSON 하나).

고르기: 지금 글로 뽑은 캐시(첨부 이름이 같음 · 꽁돈 칸 켬·끔이 지금과 같음 · 로그인 출처 글 뺌) 중 꽁돈 칸 켬 10 · 끔 10(글 id 해시 차례 — 고정).
대조(묶음 B 대 옛 캐시 C): 판정(judge_one) · 꽁돈(gold) · 마감 · 첨부에만 · 조건 축(모임) · 조건 축+값 · 지급 형태 · 의무 종류 · 소득심사 ·
     근거가 그 글 원문에 있나(묶음이 다른 글 근거를 섞나).
기준선: 남은 몫으로 B 와 C 판정이 어긋난 글을 한 건씩 다시(extract_one) — 어긋남이 묶음 탓인지(한 건도 C 와 같음) 원래 흔들림인지(한 건도 C 와 다름).

  py -3 3_시스템/_eval/sort_batch_quality.py              # 계획·예상만(사용량 0)
  py -3 3_시스템/_eval/sort_batch_quality.py --yes --out <json>
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time

SYS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SYS)
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')
CAP_N, CAP_USD, SIZE = 20, 0.17, 6
PRICE_IN, PRICE_OUT = 2.0, 10.0           # sonnet 100만 토큰당 $(sort.py 와 같음)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def pick(nf):
    rows = []
    for n in nf.notices():
        if n.get('hint') or not os.path.exists(nf.cpath(n)):
            continue
        d = json.load(open(nf.cpath(n), encoding='utf-8'))
        if set(d.get('_att') or []) != {a for a, _ in n['att']} or nf.gold_on(n) != ('지급' in d):
            continue
        rows.append((hashlib.sha1(f'{n["sid"]}:{n["id"]}'.encode()).hexdigest(), n, d))
    rows.sort(key=lambda r: r[0])
    on = [r for r in rows if nf.gold_on(r[1])][:CAP_N // 2]
    off = [r for r in rows if not nf.gold_on(r[1])][:CAP_N - len(on)]
    return on + off, len(rows)


def est(nf, group):
    chars = sum(len(nf.body_of(n)) for n in group)
    i = 2787 + 120 + 0.324 * chars
    o = 370 * len(group)
    return (i * PRICE_IN + o * PRICE_OUT) / 1e6


def fields(nf, n, d, me):
    v, _ = nf.judge_one(n, json.loads(json.dumps(d)), me)
    g = nf.gold(n, d, me, v)[0]
    strong, weak = nf.src_text(n)
    conds = d.get('조건') or []
    seen = [bool(nf.norm(c.get('근거'))) and (nf.norm(c.get('근거')) in strong or nf.norm(c.get('근거')) in weak) for c in conds]
    return {'판정': v, '꽁돈': g, '마감': d.get('마감'), '첨부에만': bool(d.get('첨부에만')),
            '축': sorted({c.get('축') for c in conds}), '축값': sorted(json.dumps([c.get('축'), c.get('값')], ensure_ascii=False, sort_keys=True) for c in conds),
            '지급': (d.get('지급') or {}).get('형태'), '의무': sorted({o.get('종류') for o in d.get('의무') or []}),
            '소득심사': bool((d.get('소득심사') or {}).get('반영')), '근거있음': [sum(seen), len(seen)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--yes', action='store_true')
    ap.add_argument('--out')
    a = ap.parse_args()
    nf = load('notice_filter_q', os.path.join(SYS, 'notice-filter.py'))
    me = nf.card()
    chosen, pool = pick(nf)
    ns = [r[1] for r in chosen]
    groups = nf.batches(ns, SIZE)
    plan = sum(est(nf, g) for g in groups)
    print(f'고를 수 있는 글 {pool} · 고름 {len(ns)}(꽁돈 칸 켬 {sum(nf.gold_on(n) for n in ns)}) · 묶음 {[len(g) for g in groups]} · 예상 ≈${plan:.3f}(상한 ${CAP_USD})')
    if not a.yes:
        print('계획만 — 부르려면 --yes')
        return 0
    if plan > CAP_USD:
        print('예상이 상한을 넘음 — 안 부름')
        return 1
    import ingest_vision as iv
    why = iv.subscription()
    if why:
        print(f'멈춤: {why}')
        return 1
    spent, out, t0, guess = 0.0, [], time.time(), 0.0
    old = {(r[1]['sid'], r[1]['id']): r[2] for r in chosen}
    for g in groups:
        ratio = max(1.0, spent / guess) if guess else 1.0      # 잰 값으로 예상을 고침(11-18 1회: 예상이 2.7배 낮아 상한을 $0.014 넘음)
        if spent + est(nf, g) * ratio > CAP_USD:
            print(f'상한 — 남은 묶음 안 부름(쓴 ${spent:.4f} · 예상 보정 ×{ratio:.1f})')
            break
        try:
            res = nf.extract_many(g)
        except iv.Stop as e:
            print(f'멈춤({e.kind}): {e.why}')
            break
        guess += est(nf, g)
        spent += sum((u or {}).get('cost') or 0 for _, u, _ in res)
        for n, (d, u, err) in zip(g, res):
            row = {'글': f'{n["sid"]}:{n["id"]}', '제목': n['title'][:50], '꽁돈칸': nf.gold_on(n), '묶음': len(g), '오류': err,
                   '옛': fields(nf, n, old[(n['sid'], n['id'])], me), '사용량': u}
            if d:
                row['묶음판'] = fields(nf, n, d, me)
                row['묶음글'] = {k: v for k, v in d.items() if not k.startswith('_')}
            out.append(row)
        print(f'  묶음 {len(g)} · 누적 ${spent:.4f}')
    # 기준선 — 판정·꽁돈이 어긋난 글만 한 건씩(남은 몫 안)
    for row in out:
        b = row.get('묶음판')
        if not b or (b['판정'] == row['옛']['판정'] and b['꽁돈'] == row['옛']['꽁돈']):
            continue
        n = next(x for x in ns if f'{x["sid"]}:{x["id"]}' == row['글'])
        if spent + est(nf, [n]) > CAP_USD:
            row['한건'] = '상한 — 못 잼'
            continue
        try:
            d, u, err = nf.extract_one(n)
        except iv.Stop as e:
            row['한건'] = f'멈춤 {e.kind}'
            break
        spent += (u or {}).get('cost') or 0
        row['한건'] = fields(nf, n, d, me) if d else f'오류 {err}'
    keys = ['판정', '꽁돈', '마감', '첨부에만', '축', '축값', '지급', '의무', '소득심사']
    ok_rows = [r for r in out if r.get('묶음판')]
    agree = {k: sum(r['묶음판'][k] == r['옛'][k] for r in ok_rows) for k in keys}
    gold_rows = [r for r in ok_rows if r['꽁돈칸']]
    for k in ('지급', '의무', '소득심사'):
        agree[k] = f'{sum(r["묶음판"][k] == r["옛"][k] for r in gold_rows)}/{len(gold_rows)}'
    seen_b = [sum(r['묶음판']['근거있음'][i] for r in ok_rows) for i in (0, 1)]
    seen_c = [sum(r['옛']['근거있음'][i] for r in ok_rows) for i in (0, 1)]
    usage_in = sum((r['사용량'] or {}).get('in', 0) for r in ok_rows)
    usage_out = sum((r['사용량'] or {}).get('out', 0) for r in ok_rows)
    base = [r for r in out if isinstance(r.get('한건'), dict)]
    summary = {'대상': len(out), '묶음 성공': len(ok_rows), '일치(칸마다)': {k: (agree[k] if isinstance(agree[k], str) else f'{agree[k]}/{len(ok_rows)}') for k in keys},
               '근거가 원문에 있음': {'묶음': seen_b, '옛': seen_c},
               '1건 평균 사용량': {'입력': round(usage_in / max(1, len(ok_rows))), '출력': round(usage_out / max(1, len(ok_rows))),
                              '$': round(sum((r['사용량'] or {}).get('cost') or 0 for r in ok_rows) / max(1, len(ok_rows)), 5)},
               '기준선(어긋난 글 한 건씩)': [{'글': r['글'], '옛': r['옛']['판정'], '묶음': r['묶음판']['판정'], '한건': r['한건']['판정'],
                                     '꽁돈 옛·묶음·한건': [r['옛']['꽁돈'], r['묶음판']['꽁돈'], r['한건']['꽁돈']]} for r in base],
               '쓴 $': round(spent, 4), '걸린 초': round(time.time() - t0)}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    if a.out:
        with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
            json.dump({'요약': summary, '글': out}, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
