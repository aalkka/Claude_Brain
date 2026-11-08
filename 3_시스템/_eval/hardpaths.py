# -*- coding: utf-8 -*-
"""코드·설정·스킬에 글자로 박힌 «내용 경로»를 잰다 (볼트 개혁 R6 · 2026-10-30).

R9(구조 이전)에서 자리가 바뀌는 경로가 코드에 박혀 있으면 이전 때마다 코드를 고쳐야 한다.
R6 완료 기준 = 이 목록의 «움직이는 경로» 0(역할 이름으로 묻게 바꿈 — `3_시스템/roles.py`).

  py -3 3_시스템/_eval/hardpaths.py [--extra C:/brain-base/src ...] [--all] [--json]

움직이는 경로(설계안 §1.3): 0_작업/<과목> · 2_지식/notes·sessions·decisions·_canvas · 1_수집/학교/고려대 공지.
그대로인 경로: 1_수집/학교/<과목>(공지 빼고) · 1_수집/받은함·_색인·_lms · 2_지식 뿌리 파일·일정·modules · 3_시스템.
과목 이름 글자(정식·별칭)도 따로 센다 — 주제 등록부(2_지식/주제.md)로 옮길 후보.
"""
import argparse
import json
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

VAULT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXT = (".py", ".ps1", ".psm1", ".mjs", ".js", ".ts", ".json", ".sh", ".md", ".tmpl")
SKIP_DIRS = {"__pycache__", "node_modules", "_index", "ledger", "vault", "_claude-memory", "_ref", ".git", "test", "dist"}
SKIP_FILES = {"known.json", "hardpaths.py"}
# 예외(까닭) — R6.2 완료 기준 «예외 밖 0» 의 예외. 늘릴 때는 까닭을 적는다.
EXEMPT = {
    "3_시스템/roles.json": "역할 원본 — 자리를 적는 유일한 곳",
    "3_시스템/roles.py": "역할 대본의 사용 예시",
    ".claude/settings.local.json": "게이트 자신(허용 규칙 글자) — 사용자 몫 · 토큰으로도 못 고침",
    "3_시스템/labreport-exp5-build.py": "일회성 보고서 생성기(지난 과제 · 다시 돌리지 않음)",
    "3_시스템/dsl-report-build.py": "일회성 보고서 생성기(주차마다 OUT 을 손으로 바꿈)",
    ".claude/skills/module-forge/scripts/test_check.py": "시험 자료 — 가짜 볼트 안 경로",
    ".claude/skills/canvas/scripts/canvas-check.py": "시험 자료 — 예시 경로",
    "3_시스템/_eval/r8_cleanup_check.py": "시험 자료 — 격리 볼트 안 가짜 경로",
    "3_시스템/restructure.py": "구조 이전 대본 — 옛 자리·새 자리를 적는 것이 본업(R9)",
    "3_시스템/_eval/r6_intake_check.py": "시험 자료 — 격리 볼트 안 가짜 경로",
    "3_시스템/_eval/update_sim.py": "시험 자료 — 옛 판 사용자 볼트의 옛 자리",
    "3_시스템/drift.py": "옛 이름 사전 — 옛 자리·새 자리를 적는 것이 본업(11-02)",
    "3_시스템/lms-intake.py": "사용 예시(--dest 도움말) — 실제 자리는 부르는 쪽이 역할로 준다",
    "3_시스템/conventions.md": "코어 글 — 코어 토큰으로 고칠 곳(10-31 R9 뒤 · 사용자 승인)",
}
ROOTS = ["3_시스템", ".claude"]

LAYER = r"(?:0_작업|1_수집|2_지식)"
LIT = re.compile(LAYER + r"(?:[/\\]{1,2}[^\s\"'`)\]|*,;<>{}]+)?")
# os.path.join(V, "2_지식", "sessions") · Join-Path $v '2_지식' 'notes' 같은 조각 잇기
JOIN = re.compile(r"[\"'](" + LAYER + r")[\"']\s*(?:,|\+\s*[\"'][/\\][\"']\s*\+|\s)\s*[\"']([^\"'/\\]+)[\"']")
MOVING = ("0_작업/", "2_지식/notes", "2_지식/sessions", "2_지식/decisions", "2_지식/_canvas", "1_수집/학교",  # R9 전 자리(지금은 없음 — 박혀 있으면 죽은 경로)
          "2_지식/배움", "2_지식/일", "2_지식/생활", "2_지식/분야", "2_지식/기록", "1_수집/배움")  # R9 뒤 자리(역할로만 묻는다)


def moving(p):
    p = p.replace("\\\\", "/").replace("\\", "/")
    if p in ("0_작업", "0_작업/"):
        return False                     # 층 뿌리는 그대로
    return any(p == m.rstrip("/") or p.startswith(m.rstrip("/") + "/") or (m.endswith("/") and p.startswith(m)) for m in MOVING)


def course_names():
    out = set()
    try:
        with open(os.path.join(VAULT, "3_시스템/lms/courses.json"), encoding="utf-8") as f:
            out |= {v for k, v in json.load(f).items() if not k.startswith("_")}
    except (OSError, ValueError):
        pass
    try:                                  # 주제 등록부가 생겼으면 학교 주제의 별칭까지(프로젝트 별칭 brain·eye 같은 낱말은 잡음)
        sys.path.insert(0, os.path.join(VAULT, "3_시스템"))
        import roles
        for t in roles.topics():
            if t.get("영역") == "학교":
                out.add(t["이름"])
                out |= set(t.get("별칭", []))
    except Exception:
        pass
    return {n for n in out if len(n) >= 2}


def files(roots):
    for r in roots:
        a = r if os.path.isabs(r) else os.path.join(VAULT, r)
        if os.path.isfile(a):
            yield a
            continue
        for dp, dns, fns in os.walk(a):
            dns[:] = [d for d in dns if d not in SKIP_DIRS]
            for f in fns:
                if f.lower().endswith(EXT) and f not in SKIP_FILES:
                    yield os.path.join(dp, f)


def scan(roots, all_paths=False):
    names = course_names()
    name_re = re.compile("|".join(sorted(map(re.escape, names), key=len, reverse=True))) if names else None
    rows = []
    for a in files(roots):
        try:
            text = open(a, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        hits = [m.group(0) for m in LIT.finditer(text)]
        hits += ["%s/%s" % (m.group(1), m.group(2)) for m in JOIN.finditer(text)]
        # 공백 든 움직이는 경로(«고려대 공지»)는 LIT 가 공백에서 끊어 못 본다 — 글자 그대로 한 번 더 센다(10-30 R9 준비에서 조리법 2곳 놓침)
        for m in MOVING:
            if " " in m:
                hits += [m] * sum(text.count(v) for v in {m, m.replace("/", "\\"), m.replace("/", "\\\\")})
        mv = [h for h in hits if moving(h)]
        nm = sorted(set(name_re.findall(text))) if name_re else []
        if mv or nm or (all_paths and hits):
            rel = os.path.relpath(a, VAULT).replace("\\", "/") if a.startswith(VAULT) else a.replace("\\", "/")
            rows.append({"file": rel, "moving": len(mv), "paths": sorted(set(mv if not all_paths else hits)), "names": nm,
                         "exempt": EXEMPT.get(rel)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extra", nargs="*", default=[], help="볼트 밖 소스(플러그인 src 등)")
    ap.add_argument("--all", action="store_true", help="그대로인 경로도 보임")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rows = scan(ROOTS + a.extra, a.all)
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    mv = [r for r in rows if r["moving"] and not r["exempt"]]
    ex = [r for r in rows if r["moving"] and r["exempt"]]
    print("움직이는 경로(예외 밖): %d곳 · %d파일" % (sum(r["moving"] for r in mv), len(mv)))
    for r in sorted(mv, key=lambda r: -r["moving"]):
        print("  %3d %s — %s" % (r["moving"], r["file"], " · ".join(r["paths"][:6]) + (" …" if len(r["paths"]) > 6 else "")))
    print("예외: %d곳 · %d파일" % (sum(r["moving"] for r in ex), len(ex)))
    for r in ex:
        print("  %3d %s — %s" % (r["moving"], r["file"], r["exempt"]))
    nm = [r for r in rows if r["names"]]
    fail = 1 if mv else 0
    print("과목 이름 글자: %d파일" % len(nm))
    for r in nm:
        print("      %s — %s" % (r["file"], " · ".join(r["names"])))
    return fail


if __name__ == "__main__":
    sys.exit(main())
