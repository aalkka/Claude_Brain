"""공지 필터·황금 → sort 체계 이관 골든 대조(S3 M0~M2 · 2026-11-18 · 설계 §9) — 사본 위에서 · Claude 0 · 볼트에 안 씀.

사본: _index/collect(상태·추출 캐시·대기 칸·보관 칸·평가) · 자격 카드 · 조리법 · 수집 대기열 · 일정 파일 2개를 임시 폴더로 복사하고
     공지 필터의 자리(STATE·CACHE·STAGE·ARCH·MARKS·REPORT·STATUS·QUEUE·RECIPES·CARD)와 오늘·시각을 그쪽·고정값으로 돌린다.
     1_수집 글·색인은 볼트 것을 읽기만 한다(엔진 상태 사본이 가리키는 글만).
M0 골든  = 옛 길(스위치 끔 · notice-filter sort_on → False): 출처별 judged()·verdicts() · 판정표(judge) · 일정 파일(장학-마감·공지-마감) · 세션 줄 ·
           moa 2개 rows(--all·보임). 옛 길은 sort 를 안 부른다(장부 폴더가 안 생겨야).
M1 이은 길 = S4 잇기 그대로(notice-filter bridge → sort_collect.bridge → sort.run · 장부는 임시 폴더) → 같은 출력.
           두 번째 bridge(rebridge 뒤)의 sort.run 은 전부 ① 기억이어야 한다.
M2 대기  = sort 판정 대기(자리 = 출처) 대 옛 extract 가 뽑을 글 — 공지-들이기 대기 = 옛 todo 와 같아야 · 황금만의 대기는 따로 셈.
M3 떨어짐 = sort.run 이 오류를 내면 그 회차는 옛 길 — 출력이 골든과 같고(세션 줄은 대기열 +1 만) 대기열에 sort 줄 하나.
합격 = 파일마다 바이트 같음 · 다리 빗나감 0 · M3.

  py -3 3_시스템/_eval/sort_notice_golden.py [--keep <폴더>]     # --keep = 임시 폴더를 지우지 않고 그 자리에 둠
"""
import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
import types
from datetime import date, datetime

SYS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.path.dirname(SYS)
sys.path.insert(0, SYS)
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep')
    ap.add_argument('--systems', help='체계 폴더(기본 3_시스템/sort · 시험이 헛돌지 않나 볼 때 고친 사본)')
    a = ap.parse_args()
    if a.systems:
        import sort
        sort.SYSTEMS = os.path.abspath(a.systems)
    T = os.path.abspath(a.keep) if a.keep else tempfile.mkdtemp(prefix='sort-golden-')
    os.makedirs(T, exist_ok=True)
    try:
        return run(T)
    finally:
        if not a.keep:
            shutil.rmtree(T, ignore_errors=True)


def run(T):
    NOW = datetime.now().replace(second=0, microsecond=0)
    TODAY = NOW.date()
    nf = load('notice_filter', os.path.join(SYS, 'notice-filter.py'))
    # ── 사본 ──
    st = os.path.join(T, 'state')
    shutil.copytree(nf.STATE, st, ignore=shutil.ignore_patterns('*.log', '*.lock', '제출'))
    shutil.copytree(nf.RECIPES, os.path.join(T, 'collect'), ignore=shutil.ignore_patterns('browser', 'candidates'))
    shutil.copy(nf.CARD, os.path.join(T, 'card.md'))
    if os.path.exists(nf.QUEUE):
        shutil.copy(nf.QUEUE, os.path.join(T, 'queue.md'))
    sheets = sorted({rc['filter']['schedule'] for rc in nf.recipes() if rc['filter'].get('schedule')})
    for side in ('golden', 'new', 'fallback'):
        os.makedirs(os.path.join(T, side, '일정'))
        for s in sheets:
            src = os.path.join(VAULT, '2_지식', '일정', s)
            if os.path.exists(src):
                shutil.copy(src, os.path.join(T, side, '일정', s))
    nf.STATE, nf.CACHE, nf.STAGE, nf.ARCH = st, os.path.join(st, '조건'), os.path.join(st, 'stage'), os.path.join(st, 'archive')
    nf.MARKS, nf.RECIPES, nf.CARD, nf.QUEUE = os.path.join(st, '평가.json'), os.path.join(T, 'collect'), os.path.join(T, 'card.md'), os.path.join(T, 'queue.md')
    nf._card.clear()

    class Day(date):
        @classmethod
        def today(cls):
            return TODAY
    nf.date = Day
    nf.time = types.SimpleNamespace(strftime=lambda fmt, *x: NOW.strftime(fmt), time=time.time, sleep=time.sleep)
    real_ws = nf.write_schedule
    side = {'now': 'golden'}
    nf.write_schedule = lambda rows, SCHED, label: real_ws(rows, os.path.join(T, side['now'], '일정', os.path.basename(SCHED)), label)
    g = load('gather', os.path.join(SYS, 'gather', 'gather.py'))
    g._nf[:] = [nf]
    moas = [p for p in g.everywhere() if not os.path.relpath(p, VAULT).replace('\\', '/').startswith(('0_작업/', '.'))]

    def capture(name):
        side['now'] = name
        D = os.path.join(T, name)
        nf.REPORT, nf.STATUS = os.path.join(D, '판정.md'), os.path.join(D, '.status.txt')
        nf._card.clear()
        out = {}
        for rc in nf.recipes():
            out[rc['id']] = {'judged': nf.judged(rc['id']), 'verdicts': nf.verdicts(rc['id'])}
        with open(os.path.join(D, 'judged.json'), 'w', encoding='utf-8', newline='\n') as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        nf.judge(quiet=True)
        for p in moas:
            key = os.path.splitext(os.path.basename(p))[0]
            for keep in (True, False):
                with open(os.path.join(D, f'moa-{key}{"-all" if keep else ""}.json'), 'w', encoding='utf-8', newline='\n') as f:
                    json.dump(g.build(g.load(p), TODAY, keep_all=keep), f, ensure_ascii=False, indent=1)
        return out

    import sort
    import sort_collect as sc
    sort.INDEX = os.path.join(T, 'sort')
    sort.reset()
    # ── M0 골든 = 옛 길(스위치 끔) ──
    nf.sort_on = lambda: False
    nf.rebridge()
    gold_out = capture('golden')
    n76 = sum(len(v['judged']) for v in gold_out.values())
    switch_ok = nf._bridged == [False] and not os.path.exists(sort.INDEX)
    # ── M1 이은 길(notice-filter bridge 그대로) ──
    nf.sort_on = lambda: True
    nf.rebridge()
    sc.MISSES.clear()
    capture('new')
    r1 = dict(nf._sort_run)
    nf.rebridge()
    nf.bridge()
    r2 = dict(nf._sort_run)
    bridged_ok = nf._bridged == [True]
    # ── 대조 ──
    bad = []
    files = sorted(os.listdir(os.path.join(T, 'golden'))) + [f'일정/{s}' for s in sorted(os.listdir(os.path.join(T, 'golden', '일정')))]
    files = [f for f in files if f != '일정']

    def compare(side, skip=()):
        out = []
        for f in files:
            if f in skip:
                continue
            a = open(os.path.join(T, 'golden', f), 'rb').read()
            b = open(os.path.join(T, side, f), 'rb').read() if os.path.exists(os.path.join(T, side, f)) else None
            same = a == b
            print(f'{"같음" if same else "다름"} {side} {f} ({len(a):,} 바이트)')
            if not same:
                out.append(f'{side}/{f}')
                al, bl = a.decode('utf-8').splitlines(), (b or b'').decode('utf-8').splitlines()
                for i, (x, y) in enumerate(zip(al + [''] * len(bl), bl + [''] * len(al))):
                    if x != y:
                        print(f'   {i + 1}행\n   골든 {x[:200]}\n   새것 {y[:200]}')
                        break
        return out
    bad += compare('new')
    if not switch_ok:
        bad.append('M0 스위치 끔인데 sort 가 돎')
    if not bridged_ok:
        bad.append('M1 이은 길이 아님')
    gold_st = sort.state(sc.SYS_GOLD)['items']
    tagged = sum(1 for r in gold_st.values() if r['갈래'] == sc.TAG_GOLD)
    print(f'판정 {n76}건(출처 {len(gold_out)}) · sort 1회 {json.dumps(r1, ensure_ascii=False)}')
    print(f'sort 2회 {json.dumps(r2, ensure_ascii=False)}')
    print(f'황금 판정 {len(gold_st)}건(황금 {tagged}) · 다리 빗나감 {len(sc.MISSES)}')
    memo_ok = all(set(v) <= {'기억', '대기', '대기 뺌', '대상 밖', '앞 체계 대기'} for v in r2.values())
    if not memo_ok:
        bad.append('2회째 기억 아님')
    if sc.MISSES:
        bad.append('다리 빗나감')
    # ── M2 판정 대기(자리 = 출처) 대 옛 extract ──
    todo = {f'collect:{n["sid"]}:{n["id"]}' for n in nf.notices()
            if (n.get('again') or not os.path.exists(nf.cpath(n))) and not ((nf.deadline(n, {}) or '9999') < TODAY.isoformat())}
    pend_n = set(sort.state('공지-들이기')['대기'])
    pend_g = set(sort.state(sc.SYS_GOLD)['대기'])
    print(f'M2 공지-들이기 대기 {len(pend_n)} · 옛 extract 할 글 {len(todo)} · {"같음" if pend_n == todo else "다름"}'
          + (f' (sort만 {sorted(pend_n - todo)[:5]} · 옛것만 {sorted(todo - pend_n)[:5]})' if pend_n != todo else ''))
    print(f'M2 황금만의 대기(캐시는 있는데 황금 칸 없음 · 마감 안 지남) {len(pend_g - pend_n)} · 자리별 {json.dumps(sort.places(), ensure_ascii=False)}')
    for where in sorted(sort.places()):
        est = sort.estimate(sort.pending(where))
        cmds = sc.judge_cmds(where, sort.pending(where))
        print(f'   {where}: {est["건수"]}건 · 주간 ≈{est["주간%"]}% · ' + ' '.join(os.path.basename(x) for x in cmds[0][1:]))
    if pend_n != todo:
        bad.append('M2 대기 다름')
    # ── M3 떨어짐 — sort.run 오류 → 그 회차 옛 길 ──
    qread = lambda: open(nf.QUEUE, encoding='utf-8').read().splitlines() if os.path.exists(nf.QUEUE) else []  # noqa: E731
    q0, real_run = qread(), sort.run

    def boom(*_a, **_k):
        raise RuntimeError('시험 — sort 고장')
    sort.run = boom
    nf.rebridge()
    try:
        capture('fallback')
    finally:
        sort.run = real_run
    fell = nf._bridged == [False] and nf.judge_one is nf._OLD['judge_one'] and nf.gold is nf._OLD['gold']
    added = [ln for ln in qread() if ln not in q0]
    rd = lambda p: open(p, encoding='utf-8').read() if os.path.exists(p) else ''  # noqa: E731
    st_g, st_f = rd(os.path.join(T, 'golden', '.status.txt')), rd(os.path.join(T, 'fallback', '.status.txt'))
    m3 = compare('fallback', skip=('.status.txt',))
    import re
    qn = lambda s: int((re.search(r'수집 대기열 열린 (\d+)건', s) or [0, 0])[1])  # noqa: E731
    m3_ok = fell and not m3 and len(added) == 1 and '`sort`' in added[0] and qn(st_f) == qn(st_g) + 1
    print(f'M3 떨어짐 — 옛 길 {fell} · 출력 다름 {len(m3)} · 대기열 새 줄 {len(added)}({added[0][:60] if added else ""}) · 세션 줄 대기열 {qn(st_g)}→{qn(st_f)} · {"합격" if m3_ok else "불합격"}')
    if not m3_ok:
        bad.append('M3 떨어짐')
    print('\n' + ('합격 — 골든 바이트 같음(이은 길) · 스위치·떨어짐 옛 길' if not bad else f'불합격: {bad}'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
