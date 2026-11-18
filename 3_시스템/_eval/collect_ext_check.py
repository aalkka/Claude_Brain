"""로그인 수집 확장(3_시스템/collect-ext · 조리법을 읽는 실행기) 격리 시험 — 진짜 크롬 + 가짜 Canvas·LearningX(로컬 HTTPS). 본 프로필·본 볼트·실제 학교 서버를 건드리지 않는다.

확장 사본의 시간 상수만 줄여 돌린다: 첫 전 과목 받기 → 조용함 → 새 공지 신호 → 바뀐 과목만 → 로그인 끊김·되살아남 → 서버 장애 → (COLLECT_CHECK_SOAK=분) 오래 돌리기.
출처는 PC 가 쓰는 꼴 그대로(ext-state.json + known-<id>.json · S5). 사람의 팝업 «허용»은 사본 manifest 의 host_permissions 로 대신한다(머리 없는 크롬은 권한 창을 못 누른다).
    py -3 -u 3_시스템/_eval/collect_ext_check.py
"""
import http.server
import json
import os
import re
import shutil
import socketserver
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import winreg

HERE = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.normpath(os.path.join(HERE, '..', 'collect-ext'))
COURSES = [111, 222]
HOST = 'canvas-a.test'          # 가짜 출처 호스트(학교 이름을 시험에 안 박는다)
SRC = 'a'                       # 출처 id — 요약 = a-run-<run>.json
ST = {'login': True, 'down': False, 'ann': [], 'plan': [], 'nonget': [], 'seen': 0, 'posts': {}, 'views': 0}


def known_doc(src=SRC, host=HOST, adapters=('canvas', 'learningx'), keep_days=0, **kw):
    """PC(collect-browser.py write_known)가 쓰는 known-<id>.json 꼴."""
    return {'exec': {'name': src, 'host': f'https://{host}', 'adapters': list(adapters), 'run_prefix': f'{src}-run-', 'raw_prefix': f'{src}-',
                     'cookie_domain': host, 'keep_days': keep_days, 'tools': {'learningx': 5}}, 'courses': COURSES, 'knownFiles': [], 'board': {}, **kw}


def write_known(ext, doc, src=SRC, sources=None):
    """known-<src>.json · ext-state.json 쓰기(바꿔치기 — 확장이 반쯤 쓴 파일을 읽지 않게)."""
    for name, body in ((f'known-{src}.json', doc), ('ext-state.json', {'sources': sources or [src]})):
        tp = os.path.join(ext, name + '.tmp')
        with open(tp, 'w', encoding='utf-8') as f:
            json.dump(body, f)
        os.replace(tp, os.path.join(ext, name))


def grant(ext, hosts):
    """사람이 팝업에서 «허용»을 누른 셈 — 시험 사본 manifest 에 그 호스트를 박는다(진짜 manifest 는 optional 뿐)."""
    p = os.path.join(ext, 'manifest.json')
    m = json.load(open(p, encoding='utf-8'))
    m['host_permissions'] = [f'https://{h}/*' for h in hosts]
    open(p, 'w', encoding='utf-8', newline='\n').write(json.dumps(m, ensure_ascii=False, indent=2))


def fast(ext, extra=()):
    """시간 상수만 줄인 사본 — 문자열이 꼭 있어야 바꾼다."""
    p = os.path.join(ext, 'sw.js')
    s = open(p, encoding='utf-8').read()
    for a, b in [('const TICK_MIN = 15;', 'const TICK_MIN = 0.5;'), ('const COOLDOWN = 30 * 60 * 1000;', 'const COOLDOWN = 20 * 1000;'),
                 ('delayInMinutes: 1, periodInMinutes', 'delayInMinutes: 0.1, periodInMinutes'), *extra]:
        assert a in s, a
        s = s.replace(a, b)
    open(p, 'w', encoding='utf-8', newline='\n').write(s)


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ct='application/json', headers=None):
        b = body.encode('utf-8') if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(b)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def js(self, obj):
        self.send(200, 'while(1);' + json.dumps(obj))

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        self.rfile.read(int(self.headers.get('Content-Length') or 0))
        ST['nonget'].append(('POST', path))
        if path.endswith('/learningx/lti/learningx_board/boards'):
            return self.send(200, """<!doctype html><html><body><div>게시판</div><div>게시판</div><div>최근</div><div>게시판 전체 게시판</div>
<script>fetch('/learningx/api/v1/learningx_board/courses/1/boards/1/posts/1/view_count',{method:'POST'}).catch(()=>{})</script></body></html>""", 'text/html; charset=utf-8',
                             headers={'Set-Cookie': 'xn_api_token=abc; Path=/; Secure'})
        self.send(200, '{}')

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        path, q = u.path, urllib.parse.parse_qs(u.query)
        if path.startswith('/api/v1/users/self'):
            ST['seen'] += 1
        if ST['down'] and path.startswith('/api/'):
            return self.send(503, '{}')
        has = 'sess=1' in (self.headers.get('Cookie') or '')      # 세션 쿠키가 있어야 로그인 — 워커 fetch 에 쿠키가 실리는지까지 잰다
        if not ST['login'] or (path.startswith('/api/') and not has):
            if path == '/api/v1/users/self':                      # 10-25 실측: 비로그인 users/self = 404
                return self.send(404, '{"errors":[{"message":"not found"}]}')
            if path.startswith('/api/'):
                return self.send(401, '{"status":"unauthenticated"}')
            return self.send(302, '', headers={'Location': 'https://sso.invalid/login'})
        if path == '/':
            return self.send(200, '<!doctype html><html><body>home</body></html>', 'text/html; charset=utf-8',
                             headers={'Set-Cookie': 'sess=1; Path=/; Secure; HttpOnly; SameSite=Lax'})
        if path == '/api/v1/users/self':
            return self.js({'id': 1})
        if path == '/api/v1/announcements':
            return self.js(ST['ann'])
        if path == '/api/v1/planner/items':
            if ST.get('fail_plan'):
                return self.send(500, '{}')
            return self.js(ST['plan'])
        if path == '/api/v1/courses':
            return self.js([{'id': c, 'name': f'과목{c}'} for c in COURSES] + [{'id': 999, 'name': '새 강좌'}])
        m = re.fullmatch(r'/api/v1/courses/(\d+)', path)
        if m:
            return self.js({'id': int(m.group(1)), 'name': '과목' + m.group(1), 'syllabus_body': ''})
        if re.fullmatch(r'/api/v1/courses/\d+/(discussion_topics|assignments|modules|files)', path):
            return self.js([])
        m = re.fullmatch(r'/courses/(\d+)/external_tools/5', path)
        if m:
            return self.send(200, """<!doctype html><html><body><iframe id="tool_content" name="tool_content"></iframe>
<form id="f" method="post" action="/learningx/lti/learningx_board/boards" target="tool_content"></form><script>document.getElementById('f').submit()</script></body></html>""", 'text/html; charset=utf-8')
        if path.startswith('/learningx/api/') and self.headers.get('Authorization') != 'Bearer abc':
            return self.send(401, '{"message":"unauthorized"}')      # 11-03 탐침: 쿠키만으론 401
        if re.fullmatch(r'/learningx/api/v1/learningx_board/courses/\d+/boards', path):
            return self.send(200, json.dumps([{'id': 4, 'title': 'Q&A 게시판'}, {'id': 5, 'title': '강의자료실'}]))
        m = re.fullmatch(r'/learningx/api/v1/learningx_board/courses/(\d+)/boards/(\d+)/posts', path)
        if m:
            ST['views'] += 1
            items = [{'id': 1, 'title': 't', 'created_at': 'x', 'view_count': ST['views']}] + ST['posts'].get(m.group(1), [])   # 조회수는 볼 때마다 바뀐다
            return self.send(200, json.dumps({'items': items, 'pagination': {}}))
        self.send(404, '{}')


class S(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def chrome_exe():
    return winreg.QueryValue(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe')


fails = []


def ok(name, cond, extra=''):
    print(('통과 ' if cond else '실패 ') + name + (f' — {extra}' if extra else ''), flush=True)
    if not cond:
        fails.append(name)


def main():
    tmp = tempfile.mkdtemp(prefix='lmsext-')
    ext = os.path.join(tmp, 'ext')
    shutil.copytree(EXT, ext, ignore=shutil.ignore_patterns('known-*.json', 'ext-state.json'))
    fast(ext, [('const MODULE_EVERY = 4;', 'const MODULE_EVERY = 2;')])
    grant(ext, [HOST])
    write_known(ext, known_doc())

    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', os.path.join(tmp, 'k.pem'), '-out', os.path.join(tmp, 'c.pem'),
                    '-days', '2', '-subj', f'/CN={HOST}'], check=True, capture_output=True)
    srv = S(('127.0.0.1', 0), H)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(os.path.join(tmp, 'c.pem'), os.path.join(tmp, 'k.pem'))
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    prof, dl = os.path.join(tmp, 'prof'), os.path.join(tmp, 'dl')
    os.makedirs(os.path.join(prof, 'Default'))
    os.makedirs(dl)
    with open(os.path.join(prof, 'Default', 'Preferences'), 'w', encoding='utf-8') as f:
        json.dump({'download': {'default_directory': dl, 'prompt_for_download': False, 'directory_upgrade': True},
                   'profile': {'default_content_setting_values': {'automatic_downloads': 1}}}, f)
    args = ['node', os.path.join(HERE, 'chrome_pipe.mjs'), chrome_exe(), ext, f'--user-data-dir={prof}', '--no-first-run', '--no-default-browser-check', '--headless=new',
            f'--host-resolver-rules=MAP {HOST} 127.0.0.1:{port}', '--ignore-certificate-errors', 'about:blank']
    pr = subprocess.Popen(args, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('크롬 감싸개', pr.pid, '임시', tmp, flush=True)

    def files():
        out = []
        for n in sorted(os.listdir(dl)):
            if n.startswith(f'{SRC}-run-') and n.endswith('.json'):
                try:
                    out.append(json.load(open(os.path.join(dl, n), encoding='utf-8')))
                except ValueError:
                    pass
        return out

    def wait(pred, sec):
        t0 = time.time()
        while time.time() - t0 < sec:
            if pred():
                return True
            time.sleep(1)
        return False

    def runs():
        return [x for x in files() if x.get('kind') == 'run']

    def stat():
        return [x for x in files() if x.get('kind') == 'status']

    try:
        ok('확장이 돈다(가짜 서버에 확인 요청이 온다)', wait(lambda: ST['seen'] > 0, 60), f"확인 {ST['seen']}회")
        if not ST['seen']:
            return
        ok('첫 전 과목 받기(daily · 탐침)', wait(lambda: runs(), 150))
        r = (runs() or [{}])[0]
        print('  요약', json.dumps({k: r.get(k) for k in ('why', 'scope', 'error')}, ensure_ascii=False), 'canvas', (r.get('canvas') or {}).get('state'), 'board', (r.get('board') or {}).get('state'), flush=True)
        ok('범위 = 전 과목 · 오류 없음', r.get('why') == 'daily' and r.get('scope') == COURSES and not r.get('error'))
        ok('요약·원시 이름 = 조리법 값(출처 id · raw_prefix)', r.get('source') == SRC and any(n.startswith(f'{SRC}-canvas-') for n in os.listdir(dl)), str(os.listdir(dl))[:200])
        ok('Canvas·게시판 끝남', (r.get('canvas') or {}).get('state') == 'done' and (r.get('board') or {}).get('state') == 'done', json.dumps((r.get('board') or {}).get('results'), ensure_ascii=False)[:200])
        ok('탐침 기록(게시판 API·쿠키 이름)', 'boards_cookie' in (r.get('probe') or {}) and 'cookies' in r, json.dumps(r.get('probe'), ensure_ascii=False)[:200])
        ok('수강 강좌 목록 기록', any(c.get('id') == 999 for c in r.get('activeCourses') or []))
        rq = r.get('requests') or {}
        ok('조회수 올리기 막힘', any('view_count' in k for k in rq.get('blocked', {})), json.dumps(rq.get('blocked'), ensure_ascii=False)[:200])
        ng = {p for _, p in ST['nonget']}
        ok('서버에 닿은 GET 아닌 요청 = LTI 진입뿐', ng == {'/learningx/lti/learningx_board/boards'}, str(ng))
        n = len(runs())
        time.sleep(70)
        ok('바뀐 것이 없으면 받지 않는다', len(runs()) == n, f'{len(runs())}건')

        ST['ann'] = [{'id': 7, 'title': '새 공지', 'posted_at': '2026-11-03T00:00:00Z', 'message': 'x', 'context_code': f'course_{COURSES[1]}'}]
        ok('새 공지 신호 → 받음', wait(lambda: len(runs()) > n, 120))
        r = runs()[-1] if runs() else {}
        ok('바뀐 과목만', r.get('why') == 'signal' and r.get('scope') == [COURSES[1]], f"{r.get('why')} {r.get('scope')}")
        n = len(runs())

        ST['posts'][str(COURSES[0])] = [{'id': 2, 'title': '새 글', 'created_at': 'y', 'view_count': 0}]
        ok('게시판 새 글 신호 → 받음', wait(lambda: len(runs()) > n, 150))
        r = runs()[-1] if runs() else {}
        ok('게시판도 바뀐 과목만', r.get('why') == 'signal' and r.get('scope') == [COURSES[0]], f"{r.get('why')} {r.get('scope')}")
        ok('게시판 신호 상태 200', (r.get('signals') or {}).get('board') == 200, json.dumps(r.get('signals')))
        n = len(runs())
        time.sleep(100)
        ok('조회수만 바뀌면 받지 않는다', len(runs()) == n, f'{len(runs())}건')

        ST['login'] = False
        ok('로그인 끊김 → 상태 알림', wait(lambda: any(x.get('login') == 'out' for x in stat()), 90))
        time.sleep(65)
        out = [x for x in stat() if x.get('login') == 'out']
        ok('끊김 알림은 한 번', len(out) == 1, f'{len(out)}건')
        ok('끊긴 동안 받지 않는다', len(runs()) == n)
        ST['login'] = True
        ok('되살아남 → 상태 알림', wait(lambda: any(x.get('login') == 'ok' for x in stat()), 90))

        k = len(files())
        ST['down'] = True
        time.sleep(70)
        ok('서버 장애는 로그인 끊김이 아니다', len([x for x in stat() if x.get('login') == 'out']) == 1 and len(files()) == k, f'{len(files())}건')
        ST['down'] = False

        r = runs()[-1] if runs() else {}
        ok('신호 상태가 요약에 실림', (r.get('signals') or {}).get('ann') == 200 and (r.get('signals') or {}).get('plan') == 200, json.dumps(r.get('signals')))
        ok('워커 쿠키 실림(쿠키 있어야 200)', r.get('workerBlind') is False)

        ST['fail_plan'] = True
        time.sleep(70)
        ok('플래너만 500 이어도 로그인·확인은 돈다', len([x for x in stat() if x.get('login') == 'out']) == 1, f"확인 {ST['seen']}")
        ST['fail_plan'] = False

        soak = int(os.environ.get('COLLECT_CHECK_SOAK') or 0)     # 분 — 평소 동작이 멈추지 않는지(틱 30초)
        if soak:
            last, worst, s0, t0 = time.time(), 0, ST['seen'], time.time()
            n = ST['seen']
            while time.time() - t0 < soak * 60:
                time.sleep(2)
                if ST['seen'] != n:
                    worst, last, n = max(worst, time.time() - last), time.time(), ST['seen']
            worst = max(worst, time.time() - last)
            ok(f'{soak}분 동안 멈춤 없음', worst < 100 and ST['seen'] - s0 >= soak, f"확인 {ST['seen'] - s0}회 · 가장 긴 틈 {int(worst)}초")
    finally:
        pr.terminate()
        subprocess.run(['taskkill', '/PID', str(pr.pid), '/T', '/F'], capture_output=True)
        srv.shutdown()
        time.sleep(2)
        shutil.rmtree(tmp, ignore_errors=True)
    print('== 실패 ' + str(len(fails)) + ('건: ' + ' · '.join(fails) if fails else '건'), flush=True)
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
