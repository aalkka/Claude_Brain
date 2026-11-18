"""태그 도구 tag — 분류가 정한 «태그» 동작을 그 대상이 보이는 자리에 맞춘다(범용 도구 셋 S8 · 2026-11-18 · 설계 = 제작자 설계 노트(배포판에 없음) §2 · §8.5 · §11).

붙일지는 분류(sort.py)가 정한다(판정 기록의 동작 {"태그": 이름}). 이 도구는 붙이고 떼는 일만 한다.
  지금 붙은 태그 = 분류 상태(_index/sort/<체계>.json)의 지금 판정 — «지금 판정에 맞추기»(멱등)라 넘김 장부를 몇 번 다시 읽어도 같다.
  보이는 자리(대상마다):
    수집글·가격줄 = 겹쳐 보이기. 1_수집 원본은 고치지 않는다 — 일정 줄 #꽁돈 · 판정표 · 수집 창 한 줄 · 모아보기 칸이 has() 로 지금 판정을 읽는다.
    노트(0_작업·2_지식 안 .md) = 프론트매터 tags — 체계가 "노트에 쓰기": true 일 때만(기본 끔 · 11-18 켠 체계 0).
      도구가 붙인 것만 뗀다(붙인 장부 = _index/sort/태그.json «붙임» · 사람이 먼저 단 같은 태그는 적지도 떼지도 않음 · 줄 = 태그.jsonl).
      노트 자리 = 어댑터 note(대상) 또는 대상 id «note:<볼트 상대 경로>».
  태그 사전 = 3_시스템/sort/태그/사전.json(개인 층 · 배포판 빈 틀 = 3_시스템/sort-examples/태그/사전.json) — 뜻 · 순서 · 가족(«티어/SSS» = 가족 티어의 값 SSS · 앞이 높음).
    어느 체계가 쓰는가는 체계 파일 «갈래» 동작에서 센다(사전에 적지 않음 — 어긋날 길이 없게).
  사람 태그(행위 tag.apply · «이거 꽁돈»): 그 태그를 주는 체계에 판정자 «사람» 판정을 적는다(sort.answer) → 분류 상태·넘김 장부가 바뀌고 겹쳐 보이기를 다시 그린다.

  py -3 3_시스템/tag.py list [--json]                 # 태그 사전 + 쓰는 체계 + 지금 붙은 수 + 문제(사전에 없는 태그 · 가족 밖 값)
  py -3 3_시스템/tag.py has <대상> <태그>               # 지금 붙었나(겹쳐 보이기 읽기 · 공지 필터·모아보기가 부르는 has() 그대로)
  py -3 3_시스템/tag.py sync [--all] [--dry]          # 넘김 장부의 새 붙임·뗌을 보이는 자리에(노트 쓰기 켠 체계만 파일을 씀) · --all = 장부 처음부터 + 전부 다시 맞춤
  py -3 3_시스템/tag.py tick                          # 15분 확인 끝(collect-tick act_tick) — sync 하고 노트를 바꾼 때만 한 줄
  py -3 3_시스템/tag.py apply <대상> <태그> [--off] [--why <말>] [--system <체계>] [--by <누가>] [--no-redraw]   # 사람이 «이거 꽁돈»(--off = «꽁돈 아님»)
"""
import argparse
import json
import os
import re
import sys
import time
from collections import Counter

SYS = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(SYS)
if SYS not in sys.path:
    sys.path.insert(0, SYS)
import sort  # noqa: E402

STATE = '태그.json'          # 넘김 커서 + 붙인 장부(노트에 쓴 것만)
LOG = '태그.jsonl'           # 노트에 붙임·뗌·사람 것 줄(덧붙이기)
TAG_RX = re.compile(r'^(?![-?])[^\s#,\[\]{}:"\'!&*%|>@`/]+$')     # 태그 이름 한 칸(가족·값 각각) — 옵시디언 태그 · YAML 흐름 목록에 따옴표 없이


def stamp():
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def ix(*p):
    return os.path.join(sort.INDEX, *p)


def dict_path():
    return os.path.join(sort.SYSTEMS, '태그', '사전.json')


# ───────── 사전 ─────────
def dictionary():
    """태그 사전 {이름: {뜻, 순서?, 가족?, 보임?}} — 없거나 깨지면 {}(겹쳐 보이기는 사전 없이도 돈다)."""
    try:
        d = json.load(open(dict_path(), encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    t = d.get('태그') if isinstance(d, dict) else None
    return t if isinstance(t, dict) else {}


def split(tag, D=None):
    """«가족/값» → (가족, 값) — 사전에 그 가족(«가족» 목록)이 있을 때만 · 아니면 (태그, None)."""
    D = dictionary() if D is None else D
    if '/' in tag:
        fam, _, val = tag.partition('/')
        if isinstance((D.get(fam) or {}).get('가족'), list):
            return fam, val
    return tag, None


def rank(tag, D=None):
    """가족 안 높이(목록 앞이 높음 → 큰 수) · 가족 밖·모르는 값 = None. 알림 도구가 «갈래가 오르면 다시»에 쓴다."""
    D = dictionary() if D is None else D
    fam, val = split(tag, D)
    order = (D.get(fam) or {}).get('가족') if val is not None else None
    return len(order) - order.index(val) if order and val in order else None


def branch_tags(s):
    """{갈래: [태그]} — 체계 파일의 갈래 동작."""
    return {g: [a['태그'] for a in (b or {}).get('동작') or [] if isinstance(a, dict) and isinstance(a.get('태그'), str)]
            for g, b in (s.get('갈래') or {}).items()}


def used():
    """{태그: [(체계, 갈래)]} — 꺼진 체계도 센다(사전 검사)."""
    out = {}
    for sid, s in sort.systems().items():
        if s.get('_err'):
            continue
        for g, ts in branch_tags(s).items():
            for t in ts:
                out.setdefault(t, []).append((sid, g))
    return out


def givers(tag):
    """그 태그를 줄 수 있는 체계 [(체계, [갈래])]."""
    out = {}
    for sid, g in used().get(tag, []):
        out.setdefault(sid, []).append(g)
    return list(out.items())


# ───────── 겹쳐 보이기 읽기 ─────────
def has(tid, tag):
    """(True 붙음 | False 판정은 났는데 안 붙음 | None 판정 없음·대기, 근거) — 그 태그를 줄 수 있는 체계의 지금 판정.
    공지 필터 꽁돈(일정 줄 #꽁돈 · 판정표 · 수집 창 한 줄 · 모아보기 꽁돈 칸)이 sort_collect.gold_from_ledger 로 부른다 —
    옛 sort.tag_of 와 같은 셈(체계 파일 이름 차례 · 처음 판정 난 체계)이라 출력 바이트 같음(골든)."""
    for sid, s in sort.systems().items():
        if s.get('_err') or not any({'태그': tag} in (b.get('동작') or []) for b in (s.get('갈래') or {}).values()):
            continue
        rec = sort.state_item(sid, tid)
        if rec and rec.get('갈래') is not None:
            return tag in sort.tags(rec), rec.get('근거', '')
    return None, ''


def attached():
    """지금 붙은 태그 {태그: [(체계, 대상)]} — 분류 상태(켠 체계만 · 꺼진 체계의 옛 판정은 안 셈)."""
    out = {}
    for sid, s in sort.systems().items():
        if s.get('_err') or s.get('켬', True) is False:
            continue
        for tid, rec in sort.state(sid)['items'].items():
            for t in sort.tags(rec):
                out.setdefault(t, []).append((sid, tid))
    return out


def problems():
    D, out = dictionary(), []
    if not os.path.exists(dict_path()):
        out.append(f'사전 없음 — {os.path.relpath(dict_path(), VAULT)} (빈 틀 = 3_시스템/sort-examples/태그/사전.json)')
    for name, e in D.items():
        if not isinstance(e, dict):
            out.append(f'{name}: 칸은 {{뜻, 순서, 가족, 보임}}')
            continue
        if not TAG_RX.match(name):
            out.append(f'{name}: 태그 이름으로 못 씀(빈칸·#·/·따옴표 등)')
        if not str(e.get('뜻') or '').strip():
            out.append(f'{name}: 뜻 없음')
        if '순서' in e and not (isinstance(e['순서'], int) and not isinstance(e['순서'], bool)):
            out.append(f'{name}: 순서 는 정수')
        fam = e.get('가족')
        if fam is not None and not (isinstance(fam, list) and fam and len(set(fam)) == len(fam)
                                    and all(isinstance(x, str) and TAG_RX.match(x) for x in fam)):
            out.append(f'{name}: 가족 은 겹치지 않는 값 목록(앞이 높음)')
    for t, where in sorted(used().items()):
        fam, val = split(t, D)
        who = ' · '.join(sorted({sid for sid, _ in where}))
        if val is None and t not in D:
            out.append(f'«{t}» 사전에 없음 — 쓰는 체계 {who}')
        elif val is not None and val not in D[fam]['가족']:
            out.append(f'«{t}» 가족 {fam} 에 없는 값 — 쓰는 체계 {who}')
        if not all(TAG_RX.match(x) for x in t.split('/', 1)):
            out.append(f'«{t}» 태그 이름으로 못 씀 — 쓰는 체계 {who}')
    return out


def listing():
    D, U, A, S = dictionary(), used(), attached(), sort.systems()
    rows = []
    names = sorted(D, key=lambda k: ((D[k] or {}).get('순서', 99) if isinstance(D[k], dict) else 99, k))
    for t in sorted(U):
        fam, _ = split(t, D)
        if fam not in names:
            names.append(fam)
    for name in names:
        e = D.get(name) if isinstance(D.get(name), dict) else {}
        mine = sorted(t for t in U if split(t, D)[0] == name)
        sysw = {}
        for t in mine:
            for sid, g in U[t]:
                sysw.setdefault(sid, set()).add(g)
        rows.append({'태그': name, '뜻': e.get('뜻', ''), '순서': e.get('순서'), '가족': e.get('가족'), '보임': e.get('보임', ''),
                     '쓰는 체계': [{'체계': sid, '켬': (S.get(sid) or {}).get('켬', True) is not False,
                                 '노트에 쓰기': (S.get(sid) or {}).get('노트에 쓰기') is True, '갈래': sorted(gs)} for sid, gs in sorted(sysw.items())],
                     '지금 붙음': {t: len(A.get(t, [])) for t in mine}})
    st = load_state()
    return {'사전': os.path.relpath(dict_path(), VAULT).replace(os.sep, '/'), '태그': rows,
            '노트에 붙인 것': sum(len(v) for v in st['붙임'].values()), '문제': problems()}


# ───────── 노트 프론트매터 ─────────
FM = re.compile(r'\A(﻿?)---(\r?\n)(.*?)(\r?\n)---[ \t]*(?=\r?\n|\Z)', re.S)
KEY = re.compile(r'^tags:[ \t]*(.*?)[ \t]*$')
ITEM = re.compile(r'^([ \t]*)-[ \t]+(.*?)[ \t]*$')


def _clean(x):
    return x.strip().strip('"\'').lstrip('#')


def _fm(text):
    """(머리 앞, 줄바꿈, 프론트매터 줄들, 머리 뒤) · 프론트매터 없으면 None."""
    m = FM.match(text)
    if not m:
        return None
    return text[:m.start(3)], m.group(2), m.group(3).split(m.group(2)) if m.group(3) else [], text[m.end(3):]


def _find(lines):
    """(tags 줄 번호 | None, 흐름 목록 값 | None, 목록 줄 번호들)."""
    for i, ln in enumerate(lines):
        k = KEY.match(ln)
        if not k:
            continue
        v = k.group(1)
        if v.startswith('[') != v.endswith(']'):
            raise ValueError('tags 가 여러 줄 흐름 목록 — 못 고치는 꼴')
        items = []
        j = i + 1
        while j < len(lines) and ITEM.match(lines[j]):
            items.append(j)
            j += 1
        return i, v, items
    return None, None, []


def fm_tags(text):
    """프론트매터 tags 목록(# · 따옴표 뗀 값) · 프론트매터 없음·못 고치는 꼴(여러 줄 흐름 목록)이면 None."""
    p = _fm(text)
    if p is None:
        return None
    lines = p[2]
    try:
        i, v, items = _find(lines)
    except ValueError:
        return None
    if i is None:
        return []
    if v:
        body = v[1:-1] if v.startswith('[') and v.endswith(']') else v
        return [_clean(x) for x in body.split(',') if _clean(x)]
    return [_clean(ITEM.match(lines[j]).group(2)) for j in items if _clean(ITEM.match(lines[j]).group(2))]


def has_key(text):
    """프론트매터에 tags 칸이 있나(도구가 칸까지 만들었으면 뗄 때 칸도 지워 원래 바이트로)."""
    p = _fm(text)
    return p is not None and any(KEY.match(ln) for ln in p[2])


def fm_set(text, tag, on, drop_key=False):
    """tags 에 태그를 넣은(on)·뺀 글 — 바뀔 것이 없으면 같은 글 · 프론트매터 없으면 None. 다른 줄·줄바꿈(CRLF)은 그대로.
    drop_key = 빼고 나서 목록이 비면 tags 칸 줄도 지움(도구가 칸을 만들었을 때)."""
    p = _fm(text)
    if p is None:
        return None
    head, nl, lines, tail = p
    have = fm_tags(text)
    if have is None:
        return None
    if (tag in have) == on:
        return text
    lines = list(lines)
    i, v, items = _find(lines)
    if i is None:
        lines.append(f'tags: [{tag}]')
    elif v:
        body = v[1:-1] if v.startswith('[') and v.endswith(']') else v
        toks = [x.strip() for x in body.split(',') if x.strip()]
        toks = toks + [tag] if on else [x for x in toks if _clean(x) != tag]
        if toks or not drop_key:
            lines[i] = 'tags: [' + ', '.join(toks) + ']'
        else:
            del lines[i]
    elif on:
        ind = ITEM.match(lines[items[-1]]).group(1) if items else '  '
        lines.insert((items[-1] if items else i) + 1, f'{ind}- {tag}')
    else:
        left = [j for j in items if _clean(ITEM.match(lines[j]).group(2)) != tag]
        for j in reversed(items):
            if _clean(ITEM.match(lines[j]).group(2)) == tag:
                del lines[j]
        if drop_key and not left:
            del lines[i]
    return head + nl.join(lines) + tail


def note_of(s, tid):
    """노트에 쓸 자리(볼트 상대 .md) — 어댑터 note(대상) 또는 «note:<경로>» · 0_작업·2_지식 안만 · 1_수집 원본·그 밖은 None(겹쳐 보이기만)."""
    ad = sort.adapter((s.get('대상') or {}).get('종류'))
    p = ad.note(tid) if ad is not None and hasattr(ad, 'note') else (tid[5:] if tid.startswith('note:') else None)
    if not isinstance(p, str) or not p:
        return None
    p = p.replace('\\', '/').lstrip('/')
    import roles
    roots = [roles.path('work'), roles.path('knowledge')]
    if not p.endswith('.md') or '..' in p.split('/') or p.startswith(roles.path('sources') + '/') \
            or not any(p.startswith(r + '/') for r in roots):
        return None
    return p


def _write(a, text):
    with open(a + '.tag-tmp', 'w', encoding='utf-8', newline='') as f:
        f.write(text)
    os.replace(a + '.tag-tmp', a)


def _note(p, t, on, owner, st, now, dry):
    """노트 하나·태그 하나를 맞춤 → 한 일(붙임 · 뗌 · 사람 것 · 노트 없음 · 프론트매터 없음 · None = 할 것 없음).
    붙임[p][t] = {"주인": [[체계, 대상]…], "시각"} — 주인이 다 빠질 때만 노트에서 뗀다(같은 태그를 두 판정이 주는 경우)."""
    a = os.path.join(VAULT, *p.split('/'))
    book = st['붙임'].setdefault(p, {})
    rec = book.get(t)
    mine = rec is not None and owner in rec['주인']
    if not on and not mine:
        return None
    try:
        text = open(a, encoding='utf-8', newline='').read()
    except OSError:
        text = None
    if not on:
        rec['주인'].remove(owner)
        if rec['주인']:
            return None
        del book[t]
        if text is None or t not in (fm_tags(text) or []):
            return '장부만 지움'                            # 노트가 없어졌거나 사람이 이미 뗌
        if not dry:
            _write(a, fm_set(text, t, False, drop_key=rec.get('키 만듦', False)))
        return '뗌'
    if text is None:
        return '노트 없음'
    have = fm_tags(text)
    if have is None:
        return '프론트매터 없음'
    if rec is not None:
        if not mine:
            rec['주인'].append(owner)
        if t in have:
            return None
    elif t in have:
        return '사람 것'                                   # 사람이 먼저 단 태그 — 적지 않으니 떼지도 않는다
    if not dry:
        _write(a, fm_set(text, t, True))
    book[t] = rec or {'주인': [owner], '시각': now, **({} if has_key(text) else {'키 만듦': True})}
    return '붙임'


# ───────── 맞추기 ─────────
def load_state():
    try:
        d = json.load(open(ix(STATE), encoding='utf-8'))
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    d.setdefault('커서', 0)
    d.setdefault('붙임', {})
    return d


def sync(all_=False, dry=False, now=None):
    """넘김 장부의 새 붙임·뗌(커서 뒤)을 보이는 자리에 맞춘다 → {한 일: 수}. 노트 쓰기를 켠 체계만 파일을 쓴다 — 나머지는 «겹쳐 보이기»(셈만).
    all_ = 장부 처음부터 + 노트 쓰기 켠 체계의 모든 대상 + 붙인 장부 전부(체계가 노트 쓰기를 껐으면 도구가 붙인 것을 뗌)."""
    now = now or stamp()
    st = load_state()
    rows, cur = sort.handoffs(st['커서'], all_)
    S = sort.systems()
    pairs = {(e['체계'], e['대상']) for e in rows if '태그' in e['동작'] or '떼기' in e['동작']}
    if all_:
        for sid, s in S.items():
            if not s.get('_err') and s.get('노트에 쓰기') is True:
                pairs |= {(sid, t) for t in sort.state(sid)['items']}
        pairs |= {tuple(o) for b in st['붙임'].values() for r in b.values() for o in r['주인']}
    cnt, logs = Counter(), []
    for sid, tid in sorted(pairs):
        s = S.get(sid) or {}
        on = not s.get('_err') and s.get('켬', True) is not False and s.get('노트에 쓰기') is True
        ours = sorted({(p, t) for p, b in st['붙임'].items() for t, r in b.items() if [sid, tid] in r['주인']})
        if not on and not (all_ and ours):
            cnt['겹쳐 보이기'] += 1                        # 수집글·가격줄 · 노트 쓰기 끔 — 읽는 쪽이 has() 로 지금 판정을 본다
            continue
        path = note_of(s, tid) if on else None
        if on and not path:
            cnt['쓸 자리 없음'] += 1                        # 1_수집 원본 · 노트가 아닌 대상 — 겹쳐 보이기만
        want = set(sort.tags(sort.state_item(sid, tid))) if path else set()
        todo = [(p, t, False) for p, t in ours if p != path or t not in want] + [(path, t, True) for t in sorted(want)]
        for p, t, flag in todo:
            did = _note(p, t, flag, [sid, tid], st, now, dry)
            if did:
                cnt[did] += 1
                logs.append({'시각': now, '체계': sid, '대상': tid, '자리': p, '태그': t, '한 일': did})
    st['붙임'] = {p: b for p, b in st['붙임'].items() if b}
    st['커서'] = cur
    if not dry:
        sort.write_if_changed(ix(STATE), st)
        sort.append_lines(ix(LOG), logs)
    return dict(cnt)


def tick():
    """15분 확인 끝(collect-tick act_tick) — 노트를 바꾼 때만 한 줄(나머지는 빈 글)."""
    r = sync()
    return ' · '.join(f'{k} {r[k]}' for k in ('붙임', '뗌', '노트 없음', '프론트매터 없음') if r.get(k))


# ───────── 사람 태그 ─────────
def apply(tid, tag, off=False, why='', system=None, by=None, now=None, redraw=True):
    """사람이 «이거 꽁돈»(off = «꽁돈 아님») — 그 태그를 주는 체계에 판정자 «사람» 판정(sort.answer) → 노트 맞춤 → 겹쳐 보이기 다시 그림(어댑터 refresh).
    갈래: 붙이기 = 그 태그를 주는 갈래(하나여야) · 떼기 = 그 태그가 없는 갈래 중 «모르면» · 아니면 하나뿐인 것."""
    gs = givers(tag)
    if system:
        gs = [x for x in gs if x[0] == system]
    if not gs:
        raise ValueError(f'«{tag}» 를 주는 체계 없음' + (f'(--system {system})' if system else '') + ' — 체계 «갈래» 동작에 먼저 넣는다(sort.rule)')
    if len(gs) > 1:
        raise ValueError(f'«{tag}» 를 주는 체계가 여럿: {" · ".join(x[0] for x in gs)} — --system 으로 고름')
    sid, branches = gs[0]
    s = sort.systems()[sid]
    if off:
        cand = [g for g in s.get('갈래') or {} if g not in branches]
        g = s.get('모르면') if s.get('모르면') in cand else (cand[0] if len(cand) == 1 else None)
    else:
        g = branches[0] if len(branches) == 1 else None
    if g is None:
        raise ValueError(f'{sid}: 고를 갈래가 하나가 아님 — {" · ".join(s.get("갈래") or {})}')
    say = why or (f'사람 «{tag} 아님»' if off else f'사람 «이거 {tag}»')
    if by:
        say += f' ({by})'
    run = sort.answer(sid, tid, g, '사람', say, now)
    notes = sync(now=now)
    ad = sort.adapter((s.get('대상') or {}).get('종류'))
    drew = ad.refresh() if redraw and ad is not None and hasattr(ad, 'refresh') else None
    return {'체계': sid, '대상': tid, '갈래': g, '근거': say, '판정': run.get(sid), '노트': notes, '다시 그림': drew}


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser(description='태그 도구 — 분류가 정한 태그를 보이는 자리에')
    ap.add_argument('cmd', choices=['list', 'has', 'sync', 'apply', 'tick'])
    ap.add_argument('target', nargs='?')
    ap.add_argument('tag', nargs='?')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--all', action='store_true', help='sync: 장부 처음부터 + 전부 다시 맞춤')
    ap.add_argument('--dry', action='store_true', help='sync: 쓰지 않음')
    ap.add_argument('--off', action='store_true', help='apply: «아님»(태그 없는 갈래)')
    ap.add_argument('--why', default='', help='apply: 근거(비우면 «사람 «이거 <태그>»»)')
    ap.add_argument('--system', help='apply: 그 태그를 주는 체계가 여럿일 때')
    ap.add_argument('--by', help='apply: 누가(brain.py {by})')
    ap.add_argument('--no-redraw', action='store_true', help='apply: 겹쳐 보이기 다시 그리기(공지 필터 judge)를 안 함')
    a = ap.parse_args()
    if a.cmd == 'list':
        d = listing()
        if a.json:
            print(json.dumps(d, ensure_ascii=False, indent=1))
            return 0
        print(f'태그 사전 {d["사전"]}')
        for r in d['태그']:
            fam = f' (가족 {" > ".join(r["가족"])})' if r['가족'] else ''
            sw = ' · '.join(f'{x["체계"]}{"" if x["켬"] else "(끔)"}{" · 노트에 씀" if x["노트에 쓰기"] else ""}' for x in r['쓰는 체계']) or '없음'
            now_on = sum(r['지금 붙음'].values())
            print(f'- {r["태그"]}{fam} — {r["뜻"] or "(뜻 없음)"} · 쓰는 체계 {sw} · 지금 붙음 {now_on}' + (f' · 보임 {r["보임"]}' if r['보임'] else ''))
        print(f'노트에 붙인 것 {d["노트에 붙인 것"]} · 문제 {len(d["문제"])}' + ''.join(f'\n  ✗ {p}' for p in d['문제']))
        return 0
    if a.cmd == 'has':
        if not (a.target and a.tag):
            sys.exit('has <대상> <태그>')
        v, why = has(a.target, a.tag)
        print(json.dumps({'붙음': v, '근거': why}, ensure_ascii=False))
        return 0
    if a.cmd == 'sync':
        print(json.dumps(sync(a.all, a.dry), ensure_ascii=False))
        return 0
    if a.cmd == 'tick':
        out = tick()
        if out:
            print(out)
        return 0
    if not (a.target and a.tag):
        sys.exit('apply <대상> <태그> [--off]')
    try:
        print(json.dumps(apply(a.target, a.tag, a.off, a.why, a.system, a.by, redraw=not a.no_redraw), ensure_ascii=False))
    except (ValueError, RuntimeError) as e:
        sys.exit(f'apply: {e}')
    return 0


if __name__ == '__main__':
    sys.modules.setdefault('tag', sys.modules['__main__'])
    sys.exit(main())
