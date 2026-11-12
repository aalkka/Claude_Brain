# -*- coding: utf-8 -*-
"""크롬이 필요한 시각 예약(mylms)이 크롬을 뒤에서 띄워 수집을 끝내는가(11-11 · 수집 설정 ②). 본 프로필·본 볼트·학교 서버 안 건드림.

  py -3 -u 3_시스템/_eval/collect_chrome_at_check.py task   # 진짜 예약(«외부뇌-수집 시험-크롬» · 75초 뒤 한 번)이 임시 볼트 lms-auto --at mylms 를 부름
                                                           #   → 시험 프로필(9311 · 확장 없음) 크롬을 띄움 · 앞창 핸들이 그대로인지 0.2초마다 · 창이 최소화인지 · 끝나면 크롬·예약 지움
  py -3 -u 3_시스템/_eval/collect_chrome_at_check.py ext    # 숨은 시험 크롬(파이프로 확장 사본 · 가짜 mylms) + 임시 볼트 lms-auto --at mylms
                                                           #   → 크롬이 떠 있으면 안 띄우고 확장 요약을 기다렸다 15분 반영 없이 바로 반영(runs 로 옮김)
둘로 가른 까닭(11-11 실측): 크롬 157 은 --load-extension 을 막고(DisableLoadExtensionCommandLineSwitch 를 꺼도 안 먹음), 파이프로 넣은 확장은 다시 띄우면 사라진다.
그래서 «예약 문맥의 띄우기»(task)와 «확장 받기 → 바로 반영»(ext)을 따로 잰다. 본 프로필에서 크롬이 꺼진 채 시각이 오면 auto.log 의 «깨우기: 크롬 …» 줄이 같은 값을 남긴다.
"""
import ctypes
import ctypes.wintypes as w
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

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)


def mod(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


ccc = mod('ccc', os.path.join(HERE, 'collect_core_check.py'))
res = []
u32 = ctypes.WinDLL('user32', use_last_error=True)
u32.GetForegroundWindow.restype = w.HWND
TASK = '외부뇌-수집 시험-크롬'
PORT = 9311                                  # 시험 크롬 포트(다른 시험의 크롬과 겹치지 않게)


def ok(name, cond, detail=''):
    res.append(bool(cond))
    print(('통과 ' if cond else '실패 ') + name + ('' if cond else f' — {detail}'), flush=True)


def pid_exe(hwnd):
    pid = w.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        return pid.value, psutil.Process(pid.value).name()
    except psutil.Error:
        return pid.value, '?'


def chrome_of(prof):
    out = []
    for p in psutil.process_iter(['name', 'cmdline']):
        try:
            cl = p.info['cmdline'] or []
            if p.info['name'] == 'chrome.exe' and any(prof in c for c in cl):
                out.append((p.pid, not any(c.startswith('--type=') for c in cl)))
        except psutil.Error:
            pass
    return out


def kill(prof):
    for pid, _ in chrome_of(prof):
        try:
            psutil.Process(pid).kill()
        except psutil.Error:
            pass


def win_state(pid):
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)

    def each(h, _):
        p = w.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(h) and u32.GetWindowTextLengthW(h):
            found.append('min' if u32.IsIconic(h) else 'shown')
        return True
    u32.EnumWindows(proc(each), 0)
    return found


def real_chrome_up():
    lf = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data', 'lockfile')
    if not os.path.exists(lf):
        return False
    try:
        with open(lf, 'ab'):
            return False
    except OSError:
        return True


def schtasks(*a):
    r = subprocess.run(['schtasks', *a], capture_output=True, creationflags=0x08000000, timeout=60)
    return r.returncode, (r.stdout + r.stderr).decode('utf-8', 'replace').strip()


def part_task():
    tmp = tempfile.mkdtemp(prefix='chrome-at-')
    tv, ts, env = ccc.temp_vault(tmp)
    la = os.path.join(ts, 'lms-auto.py')
    prof, dl, state = os.path.join(tmp, 'prof'), os.path.join(tmp, 'dl'), os.path.join(tmp, 'lms-state')
    os.makedirs(os.path.join(prof, 'Default'))
    os.makedirs(dl)
    with open(os.path.join(prof, 'Default', 'Preferences'), 'w', encoding='utf-8') as f:
        json.dump({'browser': {'has_seen_welcome_page': True}}, f)
    envs = {'PYTHONIOENCODING': 'utf-8', 'FILEOPS_NO_OBSIDIAN': '1', 'LMS_AUTO_STATE': state, 'LMS_DOWNLOADS': dl, 'LMS_CHROME_PROFILE': prof,
            'LMS_CHROME_ARGS': json.dumps([f'--remote-debugging-port={PORT}', '--no-first-run', '--no-default-browser-check', 'about:blank']),
            'LMS_HOLD': '30', 'LMS_HOLD_TICK': '5'}
    wrap = os.path.join(tmp, 'wrap.py')
    with open(wrap, 'w', encoding='utf-8') as f:
        f.write('import os, runpy, sys\n'
                f'os.environ.update({envs!r})\n'
                f'sys.argv = [{la!r}, "--at", "mylms"]\n'
                f'runpy.run_path({la!r}, run_name="__main__")\n')
    real0 = real_chrome_up()
    at = time.localtime(time.time() + 75)
    xml = ('<?xml version="1.0" encoding="UTF-16"?>\n<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
           '<RegistrationInfo><Description>외부뇌 수집 시험(collect_chrome_at_check) — 한 번 돌고 시험이 지운다</Description></RegistrationInfo>'
           f'<Triggers><TimeTrigger><StartBoundary>{time.strftime("%Y-%m-%dT%H:%M:%S", at)}</StartBoundary><Enabled>true</Enabled></TimeTrigger></Triggers>'
           '<Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>'
           '<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>'
           '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><ExecutionTimeLimit>PT5M</ExecutionTimeLimit><Priority>7</Priority></Settings>'
           f'<Actions Context="Author"><Exec><Command>{shutil.which("pyw") or "C:/Windows/pyw.exe"}</Command><Arguments>-3.11 "{wrap}"</Arguments></Exec></Actions></Task>')
    xp = os.path.join(tmp, 'task.xml')
    with open(xp, 'w', encoding='utf-16') as f:
        f.write(xml)
    rc, out = schtasks('/Create', '/TN', TASK, '/XML', xp, '/F')
    ok(f'시험 예약 등록 «{TASK}» · {time.strftime("%H:%M:%S", at)}', rc == 0, out)
    if rc:
        return
    log = os.path.join(state, 'auto.log')
    fg0 = u32.GetForegroundWindow()
    print(f'  앞창 {fg0} {pid_exe(fg0)} · 기다림 ~75초', flush=True)
    changes, ours, line, t0, seen_up = [], [], '', time.time(), None
    try:
        while time.time() - t0 < 200:
            time.sleep(0.2)
            fg = u32.GetForegroundWindow()
            if fg and (not changes or changes[-1][1] != fg) and fg != fg0:
                pid, exe = pid_exe(fg)
                changes.append((time.strftime('%H:%M:%S'), fg, pid, exe))
            mine = chrome_of(prof)
            if mine and not seen_up:
                seen_up = time.time()
            ours = [p for p, main in mine if main] or ours
            if os.path.exists(log):
                line = next((ln for ln in open(log, encoding='utf-8').read().splitlines() if '깨우기: 크롬' in ln), '')
            if line and seen_up and time.time() - seen_up > 25:
                break
        wins = [s for p in ours for s in win_state(p)]
        stole = [c for c in changes if c[2] in [p for p, _ in chrome_of(prof)] or c[2] in ours]
        print(f'  예약이 남긴 줄: {line[20:]}', flush=True)
        print(f'  앞창 바뀜 {len(changes)}번: {[(c[0], c[3]) for c in changes][:6]}', flush=True)
        ok('예약 문맥 · 크롬이 꺼진 시험 프로필 = 띄움', bool(seen_up) and '최소화 창으로 띄움' in line, (seen_up, line))
        ok('앞창 핸들 그대로(시험 크롬이 앞창이 된 적 0번)', not stole, stole)
        ok('시험 크롬 창 = 최소화(펼친 창 0)', wins and 'shown' not in wins, wins)
        ok('대본 기록 = «앞창 그대로 · 창 최소화 · 프로필 잠김»', '앞창 그대로' in line and '창 최소화' in line and '프로필 잠김' in line, line)
        ok('본 프로필 크롬 상태 그대로(잠김 여부가 시험 전과 같음)', real_chrome_up() == real0, (real0, real_chrome_up()))
    finally:
        kill(prof)
        rc, out = schtasks('/Delete', '/TN', TASK, '/F')
        ok('시험 예약 지움', rc == 0, out)


def part_ext():
    lec = mod('lec', os.path.join(HERE, 'lms_ext_check.py'))
    tmp = tempfile.mkdtemp(prefix='chrome-at-ext-')
    ext = os.path.join(tmp, 'ext')
    shutil.copytree(lec.EXT, ext)
    p = os.path.join(ext, 'sw.js')
    s = open(p, encoding='utf-8').read()
    for a, b in [('const TICK_MIN = 15;', 'const TICK_MIN = 0.5;'), ('const COOLDOWN = 30 * 60 * 1000;', 'const COOLDOWN = 20 * 1000;'),
                 ('delayInMinutes: 1, periodInMinutes', 'delayInMinutes: 0.1, periodInMinutes')]:
        assert a in s, a
        s = s.replace(a, b)
    open(p, 'w', encoding='utf-8', newline='\n').write(s)
    with open(os.path.join(ext, 'known.json'), 'w', encoding='utf-8') as f:
        json.dump({'courses': lec.COURSES, 'knownFiles': [], 'board': {}}, f)
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
    pr = subprocess.Popen(['node', os.path.join(HERE, 'chrome_pipe.mjs'), lec.chrome_exe(), ext, f'--user-data-dir={prof}', '--no-first-run', '--no-default-browser-check',
                           '--headless=new', f'--host-resolver-rules=MAP mylms.korea.ac.kr 127.0.0.1:{port}', '--ignore-certificate-errors', 'about:blank'],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, encoding='utf-8', creationflags=0x08000000)
    try:
        print('  ' + pr.stdout.readline().strip(), flush=True)
        tv, ts, env = ccc.temp_vault(os.path.join(tmp, 'v'))
        env.update(LMS_DOWNLOADS=dl, LMS_CHROME_PROFILE=prof, LMS_HOLD='330', LMS_HOLD_TICK='5')
        la = mod('la_ext', os.path.join(ts, 'lms-auto.py'))
        ok('시험 크롬이 프로필을 쥠(chrome_up)', any(la.chrome_up(prof) or time.sleep(1) for _ in range(20)))
        t0 = time.time()
        r = subprocess.run(['py', '-3.11', os.path.join(ts, 'lms-auto.py'), '--at', 'mylms'], cwd=tv, env=env, capture_output=True,
                           encoding='utf-8', errors='replace', timeout=400, creationflags=0x08000000)
        secs = int(time.time() - t0)
        log = ccc.read(os.path.join(tmp, 'v', 'lms-state', 'auto.log'))
        runs = [n for n in os.listdir(os.path.join(tmp, 'v', 'lms-state', 'runs'))] if os.path.isdir(os.path.join(tmp, 'v', 'lms-state', 'runs')) else []
        print(f'  {secs}초 · auto.log 끝: ' + ' / '.join(ln[11:19] + ' ' + ln[20:90] for ln in log.splitlines()[-6:]), flush=True)
        ok('크롬이 떠 있으면 안 띄움(«이미 실행 중»)', '깨우기: 크롬 이미 실행 중' in log, log[-300:])
        ok('확장이 받기를 끝냄 → 15분 반영 없이 바로 반영(runs 로 옮김 · «반영 끝»)', '깨우기: 반영 끝' in log and any(n.startswith('lms-run-') for n in runs), (runs, log[-400:]))
        ok('내려받기에 요약이 안 남음', not [n for n in os.listdir(dl) if n.startswith('lms-run-')], os.listdir(dl))
    finally:
        try:
            pr.stdin.write('close\n')
            pr.stdin.flush()
            pr.wait(20)
        except (OSError, subprocess.TimeoutExpired):
            pr.kill()
        kill(prof)
        srv.shutdown()


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    part = sys.argv[1] if len(sys.argv) > 1 else ''
    if part not in ('task', 'ext'):
        print(__doc__)
        return 2
    part_task() if part == 'task' else part_ext()
    print(f'\n{sum(res)}/{len(res)} 통과')
    return 0 if res and all(res) else 1


if __name__ == '__main__':
    sys.exit(main())
