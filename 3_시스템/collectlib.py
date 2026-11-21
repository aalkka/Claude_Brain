"""수집 엔진 공통 모음 — 출처·가족과 무관한 작은 부품(11-16 수집 범용화 S1).

웹 엔진(web-collect)·로그인 가족(collect-browser)·필터 학습(filter-learn)·수집 창(collect_desk)이 저마다 같은 함수를 들고 있던 것을 한 곳으로 모았다.
여기 있는 것: 시각 · 로그 한 줄(잠금) · 대기열 한 줄 쓰기·닫기 · «시각» 칸 고르기 · 전체 스위치 · 겹침 막는 잠금 · 로그인 조리법 읽기(S6).
여기 없는 것: 출처 이름·주소·학교 값 — 그것은 조리법과 개인 층 데이터 몫이다.
"""
import glob
import json
import os
import re
import time

SYS = os.path.dirname(os.path.abspath(__file__))
QUEUE = os.path.join(SYS, '_index', '수집-대기열.md')       # 수집 엔진 공용 대기열(10-27 합침)
QUEUE_HEAD = '# 수집 대기열\n> 수집 엔진(collect-tick·web-collect)이 쌓는다. 고치면 줄 앞을 `- [x]` 로.\n\n'
AT_MAX = 4                                                  # 하루 시각 칸 수(수집 창 «시각»)
SWITCH_KEYS = ('all_off', 'auto_judge', 'wake_pc')
BROWSER = ('collect', 'browser')                            # 로그인 가족 조리법 자리(개인 층 · collect-browser.py 와 같음)


def now():
    return time.strftime('%Y-%m-%d %H:%M:%S')


def log_line(path, msg):
    """로그 한 줄 덧붙이기 — 여러 예약·단추가 같은 때 쓰면 윈도의 덧붙이기가 서로 덮어 줄이 글자 중간에서 찢긴다(11-12 15:07:46 실측).
    쓰는 동안만 <로그>.lock 을 잡는다(10초 못 잡으면 그래도 쓴다 — 로그 때문에 수집을 멈추지 않는다)."""
    import msvcrt
    os.makedirs(os.path.dirname(path), exist_ok=True)
    line = f'{now()} {msg}\n'.encode('utf-8')
    with open(path + '.lock', 'a+b') as lk:
        lk.seek(0)
        try:
            msvcrt.locking(lk.fileno(), msvcrt.LK_LOCK, 1)      # 1초씩 10번 다시 해 본다
            held = True
        except OSError:
            held = False
        try:
            with open(path, 'ab') as f:
                f.write(line)
        finally:
            if held:
                lk.seek(0)
                msvcrt.locking(lk.fileno(), msvcrt.LK_UNLCK, 1)


def queue_add(src, what, who='Claude', once='line', path=None, head=QUEUE_HEAD):
    """대기열 한 줄 = 한 건 — `- [ ] <때> \\`<출처>\\` (<고칠 사람>) <일>`. 썼으면 True.
    once = 'line'(같은 출처·사람·일의 열린 줄이 있으면 안 씀) · 'what'(출처가 달라도 같은 일이 열려 있으면 안 씀 — 출처 자리에 수집 번호가 오는 상태 줄) · None(사건 줄 — 매번 씀)."""
    path = path or QUEUE
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not new and once:
        tail = what if once == 'what' else f'`{src}` ({who}) {what}'
        with open(path, encoding='utf-8') as f:
            if any(ln.startswith('- [ ] ') and ln.endswith(tail) for ln in f.read().splitlines()):
                return False
    with open(path, 'a', encoding='utf-8', newline='\n') as f:
        if new and head:
            f.write(head)
        f.write(f'- [ ] {now()} `{src}` ({who}) {what}\n')
    return True


def queue_close(text, path=None):
    """그 일이 풀렸다 — 그 글이 든 열린 줄을 닫는다(사람이 지우지 않아도 대기열이 실제 상태를 말하게). 닫았으면 True."""
    path = path or QUEUE
    if not os.path.exists(path):
        return False
    with open(path, encoding='utf-8') as f:
        old = f.read()
    new = re.sub(r'^- \[ \](?= .*' + re.escape(text) + r')', '- [x]', old, flags=re.M)
    if new == old:
        return False
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new)
    return True


def at_times(v):
    """«시각» 칸(조리법·출처 설정) — ['HH:MM', …] 를 고르고 정렬 · 틀린 꼴은 ValueError."""
    if v in (None, '', []):
        return []
    if not isinstance(v, list) or len(v) > AT_MAX:
        raise ValueError(f'at = HH:MM 목록 {AT_MAX}개까지')
    out = []
    for t in v:
        if not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d', str(t)):
            raise ValueError(f'at 꼴 HH:MM: {t!r}')
        if t not in out:
            out.append(t)
    return sorted(out)


def switches(sys_dir=None, keys=SWITCH_KEYS):
    """수집 전체 스위치(all_off·auto_judge·wake_pc) — 3_시스템/collect.local.json(이 PC 의 결정 · git 밖).
    없거나 못 읽으면 빈 dict = 수집 켜짐·자동 판정 끔. (옛 자리 읽기는 S6 에 걷음 — 그 칸이 남은 볼트는 적용 대본이 옮긴다.)"""
    try:
        d = json.load(open(os.path.join(sys_dir or SYS, 'collect.local.json'), encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    return {k: d[k] for k in keys if k in d} if isinstance(d, dict) else {}


WAKE_PC = 'collect.wake_pc'     # 기능 «PC 깨우기»(options.registry.json · 모든 시각 수집 · 11-20 나눔)
CHROME = 'collect.chrome'       # 기능 «크롬 띄우기»(로그인 출처 · 옛 collect.wake)


def wake_pc(sys_dir=None):
    """PC 깨우기 켬? — 기능 collect.wake_pc 의 고른 값(배터리 규칙 전 · 배터리로 잠깐 낮아진 값으로 예약을 바꾸지 않게).
    고른 값이 없으면 옛 자리 collect.local.json wake_pc(false = 끔 · 11-12 수집 창 «잠든 PC») · 둘 다 없으면 켬. 어떤 오류도 옛 자리 규칙."""
    d = sys_dir or SYS
    try:
        import sys
        if d not in sys.path:
            sys.path.insert(0, d)
        import options
        v = os.path.dirname(d)
        local, st = options._load(options.local_path(v))
        lv = local.get('levels') if st == 'ok' and isinstance(local, dict) else None
        if isinstance(lv, dict) and WAKE_PC in lv:
            return options.chosen(local, st, options.declarations(v, only=WAKE_PC)).get(WAKE_PC, 'high') == 'high'
    except Exception:
        pass
    return switches(d).get('wake_pc') is not False


def browser_recipes(sys_dir=None):
    """로그인 가족 조리법 — collect/browser/<id>.json(family browser · id = 파일 이름). 못 읽는 것은 건너뜀.
    수집 창·따라가기·홈·공지 필터·구조 이전이 출처 이름과 자리를 코드에 두지 않고 이것을 읽는다(S6)."""
    out = []
    for p in sorted(glob.glob(os.path.join(sys_dir or SYS, *BROWSER, '*.json'))):
        try:
            rc = json.load(open(p, encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(rc, dict) and rc.get('family') == 'browser' and rc.get('id') == os.path.splitext(os.path.basename(p))[0]:
            out.append(rc)
    return out


def rpath(rel, sys_dir=None):
    """조리법의 자리 칸(3_시스템 기준 «/» 경로) → 절대 경로 · 빈 값이면 ''."""
    return os.path.join(sys_dir or SYS, *rel.split('/')) if isinstance(rel, str) and rel else ''


def browser_state(rc, sys_dir=None):
    """로그인 출처의 상태 폴더(로그·요약 보관·마감 대기) — 조리법 state · 없으면 _index/<id>(collect-browser.Source 와 같은 규칙)."""
    return rpath(rc.get('state') or '_index/' + rc['id'], sys_dir)


def try_lock(path):
    """겹침 막는 잠금 — 쥐면 열린 파일(닫으면 놓음) · 남이 쥐고 있으면 None. 15분 예약·행위 단추·깨우기·수집 창이 같은 자리를 쓴다."""
    import msvcrt
    os.makedirs(os.path.dirname(path), exist_ok=True)
    f = open(path, 'a+')
    try:
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        return None
    return f
