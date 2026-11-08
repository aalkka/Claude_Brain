# -*- coding: utf-8 -*-
"""수집 창 스위치가 진짜 크롬 확장에 닿는가 — 진짜 크롬(머리 없음) + 가짜 mylms(로컬 HTTPS) · 임시 프로필.
본 프로필·본 볼트·실제 학교 서버를 건드리지 않는다. known.json 은 확장 사본의 것을 고친다(PC 가 쓰는 길과 같은 파일).
틀은 lms_ext_check.py 를 그대로 쓴다. 약 6분. 실행: py -3 -u 3_시스템/_eval/collect_desk_chrome_check.py
"""
import importlib.util
import json
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('lec', os.path.join(HERE, 'lms_ext_check.py'))
lec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lec)
ST, ok, fails = lec.ST, lec.ok, lec.fails
COURSES = lec.COURSES


def main():
    tmp = tempfile.mkdtemp(prefix='deskchrome-')
    ext = os.path.join(tmp, 'ext')
    shutil.copytree(lec.EXT, ext)
    p = os.path.join(ext, 'sw.js')
    s = open(p, encoding='utf-8').read()
    for a, b in [('const TICK_MIN = 15;', 'const TICK_MIN = 0.5;'), ('const COOLDOWN = 30 * 60 * 1000;', 'const COOLDOWN = 20 * 1000;'), ('delayInMinutes: 1, periodInMinutes', 'delayInMinutes: 0.1, periodInMinutes')]:
        assert a in s, a
        s = s.replace(a, b)
    open(p, 'w', encoding='utf-8', newline='\n').write(s)
    version = json.load(open(os.path.join(ext, 'manifest.json'), encoding='utf-8'))['version']

    def known(**kw):
        tp = os.path.join(ext, 'known.tmp')
        with open(tp, 'w', encoding='utf-8') as f:
            json.dump({'courses': COURSES, 'knownFiles': [], 'board': {}, **kw}, f)
        os.replace(tp, os.path.join(ext, 'known.json'))

    known(paused=True)
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', os.path.join(tmp, 'k.pem'), '-out', os.path.join(tmp, 'c.pem'),
                    '-days', '2', '-subj', '/CN=mylms.korea.ac.kr'], check=True, capture_output=True)
    srv = lec.S(('127.0.0.1', 0), lec.H)
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
    args = ['node', os.path.join(HERE, 'chrome_pipe.mjs'), lec.chrome_exe(), ext, f'--user-data-dir={prof}', '--no-first-run', '--no-default-browser-check', '--headless=new',
            f'--host-resolver-rules=MAP mylms.korea.ac.kr 127.0.0.1:{port}', '--ignore-certificate-errors', 'about:blank']
    pr = subprocess.Popen(args, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    print('크롬 감싸개', pr.pid, '임시', tmp, flush=True)

    def files():
        out = []
        for n in sorted(os.listdir(dl)):
            if n.startswith('lms-run-') and n.endswith('.json'):
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

    runs = lambda: [x for x in files() if x.get('kind') == 'run']
    try:
        time.sleep(80)                  # 틱 30초 · 첫 틱 6초 — 두 번 넘게
        ok('진짜 크롬 · 처음부터 paused = mylms 요청 0 · 요약 0', ST['seen'] == 0 and not files(), f"확인 {ST['seen']}회 · 요약 {len(files())}")
        known(paused=False)
        ok('풀면 다음 틱에 돈다', wait(lambda: ST['seen'] > 0, 60), f"확인 {ST['seen']}회")
        ok('풀면 밀린 전 과목 받기', wait(runs, 150))
        r = (runs() or [{}])[0]
        ok('요약의 판 = manifest 판(진입 파일 → sw.js 가 진짜로 돎)', r.get('version') == version, f"{r.get('version')} / {version}")
        n = len(runs())
        known(paused=True)
        time.sleep(35)                  # 이미 시작한 틱이 끝나게
        s0 = ST['seen']
        time.sleep(70)
        ok('다시 끄면 요청이 멈춘다', ST['seen'] == s0 and len(runs()) == n, f"확인 {ST['seen'] - s0}회 · 받기 {len(runs()) - n}")
        known(paused=True, fetchNow='2026-11-05T16:00:00')
        time.sleep(70)
        ok('꺼진 동안 지금 받기는 안 돈다', ST['seen'] == s0 and len(runs()) == n, f"확인 {ST['seen'] - s0}회")
        known(paused=False, fetchNow='2026-11-05T16:00:00')
        ok('켜면 지금 받기가 돈다(why = desk · 전 과목)', wait(lambda: any(x.get('why') == 'desk' and x.get('scope') == COURSES for x in runs()), 150), json.dumps([(x.get('why'), x.get('scope')) for x in runs()]))
        k = len(runs())
        time.sleep(70)
        ok('같은 값은 한 번만', len(runs()) == k, f'{len(runs())}건')
        known(paused=False, fetchNow='2026-11-05T16:05:00')
        ok('새 값이면 또 돈다', wait(lambda: len(runs()) > k, 120))
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
