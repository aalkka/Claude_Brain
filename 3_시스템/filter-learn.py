"""공지 필터 되먹임 — 나에 대한 정보가 자격 카드와 제목 관문(사용량 0)으로 들어가는 길 (2026-11-05 사용자 «나에 대한 정보를 계속 쌓아서 필터의 성능을 높여»).

LLM 0 · 네트워크 0. 사용자 일을 늘리지 않는다: 새로 묻는 일이 없고, 이미 일어나는 일(뺀 글·살린 글·손 노트·판정·카드 갱신)만 읽는다.
원칙(notice-filter 와 같음): 빼도 되는 근거가 있을 때만 뺀다 · 까닭이 안 맞는 글은 그대로 빼지 않는다(11-04 관정재단) · 값은 카드에만.

길 넷:
  ① 카드 → 제목 관문: 카드 JSON «제목규칙»(묶음마다 낱말 + 카드 조건)은 notice-filter 가 판정 때 바로 읽는다(조리법에 복사하지 않는다 — 조리법 title_skip·수집 창 낱말 칸은 출처 몫만).
     조건이 깨지면(예 4학년) 그 묶음이 꺼진다. 살린 글이 걸린 말은 카드 «풀린말»로 간다.
  ② 뺀 글·살린 글 → 규칙: 평가.json 의 헛것·쓸모(learn). 뺀 까닭의 말이 글에 없으면 규칙으로 올리지 않고 대기열 한 줄. 제목에 있고 재생 손실 0 이면 «사용자 뺌» 묶음에.
  ③ 손 노트 → 암묵 쓸모: 내-일정 등 손 노트가 가리키는 글 = «쓸모»(자동) · 판정의 지역 불충족 재단 이름 → «다른 지역» 묶음(같은 재단이 다음 학기에도 온다).
  ④ 사실 → 카드: `card set` (사용자 답·공고 대조·학적 변화를 받아 적는다) · 전후 뒤집힌 글을 바로 보여 준다 · «다시볼날»(전과 발표·학기 바뀜)이 되면 대기열 한 줄(tick).
  sweep = 대기 칸의 판정 전 글이 제목 규칙에 걸리면 추출하지 않고 장부로(사용량을 아낀다).

  py -3 3_시스템/filter-learn.py run [--dry]        # learn + sweep + tick · 조용히(수집 끝에 불린다)
  py -3 3_시스템/filter-learn.py sweep|learn|tick [--dry]
  py -3 3_시스템/filter-learn.py card set <칸> <값(JSON 또는 글자)> --why "<근거>" [--kind 사실|추론]
  py -3 3_시스템/filter-learn.py report             # 출처별 깔때기: 관찰 → 제목 통과 → 판정 → 볼트 · 쓸모·헛것
"""
import argparse
import glob
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import date

SYS = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(SYS)
RECIPES = os.path.join(SYS, 'collect')
STATE = os.path.join(SYS, '_index', 'collect')
LOG = os.path.join(STATE, '되먹임.jsonl')          # 한 일 — 낱말·표시를 무엇 때문에 바꿨는지(값 없음)
STOP = {'아님', '없음', '해당', '대상', '필요', '안함', '있음', '관심', '사용자', '이미', '지금', '아니', '함께', '때문', '모름'}
ORG = re.compile(r'(?:\(재\)\s*)?([가-힣A-Za-z]{2,14}(?:장학회|장학재단|재단|진흥원|연구원))')


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SYS, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


nf = _load('notice_filter', 'notice-filter.py')


def now():
    return time.strftime('%Y-%m-%d %H:%M')


def note(kind, **kw):
    with open(LOG, 'a', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps({'at': now(), 'kind': kind, **kw}, ensure_ascii=False) + '\n')


def queue(src, what):
    """수집 대기열 한 줄 — 엔진과 같은 꼴·같은 파일(열린 같은 줄이 있으면 또 안 쓴다). 엔진을 부르지 않는다."""
    qf = nf.QUEUE
    if os.path.exists(qf) and any(ln.startswith('- [ ] ') and ln.endswith(f'`{src}` (Claude) {what}') for ln in open(qf, encoding='utf-8').read().splitlines()):
        return
    with open(qf, 'a', encoding='utf-8', newline='\n') as f:
        f.write(f'- [ ] {now()} `{src}` (Claude) {what}\n')


# ───────── 카드 ─────────
def card_text():
    return open(nf.CARD, encoding='utf-8').read()


def save_card(d, line=None):
    """JSON 블록만 다시 쓴다 + 근거 한 줄(카드 안에만 · 값은 밖으로 안 나간다)."""
    t = card_text()
    t = re.sub(r'```json\s*\{.*?\}\s*```', lambda _: '```json\n' + json.dumps(d, ensure_ascii=False, indent=2) + '\n```', t, count=1, flags=re.S)
    t = re.sub(r'^updated: .*$', f'updated: {date.today().isoformat()}', t, count=1, flags=re.M)
    if line:
        t = t.rstrip() + '\n' + line + '\n'
    tmp = nf.CARD + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(t)
    os.replace(tmp, nf.CARD)
    nf._card.clear()


# ───────── 조리법 ─────────
def filter_recipes():
    for rp in sorted(glob.glob(os.path.join(RECIPES, '*.json'))):
        rc = json.load(open(rp, encoding='utf-8'))
        if rc.get('filter') is not None:
            yield rp, rc


def words(rx):
    return [w for w in (rx or '').split('|') if w]


def save_recipe(path, rc):
    tmp = os.path.join(os.path.dirname(path), '.' + os.path.basename(path) + '.tmp')
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(rc, f, ensure_ascii=False, indent=2)
        f.write('\n')
    for i in range(6):                  # 켜진 옵시디언이 쥐고 있을 때
        try:
            return os.replace(tmp, path)
        except PermissionError:
            if i == 5:
                raise
            time.sleep(0.2)


def unskip(ws):
    """풀린 낱말을 조리법 칸에서도 뺀다(출처 몫에 같은 말이 있을 때). 풀 때 한 번만 한다 — 사용자가 수집 창에서 다시 더한 말은 그대로 둔다."""
    for path, rc in filter_recipes():
        cur = words(rc['filter'].get('title_skip'))
        new = [w for w in cur if w not in ws]
        if new == cur:
            continue
        if new:
            rc['filter']['title_skip'] = '|'.join(new)
        else:
            rc['filter'].pop('title_skip', None)
        save_recipe(path, rc)
        note('unskip', src=rc['id'], gone=[w for w in cur if w in ws])


def sweep(dry=False, quiet=False):
    """대기 칸의 판정 전 글 중 제목 관문에 걸리는 글 → 추출하지 않고 장부로. 판정이 난 글은 judge·settle 몫이라 안 건드린다."""
    n = 0
    for rc in nf.recipes():
        sp = os.path.join(STATE, rc['id'] + '.json')
        if not os.path.exists(sp) or rc.get('enabled') is False:     # 끈 출처 = 판정 반영도 멈춘다(사용자 11-05)
            continue
        st = json.load(open(sp, encoding='utf-8'))
        changed = False
        for aid, it in st['items'].items():
            if not it.get('stage') or os.path.exists(os.path.join(nf.CACHE, f'{rc["id"]}-{aid}.json')):
                continue
            g = nf.gate(rc, {'title': it.get('title') or '', 'date': (it.get('date') or '').replace('.', '-')})
            if not g:
                continue
            n += 1
            if not quiet:
                print(f'장부로 {rc["id"]} {g[0]} — {(it.get("title") or "")[:50]}')
            if dry:
                continue
            it.pop('stage', None)
            it.pop('v_att', None)
            it.update(verdict=g[0], why=g[1])
            changed = True
            for k in ('md', 'html', 'body.html'):
                f = os.path.join(nf.STAGE, rc['id'], f'{aid}.{k}')
                if os.path.exists(f):
                    os.remove(f)
            note('sweep', src=rc['id'], id=aid, verdict=g[0])
        if changed:
            tmp = sp + '.tmp'
            with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
                json.dump(st, f, ensure_ascii=False, indent=1)
            os.replace(tmp, sp)
    return n


# ───────── ②③ 신호 → 규칙 ─────────
def hand_notes():
    """손 노트 = 지식·작업 층의 md 중 생성 파일이 아닌 것(머리 tags 에 «생성파일» 이면 뺀다)."""
    out = []
    for root in ('2_지식', '0_작업'):
        for d, _, fs in os.walk(os.path.join(VAULT, root)):
            for fn in fs:
                if not fn.endswith('.md'):
                    continue
                p = os.path.join(d, fn)
                try:
                    t = open(p, encoding='utf-8').read()
                except (OSError, UnicodeDecodeError):
                    continue
                if '생성파일' in t[:400]:
                    continue
                out.append((os.path.relpath(p, VAULT).replace('\\', '/'), t))
    return out


def all_items():
    for rc in nf.recipes():
        for aid, it in nf.state_items(rc).items():
            yield rc, aid, it


def body_of(rc, aid, it):
    """글 본문(볼트·보관·대기 어디든) — 까닭 대조용. 없으면 ''."""
    f = None
    if it.get('path'):
        f = os.path.join(VAULT, it['path'])
    elif it.get('archived'):
        f = os.path.join(nf.ARCH, it['archived'])
    elif it.get('stage'):
        f = os.path.join(nf.STAGE, rc['id'], aid + '.md')
    t = ''
    if f and os.path.exists(f):
        t = open(f, encoding='utf-8').read()
    c = os.path.join(nf.CACHE, f'{rc["id"]}-{aid}.json')
    if os.path.exists(c):
        t += json.dumps(json.load(open(c, encoding='utf-8')).get('조건') or [], ensure_ascii=False)
    return t


def reason_tokens(memo):
    head = re.split(r'\s*[—–-]\s*', memo or '')[0]
    return [w for w in re.findall(r'[가-힣A-Za-z0-9]{2,}', head) if w not in STOP]


def protected_hits(word, skip_key=None):
    """이 낱말을 빼면 잃는 글 — 남길 판정(해당·확인 필요·관심)이거나 쓸모 표시. 재생으로 잰다(LLM 0)."""
    marks = nf.load_marks()
    rx = re.compile(word)
    judged = {}
    hits, prot = [], []
    for rc, aid, it in all_items():
        if not rx.search(it.get('title') or ''):
            continue
        key = f'{rc["id"]}:{aid}'
        if key == skip_key:
            continue
        hits.append(key)
        if rc['id'] not in judged:
            judged[rc['id']] = nf.judged(rc['id'])
        v = judged[rc['id']].get(aid)
        if (v and v[0] in nf.KEEP) or (marks.get(key) or {}).get('평가') == '쓸모':
            prot.append((it.get('title') or '')[:40])
    return hits, prot


def rule_group(me, name, why, **cond):
    for g in me.setdefault('제목규칙', []):
        if g.get('이름') == name:
            return g
    g = {'이름': name, **cond, '말': [], '근거': why}
    me['제목규칙'].append(g)
    return g


def learn(dry=False, quiet=False):
    say = (lambda *a: None) if quiet else print
    marks = nf.load_marks()
    me = nf.card()
    done = {'쓸모 표시': 0, '제외어': 0, '풀림': 0, '까닭 안 맞음': 0, '거절 메모': 0, '재단': 0}
    changed_marks, changed_card = False, False
    items = list(all_items())
    # ③ 손 노트 → 암묵 쓸모 · 손으로 수집한 같은 글(1_수집 의 같은 제목 파일 · 엔진이 쓴 파일이 아닌 것)도 신호다
    notes = hand_notes()
    own = {os.path.basename((it.get('path') or it.get('archived') or '').replace('\\', '/')) for _, _, it in items}
    hand = {fn[:-3] for d, _, fs in os.walk(os.path.join(VAULT, '1_수집')) if '_색인' not in d and '.web' not in d for fn in fs if fn.endswith('.md') and fn not in own}
    for rc, aid, it in items:
        key = f'{rc["id"]}:{aid}'
        if key in marks or not it.get('hash'):       # 본문을 받은 글만(제목 장부 줄은 근거가 약하다)
            continue
        rel = (it.get('path') or it.get('archived') or '').replace('\\', '/')
        stem = os.path.splitext(os.path.basename(rel))[0]
        name = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', it.get('title') or '').strip(' .')
        ref = next((np for np, t in notes if (stem and stem in t) or (it.get('url') and it['url'] in t)), None)
        if not ref and len(name) >= 12 and any(name in h for h in hand):
            ref = '손 수집(1_수집)'
        if ref:
            done['쓸모 표시'] += 1
            say(f'쓸모(자동) {(it.get("title") or "")[:40]} ← {os.path.basename(ref)}')
            if not dry:
                marks[key] = {'평가': '쓸모', '메모': f'손 노트가 가리킴: {os.path.basename(ref)}', 'at': now(), '자동': True}
                changed_marks = True
    # ② 뺀 글 → 까닭 대조 → 제외어
    index = {f'{rc["id"]}:{aid}': (rc, aid, it) for rc, aid, it in items}

    def skip_word(rc, key, word):
        """제목 낱말 하나 → 사용자 뺌 묶음(남길 글에 걸리면 보류). 결과 한 줄."""
        nonlocal changed_card
        if word in '|'.join(words(rc['filter'].get('title_skip')) + [w for w, _ in nf.card_words(me)]):
            return f'이미 제외어 «{word}»'
        hits, prot = protected_hits(re.escape(word), key)
        if prot:
            return f'보류 — «{word}» 가 남길 글 {len(prot)}건에 걸림'
        done['제외어'] += 1
        if not dry:
            rule_group(me, '사용자 뺌', '사용자가 뺀 글의 까닭(평가.json)')['말'].append(re.escape(word))
            changed_card = True
        return f'제외어 «{word}» · 다른 글 {len(hits)}건 · 손실 0'

    for key, m in list(marks.items()):
        if key.startswith('_') or m.get('평가') != '헛것' or m.get('되먹음') or key not in index:
            continue
        rc, aid, it = index[key]
        title = it.get('title') or ''
        memo = (m.get('메모') or '').strip()
        result = ''
        if m.get('길') == '단추' or memo in ('거절', '수집 창에서 뺌'):
            # 수집 창 거절 단추(11-09) — 낱말은 사용자가 제목에서 골랐다(대조 불필요) · 메모는 글자 대조하지 않고 카드 조건 후보로 대기열에 · 옛 단추 기록(«거절»)은 까닭 없음
            memo = '' if memo in ('거절', '수집 창에서 뺌') and not m.get('길') else memo
            got = [skip_word(rc, key, w) for w in m.get('낱말') or [] if w in title]
            if memo:
                done['거절 메모'] += 1
                got.append('메모 → 대기열')
                if not dry:
                    queue('filter-learn', f'거절 메모 — 자격 카드 조건으로 올릴지 사용자에게 확인: «{memo[:60]}» · {title[:50]} (`{key}`)')
            result = ' · '.join(got) or '거절 · 까닭 없음(대조 안 함)'
            say(f'뺀 글 {title[:36]} → {result}')
            if not dry:
                m['되먹음'] = result
                changed_marks = True
            continue
        toks = reason_tokens(memo)
        in_title = [w for w in toks if w in title]
        text = body_of(rc, aid, it)
        if in_title:
            result = skip_word(rc, key, max(in_title, key=len))
        elif toks and not any(w in text for w in toks):
            result = '까닭 안 맞음 — 까닭의 말이 글에 없음'
            done['까닭 안 맞음'] += 1
            if not dry:
                queue('filter-learn', f'뺀 글의 까닭이 글과 안 맞음 — 원문 대조 뒤 사용자에게 확인: {title[:50]} (`{key}`)')
        else:
            result = '제목에 까닭의 말 없음 · 본문에만(규칙 안 올림)'
        say(f'뺀 글 {title[:36]} → {result}')
        if not dry:
            m['되먹음'] = result
            changed_marks = True
    # ② 살린 글 → 그 글을 막은 낱말을 푼다(사용자가 직접 살린 글만 · 자동 표시는 말만 한다)
    for key, m in list(marks.items()):
        if key.startswith('_') or m.get('평가') != '쓸모' or m.get('되먹음') or key not in index:
            continue
        rc, aid, it = index[key]
        title = it.get('title') or ''
        blocking = [w for w in dict.fromkeys(words(rc['filter'].get('title_skip')) + [w for w, _ in nf.card_words(me)]) if nf.word_hit(w, title)]
        if not blocking:
            continue
        if m.get('자동'):
            say(f'손 노트 글이 제외어에 걸림(그대로 둠) {title[:36]} ← {blocking[:3]}')
            continue
        done['풀림'] += len(blocking)
        say(f'살린 글 {title[:36]} → 낱말 풂 {blocking[:3]}')
        if not dry:
            me.setdefault('풀린말', [])
            me['풀린말'] += [w for w in blocking if w not in me['풀린말']]
            m['되먹음'] = f'풂 {blocking}'
            changed_marks = changed_card = True
            unskip(set(blocking))
    # ③ 판정의 지역 불충족 → 재단 이름을 제목 규칙으로(같은 재단이 다음 학기에도 온다 · 사용량 0 으로 먼저 거른다)
    seen = set(w for g in me.get('제목규칙') or [] for w in g.get('말') or [])
    for n in nf.notices():
        c = nf.cpath(n)
        if not os.path.exists(c):
            continue
        v, res = nf.judge_rules(n, json.load(open(c, encoding='utf-8')), me)
        if v != '비해당' or not any(r[0] == '불충족' and (r[2].get('축') == '지역') for r in res if isinstance(r[2], dict)):
            continue
        o = ORG.search(n['title'])
        if not o or re.escape(o.group(1)) in seen or '서울' in o.group(1):
            continue
        word = re.escape(o.group(1))
        hits, prot = protected_hits(word)
        if prot:
            continue
        seen.add(word)
        done['재단'] += 1
        say(f'다른 지역 재단 {o.group(1)} · 제목 {len(hits)}건')
        if not dry:
            rule_group(me, '다른 지역', '카드 지역 + 판정 근거', 칸='지역', 전부='서울')['말'].append(word)
            changed_card = True
    if changed_marks:
        nf.save_marks(marks)
    if changed_card:
        save_card(me)
    if any(done.values()):
        note('learn', **done, dry=dry)
    return done


# ───────── ④ 사실 → 카드 ─────────
def verdict_map():
    out = {}
    for rc in nf.recipes():
        for aid, v in nf.judged(rc['id']).items():
            out[f'{rc["id"]}:{aid}'] = v[0]
    return out


def card_set(key, raw, why, kind='사실'):
    """사용자 답·공고 대조·학적 변화를 카드에 받아 적는다 → 전후 뒤집힌 글을 보여 준다(값은 안 찍는다). 제목 규칙은 카드를 바로 읽으니 따로 맞출 일이 없다."""
    if not why:
        sys.exit('근거(--why)가 있어야 쓴다')
    try:
        val = json.loads(raw)
    except ValueError:
        val = raw
    titles = {f'{rc["id"]}:{aid}': (it.get('title') or '') for rc, aid, it in all_items()}
    before = verdict_map()
    me = nf.card()
    me[key] = val
    me['기준일'] = date.today().isoformat()
    save_card(me, f'- **[{kind}] {key}** {date.today().isoformat()} — {why}')
    after = verdict_map()
    flips = [(k, before[k], after[k]) for k in before if k in after and before[k] != after[k]]
    print(f'카드 «{key}» 씀 · 뒤집힌 글 {len(flips)}')
    for k, a, b in flips:
        print(f'  {a} → {b} · {titles.get(k, k)[:60]}')
    note('card', key=key, flips=len(flips), why=why[:80])
    if any((a in nf.KEEP) != (b in nf.KEEP) for _, a, b in flips):
        subprocess.run([*(['py', '-3'] if os.name == 'nt' else [sys.executable]), os.path.join(SYS, 'web-collect.py'), '--settle'], cwd=VAULT, capture_output=True)


def tick(dry=False, quiet=False):
    """카드 «다시볼날» {날짜: 사유} — 그 날이 지나면 대기열 한 줄(학적이 바뀌었을 수 있다 · 물을 일은 Claude 가 모은다)."""
    me = nf.card()
    days = me.get('다시볼날') or {}
    today = date.today().isoformat()
    due = {d: why for d, why in days.items() if d <= today}
    for d, why in due.items():
        if not quiet:
            print(f'카드 다시 볼 날 {d}: {why}')
        if not dry:
            queue('자격카드', f'카드 다시 볼 날 {d} — {why} (`filter-learn.py card set` 로 받아 적는다)')
    if due and not dry:
        me['다시볼날'] = {d: w for d, w in days.items() if d not in due}
        save_card(me)
    return len(due)


# ───────── 깔때기 ─────────
def report():
    marks = nf.load_marks()
    print('| 출처 | 관찰(줄) | 제목에서 뺌 | 본문 받음 | 판정 대기 | 판정 끝 | 볼트 | 쓸모 | 헛것 |')
    print('|---|---|---|---|---|---|---|---|---|')
    tot = [0] * 8
    for rc in nf.recipes():
        items = nf.state_items(rc)
        ledger = sum(1 for it in items.values() if not (it.get('path') or it.get('stage') or it.get('archived')) and '제목' in str(it.get('why') or '') or (not (it.get('path') or it.get('stage') or it.get('archived')) and str(it.get('why') or '').startswith(('제목', '사용자'))))
        cached = {a for a in items if os.path.exists(os.path.join(nf.CACHE, f'{rc["id"]}-{a}.json'))}
        got = sum(1 for it in items.values() if it.get('hash'))
        wait = sum(1 for a, it in items.items() if it.get('stage') and a not in cached)
        vault = sum(1 for it in items.values() if it.get('path'))
        good = sum(1 for a in items if (marks.get(f'{rc["id"]}:{a}') or {}).get('평가') == '쓸모')
        bad = sum(1 for a in items if (marks.get(f'{rc["id"]}:{a}') or {}).get('평가') == '헛것')
        row = [len(items), ledger, got, wait, len(cached), vault, good, bad]
        tot = [x + y for x, y in zip(tot, row)]
        print(f'| {rc["id"]} | ' + ' | '.join(map(str, row)) + ' |')
    print('| 합 | ' + ' | '.join(map(str, tot)) + ' |')
    print(f'- 놓침 장부 {len(nf.misses(marks))}건')


def switches():
    """수집 전체 스위치 all_off·auto_judge — 3_시스템/collect.local.json(이 PC 의 결정 · git 밖 · 수집 본체 통합 11-07).
    그 칸이 없으면 옛 자리 lms/desk.json 의 칸을 한 판 동안 읽는다. 둘 다 없거나 못 읽으면 수집 켜짐·자동 판정 끔(값은 true 일 때만 켬)."""
    out = {}
    for p in (os.path.join(SYS, 'lms', 'desk.json'), os.path.join(SYS, 'collect.local.json')):    # 뒤(새 자리)가 이긴다
        try:
            d = json.load(open(p, encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict):
            out.update((k, d[k]) for k in ('all_off', 'auto_judge') if k in d)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'sweep', 'learn', 'tick', 'card', 'report'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--why', default='')
    ap.add_argument('--kind', default='사실', choices=['사실', '추론'])
    a = ap.parse_args()
    if a.cmd == 'run':
        if switches().get('all_off') is True:   # 수집 «전체 끔»
            return
        q = not sys.stdout.isatty()
        done = learn(a.dry, q)
        res = {'sweep': sweep(a.dry, q), 'tick': tick(a.dry, q)}
        if not a.dry:
            note('run', **{k: v for k, v in {**done, **res}.items() if v})      # 돌았다는 기록(수집 끝에 이어졌는지 재는 줄)
    elif a.cmd == 'sweep':
        print('장부로', sweep(a.dry))
    elif a.cmd == 'learn':
        print(learn(a.dry))
    elif a.cmd == 'tick':
        print('다시 볼 날', tick(a.dry))
    elif a.cmd == 'report':
        report()
    elif a.cmd == 'card':
        if len(a.args) < 3 or a.args[0] != 'set':
            sys.exit('card set <칸> <값> --why "<근거>"')
        card_set(a.args[1], a.args[2], a.why, a.kind)


if __name__ == '__main__':
    main()
