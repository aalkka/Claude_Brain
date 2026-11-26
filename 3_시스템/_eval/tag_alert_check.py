"""태그 도구(tag.py · S8) + 알림 도구(alert.py · S9) 시험 — 격리(임시 체계·장부·노트·알림 저장소 · 볼트 파일을 안 건드림 · 망 0 · Claude 0 · 폰에 안 보냄).

태그: 사전·가족·문제 · has() = 옛 sort.tag_of · sort.preview(규칙 바꿈 재생 대조 · 안 씀) ·
      노트 쓰기(흐름·블록 목록 · CRLF 그대로 · 사람이 단 태그는 안 적고 안 뗌 · 프론트매터 없음 ·
      1_수집·노트 아닌 대상 = 겹쳐 보이기만 · 노트 쓰기 끈 체계 = 파일 0) · 멱등(다시 sync · --all) · 뗄 때 원래 바이트로 ·
      tag.apply(판정자 사람 · ① 기억이 지킴 · --off) · 오류(없는 태그 · 대상 밖 · 잠금).
알림: 때(급함 = 지금 · 잘 시간 → 아침 · 아침 · 묶음 HH:MM · 묶음이 잘 시간이면 아침) · 한 돌림 여럿 = 1초씩 순위 차례 «k / n» ·
      중복(같은 갈래 한 번 · 내림 안 울림 · 오름 다시 · 순위 없는 체계는 처음 갈래만) · 사라지면 잊음 · 지난 판정 · 꺼진 체계 ·
      mobility 꺼짐 = 수집 창만 · 서버 사본(alarms.build)에 ev-sort 사건이 실림 · inbox_put 꼴 검사·만료·같은 id ·
      alert.now(급함·아침·dry) · 수집 창 «일어난 일» 줄 · 항공권(가격 조회 사본 켬 + 녹화 가격줄 → 티어 태그 · 알림 글 · SSS 만 급함 · 차례).

  py -3 3_시스템/_eval/tag_alert_check.py
"""
import copy
import datetime as dt
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request

SYS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT = os.path.dirname(SYS)
sys.path.insert(0, SYS)
sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding='utf-8')
import sort  # noqa: E402
import tag  # noqa: E402
_ALERT = os.path.join(VAULT, '.claude', 'skills', 'mobility', 'scripts', 'alert.py')   # 알림 도구 = mobility 몫(11-18) · 없으면 알림 쪽은 건너뜀
alert = None
if os.path.exists(_ALERT):
    _spec = importlib.util.spec_from_file_location('alert', _ALERT)
    alert = importlib.util.module_from_spec(_spec)
    sys.modules['alert'] = alert
    _spec.loader.exec_module(alert)
G = sort.gold_tag()                                        # 황금 태그 이름(개인화 파트 · 없으면 «황금»)

KST = dt.timezone(dt.timedelta(hours=9))
T = tempfile.mkdtemp(prefix='tag-alert-')
fails = []


def ok(name, cond):
    print(('통과 ' if cond else '실패 ') + name)
    if not cond:
        fails.append(name)


def no_net(*a, **k):
    raise AssertionError('시험 중 진짜 망 요청')


urllib.request.urlopen = no_net


class Mem:
    """시험 어댑터 — {id: 사실}."""
    def __init__(self, rows):
        self.rows = rows

    def items(self):
        return [{'id': k, 'facts': v, '글자': 10, 'raw': {}} for k, v in self.rows.items()]

    def match(self, it, spec):
        return True

    def place(self, it):
        return it['facts'].get('자리')


def put(d, name, s):
    os.makedirs(d, exist_ok=True)
    json.dump(s, open(os.path.join(d, name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)


def lines(p):
    return open(p, encoding='utf-8').read().splitlines() if os.path.exists(p) else []


def rb(p):
    return open(p, 'rb').read()


def fresh(name):
    D, I = os.path.join(T, name, 'sys'), os.path.join(T, name, 'idx')
    sort.SYSTEMS, sort.INDEX = D, I
    sort.reset()
    sort.set_card({})
    return D, I


try:
    # ════════ 태그 ════════
    D, I = fresh('tag')
    V = os.path.join(T, 'vault')
    tag.VAULT = V
    N = os.path.join(V, '2_지식', '시험')
    os.makedirs(N)
    os.makedirs(os.path.join(V, '1_수집'))
    notes = {
        'a.md': '---\r\ntitle: a\r\ntags: [외부뇌, 시험]\r\n---\r\n본문 a\r\n'.encode('utf-8'),
        'b.md': '---\ntitle: b\ntags:\n  - 시험태그\n---\n본문 b\n'.encode('utf-8'),
        'c.md': '---\ntitle: c\ntags:\n  - x\nstatus: active\n---\n본문 c\n'.encode('utf-8'),
        'd.md': '본문만 d\n'.encode('utf-8'),
        'e.md': '---\ntitle: e\n---\n본문 e\n'.encode('utf-8'),
    }
    for k, v in notes.items():
        open(os.path.join(N, k), 'wb').write(v)
    open(os.path.join(V, '1_수집', 'x.md'), 'wb').write('---\ntitle: x\n---\n원본\n'.encode('utf-8'))
    put(os.path.join(D, '태그'), '사전', {'태그': {'시험태그': {'뜻': '시험 태그', '순서': 1}, '등급': {'뜻': '시험 등급', '가족': ['SSS', 'SS', 'S'], '순서': 2}}})
    rows = {f'note:2_지식/시험/{k}': {'점수': 5} for k in ('a.md', 'b.md', 'c.md', 'd.md')}
    rows.update({'note:2_지식/시험/e.md': {'점수': 1}, 'note:1_수집/x.md': {'점수': 5}, 'collect:x:1': {'점수': 5}})
    rows2 = {'collect:y:1': {'점수': 5}, 'collect:y:2': {'점수': 1}}
    sort.register_adapter('시험', Mem(rows))
    sort.register_adapter('시험2', Mem(rows2))
    put(D, '표시', {'id': '표시', '판': 1, '대상': {'종류': '시험'}, '노트에 쓰기': True,
                  '규칙': [{'id': 'k', '말': '점수 3 이상이면 예', '조건': {'칸': '점수', '이상': 3}, '갈래': '예', '근거': '점수 {점수}'},
                         {'id': 'z', '말': '그 밖은 아니', '조건': {'늘': True}, '갈래': '아니'}],
                  '갈래': {'예': {'동작': [{'태그': '시험태그'}]}, '아니': {'동작': []}}, '모르면': '아니', '사다리': {'claude': '끔'}})
    put(D, '겹침', {'id': '겹침', '판': 1, '대상': {'종류': '시험2'},
                  '규칙': [{'id': 'k', '말': '점수 3 이상', '조건': {'칸': '점수', '이상': 3}, '갈래': '예'}, {'id': 'z', '말': '그 밖', '조건': {'늘': True}, '갈래': '아니'}],
                  '갈래': {'예': {'동작': [{'태그': '겹침태그'}]}, '아니': {'동작': []}}, '모르면': '아니', '사다리': {'claude': '끔'}})
    put(D, '뒤', {'id': '뒤', '판': 1, '대상': {'종류': '시험', '체계': {'표시': ['예']}},
                 '규칙': [{'id': 'z', '말': '늘 보통', '조건': {'늘': True}, '갈래': '보통'}],
                 '갈래': {'보통': {'동작': []}, '뒤태그': {'동작': [{'태그': '뒤태그'}, {'태그': '등급/A'}]}}, '모르면': '보통', '사다리': {'claude': '끔'}})
    chk = sort.check(D)
    ok('sort check — «노트에 쓰기» 칸 아는 칸 · 오류 0', all(not e and not any('노트에 쓰기' in w for w in ws) for e, ws in chk.values()))
    bad = copy.deepcopy(json.load(open(os.path.join(D, '표시.json'), encoding='utf-8')))
    bad['노트에 쓰기'] = '예'
    ok('sort check — 노트에 쓰기 는 참거짓만', any('노트에 쓰기' in e for e in sort.check_one('표시', bad, sort.load_systems(D))[0]))
    ok('사전 위치 = 체계 폴더/태그/사전.json · 체계로 안 읽힘', tag.dict_path() == os.path.join(D, '태그', '사전.json') and set(sort.systems()) == {'표시', '겹침', '뒤'})
    ok('가족 — 등급/SSS = (등급, SSS) · 순위 SSS 3 > S 1 · 가족 밖 None', tag.split('등급/SSS') == ('등급', 'SSS') and tag.rank('등급/SSS') == 3
       and tag.rank('등급/S') == 1 and tag.rank('등급/A') is None and tag.rank('시험태그') is None and tag.split('없음/x') == ('없음/x', None))
    pr = tag.problems()
    ok(f'문제 — 사전에 없는 태그(겹침태그 · 뒤태그) · 가족 밖 값(등급/A) ({len(pr)})',
       any('«겹침태그» 사전에 없음' in p for p in pr) and any('«뒤태그» 사전에 없음' in p for p in pr) and any('«등급/A» 가족 등급 에 없는 값' in p for p in pr) and len(pr) == 3)

    s1 = sort.run(now='2026-11-18T10:00:00')
    ok('has() = 옛 tag_of 셈 · 붙음 · 안 붙음 · 판정 없음',
       tag.has('note:2_지식/시험/a.md', '시험태그') == (True, '점수 5') and tag.has('note:2_지식/시험/e.md', '시험태그') == (False, '그 밖은 아니')
       and tag.has('없는:대상', '시험태그') == (None, '') and sort.tag_of('note:2_지식/시험/a.md', '시험태그') == tag.has('note:2_지식/시험/a.md', '시험태그'))
    PV = os.path.join(T, 'pv')
    shutil.copytree(D, PV)
    sp = json.load(open(os.path.join(PV, '표시.json'), encoding='utf-8'))
    sp['규칙'][0]['조건'] = {'칸': '점수', '이상': 6}
    put(PV, '표시', sp)
    idx0 = {f: rb(os.path.join(I, f)) for f in os.listdir(I) if os.path.isfile(os.path.join(I, f)) and not f.endswith('.lock')}
    pv = sort.preview(PV)
    idx1 = {f: rb(os.path.join(I, f)) for f in os.listdir(I) if os.path.isfile(os.path.join(I, f)) and not f.endswith('.lock')}
    ok(f'preview(규칙 바꿈 재생 대조) — 표시 예→아니 6 · 기대는 뒤 체계 빠짐 6 · 장부·상태·넘김 안 씀 · 진짜 체계 폴더로 돌아옴 ({len(pv)})',
       sorted((r['체계'], r['전'], r['후']) for r in pv) == sorted([('표시', '예', '아니')] * 6 + [('뒤', '보통', None)] * 6) and idx0 == idx1
       and sort.SYSTEMS == D and sort.state_item('표시', 'note:2_지식/시험/a.md')['갈래'] == '예')
    r1 = tag.sync(now='T1')
    a_txt = rb(os.path.join(N, 'a.md'))
    ok(f'sync — 붙임 a·c · 사람 것 b · 프론트매터 없음 d · 쓸 자리 없음(1_수집 · 노트 아님) 2 · 겹쳐 보이기 1 ({r1})',
       r1 == {'붙임': 2, '사람 것': 1, '프론트매터 없음': 1, '쓸 자리 없음': 2, '겹쳐 보이기': 1})
    ok('흐름 목록에 덧붙임 · CRLF 그대로 · 다른 줄 그대로',
       a_txt == notes['a.md'].replace('시험]'.encode('utf-8'), '시험, 시험태그]'.encode('utf-8')))
    ok('블록 목록에 한 줄', rb(os.path.join(N, 'c.md')) == '---\ntitle: c\ntags:\n  - x\n  - 시험태그\nstatus: active\n---\n본문 c\n'.encode('utf-8'))
    ok('사람이 단 b · 프론트매터 없는 d · 원본 층 x · 아니 e — 바이트 그대로',
       rb(os.path.join(N, 'b.md')) == notes['b.md'] and rb(os.path.join(N, 'd.md')) == notes['d.md'] and rb(os.path.join(N, 'e.md')) == notes['e.md']
       and rb(os.path.join(V, '1_수집', 'x.md')) == '---\ntitle: x\n---\n원본\n'.encode('utf-8'))
    st = tag.load_state()
    ok('붙인 장부 = 도구가 붙인 a·c 만(b 는 사람 것이라 안 적음)', sorted(st['붙임']) == ['2_지식/시험/a.md', '2_지식/시험/c.md']
       and st['붙임']['2_지식/시험/a.md']['시험태그']['주인'] == [['표시', 'note:2_지식/시험/a.md']] and len(lines(os.path.join(I, '태그.jsonl'))) == 4)
    snap = {k: rb(os.path.join(N, k)) for k in notes}
    r2 = tag.sync(now='T2')
    r3 = tag.sync(all_=True, now='T3')
    ok(f'멱등 — 다시 sync 빈 것 · --all 도 붙임·뗌 0 · 노트 바이트 그대로 ({r2} · {r3})',
       r2 == {} and not r3.get('붙임') and not r3.get('뗌') and all(rb(os.path.join(N, k)) == v for k, v in snap.items()))
    rows['note:2_지식/시험/a.md']['점수'] = 1
    rows['note:2_지식/시험/b.md']['점수'] = 1
    rows['note:2_지식/시험/c.md']['점수'] = 1
    sort.reset()
    sort.register_adapter('시험', Mem(rows))
    sort.register_adapter('시험2', Mem(rows2))
    sort.run(now='2026-11-18T11:00:00')
    r4 = tag.sync(now='T4')
    ok(f'판정이 바뀌면 도구가 붙인 a·c 만 뗌 → 원래 바이트 · 사람 것 b 는 그대로 ({r4})',
       r4.get('뗌') == 2 and rb(os.path.join(N, 'a.md')) == notes['a.md'] and rb(os.path.join(N, 'c.md')) == notes['c.md'] and rb(os.path.join(N, 'b.md')) == notes['b.md']
       and tag.load_state()['붙임'] == {})

    # 사람 태그
    e_id = 'note:2_지식/시험/e.md'
    res = tag.apply(e_id, '시험태그', now='2026-11-18T12:00:00', by='시험')
    rec = sort.state_item('표시', e_id)
    ok(f'apply — 판정자 사람 · 갈래 예 · 근거 «이거» · 노트에 붙임 ({res["노트"]})',
       res['갈래'] == '예' and rec['판정자'] == '사람' and rec['근거'] == '사람 «이거 시험태그» (시험)' and res['노트'].get('붙임') == 1
       and rb(os.path.join(N, 'e.md')) == '---\ntitle: e\ntags: [시험태그]\n---\n본문 e\n'.encode('utf-8') and tag.has(e_id, '시험태그')[0] is True)
    ok('apply 넘김 — 붙임 줄 · 판정 장부 사람 줄', any(json.loads(x)['대상'] == e_id and json.loads(x)['동작'] == {'태그': '시험태그'} for x in lines(os.path.join(I, '넘김.jsonl')))
       and any(json.loads(x)['대상'] == e_id and json.loads(x)['판정자'] == '사람' for x in lines(os.path.join(I, '판정.jsonl'))))
    sort.reset()
    sort.register_adapter('시험', Mem(rows))
    sort.register_adapter('시험2', Mem(rows2))
    s5 = sort.run(now='2026-11-18T12:10:00')
    ok(f'다음 run — 입력 같으면 ① 기억이 사람 판정을 지킴 ({s5["표시"]})', sort.state_item('표시', e_id)['판정자'] == '사람' and s5['표시'].get('기억', 0) >= 1)
    res2 = tag.apply(e_id, '시험태그', off=True, now='2026-11-18T12:20:00')
    ok(f'apply --off — 모르면 갈래(아니) · 노트에서 뗌 → 원래 바이트 ({res2["노트"]})',
       res2['갈래'] == '아니' and res2['노트'].get('뗌') == 1 and rb(os.path.join(N, 'e.md')) == notes['e.md'] and tag.has(e_id, '시험태그')[0] is False)
    errs = []
    for args, kw in ((('collect:y:1', '없는태그'), {}), ((e_id, '뒤태그'), {}), (('collect:y:1', '겹침태그'), {'system': '표시'})):
        try:
            tag.apply(*args, **kw)
            errs.append(None)
        except ValueError as e:
            errs.append(str(e))
    ok(f'apply 오류 — 없는 태그 · 대상 밖(앞 체계 아니) · 그 체계는 그 태그를 안 줌 ({[str(x)[:20] for x in errs]})',
       errs[0] and '주는 체계 없음' in errs[0] and errs[1] and '대상 밖' in errs[1] and errs[2] and '주는 체계 없음' in errs[2])
    lk = sort._lock()
    try:
        sort.answer('표시', e_id, '예', '사람', 'x')
        locked = False
    except RuntimeError:
        locked = True
    finally:
        lk.close()
    ok('answer — 다른 run 이 잠금을 쥐면 안 적음(메모리에만 적으면 사라짐)', locked and sort.state_item('표시', e_id)['갈래'] == '아니')
    ok('겹쳐 보이기 체계(노트 쓰기 끔) — 파일 0 · has 는 붙음', tag.has('collect:y:1', '겹침태그')[0] is True and tag.load_state()['붙임'] == {})

    # 프론트매터 꼴
    cases = [('---\ntags: []\n---\n', True, '---\ntags: [t]\n---\n'), ('---\ntags: a\n---\n', True, '---\ntags: [a, t]\n---\n'),
             ('---\ntags: ["#t", b]\n---\n', False, '---\ntags: [b]\n---\n'), ('---\ntags:\n---\n', True, '---\ntags:\n  - t\n---\n'),
             ('---\ntags: [t]\n---\n', True, '---\ntags: [t]\n---\n'), ('﻿---\ntitle: z\n---\n', True, '﻿---\ntitle: z\ntags: [t]\n---\n'),
             ('---\ntags: [a,\n  b]\n---\n', True, None), ('본문\n', True, None)]
    got = [tag.fm_set(x, 't', on) for x, on, _ in cases]
    ok(f'프론트매터 꼴 — 빈 흐름 · 홑값 · # 붙은 값 빼기 · 빈 tags · 이미 있음 · BOM · 여러 줄 흐름(안 고침) · 없음 ({sum(g == w for g, (_, _, w) in zip(got, cases))}/{len(cases)})',
       all(g == w for g, (_, _, w) in zip(got, cases)))
    ok('fm_tags — # · 따옴표 뗌', tag.fm_tags('---\ntags: ["#가", \'나\']\n---\n') == ['가', '나'] and tag.fm_tags('x') is None)

    # ════════ 알림 ════════
    if alert is None:
        print('— 알림 쪽 건너뜀: mobility 모듈이 없다(알림 도구 = mobility 몫)')
    else:
        D, I = fresh('alert')
        m = alert.alarms()
        ok('mobility 알림 모듈 읽힘(inbox_put · inbox_events · awake)', m is not None and all(hasattr(m, x) for x in ('inbox_put', 'inbox_events', 'awake')))
        INBOX = os.path.join(T, 'alarms-in')
        m.INBOX = INBOX
        S0 = m.parse_settings(None)[0]
        alert.settings = lambda: S0
        phone_on = {'v': True}
        alert.mobility_on = lambda: phone_on['v']
        put(os.path.join(D, '태그'), '사전', {'태그': {'등급': {'뜻': '시험 등급', '가족': ['SSS', 'SS', 'S', 'A']}}})
        g_rows = {'g:1': {'g': 'SSS', '자리': 'src-a', '제목': '하나'}, 'g:2': {'g': 'SS', '자리': 'src-a', '제목': '둘'},
                  'g:3': {'g': 'S', '자리': 'src-a', '제목': '셋'}, 'g:4': {'g': 'Z', '자리': 'src-a', '제목': '넷'}}
        u_rows = {'u:1': {'k': 'x', '자리': 'src-b', '제목': '순위 없음'}}
        w_rows = {'w:1': {'w': 'q', '자리': 'src-c', '제목': '묶음 아홉'}, 'w:2': {'w': 'r', '자리': 'src-c', '제목': '묶음 밤'}}

        def adapters():
            sort.reset()
            sort.register_adapter('등급', Mem(g_rows))
            sort.register_adapter('단순', Mem(u_rows))
            sort.register_adapter('때', Mem(w_rows))
        tiers = ['SSS', 'SS', 'S', 'A']
        put(D, '등급', {'id': '등급', '이름': '시험 등급', '판': 1, '대상': {'종류': '등급'},
                      '규칙': [{'id': f'g{t}', '말': f'g 가 {t}', '조건': {'칸': 'g', '같음': t}, '갈래': t} for t in tiers]
                      + [{'id': 'z', '말': '그 밖 버림', '조건': {'늘': True}, '갈래': '버림'}],
                      '갈래': {**{t: {'동작': [{'태그': f'등급/{t}'}, {'알림': {'때': '바로', '급함': t == 'SSS'}}]} for t in tiers}, '버림': {'동작': [{'장부': {}}]}},
                      '모르면': '버림', '사다리': {'claude': '끔'}})
        put(D, '단순', {'id': '단순', '판': 1, '대상': {'종류': '단순'},
                      '규칙': [{'id': 'k', '말': 'k 그대로', '조건': {'칸': 'k', '같음': 'x'}, '갈래': 'x'}, {'id': 'z', '말': '그 밖 y', '조건': {'늘': True}, '갈래': 'y'}],
                      '갈래': {'x': {'동작': [{'알림': {'때': '아침'}}]}, 'y': {'동작': [{'알림': {'때': '아침'}}]}}, '모르면': 'y', '사다리': {'claude': '끔'}})
        put(D, '때', {'id': '때', '판': 1, '대상': {'종류': '때'},
                     '규칙': [{'id': 'q', '말': 'q', '조건': {'칸': 'w', '같음': 'q'}, '갈래': 'q'}, {'id': 'z', '말': '그 밖 r', '조건': {'늘': True}, '갈래': 'r'}],
                     '갈래': {'q': {'동작': [{'알림': {'때': '묶음 09:00'}}]}, 'r': {'동작': [{'알림': {'때': '묶음 23:30'}}]}}, '모르면': 'r', '사다리': {'claude': '끔'}})
        ok('알림 체계 check 오류 0', all(not e for e, _ in sort.check(D).values()))
        LOG = os.path.join(I, '알림.jsonl')

        def at(e):
            return dt.datetime.fromtimestamp(e['at'] / 1000, KST).strftime('%m-%d %H:%M:%S')

        def inbox():
            return {e['id']: e for e in m.inbox_events(int(dt.datetime(2026, 11, 18, 12, 0, tzinfo=KST).timestamp() * 1000))}
        N2 = dt.datetime(2026, 11, 18, 2, 0, tzinfo=KST)
        adapters()
        sort.run(only=['등급'], now='2026-11-18T02:00:00')
        a1 = alert.run(now=N2)
        L = [json.loads(x) for x in lines(LOG)]
        box = inbox()
        ok(f'02:00 첫 돌림 — 낸 3 · 버림은 없음 · 폰 냄 ({a1})', a1.get('낸') == 3 and a1.get('폰') is True and len(L) == 3 and len(box) == 3)
        order = [(x['대상'], x['갈래'], x['묶음'], box[x['id']]['title'], at(box[x['id']])) for x in L]
        ok(f'때·차례 — SSS 급함 02:00 · SS·S 는 잘 시간 → 08:00 · 1초씩 · «k / n» 순위 차례 ({order})',
           order == [('g:1', 'SSS', [1, 3], '시험 등급 · SSS', '11-18 02:00:00'), ('g:2', 'SS', [2, 3], '시험 등급 · SS', '11-18 08:00:00'),
                     ('g:3', 'S', [3, 3], '시험 등급 · S', '11-18 08:00:01')])
        ok('알림 글 = 대상 제목 · 자리 = 출처 · 급함 칸 · 사건 id ev-sort- · 꼴 맞음(mobility _inbox_ok)',
           box[L[0]['id']]['text'] == '하나' and all(x['자리'] == 'src-a' for x in L) and [x['급함'] for x in L] == [True, False, False]
           and all(i.startswith('ev-sort-') and m._inbox_ok(e, 'sort') for i, e in box.items()) and L[0]['때'] == '바로(급함)' and L[1]['때'] == '바로 → 아침')
        built = m.build(now=N2, rows=[], st={}, queue=[], settings=(S0, []), notices=[], per=({}, []), skips=set(), rings={'rings': {}, 'lines': {}, 'snoozes': {}},
                        inbox=list(box.values()))
        ids = [a['id'] for a in built['items'] if a['id'].startswith('ev-sort-')]
        ok(f'서버 사본 — /v1/alarms 꼴에 ev-sort 3건 · 칸 id·at·title·text ({len(ids)})', sorted(ids) == sorted(box) and all(set(a) <= {'id', 'at', 'title', 'text', 'open', 'mode'}
           for a in built['items'] if a['id'].startswith('ev-sort-')))
        nob = m.build(now=N2, rows=[], st={}, queue=[], settings=(S0, []), notices=[], per=({}, []), skips=set(), rings={'rings': {}, 'lines': {}, 'snoozes': {}})
        ok('서버 사본 — 설정을 손으로 준 build 는 inbox 를 안 읽음 · st 없으면 사건 없음', not [a for a in nob['items'] if a['id'].startswith('ev-sort-')]
           and not [a for a in m.build(now=N2, rows=[], settings=(S0, []), per=({}, []), skips=set(), rings={'rings': {}, 'lines': {}, 'snoozes': {}}, inbox=list(box.values()))['items'] if a['id'].startswith('ev-')])
        ok('다시 돌림 — 새 줄 없음 = 낸 0', not alert.run(now=N2).get('낸'))
        N10 = dt.datetime(2026, 11, 18, 10, 0, tzinfo=KST)
        seq = []
        for g in ('S', 'SSS', 'SS'):
            g_rows['g:2']['g'] = g
            adapters()
            sort.run(only=['등급'], now='2026-11-18T10:00:00')
            seq.append(alert.run(now=N10))
        ok(f'중복 — SS→S 내림 안 울림 · →SSS 오름 울림(급함 지금) · →SS 안 울림 ({seq})',
           seq[0].get('중복') == 1 and not seq[0].get('낸') and seq[1].get('낸') == 1 and seq[2].get('중복') == 1 and not seq[2].get('낸')
           and json.loads(lines(LOG)[-1])['울릴 때'].startswith('2026-11-18T10:00'))
        gone = g_rows.pop('g:3')
        adapters()
        sort.run(only=['등급'], now='2026-11-18T10:05:00')
        fg = alert.run(now=N10)
        g_rows['g:3'] = gone
        adapters()
        sort.run(only=['등급'], now='2026-11-18T10:10:00')
        back = alert.run(now=N10)
        ok(f'사라지면 잊음 → 다시 나오면 새것({fg} · {back})', fg.get('잊음') == 1 and back.get('낸') == 1)
        g_rows['g:5'] = {'g': 'SS', '자리': 'src-a', '제목': '다섯'}
        adapters()
        sort.run(only=['등급'], now='2026-11-18T10:20:00')
        g_rows['g:5']['g'] = 'Z'
        adapters()
        sort.run(only=['등급'], now='2026-11-18T10:21:00')
        stale = alert.run(now=N10)
        ok(f'지난 판정 — 알림 뒤 버림으로 바뀐 대상은 안 울림 ({stale})', stale.get('지난 판정') == 1 and not stale.get('낸'))
        adapters()
        sort.run(only=['단순'], now='2026-11-18T10:30:00')
        u1 = alert.run(now=N10)
        u_rows['u:1']['k'] = 'y'
        adapters()
        sort.run(only=['단순'], now='2026-11-18T10:31:00')
        u2 = alert.run(now=N10)
        u_rows['u:1']['k'] = 'x'
        adapters()
        sort.run(only=['단순'], now='2026-11-18T10:32:00')
        u3 = alert.run(now=N10)
        lu = [json.loads(x) for x in lines(LOG) if json.loads(x)['체계'] == '단순']
        ok(f'순위 없는 체계 — 처음 x · 처음 y 울림 · 다시 x 안 울림 · 아침 = 다음 날 08:00 ({u1} {u2} {u3})',
           u1.get('낸') == 1 and u2.get('낸') == 1 and u3.get('중복') == 1 and all(x['울릴 때'].startswith('2026-11-19T08:00') for x in lu))
        adapters()
        sort.run(only=['때'], now='2026-11-18T10:40:00')
        w = alert.run(now=N10)
        lw = {json.loads(x)['대상']: json.loads(x) for x in lines(LOG) if json.loads(x)['체계'] == '때'}
        ok(f'묶음 09:00(10시에) = 다음 날 09:00 · 묶음 23:30 = 잘 시간이라 아침 08:00 ({w})',
           w.get('낸') == 2 and lw['w:1']['울릴 때'].startswith('2026-11-19T09:00') and lw['w:2']['울릴 때'].startswith('2026-11-19T08:00') and lw['w:2']['때'] == '묶음 23:30 → 아침')
        phone_on['v'] = False
        before = rb(os.path.join(INBOX, 'sort.json'))
        g_rows['g:4']['g'] = 'A'
        adapters()
        sort.run(only=['등급'], now='2026-11-18T10:50:00')
        off = alert.run(now=N10)
        ok(f'mobility 꺼짐 — 수집 창(장부)에만 · 폰 저장소 그대로 ({off})', off.get('낸') == 1 and off.get('폰') is False
           and json.loads(lines(LOG)[-1])['폰'] is False and rb(os.path.join(INBOX, 'sort.json')) == before)
        phone_on['v'] = True
        g_rows['g:4']['g'] = 'SS'
        adapters()
        sort.run(only=['등급'], now='2026-11-18T11:00:00')
        sg = json.load(open(os.path.join(D, '등급.json'), encoding='utf-8'))
        sg['켬'] = False
        put(D, '등급', sg)
        adapters()
        sysoff = alert.run(now=N10)
        ok(f'꺼진 체계 — 넘김에 알림 줄이 있어도 안 울림 ({sysoff})', sysoff.get('체계 꺼짐') == 1 and not sysoff.get('낸'))
        sg['켬'] = True
        put(D, '등급', sg)
        adapters()
        n_log = len(lines(LOG))
        d1 = alert.now_one('지금 하나', '급함 글', urgent=True, place='src-a', now=N2)
        d2 = alert.now_one('아침에 하나', now=N2)
        d3 = alert.now_one('마른', now=N2, dry=True)
        box = inbox()
        ok(f'alert.now — 급함 02:00 지금 · 아님 08:00 · dry 는 안 씀 ({d1["때"]} · {d2["때"]})',
           at(box[d1['id']]) == '11-18 02:00:00' and at(box[d2['id']]) == '11-18 08:00:00' and d3['id'] not in box and len(lines(LOG)) == n_log + 2
           and json.loads(lines(LOG)[-2])['자리'] == 'src-a')
        try:
            m.inbox_put('notice', [{'id': 'ev-notice-1', 'at': 1, 'title': 't', 'made': 1}], path=INBOX)
            own = False
        except ValueError:
            own = True
        raw_before = rb(os.path.join(INBOX, 'sort.json'))
        try:
            m.inbox_put('sort', [{'id': 'ev-sort-ok', 'at': 1, 'title': 't', 'made': 1}, {'id': 'x-1', 'at': 1, 'title': 't', 'made': 1}], path=INBOX)
            shape = False
        except ValueError:
            shape = True
        nowms = int(N10.timestamp() * 1000)
        m.inbox_put('sort', [{'id': 'ev-sort-old', 'at': nowms, 'title': '옛', 'made': nowms - 8 * 86400000}], now_ms=nowms, path=INBOX)
        m.inbox_put('sort', [{'id': 'ev-sort-same', 'at': nowms, 'title': '앞', 'made': nowms}], now_ms=nowms, path=INBOX)
        m.inbox_put('sort', [{'id': 'ev-sort-same', 'at': nowms, 'title': '뒤', 'made': nowms}], now_ms=nowms, path=INBOX)
        bx = {e['id']: e for e in m.inbox_events(nowms, path=INBOX)}
        ok('inbox_put — 이 모듈 kind 거절 · 꼴 틀리면 아무것도 안 씀 · 7일 지난 것 뺌 · 같은 id 는 새것',
           own and shape and 'ev-sort-ok' not in bx and 'ev-sort-old' not in bx and bx['ev-sort-same']['title'] == '뒤' and raw_before != b'')

        # 수집 창 «일어난 일»
        spec = importlib.util.spec_from_file_location('collect_desk_alert', os.path.join(VAULT, '.claude', 'skills', 'collect_desk', 'scripts', 'collect_desk.py'))
        cd = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cd)
        cd.SORT_IX = I
        ra = cd.sort_alert_rows('src-a')
        hb = cd.history('src-c')
        ok(f'수집 창 — 자리 src-a 알림 줄 {len(ra)} · kind alert · who sort · 펼침 줄(글·체계·때·폰) · 다른 자리 안 섞임',
           cd.mobility_alerts() and len(ra) == sum(1 for x in lines(LOG) if json.loads(x)['자리'] == 'src-a') and all(r['kind'] == 'alert' and r['who'] == 'sort' and len(r['lines']) >= 3 for r in ra)
           and any('폰에 냄' in r['lines'][2] for r in ra) and any('폰 안 냄' in r['lines'][2] for r in ra) and len(hb) >= 2 and all(r['kind'] == 'alert' for r in hb[:2]))
        cd.SORT_IX = os.path.join(T, '없는')
        cd._ONCE.clear()
        ok('수집 창 — 알림 장부 없으면 기록 줄 그대로(빈 것)', cd.sort_alert_rows('src-a') == [])

        # 알림 도구 = mobility 몫(11-18 결정 — 알림 도구는 mobility 가 맡고 나머지는 본체) — 꺼짐: 분류 직후 부름이 도구를 안 부름 ·
        # 수집 창 줄은 넘김 장부에서 · 폰 전달 없음 / 켬: 분류 직후 그 자리에서 밀린 것까지 냄
        import roles
        real_on, real_ix = roles.module_on, sort._REAL_INDEX
        sort._REAL_INDEX = I                                   # 이 시험 장부를 «진짜 자리»로(분류 직후 부름이 돌게) · 끝나면 되돌림
        cd.SORT_IX = I
        try:
            roles.module_on = lambda mid, *a, **k: False if mid == 'mobility' else real_on(mid, *a, **k)
            n_log, box_before, sort.LAST_ALERT = len(lines(LOG)), rb(os.path.join(INBOX, 'sort.json')), None
            u_rows['u:2'] = {'k': 'x', '자리': 'src-b', '제목': '꺼진 때'}
            adapters()
            sort.run(only=['단순'], now='2026-11-18T12:10:00')
            cd._ONCE.clear()
            rb_rows = cd.sort_alert_rows('src-b')
            ok('mobility 꺼짐 — 분류 직후 알림 도구 안 부름(알림 장부·폰 저장소 그대로) · 수집 창은 넘김 알림 줄(제목 · 폰 안 냄)',
               not cd.mobility_alerts() and sort.alert_tool() is None and sort.LAST_ALERT is None and len(lines(LOG)) == n_log and rb(os.path.join(INBOX, 'sort.json')) == box_before
               and any('꺼진 때' in r['lines'][0] and '폰 안 냄' in r['lines'][-1] for r in rb_rows))
            roles.module_on = lambda mid, *a, **k: True if mid == 'mobility' else real_on(mid, *a, **k)
            u_rows['u:3'] = {'k': 'x', '자리': 'src-b', '제목': '켠 때'}
            adapters()
            sort.run(only=['단순'], now='2026-11-18T12:20:00')
            cd._ONCE.clear()
            rb_rows = cd.sort_alert_rows('src-b')
            got_new = [json.loads(x)['대상'] for x in lines(LOG)[n_log:]]
            ok(f'mobility 켬 — 분류 직후 그 자리에서 알림 도구(꺼진 동안 밀린 u:2 까지) · 수집 창 줄은 도구 줄로 ({sort.LAST_ALERT})',
               sort.alert_tool() is alert and (sort.LAST_ALERT or {}).get('낸') == 2 and sorted(got_new) == ['u:2', 'u:3']
               and not any('폰 안 냄(알림 도구' in r['lines'][-1] for r in rb_rows if '켠 때' in ' '.join(r['lines'])))
        finally:
            roles.module_on, sort._REAL_INDEX = real_on, real_ix

        # ════════ 항공권(가격 조회 사본 켬 + 녹화 가격줄) ════════
        _PR = [os.path.join(SYS, '_eval', 'price_rec'), os.path.join(SYS, '_eval', 'fixtures', 'price')]
        if not all(os.path.isdir(x) for x in _PR):
            print('— 항공권 건너뜀: 가격 녹화·고정본(_eval/price_rec · fixtures/price)이 없다')
        else:
            import collect_price as cp
            import sort_price as spa
            REC = os.path.join(SYS, '_eval', 'price_rec')
            TAPE = {tuple(sorted(p['요청'].items())): p['응답'] for p in json.load(open(os.path.join(REC, 'travelpayouts-icn-cts.json'), encoding='utf-8'))['녹화']}

            def tape(url, headers):
                q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
                return 200, json.dumps(TAPE[tuple(sorted(q.items()))]).encode('utf-8'), {'X-Rate-Limit-Remaining': '599'}
            PT = os.path.join(T, 'price')
            os.makedirs(os.path.join(PT, 'recipes'))
            FIX = os.path.join(SYS, '_eval', 'fixtures', 'price')     # 시험 고정본(조리법·체계)
            rc = json.load(open(os.path.join(FIX, 'tp-icn-cts.json'), encoding='utf-8'))
            rc['켬'] = True
            json.dump(rc, open(os.path.join(PT, 'recipes', rc['id'] + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
            cp.RECIPES, cp.STATE, cp.SECRETS = os.path.join(PT, 'recipes'), os.path.join(PT, 'state'), os.path.join(PT, 'secret.local.json')
            json.dump({'travelpayouts': {'token': 'TEST-TOKEN-0000'}}, open(cp.SECRETS, 'w', encoding='utf-8'))
            cp.TRANSPORT = tape
            cp.NOW = lambda: dt.datetime(2026, 11, 18, 1, 0, tzinfo=KST)
            ok('녹화 가격줄 돌림', cp.run('tp-icn-cts')['상태'] == '됨')
            D, I = fresh('price')
            sk = json.load(open(os.path.join(FIX, next(f for f in sorted(os.listdir(FIX)) if f != 'tp-icn-cts.json')), encoding='utf-8'))   # 가격 체계 고정본 하나
            SKN = sk['id']
            sk['켬'] = True
            put(D, SKN, sk)
            shutil.copytree(os.path.join(SYS, 'sort', '태그'), os.path.join(D, '태그'))
            sort.register_adapter('가격줄', spa)
            sort.run(now='2026-11-18T02:00:00')
            pst = sort.state(SKN)['items']
            sss = [k for k, r in pst.items() if r['갈래'] == 'SSS']
            honey = [k for k, r in pst.items() if r['갈래'] != '버림']
            ok(f'꿀티켓 — 티어 태그 = 태그 도구 has · SSS {len(sss)} · 꿀 {len(honey)}', len(sss) == 2 and len(honey) == 19
               and all(tag.has(k, '티어/SSS')[0] is True for k in sss) and tag.has(sss[0], '티어/SS')[0] is False and not tag.problems())
            pa = alert.run(now=N2)
            LP = [json.loads(x) for x in lines(os.path.join(I, '알림.jsonl'))]
            box = inbox()
            ranks = [spa.TIER_RANK[x['갈래']] for x in LP]
            first = box[LP[0]['id']]
            ok(f'꿀티켓 알림 — 19건 한 돌림 «k / 19» · 티어 높은 것부터 · SSS 2건만 급함 02:00 · 나머지 08:00 ({pa})',
               pa.get('낸') == 19 and [x['묶음'] for x in LP] == [[k, 19] for k in range(1, 20)] and ranks == sorted(ranks, reverse=True)
               and [x['급함'] for x in LP] == [True, True] + [False] * 17 and at(first).startswith('11-18 02:00') and at(box[LP[2]['id']]).startswith('11-18 08:00'))
            ok(f'꿀티켓 알림 글 = sort_price 폰 꼴 · 누름 = 홈(https 링크는 폰이 못 엶 → open 없음 · 링크는 장부에) — «{first["title"]}»',
               first['title'].startswith('SSS 항공권 · 2인 ') and '→' in first['text'] and '박' in first['text'] and 'open' not in first and LP[0].get('링크', '').startswith('https://')
               and LP[0]['자리'] == rc['label'])
            price = {r['id']: r['2인가'] for r in cp.rows_of('tp-icn-cts')}
            ok('같은 티어 안 = 싼 것부터 · rank·alert_key 꼴', all(LP[i]['갈래'] != LP[i + 1]['갈래'] or price[LP[i]['대상']] <= price[LP[i + 1]['대상']] for i in range(len(LP) - 1))
               and [spa.alert_key({'facts': {'2인가': 5}}), spa.rank('버림'), spa.rank('SSS')] == [5, None, 6])
            again = alert.run(now=N2)
            ok('꿀티켓 — 다시 돌림 낸 0', not again.get('낸'))

    # ════════ 공지 사본 — 사람이 단 황금 태그(tag.apply → 공지 필터 다리 · 골든과 같은 사본 길 · 1_수집 은 읽기만) ════════
    D, I = fresh('notice')
    sort.SYSTEMS = os.path.join(SYS, 'sort')                # 진짜 체계 파일(읽기만) · 장부는 임시
    sort.reset()
    for k in list(sort._adapters):
        del sort._adapters[k]
    spec = importlib.util.spec_from_file_location('notice_filter', os.path.join(SYS, 'notice-filter.py'))
    nf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nf)
    if not (os.path.isdir(nf.STATE) and os.path.isdir(sort.SYSTEMS)):
        print('— 공지 사본 건너뜀: 이 볼트에 공지 수집 자료(_index/collect)나 분류 체계가 없다')
    else:
        NS = os.path.join(T, 'notice')
        stt = os.path.join(NS, 'state')
        shutil.copytree(nf.STATE, stt, ignore=shutil.ignore_patterns('*.log', '*.lock', '제출'))
        shutil.copytree(nf.RECIPES, os.path.join(NS, 'collect'), ignore=shutil.ignore_patterns('browser', 'candidates'))
        shutil.copy(nf.CARD, os.path.join(NS, 'card.md'))
        nf.STATE, nf.CACHE, nf.STAGE, nf.ARCH = stt, os.path.join(stt, '조건'), os.path.join(stt, 'stage'), os.path.join(stt, 'archive')
        nf.MARKS, nf.RECIPES, nf.CARD, nf.QUEUE = os.path.join(stt, '평가.json'), os.path.join(NS, 'collect'), os.path.join(NS, 'card.md'), os.path.join(NS, 'queue.md')
        nf._card.clear()
        nf.sort_on = lambda: True
        nf.rebridge()
        sids = [rc['id'] for rc in nf.recipes()]
        before = {sid: nf.judged(sid) for sid in sids}
        import sort_collect as sc
        gst = sort.state(G)
        allow = ('해당', '확인 필요')
        pick = next((k for k, r in sorted(gst['items'].items()) if r['갈래'] == '아님'
                     and (sort.state_item('공지-들이기', k) or {}).get('갈래') in allow), None) or next(iter(sorted(gst['대기'])), None)
        ok(f'공지 사본 — 사람이 {G} 을 달 글 있음 ({pick})', pick is not None)
        psid, pid = pick.split(':')[1], pick.split(':', 2)[2]
        ok(f'공지 사본 — 그 글은 지금 {G} 아님', not before[psid][pid][1].startswith(G))
        r_on = tag.apply(pick, G, now='2026-11-18T12:00:00', redraw=False)
        nf.rebridge()
        after = nf.judged(psid)
        rec = sort.state_item(G, pick)
        ok(f'공지 사본 — apply 뒤 공지 필터 다리가 tag.has 로 «{G}» 을 맨 앞에 · 판정자 사람이 다음 다리 run 에도 남음(지문 같음) ({r_on["판정"]} · {nf._sort_run.get(G)})',
           after[pid][1].startswith(G) and rec['판정자'] == '사람' and nf._sort_run.get(G, {}).get('기억', 0) >= 1 and not sc.MISSES)
        others = {s: {k: v for k, v in nf.judged(s).items() if f'collect:{s}:{k}' != pick} for s in sids}
        ok('공지 사본 — 다른 글은 판정·한 줄 그대로', all(others[s] == {k: v for k, v in before[s].items() if f'collect:{s}:{k}' != pick} for s in sids))
        tag.apply(pick, G, off=True, now='2026-11-18T12:05:00', redraw=False)
        nf.rebridge()
        ok(f'공지 사본 — apply --off 뒤 «{G}» 빠짐(갈래 아님 · 판정자 사람)', not nf.judged(psid)[pid][1].startswith(G) and sort.state_item(G, pick)['판정자'] == '사람')
finally:
    shutil.rmtree(T, ignore_errors=True)

print('\n' + ('전부 통과' if not fails else f'실패 {len(fails)}: {fails}'))
sys.exit(1 if fails else 0)
