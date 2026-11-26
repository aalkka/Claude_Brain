"""수집 15분 반영 — 행위 collect.tick(15분 예약 · 수집 창 «지금 받기»)이 부른다(본체 · 11-16 수집 범용화 S4 · S6 에 행위 이름 바꿈).

한 번에: 잠금 → 로그인 가족 출처마다 요약 들이기(collect-browser.py) → known.json → 웹 수집(받을 차례만 · web-collect.py)
  → 제출 기록(새 요약이 들어온 출처만) → 판정 한 줄(notice-filter judge) → 침묵 감시 → 보고(report.txt · 1시간에 한 번)
  → 분류 배우기 틱(sort_learn.py tick · py -3 · 그림자만 · 실패해도 수집 그대로 · 11-18)
  → 가격 조회 틱(collect_price.py --tick · 조리법 «주기» 차례만 · «됨»이면 그 label 의 가격줄 체계를 sort.py run · 11-20 잇기)
  → 분류 동작 틱(태그 tag.py · 알림 = mobility alert.py(켜졌을 때만) · 넘김 장부의 새 줄 · 이 파이썬 안 · 실패해도 수집 그대로 · 11-18 S8·S9).
마지막 줄 = «받은 것: <출처 이름> 요약 N · 웹 새 글 M» — brain.py 가 «받은 것 없음»이면 장부에 짧게만 적는다(actions.json 의 empty).
잠금·로그 자리 = 예약 엔진(collect-schedule.py)과 같음(수집 창·로드맵이 그 로그를 읽는다).

  py -3.11 3_시스템/collect-tick.py [--dry]        # 15분 반영 한 번(--dry = 무엇을 할지만)
  py -3.11 3_시스템/collect-tick.py --at <출처>    # 시각 예약 «외부뇌-수집 <출처>»(= collect-schedule.py --at)
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys

SYS = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(SYS)
sys.path.insert(0, SYS)
import collectlib as cl  # noqa: E402

PY = sys.executable
_mods = {}


def _mod(name, file):
    if name not in _mods:
        sp = importlib.util.spec_from_file_location(name, os.path.join(SYS, file))
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        _mods[name] = m
    return _mods[name]


def engine():
    """예약 엔진 — 잠금·로그 자리와 시각 받기."""
    return _mod('collect_schedule', 'collect-schedule.py')


def family():
    """로그인 가족(collect-browser.py) — 없으면 None(웹 수집만 돈다)."""
    return _mod('collect_browser', 'collect-browser.py') if os.path.isfile(os.path.join(SYS, 'collect-browser.py')) else None


def sources():
    f = family()
    return f.sources() if f else []


def sh(args):
    p = subprocess.run(args, cwd=VAULT, capture_output=True, text=True, encoding='utf-8', errors='replace',
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))  # 예약 작업에서 콘솔 창이 번쩍이지 않게
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def log(msg):
    cl.log_line(engine().LOG, msg)
    print(msg)


def queue(src, what):
    """사건 줄(매번 씀) — 시험이면 시험 상태 폴더의 대기열."""
    t = engine().TEST_STATE
    if cl.queue_add(src, what, 'Claude', once=None, path=os.path.join(t, 'repair-queue.md') if t else cl.QUEUE):
        log(f'대기열 {src}: {what}')


def learn_tick():
    """분류 배우기 틱(sort_learn.py tick · S5·S7 그림자 + S6 받은함 그림자 · 11-18 보스) — 판정·파일 이동 없음 · LLM 0.
    sklearn 이 py -3 에만 있어 py -3 으로 부른다(이 대본은 py -3.11). 따로 감쌈: 실패해도 수집은 그대로(로그 한 줄).
    할 것이 없으면(엔진 상태·체계 파일 그대로 · 새 사람 이동 없음) 출력도 로그도 없다."""
    try:
        import shutil
        py3 = ['py', '-3'] if shutil.which('py') else [PY]
        rc, out = sh([*py3, os.path.join(SYS, 'sort_learn.py'), 'tick'])
        out = out.strip()
        if rc or out:
            log(f'sort_learn tick rc={rc} ' + out[-300:])
    except Exception as e:
        log(f'sort_learn tick 예외 {e!r}'[:300])


def price_systems(labels):
    """켬 true 인 가격줄 체계 중 대상.출처.label 이 labels 에 드는 것(label 칸이 없으면 모든 가격줄)."""
    out, d = [], os.path.join(SYS, 'sort')
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        if not f.endswith('.json'):
            continue
        try:
            s = json.load(open(os.path.join(d, f), encoding='utf-8'))
        except (OSError, ValueError):
            continue
        tgt = (s.get('대상') or {}) if isinstance(s, dict) else {}
        lab = (tgt.get('출처') or {}).get('label')
        if s.get('켬') is True and tgt.get('종류') == '가격줄' and (lab is None or lab in labels):
            out.append(s.get('id') or f[:-5])
    return out


def price_tick():
    """가격 조회 틱(11-20 잇기) — collect_price.py --tick(켬 조리법 중 «주기.시간»이 찬 것만 · 망 GET · LLM 0) → «됨»인 출처의 label 을 보는
    가격줄 체계를 sort.py run --system …(알림 동작은 분류가 그 자리에서 알림 도구로 · sort.alert_now). 따로 감쌈 · 실패해도 수집 그대로 ·
    차례가 아니면 출력도 로그도 없다. 끄기 = 조리법 «켬» false."""
    p = os.path.join(SYS, 'collect_price.py')
    if not os.path.isfile(p):
        return
    try:
        rc, out = sh([PY, p, '--tick'])
        out = out.strip()
        if not rc and not out:
            return
        try:
            ran = json.loads(out.splitlines()[-1])
        except (ValueError, IndexError):
            ran = {}
        log(f'price tick rc={rc} ' + (' · '.join(f'{k} {v.get("상태")} 조회 {v.get("조회", 0)} 줄 {v.get("줄", 0)}' for k, v in ran.items()) or out[-300:]))
        systems = price_systems({v.get('label') for v in ran.values() if v.get('상태') == '됨'})
        if systems:
            rc2, out2 = sh([PY, os.path.join(SYS, 'sort.py'), 'run'] + [a for s in systems for a in ('--system', s)])
            log(f'sort run {"·".join(systems)} rc={rc2} ' + out2.strip()[-300:])
    except Exception as e:
        log(f'price tick 예외 {e!r}'[:300])


ALERT_TOOL = os.path.join(os.path.dirname(SYS), '.claude', 'skills', 'mobility', 'scripts', 'alert.py')     # 알림 도구 = mobility 모듈(11-18)


def mobility_on():
    try:
        if SYS not in sys.path:
            sys.path.insert(0, SYS)
        import roles
        return bool(roles.module_on('mobility'))
    except Exception:  # noqa: BLE001 — 모르면 안 부름
        return False


def act_tick():
    """분류 동작 틱(범용 도구 셋 S8·S9 · 11-18) — 넘김 장부의 새 줄을 태그 도구(tag.py sync · «노트에 쓰기» 켠 체계만 파일을 씀)와
    알림 도구(alert.py run · 알림 동작이 있는 체계만 폰·수집 창)가 맞춘다. LLM 0 · 둘 다 순수 파이썬이라 이 파이썬(py -3.11)으로 · 숨은 창(sh).
    노트 쓰기 켠 체계 0 · 알림 동작 체계 = 지금 없음(옛 항공권 관찰 체계는 11-23 폐기 · 분류 run 이 이미 알림 도구를 불렀으면 여기는 그물).
    따로 감쌈 · 실패해도 수집 그대로 · 한 일이 없으면 출력도 로그도 없다."""
    for f, p in (('tag.py', os.path.join(SYS, 'tag.py')), ('alert.py', ALERT_TOOL)):
        if not os.path.isfile(p):                              # 이 도구가 없는 볼트(시험 사본 · 옛 배포판 · mobility 없음)
            continue
        if f == 'alert.py' and not mobility_on():              # 알림 도구 = mobility 몫(11-18) — 꺼졌으면 조용히 건너뜀(수집 창은 넘김을 직접 읽음)
            continue
        try:
            rc, out = sh([PY, p, 'tick'])
            out = out.strip()
            if rc or out:
                log(f'{f[:-3]} tick rc={rc} ' + out[-300:])
        except Exception as e:
            log(f'{f[:-3]} tick 예외 {e!r}'[:300])


def got_line(srcs, got, web, tail=''):
    return '받은 것: ' + ''.join(f'{s.name} 요약 {got.get(s.id, 0)} · ' for s in srcs) + f'웹 새 글 {web}' + tail


def tick(dry=False):
    """15분 반영 한 번. 돌려줌 = 받은 것 한 줄."""
    srcs = sources()
    if cl.switches(SYS).get('all_off') is True:
        for s in srcs:
            s.write_known()             # 확장에 멈춤을 알린다
        return got_line(srcs, {}, 0, ' (전체 꺼짐)')
    held = cl.try_lock(engine().lock_path())
    if not held:
        return got_line(srcs, {}, 0, ' (다른 처리 중)')
    try:
        got = {s.id: s.intake(dry) for s in srcs}
        if not dry and any(got.values()):                          # 엔진 기록 한 줄 — 수집 창이 엔진 자리(_index/collect)를 지켜본다
            log('반영 ' + ' · '.join(f'{s.id} 요약 {got[s.id]}' for s in srcs if got[s.id]))
        web_new = 0
        if not dry:
            for s in srcs:
                s.write_known()
            # 범용 수집(공개 웹 · 수집 계약 출처) — 받을 차례가 아니면 web-collect 가 스스로 건너뛴다(시각 · recheck_hours)
            rc, out = sh([PY, os.path.join(SYS, 'web-collect.py')])
            kept = ' · '.join(ln for ln in out.splitlines() if '받음' in ln or '대기열' in ln)[:400]
            if rc or kept:                                          # 15분마다 돈다 — 받은 것이 없으면 로그도 없다
                log(f'web-collect rc={rc} ' + kept)
            web_new = sum(int(m) for m in re.findall(r'받음 (\d+)/', out))
            if rc:
                queue('web', f'web-collect.py 실패 rc={rc}')
            for s in srcs:                                          # 제출 기록(work.py 근거 «제출») — 새 원시가 들어온 때만
                if got[s.id]:
                    s.submit()
            if any(got.values()):                                   # 세션 시작 한 줄(.status.txt)이 대기열을 따라가게 — LLM 0
                sh([PY, os.path.join(SYS, 'notice-filter.py'), 'judge'])
            for s in srcs:
                s.watch(got[s.id])
            for s in srcs:
                s.write_report()
            learn_tick()
            price_tick()
            act_tick()
        return got_line(srcs, got, web_new, ' (마른 실행)' if dry else '')
    finally:
        try:
            import msvcrt
            held.seek(0)
            msvcrt.locking(held.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        held.close()


def main():
    ap = argparse.ArgumentParser(description='수집 15분 반영')
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--at', metavar='출처', help='시각 예약이 부름 — 로그인 출처 = 크롬 띄우고 반영까지 붙들기 · 웹 = 받을 차례면 받기')
    a = ap.parse_args()
    if a.at:
        return engine().run_at(a.at)
    print(tick(a.dry))


if __name__ == '__main__':
    main()
