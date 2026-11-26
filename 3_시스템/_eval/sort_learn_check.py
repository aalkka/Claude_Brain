"""sort 배우기 시험(S5·S6·S7 · 2026-11-18) — Claude 0 · 흉내는 임시 폴더 · 진짜 자료는 읽기만(장부·상태·받은함에 안 씀).

A S5 그림자 흉내(시험 체계 · 가짜 Claude 특징): 처음 run = 역사 · 후보 등록 · 10건 연속 → 통과 + 대기열 한 줄(한 번) · 통과 뒤 어긋남 → 은퇴 ·
     빼는 갈래 20건 · 자리 따로 셈 · 통과 전 어긋남 → 탈락(다시 안 올림) · revert → 거부 · 그림자가 판정·체계 파일을 안 바꿈 · 끔 = 파일 0.
B S5 76건 재생(진짜 공지 판정 · run dry): 보기 76 · 통과 0 · 진짜 장부 안 바뀜 · 기본 끔이라 배우기 0 + 낱말 꼴(설계 §6 «겨울계절수업·전형») 대조.
C S7 evalcls 재생: 측정/notice.json·folder.json 을 sort_learn 의 prequential·cover 로 → 측정 result.json B 값(덮음·판정 수·문턱·정확)과 같음.
D S7 흉내: 그림자 = 예측만 적고 판정은 대기 그대로 → Claude 판정이 오면 대조 맞음 · 켬 = ③ 이 정함(판정자 통계 · 안 배움).
E S7 다시 재기 = 대기열 한 줄(열린 동안 한 번).
F S6 흉내(가짜 장부): 시작 뒤 사람 이동 10 연속 맞음 → 통과 + 대기열 한 줄 · 틀리면 연속 0 · 장부·받은함 안 바뀜 + 진짜 장부 재생(읽기만).
G 15분 확인 길: 배우기 틱(dry 판정 + 배우기만 씀 · 멎으면 건너뜀) · sklearn 없는 파이썬(py -3.11)은 ③ 건너뜀.

  py -3 3_시스템/_eval/sort_learn_check.py
"""
import json
import os
import re
import shutil
import sys
import tempfile
import time
import types

SYS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.path.dirname(SYS)
sys.path.insert(0, SYS)
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')
import sort  # noqa: E402
import sort_learn as L  # noqa: E402
import sort_inbox as SI  # noqa: E402

REAL_SYSTEMS, REAL_INDEX = sort.SYSTEMS, sort.INDEX
T = tempfile.mkdtemp(prefix='sort-learn-')
fails = []


def ok(name, cond, more=''):
    print(('통과 ' if cond else '실패 ') + name + (f' — {more}' if more else ''))
    if not cond:
        fails.append(name)


# ── 가짜 Claude 특징(함수 규칙) + 시험 어댑터 ──
def fjudge(item, env):
    g = item['facts'].get('_claude')
    return {'갈래': g, '근거': 'claude 특징'} if g else {'모름': '추출 전'}


fake = types.ModuleType('fake_claude')
fake.judge = fjudge
sys.modules['fake_claude'] = fake


class Ad:
    LEARN = ('제목',)

    def __init__(self):
        self.rows = {}

    def items(self):
        return [{'id': k, 'facts': dict(f), '글자': 10, 'raw': {}} for k, f in sorted(self.rows.items())]

    def match(self, it, spec):
        return True

    def place(self, it):
        return it['facts']['자리']

    def pre(self, it):
        return {**it, 'facts': {k: v for k, v in it['facts'].items() if k != '_claude'}}

    def text(self, it):
        return it['facts']['제목']

    def order(self, it):
        return (it['id'],)


def system(sid, adopt='끔', stats=False):
    return {'id': sid, '이름': sid, '판': 1, '대상': {'종류': '시험글'},
            '규칙': [{'id': 'n1', '말': '가짜 Claude 특징대로', '만든이': '시험', '함수': 'fake_claude.judge'}],
            '갈래': {'들임': {'동작': [{'들이기': {}}]}, '뺌': {'동작': [{'장부': {}}]}}, '모르면': '들임',
            '사다리': {'기억': True, '규칙': True, '통계': stats, 'claude': '버튼'}, '자동채택': adopt}


def setup(name, s):
    d, idx = os.path.join(T, name, 'sys'), os.path.join(T, name, 'idx')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, s['id'] + '.json'), 'w', encoding='utf-8') as f:
        json.dump(s, f, ensure_ascii=False)
    sort.SYSTEMS, sort.INDEX = d, idx
    L.QUEUE = os.path.join(T, name, 'queue.md')
    sort.reset()
    L._files.clear()
    L._models.clear()
    return d, idx


def add(ad, start, n, title, place, g):
    for k in range(start, start + n):
        ad.rows[f'{k:04d}'] = {'제목': f'{title} {k}', '자리': place, **({'_claude': g} if g else {})}
    return start + n


def qlines():
    return [x for x in (open(L.QUEUE, encoding='utf-8').read().splitlines() if os.path.exists(L.QUEUE) else []) if x.startswith('- [ ]')]


def cand(sid, word, place):
    st = L.load(L.path('채택', sid), {'후보': {}})
    return next(((k, c) for k, c in st['후보'].items() if c['낱말'] == word and c['자리'] == place), (None, None))


def verdicts(sid):
    return {k: (r['갈래'], r['판정자'], r['규칙']) for k, r in sort.state(sid)['items'].items()}


try:
    # ════ A S5 그림자 흉내 ════
    ad = Ad()
    sort.register_adapter('시험글', ad)
    d, idx = setup('A', system('T', adopt='그림자'))
    sysfile = open(os.path.join(d, 'T.json'), 'rb').read()
    i = add(ad, 0, 4, '계절수업 안내', 'A', '들임')
    for k in range(8):
        ad.rows[f'{i + k:04d}'] = {'제목': f'기타공지 {i + k}', '자리': 'A', '_claude': '들임' if k % 2 else '뺌'}
    i += 8
    r1 = sort.run()
    k1, c1 = cand('T', '계절수업', 'A')
    ok('S5 처음 run = 역사 — 후보 «계절수업»(안내와 같은 글 묶음 → 긴 낱말 하나) · 연속 0 · 필요 10',
       c1 is not None and c1['연속'] == 0 and c1['필요'] == 10 and c1['상태'] == '그림자' and cand('T', '안내', 'A')[1] is None, str(c1))
    ok('S5 run 돌려줌 꼴 그대로(배우기는 LEARNED 에만)', set(r1['T']) <= {'규칙', '바뀜', '기억'} and 'T' in sort.LEARNED, str(r1))
    i = add(ad, i, 9, '계절수업 안내', 'A', '들임')
    sort.run()
    ok('S5 새 보기 9건 → 연속 9 · 아직 그림자', cand('T', '계절수업', 'A')[1]['연속'] == 9)
    i = add(ad, i, 1, '계절수업 안내', 'A', '들임')
    sort.run()
    c = cand('T', '계절수업', 'A')[1]
    q1 = qlines()
    ok('S5 10건 연속 → 통과 + 규칙 줄(쓰지는 않음) + 대기열 한 줄', c['상태'] == '통과' and c['규칙줄']['조건'] == {'칸': '제목', '포함': '계절수업'}
       and c['규칙줄']['만든이'].startswith('자동') and len(q1) == 1 and '그림자 통과' in q1[0], q1[0] if q1 else '')
    sort.run()
    ok('S5 새것 없이 다시 run — 대기열 그대로 한 줄', len(qlines()) == 1)
    ok('S5 그림자가 체계 파일을 안 바꿈(바이트 같음)', open(os.path.join(d, 'T.json'), 'rb').read() == sysfile)
    ok('S5 그림자가 판정을 안 바꿈(전부 규칙 n1 · 가짜 Claude 갈래 그대로)',
       all(v == (ad.rows[k]['_claude'], '규칙', 'n1') for k, v in verdicts('T').items()))
    i = add(ad, i, 1, '계절수업 변경', 'A', '뺌')
    sort.run()
    ok('S5 통과 뒤 어긋남 → 은퇴', cand('T', '계절수업', 'A')[1]['상태'] == '은퇴')
    j = add(ad, i, 3, '계절수업 B', 'B', '뺌')
    sort.run()
    kb, cb = cand('T', '계절수업', 'B')
    ok('S5 자리 따로 — B 후보(빼는 갈래 → 필요 20) · A 는 그대로 은퇴', cb is not None and cb['필요'] == 20 and cb['연속'] == 0
       and cand('T', '계절수업', 'A')[1]['상태'] == '은퇴', str(cb))
    j = add(ad, j, 1, '계절수업 B', 'B', '들임')
    sort.run()
    j = add(ad, j, 3, '계절수업 B', 'B', '뺌')
    sort.run()
    st = L.load(L.path('채택', 'T'), {})
    ok('S5 통과 전 어긋남 → 탈락 · 다시 안 올림', st['후보'][kb]['상태'] == '탈락'
       and sum(1 for c in st['후보'].values() if c['낱말'] == '계절수업' and c['자리'] == 'B') == 1)
    j = add(ad, j, 3, '장학금 C', 'C', '들임')
    sort.run()
    kc, cc = cand('T', '장학금', 'C')
    out = sort.revert(sid='T', rule=kc)
    j = add(ad, j, 2, '장학금 C', 'C', '들임')
    sort.run()
    cc = cand('T', '장학금', 'C')[1]
    ok('S5 revert(그림자 후보) → 거부 · 그 뒤 안 셈', out.get('거부') == kc and cc['상태'] == '거부' and cc['연속'] == 0, str(out))
    logs = [json.loads(x) for x in open(os.path.join(idx, '채택.jsonl'), encoding='utf-8')]
    ok('S5 장부 — 후보·맞음·통과·은퇴·탈락·거부 줄', {'후보', '맞음', '통과', '은퇴', '탈락', '거부'} <= {x['일'] for x in logs})
    shadow_v = verdicts('T')
    # 같은 자료를 끔으로 — 판정 같음 · 배우기 파일 없음
    setup('A0', system('T', adopt='끔'))
    sort.run()
    ok('S5 끔 — 채택 파일 없음 · LEARNED 없음 · 판정은 그림자 켬과 같음',
       not os.path.exists(L.path('채택', 'T')) and 'T' not in sort.LEARNED and verdicts('T') == shadow_v)
    s_bad = system('T', adopt='켬')
    ok('S5 check — 자동채택 «켬» 은 아직 오류(진짜 채택은 사용자 결정 뒤)', any('자동채택' in e for e in sort.check_one('T', s_bad, {'T': s_bad})[0]))

    # ════ D S7 흉내 ════
    ad.rows.clear()
    setup('D', system('S', stats='그림자'))
    for k in range(30):
        ad.rows[f'{k:04d}'] = {'제목': '장학 지원 안내 생활비' if k % 2 else '행사 참가 모집 공연', '자리': 'A', '_claude': '들임' if k % 2 else '뺌'}
    sort.run()
    s7 = L.load(L.path('통계', 'S'), {})
    ok('S7 문턱 잼(시간 순 누적 · 98%) · 보기 30', s7.get('n') == 30 and s7.get('문턱') is not None and s7.get('덮음', 0) > 0, f'{s7.get("문턱")} {s7.get("덮음")}/{s7.get("잰 수")}')
    ad.rows['0100'] = {'제목': '장학 지원 안내 생활비 새', '자리': 'A'}
    ad.rows['0101'] = {'제목': '행사 참가 모집 공연 새', '자리': 'A'}
    sort.run()
    s7 = L.load(L.path('통계', 'S'), {})
    ok('S7 그림자 — 대기 그대로(판정 안 함) · 예측 2건 적음', {'0100', '0101'} <= set(sort.state('S')['대기'])
       and set(s7['예측']) == {'0100', '0101'} and all(p['정함'] for p in s7['예측'].values()), str(s7['예측']))
    ad.rows['0100']['_claude'], ad.rows['0101']['_claude'] = '들임', '뺌'
    sort.run()
    s7 = L.load(L.path('통계', 'S'), {})
    ok('S7 그림자 대조 — Claude 판정이 오면 맞음 2', s7['대조']['맞음'] == 2 and not s7['예측'], str(s7['대조']))
    setup('D', system('S', stats=True))
    ad.rows['0102'] = {'제목': '장학 지원 안내 생활비 셋', '자리': 'A'}
    sort.run()
    rec = sort.state('S')['items'].get('0102') or {}
    ok('S7 켬 — ③ 이 정함(판정자 통계) · 안 배움(보기 32 그대로)', rec.get('판정자') == '통계' and rec.get('갈래') == '들임'
       and sort.LEARNED['S']['보기'] == 32, f'{rec.get("판정자")} {rec.get("갈래")} {rec.get("근거")}')

    # ════ E S7 다시 재기 ════
    setup('E', system('S', stats='그림자'))
    L.AGAIN_N = 20
    try:
        sort.run()
        sort.run()
    finally:
        L.AGAIN_N = 300
    q = qlines()
    ok('S7 다시 재기 — 보기 > 문턱 수면 대기열 한 줄(두 번 돌려도 한 줄)', len(q) == 1 and '다시 재기' in q[0], q[0] if q else '')

    # ════ G 15분 확인 길 — 배우기 틱 · sklearn 없는 파이썬 ════
    setup('G', system('S', adopt='그림자', stats='그림자'))
    ticks = [L.tick(inbox=False)['돎'] for _ in range(4)]
    ok('틱 — 판정 상태는 안 씀(dry) · 배우기 파일만 · 배우기 파일이 멎으면 건너뜀(첫 틱 돎 · 넷째 틱 건너뜀)',
       ticks[0] and not ticks[-1] and not os.path.exists(os.path.join(sort.INDEX, 'S.json'))
       and os.path.exists(L.path('채택', 'S')) and os.path.exists(L.path('통계', 'S')), str(ticks))
    setup('G2', system('S', stats='그림자'))
    real_have = L.have_sklearn
    L.have_sklearn = lambda: False
    try:
        sort.run()
    finally:
        L.have_sklearn = real_have
    ok('sklearn 없는 파이썬(15분 확인 py -3.11) — ③ 건너뜀 · 통계 파일 안 씀 · 판정은 그대로',
       str(sort.LEARNED['S'].get('통계', '')).startswith('건너뜀') and not os.path.exists(L.path('통계', 'S')) and sort.state('S')['items'], str(sort.LEARNED['S']))

    # ════ C S7 evalcls 재생 ════
    M = os.path.join(VAULT, '0_작업', '일', '외부뇌', '범용도구', '측정')
    if not os.path.exists(os.path.join(M, 'result.json')):     # 제작자 측정(evalcls) 파일 — 받은 볼트에는 없다
        print('건너뜀 S7 evalcls 재생 — 측정 파일 없음(%s)' % M)
    else:
        R = json.load(open(os.path.join(M, 'result.json'), encoding='utf-8'))
        N = [r for r in json.load(open(os.path.join(M, 'notice.json'), encoding='utf-8')) if r['verdict'] != '지남']
        ny = ['keep' if r['verdict'] in ('해당', '확인 필요', '관심') else 'drop' for r in N]
        nt = [(r['title'] or '') + '\n' + re.sub(r'\s+', ' ', r['body'])[:600] for r in N]
        t0 = time.time()
        n, tot, acc, thr = L.cover(L.prequential(nt, ny, start=10, step=1), ny)
        B = R['notice']['B']
        ok('S7 evalcls 재생 — 공지 B 덮음·판정 수·문턱 같음', (n, tot) == (B['cover_n'], B['total']) and abs(thr - B['thr']) < 1e-9,
           f'{n}/{tot} 문턱 {thr:.4f} (측정 {B["cover_n"]}/{B["total"]} {B["thr"]:.4f}) · {time.time() - t0:.1f}초')
        F = json.load(open(os.path.join(M, 'folder.json'), encoding='utf-8'))
        fy, ft = [r['course'] for r in F], [r['fn'] + '\n' + r['body'][:600] for r in F]
        t0 = time.time()
        n, tot, acc, thr = L.cover(L.prequential(ft, fy, start=10, step=6), fy)
        B = R['folder']['B']
        ok('S7 evalcls 재생 — 폴더 B(6건마다 다시 배움) 덮음·판정 수·문턱·정확 같음',
           (n, tot) == (B['cover_n'], B['total']) and abs(thr - B['thr']) < 1e-9 and abs(acc - B['acc_at_thr']) < 1e-9,
           f'{n}/{tot} 정확 {acc:.3f} 문턱 {thr:.4f} (측정 {B["cover_n"]}/{B["total"]} {B["acc_at_thr"]:.3f}) · {time.time() - t0:.1f}초')
        n2, tot2, _, _ = L.cover(L.prequential(ft, fy, start=10), fy)
        print(f'   (참고) 폴더 B 엔진 기본(다시 배우기 ≤ {L.MAX_FITS}번): {n2}/{tot2}')

    # ════ F S6 흉내 ════
    FD = os.path.join(T, 'F')
    inbox = os.path.join(FD, 'inbox')
    os.makedirs(inbox)
    open(os.path.join(inbox, '열역학 과제77.pdf'), 'w').close()
    led = os.path.join(FD, 'ops.jsonl')
    base = '1_수집/받은함'
    dests = {'열역학 과제': '1_수집/배움/열역학/과제', '실험 보고서': '1_수집/배움/실험/제출'}
    rows, sec = [], [0]

    def ts():
        sec[0] += 1
        return '2026-11-01T%02d:%02d:%02d+09:00' % (sec[0] // 3600, sec[0] // 60 % 60, sec[0] % 60)

    def move(name, by, dst_dir):
        rows.append({'id': f'cp{len(rows)}', 'ts': ts(), 'op': 'cp', 'by': 'phone', 'src': f'phone:{name}', 'dst': f'{base}/{name}'})
        rows.append({'id': f'mv{len(rows)}', 'ts': ts(), 'op': 'mv', 'by': by, 'src': f'{base}/{name}', 'dst': f'{dst_dir}/{name}'})

    for k in range(16):
        w = '열역학 과제' if k % 2 else '실험 보고서'
        move(f'{w}{k}.pdf', 'claude', dests[w])
    start = rows[-1]['ts'][:19]
    for k in range(16, 28):
        w = '열역학 과제' if k % 2 else '실험 보고서'
        move(f'{w}{k}.pdf', 'obsidian', dests[w])

    def write_led():
        with open(led, 'w', encoding='utf-8', newline='\n') as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)
    write_led()
    before = open(led, 'rb').read()
    L.QUEUE = os.path.join(FD, 'queue.md')
    res = SI.shadow(ledger=led, base=base, inbox_dir=inbox, index=os.path.join(FD, 'idx'), now=start)
    ok('S6 사람 이동 12 → 연속 ≥ 10 · 통과 + 대기열 한 줄', res['연속'] >= 10 and res['통과'] and len(qlines()) == 1,
       f'맞음 {res["맞음"]} 틀림 {res["틀림"]} 모름 {res["모름"]} 연속 {res["연속"]}')
    ok('S6 Claude 이동은 배움에만(대조 = 사람 12)', res['사람 대조'] == 12 and res['배움 줄'] == 28)
    ok('S6 지금 받은함 예측(보기만)', res['지금 받은함'] and res['지금 받은함'][0]['예측'] == dests['열역학 과제'], str(res['지금 받은함']))
    res = SI.shadow(ledger=led, base=base, inbox_dir=inbox, index=os.path.join(FD, 'idx'), now=start)
    ok('S6 다시 불러도 새로 잰 것 0 · 대기열 한 줄', res['새로 잰 것'] == 0 and len(qlines()) == 1)
    move('열역학 과제99.pdf', 'obsidian', dests['실험 보고서'])
    write_led()
    before = open(led, 'rb').read()
    res = SI.shadow(ledger=led, base=base, inbox_dir=inbox, index=os.path.join(FD, 'idx'), now=start)
    ok('S6 사람이 다른 자리로 → 틀림 · 연속 0 · 최고 그대로', res['연속'] == 0 and res['최고'] >= 10 and res['틀림'] == 1)
    ok('S6 장부·받은함 안 바뀜(옮기는 코드 없음)', open(led, 'rb').read() == before and os.listdir(inbox) == ['열역학 과제77.pdf'])
    # 진짜 장부 재생(읽기만)
    real_led = SI.LEDGER
    m0 = (os.path.getsize(real_led), os.path.getmtime(real_led)) if os.path.exists(real_led) else None   # 새 볼트 = 장부 아직 없음
    t0 = time.time()
    rr = SI.shadow(replay=True, index=os.path.join(FD, 'never'))
    ok('S6 진짜 장부 재생 — 읽기만(장부 크기·시각 그대로 · 상태 안 씀)', ((os.path.getsize(real_led), os.path.getmtime(real_led)) if os.path.exists(real_led) else None) == m0
       and not os.path.exists(os.path.join(FD, 'never')),
       f'배움 {rr["배움 줄"]} · 사람 대조 {rr["사람 대조"]} · 맞음 {rr["맞음"]} 틀림 {rr["틀림"]} 모름 {rr["모름"]} · {time.time() - t0:.1f}초')

    # ════ B S5 76건 재생(진짜 · 읽기만) ════
    if not os.path.exists(os.path.join(REAL_SYSTEMS, '공지-들이기.json')):     # 제작자 볼트의 분류 체계·장부를 되풀이 — 받은 볼트에는 없다
        print('건너뜀 B S5 76건 재생 — 체계 «공지-들이기» 없음')
    else:
        sort.SYSTEMS, sort.INDEX = REAL_SYSTEMS, REAL_INDEX
        L.QUEUE = None
        sort.reset()
        snap = {f: (os.path.getsize(os.path.join(REAL_INDEX, f)), os.path.getmtime(os.path.join(REAL_INDEX, f))) for f in (os.listdir(REAL_INDEX) if os.path.isdir(REAL_INDEX) else [])}   # 새 볼트 = 분류 색인 아직 없음
        t0 = time.time()
        rp = L.replay('공지-들이기')
        ok('S5 76건 재생 — 보기 76 · 통과 0(그림자 10건을 못 채움)', rp['보기'] == 76 and not rp['통과'],
           f'후보 {rp["일"].get("후보", 0)} · 맞음 {rp["일"].get("맞음", 0)} · 탈락 {rp["일"].get("탈락", 0)} · 최고 연속 {rp["최고 연속"]} · '
           f'③ {rp.get("③")} · {time.time() - t0:.1f}초')
        print('   자리 없이 후보(포함 꼴):', rp['자리 없이 후보'])
        ok('엔진 기본 끔 — «자동채택»·«사다리.통계» 칸이 없는 체계는 배우기 0', not sort.learn_on({'사다리': {}}) and L.modes({}) == (False, None))
        snap2 = {f: (os.path.getsize(os.path.join(REAL_INDEX, f)), os.path.getmtime(os.path.join(REAL_INDEX, f))) for f in (os.listdir(REAL_INDEX) if os.path.isdir(REAL_INDEX) else [])}   # 새 볼트 = 분류 색인 아직 없음
        ok('S5 재생은 진짜 장부·상태를 안 씀', snap == snap2, str(set(snap2) ^ set(snap)))
        # 낱말 꼴 대조 — 설계 §6 측정(«낱말 w 가 있으면» = 낱말 단위)과 같은 셈이면 «겨울계절수업»·«전형»
        s0 = sort.systems()['공지-들이기']
        exs = L.examples('공지-들이기', s0, sort.adapter('수집글'), sort.DECIDED['공지-들이기'])
        words = {}
        for e in exs:
            for w in set(L.tok(e['칸']['제목'])):
                words.setdefault(w, []).append(e['갈래'])
        tokw = sorted((w, g[0]) for w, g in words.items() if len(g) >= 3 and len(set(g)) == 1)
        ok('S5 낱말 단위로 세면 설계 §6 측정의 두 낱말(겨울계절수업·전형 → 확인 필요)이 나옴',
           {('겨울계절수업', '확인 필요'), ('전형', '확인 필요')} <= set(tokw), f'지금 판정으로 {tokw}')
finally:
    sort.SYSTEMS, sort.INDEX = REAL_SYSTEMS, REAL_INDEX
    sort.reset()
    shutil.rmtree(T, ignore_errors=True)

print('\n' + ('전부 통과' if not fails else f'실패 {len(fails)}: {fails}'))
sys.exit(1 if fails else 0)
