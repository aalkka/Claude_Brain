"""공지 필터 — «나에게 해당되는 공지만» (큰 그림 알림 모듈의 판정 층 v0 · 2026-10-27).

원칙: 해당을 맞히는 게 아니라 «빼도 된다는 근거가 있을 때만 뺀다». 놓침(재현율)이 헛것보다 비싸다.
층  ① 조건 추출 — claude -p(ingest_vision 의 최소 호출 재사용 · 구독만 · 새 공지만 · 캐시). 조건마다 원문 인용 필수.
    ② 근거 검사 — 인용이 원문에 글자 그대로 없으면 그 조건은 «모름»(모델이 지어낸 조건으로 빼지 않게).
    ③ 판정 — 자격 카드([[자격-카드]] 의 JSON — 자리는 `roles.find_note`)와 결정적으로 대조 → 해당 / 확인 필요 / 비해당.
       비해당 = 근거 있는 불충족이 하나라도 · 확인 필요 = 불충족 없음 + 모름 있음(또는 조건이 첨부·그림에만) · 해당 = 그 밖.
출력 2_지식/일정/<조리법 filter.schedule>(생성 파일 · 해당·확인 필요만 · 체크 보존 · 같은 이름을 쓰는 출처끼리 한 파일) · 판정표 3_시스템/_index/collect/판정.md(근거 한 줄씩).
저장 전 거르기(10-29 · 수집은 선별): 엔진(web-collect)이 글을 받기 전에 gate()(제목만 · LLM 0)를 묻고, 받은 글은 대기 칸
    (_index/collect/stage — 볼트 지식층 밖)에 둔다. 판정이 나면 엔진 settle 이 verdicts()를 물어 KEEP(해당·확인 필요·관심)만
    볼트로 들이고, 비해당은 대기 칸에 둔 채 장부 한 줄(카드가 바뀌면 다시 판정) · 지남은 지운다. 추출은 본문만 먼저(첨부는 들인 뒤).
꽁돈(11-10 · 황금 태그): 조리법 filter.gold 가 켠 글은 추출 때 지급 형태·선정 뒤 의무·소득 심사도 뽑는다(같은 호출).
    판정이 해당·확인 필요이고 카드 «꽁돈» 칸(현금·막는 의무·소득 심사)을 넘으면 일정 줄에 #꽁돈 · 판정표에 «꽁돈» · 수집 창 한 줄 맨 앞에 «꽁돈».

  py -3.11 3_시스템/notice-filter.py extract [--max N] [--again 글번호...]   # 추출 안 된 공지만 claude -p(--again = 첨부 색인을 고친 글도 다시) — 사용량이 든다(누를 때만) · 끝나면 settle
  py -3.11 3_시스템/notice-filter.py judge                # 캐시로 판정·출력만(사용량 0)
"""
import argparse
import concurrent.futures as cf
import glob
import json
import os
import re
import shutil
import sys
import time
from datetime import date, datetime

SYS = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(SYS)
sys.path.insert(0, SYS)
import roles  # noqa: E402 — 노트는 이름으로 찾는다(볼트 개혁 R6 · 옮겨도 따라감)
CARD = os.path.join(VAULT, *(roles.find_note('자격-카드') or roles.path('notes', '자격-카드.md')).split('/'))
RECIPES = os.path.join(SYS, 'collect')          # 거를 출처 = 조리법에 "filter" 가 있는 것(출처 이름을 코드에 두지 않는다)
STATE = os.path.join(SYS, '_index', 'collect')
CACHE = os.path.join(SYS, '_index', 'collect', '조건')
REPORT = os.path.join(SYS, '_index', 'collect', '판정.md')
STAGE = os.path.join(STATE, 'stage')                 # 엔진 대기 칸 — <출처id>/<글번호>.md (web-collect 의 STAGE 와 같은 곳)
KEEP = ('해당', '확인 필요', '관심')                    # 볼트에 들이는 판정. 나머지(비해당·지남)는 장부 한 줄
ARCH = os.path.join(STATE, 'archive')                # 보관 칸 — 볼트에 들였다가 빼낸 글(첨부째 · 볼트와 같은 상대 경로 · 자동으로 지우지 않음)
MARKS = os.path.join(STATE, '평가.json')              # 사용자 표시(헛것·쓸모)와 놓침 기록 — 성과 칸의 정답
QUEUE = os.path.join(SYS, '_index', '수집-대기열.md')
LMS_SID = 'lms-post'
LMS_PENDING = os.path.join(SYS, '_index', 'lms', '마감-대기.json')
STATUS = os.path.join(STATE, '.status.txt')          # 세션 시작이 읽는 한 줄(생산자 = judge · 소비자 = 훅 — 1.5절과 같은 분리)
WD = '월화수목금토일'

AXES = ['신분', '학년', '이수학기', '성적', '이수학점', '소득', '지역', '전공', '특수', '국적', '병역', '봉사', '대외활동', '근로', '성별', '할일', '기타']
SYSTEM = """너는 대학 공지에서 «누가 해당하는가(자격·대상 조건)»만 뽑는 추출기다. 판단하지 말고 원문에 적힌 조건만 옮긴다.
JSON 하나만 출력한다(앞뒤 글 없음):
{"조건":[{"축":"<축>","값":<기계값>,"근거":"<원문에서 글자 그대로 복사한 구절 10~80자>"}],
 "마감":"YYYY-MM-DD 또는 null","금액":"짧게 또는 null","첨부에만":true|false,"요약":"무엇에 대한 공지인지 명사구 15자 이내"}
축과 기계값:
- 신분: ["학부","대학원","재학","휴학","신입생","졸업예정"] 중 허용 목록
- 학년: 허용 학년 정수 목록 예 [2,3]
- 이수학기: {"이상":n} 또는 {"이하":n}
- 성적: {"평점이상":3.0} (4.5 만점 기준이 아니면 {"평점이상":x,"만점":4.3})
- 이수학점: {"이상":12}
- 소득: {"구간이하":8} 또는 {"기초차상위":true} 또는 {"가계곤란":true}
- 지역: {"지역":["거창군"],"기준":"본인|부모|출신고교|아무나"}
- 전공: {"허용":["이공계"]} 또는 {"제외":["의학"]}
- 특수: {"필요":["북한이탈주민"]} (다자녀·보훈·장애·한부모·선원가족·농업인 자녀 등 특정 집단)
- 국적: {"허용":["대한민국"]} 또는 {"허용":["외국인"]}
- 병역, 봉사, 대외활동, 근로: {"필요":true} 또는 짧은 설명
- 성별: {"허용":["여"]}
- 할일: 학사 공지에서 «이 공지가 요구하는 행동의 대상» 예 {"대상":"다중전공 이수자"}
- 기타: 위에 없는 조건 짧은 설명
규칙: 근거는 반드시 원문 그대로(띄어쓰기 포함, 고치지 말 것). 조건이 «첨부 참조»·그림에만 있다고 보이면 "첨부에만":true.
조건이 없으면 "조건":[]. 마감은 이 공지의 신청·접수 마감(학교 기한이 따로 있으면 학교 기한)."""
# 꽁돈 칸(11-10) — 조리법 filter.gold 가 켠 글에만 덧붙인다(true = 모든 글 · 글자 = 제목이 맞는 글). 자격 판정과 따로 «받으면 통장으로 현금이 오고
# 무거운 의무가 없는가»를 본다. 근거는 조건과 같이 원문 그대로 — 원문에 없으면 그 칸은 모름.
GOLD = """
이 공지가 장학금·지원금 모집이면 JSON 에 세 칸을 더한다(아니면 "지급":null,"의무":[],"소득심사":null):
 "지급":{"형태":"현금|등록금|혼합|모름","근거":"<원문 그대로 10~80자>"}
   현금 = 학생 본인에게 돈을 준다(계좌 입금·생활비·생활지원금·학업보조금·학업장려금·연구지원금 등) · 등록금 = 등록금·수업료로만 준다(감면·대납)
   혼합 = 둘 다 · 원문에서 알 수 없으면 모름
 "의무":[{"종류":"보고서|활동|근로봉사|사용계획|행사|성적유지|기타","근거":"<원문 그대로>"}]
   선정된 뒤 해야 하는 일만(연구·결과 보고서 제출 · 정기 활동·멘토링 · 근로·봉사 시간 · 사용계획서·영수증 · 행사 참석 · 성적 유지). 지원할 때 내는 서류는 의무가 아니다.
 "소득심사":{"반영":true,"근거":"<원문 그대로>"} — 자격 조건은 아니지만 심사에서 소득·가계 형편을 본다는 문장이 있을 때만. 없으면 null."""
GOLD_DEFAULT = {'지급': ['현금', '혼합'], '막는 의무': ['보고서', '활동', '근로봉사', '사용계획'], '소득심사 막음': True}   # 카드 «꽁돈» 칸이 덮어쓴다

SEOUL_GU = '종로 중 용산 성동 광진 동대문 중랑 성북 강북 도봉 노원 은평 서대문 마포 양천 강서 구로 금천 영등포 동작 관악 서초 강남 송파 강동'.split()
FIELD_OK = r'이공|자연과학|이학|이과|물리|기초과학|과학기술|STEM|자연계'
FIELD_NO = r'의생명|의학|의과|치의|한의|약학|간호|보건|농업|농촌|농학|수산|인문|사회과학|예체능|예술|체육|경영|법학|교육|신학|사범'


_card = []


def card():
    if not _card:
        t = open(CARD, encoding='utf-8').read()
        _card.append(json.loads(re.search(r'```json\s*(\{.*?\})\s*```', t, re.S).group(1)))
    return _card[0]


def recipes():
    for rp in sorted(glob.glob(os.path.join(RECIPES, '*.json'))):
        rc = json.load(open(rp, encoding='utf-8'))
        if rc.get('filter'):
            yield rc


def state_items(rc):
    sp = os.path.join(STATE, rc['id'] + '.json')
    return json.load(open(sp, encoding='utf-8'))['items'] if os.path.exists(sp) else {}


def notices(sid=None):
    """엔진 상태에서 — 볼트 글(path) · 보관 칸 글(archived) · 대기 칸 글(stage). 주소 꼴을 읽지 않으니 어떤 가족·출처든 같다.
    제목만으로 걸러진 글(본문을 받지 않음)은 여기 없다 → judge 가 상태의 장부 줄로 따로 적는다."""
    for rc in recipes():
        if sid and rc['id'] != sid:
            continue
        for aid, it in state_items(rc).items():
            if it.get('path'):
                where, f = '볼트', os.path.join(VAULT, it['path'])
            elif it.get('archived'):
                where, f = '보관 칸', os.path.join(ARCH, it['archived'])
            elif it.get('stage'):
                where, f = '대기 칸', os.path.join(STAGE, rc['id'], aid + '.md')
            else:
                continue
            if not os.path.exists(f):
                continue
            t = open(f, encoding='utf-8').read()
            body = t.split('\n---', 1)[1] if '\n---' in t else t
            yield {'sid': rc['id'], 'rc': rc, 'id': aid, 'path': f, 'text': body, 'where': where, 'staged': where != '볼트',
                   'att': [] if where == '대기 칸' else attached_text(f, ARCH if where == '보관 칸' else VAULT),
                   'url': it.get('url') or (re.search(r'^url: "([^"]+)"', t, re.M) or [None, ''])[1],
                   'title': re.search(r'^# (.*)$', t, re.M).group(1), 'date': it.get('date') or '', 'again': bool(it.get('reextract'))}   # again = 글이 수정돼 새 판을 받음(web-collect revise) — 다시 뽑을 때까지 옛 캐시로 판정
    if not sid or sid == LMS_SID:        # LMS 글 — 날짜는 있는데 마감인지 불명확한 글(schedule.py 가 적는다). 같은 단추가 뽑고, 결과는 schedule.py 가 일정 줄로 쓴다
        for pid, it in (json.load(open(LMS_PENDING, encoding='utf-8')) if os.path.exists(LMS_PENDING) else {}).items():
            f = os.path.join(VAULT, it['path'])
            if os.path.exists(f):
                t = open(f, encoding='utf-8').read()
                yield {'sid': LMS_SID, 'rc': {'id': LMS_SID, 'name': 'LMS 글', 'filter': {}}, 'id': pid, 'path': f, 'text': t.split('\n---', 1)[1] if '\n---' in t else t,
                       'where': '대기 칸', 'staged': False, 'att': [], 'url': '', 'title': it['title'], 'date': it['date'],
                       'hint': '이 글은 강의 게시판·공지 글이다. «마감»은 과제·제출·신청처럼 학생이 해야 할 일의 마감이다. 수업·시험 날짜는 마감이 아니다.\n'}


def attached_text(post_md, root=VAULT, per=3500, total=9000):
    """엔진 규칙(출처 무관): 글 md 와 같은 이름 폴더의 첨부·그림 → <root>/1_수집/_색인 의 글자(OCR 포함). [(파일 이름, 글자)].
    root = 볼트 또는 보관 칸(볼트와 같은 상대 경로로 색인째 옮겨 둔다)."""
    d = os.path.splitext(post_md)[0]
    out, used = [], 0
    if not os.path.isdir(d):
        return out
    src_root = os.path.join(root, '1_수집')
    for fp in sorted(os.path.join(d, x) for x in os.listdir(d)):   # glob 금지 — 폴더 이름의 [교외-11_2] 를 글자 묶음으로 읽는다
        ip = os.path.join(src_root, '_색인', os.path.relpath(fp, src_root)) + '.색인.md'
        if not os.path.exists(ip):
            continue
        t = open(ip, encoding='utf-8').read()
        t = t.split('\n---', 1)[1] if t.startswith('---') and '\n---' in t else t
        if '추출 실패' in t[:400]:
            continue
        t = re.sub(r'\n{3,}', '\n\n', t).strip()[:per]
        if used + len(t) > total:
            t = t[:max(0, total - used)]
        if t:
            out.append((os.path.basename(fp), t))
            used += len(t)
        if used >= total:
            break
    return out


def cpath(n):
    return os.path.join(CACHE, f'{n["sid"]}-{n["id"]}.json')


def norm(s):
    return re.sub(r'\s+', '', s or '')


# ───────── ① 추출 ─────────
def parse_json(out):
    m = re.search(r'\{.*\}', out or '', re.S)
    if not m:
        return None
    s = m.group(0)
    for t in (s, re.sub(r'",\s*"\s*\}(?::null\})?', '"}', s)):   # 흔한 깨짐: 문자열 끝에 «","}» 가 붙음
        try:
            return json.loads(t)
        except ValueError:
            continue
    return None


def extract_one(n):
    import ingest_vision as iv
    text = n['text']
    if len(text) > 9000:
        text = text[:9000] + '\n…(이하 생략)'
    att = ''.join(f'\n\n=== 첨부: {name} (색인 글자 · OCR 일 수 있음) ===\n{t}' for name, t in n['att'])
    content = [{'type': 'text', 'text': f'{n.get("hint", "")}제목: {n["title"]}\n등록일자: {n["date"]}\n\n{text}{att}'}]
    d, tot = None, {'in': 0, 'out': 0, 'cost': 0.0}
    system = SYSTEM + (GOLD if gold_on(n) else '')
    for attempt in range(2):            # JSON 이 깨지면 한 번 더 묻는다(10-27: 36건 중 4건 «"근거":"…","}» 꼴)
        out, usage, err = iv._run(content, system=system)
        tot['in'] += usage.get('in', 0)
        tot['out'] += usage.get('out', 0)
        tot['cost'] += usage.get('cost') or 0.0
        for k, val in (usage.get('parts') or {}).items():
            tot[k] = tot.get(k, 0) + val
        if usage.get('rate_limit'):
            tot['rate_limit'] = usage['rate_limit']
        if err:
            return None, tot, err
        d = parse_json(out)
        if isinstance(d, dict):
            break
    usage = tot
    if not isinstance(d, dict):
        return None, usage, 'JSON 아님(2회): ' + out[:120]
    d['_at'] = time.strftime('%Y-%m-%d %H:%M:%S')
    d['_model'] = iv.MODEL
    d['_tokens'] = usage
    d['_att'] = [name for name, _ in n['att']]
    return d, usage, ''


def clear_again(n):
    """다시 뽑았으니 «수정돼 다시 뽑을 것» 표시를 끈다(엔진 상태 한 칸 — reject 처럼 상태 파일을 직접 고친다)."""
    sp = os.path.join(STATE, n['sid'] + '.json')
    try:
        st = json.load(open(sp, encoding='utf-8'))
        if st['items'][n['id']].pop('reextract', None):
            with open(sp + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
                json.dump(st, f, ensure_ascii=False, indent=1)
            os.replace(sp + '.tmp', sp)
    except (OSError, ValueError, KeyError):
        pass


def stale(n):
    """다시 뽑을 공지 — 첨부 글자가 생겼는데 캐시가 첨부 없이 뽑혔고(첨부에만·확인 필요) 마감이 안 지난 것."""
    if not os.path.exists(cpath(n)):
        return True
    d = json.load(open(cpath(n), encoding='utf-8'))
    if not n['att'] or set(d.get('_att') or []) >= {a for a, _ in n['att']}:
        return False
    dl = deadline(n, d)
    return bool(d.get('첨부에만') or not d.get('조건')) and (dl is None or dl >= date.today().isoformat())


def extract(maxn, refresh=False, workers=1, sid=None, settle=True, stop_on_warning=False, again=()):
    """추출 안 된 공지만 claude -p → 캐시. settle=True 면 끝에 엔진 settle 을 실행시킨다(엔진이 부를 때는 False).
    stop_on_warning = 사용량 경고(한도 가까움)가 뜨면 거기서 멈춘다 — 자동 추출(조리법 filter.auto)용.
    again = 캐시가 있어도 다시 뽑을 글번호(첨부 색인을 고친 공고 — 사람이 짚을 때만). 돌려줌 = 합계 dict."""
    import ingest_vision as iv
    cb = getattr(iv, 'claude_bin', None)            # 리허설 대역(flow_rehearsal_check)엔 없다
    why = iv.subscription()
    if why:
        kind = cb.LAST.get('kind') if cb else ''
        if kind in (cb.LAPSED, cb.LOGIN) if cb else False:     # 구독 해지·로그인 끊김(11-11) — 윈도 알림은 끊김마다 한 번 · 자동은 대기열에도 안 적는다(폰에 되풀이 안 뜨게)
            cb.alert()
            if stop_on_warning:
                print(f'멈춤({kind}): {why} — 구독이 필요한 자동 추출은 쉰다')
                return {'in': 0, 'out': 0, 'ok': 0, 'err': 0, 'cost': 0.0, 'stopped': kind}
        sys.exit(f'멈춤: {why} — 구독이 아니면 부르지 않는다')
    today = date.today().isoformat()
    todo = [n for n in notices(sid) if (n['id'] in again or n.get('again') or (stale(n) if refresh else not os.path.exists(cpath(n))))
            and not ((deadline(n, {}) or '9999') < today)][:maxn]       # 마감이 지난 글은 뽑지 않는다(판정해도 «지남»)
    # 프롬프트 캐시는 끈 채 — 10-29 실측: 켜면 공지 본문까지 캐시 쓰기(2배)로 첫 호출 $0.0096 → $0.0163. 공지마다 본문이 달라
    # 다시 읽히는 몫(시스템 지시문)이 작아 손해다. 같은 글을 되풀이할 때만 이득(2회째 $0.0057).
    print(f'추출할 공지 {len(todo)}')
    os.makedirs(CACHE, exist_ok=True)
    tot = {'in': 0, 'out': 0, 'ok': 0, 'err': 0, 'cost': 0.0}

    def one(n):
        r = extract_one(n)
        if r[2] and re.search(r'OAuth|refresh', r[2]):       # 동시 호출이 토큰 갱신에서 부딪힘(10-27 9건 전부) — 잠깐 쉬고 한 번 더
            time.sleep(20)                                   # 10-29: 5초 뒤 재시도도 실패, 수십 초 뒤엔 성공(갱신 잠금이 풀리는 시간)
            r = extract_one(n)
        return r
    ex = cf.ThreadPoolExecutor(workers) if workers > 1 else None
    try:                                # 하나씩(기본)이면 사용량 경고에 바로 멈출 수 있다
        for n, (d, usage, err) in (zip(todo, ex.map(one, todo)) if ex else ((n, one(n)) for n in todo)):
            tot['in'] += usage.get('in', 0)
            tot['out'] += usage.get('out', 0)
            tot['cost'] += usage.get('cost') or 0.0
            if err:
                tot['err'] += 1
                print(f'  ✗ {n["title"][:40]} — {err[:120]}')
            else:
                with open(cpath(n), 'w', encoding='utf-8', newline='\n') as f:
                    json.dump(d, f, ensure_ascii=False, indent=1)
                tot['ok'] += 1
                if n.get('again'):
                    clear_again(n)
            if usage.get('rate_limit'):
                print('  ⚠ 사용률:', usage['rate_limit'])
                if stop_on_warning:
                    tot['warning'] = usage['rate_limit']
                    break
    except iv.Stop as e:
        print(f'멈춤({e.kind}): {e.why} — 남은 공지는 다음에')
        if cb and e.kind in (cb.LAPSED, cb.LOGIN):   # 호출 중에 끊김을 앎 — 알림 한 번 · 사용량 경고 줄은 안 남긴다
            cb.alert()
            tot['stopped'] = e.kind
        else:
            tot['warning'] = f'{e.kind}: {e.why}'
    finally:
        if ex:
            ex.shutdown(cancel_futures=True)
    print(f'추출 끝 — 성공 {tot["ok"]} · 실패 {tot["err"]} · 토큰 입력 {tot["in"]:,} · 출력 {tot["out"]:,} · 환산 ${tot["cost"]:.3f}')
    if tot['ok'] and settle:            # 판정이 난 대기 글을 볼트로 들이거나 장부로 — 엔진 몫(이 파일은 엔진을 부르지 않고 실행만 시킨다)
        import subprocess
        py = ['py', '-3'] if shutil.which('py') else [sys.executable]
        p = subprocess.run(py + [os.path.join(SYS, 'web-collect.py'), '--settle'], cwd=VAULT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        print((p.stdout or '').strip()[-600:] or f'settle rc={p.returncode} {(p.stderr or "")[-300:]}')
        if any(n['sid'] == LMS_SID for n in todo):   # LMS 글 결과는 일정 생성기가 줄로 쓴다
            subprocess.run(py + [os.path.join(SYS, 'schedule.py'), 'build'], cwd=VAULT, capture_output=True)
    return tot


# ───────── ③ 판정 ─────────
def low_bound(s):
    m = re.search(r'(\d+(?:\.\d+)?)', str(s or ''))
    return float(m.group(1)) if m else None


def check(c, me):
    """조건 하나 → ('충족'|'불충족'|'모름', 까닭)."""
    ax, v = c.get('축'), c.get('값')
    v = v if isinstance(v, dict) else ({'목록': v} if isinstance(v, list) else {'설명': v})
    if ax == '신분':
        allow = v.get('목록') or []
        if not allow:
            return '모름', '신분 값 없음'
        mine = {'학부', '재학'}
        if mine & set(allow):
            return '충족', '학부 재학'
        return '불충족', f'대상 {allow}'
    if ax == '학년':
        allow = [int(x) for x in (v.get('목록') or []) if str(x).isdigit()]
        if not allow:
            return '모름', '학년 값 없음'
        if me['학년'] in allow:
            return '충족', f'{me["학년"]}학년'
        nxt = next_grade(me)
        if FUTURE.search(c.get('근거') or '') and nxt in allow:
            return '충족', f'다음 학기 {nxt}학년'
        return '불충족', f'대상 {allow}학년 · 나 {me["학년"]}학년'
    if ax == '성적':
        whole = re.search(r'전체|누적|전 ?학기|총', c.get('근거') or '')     # «전체학기 85점» 을 직전 학기로 대신하지 않는다(10-27)
        need = v.get('평점이상')
        mine = low_bound(me.get('누적평점') if whole else (me.get('직전학기') or {}).get('평점'))
        if need is None or mine is None:
            return '모름', ('누적 평점 모름' if whole else '평점 기준·내 평점 모름')
        full = float(v.get('만점') or 4.5)
        mine_s = 50 + mine * 10 if full == 100 else mine / 4.5 * full      # 4.5 → 100: A+ 4.5=95 · A 4.0=90 · B+ 3.5=85(등급 하한)
        return ('충족', f'{"누적 " if whole else ""}{mine} 이상(≈{mine_s:g}) ≥ {need}') if mine_s >= float(need) else ('모름', f'기준 {need} · 내 하한 {mine}')
    if ax == '소득':
        mine = me.get('소득구간') or ''
        if not mine:
            return '모름', '소득구간 모름'
        lo = low_bound(mine)
        if v.get('기초차상위') or v.get('가계곤란'):
            return ('불충족', f'저소득 대상 · 나 {mine}') if lo and lo >= 4 else ('모름', mine)
        k = v.get('구간이하')
        if k is not None and lo is not None:
            return ('불충족', f'{k}구간 이하 대상 · 나 {mine}') if lo > float(k) else ('충족', mine)
        return '모름', '소득 기준 해석 못 함'
    if ax == '지역':
        regs = [str(r) for r in (v.get('지역') or [])]
        if not regs:
            return '모름', '지역 값 없음'
        where = me.get('지역') or {}
        if not any(where.get(k) for k in ('본인', '부모', '출신고교')):
            return '모름', '내 지역 모름'
        seoul = all(where.get(k) == '서울' for k in ('본인', '부모', '출신고교'))
        for r in regs:
            if '서울' in r:
                return '충족', '서울'
            if any(r.startswith(g) for g in SEOUL_GU):
                return '모름', f'{r}(서울 구 — 내 구 모름)'
        return ('불충족', f'지역 {regs} · 나 전부 서울') if seoul else ('모름', f'지역 {regs}')
    if ax == '전공':
        allow, deny = ' '.join(map(str, v.get('허용') or [])), ' '.join(map(str, v.get('제외') or []))
        mine = f'{me.get("단과대", "")} {me.get("학과", "")}'
        if allow:
            if re.search(r'불문|제한 ?없', allow):
                return '충족', '전공 불문'
            if re.search(FIELD_OK, allow):
                return '충족', f'{allow} ∋ 물리'
            if re.search(FIELD_NO, allow) and not re.search(FIELD_OK, allow):
                return '불충족', f'분야 {allow} · 나 {mine}'
            return '모름', f'분야 {allow}'
        if deny:
            return ('불충족', f'제외 {deny}') if re.search(r'물리|이과|이학|자연', deny) else ('충족', f'제외 {deny} 아님')
        return '모름', '전공 값 없음'
    if ax == '특수':
        need = v.get('필요') or v.get('목록') or v.get('설명')
        if not need:
            return '모름', '특수 값 없음'
        return ('불충족', f'대상 {need} · 나 해당 없음') if me.get('특수') == [] else ('모름', str(need))
    if ax == '국적':
        allow = ' '.join(map(str, v.get('허용') or v.get('목록') or []))
        if '대한민국' in allow or '내국' in allow or '한국' in allow:
            return '충족', '대한민국'
        if '외국' in allow:
            return '불충족', '외국인 대상'
        return '모름', allow or '국적 값 없음'
    if ax == '병역':
        return ('충족', '병역 마침') if me.get('병역') == '마침' else ('모름', '병역')
    if ax == '할일':
        tgt = str(v.get('대상') or v.get('설명') or '')
        hs = me.get('학사') or {}
        for k, val in hs.items():
            if k in tgt:
                return ('불충족', f'{k}: {val}') if val in ('없음', '마침', '완료', '해당 없음') else ('충족', f'{k}: {val}')
        return '모름', tgt or '할일 대상'
    if ax == '이수학기':
        done = finished(me)
        if v.get('이하') is not None and done is not None:      # «3학년 1학기(5학기) 등록 예정» 을 {"이하": 4} 로 뽑은 꼴(11-05 장학 공지) — 예정 근거면 지금 학기까지 끝낸 것으로 센다
            now = done + 1 if FUTURE.search(c.get('근거') or '') else done
            return ('충족', f'{now}학기 이수 ≤ {v["이하"]}') if now <= int(v['이하']) else ('불충족', f'{v["이하"]}학기 이하 · 나 {now}학기')
        need = v.get('이상')
        if done is None or need is None:
            return '모름', f'이수학기 {json.dumps(v, ensure_ascii=False)}'
        need = int(need)
        if need <= done:
            return '충족', f'{done}학기 이수 ≥ {need}'
        if FUTURE.search(c.get('근거') or '') and need <= done + 2:     # 끝낸 학기 + 지금 학기 + 다음 학기
            return '충족', f'다음 학기가 {done + 2}학기째'
        if need == done + 1:
            return '모름', f'{need}학기 이수 — 지금 학기 포함 여부 모름(끝낸 {done})'
        return '불충족', f'{need}학기 이상 · 나 {done}학기 이수'
    if ax == '이수학점':
        need = v.get('이상')
        if re.search(r'매 ?(?:정규)?학기|모든 학기|각 학기', c.get('근거') or ''):
            every = me.get('매학기12학점이상')
            if every is None or need is None or float(need) > 12:
                return '모름', '매 학기 이수학점 모름'
            return ('충족', '매 학기 12학점 이상') if every else ('불충족', '12학점 미만 학기 있음')
        if re.search(r'총\s*\d|누적', c.get('근거') or ''):     # 누적 조건을 직전 학기 값과 견주지 않는다(10-29 «총 102학점» vs 직전 12 오판)
            mine, done = me.get('누적이수학점'), finished(me)
            if need is not None and mine is not None:
                return ('충족', f'누적 {mine} ≥ {need}') if float(mine) >= float(need) else ('불충족', f'총 {need}학점 이상 · 나 누적 {mine}')
            if need is not None and done is not None and float(need) > done * MAX_CREDITS:
                return '불충족', f'총 {need}학점 이상 · 나 최대 {done * MAX_CREDITS}({done}학기 · 학기당 {MAX_CREDITS} 상한)'
            return '모름', '누적 이수학점 모름'
        mine = (me.get('직전학기') or {}).get('이수학점')
        if need is None or mine is None:
            return '모름', '직전 학기 이수학점 모름'
        return ('충족', f'{mine} ≥ {need}') if float(mine) >= float(need) else ('불충족', f'{need}학점 이상 · 나 {mine}')
    if ax == '근로':
        w = me.get('근로의향')
        return ('모름', '근로 의향 모름') if w is None else (('충족', '근로 의향 있음') if w else ('불충족', '국가근로 안 함'))
    if ax == '기타':
        return other(str(c.get('값') or ''), me)
    # 이수학기·봉사·대외활동·성별 — 카드 값이 있으면 쓰고 없으면 모름
    key = {'봉사': '봉사', '대외활동': '대외활동', '성별': '성별'}.get(ax)
    if key and me.get(key) is not None:
        return '모름', f'{ax}: {me[key]}'
    return '모름', f'{ax}: {json.dumps(c.get("값"), ensure_ascii=False)[:40]}'


def yes(x):
    return x in (True, '예', '있음', '함', '마침', '완료')


def other(t, me):
    """«기타» 자유 서술 조건 — 자주 나오는 꼴만 결정적으로. 나머지는 모름(10-27 장학 30건에서 뽑은 꼴)."""
    if re.search(r'서울캠퍼스|안암', t):
        return ('충족', '서울캠퍼스') if me.get('캠퍼스') == '서울' else ('모름', '캠퍼스')
    if re.search(r'국가장학금.{0,12}신청', t):
        v = me.get('국가장학금신청')
        return ('모름', '국가장학금 신청 여부 모름') if v is None else (('충족', '국가장학금 신청함') if yes(v) else ('불충족', '국가장학금 미신청'))
    if re.search(r'형제|자매', t):
        v = me.get('형제자매재학')
        return ('모름', '형제·자매 동시 재학 모름') if v is None else (('충족', '형제·자매 재학') if yes(v) else ('불충족', '형제·자매 동시 재학 아님'))
    if re.search(r'징계', t):
        v = me.get('징계')
        return ('모름', '징계 이력 모름') if v is None else (('충족', '징계 없음') if v == '없음' else ('불충족', '징계 있음'))
    if re.search(r'9학기|초과학기|부분 ?등록', t):
        n = re.search(r'(\d)학년 (\d)학기', me.get('학기') or '')
        return ('충족', '9학기 미만 · 정상 등록') if n else ('모름', '학기 수')
    if re.search(r'전공 ?미배정|제1전공 배정', t):
        return ('충족', f'제1전공 {me.get("학과")}') if me.get('학과') else ('모름', '전공 배정')
    if re.search(r'(?:대한민국|국내|한국).{0,6}(?:고등학교|고교).{0,4}졸업', t):     # 11-05 장학 공지 — 카드의 출신고교는 국내 지역이다
        school = (me.get('지역') or {}).get('출신고교')
        return ('충족', f'출신고교 {school}') if school else ('모름', '출신고교 모름')
    if re.search(r'외국대학 수학|교환학생으로 수학|국제교류 프로그램', t):
        return '충족', '본교 재학 중(교환 아님)'
    if re.search(r'편입생?.{0,8}(?:제외|불가|제한)', t):
        if len(t) > 14:      # «신·편입생 제외, 잔여 정규학기 1개…» 같은 복합 조건은 한 조각만 풀어 충족으로 치지 않는다
            return '모름', f'복합 조건: {t[:40]}'
        v = me.get('편입생')
        return ('모름', '편입 여부 모름') if v is None else (('불충족', '편입생') if yes(v) else ('충족', '편입생 아님'))
    if re.search(r'휴학 ?계획', t):
        key = next((k for k in me if k.startswith('휴학계획')), None)
        v = me.get(key) if key else None
        return ('모름', '휴학 계획 모름') if v is None else (('불충족', '휴학 계획 있음') if yes(v) else ('충족', '휴학 계획 없음'))
    m = re.search(r'(\d{4})년 ?(\d{1,2})월 ?(\d{1,2})일 이후 출생', t)
    if m or re.search(r'만 ?\d+세 이하', t):
        born = str(me.get('출생') or '')
        bm = re.match(r'(\d{4})(?:-(\d{2})-(\d{2}))?$', born)      # «2004» 처럼 해만 알아도 연도가 갈리면 판정한다
        if not bm:
            return '모름', '출생일 모름'
        if m:
            if bm[2] is None:
                if int(bm[1]) != int(m[1]):
                    ok = int(bm[1]) > int(m[1])
                else:
                    return '모름', f'출생 {born}년 — 월·일 모름'
            else:
                ok = tuple(map(int, bm.groups())) >= tuple(map(int, m.groups()))
            if ok:
                return '충족', f'{born} ≥ {m[1]}-{int(m[2]):02d}-{int(m[3]):02d} 출생'
            if re.search(r'군필|군복무', t) and me.get('병역') == '마침':
                return '모름', '군복무 기간 제외 계산 필요'
            return '불충족', f'{m[1]}년 {m[2]}월 {m[3]}일 이후 출생 대상 · 나 {born}'
        return '모름', '만 나이 기준 해석 못 함'
    if re.search(r'중복.{0,6}(?:수혜|지원).{0,4}(?:불가|제한)|타 ?(?:재단|장학금).{0,16}중복', t):
        if re.search(r'신청자|신청 ?불가', t):   # «X 신청자 신청 불가» 는 받는 것이 아니라 신청이 기준이라 카드로 못 푼다
            return '모름', f'기타: {t[:50]}'
        v = me.get('장학수혜')
        return ('충족', '지금 받는 장학 없음(중복 수혜 조건)') if v in ([], '없음') else ('모름', '받는 장학 모름')
    if re.search(r'계속 ?장학생.{0,30}제외', t):
        v = me.get('장학수혜')
        return ('충족', '계속 장학생 아님') if v in ([], '없음') else ('모름', '계속 장학 수혜 모름')
    if re.search(r'기수혜|선발 완료된 장학금의 포기', t):
        return ('불충족', '받은 장학금 없음(포기 대상 아님)') if me.get('장학수혜') in ([], '없음') else ('모름', '이번 학기 장학 수혜 모름')
    return '모름', f'기타: {t[:50]}'


MAX_CREDITS = 30        # 학기당 이수학점 상한(정규 24 + 계절 6) — 누적 조건은 이것으로도 못 닿을 때만 뺀다


# «3학년 1학기에 등록 예정인 자» = 다음 학기 기준 조건 — 지금 학년과 견주면 자격 있는 글을 뺀다(11-04 장학 공지 · 사용자가 살려서 드러남)
FUTURE = re.compile(r'예정|진학')


def next_grade(me):
    """다음 학기의 학년 — 지금이 2학기면 한 학년 위. 모르면 None."""
    m = re.search(r'(\d)학년\s*(\d)학기', str(me.get('학기') or ''))
    return int(m[1]) + (1 if m[2] == '2' else 0) if m else None


def finished(me):
    """끝낸 학기 수(지금 학기 빼고) — 카드 «학기» «2학년 2학기» 꼴에서. 모르면 None."""
    m = re.search(r'(\d)학년 (\d)학기', me.get('학기') or '')
    return (int(m.group(1)) - 1) * 2 + int(m.group(2)) - 1 if m else None


def interest(text, me):
    """카드 «관심» — 자격이 없어도 알고 싶은 주제. 걸리면 비해당도 «관심»으로 남긴다(10-29: 학사 정답 «관련» 복수전공을 자격으로 뺀 놓침)."""
    return next((k for k in me.get('관심') or [] if k and k in (text or '')), None)


def cond_ok(g, me):
    """제목 규칙 묶음의 카드 조건 — 조건이 없으면 늘 켜짐. 카드 칸이 비면(모름) 빼는 근거가 없으니 끈다."""
    k = g.get('칸')
    if not k:
        return True
    v = me.get(k)
    if v is None:
        return False
    if '같음' in g:
        return v == g['같음']
    if '포함' in g:
        return g['포함'] in (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False))
    if '전부' in g:      # 비어 있는 칸(예 구 모름)은 세지 않는다 — 적힌 값이 전부 그 값이고 하나는 있어야 한다
        vals = [x for x in (v.values() if isinstance(v, dict) else []) if x is not None]
        return bool(vals) and all(x == g['전부'] for x in vals)
    if '미만' in g:
        return isinstance(v, (int, float)) and v < g['미만']
    if '이상' in g:
        return isinstance(v, (int, float)) and v >= g['이상']
    return False


def card_words(me):
    """지금 켜진 카드 «제목규칙» 낱말 [(낱말, 묶음 이름)] — 조건이 깨진 묶음·풀린말은 뺀다. 출처 공통 규칙은 조리법에 복사하지 않고 여기서 바로 읽는다."""
    pulled = set(me.get('풀린말') or [])
    return [(w, g.get('이름') or '이름 없음') for g in me.get('제목규칙') or [] if cond_ok(g, me) for w in g.get('말') or [] if w not in pulled]


def word_hit(word, title):
    try:
        return bool(re.search(word, title or ''))
    except re.error:        # 카드 낱말을 손으로 잘못 적어도 수집을 세우지 않는다 — 빼는 근거가 없으니 안 뺀다
        return False


def card_rule(title, me):
    """제목이 카드 규칙에 걸리면 묶음 이름, 아니면 None. 관심 주제는 안 뺀다."""
    if interest(title, me):
        return None
    return next((name for w, name in card_words(me) if word_hit(w, title)), None)


def title_deadline(rc, title, posted):
    """조리법 filter.title_deadline(월·일 두 묶음 정규식) = 제목에 박힌 마감 · filter.title_closed = 이미 마감 표시(→ '0000-00-00').
    출처마다 다른 제목 관례는 조리법 데이터로(엔진·필터에 출처 꼴을 두지 않는다)."""
    f = rc.get('filter') or {}
    if f.get('title_closed') and re.search(f['title_closed'], title or ''):
        return '0000-00-00'
    m = re.search(f['title_deadline'], title or '') if f.get('title_deadline') else None
    if not m:
        return None
    y = int((posted or str(date.today().year))[:4])
    mo, da = int(m.group(1)), int(m.group(2))
    if posted and mo < int(posted[5:7]) - 2:
        y += 1
    return f'{y:04d}-{mo:02d}-{da:02d}'


def gate(rc, row):
    """엔진이 글을 받기 전에 묻는다(제목만 · LLM 0 · 요청 0) → (판정, 근거) 또는 None(받아서 판정).
    지남 = 제목 마감이 지났거나 «마감» 표시 · 비해당 = 제목 지역 불충족(관심 주제면 빼지 않는다)."""
    t = row.get('title') or ''
    skip = (rc.get('filter') or {}).get('title_skip')       # 조리법 데이터 — 넓은 게시판에서 제목만으로 빼도 되는 꼴
    if skip and re.search(skip, t) and not interest(t, card()):
        return '비해당', '제목 관심 밖'
    rule = card_rule(t, card()) if rc.get('filter') else None
    if rule:
        return '비해당', f'제목 규칙({rule})'
    dl = title_deadline(rc, t, row.get('date') or '')
    if dl and dl < date.today().isoformat():
        return '지남', '제목 «마감» 표시' if dl == '0000-00-00' else f'제목 마감 {dl}'
    me = card()
    tr = title_region({'title': t}, me)
    if tr and tr[0] == '불충족' and not interest(t, me):
        return '비해당', tr[1]
    return None


TITLE_REGION = re.compile(r'([가-힣]{2,4}(?:시|군|구))(?=\s*(?:대학생|지역|출신|거주)|민)')


def title_region(n, me):
    """제목에 박힌 지역(«안산시 대학생»·«거창군 지역출신»·«은평구민») — 조건이 첨부에만 있어도 결정적으로 뺀다."""
    m = TITLE_REGION.search(n['title'])
    if not m:
        return None
    c = {'축': '지역', '값': {'지역': [m.group(1)]}, '근거': n['title']}
    st, why = check(c, me)
    return (st, why + '(제목)', c)


IMG = ('.jpg', '.jpeg', '.png', '.gif')
NEG = re.compile(r'해당\s*없|해당되지|해당 안|제외|불가|아닌 |아닙니다')


def src_text(n):
    """근거 대조용 원문 — (본문·문서 첨부, 그림 OCR). 그림 글자는 깨진 글자일 수 있어 따로 둔다."""
    return (norm(n['text'] + ''.join(t for a, t in n['att'] if not a.lower().endswith(IMG))),
            norm(''.join(t for a, t in n['att'] if a.lower().endswith(IMG))))


def gold_on(n):
    g = (n['rc'].get('filter') or {}).get('gold')
    return g is True or (isinstance(g, str) and bool(re.search(g, n['title'])))


def gold(n, d, me, v):
    """꽁돈(황금 태그) — 해당·확인 필요 가운데 통장으로 현금이 오고, 막는 의무·소득 심사가 없는 글.
    돌려줌 (True | False | None, 까닭). None = 따질 수 없음(꽁돈 칸이 꺼진 출처 · 꽁돈 칸 없이 뽑힌 옛 캐시 · 자격 밖).
    근거가 원문에 없으면: 지급은 «모름»(황금 아님) · 의무·소득 심사는 있는 것으로 본다(헛황금을 막는 쪽)."""
    if not gold_on(n) or v not in ('해당', '확인 필요') or '지급' not in d:
        return None, ''
    cfg = {**GOLD_DEFAULT, **(me.get('꽁돈') or {})}
    strong, weak = src_text(n)
    seen = lambda q: bool(norm(q)) and (norm(q) in strong or norm(q) in weak)
    pay = d.get('지급') or {}
    form = pay.get('형태') if seen(pay.get('근거')) else '모름'
    if form not in cfg['지급']:
        return False, f'지급 {form or "모름"}'
    heavy = [o.get('종류') for o in d.get('의무') or [] if o.get('종류') in cfg['막는 의무']]
    if heavy:
        return False, '의무 ' + '·'.join(dict.fromkeys(heavy))
    if cfg.get('소득심사 막음') and (d.get('소득심사') or {}).get('반영'):
        return False, '소득 심사'
    return True, f'꽁돈 · {form} «{(pay.get("근거") or "")[:30]}»'


def judge_one(n, d, me):
    v, res = judge_rules(n, d, me)
    if v == '비해당' and load_marks().get(f'{n["sid"]}:{n["id"]}', {}).get('평가') == '쓸모':    # 사용자가 살린 글(수집 창) — 규칙이 다시 빼지 않는다
        return '관심', res + [('관심', '사용자 쓸모 표시', {})]
    return v, res


def judge_rules(n, d, me):
    skip = (n['rc'].get('filter') or {}).get('title_skip')      # gate() 와 같은 제외어 — 이미 볼트에 든 글도 일정에 다시 안 올린다(11-05 대산농촌재단)
    if skip and re.search(skip, n['title']) and not interest(n['title'], me):
        return '비해당', [('불충족', '제목 제외(조리법 title_skip)', {'근거': n['title']})]
    rule = card_rule(n['title'], me) if n['rc'].get('filter') else None     # LMS 글(filter {})은 제목 규칙 대상이 아니다
    if rule:
        return '비해당', [('불충족', f'제목 규칙({rule})', {'근거': n['title']})]
    strong, weak = src_text(n)
    res = []
    for c in d.get('조건') or []:
        if c.get('축') not in AXES:
            c['축'] = '기타'
        q = norm(c.get('근거') or '')
        if not q or (q not in strong and q not in weak):
            res.append(('모름', f'근거 원문 없음({c.get("축")})', c))
            continue
        st, why = check(c, me)
        if st == '불충족' and c.get('축') in ('신분', '학년') and NEG.search(c.get('근거') or ''):   # 제외 문장을 허용 목록으로 뽑은 꼴(11-05 «졸업예정자는 해당없음» → 대상 [졸업예정]) — 추출이 뒤집혔을 수 있어 빼지 않는다
            st, why = '모름', f'{why}(근거가 제외 문장 — 원문 확인)'
        if st == '불충족' and q not in strong:      # 그림 글자만이 근거면 빼지 않는다(10-27 해동 포스터 «소득분뭐 4문뭐»)
            st, why = '모름', f'{why}(그림 OCR 근거 — 원문 확인)'
        res.append((st, why, c))
    tr = title_region(n, me)
    if tr:
        res.append(tr)
    no = [r for r in res if r[0] == '불충족']
    unk = [r for r in res if r[0] == '모름']
    if no:
        v = '비해당'
        k = interest(f'{n["title"]} {d.get("요약") or ""}', me)
        if k:
            v = '관심'
            res.append(('관심', f'관심 «{k}»', {}))
    elif unk or d.get('첨부에만') or not res:
        v = '확인 필요'
    else:
        v = '해당'
    return v, res


def deadline(n, d):
    if d.get('마감') and re.match(r'\d{4}-\d{2}-\d{2}$', str(d['마감'])):
        return d['마감']
    return title_deadline(n['rc'], n['title'], n['date'])


def judged(sid):
    """{글번호: (판정, 근거 한 줄, 마감)} — 마감과 무관한 판정(해당·확인 필요·관심·비해당). 추출 캐시가 있는 글만(LLM 0)."""
    me, out = card(), {}
    for n in notices(sid):
        if not os.path.exists(cpath(n)):
            continue
        d = json.load(open(cpath(n), encoding='utf-8'))
        v, res = judge_one(n, d, me)
        why = ' · '.join(dict.fromkeys(x[1] for x in res if x[0] in ('불충족', '모름', '관심')))
        if gold(n, d, me, v)[0]:          # 수집 창은 이 한 줄(엔진 상태 why)을 보여 준다 — 꽁돈을 맨 앞에
            why = '꽁돈' + (f' · {why}' if why else '')
        out[n['id']] = (v, why[:160], deadline(n, d))
    return out


def verdicts(sid):
    """엔진 settle 이 부른다 → {글번호: (판정, 근거 한 줄)}. 판정 = KEEP(해당·확인 필요·관심) · 비해당 ·
    지남(마감이 지났으면 판정과 무관하게 — 때는 되돌아가지 않는다)."""
    today = date.today().isoformat()
    return {k: (('지남', f'마감 {dl}' if dl != '0000-00-00' else '«마감» 표시') if dl and dl < today else (v, why))
            for k, (v, why, dl) in judged(sid).items()}


# ───────── 성과 칸 — 사용자 표시(헛것·쓸모)와 놓침 장부 (M1-4 · 10-29) ─────────
def load_marks():
    return json.load(open(MARKS, encoding='utf-8')) if os.path.exists(MARKS) else {}


def save_marks(m):
    with open(MARKS + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    os.replace(MARKS + '.tmp', MARKS)


def mark(aid, what, memo='', **more):
    """볼트 글 하나에 사용자 표시 — 헛것(필요 없었음) · 쓸모(썼음). Claude 가 사용자 말을 받아 적는다. 글번호는 끝자리만 줘도 된다.
    more = 빈 값이 아닌 것만 붙는다(거절 단추: 길='단추' · 낱말=제목에서 고른 낱말 — filter-learn 이 메모 대신 이것으로 배운다)."""
    hits = [(rc['id'], k) for rc in recipes() for k in state_items(rc) if k == aid or k.endswith(aid)]
    if len(hits) != 1:
        sys.exit(f'글번호 «{aid}»: {len(hits)}건 일치 — 더 길게 적을 것')
    m = load_marks()
    m[f'{hits[0][0]}:{hits[0][1]}'] = {'평가': what, '메모': memo, **{k: v for k, v in more.items() if v}, 'at': time.strftime('%Y-%m-%d %H:%M')}
    save_marks(m)
    print(f'표시 {hits[0][0]} {hits[0][1]} = {what}')


def reject(aid, why, words=(), button=False):
    """사용자가 읽고 뺀 글 — 추출하지 않고(사용량 0) 대기 칸에서 지워 제목·근거 장부 줄만 남긴다. Claude 가 사용자 말을 받아 적는다.
    button = 수집 창 거절 단추(11-09) — why 는 사용자 메모(비어도 됨) · words 는 제목에서 고른 낱말. 단추가 «거절»을 까닭으로 적어 되먹임이 «까닭 안 맞음»을 내던 것을 막는다."""
    hits = [rc for rc in recipes() if aid in state_items(rc)]
    if len(hits) != 1:
        sys.exit(f'글번호 «{aid}»: {len(hits)}건 일치')
    rc = hits[0]
    sp = os.path.join(STATE, rc['id'] + '.json')
    st = json.load(open(sp, encoding='utf-8'))
    it = st['items'][aid]
    it.pop('stage', None)
    words = [w for w in dict.fromkeys(w.strip() for w in words) if w]
    said = ' · '.join([f'«{w}»' for w in words] + ([why] if why else []))
    it.update(verdict='비해당', why=f'사용자: {said or "거절"}')
    with open(sp + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(st, f, ensure_ascii=False, indent=1)
    os.replace(sp + '.tmp', sp)
    for k in ('md', 'html', 'body.html'):
        f = os.path.join(STAGE, rc['id'], f'{aid}.{k}')
        if os.path.exists(f):
            os.remove(f)
    mark(aid, '헛것', why, 길='단추' if button else '', 낱말=words)
    print(f'뺌 {rc["id"]} {it.get("title", "")[:50]}')


def miss(what, url=''):
    """놓침 기록 — 원했는데 수집이 못 가져온 것(어디서 찾았는지 주소와 함께)."""
    m = load_marks()
    m.setdefault('_놓침', []).append({'무엇': what, 'url': url, 'at': time.strftime('%Y-%m-%d %H:%M')})
    save_marks(m)
    print(f'놓침 기록 {len(m["_놓침"])}건째')


def misses(marks):
    """놓침 장부 = 내-일정에서 바깥 주소(http)를 원본으로 단 줄(수집 출처 밖에서 찾아 옮긴 것 · 받은 글 주소는 뺀다) + miss 기록."""
    got = {it.get('url') for rc in recipes() for it in state_items(rc).values() if it.get('url')}
    out = []
    f = os.path.join(VAULT, '2_지식', '일정', '내-일정.md')
    if os.path.exists(f):
        for ln in open(f, encoding='utf-8').read().splitlines():
            m = re.match(r'^\s*- \[[ xX]\] (\d{4}-\d{2}-\d{2}).*?\[원본\]\((https?://[^)\s]+)\)', ln)
            if m and m.group(2) not in got:
                out.append((m.group(1), re.sub(r'\s*\[원본\]\([^)]*\)', '', ln.split('] ', 1)[1])[11:].split(' — ')[0][:70], m.group(2)))
    out += [(x.get('at', '')[:10], x.get('무엇', ''), x.get('url', '')) for x in marks.get('_놓침', [])]
    return out


def write_status(S):
    """세션 시작 한 줄(생산자) — 판정 대기·열린 수집 대기열이 있을 때만. 없으면 파일을 지워 훅이 조용하게."""
    pending = sum(s['판정 대기'] for s in S.values())
    qopen = sum(1 for ln in open(QUEUE, encoding='utf-8').read().splitlines() if ln.startswith('- [ ]')) if os.path.exists(QUEUE) else 0
    msg = ' · '.join(x for x in (f'판정 대기 {pending}건 — 추출 단추 `py -3.11 3_시스템/notice-filter.py extract`' if pending else '',
                                 f'수집 대기열 열린 {qopen}건 — `3_시스템/_index/수집-대기열.md`' if qopen else '') if x)
    if msg:
        with open(STATUS, 'w', encoding='utf-8', newline='\n') as f:
            f.write(msg + '\n')
    elif os.path.exists(STATUS):
        os.remove(STATUS)


def judge(quiet=False):
    me = card()
    rows, missing = [], 0
    for n in notices():
        if not os.path.exists(cpath(n)):
            missing += 1
            rows.append((n, '판정 대기' if n['where'] == '대기 칸' else '추출 안 됨', [], deadline(n, {}), {}))
            continue
        d = json.load(open(cpath(n), encoding='utf-8'))
        v, res = judge_one(n, d, me)
        rows.append((n, v, res, deadline(n, d), d))
    today = date.today().isoformat()
    rows = [(n, v + (' · 마감 지남' if dl and dl < today and v != '비해당' else ''), res, dl, d) for n, v, res, dl, d in rows]
    order = {'해당': 0, '확인 필요': 1, '관심': 2, '판정 대기': 3, '해당 · 마감 지남': 4, '확인 필요 · 마감 지남': 5, '관심 · 마감 지남': 6,
             '판정 대기 · 마감 지남': 7, '비해당': 8, '추출 안 됨': 9, '추출 안 됨 · 마감 지남': 9}
    rows.sort(key=lambda r: (r[0]['sid'], order[r[1]], r[3] or '9999'))
    # 판정표 — 근거 한 줄
    L = [f'# 공지 판정 ({time.strftime("%Y-%m-%d %H:%M")})', '> notice-filter.py judge · 카드 = [[자격-카드]] · 비해당은 근거 인용이 원문에 있는 불충족만',
         '> 자리: **볼트** = 1_수집 에 든 글 · **대기 칸** = 판정 전이거나 비해당이라 볼트 밖(_index/collect/stage)에 둔 글 · **장부** = 본문을 받지 않고 제목·근거만 남긴 글 · **보관 칸** = 볼트에 들였다가 빼낸 글(_index/collect/archive · 첨부째 · 자동으로 지우지 않음 · 되돌리기 `web-collect.py --restore`)', '']
    cnt, golds = {}, []
    for n, v, res, dl, d in rows:
        cnt[(n['sid'], v)] = cnt.get((n['sid'], v), 0) + 1
        g, gwhy = gold(n, d, me, v)
        if g:
            golds.append(f'- {dl or "마감?"} · {n["title"][:60]} — {gwhy}')
        elif g is False:
            gwhy = f'꽁돈 아님({gwhy})'
        if v == '비해당':
            r = next(x for x in res if x[0] == '불충족')
            why = f'{r[1]} — «{(r[2].get("근거") or "")[:60]}»'
        elif v.startswith('관심'):
            r = next((x for x in res if x[0] == '불충족'), None)
            why = next(x[1] for x in res if x[0] == '관심') + (f' · 자격 밖: {r[1]}' if r else '')
        elif v.startswith('확인 필요'):
            why = ' · '.join(dict.fromkeys(x[1] for x in res if x[0] == '모름'))[:120] or ('조건이 첨부·그림에만' if d.get('첨부에만') else '조건 없음')
        elif v.startswith('해당'):
            why = ' · '.join(x[1] for x in res)[:120]
        else:
            why = '추출 전 — `notice-filter.py extract`' if v.startswith('판정 대기') else ''
        if gwhy:
            why = f'{why} · {gwhy}' if why else gwhy
        L.append(f'- **{v}**{" · 꽁돈" if g else ""} {dl or "마감?"} · {"" if n["where"] == "볼트" else "(" + n["where"] + ") "}{n["title"][:60]} — {why}')
    for rc in recipes():                 # 장부 — 제목만으로 걸러져 본문을 받지 않은 글
        for aid, it in state_items(rc).items():
            if not it.get('path') and not it.get('stage') and not it.get('archived') and it.get('verdict'):
                cnt[(rc['id'], '장부 ' + it['verdict'])] = cnt.get((rc['id'], '장부 ' + it['verdict']), 0) + 1
                L.append(f'- **{it["verdict"]}** (장부) · {(it.get("title") or "")[:60]} — {it.get("why", "")} · {it.get("url", "")}')
    L += ['', '## 꽁돈 (해당·확인 필요 중 현금 · 막는 의무 없음 · 기준 = 카드 «꽁돈» 칸)', *(golds or ['- 없음'])]
    L += ['', '## 집계', *[f'- {k[0]} {k[1]}: {c}' for k, c in sorted(cnt.items())]]
    # 성과 칸(M1-4) — 출처별 자리 수 · 사용자 표시 · 놓침 장부. 목표값은 기준선(M2 뒤 2주)을 잰 다음 정한다.
    marks, S = load_marks(), {}
    zero = lambda: {'볼트': 0, '대기 칸': 0, '판정 대기': 0, '장부': 0, '보관 칸': 0, '헛것': 0, '쓸모': 0}
    for n, v, res, dl, d in rows:
        s = S.setdefault(n['sid'], zero())
        s['판정 대기' if v.startswith('판정 대기') else n['where']] += 1
        mk = marks.get(f'{n["sid"]}:{n["id"]}', {}).get('평가')
        if mk in ('헛것', '쓸모') and n['where'] == '볼트':
            s[mk] += 1
    for (sid, k), c in cnt.items():
        if k.startswith('장부 '):
            S.setdefault(sid, zero())['장부'] += c
    ms = misses(marks)
    P = ['## 성과 (출처별 · 로드맵 M1-4)', '| 출처 | 볼트 | 대기 칸 | 판정 대기 | 장부 | 보관 칸 | 헛것 표시 | 쓸모 표시 |', '|---|---|---|---|---|---|---|---|',
         *[f'| {sid} | {s["볼트"]} | {s["대기 칸"]} | {s["판정 대기"]} | {s["장부"]} | {s["보관 칸"]} | {s["헛것"]} | {s["쓸모"]} |' for sid, s in sorted(S.items())],
         f'- 놓침 장부 {len(ms)}건 — 수집 출처 밖에서 찾아 옮긴 일정 줄 + 기록한 놓침', *[f'  - {a} {b} — {c}' for a, b, c in ms],
         '- 표시: `py -3.11 3_시스템/notice-filter.py mark <글번호> 헛것|쓸모 [메모]` · `… miss "<무엇>" [주소]` (Claude 가 사용자 말을 받아 적는다)', '']
    L[4:4] = P
    write_status(S)
    # 카드에 물으면 줄어드는 «모름» — 많이 걸리는 순(마감 남은 확인 필요만 · 한 공지에 한 번)
    asks = {}
    for n, v, res, dl, d in rows:
        if v == '확인 필요':
            for k in {re.sub(r'[:(].*', '', x[1]).strip() for x in res if x[0] == '모름' and not x[1].startswith('근거 원문 없음')}:
                asks[k] = asks.get(k, 0) + 1
            if d.get('첨부에만'):
                asks['조건이 첨부·그림에만'] = asks.get('조건이 첨부·그림에만', 0) + 1
    L += ['', '## 카드에 물으면 줄어드는 모름', *[f'- {k}: {c}건' for k, c in sorted(asks.items(), key=lambda kv: -kv[1])]]
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    with open(REPORT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(L) + '\n')
    sheets = {}                          # 조리법 filter.schedule = 일정 파일 이름 · label = 줄 머리. 여러 출처가 한 파일을 나눠 쓴다 — 출처마다 쓰면 뒤 출처가 앞 줄을 덮는다
    for rc in recipes():
        if rc['filter'].get('schedule'):
            sheets.setdefault(rc['filter']['schedule'], []).append(rc)
    for name, rcs in sheets.items():
        sids = {rc['id'] for rc in rcs}
        write_schedule([r for r in rows if r[0]['sid'] in sids and r[1] in KEEP + ('판정 대기',) and r[3]],
                       os.path.join(VAULT, '2_지식', '일정', name), rcs[0]['filter'].get('label', rcs[0]['name']))
    if not quiet:
        print('\n'.join(L))
    if missing:
        print(f'\n추출 안 된 공지 {missing} — `notice-filter.py extract`')
    return cnt


def write_schedule(rows, SCHED, label):
    import schedule as sc
    done = set()
    if os.path.exists(SCHED):
        for ln in open(SCHED, encoding='utf-8').read().splitlines():
            m = sc.LINE.match(ln)
            if m and m.group(1) in 'xX' and m.group(6):
                done.add(m.group(6))
    today = date.today().isoformat()
    lines, seen, me = [], set(), card()
    for n, v, res, dl, d in sorted(rows, key=lambda r: r[3]):
        if dl < today:
            continue
        dd = datetime.strptime(dl, '%Y-%m-%d')
        # 짧은 글 번호는 게시판마다 따로 늘어나 한 파일에서 겹칠 수 있다(체크가 번지고 알림 키가 같아진다) — 출처를 붙인다. 포털 18자리는 게시판 번호가 들어 있고 이미 쓰는 줄이라 그대로
        bid = f'sch-{n["id"]}' if len(n['id']) >= 12 else f'sch-{n["sid"]}-{n["id"]}'
        tag = ('' if v == '해당' else f' ({v})') + (' #꽁돈' if gold(n, d, me, v)[0] else '')   # 황금 태그(CSS 조각 꽁돈.css)
        name = re.sub(r'^\[[^\]]*\]\s*', '', n['title'])[:50]
        if (dl, norm(name)) in seen:     # 같은 글을 여러 게시판이 올림(표본 공대·전기전자 공지 제목 3개가 같다) — 한 줄만
            continue
        seen.add((dl, norm(name)))
        link = f'[원문]({n["url"]})' if n['staged'] else sc.src_link(os.path.relpath(n['path'], VAULT))   # 대기 칸 글은 볼트에 없다
        lines.append(f'- [{"x" if bid in done else " "}] {dl} ({WD[dd.weekday()]}) {(n["rc"].get("filter") or {}).get("label", label)} · {name}{tag} {link} ^{bid}')
    title = os.path.splitext(os.path.basename(SCHED))[0].replace('-', ' ')
    head = ['---', 'type: episodic', f'title: {title}', f'created: {today}', f'updated: {today}', f'tags: [일정, {label}, 생성파일]',
            'links: ["[[외부뇌-일정-형식]]", "[[자격-카드]]"]', 'status: active', 'source: claude', '---', f'# {title} (생성 파일)', '',
            '> `3_시스템/notice-filter.py judge` 가 «해당»·«확인 필요» 중 마감이 남은 것만 다시 쓴다(조리법 `filter.schedule`). 체크만 남는다. 비해당과 근거는 `3_시스템/_index/collect/판정.md`. 꽁돈 태그 = 통장으로 현금이 오고 막는 의무가 없는 것(카드 «꽁돈» 칸).', '']
    with open(SCHED, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(head + lines) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['extract', 'judge', 'mark', 'miss', 'reject'])
    ap.add_argument('args', nargs='*', help='mark <글번호> 헛것|쓸모 [메모] · miss "<무엇>" [주소] · reject <글번호> <까닭> | reject <글번호> --button [--word 낱말]… [--memo 메모]')
    ap.add_argument('--button', action='store_true', help='reject: 수집 창 거절 단추(까닭 = 고른 낱말·메모 · 둘 다 비어도 됨)')
    ap.add_argument('--word', action='append', default=[], help='reject --button: 제목에서 고른 낱말(여럿)')
    ap.add_argument('--memo', default='', help='reject --button: 사용자 메모')
    ap.add_argument('--max', type=int, default=60)
    ap.add_argument('--refresh', action='store_true', help='첨부 글자가 새로 생긴 «첨부에만» 공지를 다시 뽑는다')
    ap.add_argument('--again', nargs='+', default=[], metavar='글번호', help='캐시가 있어도 이 글을 다시 뽑는다(첨부 색인을 고친 공고)')
    ap.add_argument('--workers', type=int, default=1, help='동시 claude -p 수(여럿이면 OAuth 갱신이 부딪힐 수 있음)')
    ap.add_argument('--source', help='이 출처 id 만')
    a = ap.parse_args()
    if a.cmd == 'extract':
        extract(a.max, a.refresh, a.workers, a.source, again=a.again)
    elif a.cmd == 'mark':
        if len(a.args) < 2 or a.args[1] not in ('헛것', '쓸모'):
            sys.exit('mark <글번호> 헛것|쓸모 [메모]')
        mark(a.args[0], a.args[1], ' '.join(a.args[2:]))
    elif a.cmd == 'reject':
        if a.button and len(a.args) == 1:
            reject(a.args[0], a.memo.strip(), a.word, button=True)
        elif not a.button and len(a.args) >= 2:
            reject(a.args[0], ' '.join(a.args[1:]))
        else:
            sys.exit('reject <글번호> <까닭> | reject <글번호> --button [--word 낱말]… [--memo 메모]')
    elif a.cmd == 'miss':
        if not a.args:
            sys.exit('miss "<무엇>" [주소]')
        miss(a.args[0], a.args[1] if len(a.args) > 1 else '')
    else:
        judge()


if __name__ == '__main__':
    main()
