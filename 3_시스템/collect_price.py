"""가격 조회 가족 — 공개 가격 API 를 결정적으로 다시 묻고 «가격줄»을 낸다(범용 도구 셋 S2 준비 · 2026-11-18 · 설계 = 제작자 설계 노트(배포판에 없음) §8.3).

수집 엔진의 한 가족이다(웹 엔진 web-collect 의 regex·rss 와 나란히). 출처마다 다른 것은 **조리법 데이터**(노선·기간·박·직항·통화·상한),
같은 것은 **엔진**(묻기·짝짓기·상한·장부). 제공자(provider) 코드는 응답 꼴을 가격줄로 옮기는 일만 한다 — 지금은 travelpayouts 하나.

비용 0(사용자 11-18 03:1x «단 비용이 들지 않게»): 유료 API·유료 등급을 부르는 길이 코드에 없다. 받을 수 있는 호스트는 ALLOWED 뿐이고,
  네트워크 함수는 GET 하나다. 출처마다 상한 = 조리법 «상한»(분 = 무료 한도의 절반 · 하루 = 계획의 두 배) — 넘으면 멈추고 상태 «한도».
키: 개인 층 파일 3_시스템/collect-price.local.json(git 제외 · 3_시스템/*.local.json) — {"travelpayouts": {"token": "…"}}.
  없거나 비면 조용히 상태 «키 없음»(망 요청 0 · 대기열 줄 0). 토큰은 머리글(X-Access-Token)로만 보내고 장부·로그에 남기지 않는다.
층: 조리법 = 3_시스템/collect/price/<id>.json(하위 폴더 = 웹 엔진의 collect/*.json 에 안 걸림 · 수집 창에 안 뜸)
    장부 = 3_시스템/_index/collect/price/<id>/ — 상태.json(지금 상태) · 가격줄.json(마지막으로 성공한 돌림의 줄 · 분류 어댑터 sort_price 가 읽음)
           호출.jsonl(망 요청 한 줄씩 · 상한 셈) · 장부.jsonl(돌림마다 날짜 쌍별 최저 · 가격선 다시맞춤 자료 — 지금은 쌓기만).
진짜 수집에 안 잇는다(S2 준비): 예약·15분 확인·수집 창 어디서도 부르지 않는다. 조리법 «켬»이 false 면 --force 없이는 안 돈다.

  py -3 3_시스템/collect_price.py --plan <id>            # 물을 것만(망 요청 0 · 키를 안 읽음)
  py -3 3_시스템/collect_price.py --source <id> [--force] # 한 번 돌림(켬 · 키 · 상한을 지킴)
  py -3 3_시스템/collect_price.py --status               # 출처별 지금 상태
"""
import argparse
import datetime as dt
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

SYS = os.path.dirname(os.path.abspath(__file__))
RECIPES = os.path.join(SYS, 'collect', 'price')
STATE = os.path.join(SYS, '_index', 'collect', 'price')
SECRETS = os.path.join(SYS, 'collect-price.local.json')
ALLOWED = {'api.travelpayouts.com'}           # 받을 수 있는 호스트 전부 — 유료 API 호스트는 여기에 없다
UA = 'BrainCollector/0.2 (+price family)'
GAP = 1.0                                     # 요청 사이 최소 간격(초)
TRANSPORT = None                              # 시험이 바꿔 끼움: f(url, headers) → (상태 코드, 본문 bytes, 머리글 dict) · None = urllib
NOW = None                                    # 시험이 바꿔 끼움: () → datetime
TIERS = ('새벽', '오전', '오후')               # 출발 시각대(사용자 낱말 셋) — 새벽 00~06 · 오전 06~12 · 오후 12~24


class Stop(Exception):
    """이 돌림을 멈춤 — 상태 낱말(키 없음 · 키 틀림 · 한도 · 오류 · 통화 다름)과 까닭."""
    def __init__(self, state, why=''):
        super().__init__(f'{state}: {why}')
        self.state, self.why = state, why


def now():
    return NOW() if NOW else dt.datetime.now().astimezone()


def stamp(t=None):
    return (t or now()).strftime('%Y-%m-%dT%H:%M:%S')


# ───────── 조리법 · 키 ─────────
def recipes():
    out = {}
    if os.path.isdir(RECIPES):
        for f in sorted(os.listdir(RECIPES)):
            if f.endswith('.json'):
                try:
                    rc = json.load(open(os.path.join(RECIPES, f), encoding='utf-8'))
                except ValueError:
                    continue
                if isinstance(rc, dict) and rc.get('id') == f[:-5] and rc.get('family') == 'price':
                    out[rc['id']] = rc
    return out


def secret(provider):
    """개인 층 키 — 없거나 비면 None(«키 없음»). 이 함수만 키 파일을 읽는다."""
    try:
        d = json.load(open(SECRETS, encoding='utf-8'))
    except (OSError, ValueError):
        return None
    tok = ((d or {}).get(provider) or {}).get('token') if isinstance(d, dict) else None
    return tok.strip() if isinstance(tok, str) and tok.strip() else None


# ───────── 장부 ─────────
def sdir(rid):
    return os.path.join(STATE, rid)


def write_json(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(p + '.tmp', p)


def append(p, rows):
    if rows:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'a', encoding='utf-8', newline='\n') as f:
            f.writelines(json.dumps(r, ensure_ascii=False) + '\n' for r in rows)


def calls(rid):
    try:
        return [json.loads(ln) for ln in open(os.path.join(sdir(rid), '호출.jsonl'), encoding='utf-8') if ln.strip()]
    except OSError:
        return []


def set_state(rid, state, **more):
    d = {'상태': state, '시각': stamp(), **more}
    write_json(os.path.join(sdir(rid), '상태.json'), d)
    return d


def status():
    out = {}
    for rid in recipes():
        try:
            out[rid] = json.load(open(os.path.join(sdir(rid), '상태.json'), encoding='utf-8'))
        except (OSError, ValueError):
            out[rid] = {'상태': '안 돎'}
    return out


# ───────── 망(GET 하나 · 허용 호스트만 · 상한) ─────────
_last = [0.0]


def get(rid, rc, url, headers):
    host = urllib.parse.urlsplit(url).hostname
    if host not in ALLOWED:
        raise Stop('오류', f'허용 밖 호스트 {host}')
    cap = rc.get('상한') or {}
    t = now()
    done = calls(rid)
    day = sum(1 for c in done if c.get('시각', '')[:10] == stamp(t)[:10])
    minute = sum(1 for c in done if c.get('시각', '') >= stamp(t - dt.timedelta(seconds=60)))
    if day >= int(cap.get('하루', 0)):
        raise Stop('한도', f'하루 {day}/{cap.get("하루", 0)}')
    if minute >= int(cap.get('분', 0)):
        raise Stop('한도', f'분 {minute}/{cap.get("분", 0)}')
    if TRANSPORT is None:
        wait = GAP - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
    row = {'시각': stamp(t), '주소': url}            # 토큰은 머리글로만 보낸다 — 주소에 없다
    try:
        if TRANSPORT is not None:
            code, body, hdr = TRANSPORT(url, headers)
        else:
            req = urllib.request.Request(url, headers=headers, method='GET')
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    code, body, hdr = r.status, r.read(), dict(r.headers)
            except urllib.error.HTTPError as e:
                code, body, hdr = e.code, e.read() or b'', dict(e.headers or {})
            _last[0] = time.time()
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        append(os.path.join(sdir(rid), '호출.jsonl'), [{**row, '코드': None}])
        raise Stop('오류', f'망 {type(e).__name__}')
    append(os.path.join(sdir(rid), '호출.jsonl'), [{**row, '코드': code, '남음': (hdr or {}).get('X-Rate-Limit-Remaining')}])
    if (hdr or {}).get('Content-Encoding', '').lower() == 'gzip':
        body = gzip.decompress(body)
    if code in (401, 403):
        raise Stop('키 틀림', f'HTTP {code}')
    if code == 429:
        raise Stop('한도', 'HTTP 429(제공자 분당 한도)')
    if code != 200:
        raise Stop('오류', f'HTTP {code}')
    try:
        return json.loads(body.decode('utf-8'))
    except ValueError:
        raise Stop('오류', 'JSON 아님')


# ───────── 날짜 · 시각 ─────────
def tz_of(rc):
    s = rc.get('시간대') or '+09:00'
    sign = -1 if s[0] == '-' else 1
    h, m = s.lstrip('+-').split(':')
    return dt.timezone(sign * dt.timedelta(hours=int(h), minutes=int(m)))


def local(ts, tz):
    """ISO 시각 → 조리법 시간대의 벽시계(공항 둘 다 같은 시간대일 때 · 인천·신치토세 = +09:00). 시간대가 없으면 그대로 읽는다."""
    t = dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
    return t.astimezone(tz) if t.tzinfo else t


def band(t):
    return '새벽' if t.hour < 6 else '오전' if t.hour < 12 else '오후'


def months(a, b):
    y, m = int(a[:4]), int(a[5:7])
    out = []
    while f'{y:04d}-{m:02d}' <= b[:7]:
        out.append(f'{y:04d}-{m:02d}')
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


# ───────── 제공자: travelpayouts(Aviasales Data API v3 prices_for_dates) ─────────
# 문서 = support.travelpayouts.com/hc/en-us/articles/203956163(11-12 판) · 한도 = …/4402565416594(분당 600 · 하루 값 없음).
# 응답 = {"success", "data": [{origin, destination, origin_airport, destination_airport, price, airline, flight_number,
#          departure_at, return_at, transfers, return_transfers, duration, duration_to, duration_back, link}], "currency"}
# 값 = 최근 48시간 Aviasales 사용자 검색 캐시(묵을 수 있음) · 1인 · 위탁 수하물 칸 없음 · 왕복 줄은 오는 편 편명이 없음.
TP_PATH = 'https://api.travelpayouts.com/aviasales/v3/prices_for_dates'


def tp_queries(rc):
    """물을 것 — 편도 가는·오는 × 달 + (왕복도) 왕복 달 쌍(가는 달 ≤ 오는 달). 토큰은 넣지 않는다(머리글)."""
    a, b = rc['기간']
    ms = months(a, b)
    base = {'currency': rc.get('통화', 'krw'), 'direct': 'true' if rc.get('직항만') else 'false', 'sorting': 'price',
            'unique': 'false', 'limit': str(rc.get('쪽당', 1000)), 'page': '1'}
    if rc.get('market'):
        base['market'] = rc['market']
    q = []
    for way, (o, d) in (('가는', rc['노선']['가는']), ('오는', rc['노선']['오는'])):
        for m in ms:
            q.append({'꼴': '편도', '방향': way, 'params': {**base, 'origin': o, 'destination': d, 'departure_at': m, 'one_way': 'true'}})
    if rc.get('왕복도', True):
        o, d = rc['노선']['가는']
        for i, m1 in enumerate(ms):
            for m2 in ms[i:]:
                q.append({'꼴': '왕복', '방향': '왕복', 'params': {**base, 'origin': o, 'destination': d, 'departure_at': m1, 'return_at': m2, 'one_way': 'false'}})
    return q


def tp_url(params):
    return TP_PATH + '?' + urllib.parse.urlencode(params)


def tp_leg(x, rc, tz, back=False):
    """응답 한 줄 → 다리 하나(가는 편은 departure_at, 왕복 줄의 오는 편은 return_at)."""
    t = local(x['return_at'] if back else x['departure_at'], tz)
    o, d = (x.get('destination'), x.get('origin')) if back else (x.get('origin'), x.get('destination'))
    return {'날짜': t.date().isoformat(), '시각': t.strftime('%H:%M'), '출발시각대': band(t),
            '출발': (x.get('destination_airport') if back else x.get('origin_airport')) or o,
            '도착': (x.get('origin_airport') if back else x.get('destination_airport')) or d,
            '항공사': x.get('airline') or '모름', '편명': '모름' if back else (str(x.get('flight_number') or '') or '모름'),
            '경유': int(x.get('return_transfers' if back else 'transfers') or 0)}


def tp_parse(resp, q, rc, tz):
    """응답 하나 → (다리 목록 | 왕복 줄 목록). 통화가 조리법과 다르면 멈춤(값을 잘못 읽지 않게)."""
    if not isinstance(resp, dict) or resp.get('success') is not True:
        raise Stop('오류', f'success 아님 — {str((resp or {}).get("error"))[:80]}')
    cur = resp.get('currency')
    if cur and cur.lower() != rc.get('통화', 'krw').lower():
        raise Stop('통화 다름', f'{cur} ≠ {rc.get("통화")}')
    out = []
    for x in resp.get('data') or []:
        if not isinstance(x, dict) or not isinstance(x.get('price'), (int, float)) or not x.get('departure_at'):
            continue
        link = 'https://www.aviasales.com' + x['link'] if str(x.get('link', '')).startswith('/') else x.get('link')
        if q['꼴'] == '편도':
            out.append({'다리': tp_leg(x, rc, tz), '값': int(round(x['price'])), '링크': link})
        elif x.get('return_at'):
            out.append({'가는편': tp_leg(x, rc, tz), '오는편': tp_leg(x, rc, tz, back=True), '1인가': int(round(x['price'])), '링크': link})
    return out


PROVIDERS = {'travelpayouts': {'queries': tp_queries, 'url': tp_url, 'parse': tp_parse, 'host': 'api.travelpayouts.com',
                               'headers': lambda tok: {'X-Access-Token': tok, 'Accept-Encoding': 'gzip, deflate', 'Accept': 'application/json', 'User-Agent': UA}}}


# ───────── 짝짓기 · 가격줄 ─────────
def nights(a, b):
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def trip_key(go, back):
    """여정 열쇠 = 항공사·날짜·출발 시각(편명은 뺌 — 왕복 줄은 오는 편 편명이 없어 같은 여정이 둘로 갈리지 않게)."""
    return f'{go["항공사"]}@{go["날짜"]}T{go["시각"]}+{back["항공사"]}@{back["날짜"]}T{back["시각"]}'


def price_row(rc, go, back, one, link, kind, seen):
    """가격줄 꼴(설계 §8.3) — 2인가 = 1인가 × 인원(«2인 확인» false · 특가 좌석은 1석만 남을 수 있음) · 위탁 = 조리법 «위탁»(항공사별 · 기본 모름)."""
    n = int(rc.get('인원', 2))
    bag = rc.get('위탁') or {}
    by = bag.get('항공사') or {}
    w = [by.get(go['항공사']), by.get(back['항공사'])]
    return {'id': f'{rc["id"]}:{trip_key(go, back)}', '꼴': kind,
            '출처': {'id': rc['id'], 'label': rc.get('label'), '제공': rc.get('provider')},
            '본 시각': seen, '가는편': go, '오는편': back, '박': nights(go['날짜'], back['날짜']),
            '경유': go['경유'] + back['경유'], '1인가': one, '2인가': one * n, '인원': n, '2인 확인': n == 1,
            '통화': rc.get('통화', 'krw').upper(), '위탁': w[0] if w[0] and w[0] == w[1] else bag.get('기본', '모름'),
            '링크': link}


def pair(rc, legs, seen):
    """편도 다리 → 왕복 조합(설계 §8.3 «편도로 묻고 코드가 짝짓는다») — 가는 날 d · 오는 날 d+박(조리법 박 범위) · 둘 다 기간 안.
    한 날에 다리가 여럿이면 싼 것부터 «날당»개까지(시간대가 다른 편을 남기려고)."""
    a, b = rc['기간']
    lo, hi = rc['박']
    keep = int(rc.get('날당', 3))
    by = {'가는': {}, '오는': {}}
    for way, leg, val, link in legs:
        by[way].setdefault(leg['날짜'], []).append((val, leg, link))
    for d in by.values():
        for k in d:
            d[k] = sorted(d[k], key=lambda x: x[0])[:keep]
    rows = []
    for day, gos in sorted(by['가는'].items()):
        if not (a <= day <= b):
            continue
        for n in range(lo, hi + 1):
            r = (dt.date.fromisoformat(day) + dt.timedelta(days=n)).isoformat()
            if r > b:
                break
            for gv, go, gl in gos:
                for bv, back, _ in by['오는'].get(r, []):
                    rows.append(price_row(rc, go, back, gv + bv, gl, '편도 짝', seen))
    return rows


def dedupe(rows):
    """같은 여정(편·시각)이 왕복 줄과 편도 짝에 둘 다 나오면 싼 것 하나."""
    best = {}
    for r in rows:
        k = trip_key(r['가는편'], r['오는편'])
        if k not in best or r['1인가'] < best[k]['1인가']:
            best[k] = r
    return sorted(best.values(), key=lambda r: (r['2인가'], r['가는편']['날짜'], r['id']))


def lowest(rows):
    """장부 한 돌림 — 날짜 쌍별 최저 2인가(가격선 다시맞춤 자료 · 설계 §8.4)."""
    low = {}
    for r in rows:
        k = (r['가는편']['날짜'], r['오는편']['날짜'])
        if r['경유'] == 0 and (k not in low or r['2인가'] < low[k]):
            low[k] = r['2인가']
    return [{'가는날': k[0], '오는날': k[1], '2인가': v} for k, v in sorted(low.items())]


# ───────── 돌림 ─────────
def plan(rc):
    p = PROVIDERS[rc['provider']]
    return [{**q, '주소': p['url'](q['params'])} for q in p['queries'](rc)]


def run(rid, force=False):
    """한 출처 한 번 — 돌려줌 = 상태 dict. 키 없음·꺼짐은 망 요청 0. 실패하면 가격줄.json 은 지난 것 그대로(지우지 않음)."""
    rc = recipes().get(rid)
    if rc is None:
        raise SystemExit(f'조리법 없음: {rid}')
    if rc.get('켬') is not True and not force:
        return set_state(rid, '꺼짐')
    p = PROVIDERS.get(rc.get('provider'))
    if p is None:
        return set_state(rid, '오류', 까닭=f'모르는 제공자 {rc.get("provider")}')
    tok = secret(rc['provider'])
    if not tok:
        return set_state(rid, '키 없음')
    tz, seen = tz_of(rc), stamp()
    legs, rows, n = [], [], 0
    try:
        for q in p['queries'](rc):
            resp = get(rid, rc, p['url'](q['params']), p['headers'](tok))
            n += 1
            for x in p['parse'](resp, q, rc, tz):
                if q['꼴'] == '편도':
                    legs.append((q['방향'], x['다리'], x['값'], x['링크']))
                else:
                    rows.append(price_row(rc, x['가는편'], x['오는편'], x['1인가'], x['링크'], '왕복', seen))
    except Stop as e:
        return set_state(rid, e.state, 까닭=e.why, 조회=n)
    rows = dedupe(rows + pair(rc, legs, seen))
    write_json(os.path.join(sdir(rid), '가격줄.json'), {'시각': seen, 'rows': rows})
    append(os.path.join(sdir(rid), '장부.jsonl'), [{'시각': seen, '최저': lowest(rows)}])
    return set_state(rid, '됨', 조회=n, 줄=len(rows), 다리=len(legs))


def rows_of(rid):
    try:
        return json.load(open(os.path.join(sdir(rid), '가격줄.json'), encoding='utf-8')).get('rows') or []
    except (OSError, ValueError):
        return []


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap = argparse.ArgumentParser()
    ap.add_argument('--plan')
    ap.add_argument('--source')
    ap.add_argument('--force', action='store_true', help='조리법 켬이 false 여도 한 번')
    ap.add_argument('--status', action='store_true')
    a = ap.parse_args()
    if a.plan:
        rc = recipes().get(a.plan) or sys.exit(f'조리법 없음: {a.plan}')
        for q in plan(rc):
            print(f'{q["꼴"]} {q["방향"]} {q["주소"]}')
    elif a.source:
        print(json.dumps(run(a.source, a.force), ensure_ascii=False))
    else:
        print(json.dumps(status(), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
