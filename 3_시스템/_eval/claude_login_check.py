"""Claude 앱 로그인 풀림 알림 시험 — 가짜 기록 줄 · 11-20 실제 기록 되풀이 · 건강 줄 · 서버 순찰(같은 풀림에 한 번). 폰에 보내지 않는다(send 가짜).
    py -3 3_시스템/_eval/claude_login_check.py"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)
VAULT = os.path.dirname(SYS)
sys.path.insert(0, SYS)
import claude_login as cl  # noqa: E402

res = []


def ok(name, cond, val=''):
    res.append(bool(cond))
    print(('통과' if cond else '실패'), name, val)


def logs(main=(), rc=()):
    d = tempfile.mkdtemp(prefix='claude_logs_')
    for name, ls in (('main.log', main), ('remote-control.log', rc)):
        if ls is not None:
            with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
                f.write('\n'.join(ls) + ('\n' if ls else ''))
    return d


STALE = '2026-11-20 07:11:20 [info] oauth: /authorize not sent: the server says this sign-in is too old (session_stale_relogin), so the person must sign in again'
RENEW = '2026-11-20 07:11:20 [warn] [oauth] Code-tab token renewal (timer) failed: session_stale_relogin'
CLEAR = '2026-11-20 13:02:55 [info] [oauth] clearing latched session_stale_relogin failures'
DROP = '2026-11-20 13:02:55 [info] [oauth] dropped the stored session_stale_relogin failures: the sessionKey changed'
NOISE = '2026-11-20 06:03:18 [info] [oauth] looking up token for orgId=x'

st = cl.state(logs([NOISE, STALE, RENEW]))
ok('L1 가짜 «sign-in is too old» 줄 = 풀림 · 풀린 때 07:11:20', st['state'] == 'stale' and st['since'] == '2026-11-20 07:11:20', st)
st = cl.state(logs([NOISE, STALE, RENEW, CLEAR, DROP]))
ok('L2 뒤에 «clearing latched» = 되찾음(되찾음 줄 속 낱말을 풀림으로 안 셈)', st['state'] == 'ok', st)
again = '2026-12-18 09:00:01 [info] oauth: /authorize not sent: the server says this sign-in is too old (session_stale_relogin)'
st = cl.state(logs([STALE, CLEAR, again]))
ok('L3 되찾은 뒤 다시 풀림 = 새 풀린 때', st['state'] == 'stale' and st['since'] == '2026-12-18 09:00:01', st)
rc = ['2026-11-20 07:12:24.388 [info] state off → auth_stale (no_auth) trigger=my_access']
st = cl.state(logs([NOISE], rc))
ok('L4 원격 제어 기록 «→ auth_stale» 만으로도 풀림', st['state'] == 'stale' and st['src'] == 'remote-control.log', st)
st = cl.state(logs([NOISE], rc + ['2026-11-20 13:03:00.914 [info] state auth_stale → pending trigger=my_access']))
ok('L5 «auth_stale →» = 되찾음', st['state'] == 'ok', st)
ok('L6 기록 폴더 없음 = 모름', cl.state(os.path.join(tempfile.gettempdir(), 'no-such-claude-logs'))['state'] == 'unknown')

# 11-20 실제 기록 되풀이 — 12:00 까지 자르면 풀림(07:11:20) · 통째면 되찾음
real = cl.logs_dir()
cut = None
if real and os.path.exists(os.path.join(real, 'main.log')):
    cut = {}
    for name in ('main.log', 'remote-control.log'):
        ls = cl._lines(os.path.join(real, name), cl.TAIL if name == 'main.log' else 0) or []
        cut[name] = [ln for ln in ls if cl.TS.match(ln) and ln[:16] <= '2026-11-20 12:00']
    if not any('2026-11-20 07:11' in ln for ln in cut['main.log']):
        print('건너뜀 R1·R2 — 11-20 기록이 이 PC 에 없음(기록은 돌며 지워진다)')
        cut = False
if cut:
    st = cl.state(logs(cut['main.log'], cut['remote-control.log']))
    ok('R1 실제 기록 12:00 까지 = 풀림 07:11:20', st['state'] == 'stale' and st['since'] == '2026-11-20 07:11:20', st)
    st = cl.state(real)
    ok('R2 실제 기록 지금 = 되찾음(13:02 다시 로그인)', st['state'] == 'ok', st)
elif cut is None:
    print('건너뜀 R1·R2 — 이 PC 에 데스크톱 앱 기록 없음')

# 건강 줄
ok('H1 풀림 = 건강 줄 하나(warn)', [r[1] for r in cl.health_rows({'state': 'stale', 'since': '2026-11-20 07:11:20'})] == ['warn'])
ok('H2 됨·모름 = 건강 줄 없음', cl.health_rows({'state': 'ok'}) == [] and cl.health_rows({'state': 'unknown'}) == [])

# 서버 순찰 — 같은 풀림에 한 번
MOB = os.path.join(VAULT, '.claude', 'skills', 'mobility', 'scripts')
if os.path.isfile(os.path.join(MOB, 'server.py')):
    sys.path.insert(0, MOB)
    import server  # noqa: E402
    server.LOGIN_ALERT = os.path.join(tempfile.mkdtemp(prefix='login_alert_'), 'login-alert.json')
    server.log = lambda *_a, **_k: None
    sent = []
    good = lambda t, x, g: sent.append((t, x, g)) or True  # noqa: E731
    s1 = {'state': 'stale', 'since': '2026-11-20 07:11:20', 'src': 'main.log'}
    ok('S1 처음 풀림 = 보냄', server.login_tick(s1, good) == 'sent' and len(sent) == 1 and sent[0][0] == 'Claude 다시 로그인 필요', sent)
    ok('S2 같은 풀림 다음 순찰 = 안 보냄', server.login_tick(s1, good) == 'same' and len(sent) == 1)
    ok('S3 되찾음 = 아무것도', server.login_tick({'state': 'ok'}, good) == 'ok' and len(sent) == 1)
    s2 = {'state': 'stale', 'since': '2026-12-18 09:00:01', 'src': 'main.log'}
    ok('S4 보내기 실패 = 안 적음(다음 순찰에 다시)', server.login_tick(s2, lambda *a: False) == 'fail'
       and json.load(open(server.LOGIN_ALERT, encoding='utf-8'))['since'] == s1['since'])
    ok('S5 새 풀림 = 다시 한 번', server.login_tick(s2, good) == 'sent' and len(sent) == 2 and sent[1][2] == s2['since'])
else:
    print('건너뜀 S1~S5 — mobility 모듈 없음(배포판 꼴) · 건강 줄만')

print('%d/%d' % (sum(res), len(res)))
sys.exit(0 if all(res) else 1)
