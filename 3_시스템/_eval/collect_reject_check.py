"""수집 창 거절 단추(11-09) — collect_desk.py·notice-filter.py 를 불러 엔진·볼트 쓰기 없이 잰다.
잰다: 제목 낱말 단추 · reject 명령이 엔진에 넘기는 인자(빈칸·대시 메모) · 판정 대기 아닌 글·제목에 없는 낱말 거부 ·
     옛 item reject 도 까닭 «거절»을 안 적음 · 연습 화면 흉내 · actions.json 새 행위 · notice-filter CLI 해석."""
import importlib.util
import json
import os
import sys

sys.dont_write_bytecode = True
AN = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # 볼트
fails = []


def ok(name, cond, got=None):
    print(('통과 ' if cond else '실패 ') + name + ('' if cond or got is None else f' — {got}'))
    if not cond:
        fails.append(name)


def load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


cd = load('cd', os.path.join(AN, '.claude', 'skills', 'collect_desk', 'scripts', 'collect_desk.py'))

# 제목 낱말
w = cd.title_words('[기아] 26년 엔지니어(생산직) 설비기술인력 채용 (~11/18(수) 15시까지)')
ok('낱말: 날짜·숫자 빠지고 기관·직무 남음', w[:4] == ['기아', '엔지니어', '생산직', '설비기술인력'] and '26년' not in w and '11' not in w, w)
w = cd.title_words('2026학년도 비교과과정 및 쿠카이브 만족도 조사 안내')
ok('낱말: 흔한 말(안내)·학년도 빠짐', '안내' not in w and '2026학년도' not in w and '쿠카이브' in w, w)
ok('낱말: 12개까지', len(cd.title_words(' '.join(f'낱말{i}가' for i in range(30)))) == 12)

# reject 명령 — 엔진 호출을 가로챈다
calls = []
cd.engine = lambda *a: calls.append(a)
cd.recipe_of = lambda sid: {}
ITEMS = {'1882': {'title': '[기아] 설비기술인력 채용', 'url': 'u'},                       # 판정 대기(stage·verdict 없음)
         '9': {'title': '볼트 글', 'path': 'x.md'}}
cd.load = lambda *p, default=None: {'items': ITEMS} if p[-1].endswith('.json') and p[-1] != '평가.json' else default


class NoBusy:
    def __init__(self, *a):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


cd.Busy = NoBusy
cd.reject('ku-ee-job', '1882', '기아|설비기술인력|기아', '-생산직 안 함')
ok('reject: 낱말(겹침 하나)·메모(대시)가 = 꼴로 넘어감 · 다음 판정', calls == [('notice-filter.py', 'reject', '1882', '--button', '--word=기아', '--word=설비기술인력', '--memo=-생산직 안 함'), ('notice-filter.py', 'judge')], calls)
calls.clear()
cd.reject('ku-ee-job', '1882', '', '')
ok('reject 빈칸: 낱말 없이 · 빈 메모', calls[0] == ('notice-filter.py', 'reject', '1882', '--button', '--memo='), calls)
for args, why in ((('ku-ee-job', '1882', '삼성', ''), '제목에 없는 낱말'), (('ku-ee-job', '9', '', ''), '판정 대기 글만'), (('ku-ee-job', '없음', '', ''), '없는 글')):
    calls.clear()
    try:
        cd.reject(*args)
        ok(f'거부: {why}', False, '거부 안 함')
    except cd.Refuse as e:
        ok(f'거부: {why} · 엔진 0', why in str(e) and not calls, (str(e), calls))
calls.clear()
cd.item('ku-ee-job', '1882', 'reject')
ok('옛 item reject: 까닭 «거절» 대신 --button', calls[0] == ('notice-filter.py', 'reject', '1882', '--button'), calls)

# 연습 화면 흉내
import datetime as dt
src = 'ku-x'
F = {f'3_시스템/collect/{src}.json': {'id': src}, f'3_시스템/_index/collect/{src}.json': {'items': {'n1': {'title': '학생회 설문 참여 부탁', 'stage': 1}}},
     '3_시스템/lms/desk.json': {}}
cd.practice_act(F, {'id': 'collect_desk.reject', 'args': {'source': src, 'id': 'n1', 'words': '학생회|설문', 'memo': '관심 없음'}}, dt.datetime(2026, 11, 9))
it = F[f'3_시스템/_index/collect/{src}.json']['items']['n1']
ok('연습: 장부로 · 근거 = 낱말 + 메모', it.get('verdict') == '뺌' and 'stage' not in it and it['why'] == f'{cd.ME}: «학생회» · «설문» · 관심 없음', it)
try:
    cd.practice_act(F, {'id': 'collect_desk.reject', 'args': {'source': src, 'id': 'n1', 'words': '없는말', 'memo': ''}}, dt.datetime(2026, 11, 9))
    ok('연습: 제목에 없는 낱말 거부', False)
except cd.Refuse:
    ok('연습: 제목에 없는 낱말 거부', True)

# 행위 선언
acts = json.load(open(os.path.join(AN, '3_시스템', 'actions.json'), encoding='utf-8'))
flat = json.dumps(acts, ensure_ascii=False)
ok('actions.json: collect_desk.reject 선언 · 인자 넷 · -- 뒤 위치 인자', '"collect_desk.reject"' in flat and '"reject", "--", "{source}", "{id}", "{words}", "{memo}"' in flat)

# notice-filter CLI 해석(reject 함수는 가로챔)
nf = load('nf', os.path.join(AN, '3_시스템', 'notice-filter.py'))
got = []
nf.reject = lambda *a, **k: got.append((a, k))
for argv in (['reject', '1882', '--button', '--word=기아', '--memo=-생산직'], ['reject', '1882', '--button'], ['reject', '1882', '말로', '뺀', '까닭']):
    sys.argv = ['notice-filter.py'] + argv
    nf.main()
ok('CLI: 단추 · 낱말 · 대시 메모', got[0] == (('1882', '-생산직', ['기아']), {'button': True}), got[0])
ok('CLI: 단추 빈칸', got[1] == (('1882', '', []), {'button': True}), got[1])
ok('CLI: Claude 가 받아 적는 옛 꼴 그대로', got[2] == (('1882', '말로 뺀 까닭'), {}), got[2])
for argv in (['reject', '1882'], ['reject', '1882', 'a', '--button']):
    sys.argv = ['notice-filter.py'] + argv
    try:
        nf.main()
        ok(f'CLI 거부 {argv}', False)
    except SystemExit:
        ok(f'CLI 거부 {" ".join(argv)}', True)

print(f'실패 {len(fails)}')
sys.exit(1 if fails else 0)
