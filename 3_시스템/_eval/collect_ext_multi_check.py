"""로그인 수집 확장 — «두 번째 Canvas 사이트를 조리법만으로»(범용성 증거 · 11-16 LMS 범용화 S5). 본 프로필·본 볼트·실제 학교 서버를 건드리지 않는다.
진짜 크롬(머리 없음) + 가짜 출처 셋(로컬 HTTPS 하나 · 호스트로 가름) · 임시 프로필 · 임시 볼트:
  A = Canvas+LearningX(collect_ext_check 의 가짜) · B = Canvas 만(다른 호스트·과목·머리 · 첫 화면이 POST 를 쏜다) · C = 허용 안 한 출처.
PC 몫도 진짜 코드: 임시 볼트에 조리법 셋(collect/browser/a·b·c.json)만 두고 collect-browser.py --known 이 쓴 ext-state.json·known-*.json 을 확장 사본에 그대로 넣는다.
잼: B 가 제 과목·제 머리(b-run-·b-canvas-)로 받음 · A 도 받음 · C 는 서버 요청 0 · B 탭의 POST 는 막힘(서버 0) · A 의 GET 아닌 요청 = LTI 진입뿐. 약 4분.
    py -3 -u 3_시스템/_eval/collect_ext_multi_check.py
"""
import importlib.util
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location('lec', os.path.join(HERE, 'collect_ext_check.py'))
lec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lec)
ok, fails = lec.ok, lec.fails
A, B, C = lec.HOST, 'canvas-b.test', 'canvas-c.test'
B_COURSES = [333]
HIT = {B: [], C: []}                    # (방법, 경로) — B·C 서버에 닿은 요청


class M(lec.H):
    def _host(self):
        return (self.headers.get('Host') or '').split(':')[0]

    def do_POST(self):
        h = self._host()
        if h not in HIT:
            return super().do_POST()
        self.rfile.read(int(self.headers.get('Content-Length') or 0))
        HIT[h].append(('POST', urllib.parse.urlparse(self.path).path))
        self.send(200, '{}')

    def do_GET(self):
        h = self._host()
        if h not in HIT:
            return super().do_GET()
        path = urllib.parse.urlparse(self.path).path
        HIT[h].append(('GET', path))
        if path == '/':                 # 첫 화면이 쓰기 요청을 쏜다(조회수 올리기 같은 것) — 수집 탭에선 막혀야 한다
            return self.send(200, "<!doctype html><html><body>home<script>fetch('/api/v1/courses/333/mark',{method:'POST'}).catch(()=>{})</script></body></html>",
                             'text/html; charset=utf-8', headers={'Set-Cookie': 'sessb=1; Path=/; Secure; HttpOnly; SameSite=Lax'})
        if path.startswith('/api/') and 'sessb=1' not in (self.headers.get('Cookie') or ''):
            return self.send(404 if path == '/api/v1/users/self' else 401, '{}')
        if path == '/api/v1/users/self':
            return self.js({'id': 2})
        if path in ('/api/v1/announcements', '/api/v1/planner/items'):
            return self.js([])
        if path == '/api/v1/courses':
            return self.js([{'id': c, 'name': f'B과목{c}'} for c in B_COURSES])
        m = re.fullmatch(r'/api/v1/courses/(\d+)', path)
        if m:
            return self.js({'id': int(m.group(1)), 'name': 'B과목' + m.group(1), 'syllabus_body': ''})
        if re.fullmatch(r'/api/v1/courses/\d+/(discussion_topics|assignments|modules|files)', path):
            return self.js([])
        self.send(404, '{}')


def pc_known(root):
    """임시 볼트에 조리법 셋만 두고 PC 의 진짜 --known 을 돌린다 → 그 확장 폴더(ext-state.json · known-*.json)."""
    tv = os.path.join(root, 'vault')
    ts = os.path.join(tv, '3_시스템')
    os.makedirs(os.path.join(ts, 'collect', 'browser'))
    for f in ('collect-browser.py', 'collectlib.py', 'roles.py', 'roles.json'):
        shutil.copy2(os.path.join(SYS, f), ts)
    shutil.copytree(os.path.join(SYS, 'collect-adapters'), os.path.join(ts, 'collect-adapters'), ignore=shutil.ignore_patterns('__pycache__'))
    for sid, host, adapters, units in (('a', A, ['canvas', 'learningx'], lec.COURSES), ('b', B, ['canvas'], B_COURSES), ('c', C, ['canvas'], [444])):
        json.dump({str(u): f'{sid}과목{u}' for u in units}, open(os.path.join(ts, f'units-{sid}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        json.dump({'id': sid, 'name': sid.upper(), 'family': 'browser', 'adapters': adapters, 'run_prefix': f'{sid}-run-', 'raw_prefix': f'{sid}-',
                   'units': f'units-{sid}.json', 'manifest': f'_index/{sid}/manifest.json', 'state': f'_index/{sid}', 'login': {'cookie_domain': host},
                   'ext': {'host': f'https://{host}'}}, open(os.path.join(ts, 'collect', 'browser', f'{sid}.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    env = dict(os.environ, PYTHONIOENCODING='utf-8', COLLECT_TEST_STATE=os.path.join(root, 'state'))
    r = subprocess.run([sys.executable, os.path.join(ts, 'collect-browser.py'), '--known'], cwd=tv, env=env, capture_output=True, encoding='utf-8', errors='replace',
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    out = os.path.join(ts, 'collect-ext')
    idx = json.load(open(os.path.join(out, 'ext-state.json'), encoding='utf-8')) if os.path.exists(os.path.join(out, 'ext-state.json')) else {}
    kb = json.load(open(os.path.join(out, 'known-b.json'), encoding='utf-8')) if os.path.exists(os.path.join(out, 'known-b.json')) else {}
    ok('PC: 조리법 셋만 두면 --known 이 출처 셋을 씀(코드 고침 0)', r.returncode == 0 and idx.get('sources') == ['a', 'b', 'c']
       and kb.get('exec', {}).get('host') == f'https://{B}' and kb.get('courses') == B_COURSES, (r.returncode, r.stderr[-300:], idx, kb.get('exec')))
    return out


def main():
    tmp = tempfile.mkdtemp(prefix='extmulti-')
    ext = os.path.join(tmp, 'ext')
    shutil.copytree(lec.EXT, ext, ignore=shutil.ignore_patterns('known-*.json', 'ext-state.json'))
    lec.fast(ext)
    lec.grant(ext, [A, B])              # C 는 허용 안 함 — 사람이 팝업에서 안 누른 셈
    made = pc_known(tmp)
    for n in os.listdir(made):
        shutil.copy2(os.path.join(made, n), ext)
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', os.path.join(tmp, 'k.pem'), '-out', os.path.join(tmp, 'c.pem'),
                    '-days', '2', '-subj', f'/CN={A}'], check=True, capture_output=True)
    srv = lec.S(('127.0.0.1', 0), M)
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
    rules = ', '.join(f'MAP {h} 127.0.0.1:{port}' for h in (A, B, C))
    args = ['node', os.path.join(HERE, 'chrome_pipe.mjs'), lec.chrome_exe(), ext, f'--user-data-dir={prof}', '--no-first-run', '--no-default-browser-check', '--headless=new',
            f'--host-resolver-rules={rules}', '--ignore-certificate-errors', 'about:blank']
    pr = subprocess.Popen(args, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('크롬 감싸개', pr.pid, '임시', tmp, flush=True)

    def runs(sid):
        out = []
        for n in sorted(os.listdir(dl)):
            if n.startswith(f'{sid}-run-') and n.endswith('.json'):
                try:
                    d = json.load(open(os.path.join(dl, n), encoding='utf-8'))
                except ValueError:
                    continue
                if d.get('kind') == 'run':
                    out.append(d)
        return out

    def wait(pred, sec):
        t0 = time.time()
        while time.time() - t0 < sec:
            if pred():
                return True
            time.sleep(1)
        return False

    try:
        ok('A 받기(Canvas+LearningX)', wait(lambda: runs('a'), 200))
        ok('B 받기 — 조리법만으로 두 번째 Canvas', wait(lambda: runs('b'), 200))
        time.sleep(5)
        ra, rb = (runs('a') or [{}])[0], (runs('b') or [{}])[0]
        print('  A', json.dumps({k: ra.get(k) for k in ('source', 'why', 'scope', 'error')}, ensure_ascii=False), '· B', json.dumps({k: rb.get(k) for k in ('source', 'why', 'scope', 'error')}, ensure_ascii=False), flush=True)
        ok('A = 전 과목 · Canvas·게시판 끝남', ra.get('scope') == lec.COURSES and not ra.get('error') and (ra.get('canvas') or {}).get('state') == 'done' and (ra.get('board') or {}).get('state') == 'done')
        ok('B = 제 과목 · 제 출처 id · Canvas 끝남 · 게시판 칸 없음', rb.get('source') == 'b' and rb.get('scope') == B_COURSES and not rb.get('error')
           and (rb.get('canvas') or {}).get('state') == 'done' and 'board' not in rb, json.dumps({k: rb.get(k) for k in ('source', 'scope', 'error', 'canvas')}, ensure_ascii=False)[:300])
        bc = [n for n in os.listdir(dl) if n.startswith('b-canvas-')]
        braw = json.load(open(os.path.join(dl, bc[0]), encoding='utf-8')) if bc else {}
        ok('B 원시 = 제 머리(b-canvas-) · 제 호스트 · 제 과목', bool(bc) and braw.get('host') == B and [c.get('id') for c in braw.get('courses') or []] == B_COURSES,
           json.dumps([sorted(os.listdir(dl))[:8], braw.get('host'), [c.get('id') for c in braw.get('courses') or []]], ensure_ascii=False)[:300])
        posts = [p for m, p in HIT[B] if m == 'POST']
        ok('B 탭의 POST = 서버에 0(막힘)', not posts and any(k.startswith('POST ') for k in ((rb.get('requests') or {}).get('blocked') or {})), json.dumps([posts, (rb.get('requests') or {}).get('blocked')], ensure_ascii=False)[:300])
        ok('A 의 GET 아닌 요청 = LTI 진입뿐', {p for _, p in lec.ST['nonget']} <= {'/learningx/lti/learningx_board/boards'}, str(lec.ST['nonget']))
        ok('C(허용 안 함) = 서버 요청 0 · 요약 0', not HIT[C] and not [n for n in os.listdir(dl) if n.startswith('c-')], json.dumps([HIT[C][:5], [n for n in os.listdir(dl) if n.startswith('c-')]]))
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
