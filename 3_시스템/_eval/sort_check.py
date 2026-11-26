"""sort.py 단위 시험(S1 · 2026-11-18) — 격리(임시 폴더의 장부·체계 · 볼트 파일을 안 건드림 · Claude 0).
잰다: 조건 낱말·묶음·모름 전파 · 참조(@값 기간 · @카드 + 카드기본 · 체계.) · 근거 틀 · 표 규칙(설계 §8.4 예 SS·S·A·버림·성수기) ·
     사다리(② 규칙 → ① 기억 · 사실이 바뀌면 다시 · 함수 None/모름 · ④ 대기 vs 모르면) · 앞 체계 의존 · 장부(바뀐 것만) ·
     동작 넘김(태그 붙임·뗌) · 판정 대기 자리 단위(한 대상 한 줄) · check(예시 통과 · 망가진 체계의 오류·고리)."""
import json
import os
import shutil
import sys
import tempfile

SYS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, SYS)
sys.dont_write_bytecode = True
import sort  # noqa: E402

T = tempfile.mkdtemp(prefix='sort-check-')
fails = []


def ok(name, cond):
    print(('통과 ' if cond else '실패 ') + name)
    if not cond:
        fails.append(name)


def env(facts, vals=None, card=None, deps=None):
    return {'사실': facts, '값': vals or {}, '카드': card or {}, '체계': deps or {}}


class Mem:
    """시험 어댑터 — 사실 dict 목록."""
    def __init__(self, rows):
        self.rows = rows

    def items(self):
        return [{'id': k, 'facts': v, '글자': 100, 'raw': {}} for k, v in self.rows.items()]

    def match(self, it, spec):
        return True

    def place(self, it):
        return it['facts'].get('자리')


def put(d, name, s):
    os.makedirs(d, exist_ok=True)
    json.dump(s, open(os.path.join(d, name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)


def lines(p):
    return open(p, encoding='utf-8').read().splitlines() if os.path.exists(p) else []


try:
    # ── 조건 낱말 ──
    f = {'a': 3, 's': '장학 공지', 'l': ['보고서', '행사', '보고서'], 'n': None, '지급': {'형태': '현금'}}
    cases = [({'칸': 'a', '같음': 3}, True), ({'칸': 'a', '아님': 3}, False), ({'칸': 'a', '안에': [1, 3]}, True),
             ({'칸': 'l', '겹침': ['활동', '보고서']}, True), ({'칸': 's', '포함': '장학'}, True), ({'칸': 's', '맞음': '^장학'}, True),
             ({'칸': 'a', '초과': 3}, False), ({'칸': 'a', '이상': 3}, True), ({'칸': 'a', '미만': 4}, True), ({'칸': 'a', '이하': 2}, False),
             ({'칸': 'a', '사이': [1, 3]}, True), ({'칸': 'n', '있음': True}, False), ({'칸': 'x', '모름': True}, True),
             ({'칸': 'x', '같음': 1}, None), ({'칸': 'n', '안에': [1]}, False), ({'칸': 's', '초과': 1}, None),
             ({'칸': '지급.형태', '같음': '현금'}, True)]
    ok('조건 낱말 13 + 빈 칸·꼴 다름 = 모름', all(sort.cond(c, env(f)) is r for c, r in cases))
    ok('묶음 — 모두(거짓 > 모름) · 하나라도(참 > 모름) · 아님(모름 그대로)',
       sort.cond({'모두': [{'칸': 'x', '같음': 1}, {'칸': 'a', '같음': 0}]}, env(f)) is False
       and sort.cond({'모두': [{'칸': 'x', '같음': 1}, {'칸': 'a', '같음': 3}]}, env(f)) is None
       and sort.cond({'하나라도': [{'칸': 'x', '같음': 1}, {'칸': 'a', '같음': 3}]}, env(f)) is True
       and sort.cond({'아님': {'칸': 'x', '같음': 1}}, env(f)) is None and sort.cond({'아님': {'칸': 'a', '같음': 1}}, env(f)) is True)
    rv = {'박범위': [3, 6], '하한': 3, '상한': 4}
    ok('사이 오른쪽 참조 — "@값"([작은, 큰]) · ["@값", "@값"] · 없는 값은 모름 · check 가 허용(11-18 S2)',
       sort.cond({'칸': 'a', '사이': '@박범위'}, env(f, rv)) is True and sort.cond({'칸': 'a', '사이': ['@하한', '@상한']}, env(f, rv)) is True
       and sort.cond({'칸': 'a', '사이': ['@하한', 2]}, env(f, rv)) is False and sort.cond({'칸': 'a', '사이': ['@없음', 9]}, env(f, rv)) is None
       and not sort.bad_cond({'칸': 'a', '사이': '@박범위'}, {'값': rv}, {}, 'w') and not sort.bad_cond({'칸': 'a', '사이': ['@하한', '@상한']}, {'값': rv}, {}, 'w')
       and sort.bad_cond({'칸': 'a', '사이': ['@없음', 1]}, {'값': rv}, {}, 'w') and sort.bad_cond({'칸': 'a', '사이': 3}, {'값': rv}, {}, 'w'))
    b = {}
    sort.cond({'칸': 'l', '겹침': ['행사', '보고서']}, env(f), b)
    ok('겹침 = 사실 차례 · 겹친 것 한 번씩', b['겹침'] == ['보고서', '행사'])
    e = env({'지급': {'형태': None, '근거': '생활비 지급 대상자에게 학기마다 지급한다는 긴 문장입니다'}}, deps={'공지': '해당'})
    ok('근거 틀 {칸|기본} {칸:N} {겹침}', sort.fill('지급 {지급.형태|모름} «{지급.근거:6}» {겹침}', e, {'겹침': ['a', 'b']}) == '지급 모름 «생활비 지급» a·b')
    # ── 참조 ──
    vals = {'가격선': {'기본': 700000, '기간': [{'걸침': ['2027-02-01', '2027-02-13'], '값': 900000}], '걸침칸': ['가는편.날짜', '오는편.날짜']}}
    trip = lambda a, b: {'가는편': {'날짜': a}, '오는편': {'날짜': b}}  # noqa: E731
    ok('@값 기간 — 걸치면 기간 값 · 아니면 기본 · 날짜 없으면 모름',
       sort.resolve('@가격선', env(trip('2027-02-10', '2027-02-15'), vals)) == 900000
       and sort.resolve('@가격선', env(trip('2027-01-20', '2027-01-25'), vals)) == 700000
       and sort.resolve('@가격선', env({}, vals)) is sort.MISSING)
    sort.set_card({'황금': {'지급': ['현금']}})
    cv = sort.card_view({'카드기본': {'황금': {'지급': ['현금', '혼합'], '소득심사 막음': True}}})
    ok('@카드 + 카드기본 — 카드가 이기고 빈 열쇠만 채움', cv['황금'] == {'지급': ['현금'], '소득심사 막음': True})
    ok('체계.<id> · 빼기', sort.resolve('체계.공지', e) == '해당' and sort.resolve({'빼기': ['@가격선', 'p']}, env({'p': 1, **trip('2027-01-01', '2027-01-05')}, vals)) == 699999)
    # ── 표 규칙(예시 체계 · 설계 §8.4 예) ──
    ex = json.load(open(os.path.join(sort.EXAMPLES, '항공권-티어.json'), encoding='utf-8'))
    ex['id'] = 'tier'

    def tier(price, go, back, bag, dates=('2027-01-20', '2027-01-25')):
        fc = {'2인가': price, '가는편': {'날짜': dates[0], '출발시각대': go}, '오는편': {'날짜': dates[1], '출발시각대': back}, '위탁': bag}
        return sort.rules_eval(ex, env(fc, ex['값']), {'facts': fc}).get('갈래')
    ok('표 — 40만·오전·오후·위탁 포함 SS · 위탁 별도 S · 오는 편 새벽 A',
       tier(400000, '오전', '오후', '포함') == 'SS' and tier(400000, '오전', '오후', '별도') == 'S' and tier(400000, '오전', '새벽', '포함') == 'A')
    ok('표 — 가격선 넘으면 버림 · 27만 SSS(가둠 6) · 성수기 75만 = 가격선 90만 → B',
       tier(710000, '오전', '오후', '포함') == '버림' and tier(270000, '오전', '오후', '포함') == 'SSS'
       and tier(750000, '오전', '오후', '별도', ('2027-02-10', '2027-02-14')) == 'B')
    ok('표 — 시간대 칸이 없으면 모름', '모름' in sort.rules_eval(ex, env({'2인가': 400000, **trip('2027-01-20', '2027-01-25')}, ex['값']), {'facts': {}}))

    # ── 사다리 · 장부 · 넘김 · 대기 ──
    D, I = os.path.join(T, 'sys'), os.path.join(T, 'idx')
    sort.SYSTEMS, sort.INDEX = D, I
    sort.reset()
    rows = {'a': {'점수': 5, '자리': 'src1'}, 'b': {'점수': 1, '자리': 'src1'}, 'c': {'자리': 'src2'}}
    sort.register_adapter('시험', Mem(rows))
    calls = []

    def fn(it, ev):
        calls.append(it['id'])
        return None if it['facts'].get('점수', 0) < 3 else {'갈래': '큼', '근거': '함수'}
    sys.modules['sort_test_fn'] = type(sys)('sort_test_fn')
    sys.modules['sort_test_fn'].fn = fn
    sys.modules['sort_test_fn'].unk = lambda it, ev: {'모름': '특징 없음'} if '점수' not in it['facts'] else None
    put(D, '크기', {'id': '크기', '판': 1, '대상': {'종류': '시험'}, '특징': {'claude': 't.크기'},
                  '규칙': [{'id': 'u', '말': '점수 없으면 모름', '함수': 'sort_test_fn.unk'},
                         {'id': 'f', '말': '함수가 크면 큼', '함수': 'sort_test_fn.fn'},
                         {'id': 'r', '말': '점수 2 미만은 작음', '조건': {'칸': '점수', '미만': 2}, '갈래': '작음', '근거': '점수 {점수}'}],
                  '갈래': {'큼': {'동작': [{'태그': '큼'}, {'알림': {'때': '바로', '급함': True}}]}, '작음': {'동작': []}}, '모르면': '작음'})
    put(D, '뒤', {'id': '뒤', '판': 1, '대상': {'종류': '시험', '체계': {'크기': ['큼']}},
                 '규칙': [{'id': 'z', '말': '늘 예', '조건': {'늘': True}, '갈래': '예'}], '갈래': {'예': {'동작': []}}, '모르면': '예',
                 '사다리': {'claude': '끔'}})
    s1 = sort.run(now='T1')
    L1 = lines(os.path.join(I, '판정.jsonl'))
    ok('② 함수·조건 · 함수 None = 다음 규칙 · 함수 모름 = ④ 대기(c)',
       s1['크기'] == {'규칙': 2, '바뀜': 2, '대기': 1} and sort.state_item('크기', 'a')['갈래'] == '큼'
       and sort.state_item('크기', 'b')['근거'] == '점수 1' and 'c' in sort.state('크기')['대기'])
    ok('앞 체계 의존 — 큼만 대상 · 대기는 기다림', s1['뒤'] == {'규칙': 1, '바뀜': 1, '대상 밖': 1, '앞 체계 대기': 1})
    ok('급함 = 알림 칸 · 장부 3줄(바뀐 것만)', sort.state_item('크기', 'a')['급함'] is True and len(L1) == 3)
    out1 = [json.loads(x) for x in lines(os.path.join(I, '넘김.jsonl'))]
    ok('넘김 — a 태그 붙임 + 알림', [x['동작'] for x in out1] == [{'태그': '큼'}, {'알림': {'때': '바로', '급함': True}}])
    calls.clear()
    sort.reset()
    sort.register_adapter('시험', Mem(rows))
    s2 = sort.run(now='T2')
    ok('① 기억 — 다시 돌리면 함수를 안 부르고 장부·넘김이 안 늘어남',
       s2['크기'].get('기억') == 2 and not calls and len(lines(os.path.join(I, '판정.jsonl'))) == 3 and len(lines(os.path.join(I, '넘김.jsonl'))) == 2)
    rows['a']['점수'] = 1
    sort.reset()
    sort.register_adapter('시험', Mem(rows))
    s3 = sort.run(now='T3')
    out3 = [json.loads(x)['동작'] for x in lines(os.path.join(I, '넘김.jsonl'))[2:]]
    ok('사실이 바뀌면 다시 판정 · 태그 뗌 · 뒤 체계에서 빠짐', sort.state_item('크기', 'a')['갈래'] == '작음' and {'떼기': '큼'} in out3
       and s3['뒤'].get('빠짐') == 1 and sort.state_item('뒤', 'a') is None)
    ok('자리 단위 대기 — src2 에 1건 · src1 0건', sort.places() == {'src2': 1} and not sort.pending('src1'))
    est = sort.estimate(sort.pending('src2'))
    ok('예상 = 고정분 + 글자 × 0.324(설계 §5)', est['건수'] == 1 and est['입력'] == round(sort.FIXED_IN + 0.324 * 100))
    sys_k = json.load(open(os.path.join(D, '크기.json'), encoding='utf-8'))
    sys_k['사다리'] = {'claude': '끔'}
    put(D, '크기', sys_k)
    sort.reset()
    sort.register_adapter('시험', Mem(rows))
    sort.run(now='T4')
    ok('④ 끔이면 모르면 갈래(판정자 모르면)', sort.state_item('크기', 'c')['판정자'] == '모르면' and not sort.state('크기')['대기'])

    # ── S4: 자리 요약 · 묶어 부르기 예상 · 사건(알림 줄)·되돌리기 ──
    P = json.load(open(os.path.join(I, sort.PLACES), encoding='utf-8'))
    pk = P['체계']['크기']
    ok('자리 요약 — 자리별 판정·맞은 규칙·갈래 · 대기 0 이면 판정 칸 빔',
       pk['src1'] == {'대기': 0, '판정': 2, '맞은': {'r': 2}, '갈래': {'r': {'작음': 2}}} and pk['src2']['맞은'] == {'모르면': 1} and P['판정'] == {})
    fake = {f'x{i}': {'자리': 'p', '체계': ['크기'], '특징': [], '글자': 100, '종류': '시험', '모델': 'sonnet'} for i in range(8)}
    e1 = sort.estimate(fake)
    sys_k['묶음'] = 6
    put(D, '크기', sys_k)
    sort.reset()
    e6 = sort.estimate(fake)
    big = {**fake, 'y': {**fake['x0'], '글자': 30000}}
    e6b = sort.estimate(big)
    ok('묶어 부르기 예상 — 끔 8호출 · 묶음 6 = 2호출(고정분 2번) · 큰 글은 따로',
       e1['호출'] == 8 and e6['호출'] == 2 and e6['입력'] == round(2 * sort.FIXED_IN + 8 * 0.324 * 100) and e6['$'] < e1['$'] and e6b['호출'] == 3)
    sys_k['묶음'] = 7
    put(D, '크기', sys_k)
    sort.reset()
    ok('check — 묶음 1~6 밖은 오류', any('묶음' in x for x in sort.check(D)['크기'][0]))
    sys_k.pop('묶음')
    sys_k['규칙'].insert(0, {'id': 'a1', '말': '제목에 «전형»', '만든이': '자동 11-18 · 지지 3 · 그림자 10/10', '조건': {'칸': '점수', '같음': 9}, '갈래': '큼'})
    sys_k['값'] = {'가격선': 640000}
    put(D, '크기', sys_k)
    sort.reset()
    ea = sort.event_add('크기', '채택', '제목에 «전형» → 큼', {'규칙': 'a1'}, now='T5')
    ep = sort.event_add('크기', '가격선', '가격선 70만 → 64만', {'값': '가격선', '전': 700000, '후': 640000}, now='T5')
    ev = sort.event_add('크기', '가격선', '가격선 64만 → 60만', {'값': '가격선', '전': 640000, '후': 600000}, now='T5')
    ok('사건 — 셋 다 열림', {e['id'] for e in sort.events()} == {ea, ep, ev})
    sort.register_adapter('시험', Mem(rows))
    sort.revert(ea, now='T6')
    r_a1 = next(r for r in sort.systems()['크기']['규칙'] if r['id'] == 'a1')
    ok('되돌리기(채택) — 규칙 끔 + 거부 · 사건 닫힘 · 체계 파일 검사 통과',
       r_a1['켬'] is False and r_a1['거부'] is True and ea not in {e['id'] for e in sort.events()} and not sort.check(D)['크기'][0])
    sort.revert(ep, now='T6')
    ok('되돌리기(가격선) — 값이 «전»으로', sort.systems()['크기']['값']['가격선'] == 700000)
    try:
        sort.revert(ev, now='T6')
        stale = False
    except ValueError:
        stale = True
    try:
        sort.revert(sid='크기', rule='r', now='T6')
        human = False
    except ValueError:
        human = True
    sort.ack(ev, now='T7')
    shut = {e['id']: e.get('닫힘') for e in sort.events(False)}
    ok('되돌리기 막음 — 값이 그 뒤 바뀜 · 사람 규칙 · 확인 = 닫힘(되돌림 2 · 확인 1)',
       stale and human and shut == {ea: '되돌림', ep: '되돌림', ev: '확인'} and not sort.events())
    import sort_collect as sc
    sc._pm[:] = [{}]
    cmd1 = sc.judge_cmds('src9', {'collect:src9:1': {'특징': ['notice.gold']}})
    cmd6 = sc.judge_cmds('src9', {'collect:src9:1': {'특징': ['notice.gold']}}, batch=6)
    ok('수집글 ④ — 묶음 1 은 옛 꼴 그대로 · 묶음 6 = --batch 6', '--batch' not in cmd1[0] and cmd6[0][-2:] == ['--batch', '6'] and '--again' in cmd1[0])

    # ── 묶어 부르기(notice-filter extract_many) — 가짜 claude 로 꼴만(사용량 0) ──
    import importlib.util
    import types
    spec = importlib.util.spec_from_file_location('nf_t', os.path.join(SYS, 'notice-filter.py'))
    nft = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nft)
    got_calls = []

    def fake_run(content, system=''):
        got_calls.append((system.endswith(nft.BATCH), content[0]['text'].count('=== 공지 ')))
        if nft.BATCH in system:          # 묶음 — 2번 글을 빠뜨림
            return '[{"번호":1,"조건":[],"마감":null},{"번호":3,"조건":[],"마감":"2026-12-01"}]', {'in': 3000, 'out': 600, 'cost': 0.012}, ''
        return '{"조건":[],"마감":null,"요약":"한 건"}', {'in': 2900, 'out': 300, 'cost': 0.009}, ''
    sys.modules['ingest_vision'] = types.SimpleNamespace(_run=fake_run, MODEL='sonnet')
    ns = [{'rc': {'filter': {'gold': True}}, 'title': f't{i}', 'date': '2026-11-01', 'text': '본문' * 50, 'att': []} for i in range(3)]
    res = nft.extract_many(ns)
    ok('extract_many — 한 호출 3건 · 빠진 2번만 한 건씩 다시 · 사용량 3등분 · 묶음 칸',
       got_calls == [(True, 3), (True, 3), (False, 0)] and res[0][0]['_tokens']['묶음'] == 3 and res[2][0]['마감'] == '2026-12-01'
       and res[1][0]['요약'] == '한 건' and res[0][1]['in'] == 2000)
    ns2 = ns + [{'rc': {'filter': {}}, 'title': 'x', 'date': '', 'text': '짧음', 'att': []}]
    bs = nft.batches(ns2, 6)
    ok('batches — 지시문(황금 칸)이 다르면 다른 묶음 · 1 = 한 건씩', [len(b) for b in bs] == [3, 1] and len(nft.batches(ns2, 1)) == 4)
    del sys.modules['ingest_vision']

    # ── check ──
    res = sort.check(sort.EXAMPLES)
    ok('check — 예시 체계 오류 0', all(not E for E, W in res.values()) and res)
    B = os.path.join(T, 'bad')
    put(B, 'x', {'id': 'x', '판': 1, '대상': {'종류': '시험', '체계': {'y': ['예']}}, '규칙': [
        {'id': 'r1', '말': '', '조건': {'칸': 'a', '비슷': 1}, '갈래': '없는갈래'},
        {'id': 'r2', '말': '참조', '조건': {'칸': '@없는값', '같음': 1}, '갈래': '예'},
        {'id': 'r3', '말': '표', '표': {'점수': [{'칸': 'a', '단계': [[5, 1], [1, 2]]}], '갈래': {'1': '없음'}}}],
        '갈래': {'예': {'동작': [{'알림': {'때': '언젠가'}}]}}, '모르면': '아니오'})
    put(B, 'y', {'id': 'y', '판': 1, '대상': {'종류': '시험', '체계': {'x': ['예']}}, '규칙': [{'id': 'k', '말': '늘', '조건': {'늘': True}, '갈래': '예'}],
                 '갈래': {'예': {'동작': []}}, '모르면': '예'})
    E = ' | '.join(sort.check(B)['x'][0])
    want = ['«말»', '«비슷»', '없는갈래', '@없는값', '오름차순', '«없음»', '알림.때', '모르면', '고리']
    ok('check — 망가진 체계 오류 9가지(말·낱말·갈래·참조·단계·표 갈래·알림·모르면·고리)', all(w in E for w in want))
    if not all(w in E for w in want):
        print('   ', E)
finally:
    shutil.rmtree(T, ignore_errors=True)

print(f'\n{"전부 통과" if not fails else f"실패 {len(fails)}"}')
sys.exit(1 if fails else 0)
