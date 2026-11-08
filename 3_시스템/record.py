#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""세션 기록의 기계 일 — session-record 스킬이 부른다(11-02).

실측: 기록 1회에 도구 평균 19회, 그 대부분이 recent·open-loops·MOC 를 즉석 코드로 고치고 재는 일이었다.
결정이 필요 없는 일이라 대본으로 옮겼다. 판단(수준·내용·삭제)은 스킬·모델 몫으로 남는다.

  py -3 3_시스템/record.py recent "<한 줄>"    recent.md 맨 위에 넣고 9줄로 자른다(150자 넘으면 거부)
  py -3 3_시스템/record.py skip <id> [...]     밀린 세션을 영구 제외
  py -3 3_시스템/record.py check               open-loops 크기 · MOC 미등재 · 프론트매터 · 제어 문자 · 상한
"""
import datetime as dt
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import drift  # noqa: E402
import roles  # noqa: E402

VAULT = os.path.dirname(HERE)
RECENT = os.path.join(VAULT, "2_지식", "recent.md")
SKIP = os.path.join(HERE, "_index", ".pending-skip.txt")
KEEP = 9
LIMIT = 150
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def recent(line):
    line = line.strip()
    if not line.startswith("- "):
        line = "- " + line
    if len(line) > LIMIT:
        print(f"거부: {len(line)}자({LIMIT}자까지). 줄여서 다시.")
        return 1
    with open(RECENT, encoding="utf-8", newline="") as h:
        lines = h.read().replace("\r\n", "\n").split("\n")
    at = next((i for i, x in enumerate(lines) if x.startswith("- ")), len(lines))
    old = [x for x in lines[at:] if x.startswith("- ")]
    kept = [line] + old[: KEEP - 1]
    with open(RECENT, "w", encoding="utf-8", newline="") as h:
        h.write("\n".join(lines[:at] + kept) + "\n")
    print(f"recent {len(kept)}줄 · 밀려 나간 줄 {max(0, len(old) + 1 - KEEP)}")
    return 0


def skip(ids):
    os.makedirs(os.path.dirname(SKIP), exist_ok=True)
    with open(SKIP, "a", encoding="utf-8", newline="") as h:
        for i in ids:
            h.write(i[:8] + "\n")
    print("제외:", " ".join(i[:8] for i in ids))
    return 0


def notes():
    """stop-check 와 같은 대상 — 역할 묶음 moc_notes · _접두 하위폴더 제외"""
    exempt = roles.path("modules")
    for d in roles.group("moc_notes"):
        base = os.path.join(VAULT, d)
        for dp, _, fs in os.walk(base):
            r = os.path.relpath(dp, VAULT).replace(os.sep, "/")
            if "/_" in "/" + r.replace("2_지식", "", 1):
                continue
            for f in fs:
                if f.endswith(".md"):
                    yield os.path.join(dp, f), d != exempt


def module_steps():
    """켜진 모듈이 선언한 기록 단계(module.json contributes.record) — 낸 줄이 곧 고칠 것이다. 모듈 이름을 여기 박지 않는다"""
    out = []
    for m in roles.modules(on_only=True):
        try:
            argv = ((m["json"] or {}).get("contributes") or {}).get("record")
            if argv:
                r = subprocess.run([sys.executable if t == "{py}" else t for t in argv], cwd=VAULT, capture_output=True, timeout=20,
                                   env=dict(os.environ, PYTHONIOENCODING="utf-8"))
                out += [x for x in r.stdout.decode("utf-8", "replace").splitlines() if x.strip()]
        except (OSError, ValueError, subprocess.TimeoutExpired):
            continue
    return out


def check():
    bad = []
    with open(os.path.join(VAULT, "2_지식", "MOC.md"), encoding="utf-8") as h:
        moc = h.read()
    today = dt.date.today().isoformat()
    for p, need_moc in notes():
        name = os.path.basename(p)
        try:
            with open(p, encoding="utf-8-sig", errors="replace") as h:
                t = h.read()
        except OSError:
            continue
        if not t.startswith("---"):
            bad.append(f"프론트매터 없음: {drift.rel(p)}")
        if need_moc and not re.search(r"\[\[" + re.escape(name[:-3]) + r"[\]|#]", moc):
            bad.append(f"MOC 미등재: {drift.rel(p)}")
    sess = os.path.join(VAULT, roles.path("sessions"))
    for f in os.listdir(sess) if os.path.isdir(sess) else ():
        if f.startswith(today) and f.endswith(".md"):
            with open(os.path.join(sess, f), encoding="utf-8", errors="replace") as h:
                n = len(CTRL.findall(h.read()))
            if n:
                bad.append(f"제어 문자 {n}개(역슬래시 붕괴): {f}")
    for p in (os.path.join(VAULT, "2_지식", "open-loops.md"), RECENT):
        bad += [f"{w} {t}" for _, w, t in drift.limits_of(p)]
    bad += module_steps()
    size = os.path.getsize(os.path.join(VAULT, "2_지식", "open-loops.md"))
    if not bad:
        print(f"기록 점검 통과 · open-loops {size}바이트")
        return 0
    print(f"고칠 것 {len(bad)} · open-loops {size}바이트")
    for b in bad:
        print(" ", b)
    return 0


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    if argv[:1] == ["recent"] and len(argv) == 2:
        return recent(argv[1])
    if argv[:1] == ["skip"] and len(argv) > 1:
        return skip(argv[1:])
    if argv[:1] == ["check"]:
        return check()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
