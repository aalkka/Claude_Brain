"""filter-learn.py·notice-filter.py 제목 규칙·일정 묶기 시험 — 격리(임시 폴더의 카드·조리법·평가·상태 사본 · 볼트 파일을 안 건드림). 2026-11-05.
잰다: 카드 규칙이 조리법 복사 없이 걸림 · 거르기 없는 출처·관심 주제·깨진 낱말은 안 뺌 · 살린 글 → 낱말 풀림 → 제목 관문 통과 ·
     뺀 까닭이 글에 없으면 규칙 안 올리고 대기열 · 까닭이 맞으면 전 출처 제외어 · 카드 조건이 깨지면 묶음이 꺼짐 · 다시볼날 → 대기열 ·
     대기 칸 판정 전 글 → 장부 · 제외 문장 근거는 빼지 않음 · 출처 여럿이 일정 파일 하나를 나눠 씀(덮어쓰기·겹침·체크 번짐 없음)."""
import importlib.util
import json
import os
import shutil
import sys
import tempfile

SYS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sp = importlib.util.spec_from_file_location('fl', os.path.join(SYS, 'filter-learn.py'))
sys.dont_write_bytecode = True
fl = importlib.util.module_from_spec(sp)
sp.loader.exec_module(fl)
nf = fl.nf

T = tempfile.mkdtemp(prefix='fl-check-')
fails = []


def ok(name, cond):
    print(('통과 ' if cond else '실패 ') + name)
    if not cond:
        fails.append(name)


try:
    # 격리: 필터·되먹임이 보는 자리를 전부 임시로
    os.makedirs(os.path.join(T, 'collect'))
    os.makedirs(os.path.join(T, 'state', '조건'))
    os.makedirs(os.path.join(T, 'state', 'stage', 'src-a'))
    card = '---\ntitle: 시험 카드\nupdated: 2026-01-01\n---\n# 카드\n\n```json\n' + json.dumps({
        '학년': 2, '신분': '학부 재학', '관심': [], '지역': {'본인': '서울', '구': None},
        '제목규칙': [{'이름': '신입 채용', '칸': '학년', '미만': 4, '말': ['신입사원']},
                 {'이름': '관심 밖', '말': ['공연']},
                 {'이름': '다른 지역', '칸': '지역', '전부': '서울', '말': ['거창군']}],
        '다시볼날': {'2000-01-01': '시험 사유', '2999-01-01': '먼 날'}}, ensure_ascii=False, indent=2) + '\n```\n\n## 답의 출처\n- 그대로 남아야 함\n'
    cf = os.path.join(T, '자격-카드.md')
    open(cf, 'w', encoding='utf-8', newline='\n').write(card)
    rc = {'id': 'src-a', 'name': 'A', 'contract': 'x', 'family': 'regex', 'filter': {'kind': '할일', 'title_skip': '출처몫|공모전'}}
    rp = os.path.join(T, 'collect', 'src-a.json')
    json.dump(rc, open(rp, 'w', encoding='utf-8'), ensure_ascii=False)
    q = os.path.join(T, '수집-대기열.md')
    open(q, 'w', encoding='utf-8').write('# 수집 대기열\n')
    marks = os.path.join(T, 'state', '평가.json')
    items = {
        'p1': {'title': '2026 학생 공모전 안내', 'date': '2026-10-01', 'path': 'v/p1.md', 'hash': 'a'},       # 사용자가 살림 → 조리법 낱말 공모전 풀림
        'p2': {'title': '관정재단 신규장학생 선발', 'date': '2026-10-02', 'path': 'v/p2.md', 'hash': 'b'},     # «저소득 아님»으로 뺐으나 글에 그 말이 없음
        'p3': {'title': '통영시 희망재단 대학생 장학금', 'date': '2026-10-03', 'path': 'v/p3.md', 'hash': 'c'},  # «희망재단 아님» → 제목에 있음 → 제외어
        'p4': {'title': '겨울 공연 안내', 'date': '2026-10-03', 'path': 'v/p4.md', 'hash': 'e'},                # 사용자가 살림 → 카드 낱말 공연 풀림
        's1': {'title': '삼성 신입사원 채용', 'date': '2026-10-04', 'stage': True, 'hash': 'd', 'url': 'http://x/s1'},   # 대기 칸 판정 전 → 장부
    }
    json.dump({'items': items}, open(os.path.join(T, 'state', 'src-a.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    open(os.path.join(T, 'state', 'stage', 'src-a', 's1.md'), 'w', encoding='utf-8').write('# 삼성 신입사원 채용\n\n---\n본문')
    os.makedirs(os.path.join(T, 'v'))
    for k, body in (('p1', '# 2026 학생 공모전 안내\n\n---\n본문'), ('p2', '# 관정재단 신규장학생 선발\n\n---\n성적우수 장학금 본문'), ('p3', '# 통영시 희망재단\n\n---\n본문'), ('p4', '# 겨울 공연 안내\n\n---\n본문')):
        open(os.path.join(T, 'v', k + '.md'), 'w', encoding='utf-8').write(body)
    json.dump({'src-a:p1': {'평가': '쓸모', '메모': '사용자 살림'},
               'src-a:p4': {'평가': '쓸모', '메모': '사용자 살림'},
               'src-a:p2': {'평가': '헛것', '메모': '저소득 아님 — 10분위 넘음'},
               'src-a:p3': {'평가': '헛것', '메모': '희망재단 아님'}}, open(marks, 'w', encoding='utf-8'), ensure_ascii=False)
    nf.CARD, nf.RECIPES, nf.STATE, nf.STAGE, nf.CACHE, nf.MARKS, nf.QUEUE, nf.VAULT, nf.ARCH = cf, os.path.join(T, 'collect'), os.path.join(T, 'state'), os.path.join(T, 'state', 'stage'), os.path.join(T, 'state', '조건'), marks, q, T, os.path.join(T, 'arch')
    nf.REPORT, nf.STATUS, nf.LMS_PENDING = os.path.join(T, 'state', '판정.md'), os.path.join(T, 'state', '.status.txt'), os.path.join(T, '없음.json')
    nf._card.clear()
    fl.RECIPES, fl.STATE, fl.LOG, fl.VAULT = nf.RECIPES, nf.STATE, os.path.join(T, 'state', '되먹임.jsonl'), T
    os.makedirs(os.path.join(T, '2_지식', '일정'))
    os.makedirs(os.path.join(T, '1_수집'))

    row = lambda t: {'title': t, 'date': '2026-10-05'}
    rc0 = json.load(open(rp, encoding='utf-8'))
    ok('카드 규칙: 조리법에 없어도 제목 관문에 걸림 · 근거 = 묶음 이름', nf.gate(rc0, row('현대 신입사원 모집')) == ('비해당', '제목 규칙(신입 채용)'))
    ok('카드 규칙: 거르기 없는 출처(filter {})엔 안 걸림', nf.gate({'id': 'x', 'filter': {}}, row('현대 신입사원 모집')) is None)
    n0 = {'sid': 'x', 'id': '1', 'title': '현대 신입사원 모집', 'rc': {'filter': {}}, 'text': '', 'att': []}
    ok('카드 규칙: LMS 글(filter {}) 판정에도 안 걸림', nf.judge_rules(n0, {'조건': []}, nf.card())[0] == '확인 필요')
    ok('카드 규칙: 거르는 출처 판정에 걸림', nf.judge_rules(dict(n0, rc=rc0), {'조건': []}, nf.card())[0] == '비해당')
    ok('카드 규칙: 관심 주제면 안 뺌', nf.card_rule('신입사원 반도체', {'관심': ['반도체'], '제목규칙': [{'이름': 'x', '말': ['신입사원']}]}) is None)
    ok('카드 규칙: 깨진 낱말은 수집을 안 세움', nf.card_rule('(깨짐 제목', {'제목규칙': [{'이름': 'x', '말': ['(깨짐']}]}) is None)
    ok('cond: 빈 칸(구)은 세지 않음', nf.cond_ok({'칸': '지역', '전부': '서울'}, nf.card()))

    # 제외 문장 오독(판정)
    me = nf.card()
    neg = {'sid': 'x', 'id': '2', 'title': '졸업요구 안내', 'rc': {'filter': {'kind': '할일'}}, 'text': '2027년 2월 졸업예정자는 해당없음. 대학원생 대상 안내', 'att': []}
    ok('제외 문장 근거의 신분 불충족 → 확인 필요', nf.judge_rules(neg, {'조건': [{'축': '신분', '값': ['졸업예정'], '근거': '2027년 2월 졸업예정자는 해당없음.'}]}, me)[0] == '확인 필요')
    ok('허용 문장 근거의 신분 불충족 → 비해당 그대로', nf.judge_rules(neg, {'조건': [{'축': '신분', '값': ['대학원'], '근거': '대학원생 대상 안내'}]}, me)[0] == '비해당')

    n = fl.sweep(quiet=True)
    st = json.load(open(os.path.join(T, 'state', 'src-a.json'), encoding='utf-8'))['items']
    ok('sweep: 대기 칸 판정 전 글 → 장부', n == 1 and not st['s1'].get('stage') and st['s1']['verdict'] == '비해당' and st['s1']['why'] == '제목 규칙(신입 채용)' and not os.path.exists(os.path.join(T, 'state', 'stage', 'src-a', 's1.md')))

    r = fl.learn(quiet=True)
    me = nf.card()
    ok('살린 글: 막은 조리법 낱말이 풀린말로', '공모전' in (me.get('풀린말') or []))
    rc2 = json.load(open(rp, encoding='utf-8'))
    got = rc2['filter']['title_skip'].split('|')
    ok('살린 글: 조리법에서 낱말이 빠지고 출처 몫은 남음', '공모전' not in got and '출처몫' in got)
    ok('살린 글: 비슷한 글이 제목 관문 통과', nf.gate(rc2, row('다른 공모전 안내')) is None)
    ok('살린 글: 막은 카드 낱말도 풀림', '공연' in (me.get('풀린말') or []) and nf.gate(rc2, row('봄 공연 안내')) is None)
    ok('되먹임이 조리법에 카드 낱말을 안 넣음', not {'신입사원', '거창군', '공연', '희망재단'} & set(got))
    qt = open(q, encoding='utf-8').read()
    ok('까닭 안 맞음(관정재단): 규칙 안 올리고 대기열', r['까닭 안 맞음'] == 1 and '관정재단' in qt and nf.gate(rc2, row('저소득 장학 안내')) is None)
    ok('까닭 맞음: 사용자 뺌 묶음 → 전 출처 제외어', nf.gate({'id': '다른', 'filter': {'kind': '자격'}}, row('희망재단 장학')) == ('비해당', '제목 규칙(사용자 뺌)'))
    r2 = fl.learn(quiet=True)
    ok('되풀이해도 또 안 함', not any(r2.values()))

    t0 = open(cf, encoding='utf-8').read()
    ok('카드 조건 전: 신입 채용 켜짐', nf.gate(rc2, row('현대 신입사원 모집')) is not None)
    fl.card_set('학년', '4', '시험')
    ok('카드 조건이 깨지면 묶음이 꺼짐(4학년 → 신입 채용 풀림)', nf.gate(rc2, row('현대 신입사원 모집')) is None)
    t1 = open(cf, encoding='utf-8').read()
    ok('카드: JSON 밖 글이 남고 근거 줄이 붙음', '그대로 남아야 함' in t1 and '**[사실] 학년**' in t1 and t1.count('```json') == t0.count('```json'))

    fl.tick(quiet=True)
    me = nf.card()
    ok('다시볼날: 지난 날만 대기열로 · 먼 날은 남음', '시험 사유' in open(q, encoding='utf-8').read() and list(me['다시볼날']) == ['2999-01-01'])

    # 일정 파일 하나를 나눠 쓰기 — 같은 번호의 다른 출처 · 같은 글을 올린 출처 · 포털 18자리 번호
    LONG = '000100000000003857'
    for sid, its in (('src-b', {'7': '가 안내', LONG: '포털 긴 번호 글'}), ('src-c', {'7': '나 안내', '8': '[학부] 가 안내'})):
        json.dump({'id': sid, 'name': sid, 'contract': 'x', 'family': 'regex', 'filter': {'kind': '할일', 'schedule': '묶음.md', 'label': '공지'}},
                  open(os.path.join(T, 'collect', sid + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        json.dump({'items': {k: {'title': t, 'date': '2026-10-10', 'path': f'v/{sid}-{k}.md', 'hash': 'z'} for k, t in its.items()}},
                  open(os.path.join(T, 'state', sid + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        for k, t in its.items():
            open(os.path.join(T, 'v', f'{sid}-{k}.md'), 'w', encoding='utf-8').write(f'# {t}\n\n---\n본문')
            json.dump({'조건': [], '마감': '2999-01-01'}, open(os.path.join(T, 'state', '조건', f'{sid}-{k}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    sf = os.path.join(T, '2_지식', '일정', '묶음.md')
    nf.judge(quiet=True)
    L = [ln for ln in open(sf, encoding='utf-8').read().splitlines() if ln.startswith('- [')]
    ok('나눠 쓰기: 두 출처 줄이 다 뜸(뒤 출처가 안 덮음)', any('나 안내' in x for x in L) and any('포털 긴 번호 글' in x for x in L))
    ok('나눠 쓰기: 같은 글은 한 줄', sum('가 안내' in x for x in L) == 1 and len(L) == 3)
    ok('나눠 쓰기: 짧은 번호는 출처가 붙어 안 겹침 · 긴 번호는 그대로', any(x.endswith('^sch-src-b-7') for x in L) and any(x.endswith('^sch-src-c-7') for x in L) and any(x.endswith(f'^sch-{LONG}') for x in L))
    t = open(sf, encoding='utf-8').read()
    open(sf, 'w', encoding='utf-8', newline='\n').write(''.join((ln.replace('- [ ]', '- [x]', 1) if ln.endswith('^sch-src-b-7') else ln) + '\n' for ln in t.splitlines()))
    nf.judge(quiet=True)
    L = [ln for ln in open(sf, encoding='utf-8').read().splitlines() if ln.startswith('- [')]
    ok('나눠 쓰기: 체크가 남고 같은 번호 다른 출처로 안 번짐', any(x.startswith('- [x]') and x.endswith('^sch-src-b-7') for x in L) and any(x.startswith('- [ ]') and x.endswith('^sch-src-c-7') for x in L))
finally:
    shutil.rmtree(T, ignore_errors=True)

print(f'실패 {len(fails)}')
sys.exit(1 if fails else 0)
