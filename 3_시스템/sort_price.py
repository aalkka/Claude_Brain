"""분류 어댑터 «가격줄» + 알림 사건 꼴(범용 도구 셋 S2 준비 · 2026-11-18 · 설계 §2 대상 어댑터 · §7 · §8.6).

대상 = 가격 조회 가족(collect_price)이 마지막으로 성공한 돌림의 가격줄 — id · 사실(가격줄 그대로) · 자리(출처 label).
분류 엔진에 잇는 길: sort.py ADAPTERS 에 '가격줄': 'sort_price' 한 줄. 지금은 안 잇는다(S2 준비 · sort.py 는 다른 일꾼 몫) —
시험은 sort.register_adapter('가격줄', sort_price) 로 끼운다.

알림 도구(alert.py · S9 11-18)가 이 어댑터의 rank(갈래) · alert_key(대상) · alert_event(…)['폰'] 의 제목·글을 쓴다(때·중복·전달은 알림 도구 몫).
알림 사건(이 파일은 어디에도 보내지 않는다): alert_event(판정 기록, 가격줄 사실, 지금) → 사건 하나.
  티어 · 급함 · 때(바로 | 아침) · 보낼 시각 · 가는 편·오는 편(날짜·시각·시각대·항공사·편명) · 박 · 1인가 · 2인가 · 2인 확인 · 위탁 · 링크 · 본 시각 ·
  중복 열쇠 · 폰(mobility 알림 사건 꼴 {id, at, title, text, made, open} — 잇기 때 kind «sort» 로 넘김).
  잘 시간(설계 §7 · 알림-설정 잘_시간 기본 23:00~08:00)에는 급함이 아니면 아침으로 · 급함(SSS)은 밤에도 바로.
  중복(설계 §8.6): 같은 표·같은 티어는 한 번 · 티어가 오르면 다시 · 내려가면 안 울림 · 사라졌다 다시 나오면 새 표(부르는 쪽이 울린 표에서 뺌).
"""
import datetime as dt
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect_price as cp  # noqa: E402

TIER_RANK = {'C': 1, 'B': 2, 'A': 3, 'S': 4, 'SS': 5, 'SSS': 6}
SLEEP = ('23:00', '08:00')
WEEK = '월화수목금토일'


# ───────── 어댑터(sort 가 부름) ─────────
def items():
    for rid in sorted(cp.recipes()):
        for r in cp.rows_of(rid):
            yield {'id': r['id'], 'facts': r, '글자': 0, 'raw': {'recipe': rid}}


def match(item, spec):
    """대상 칸 — 출처 = {label | id | 제공: 값}(모두 같아야) · 모르는 칸은 안 맞음(sort_collect 와 같음)."""
    src = item['facts'].get('출처') or {}
    for k, v in spec.items():
        if k != '출처' or not isinstance(v, dict) or any(src.get(kk) != vv for kk, vv in v.items()):
            return False
    return True


def place(item):
    return (item['facts'].get('출처') or {}).get('label')


# ───────── 알림 사건(정의만) ─────────
def _hm(s):
    h, m = s.split(':')
    return int(h) * 60 + int(m)


def asleep(t, sleep=SLEEP):
    a, b, m = _hm(sleep[0]), _hm(sleep[1]), t.hour * 60 + t.minute
    return a != b and ((a <= m or m < b) if a > b else (a <= m < b))


def next_clock(t, hhmm):
    h, m = map(int, hhmm.split(':'))
    x = t.replace(hour=h, minute=m, second=0, microsecond=0)
    return x if x > t else x + dt.timedelta(days=1)


def won(v):
    return f'{v / 10000:.1f}'.rstrip('0').rstrip('.') + '만'


def day_text(d):
    x = dt.date.fromisoformat(d)
    return f'{x.month}/{x.day}({WEEK[x.weekday()]})'


def leg_text(g):
    fl = '' if g.get('편명') in (None, '모름') else f' {g.get("항공사", "")}{g["편명"]}'
    return f'{day_text(g["날짜"])} {g["출발시각대"]} {g["시각"]}{fl}'


def ms(t):
    return int(t.timestamp() * 1000)


def alert_event(rec, facts, now, sleep=SLEEP):
    """판정 기록(sort.record 꼴: 대상·체계·갈래·급함·동작) + 가격줄 사실 → 알림 사건. 알림 동작이 없는 갈래(버림)면 None."""
    al = next((a['알림'] for a in rec.get('동작') or [] if isinstance(a.get('알림'), dict)), None)
    if al is None:
        return None
    tier, urgent = rec['갈래'], rec.get('급함') is True
    want = al.get('때', '바로')
    if urgent:                                        # 급함 = 잘 시간·묶음을 건너뜀(설계 §7)
        send, word = now, '바로'
    elif want.startswith('묶음 '):
        send, word = next_clock(now, want[3:]), want
    elif want == '아침' or asleep(now, sleep):
        send, word = next_clock(now, sleep[1]), '아침'
    else:
        send, word = now, '바로'
    go, back = facts['가는편'], facts['오는편']
    two = '' if facts.get('2인 확인') else ' · 2인 확인 전'
    title = f'{tier} 항공권 · 2인 {won(facts["2인가"])}{two}'
    text = f'{leg_text(go)} → {leg_text(back)} · {facts["박"]}박 · 위탁 {facts.get("위탁", "모름")}'
    key = f'{rec["대상"]}|{tier}'
    return {'종류': 'sort', '체계': rec['체계'], '대상': rec['대상'], '티어': tier, '급함': urgent,
            '때': word,
            '보낼 시각': send.isoformat(timespec='minutes'),
            '가는편': {k: go.get(k) for k in ('날짜', '시각', '출발시각대', '항공사', '편명', '경유')},
            '오는편': {k: back.get(k) for k in ('날짜', '시각', '출발시각대', '항공사', '편명', '경유')},
            '박': facts['박'], '1인가': facts['1인가'], '2인가': facts['2인가'], '2인 확인': bool(facts.get('2인 확인')),
            '통화': facts.get('통화'), '위탁': facts.get('위탁', '모름'), '링크': facts.get('링크'), '본 시각': facts.get('본 시각'),
            '중복 열쇠': key,
            '폰': {'id': 'ev-sort-' + hashlib.sha1(key.encode('utf-8')).hexdigest()[:12], 'at': ms(send), 'title': title, 'text': text,
                   'made': ms(now), **({'open': facts['링크']} if facts.get('링크') else {})}}


def alert_due(sent, rec):
    """울릴 차례인가 — sent = {대상: 이미 울린 가장 높은 티어}. 처음 · 티어 오름 = 참 · 같음·내림·티어 아님 = 거짓."""
    t = rec.get('갈래')
    if t not in TIER_RANK:
        return False
    old = sent.get(rec['대상'])
    return old is None or TIER_RANK[t] > TIER_RANK.get(old, 0)


def rank(branch):
    """알림 도구의 «갈래가 오르면 다시» 순위 — 티어(C 1 … SSS 6) · 버림 등 티어 아님 = None."""
    return TIER_RANK.get(branch)


def alert_key(item):
    """한 돌림에 여럿일 때 같은 티어 안 차례 — 싼 것부터(order 와 같음)."""
    v = ((item or {}).get('facts') or {}).get('2인가')
    return v if isinstance(v, (int, float)) else float('inf')


def order(events):
    """한 돌림에 여럿이면 폰 한 알림에 «k / n» — 티어 높은 것부터, 같으면 싼 것부터."""
    return sorted(events, key=lambda e: (-TIER_RANK.get(e['티어'], 0), e['2인가'], e['대상']))
