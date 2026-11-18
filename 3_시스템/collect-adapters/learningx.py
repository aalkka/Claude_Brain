"""어댑터 learningx — Canvas 에 LTI 로 붙는 LearningX 게시판·외부 도구의 요약 칸 판정·검증 개수·이미 받은 것(11-16 수집 범용화 S4).

로그인 가족(collect-browser.py)이 출처 조리법의 `adapters` 차례대로 부른다. 출처 이름·주소·학교 값은 여기 없다 — 조리법 몫.
요약의 `board` 칸 = {state, results{<단위>: {error, boards[{name, seen, skipped, err}]}}} · 원시 = <raw_prefix>board-<단위>-<run>*.json.
"""
import calendar
import re
import time

PART = 'board'          # 요약 칸 이름 · 검증 키 머리(board:<단위>)
RAW = 'board'           # 원시 파일 이름 칸 — <raw_prefix>board-…
SIGNALS = ()


def judge(src, run, s):
    """state 가 done 이어도 속은 실패일 수 있다(10-26 첫 실수집: 게시판 8과목 모두 no_board_tool 인데 done)."""
    results = ((s.get(PART) or {}).get('results') or {})
    berr = {k: v.get('error') for k, v in results.items() if isinstance(v, dict) and v.get('error')}
    if berr:
        src.queue(run, f'게시판 실패 {len(berr)}과목 · {sorted(set(map(str, berr.values())))}')
    perr = [f'{k} {b.get("name")}: {b.get("err")}' for k, v in results.items() if isinstance(v, dict) for b in v.get('boards') or [] if b.get('err')]
    if perr:                                                    # 과목은 done 인데 글을 못 연 경우(조회수 막기 0.2.0 뒤 첫 관찰 자리)
        src.queue(run, f'게시판 글 오류 {len(perr)}곳 · {perr[:4]}'[:300])


def counts(s):
    """검증기 개수 — 단위마다 게시판 본 글(건너뛴 게시판 빼고)."""
    out = {}
    for cid, r in ((s.get(PART) or {}).get('results') or {}).items():
        if isinstance(r, dict) and 'boards' in r:
            out[f'{PART}:{cid}'] = sum(b.get('seen') or 0 for b in r['boards'] if not b.get('skipped'))
    return out


def post_at(rec):
    """게시판 글을 받은 시각(ms). 옛 기록은 수집 번호(YYYYMMDD-HHMM · 그것도 없으면 그날 0시)로 — 이르게 잡으면 한 번 더 열릴 뿐이다."""
    try:
        return calendar.timegm(time.strptime(rec['at'][:19], '%Y-%m-%dT%H:%M:%S')) * 1000
    except (KeyError, TypeError, ValueError):
        pass
    m = re.match(r'(\d{8})(?:-(\d{4}))?', rec.get('run') or '')
    return int(time.mktime(time.strptime(m.group(1) + (m.group(2) or '0000'), '%Y%m%d%H%M'))) * 1000 if m else None


def xn_needed(man):
    """LearningX 모듈 목록을 잴 과목 — 외부 도구 항목이 있는데 아직 못 쟀거나(실패는 세 번까지) 잰 뒤 새 항목이 생긴 과목. 한 번 잰 뒤에는 필요할 때만 돈다."""
    out = []
    for c, ids in (man.get('tool_items') or {}).items():
        p = (man.get('xn_probe') or {}).get(c) or {}
        fresh = not set(ids) <= set(p.get('items') or [])
        if c.isdigit() and (fresh or (not p.get('ok') and p.get('tries', 0) < 3) or open_lectures(p)):
            out.append(int(c))
    return out


def open_lectures(p):
    """추적하는 대체 강의 가운데 기한이 안 지났는데 아직 완료가 아닌 것이 있는가 — 있으면 완료 값을 받을 때까지 전 과목 받기마다 다시 잰다(11-06 · 없으면 요청 0)."""
    now_utc = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    return any(not x.get('done') and (x.get('due') or '') > now_utc for x in p.get('lectures') or [])


def known(src, man):
    """확장이 읽는 «이미 받은 것» 몫 — 게시판 글 키 · 글 번호 → 받은 시각(받은 뒤 수정된 글만 다시 연다) · 외부 도구 목록을 잴 과목."""
    board_at = {}
    for c, v in man.get('board', {}).items():
        for rec in v.values():
            m = re.search(r'/posts/(\d+)', (rec or {}).get('path') or '')
            ms = post_at(rec) if m else None
            if ms:
                board_at.setdefault(c, {})[m.group(1)] = max(ms, board_at.get(c, {}).get(m.group(1), 0))
    return {
        'board': {c: sorted(v) for c, v in man.get('board', {}).items() if c.isdigit()},
        'boardAt': board_at,
        'xnProbe': xn_needed(man),
    }
