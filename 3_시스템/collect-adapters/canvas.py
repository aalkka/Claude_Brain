"""어댑터 canvas — Canvas 학습 플랫폼(학교 여러 곳이 같은 꼴)의 요약 칸 판정·검증 개수·이미 받은 것·제출 기록(11-16 수집 범용화 S4).

로그인 가족(collect-browser.py)이 출처 조리법의 `adapters` 차례대로 부른다. 출처 이름·주소·학교 값은 여기 없다 — 조리법(collect/browser/<id>.json) 몫.
요약(확장 → 다운로드 <run_prefix><run>.json)의 `canvas` 칸 = {state, result{error, summary[{id, 공지, 과제, 막힘}]}} · 원시 = <raw_prefix>canvas-<run>*.json.
"""
import json

PART = 'canvas'                                         # 요약 칸 이름 · 검증 키 머리(canvas:<단위>)
RAW = 'canvas'                                          # 원시 파일 이름 칸 — <raw_prefix>canvas-…
SIGNALS = ('ann', 'plan')                               # 가벼운 확인 신호(공지·할 일) — 200 이 아니면 전 과목 받기만으로 돈다
SUBMITTED = ('submitted', 'graded', 'pending_review')   # work.py 와 같은 «낸 것»


def judge(src, run, s):
    """state 가 done 이어도 속은 실패일 수 있다 — 결과 칸의 오류 · 접근이 막힌 단위(수강이 끝난 과목 등)."""
    res = (s.get(PART) or {}).get('result') or {}
    if res.get('error'):
        src.queue(run, f'canvas 오류 `{res["error"]}`')
    for c in res.get('summary') or []:
        if c.get('막힘'):
            src.queue('courses', f'과목 {c.get("id")} 접근 불가 {c["막힘"][:3]} — 수강 끝났으면 {src.units_name} 에서 뺀다'[:300], once=True)


def counts(s):
    """검증기 개수 — 단위마다 공지+과제(지난 수집과 견줌)."""
    out = {}
    for c in ((s.get(PART) or {}).get('result') or {}).get('summary') or []:
        out[f'{PART}:{c.get("id")}'] = (c.get('공지') or 0) + (c.get('과제') or 0)
    return out


def known(src, man):
    """확장이 읽는 «이미 받은 것» 몫 — 받은 Canvas 파일 번호(manifest files 의 canvas:<번호>)."""
    return {'knownFiles': sorted(k.split(':', 1)[1] for k in man.get('files', {}) if k.startswith(PART + ':'))}


def submissions(src):
    """원시(<원본>/<raw_dir>/<raw_prefix>canvas-*.json)의 «내 제출» → {주제: [{과제, 파일[], 때}]} — 과제마다 가장 새 수집(11-16 S3 · work.py 에서 옮김)."""
    from urllib.parse import unquote_plus
    try:
        courses = src.units()
    except (OSError, ValueError):
        return {}
    by = {}
    for f in src.raw_files(RAW):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for c in d.get("courses") or []:
            name = courses.get(str(c.get("id")))
            if not name:
                continue
            topic = src.topic(name)
            for a in c.get("assignments") or []:
                s = a.get("submission") or {}
                if s.get("workflow_state") not in SUBMITTED:
                    continue
                files = [x.get("display_name") or unquote_plus(x.get("filename") or "") for x in s.get("attachments") or []]
                by.setdefault(topic, {})[a.get("id")] = {"과제": a.get("name") or "", "파일": [x for x in files if x], "때": s.get("submitted_at") or ""}
    return {t: list(v.values()) for t, v in by.items()}
