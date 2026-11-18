"""로그인 가족 `browser` — 사람 크롬 안 확장이 받은 것을 볼트에 들인다(본체 · 11-16 수집 범용화 S4 · 옛 학교 전용 반영 대본에서 옮김).

출처 = 조리법 `3_시스템/collect/browser/<id>.json`(개인 층) · 플랫폼 어댑터 = `3_시스템/collect-adapters/<이름>.py`(조리법 `adapters` 차례).
확장이 다운로드 폴더에 남긴 요약 <run_prefix><run>.json 마다(15분 반영 collect-tick.py 가 부름):
  요약 보관(상태 폴더 runs/) → 어댑터 판정(대기열) → 검증 → 파일화(조리법 filer · 원시 <raw_prefix>*-<run>*.json) → ingest.py(바뀐 단위 색인) → schedule.py build(일정)
  그 뒤 같은 반영이 known-<id>.json(확장이 읽는 «이미 받은 것» · 실행 칸) · 제출 기록 · 침묵 감시 · 보고(report.txt)를 부른다.
확장(본체 `3_시스템/collect-ext/` · 조리법을 읽는 실행기 · S5) ← PC: 그 폴더의 ext-state.json(출처 id 목록) + known-<id>.json(exec = 조리법 실행 칸 · 멈춤 · 지금 받기).
상태 알림(kind=status · 로그인 끊김·되살아남)은 대기열 줄 하나를 열고 닫기만 한다. 실패·사람 몫(로그인 등)은 수집 대기열에 — 로그인은 사람.
시각 받기·깨우기 = 본체 예약 엔진(collect-schedule.py)의 «제공자» 약속: schedule_tasks(wake) · run_at(sid) · at_sources() · LEGACY_TASKS.

조리법 칸: id · name(받은 것 줄·제출 기록 이름) · family(browser) · adapters · run_prefix · raw_prefix · raw_dir(원본 층 아래 원시 보관 칸)
  · units(단위 지도 {번호: 폴더 이름}) · units_root(단위 폴더의 역할 · roles.json) · manifest(파일화 장부) · ext{host(https://호스트 · 확장이 여는 곳 · 팝업 «허용» 대상), keep_days(세션 쿠키에 붙일 만료 · 0 = 안 붙임), tools{어댑터: 사이트 번호}(예: learningx = 게시판 LTI 도구 번호 · 학교마다 다름 · S7)}
  · state(로그·요약 보관·잠금 자리) · settings(enabled·at·fetch_now 를 읽는 파일) · at_default(settings 에 at 칸이 없을 때)
  · action(시각 예약이 부르는 행위) · legacy_tasks(맡아 둔 옛 예약 이름) · wake_level(기능 단계 id) · filer(파일화 대본)
  · login{line(끊김 대기열 줄), cookie_domain(쿠키 판정 도메인)} · report{from, days, login_max, items_note, items}

  py -3.11 3_시스템/collect-browser.py --known [--source <id>]       # 확장 쪽 known-<id>.json·ext-state.json 만 다시 쓰기
  py -3.11 3_시스템/collect-browser.py --wake [--source <id>]        # (옛 깨우기 예약) 크롬을 뒤에서 띄우고 반영까지 PC 를 붙든다 · 재우는 것은 윈도 몫
  py -3.11 3_시스템/collect-browser.py --report [--source <id>]      # 판정 — 날마다 받기·끊김 · 연속 · 배터리 깨기 · 사람 로그인 · 세션 수명
  py -3.11 3_시스템/collect-browser.py --submissions                 # 제출 기록 일반 칸만 다시 쓰기
  py -3.11 3_시스템/collect-browser.py --wake-state [--source <id>]  # on | off <까닭> — 시각 예약을 둘지
시험만: COLLECT_TEST_STATE(상태 폴더) · COLLECT_DOWNLOADS · COLLECT_CHROME_PROFILE(임시 프로필) · COLLECT_CHROME_ARGS(더할 크롬 인자 JSON) · COLLECT_HOLD · COLLECT_HOLD_TICK · COLLECT_TASK_DRY=1.
"""
import argparse
import contextlib
import ctypes
import glob
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import time

SYS = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(SYS)
sys.path.insert(0, SYS)
import roles  # noqa: E402 — 단위 폴더·원본 자리는 역할로(구조를 옮겨도 따라감)
import collectlib as cl  # noqa: E402 — 수집 엔진 공통(로그·대기열·시각·스위치·잠금)

RECIPES = os.path.join(SYS, 'collect', 'browser')
ADAPTERS = os.path.join(SYS, 'collect-adapters')
EXT = os.path.join(SYS, 'collect-ext')                             # 확장 폴더(본체 · S5) — PC 가 쓰는 출처 목록·known 이 여기(확장은 제 폴더만 읽는다)
TEST_STATE = os.environ.get('COLLECT_TEST_STATE') or ''                # 시험 때만 — 상태(로그·대기열·요약 보관·깨기 표시)를 이 폴더로
DOWNLOADS = os.environ.get('COLLECT_DOWNLOADS') or os.path.join(os.path.expanduser('~'), 'Downloads')
PY = sys.executable
HOLD = float(os.environ.get('COLLECT_HOLD') or 25 * 60)                # 예약 깨우기 뒤 PC 를 붙드는 최대 시간(초 · 시험만 줄인다)
HOLD_TICK = float(os.environ.get('COLLECT_HOLD_TICK') or 30)           # 붙드는 동안 몇 초마다 보나(시험만 줄인다)
CHROME_PROFILE = os.environ.get('COLLECT_CHROME_PROFILE') or ''        # 시험만 — 임시 프로필(비면 본 프로필 = 크롬 기본 자리)
REPORT_EVERY = 3600
TASK = '외부뇌-수집 '                                               # 시각 예약 이름 머리(collect-schedule.py 와 같음)
QUIET_LINE = '확장 침묵 — 깨어 있던 26시간 동안 요약 없음(크롬 꺼짐·확장 고장·확장 끔 확인)'
RESTART_NEAR = 120         # 끊김·넘김이 크롬 시작 기록 뒤 이 초 안이면 «재시작 뒤» — 확장 0.3.0 은 시작과 첫 확인이 겹치면 까닭 칸이 gap 으로 남는다(11-05 13:07 실측 · 시작 1초 뒤 끊김이 gap)


def now():
    return cl.now()


def sh(args):
    p = subprocess.run(args, cwd=VAULT, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))  # 예약 작업에서 콘솔 창이 번쩍이지 않게
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def switches():
    """수집 전체 스위치 all_off·auto_judge·wake_pc — collectlib.switches(이 PC 의 collect.local.json)."""
    return cl.switches(SYS)


def _load(name, path):
    sp = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(sp)
    sp.loader.exec_module(m)
    return m


_mods = {}


def adapter(name):
    """플랫폼 어댑터 — collect-adapters/<이름>.py(PART · RAW · SIGNALS · judge · counts · known · [submissions])."""
    if not re.fullmatch(r'[a-z0-9_]+', name or ''):
        raise ValueError(f'어댑터 이름 꼴: {name!r}')
    if name not in _mods:
        _mods[name] = _load('collect_adapter_' + name, os.path.join(ADAPTERS, name + '.py'))
    return _mods[name]


def engine():
    """본체 시각 예약 엔진(collect-schedule.py) — 예약 맞추기·schtasks 는 그쪽."""
    if 'engine' not in _mods:
        _mods['engine'] = _load('collect_schedule', os.path.join(SYS, 'collect-schedule.py'))
    return _mods['engine']


def tick_mod():
    """15분 반영(collect-tick.py) — 깨우기가 요약을 보면 기다리지 않고 바로 반영한다."""
    if 'tick' not in _mods:
        _mods['tick'] = _load('collect_tick', os.path.join(SYS, 'collect-tick.py'))
    return _mods['tick']


def recipes():
    """로그인 가족 조리법 — collect/browser/*.json(family browser · id 가 파일 이름과 같음). 못 읽는 것은 건너뜀."""
    out = []
    for p in sorted(glob.glob(os.path.join(RECIPES, '*.json'))):
        try:
            rc = json.load(open(p, encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(rc, dict) and rc.get('family') == 'browser' and rc.get('id') == os.path.splitext(os.path.basename(p))[0]:
            out.append(rc)
    return out


def put_text(path, text):
    """확장 폴더 파일 쓰기 — 임시 파일 → 바꿔치기(확장이 반쯤 쓴 파일을 읽지 않게)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f'{path}.{os.getpid()}.tmp'       # 창의 --known 과 15분 반영이 같은 순간에 써도 서로의 임시 파일을 안 덮는다
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    for i in range(10):                     # 윈도는 다른 쪽이 바꾸거나 크롬이 읽는 순간 거부한다(동시 12개 실측 1건 · 11-05)
        try:
            os.replace(tmp, path)
            break
        except PermissionError:
            if i == 9:
                os.remove(tmp)
                raise
            time.sleep(0.2)


def write_index():
    """확장이 읽는 출처 목록 ext-state.json = 로그인 조리법 id 들 — 바뀔 때만 쓴다. 새 출처 = 조리법 파일 하나(확장 코드는 그대로)."""
    body = json.dumps({'sources': [rc['id'] for rc in recipes()]}, ensure_ascii=False, indent=1)
    p = os.path.join(EXT, 'ext-state.json')
    try:
        if open(p, encoding='utf-8').read() == body:
            return
    except OSError:
        pass
    put_text(p, body)


_srcs = []


def sources():
    """조리법마다 출처 하나(한 프로세스 안에서 같은 물체 — 시험이 고친 것이 반영에도 쓰이게)."""
    if not _srcs:
        _srcs.extend(Source(rc) for rc in recipes())
    return list(_srcs)


def source(sid=None):
    """그 id 의 출처 — 없으면 첫 출처. 출처가 하나도 없으면 None."""
    ss = sources()
    return next((s for s in ss if s.id == sid), None) if sid else (ss[0] if ss else None)


class Source:
    """로그인 출처 하나 — 조리법 값 + 그 출처의 상태 자리. 이름(대문자 칸)은 옛 반영 대본의 전역 이름 그대로(시험이 같은 이름으로 바꿔 넣는다)."""

    def __init__(self, rc):
        self.rc = rc
        self.id = rc['id']
        self.name = rc.get('name') or self.id
        p = lambda rel: os.path.join(SYS, *rel.split('/'))
        self.STATE = TEST_STATE or p(rc.get('state') or '_index/' + self.id)
        self.RUNS = os.path.join(self.STATE, 'runs')
        self.LOG = os.path.join(self.STATE, 'auto.log')
        self.QUIET = os.path.join(self.STATE, 'quiet.json')        # 요약 없이 지난 예약 횟수
        self.STATS = os.path.join(self.STATE, 'stats.json')        # 검증기 기준 — 단위별 지난 개수
        self.REPORT = os.path.join(self.STATE, 'report.txt')       # --report 출력 — 로드맵 화면이 읽는다(화면은 명령을 안 돌린다)
        self.REPORT_TRY = os.path.join(self.STATE, 'report.try')   # 마지막으로 쓰려 한 때 — 실패해도 1시간에 한 번만 다시 잰다
        self.QUEUE = os.path.join(TEST_STATE, 'repair-queue.md') if TEST_STATE else cl.QUEUE    # 수집 공용 대기열
        self.MANIFEST = p(rc['manifest'])
        self.UNITS = p(rc['units'])
        self.units_name = os.path.basename(self.UNITS)
        self.KNOWN = os.path.join(EXT, f'known-{self.id}.json')
        self.SETTINGS = p(rc['settings']) if rc.get('settings') else ''
        self.run_prefix = rc['run_prefix']
        self.raw_prefix = rc['raw_prefix']
        self.filer = rc.get('filer') or ''
        login = rc.get('login') or {}
        self.LOGIN_LINE = login.get('line') or f'{self.id} 로그인 만료 — 크롬에서 로그인'
        self.host = login.get('cookie_domain') or ''
        self.adapters = [adapter(n) for n in rc.get('adapters') or []]

    # ── 작은 부품 ──
    def sh(self, args):
        return sh(args)

    def log(self, msg):
        """한 줄 덧붙이기 — 쓰는 동안만 <로그>.lock 을 잡는다(collectlib.log_line · 11-12 찢긴 줄 실측)."""
        cl.log_line(self.LOG, msg)
        print(msg)

    def close_lines(self, text):
        """그 일이 풀렸다 — 열린 줄을 닫는다(사람이 지우지 않아도 대기열이 실제 상태를 말하게)."""
        if cl.queue_close(text, self.QUEUE):
            self.log(f'대기열: 줄 닫음 — {text[:30]}')

    def close_login(self):
        self.close_lines(self.LOGIN_LINE)

    def queue(self, run, what, who='Claude', once=False):
        """대기열 — 한 줄 = 한 건. who = 고칠 사람(로그인·보안 검사는 사람). once = 상태 줄(같은 줄이 열려 있으면 또 쓰지 않음) · 사건 줄(격리·누락)은 수집마다 남긴다."""
        os.makedirs(self.STATE, exist_ok=True)
        mode = 'what' if (once or what in (self.LOGIN_LINE, QUIET_LINE)) else None
        if cl.queue_add(run, what, who, once=mode, path=self.QUEUE):
            self.log(f'대기열 {run}: {what}')

    def settings(self):
        """출처 스위치(enabled·at·fetch_now) — 없거나 못 읽으면 전부 켜짐. 전체 스위치는 switches()."""
        try:
            d = json.load(open(self.SETTINGS, encoding='utf-8'))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def units(self):
        """단위 지도 {번호: 폴더 이름}(«_제외» 칸 포함) — 못 읽으면 예외."""
        return json.load(open(self.UNITS, encoding='utf-8'))

    def raw_files(self, kind):
        """원본 층에 보관한 그 종류의 원시 — 오래된 것부터."""
        return sorted(glob.glob(os.path.join(roles.abs('sources'), self.rc.get('raw_dir') or '', f'{self.raw_prefix}{kind}-*.json')), key=os.path.getmtime)

    def topic(self, name):
        return roles.canon(name) or name

    def at(self):
        """크롬을 띄울 시각 — settings at(빈 목록 = 안 띄움) · 칸이 없거나 틀리면 at_default."""
        d = self.settings()
        if 'at' not in d:
            return list(self.rc.get('at_default') or [])
        try:
            return cl.at_times(d.get('at'))
        except ValueError:
            return list(self.rc.get('at_default') or [])

    # ── 요약 들이기 ──
    def intake(self, dry=False):
        """다운로드의 요약을 차례로 처리 — 한 요약이 깨져도 다음 것은 간다. 돌려줌 = 처리한 요약 수(상태 알림 포함)."""
        runs = sorted(glob.glob(os.path.join(DOWNLOADS, f'{self.run_prefix}*.json')), key=os.path.getmtime)
        for sp in runs:
            try:
                self.process(sp, dry)
            except Exception as e:  # 한 수집이 깨져도 다음 것과 known 갱신은 간다
                self.queue(os.path.basename(sp), f'{self.id} 반영 예외 `{e!r}`')
        return len(runs)

    def process(self, sp, dry):
        s = json.load(open(sp, encoding='utf-8'))
        run = s.get('run') or os.path.basename(sp)[len(self.run_prefix):-5]
        since = (s.get('startedAt') or os.path.getmtime(sp) * 1000) / 1000 - 60
        parts = ' '.join(f'{a.PART}={(s.get(a.PART) or {}).get("state")}' for a in self.adapters)
        self.log(f'확장 상태 {run}: 로그인 {s.get("login")}' if s.get('kind') == 'status' else
                 f'수집 {run} ({s.get("why")}) 오류={s.get("error")} {parts}')
        if dry:
            return
        os.makedirs(self.RUNS, exist_ok=True)
        dest = os.path.join(self.RUNS, os.path.basename(sp))
        if os.path.exists(dest):                                    # 같은 분에 난 요약 — 덮지 않는다
            base, ext = os.path.splitext(dest)
            dest = f'{base}-{int(time.time())}{ext}'
        shutil.move(sp, dest)  # 먼저 치운다 — 파일화가 <raw_prefix>*-<run>*.json 으로 요약까지 집어 가지 않게(10-26 첫 실수집)
        if s.get('kind') == 'status':                               # 받은 것 없는 상태 알림 — 아래 파일화·일정 없음
            if s.get('login') == 'out':
                self.queue(run, self.LOGIN_LINE, roles.me())
            else:
                self.close_login()
            return
        if s.get('error') == 'login_required':
            self.queue(run, self.LOGIN_LINE, roles.me())
        elif s.get('error') == 'net':
            self.log(f'{run}: 망 오류 — 확장이 다음 확인 때 다시 한다')
        elif s.get('error'):
            self.queue(run, f'확장 오류 `{s["error"]}`')
        else:
            self.close_login()
        cmap = self.units()
        fresh = [f'{c.get("id")} {c.get("name")}' for c in s.get('activeCourses') or []
                 if str(c.get('id')) not in cmap and str(c.get('id')) not in (cmap.get('_제외') or {})]
        if fresh:                                                   # 새 학기 — 지도에 없는 단위는 조용히 안 받는다
            self.queue('courses', f'과목 지도({self.units_name})에 없는 수강 강좌 {len(fresh)}개: {fresh}'[:400], once=True)
        for a in self.adapters:
            part = a.PART
            st = (s.get(part) or {}).get('state')
            if st and st != 'done':
                self.queue(run, f'{part} 상태 `{st}` · {json.dumps((s.get(part) or {}).get("result") or (s.get(part) or {}).get("results"), ensure_ascii=False)[:300]}')
        for a in self.adapters:                                     # state 가 done 이어도 속은 실패일 수 있다 — 어댑터가 칸을 본다
            a.judge(self, run, s)
        sig = s.get('signals') or {}
        dead = [k for a in self.adapters for k in a.SIGNALS if k in sig and sig[k] != 200]
        if dead:
            self.queue('signals', f'신호 안 됨 {dead} {[sig[k] for k in dead]} — 전 과목 받기만으로 돈다', once=True)
        else:
            self.close_lines('신호 안 됨')
        if s.get('workerBlind'):
            self.queue('signals', '워커 fetch 에 쿠키가 안 실림 — 신호를 못 본다(탭으로 받기만)', once=True)
        self.verify(run, s)
        rq = s.get('requests') or {}
        if rq:
            self.log(f'요청 GET {rq.get("get")} · 그 밖 {sum((rq.get("other") or {}).values())} · 막힘 {sum((rq.get("blocked") or {}).values())}')

        jsons = glob.glob(os.path.join(DOWNLOADS, f'{self.raw_prefix}*-{run}*.json'))
        jsons = [j for j in jsons if not os.path.basename(j).startswith(self.run_prefix)]
        if jsons and not self.filer:                # 파일화 대본이 없는 출처(배포판에서 처음 만든 출처 · S6) — 원시는 다운로드 폴더에 둔 채 한 줄만
            self.queue('filer', f'파일화 대본 없음(조리법 filer) — 받은 원시 {len(jsons)}개가 다운로드 폴더에 남음', once=True)
            jsons = []
        if jsons:
            fname = os.path.splitext(self.filer)[0]
            rc, out = self.sh([PY, os.path.join(SYS, self.filer), '--source', self.id, '--run', run, '--since', str(since), '--downloads', DOWNLOADS])
            if rc:
                self.queue(run, f'{self.filer} 실패 rc={rc}')
            left = [os.path.basename(j) for j in jsons if os.path.exists(j)]
            if left:
                self.queue(run, f'처리 안 된 JSON {left}')
            try:                                    # 파일화 끝의 보고 = 첫 칸 «{» 로 시작하는 마지막 JSON
                starts = [m.start() for m in re.finditer(r'^\{', out, re.M)]
                rep = json.loads(out[starts[-1]:]) if starts else {}
            except ValueError:
                rep = {}
            # 로그는 보고의 숫자만(전문을 자르면 정작 숫자가 잘린다 — 10-27)
            self.log(f'{fname} rc={rc} 새 글 {rep.get("md")} · 바뀐 글 {rep.get("md_changed")} · 파일 들임 {rep.get("files_in")} · 중복 {rep.get("files_dup")} · '
                     f'짝메모 {rep.get("memos")} · 격리 {len(rep.get("files_quarantined") or [])} · 누락 {len(rep.get("files_missing") or [])}'
                     + ('' if rep else ' · 보고 못 읽음: ' + ' '.join(out.split())[-300:]))
            if rep.get('files_quarantined'):
                self.queue(run, f'격리 {len(rep["files_quarantined"])}건 — 검사기 오탐인지 확인', roles.me() + '·Claude')
            if rep.get('files_missing'):
                self.queue(run, f'다운로드 누락 {len(rep["files_missing"])}건 {[x.get("name") for x in rep["files_missing"]][:3]} — 다음 받기에 다시 연다(세 번까지)'[:300])
            units = self.units()
            root = roles.abs(self.rc['units_root']) if self.rc.get('units_root') else VAULT
            folders = [os.path.join(root, units[c]) for c in (rep.get('courses') or units) if c in units]
            folders = [f for f in folders if os.path.isdir(f)]
            if folders:
                rc, out = self.sh(['py', '-3', os.path.join(SYS, 'ingest.py'), *folders])   # ingest 는 py -3(pypdfium2) — incident-2026-10-25
                self.log(f'ingest rc={rc} ' + ' '.join(out.split())[-300:])
                if rc:
                    self.queue(run, f'ingest.py 실패 rc={rc}')
        else:
            self.log(f'{run}: 내려받은 수집 JSON 없음')
            if not s.get('error') and 'done' in [(s.get(a.PART) or {}).get('state') for a in self.adapters]:
                self.queue(run, '요약은 끝났는데 수집 JSON 이 안 내려옴 — 크롬 다운로드 막힘 확인')
        rc, out = self.sh([PY, os.path.join(SYS, 'schedule.py'), 'build'])
        self.log(f'schedule rc={rc} {out.strip()}')
        if rc:
            self.queue(run, f'schedule.py 실패 rc={rc} ' + ' '.join(out.split())[-200:], once=True)

    def verify(self, run, s):
        """검증기 — 오류 없이 조용히 비는 실패를 잡는다. 화면·API 가 바뀌면 «0건 성공»이 된다.
        단위마다 지난 수집의 개수(어댑터가 셈)와 견주고, 단위 지도에 있는데 빠진 단위를 찾는다."""
        prev = json.load(open(self.STATS, encoding='utf-8')) if os.path.exists(self.STATS) else {}
        cur = {}
        for a in self.adapters:
            cur.update(a.counts(s))
        expected = [str(c) for c in s['scope']] if s.get('scope') else [k for k in self.units() if k.isdigit()]  # 신호 수집은 바뀐 단위만
        for a in self.adapters:
            if (s.get(a.PART) or {}).get('state') == 'done':
                gone = [c for c in expected if f'{a.PART}:{c}' not in cur]
                if gone:
                    self.queue(run, f'검증: {a.PART} 결과에 없는 과목 {gone}', once=True)
        for k, v in cur.items():
            if v == 0 and prev.get(k, 0) > 0:
                self.queue(run, f'검증: {k} 0건(지난 수집 {prev[k]}건) — 화면·API 구조 변화 의심', once=True)
        prev.update({k: v for k, v in cur.items() if v > 0})   # 0 은 기준을 덮지 않는다(한 번 빈 것으로 기준이 무너지지 않게)
        os.makedirs(self.STATE, exist_ok=True)
        with open(self.STATS, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(prev, f, ensure_ascii=False, indent=1)

    # ── PC → 확장 ──
    def exec_block(self):
        """확장 실행 칸(known-<id>.json 의 exec) — 조리법 값만 넘긴다(어댑터 코드는 확장 폴더 안 · 조리법은 데이터)."""
        e = self.rc.get('ext') or {}
        return {'name': self.name, 'host': str(e.get('host') or '').rstrip('/'), 'adapters': list(self.rc.get('adapters') or []),
                'run_prefix': self.run_prefix, 'raw_prefix': self.raw_prefix, 'cookie_domain': self.host, 'keep_days': int(e.get('keep_days') or 0),
                'tools': {str(k): v for k, v in (e.get('tools') or {}).items() if str(v).isdigit()}}      # 어댑터가 쓰는 사이트 번호(예: learningx 게시판 LTI 도구) · S7

    def write_known(self):
        """확장이 15분 확인 때 읽는 known-<id>.json — 실행 칸 · 단위 · 어댑터 몫(이미 받은 것) · 멈춤 · 지금 받기. 출처 목록 ext-state.json 도 맞춘다."""
        man = json.load(open(self.MANIFEST, encoding='utf-8')) if os.path.exists(self.MANIFEST) else {}
        units = self.units()
        known = {'generatedAt': now(), 'exec': self.exec_block(), 'courses': [int(k) for k in units if k.isdigit()]}
        for a in self.adapters:
            known.update(a.known(self, man))
        d = self.settings()
        known['paused'] = switches().get('all_off') is True or d.get('enabled') is False    # 확장이 15분 확인 때 읽고 멈춘다
        if d.get('fetch_now'):          # 수집 창 «지금 받기» — PC 에서 확장으로 가는 길은 이 파일뿐이라 다음 15분 확인 때 돈다
            known['fetchNow'] = d['fetch_now']
        put_text(self.KNOWN, json.dumps(known, ensure_ascii=False, indent=1))
        write_index()
        return known

    # ── 제출 기록(work.py 근거 «제출») ──
    def submissions_by(self):
        by = {}
        for a in self.adapters:
            if hasattr(a, 'submissions'):
                by.update(a.submissions(self))
        return by

    def write_submissions(self):
        """제출 기록 일반 칸 _index/collect/제출/<id>.json 에 이 출처 몫을 쓴다 — 임시 파일 뒤 교체 · 같으면 안 씀."""
        path = os.path.join(SYS, '_index', 'collect', '제출', self.id + '.json')
        text = json.dumps({'name': self.name, 'by': self.submissions_by()}, ensure_ascii=False, indent=1, sort_keys=True)
        try:
            if open(path, encoding='utf-8').read() == text:
                return False
        except OSError:
            pass
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + '.tmp', 'w', encoding='utf-8', newline='\n') as f:
            f.write(text)
        os.replace(path + '.tmp', path)
        return True

    def submit(self):
        """반영 뒤(새 요약이 들어온 때만) — 실패는 대기열 한 줄."""
        try:
            self.write_submissions()
        except Exception as e:
            self.queue('submissions', f'제출 기록 쓰기 실패 `{e!r}`', once=True)

    # ── 감시 ──
    def quiet_watch(self, got):
        """요약이 안 오는 것을 잡는다 — 크롬 꺼짐·확장 고장·확장 끔. 0.1.x 는 이렇게 일주일을 모르고 지났다.
        예약이 15분마다 부르니 횟수 = 깨어 있던 시간(절전·꺼짐은 안 센다). 전 단위 받기가 12시간마다니 26시간이면 고장이다."""
        d = json.load(open(self.QUIET, encoding='utf-8')) if os.path.exists(self.QUIET) else {'ticks': 0}
        d['ticks'] = 0 if got else d['ticks'] + 1
        days = d.setdefault('days', {})                             # 날마다 예약이 돈 횟수 = 그날 PC 가 깨어 있었다는 증거(판정이 «꺼진 날»을 가른다)
        today = time.strftime('%Y-%m-%d')
        days[today] = days.get(today, 0) + 1
        for k in sorted(days)[:-40]:
            del days[k]
        if got:
            self.close_lines(QUIET_LINE)
        elif d['ticks'] == 26 * 4:
            with open(self.QUEUE, encoding='utf-8') if os.path.exists(self.QUEUE) else io.StringIO() as f:
                if not re.search(r'^- \[ \] .*' + re.escape(self.LOGIN_LINE), f.read(), re.M):      # 로그인 끊김이면 그 줄이 이미 말한다
                    self.queue('extension', QUIET_LINE, roles.me() + '·Claude')
        with open(self.QUIET, 'w', encoding='utf-8') as f:
            json.dump(d, f)

    def watch(self, n):
        """반영 끝 감시 — 침묵(끈 동안 요약이 없는 것은 침묵이 아니다) · 받기 도중 끊겨 요약 없이 남은 원시."""
        self.quiet_watch(bool(n) or self.settings().get('enabled') is False)
        stale = [os.path.basename(p) for a in self.adapters for p in glob.glob(os.path.join(DOWNLOADS, f'{self.raw_prefix}{a.RAW}-*.json'))
                 if time.time() - os.path.getmtime(p) > 2 * 3600]
        if stale:                                               # 받기 도중 끊겨 요약이 안 남은 수집 — 조용히 쌓이지 않게
            self.queue('orphan', f'요약 없는 수집 JSON {len(stale)}개가 내려받기에 남음 — 끊긴 받기', once=True)

    # ── 판정(--report) ──
    def run_files(self):
        out = []
        for p in sorted(glob.glob(os.path.join(self.RUNS, f'{self.run_prefix}*.json'))):
            try:
                s = json.load(open(p, encoding='utf-8'))
            except ValueError:
                continue
            s['_t'] = (s.get('startedAt') or s.get('at') or os.path.getmtime(p) * 1000) / 1000
            out.append(s)
        return sorted(out, key=lambda s: s['_t'])

    def cookie_judge(self, runs, events):
        """출처 쿠키에 영구(만료)가 붙어 있는가 — (판정, 줄 목록). 값은 안 본다(이름·종류·개수만). 도메인 = 조리법 login.cookie_domain(상위 도메인 쿠키는 안 셈).
        근거 = 크롬을 켤 때 세션이던 쿠키 개수(startup 기록 · 확장 0.3.0 부터) · 저장 실패 기록 · 영구로 찍힌 요약.
        요약의 «세션으로 남은 것»은 판정에 안 쓴다 — 받기가 끝난 순간이라 서버가 방금 준 쿠키는 쿠키가 바뀐 뒤 3초(계속 바뀌어도 30초)까지 세션이다.
        11-05 16:30 요약(13초 런 · GET 156)이 5/5 세션으로 찍혀 «뒷걸음»으로 읽혔다(격리 쿠키 시험이 같은 모양을 재현 — 세션으로 찍힌 쿠키도 뒤이어 영구가 된다)."""
        mine = lambda meta: [c for c in meta or [] if str(c.get('domain', '')).lstrip('.') == self.host]
        starts = [e for e in events if e.get('ev') == 'startup' and e.get('cookies') is not None]
        fails = [e for e in events if e.get('ev') == 'keep_fail']
        snaps = []
        for s in runs:
            ms = mine(s.get('cookies'))
            if ms:
                snaps.append({'t': (s.get('startedAt') or s['_t'] * 1000), 'n': len(ms), 'kept': sum(1 for c in ms if not c.get('session')),
                              'dur': round(((s.get('endedAt') or 0) - (s.get('startedAt') or 0)) / 1000)})
        last = starts[-1] if starts else None
        if fails:
            verdict = f'의심 — 저장 실패 {len(fails)}회({", ".join(sorted({str(e.get("name")) for e in fails}))})'
        elif last and not last.get('cookies'):
            verdict = f'의심 — 크롬을 켤 때 쿠키 0개({hm(last["t"])})'
        elif last and last.get('session'):
            verdict = f'의심 — 크롬을 켤 때 세션 쿠키 {last["session"]}/{last["cookies"]}개({hm(last["t"])})'
        elif last or any(x['kept'] for x in snaps):
            verdict = '유지됨'
        else:
            verdict = '미확인(크롬을 다시 켠 기록도 영구로 찍힌 요약도 아직 없다)'
        good = [e for e in starts if e.get('cookies') and not e.get('session')]
        parts = [f'크롬을 켤 때 전부 영구 {len(good)}/{len(starts)}회' + (f'({" · ".join(hm(e["t"]) for e in starts[-4:])})' if starts else ''),
                 f'저장 실패 {len(fails)}회']
        kept = [x for x in snaps if x['kept']]
        if kept:
            parts.append('영구로 찍힌 요약 ' + ' · '.join(f'{hm(x["t"])} {x["kept"]}/{x["n"]}' for x in kept[-3:]))
        lines = [f'· 쿠키 영구(판정): {verdict} — ' + ' · '.join(parts)]
        if snaps:
            # 앞머리 «쿠키: <출처> N개 · 세션 쿠키로 남은 것 K개»는 그대로 둔다 — 로드맵 화면 대본(제작자 측정 대본)이 이 모양을 정규식으로 읽는다
            x = snaps[-1]
            lines.append(f'· 쿠키: {self.id} {x["n"]}개 · 세션 쿠키로 남은 것 {x["n"] - x["kept"]}개(마지막 요약 {hm(x["t"])} 런 {x["dur"]}초 · 값은 안 봄'
                         + (' — 받기가 끝난 순간엔 방금 받은 쿠키가 세션으로 보인다(저장은 바뀐 뒤 3~30초) → 판정에 안 씀 · 위 «쿠키 영구(판정)»을 본다)' if x['n'] > x['kept'] else ')'))
        return verdict, lines

    def report(self, days=None):
        """M2 판정 — 완료 기준(조리법 report 칸)을 칸마다 잰다. 기준을 넘긴 칸만 «통과», 못 잰 칸은 «보류»·«안 잼»으로 둔다(과대 마감 금지)."""
        rp = self.rc.get('report') or {}
        need = int(rp.get('days') or 7)
        days = need if days is None else days
        m2_from = rp.get('from') or '2000-01-01'
        login_max = rp.get('login_max')
        items = [tuple(x) for x in rp.get('items') or []]
        runs = self.run_files()
        events = login_events(runs)
        quiet = json.load(open(self.QUIET, encoding='utf-8')) if os.path.exists(self.QUIET) else {}
        awake = quiet.get('days') or {}
        log_text = open(self.LOG, encoding='utf-8', errors='replace').read() if os.path.exists(self.LOG) else ''     # 찢긴 줄 하나에 판정 전체가 죽지 않게(11-12)
        day = lambda t: time.strftime('%Y-%m-%d', time.localtime(t))
        today = time.strftime('%Y-%m-%d')
        d0 = max(m2_from, day(time.time() - (days * 2 - 1) * 86400))
        span = [day(time.mktime(time.strptime(d0, '%Y-%m-%d')) + i * 86400 + 7200) for i in range(0, 40)]
        span = [d for d in span if d <= today]
        # 그날 어느 때든 끊겨 있었는가 — 끊김 기록을 차례로 따라간다(첫 줄 앞 상태는 모름)
        out_days, st = set(), None
        for d in span:
            ev = [e for e in events if e.get('ev') == 'login' and day(e['t'] / 1000) == d]
            if st == 'out' or any(e.get('login') == 'out' for e in ev):
                out_days.add(d)
            st = ev[-1].get('login') if ev else st
        print(f'M2 판정 — {time.strftime("%m-%d %H:%M")} · 기준일 {m2_from} 부터 · 확장 판 {(runs[-1].get("version") if runs else "?")}')
        print('날짜   깸  무인받기 사람받기 일정 실패 끊김 판정')
        verdict = {}
        for d in span:
            rr = [s for s in runs if day(s['_t']) == d and s.get('kind') != 'status']
            good = [s for s in rr if not s.get('error') and (s.get(self.adapters[0].PART if self.adapters else '') or {}).get('state') == 'done']   # 받기 성공 = 첫 어댑터(주 플랫폼) 칸이 done
            auto = [s for s in good if s.get('why') in ('daily', 'signal')]   # 시험·단추로 돈 받기는 무인으로 안 친다
            hand = [s for s in good if s.get('why') not in ('daily', 'signal')]
            bad = len(rr) - len(good)
            sched = len(re.findall(r'^' + d + r' \d\d:\d\d:\d\d schedule rc=0', log_text, re.M))
            cut = d in out_days
            ticks = awake.get(d)
            if auto and sched:
                v = '통과'
            elif cut:
                v = '끊김'                  # 기준상 대기열·알림에 남으면 인정 — 아래 끊김 칸에서 본다
            elif not rr and not ticks:
                v = '꺼짐' if d != today else '진행 중'
            elif d == today:
                v = '진행 중'
            else:
                v = '미달'
            verdict[d] = v
            print(f'{d[5:]}  {ticks if ticks is not None else "-":>3} {len(auto):>6} {len(hand):>7} {sched:>4} {bad:>4} {"예" if cut else "":>3}  {v}')
        # 연속 — 꺼진 날·오늘 진행 중은 세지도 끊지도 않는다
        streak = 0
        for d in reversed(span):
            v = verdict[d]
            if v in ('꺼짐', '진행 중'):
                continue
            if v == '미달':
                break
            streak += 1
        off = sum(1 for d in span if verdict[d] == '꺼짐')
        print(f'· 연속 무인 수집: {streak}/{need}일(끊김으로 지난 날 포함 · 꺼진 날 {off}일은 안 셈) → {"통과" if streak >= need else "미달"}')
        # 끊김 칸 — 대기열에 남았는가 · 다시 로그인하면 바로 받았는가
        qt = open(self.QUEUE, encoding='utf-8').read() if os.path.exists(self.QUEUE) else ''
        logins = [e for e in events if e.get('ev') == 'login']
        cuts = [e for e in logins if e.get('login') == 'out']
        opened = sum(1 for e in cuts if time.strftime('%Y-%m-%d', time.localtime(e['t'] / 1000)) in qt or self.LOGIN_LINE in qt)
        still = len(re.findall(r'^- \[ \] .*' + re.escape(self.LOGIN_LINE), qt, re.M))
        print(f'· 끊김 알림: 끊김 {len(cuts)}회 · 대기열 줄 있음 {opened}회 · 지금 열린 줄 {still}')
        humans, delays = [], []
        for a, b in zip(logins, logins[1:]):
            if a.get('login') == 'out' and b.get('login') == 'ok':
                humans.append(b['t'] / 1000)
                nxt = [s['_t'] for s in runs if s.get('kind') != 'status' and s['_t'] >= b['t'] / 1000 - 60]
                delays.append(round((nxt[0] - b['t'] / 1000) / 60) if nxt else None)
        if delays:
            print(f'· 다시 로그인 → 받기까지(분): {delays} (None = 그 뒤 받기 없음 — 지난 받기가 안전망 안이면 정상)')
        week = [t for t in humans if t >= time.time() - 7 * 86400]
        verdict_login = '보류(N 미정 — 세션 수명 뒤 정함)' if login_max is None else ('통과' if len(week) <= login_max else '미달')
        print(f'· 사람 로그인: 최근 7일 {len(week)}회 · 기준 N={login_max} → {verdict_login}')
        # 세션 수명 — 쿠키가 남았는데 끊기면 서버 쪽 세션이 끝난 것이다(0.3.0 부터 기록)
        start, spans = None, []
        for e in logins:
            if e.get('login') == 'ok' and start is None:
                start = e['t']
            elif e.get('login') == 'out':
                if start is not None:
                    spans.append((start, e['t'], e))
                start = None
        server = [e for e in cuts if e.get('main') is True]
        lost = [e for e in cuts if e.get('main') is False]
        unknown = [e for e in cuts if e.get('main') is None]
        surv = [e for e in events if e.get('ev') == 'survived']
        print(f'· 끊긴 까닭: 서버 쪽 세션 끝 {len(server)}회 · 쿠키 잃음 {len(lost)}회 · 기록 전이라 모름 {len(unknown)}회')
        if spans:
            print('· 세션 수명(로그인→끊김을 본 때 · 꺼진 시간 포함): ' + ' · '.join(f'{time.strftime("%m-%d %H:%M", time.localtime(a / 1000))} {round((b - a) / 3600000, 1)}시간' for a, b, _ in spans[-6:]))
        if start is not None:
            print(f'· 지금 세션: {round((time.time() * 1000 - start) / 3600000, 1)}시간째 유지(서버 쪽 수명의 하한)')
        gone = [e.get('min') for e in server if e.get('min')]
        kept = [e.get('min') for e in surv if e.get('min')]
        r_ok = [e for e in surv if after_restart(e, events)]
        r_cut = [e for e in cuts if after_restart(e, events)]     # 까닭 칸이 gap 이어도 크롬을 켠 직후면 재시작 뒤 끊김이다
        print(f'· 재시작 넘김: 넘김 {len(r_ok)}회 · 재시작 뒤 끊김 {len(r_cut)}회' + ''.join(
            f' [{hm(e["t"])} 쿠키 {e.get("cookies", "?")}개 · {"서버 쪽 끝" if e.get("main") is True else "쿠키 잃음" if e.get("main") is False else "까닭 모름"}'
            + (f' · 틈 {e["min"]}분' if e.get('min') else '') + ']' for e in r_cut[-3:]))
        print(f'· 유휴 수명: 넘긴 가장 긴 틈 {max(kept) if kept else "-"}분 · 서버가 끊은 가장 짧은 틈 {min(gone) if gone else "-"}분')
        # 쿠키에 만료가 붙어 있는가(이름·종류·개수만) — 판정은 크롬을 켤 때 기록으로 · 요약 끝 순간은 참고
        for ln in self.cookie_judge(runs, events)[1]:
            print(ln)
        w = battery_wakes(days * 2)
        if w is None:
            print('· 배터리에서 깨기: 못 읽음(윈도 전원 기록)')
        else:
            print(f'· 배터리에서 타이머로 깨기: {w[0]}회 → {"통과" if w[0] == 0 else "미달"} · 전원 연결 타이머 깨기 {w[1]}회 · 그 밖 깸 {w[2]}회 · 입회 시험 깸 {w[3]}회(안 셈)')
        res = item_results(rp.get('items_note'))
        print('· 항목(사람 입회): ' + ' · '.join(f'{n} {res.get(k) or "안 잼"}' for n, k in items))
        print(f'· 요약 없이 지난 예약 {quiet.get("ticks", "-")}회')
        done = streak >= need and (w is not None and w[0] == 0) and login_max is not None and len(week) <= login_max and all(res.get(k) for _, k in items)
        print(f'판정: {"M2 완료 기준 통과" if done else "미달"} — 연속 {streak}/{need}일')

    def write_report(self):
        """수집 돌 때 --report 출력을 파일로 남긴다 — 1시간에 1번 이하(한 번에 약 3.9초 · 전원 기록 읽기). 맨 윗줄 = 잰 시각 · 낡으면 화면의 때로 드러난다.
        실패해도 수집 결과에 영향이 없다(잡아서 로그 한 줄)."""
        tmp = f'{self.REPORT}.{os.getpid()}.tmp'
        try:
            if os.path.exists(self.REPORT_TRY) and 0 <= time.time() - os.path.getmtime(self.REPORT_TRY) < REPORT_EVERY:
                return False
            os.makedirs(self.STATE, exist_ok=True)
            with open(self.REPORT_TRY, 'w', encoding='utf-8') as f:
                f.write(now() + '\n')
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                self.report()
            with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
                f.write(f'잰 시각: {now()}\n{buf.getvalue()}')
            os.replace(tmp, self.REPORT)
            return True
        except Exception as e:  # 판정 파일은 곁일이다 — 수집을 깨지 않는다
            try:
                self.log(f'report.txt 못 씀 {e!r}')
            except Exception:
                pass
            return False
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    # ── 깨우기·시각 예약 ──
    def wake_level(self):
        """기능 단계(조리법 wake_level · options.py) — 못 읽거나 칸이 없으면 'high'(지금 동작)."""
        lvl = self.rc.get('wake_level')
        if not lvl:
            return 'high'
        try:
            import options
            return options.level(lvl)
        except Exception:
            return 'high'

    def wake_chosen(self):
        """기능 단계의 고른 값(배터리 규칙 전) — 깨우기 예약을 둘지는 이 값으로 정한다(배터리로 잠깐 낮아진 값으로 예약을 지우지 않게). 못 읽으면 'high'."""
        lvl = self.rc.get('wake_level')
        if not lvl:
            return 'high'
        try:
            import options
            local, st = options._load(options.local_path(None))
            return options.chosen(local, st, options.declarations(None, only=lvl)).get(lvl, 'high')
        except Exception:
            return 'high'

    def wake_state(self):
        """시각 깨우기를 하나 — 값은 기능 단계 하나(수집 창 «깨우기» 스위치도 이 값을 바꾼다 · 11-07 «두 스위치 통일»).
        단계가 높음이어도 수집 전체 끔·출처 끔이면 안 깨운다(깨워 놓고 아무것도 안 하는 헛깨우기를 막음). 돌려줌 = (켬, 까닭 낱말)."""
        if switches().get('all_off') is True:
            return False, 'all_off'
        if self.settings().get('enabled') is False:
            return False, 'source_off'
        if self.wake_chosen() != 'high':
            return False, 'level_low'
        return True, ''

    def wake_sync(self):
        """시각 예약 전체를 맞춘다(본체 엔진) — 꺼진 날의 깨우기가 부른다."""
        return engine().sync_tasks(dry=bool(TEST_STATE or os.environ.get('COLLECT_TASK_DRY')))

    def schedule_task(self, wake):
        """이 출처의 시각 예약 줄 — 크롬이 필요한 방법 → 기능 단계 높음 · 출처 켬 · 시각이 있을 때만.
        행위 = 조리법 action --at <id> — 옛 깨우기 예약과 갈라 옛 것이 남아도 두 번 돌지 않게(legacy_wake)."""
        on, _ = self.wake_state()
        at = self.at()
        if on and at and self.rc.get('action'):
            return {TASK + self.id: (at, wake, [self.rc['action'], '--', '--at', self.id], f'{self.id}(크롬 확장) — 크롬이 꺼져 있으면 뒤에서 띄우고 확장이 받은 것을 반영')}
        return {}

    def hold_awake(self):
        """예약 깨우기가 부른다. 크롬을 띄우고 요약이 반영될 때까지(최대 25분) PC 를 붙든다 — 타이머로 깬 PC 는 윈도가 무인 절전(120초 · 실측)으로 곧 다시 재운다.
        다시 재우는 것은 윈도 몫이다. 대본이 강제로 재우면 사람이 막 연 PC·폰에서 깨운 PC·원격 작업 중인 PC 를 재운다(11-03 검토로 뺌)."""
        self.log(f'깨우기: 크롬 {ensure_chrome()}')
        before = set(os.listdir(self.RUNS)) if os.path.isdir(self.RUNS) else set()
        es = ctypes.windll.kernel32.SetThreadExecutionState
        es(0x80000000 | 0x00000001)                                 # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        try:
            t0 = time.time()
            while time.time() - t0 < HOLD:
                time.sleep(HOLD_TICK)
                if glob.glob(os.path.join(DOWNLOADS, f'{self.run_prefix}*.json')):     # 확장이 받기를 끝냄 — 15분 반영을 기다리지 않고 바로 반영(잠금이 차 있으면 반영 중이니 다음 바퀴에 본다)
                    tick_mod().tick(False)
                if set(os.listdir(self.RUNS) if os.path.isdir(self.RUNS) else ()) - before:
                    return self.log(f'깨우기: 반영 끝 · 붙들기 놓음({int(time.time() - t0)}초)')
            self.log('깨우기: 25분 안에 받은 것 없음 · 붙들기 놓음')
        finally:
            es(0x80000000)

    def wake(self):
        """시각 예약(«외부뇌-수집 <id>» → --at <id>)이 부른다 — 크롬이 꺼져 있으면 뒤에서 띄우고 반영까지 붙든다."""
        on, why = self.wake_state()
        if not on:                      # 꺼진 날 예약이 돌았다 = 예약이 값과 어긋남 — 예약을 값대로 맞춰 다음부터 안 돈다
            rc, out = self.wake_sync()
            return self.log(f'깨우기: 꺼 둠({why}) · 예약 맞춤 rc={rc} {out[-120:]}')
        if self.wake_level() != 'high':     # 고른 값은 높음인데 배터리 규칙으로 지금 낮음 = 크롬을 새로 띄우지도 PC 를 붙들지도 않음(예약은 그대로)
            return self.log('깨우기: 낮음 — 크롬을 띄우지 않음')
        return self.hold_awake()

    def legacy_wake(self):
        """옛 깨우기 예약(조리법 legacy_tasks)이 불렀다 — 시각을 수집 창에서 정했거나(settings at) 새 예약 «외부뇌-수집 <id>» 가 있으면
        새 예약이 맡으므로 아무것도 안 한다(같은 시각에 두 번 · 비운 시각에 크롬을 띄우는 일을 막음). 둘 다 아니면 예전처럼 wake()."""
        if 'at' in self.settings() or engine().schtasks('/Query', '/TN', TASK + self.id)[0] == 0:
            return self.log('깨우기(옛 예약): 새 시각 예약이 맡음 — 건너뜀')
        return self.wake()


# ── 판정 부품(출처 무관) ──
def login_events(runs):
    """요약마다 실린 확장 로그인 기록을 시간순 하나로(겹치는 줄은 한 번만)."""
    seen = {}
    for s in runs:
        for e in s.get('loginLog') or []:
            seen[(e.get('t'), e.get('ev'))] = e
    return [seen[k] for k in sorted(seen, key=lambda k: k[0] or 0)]


def hm(ms):
    return time.strftime('%m-%d %H:%M', time.localtime(ms / 1000))


def after_restart(e, events):
    """이 기록이 크롬을 다시 켠 직후인가 — 까닭 칸이 startup 이거나, 그 앞 RESTART_NEAR 초 안에 startup 기록이 있다."""
    if e.get('after') == 'startup':
        return True
    t = e.get('t') or 0
    return any(s.get('ev') == 'startup' and 0 <= t - (s.get('t') or 0) <= RESTART_NEAR * 1000 for s in events)


def power_events(days):
    """윈도 전원 기록 — 깬 까닭과 그때 전원선 여부(읽기만). 못 읽으면 None."""
    ps = ("$s=(Get-Date).AddDays(-%d);$o=@();foreach($f in @(@{ProviderName='Microsoft-Windows-Power-Troubleshooter';Id=1},@{ProviderName='Microsoft-Windows-Kernel-Power';Id=105})){"
          "$f.LogName='System';$f.StartTime=$s;Get-WinEvent -FilterHashtable $f -ErrorAction SilentlyContinue|ForEach-Object{$d=@{};foreach($x in ([xml]$_.ToXml()).Event.EventData.Data){$d[$x.Name]=$x.'#text'};"
          "$o+=@{t=$_.TimeCreated.ToString('yyyy-MM-ddTHH:mm:ss');id=$_.Id;d=$d}}};[Console]::OutputEncoding=[Text.Encoding]::UTF8;$o|ConvertTo-Json -Depth 4 -Compress") % days
    rc, out = sh(['powershell', '-NoProfile', '-Command', ps])
    try:
        ev = json.loads(out) if out.strip() else []
    except ValueError:
        return None
    return sorted(ev if isinstance(ev, list) else [ev], key=lambda e: e['t'])


def battery_wakes(days):
    """(배터리에서 타이머로 깬 횟수, 전원 연결에서 타이머로 깬 횟수, 그 밖 깸, 사람 입회 시험 깸). 전원선 여부 = 깨기 전 마지막 Kernel-Power 105.
    «외부뇌 깨우기 시험»(wake-test.ps1 · T1·T5 입회 시험)이 깨운 것은 따로 센다 — 수집 예약이 가방 속 PC 를 깨웠는지가 기준이라서(11-12 Wi-Fi 시험 2회가 미달로 셈 · 11-14)."""
    ev = power_events(days)
    if ev is None:
        return None
    ac, bat, plug, other, test = None, 0, 0, 0, 0
    for e in ev:
        d = e.get('d') or {}
        if e['id'] == 105:
            ac = str(d.get('AcOnline')).lower() == 'true'
        elif '외부뇌 깨우기 시험' in str(d.get('WakeSourceText') or ''):
            test += 1
        elif str(d.get('WakeTimerOwnerLength') or '0') != '0' or 'timer' in str(d.get('WakeSourceText') or '').lower():
            if ac is False:
                bat += 1
            else:
                plug += 1
        else:
            other += 1
    return bat, plug, other, test


def item_results(note):
    """시험표(조리법 report.items_note 노트 §3)의 결과 칸 — 사람이 입회해 잰 항목."""
    if not note:
        return {}
    try:
        p = os.path.join(VAULT, *roles.find_note(note).split('/'))
        rows = {}
        for ln in open(p, encoding='utf-8').read().splitlines():
            c = [x.strip() for x in ln.split('|')]
            if len(c) >= 6 and re.fullmatch(r'T\d+', c[1]):
                rows[c[1]] = c[5]
        return rows
    except (OSError, AttributeError):
        return {}


# ── 크롬(사람 크롬 · 프로필 하나) ──
def chrome_profile():
    return CHROME_PROFILE or os.path.join(os.environ.get('LOCALAPPDATA') or '', 'Google', 'Chrome', 'User Data')


def chrome_up(prof):
    """그 프로필의 크롬이 떠 있는가 — 크롬은 프로필 폴더의 lockfile 을 쓰기 막음으로 쥐고 있다(닫으면 지워짐 · 11-11 실측).
    옛 tasklist 는 프로필을 안 가려 시험 크롬·격리 시험이 떠 있으면 사람 크롬이 꺼져 있어도 «이미 실행 중»이 됐다."""
    lf = os.path.join(prof, 'lockfile')
    if not os.path.exists(lf):
        return False
    try:
        with open(lf, 'ab'):
            return False                                        # 열림 = 쥔 크롬 없음(남은 파일)
    except OSError:
        return True


def _exe_of(hwnd):
    """창 주인 프로그램 이름(앞창 기록용) — 못 읽으면 빈칸."""
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    pid = ctypes.c_ulong()
    u32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
    h = k32.OpenProcess(0x1000, False, pid.value)               # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ''
    try:
        buf, n = ctypes.create_unicode_buffer(520), ctypes.c_ulong(520)
        return os.path.basename(buf.value) if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else ''
    finally:
        k32.CloseHandle(h)


def _chrome_win(pid):
    """그 크롬 프로세스의 보이는 큰 창 — 'min'(최소화) · 'shown'(펼침) · ''(아직 없음)."""
    u32 = ctypes.windll.user32
    found = []
    proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def each(hwnd, _):
        p = ctypes.c_ulong()
        u32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(p))
        if p.value == pid and u32.IsWindowVisible(ctypes.c_void_p(hwnd)):
            cls = ctypes.create_unicode_buffer(64)
            u32.GetClassNameW(ctypes.c_void_p(hwnd), cls, 64)
            if cls.value == 'Chrome_WidgetWin_1' and u32.GetWindowTextLengthW(ctypes.c_void_p(hwnd)):
                found.append('min' if u32.IsIconic(ctypes.c_void_p(hwnd)) else 'shown')
        return True
    u32.EnumWindows(proc(each), 0)
    return 'shown' if 'shown' in found else found[0] if found else ''


def ensure_chrome():
    """확장은 크롬이 떠 있어야 돈다. 그 프로필 크롬이 꺼져 있으면 최소화·비활성 창으로 띄운다(SW_SHOWMINNOACTIVE) — --no-startup-window 는 크롬이 바로 끝난다(11-03 실측).
    창 없는 데스크톱(quietwin)에 띄우면 안 된다: 뒤에 사람이 연 크롬 창이 그 숨은 프로세스로 넘어가 화면에 안 나온다.
    띄운 뒤 20초 동안 앞 창이 크롬으로 바뀌는지와 창 꼴(최소화)을 재서 돌려준다(auto.log 에 남는다 — 예약 문맥에서 앞 창을 안 뺏는지의 기록)."""
    prof = chrome_profile()
    if chrome_up(prof):
        return '이미 실행 중'
    try:
        import winreg
        exe = winreg.QueryValue(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe')
    except OSError:
        return '경로 못 찾음'
    u32 = ctypes.windll.user32
    u32.GetForegroundWindow.restype = ctypes.c_void_p
    fg0 = u32.GetForegroundWindow() or 0
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 7                                          # SW_SHOWMINNOACTIVE
    extra = json.loads(os.environ.get('COLLECT_CHROME_ARGS') or '[]')
    pr = subprocess.Popen([exe] + ([f'--user-data-dir={prof}'] if CHROME_PROFILE else []) + extra, startupinfo=si, close_fds=True)
    took, win = '', ''
    for _ in range(40):
        time.sleep(0.5)
        fg = u32.GetForegroundWindow() or 0
        if fg != fg0 and not took:
            took = _exe_of(fg) or '?'
        win = _chrome_win(pr.pid) or win
    front = '그대로' if not took else f'바뀜({took})'
    return f'최소화 창으로 띄움 · 앞창 {front} · 창 {dict(min="최소화", shown="펼침").get(win, "못 봄")} · 프로필 {"잠김" if chrome_up(prof) else "안 잠김"}'


# ── 예약 엔진 제공자 약속(collect-schedule.py 가 이 모듈을 읽는다) ──
def at_sources():
    """제공자 약속 — 이 가족이 맡는 시각 출처 id."""
    return tuple(s.id for s in sources())


def schedule_tasks(wake):
    """제공자 약속 — {예약 이름: (시각들, 깨우기, 행위 인자, 설명)}."""
    out = {}
    for s in sources():
        out.update(s.schedule_task(wake))
    return out


def run_at(sid):
    """제공자 약속 — 시각 예약 «외부뇌-수집 <id>»가 부른다."""
    s = source(sid)
    return s.wake() if s else print(f'출처 없음: {sid}')


LEGACY_TASKS = tuple(n for rc in recipes() for n in rc.get('legacy_tasks') or ())     # 제공자 약속 — 맡아 둔 옛 예약(맞추기 결과 줄에만 적는다)


def main():
    ap = argparse.ArgumentParser(description='로그인 가족(browser)')
    ap.add_argument('--source', metavar='출처', help='출처 id(없으면 모든 출처 · --report·--wake-state 는 첫 출처)')
    ap.add_argument('--known', action='store_true')
    ap.add_argument('--wake', action='store_true')
    ap.add_argument('--wake-state', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--submissions', action='store_true')
    a = ap.parse_args()
    ss = [source(a.source)] if a.source else sources()
    if not ss or ss[0] is None:
        return print('로그인 가족 출처 없음(collect/browser/*.json)')
    if a.wake_state:
        on, why = ss[0].wake_state()
        return print('on' if on else 'off ' + why)
    if a.report:
        return ss[0].report()
    for s in ss:
        if a.wake:
            s.legacy_wake() if not TEST_STATE else s.wake()      # 시험 볼트에는 예약이 없다
        elif a.submissions:
            print(f'{s.id} 제출 기록:', '씀' if s.write_submissions() else '같음')
        elif a.known:
            k = s.write_known()
            print(f'{s.id} {os.path.basename(s.KNOWN)} — 단위 {len(k["courses"])} · 칸 ' + ' · '.join(f'{x} {len(v)}' for x, v in k.items() if isinstance(v, (list, dict)) and x != 'courses'))
        else:
            ap.print_help()
            break


if __name__ == '__main__':
    main()
