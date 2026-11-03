#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dist-sync — 두 볼트의 코어 괴리를 층별로 진단하고 업데이트 계획을 낸다.

  py -3 dist-diff.py --a <원본볼트> --b <대상볼트> --mode update|publish [--out <파일>]
  py -3 dist-diff.py --a <배포판> --b <대상볼트> --apply-plugins      (승인 뒤에만)
  py -3 dist-diff.py --a <배포판> --b <대상볼트> --mode update --plan-out <계획.json>
      (P1 · 2026-10-29 볼트 개혁 R3) 계획만 쓴다 — 볼트 내용을 바꾸는 것은 배포판의 `3_시스템/fileops.py update`
      (옛 판은 휴지통 · 장부 · 묶음 하나로 되돌리기). 이 대본은 여전히 볼트 내용을 쓰지 않는다.
  py -3 dist-diff.py --build-known <배포판 worktree>
      (publish 때) 배포판 이력에서 판 해시 표를 만든다 — 안 고친 파일과 사용자가 고친·만든 파일을 가르는 근거.

**진단은 볼트 내용을 고치지 않는다.** 계획·합본은 `3_시스템/_index/dist-sync/` 에만 쓴다.
볼트 쓰기는 `--apply-plugins` 하나뿐이다(2026-10-23) — 배포 플러그인 폴더를 배포판과 같게 하고
배포판이 거둔 플러그인을 지운다. 있는 data.json(사용자 설정)은 건드리지 않는다.

층 분류 근거 → [[외부뇌-dist-sync-모듈]] · ADR-012.
module-forge 스캐폴드 보일러플레이트 ①~⑤는 실측 인시던트 대응이라 지우지 말 것.
"""
import sys, os, re, argparse, hashlib, fnmatch, datetime, json, shutil, filecmp, subprocess, difflib, tempfile

# ① stdout/stderr UTF-8 강제 — Windows 콘솔 기본 cp949 → 한글 출력 시 크래시.
#    (incident-2026-07-04-search-stdout-cp949 계열)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# ② 플러그인 루트 = 이 파일 기준 상대. ${CLAUDE_PLUGIN_ROOT}와 동형(이식성).
HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.abspath(os.path.join(HERE, ".."))
# 내용 층 자리는 역할로(볼트 개혁 R6 · 3_시스템/roles.json) — 시스템 문서 둘은 이름으로 찾는다(옮겨도 따라감)
sys.path.insert(0, os.path.abspath(os.path.join(PLUGIN_ROOT, "..", "..", "..", "3_시스템")))
import roles  # noqa: E402
_CONTENT = [p + "/*" for p in roles.group("content")]
_SYSDOCS = [roles.find_note("설계노트") or roles.path("notes", "설계노트.md"), roles.find_note("사용자설명서") or roles.path("notes", "사용자설명서.md")]

# ── 층 분류. 위에서부터 먼저 맞는 것을 쓴다 ───────────────────────────────
# 개인: 읽지도 않는다. 목록조차 만들지 않는다.
KNOWLEDGE = "2_지식"  # mf:allow-path  (뿌리의 씨앗·원본 목록만 보러 들어가는 칸)
PERSONAL = [
    "1_수집/*", *_CONTENT, "3_시스템/_index/*",  # mf:allow-path
    "3_시스템/_claude-memory/*", ".obsidian/*", ".git/*", "__pycache__/*",  # mf:allow-path
    # DoD 검증(2026-09-12)이 잡은 결함 — settings.local.json 은 개인 권한 설정이고
    # gitignore 대상인데 `.claude/skills/*` 형제라 코어로 분류됐다. 적용 단계였다면 유출.
    ".claude/settings.local.json", "_변환본/*",  # mf:allow-path
    # 2026-10-23 — 작업 폴더(ADR-014 계열)·금고·글씨체 사전은 사용자 것. 금고 파일이 «미분류»로 리포트에 올라왔다.
    "0_작업/*", "3_시스템/vault/*", "3_시스템/handwriting/samples/*",  # mf:allow-path
    "3_시스템/handwriting/profile.md", "3_시스템/handwriting/samples.json",  # mf:allow-path
    # 2026-10-29 볼트 개혁(ADR-018) — 행위 장부에는 개인 경로·파일명·까닭이 든다. 장부 보기도 사용자 것.
    "3_시스템/ledger/*", "2_지식/장부.md",  # mf:allow-path
    # 2026-11-03 볼트 개혁 반영 — 개인 일정 · 옛 노트 자리 · 제작자 모듈(eye = 개인 프로젝트 · study-helper = 공개 저장소가 따로)
    # 학교 수집(LMS·공지 조리법·판정)·보고서 대본은 특정 학교·과제에 묶여 있다 · 행위는 optional 이라 없어도 고장이 아니다
    "2_지식/일정/*", "2_지식/notes/*", ".claude/skills/eye/*", ".claude/skills/study-helper/*",  # mf:allow-path
    "3_시스템/lms/*", "3_시스템/lms-*", "3_시스템/collect/*", "3_시스템/web-collect.py", "3_시스템/notice-filter.py",  # mf:allow-path
    "3_시스템/labreport-*", "3_시스템/dsl-report-build.py", "3_시스템/md2docx-simple.py",  # mf:allow-path
    "3_시스템/ask.py", "3_시스템/travel-mode.ps1",  # mf:allow-path
]
# 예외 — 개인 폴더 안이지만 제작자가 배포하는 것
PERSONAL_EXCEPT = list(_SYSDOCS)

# 씨앗: 머리말(제작자 규약) + 항목(사용자 데이터)이 한 파일에 섞여 있다.
SEED = [
    "2_지식/recent.md", "2_지식/open-loops.md", "2_지식/MOC.md",  # mf:allow-path
    "2_지식/profile.md", "3_시스템/config.json",  # mf:allow-path
    *_SYSDOCS,
    "2_지식/주제.md",  # mf:allow-path  (볼트 개혁 R6 — 머리말 = 규약 · JSON 블록 = 개인 주제)
    "2_지식/보존.md",  # mf:allow-path  (볼트 개혁 R8 — 표 값은 사용자가 고침)
]
# CLAUDE.md 는 단독 층 — §0(개인) + 나머지(코어)가 한 파일이다.
# 경로 «세그먼트» 제외 — 글로브는 중첩 경로를 못 잡는다.
#   DoD 검증(2026-09-12)에서 `.claude/skills/*/scripts/__pycache__/*.pyc` 가 새어 들어왔고
#   worktree 의 `.git` 은 디렉터리가 아니라 **파일**이라 «지워질 파일» 목록에 올랐다.
#   적용 단계였다면 저장소를 지울 뻔했다.
EXCLUDE_SEG = {"__pycache__", ".git", ".obsidian", "_index", "_claude-memory", "node_modules", ".trash"}
EXCLUDE_EXT = (".pyc", ".pyo", ".lock", ".tmp")

# 배포판이 직접 만든 Obsidian 플러그인(2026-10-13 Brain Sheet) — `.obsidian/` 은 통째로 제외지만 이 폴더는 코어다.
# 남의 커뮤니티 플러그인 본체는 여전히 제외. 플러그인 설정(data.json)은 사용자 것이라 개인.
DIST_PLUGINS = [".obsidian/plugins/brain-source/", ".obsidian/plugins/brain-base/", ".obsidian/plugins/brain-calendar/"]  # mf:allow-path
DIST_PLUGIN_PERSONAL = {"data.json"}
# 배포판이 거둔 플러그인 → 대신 쓰는 것(2026-10-22 brain-sheet → brain-source · .sheet 를 이어 맡음).
# 거둔 것만 지우고 대신 쓰는 것을 켜야 한다 — 거둔 것이 «켜짐» 으로 남아 있으면 brain-source 는
# 그쪽이 .sheet 를 맡는 줄 알고 비켜서, 아무도 안 맡은 .sheet 가 탐색기에서 사라진다(10-18 버그와 같은 꼴).
RETIRED_PLUGINS = {"brain-sheet": "brain-source"}
COMMUNITY = ".obsidian/community-plugins.json"  # mf:allow-path
# 기존 볼트에 처음 들어올 때의 설정 — data.json 이 없으면 brain-base 는 새 설치로 보고 곁창·리본을 기본 배치로 바꾼다.
# 새 설치는 업데이터를 거치지 않으므로, 업데이터가 넣을 때는 사용자의 배치·기본 탐색기를 그대로 둔다(2026-11-03 사본 시험).
FIRST_ARRIVAL = {"brain-base": {"replaceExplorer": False}}

# 판 해시 표(2026-11-03) — 배포판이 실어 보낸 코어의 과거 판. 안 고친 파일과 사용자가 고친·만든 파일을 가른다.
# git 공통 조상에 기대지 않고(얕은 복제·이력 고쳐 쓰기에도 그대로) 내용 없이 해시만 싣는다. 만드는 곳 = publish(--build-known).
KNOWN_REL = ".claude/skills/dist-sync/known-hashes.json"  # mf:allow-path
LINE_FILES = {".gitignore", ".gitattributes"}  # mf:allow-path  줄 모음 — 사용자 줄을 잃으면 숨긴 파일이 커밋된다. 겹치면 양쪽을 다 남긴다
KEEP_IF_MODIFIED = {"3_시스템/default-layout.json"}  # mf:allow-path  사용자가 «지금 배치를 기본으로» 한 결과 — 합칠 것이 아니다
RX_S0 = re.compile(r"^## §0.*?(?=^## )", re.S | re.M)
S0_MARK = "<!-- §0 -->\n"
MISSING = object()
ANON_AUTHOR = "External Brain"  # 배포판 커밋 작성자 — 배포판 worktree 는 제작자 저장소와 설정을 나눠 쓴다
MIN_LIKENESS = 0.3  # 과거 판과 이보다 덜 닮으면 합치지 않고 묻는다(줄 비율 · 낮을수록 사용자가 통째로 다시 쓴 것)
UPDATE_SKILL = os.path.join(".claude", "skills", "dist-sync", "skills", "update", "SKILL.md")
# 계획 칸 `why` — 사람이 읽고 리포트가 묶는 말
WHY_NEW, WHY_REPLACE, WHY_MERGED, WHY_REMOVED, WHY_SEED = "새로 넣음", "새 판으로 바꿈", "내 수정과 합침", "배포판이 뺀 것 휴지통", "없는 씨앗 넣음"

L_CLAUDE = "CLAUDE.md"  # mf:allow-path  (층 라벨 겸 경로 — 리터럴은 여기 한 곳뿐)
SPECIAL = [L_CLAUDE]

# 코어: 통째로 교체 가능
CORE = [
    ".claude/skills/*", ".claude/settings.json", ".claude/output-styles/*",  # mf:allow-path
    "3_시스템/hooks/*", "3_시스템/search.py", "3_시스템/session-stub.py",  # mf:allow-path
    "3_시스템/tokens.py", "3_시스템/conventions.md", "3_시스템/_ref/*",  # mf:allow-path
    "3_시스템/_eval/*", "README.md", ".gitattributes", ".gitignore",  # mf:allow-path
    # 원본 형식 수용(2026-10-14) — 색인기·그림 소화·원본 목록 보기
    "3_시스템/ingest.py", "3_시스템/ingest_vision.py", "3_시스템/claude_bin.py", "2_지식/원본 목록.base",  # mf:allow-path
    "3_시스템/hwlayout.py",  # mf:allow-path  — 손글씨 줄 상자(판서 끌어 고르기 · 2026-11-02)
    "3_시스템/handwriting/README.md",  # mf:allow-path
    # 볼트 행위(2026-10-29 · ADR-018) — 단일 실행자 · 배포판 이전(migration) 파일
    "3_시스템/fileops.py", "3_시스템/migrations/*", "3_시스템/sendto-inbox.ps1",  # mf:allow-path
    # 행위 층(볼트 개혁 R4 · 2026-10-30) — 실행기 + 코어 행위 선언(장부 ledger/actions.jsonl 은 개인)
    "3_시스템/brain.py", "3_시스템/actions.json", "3_시스템/props-sync.py",  # mf:allow-path
    # 역할 → 자리(볼트 개혁 R6 · 2026-10-30) — 코드가 자리를 박지 않고 묻는 곳(주제 목록 2_지식/주제.md 는 씨앗)
    "3_시스템/roles.py", "3_시스템/roles.json",  # mf:allow-path
    # 주제 카드(R7) · 정리 후보(R8) · 구조 이전·받은함 자동 분류(R9) — 2026-10-30
    "3_시스템/topic.py", "3_시스템/cleanup.py", "3_시스템/restructure.py", "3_시스템/inbox.py",  # mf:allow-path
    # 작업 폴더 원칙 — 끝남 판정·제출본 대조·정리 계획(2026-10-31) · 근거 표·정리 규칙(보편화 2026-11-02)
    "3_시스템/work.py", "3_시스템/work.json",  # mf:allow-path
    # 따라가기 — 옵시디언 밖에서 옮기거나 지운 파일 뒤처리(설계안 §19.3 · 2026-11-03)
    "3_시스템/follow.py", "3_시스템/outside.py", "3_시스템/default-layout.json",  # mf:allow-path
    # 코어 훅·행위가 부르는 대본(2026-11-03 반영 때 층 분류) — 표 고침·MOC·어긋남·기록·주간·일정·변환 · 대화창 규약 글
    "3_시스템/mdtable.py", "3_시스템/moc.py", "3_시스템/drift.py", "3_시스템/record.py", "3_시스템/weekly.py",  # mf:allow-path
    "3_시스템/skillstat.py", "3_시스템/schedule.py", "3_시스템/docpdf.py", "3_시스템/vault-chat/*",  # mf:allow-path
    # 공휴일 표 받기(캘린더가 읽음 · 표는 일정 폴더 — 개인) — 2026-11-03
    "3_시스템/holidays.py",  # mf:allow-path
]

# publish 방향에서 배포판에 새어 나가면 안 되는 것 (2026-08-03 전수검사 계열)
# 실명·호칭·개인 저장소 이름은 여기 적지 않는다 — 이 스크립트도 배포되므로 패턴 자체가 샌다.
# 볼트마다 LEAK_LOCAL(gitignore)에 «정규식<TAB>이름» 을 한 줄씩 적는다. 없으면 리포트가 경고한다.
LEAK_LOCAL = os.path.join("3_시스템", "_index", "dist-sync", "leak-patterns.txt")
LEAK = [
    (r"[\w.+-]+@[\w-]+\.[\w.-]+", "이메일"),
    (r"C--[\w-]+", "Claude 프로젝트 폴더 이름"),
    (r"C:[\\/]Users[\\/][^\s\"')]+", "사용자 홈 경로"),
    (r"\b[0-9a-f]{8}\b(?![0-9a-f])", "세션 id 후보(⚠ PubMed·DOI 오탐 가능)"),
]
# 기계 치환이 깬 흔적 (2026-08-03 일괄치환이 남긴 `사용자이` 계열)
BROKEN = [r"사용자이\s", r"사용자은\s", r"사용자을\s", r"사용자가가", r"사용자이가"]


# ⚠ 위 목록 줄의 `mf:allow-path`는 **P0(읽기 전용)에서만 정당하다.**
#   check.py 의 I1 은 «언급»과 «접근»을 구분하지 못해 분류표를 코어 수정으로 읽는다.
#   check.py 자신도 같은 이유로 자기 CORE_PATHS 에 같은 escape 를 달았다.
#   ⛔ P1 에서 쓰기를 열면 이 escape 가 **진짜 위반을 가린다.** 그때는 escape 를 걷고
#      module-forge 가드레일과의 충돌을 정면으로 푼다(ADR-012 미결).


def layer(rel):
    """경로 → 층. 제외가 가장 강하고, 그다음 개인, 예외가 개인보다 강하다."""
    p = rel.replace("\\", "/")
    segs = p.split("/")
    for d in DIST_PLUGINS:
        if p.startswith(d):
            if p.endswith(EXCLUDE_EXT):
                return "제외"
            return "개인" if p[len(d):] in DIST_PLUGIN_PERSONAL else "코어"
    if EXCLUDE_SEG & set(segs) or p.endswith(EXCLUDE_EXT):
        return "제외"
    if p in PERSONAL_EXCEPT:
        return "씨앗"
    for g in PERSONAL:
        if fnmatch.fnmatch(p, g) or p.startswith(g.rstrip("*")):
            return "개인"
    if p in SPECIAL:
        return L_CLAUDE
    if p in SEED:
        return "씨앗"
    for g in CORE:
        if fnmatch.fnmatch(p, g) or p.startswith(g.rstrip("*")):
            return "코어"
    # 지식 칸의 나머지는 역할에 없어도 사용자 것이다 — 옛 판 자리(sessions·decisions)와 사용자가 만든 폴더의 이름이 리포트에 올라왔다(2026-11-03 사본 시험)
    if p.startswith(KNOWLEDGE + "/"):
        return "개인"
    return "미분류"


def sha(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            # 줄바꿈 차이를 괴리로 세지 않는다 — .gitattributes 가 LF 고정이라
            # CRLF 는 노이즈다(오늘 status 의 4건이 전부 이것이었다).
            h.update(f.read().replace(b"\r\n", b"\n"))
    except OSError:
        return None
    return h.hexdigest()[:12]


def walk(root):
    """개인 층은 들어가지도 않는다."""
    out = {}
    for dp, dns, fns in os.walk(root):
        rel_dir = os.path.relpath(dp, root).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        # 배포 플러그인으로 가는 길(.obsidian · .obsidian/plugins)은 그 폴더 하나만 보러 들어간다 — 형제 파일은 layer 가 제외한다
        dns[:] = [d for d in dns
                  if (rel_dir + "/" + d).lstrip("/") == KNOWLEDGE
                  or any(x.startswith((rel_dir + "/" + d).lstrip("/") + "/") for x in DIST_PLUGINS)
                  or layer((rel_dir + "/" + d).lstrip("/") + "/x") not in ("개인", "제외")]
        for fn in fns:
            rel = (rel_dir + "/" + fn).lstrip("/")
            if layer(rel) in ("개인", "제외"):
                continue
            out[rel] = os.path.join(dp, fn)
    return out


def scan_leaks(files):
    hits = []
    for rel, full in sorted(files.items()):
        # css·js 도 본다 — brain-source styles.css 주석에 호칭이 7곳 있었다(2026-10-22).
        # 압축된 js 는 16진 8자가 흔해 세션 id 후보는 거기서 세지 않는다.
        code = re.search(r"\.(css|js|mjs)$", rel)
        if not (code or re.search(r"\.(md|py|ps1|json|sh|tsv|txt)$", rel)):
            continue
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    # 번들 js 는 한글을 \uXXXX 로 내보낸다 — 풀지 않으면 호칭·실명을 못 본다(2026-10-23 빈틈)
                    if code:
                        line = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), line)
                    for rx, label in LEAK:
                        if code and label.startswith("세션 id"):
                            continue
                        if re.search(rx, line):
                            hits.append((rel, i, label, line.strip()[:90]))
                            break
        except OSError:
            continue
    return hits


def scan_broken(files):
    hits = []
    for rel, full in sorted(files.items()):
        if not re.search(r"\.(md|py|ps1)$", rel):
            continue
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    for rx in BROKEN:
                        if re.search(rx, line):
                            hits.append((rel, i, line.strip()[:90]))
                            break
        except OSError:
            continue
    return hits


def load_local_leaks(vault):
    """볼트 전용 패턴(실명·호칭·개인 저장소 이름). 파일이 없으면 None."""
    p = os.path.join(vault, LEAK_LOCAL)
    if not os.path.exists(p):
        return None
    out = []
    with open(p, encoding="utf-8") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if ln.strip() and not ln.startswith("#"):
                rx, _, label = ln.partition("\t")
                out.append((rx, label.strip() or "개인 패턴"))
    return out


def author_hits(B):
    """배포판 worktree 에서 아직 안 올린 커밋 중 작성자·커미터가 익명이 아닌 것의 해시(2026-11-03 실명·메일 커밋 2개를 파일 스캔이 못 봄)."""
    out = git_out(B, "log", "--format=%h%x00%an%x00%cn", "@{u}..HEAD") or b""
    hits = []
    for line in out.decode("utf-8", "replace").splitlines():
        h, an, cn = line.split("\0")
        if an != ANON_AUTHOR or cn != ANON_AUTHOR:
            hits.append(h)
    return hits


def plan_lines(plan):
    """업데이트 계획을 사람이 읽을 줄로 — 승인하는 사람이 보는 것."""
    L = []
    w = L.append
    if plan.get("error"):
        return ["## ⛔ 업데이트 계획을 못 냈다", "", plan["error"], ""]
    by = {}
    for o in plan["ops"]:
        by.setdefault(o.get("why", ""), []).append(o["rel"])
    w("## 이 업데이트가 할 일")
    w("")
    w("- " + " · ".join("%s %d" % (k, len(v)) for k, v in by.items()) if by else "- 바꿀 파일 없음")
    w("- 못 합쳐 그대로 둠 %d · 사용자 판을 남김 %d" % (len(plan["conflicts"]), len(plan["kept"])))
    w("")
    for title, why in (("내 수정과 합침 — 내 수정과 배포판 변경을 둘 다 살렸다", WHY_MERGED),
                       ("배포판이 뺀 파일 — 안 고친 것이라 휴지통으로(30일)", WHY_REMOVED),
                       ("없던 씨앗을 넣음 — 덮어쓰지 않는다", WHY_SEED)):
        if by.get(why):
            w("### %s" % title)
            w("")
            w("\n".join("- `%s`" % r for r in by[why]))
            w("")
    if plan["conflicts"]:
        w("### ⛔ 못 합침 — 내 파일을 그대로 둔다. 하나씩 정해야 한다")
        w("")
        for c in plan["conflicts"]:
            w("- `%s` — %s · 새 판 = `%s`" % (c["rel"], c["why"], c["new"]))
        w("")
    if plan["kept"]:
        w("### 사용자 판을 남김")
        w("")
        w("\n".join("- `%s`" % k for k in plan["kept"]))
        w("")
    return L


def report(A, B, mode, plan=None):
    fa, fb = walk(A), walk(B)
    added = sorted(set(fa) - set(fb))       # A 에만 = B 에 새로 들어갈 것
    # ⛔ B 에만 있는 것 ≠ «배포판이 지운 것». 대상 볼트가 스스로 만든 파일이 전부 여기 섞인다.
    #   실측(2026-09-12): 공통 조상 기준 0건인데 단순 집합차로는 51건이 나왔다.
    #   update 는 판 해시 표로 가른다(update_plan). 여기 목록은 publish 방향에서만 쓴다.
    removed = sorted(set(fb) - set(fa))
    common = sorted(set(fa) & set(fb))
    changed = [r for r in common if sha(fa[r]) != sha(fb[r])]

    L = []
    w = L.append
    w("# dist-sync 진단 — %s" % datetime.date.today())
    w("")
    if mode == "update" and sha(os.path.join(A, UPDATE_SKILL)) != sha(os.path.join(B, UPDATE_SKILL)):
        # 옛 스킬도 배포판 쪽 이 대본을 돌린다 — 새 절차로 넘어오는 길은 여기다
        w("> **이 볼트의 `dist-sync:update` 스킬은 옛 판이다.** «P0 = 진단뿐»·«적용은 열려 있지 않다»는 옛 판의 말이다.")
        w("> 이 배포판은 적용 장치를 실어 왔다. 사용자에게 알리고 `%s` 를 읽어 그 절차를 따른다(미리 보기, 사람 승인, 적용)."
          % os.path.join(A, UPDATE_SKILL).replace("\\", "/"))
        w("")
    w("- 방향: **%s**  (A=%s → B=%s)" % (mode, A, B))
    w("- A 추적 %d파일 · B 추적 %d파일 (개인 층은 열지 않았다)" % (len(fa), len(fb)))
    w("")
    w("## 층별 요약")
    w("")
    w("| 층 | 새로 들어감 | 내용 다름 | %s |" % ("대상에만(지우는 것 아님)" if mode == "update" else "**지워짐**"))
    w("|---|---:|---:|---:|")
    for lay in ("코어", "씨앗", L_CLAUDE, "미분류"):
        w("| %s | %d | %d | %d |" % (
            lay,
            sum(1 for r in added if layer(r) == lay),
            sum(1 for r in changed if layer(r) == lay),
            sum(1 for r in removed if layer(r) == lay)))
    w("")

    if mode == "update" and plan:
        L += plan_lines(plan)
    if removed and mode == "publish":
        w("## ⛔ 대상 볼트에만 있는 파일 — **지울 목록이 아니다**")
        w("")
        w("여기에는 두 가지가 섞여 있다 — ⑴배포판이 제거한 것 ⑵**대상 볼트가 스스로 만든 것.**")
        w("")
        for r in removed:
            w("- `%s`  (%s 층)" % (r, layer(r)))
        w("")

    for lay, note in (("코어", "통째 교체 가능"),
                      ("씨앗", "**머리말만 갱신 · 항목 보존** — Claude 판단 구간"),
                      (L_CLAUDE, "**§0 보존 · 나머지 교체** — Claude 판단 구간"),
                      ("미분류", "⚠ 층 규칙에 없다. 분류를 정하기 전에는 옮기지 않는다")):
        if mode == "update" and lay in ("코어", L_CLAUDE):     # 위 «할 일» 이 대신한다
            continue
        items = [r for r in added if layer(r) == lay] + [r for r in changed if layer(r) == lay]
        if not items:
            continue
        w("## %s — %s" % (lay, note))
        w("")
        for r in sorted(set(items)):
            w("- `%s`%s" % (r, "  *(새 파일)*" if r in added else ""))
        w("")

    if mode == "publish":
        local = load_local_leaks(A)
        if local:
            LEAK.extend(local)
        leaks = scan_leaks({r: fa[r] for r in (added + changed) if r in fa})
        w("## 익명화 후보 — %d건" % len(leaks))
        w("")
        if local is None:
            w("⚠ `%s` 가 없어 **실명·호칭은 검사하지 않았다.** «정규식<TAB>이름» 을 한 줄씩 적고 다시 돌린다."
              % LEAK_LOCAL.replace(os.sep, "/"))
            w("")
        w("스크립트는 **찾기만** 한다. 실제 문구는 사람·Claude 가 쓴다 —")
        w("기계 일괄치환이 `<호칭>님이`를 `사용자이`로 만든 전례가 있다(2026-08-03).")
        w("")
        for rel, i, label, txt in leaks[:60]:
            w("- `%s:%d` — %s: `%s`" % (rel, i, label, txt))
        if len(leaks) > 60:
            w("- … 외 %d건" % (len(leaks) - 60))
        w("")
        broken = scan_broken(fb)
        w("## 대상 볼트의 치환 파손 — %d건" % len(broken))
        w("")
        for rel, i, txt in broken:
            w("- `%s:%d` — `%s`" % (rel, i, txt))
        w("")
        named = author_hits(B)
        w("## 올라갈 커밋의 작성자 — 익명이 아닌 것 %d건" % len(named))
        w("")
        if named:
            w("push 전에 작성자를 고친다. 위 익명화 후보는 파일만 보고 이 칸을 보지 않는다.")
            w("")
        for h in named:
            w("- `%s`" % h)
        w("")

    if mode == "update":
        plan, _ = plugins(A, B, dry=True)
        w("## 배포 플러그인 교체 계획 — %d건" % sum(1 for x in plan if x[0] != "·"))
        w("")
        w("승인 뒤 `--apply-plugins` 로만 실행한다. **옵시디언을 닫고** 돌린다(켜 둔 옵시디언은 플러그인 목록을 자기 기억으로 다시 쓴다).")
        w("")
        for x in plan:
            w("- %s %s" % x)
        w("")

    w("## 이 리포트가 하지 않은 것")
    w("")
    w("- 볼트 내용을 **하나도 고치지 않았다**(계획·합본은 `3_시스템/_index/dist-sync/` 에만).")
    w("- 개인 층(`1_수집/`·`notes|sessions|decisions/`·`_index/`·`_claude-memory/`)은 **열지 않았다.**")
    w("- 씨앗 파일의 «머리말과 항목의 경계»는 재지 않았다 — 사람·Claude 가 읽어야 한다.")
    return "\n".join(L) + "\n", (len(added), len(changed), len(removed))


def plugin_dir(root, name):
    return os.path.join(root, ".obsidian", "plugins", name)


def obsidian_running():
    if os.name != "nt":
        return False
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/NH"],
                             capture_output=True, text=True, errors="replace").stdout
    except OSError:
        return False
    return "obsidian.exe" in out.lower()


def plugins(A, B, dry):
    """배포 플러그인 교체 — 들이기(DIST_PLUGINS 폴더를 A 와 같게) + 거두기(RETIRED_PLUGINS 지우기) + 켜짐 목록.
    data.json 은 어느 쪽도 건드리지 않는다. 돌려주는 것 = [(표시, 설명)], 실행 여부."""
    log = []
    names = [d.rstrip("/").rsplit("/", 1)[1] for d in DIST_PLUGINS]
    for n in names:
        src, dst = plugin_dir(A, n), plugin_dir(B, n)
        if not os.path.isfile(os.path.join(src, "manifest.json")):
            # 들일 것이 없는데 거두면 .sheet 를 맡을 플러그인이 하나도 안 남는다
            return log + [("✗", "배포판에 `%s` 가 없다 — 들이기·거두기 모두 멈춤" % n)], False
        want = {f for f in os.listdir(src)
                if os.path.isfile(os.path.join(src, f))
                and f not in DIST_PLUGIN_PERSONAL and not f.endswith(EXCLUDE_EXT)}
        have = {f for f in os.listdir(dst) if os.path.isfile(os.path.join(dst, f))} if os.path.isdir(dst) else set()
        if not dry:
            os.makedirs(dst, exist_ok=True)
        same = 0
        for f in sorted(want):
            s, d = os.path.join(src, f), os.path.join(dst, f)
            if f in have and filecmp.cmp(s, d, shallow=False):
                same += 1
                continue
            log.append(("+", "`%s/%s` %s" % (n, f, "바꿈" if f in have else "넣음")))
            if not dry:
                shutil.copyfile(s, d)
        for f in sorted(have - want - DIST_PLUGIN_PERSONAL):
            log.append(("-", "`%s/%s` 지움(배포판에 없음)" % (n, f)))
            if not dry:
                os.remove(os.path.join(dst, f))
        if same:
            log.append(("·", "`%s` 같은 파일 %d개 그대로" % (n, same)))
        if n in FIRST_ARRIVAL and not os.path.exists(os.path.join(dst, "data.json")):
            log.append(("+", "`%s/data.json` 처음 설정 — 지금 배치·기본 탐색기를 그대로 둔다" % n))
            if not dry:
                write_text(os.path.join(dst, "data.json"), json.dumps(FIRST_ARRIVAL[n], indent=2) + "\n")

    on_path = os.path.join(B, COMMUNITY)
    try:
        with open(on_path, encoding="utf-8") as f:
            on = json.load(f)
    except (OSError, ValueError):
        on = []
    new_on = list(on)
    for old, new in RETIRED_PLUGINS.items():
        d = plugin_dir(B, old)
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                p = os.path.join(d, f)
                if f in DIST_PLUGIN_PERSONAL:
                    log.append(("·", "`%s/%s` 남김(사용자 설정)" % (old, f)))
                elif os.path.isfile(p):
                    log.append(("-", "`%s/%s` 지움(배포판이 거둠 → `%s`)" % (old, f, new)))
                    if not dry:
                        os.remove(p)
            if not dry and not os.listdir(d):
                os.rmdir(d)
        if old in new_on:
            new_on.remove(old)
            log.append(("-", "켜짐 목록에서 `%s` 뺌" % old))
            if new not in new_on:
                new_on.append(new)
                log.append(("+", "켜짐 목록에 `%s` 넣음(`%s` 를 이어 맡음)" % (new, old)))
    if new_on != on and not dry:
        with open(on_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(new_on, indent=2, ensure_ascii=False) + "\n")
    for n in names:
        if n not in new_on:
            log.append(("·", "`%s` 는 꺼져 있다 — 옵시디언 설정 › 커뮤니티 플러그인에서 켠다" % n))
    return log, True


def merge_claude(a_path, b_path):
    """배포판 규약 파일(L_CLAUDE) 본문에 대상의 §0(사용자 칸 · 인터뷰 산출물)을 끼운다. §0 을 어느 한쪽에서 못 찾으면 None — 손으로."""
    with open(a_path, encoding="utf-8") as f:
        ta = f.read()
    if not b_path or not os.path.exists(b_path):
        return ta
    with open(b_path, encoding="utf-8") as f:
        tb = f.read()
    ma, mb = RX_S0.search(ta), RX_S0.search(tb)
    if not ma or not mb:
        return None
    return ta[:ma.start()] + mb.group(0) + ta[ma.end():]


def dist_version(A):
    try:
        return subprocess.run(["git", "-C", A, "describe", "--tags", "--always"],
                              capture_output=True, text=True, errors="replace").stdout.strip()
    except OSError:
        return ""


# ── 판 해시 표 · 합치기 ─────────────────────────────────────────────────────

def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def body(rel, data):
    """견주는 내용 — 줄바꿈 차이는 빼고, 규약 파일은 §0 도 뺀다(인터뷰가 채워 사람마다 다르다)."""
    data = data.replace(b"\r\n", b"\n")
    if rel == L_CLAUDE:
        data = RX_S0.sub(S0_MARK, data.decode("utf-8", "replace"), count=1).encode("utf-8")
    return data


def key_of(rel, data):
    return hashlib.sha256(body(rel, data)).hexdigest()[:12]


def core_zone(rel):
    """표에 오르는 자리 = 배포판이 실어 보낸 코어. 표에 없는 경로는 업데이터가 사용자가 만든 것으로 보고 손대지 않는다."""
    if any(rel.startswith(d) for d in DIST_PLUGINS) or rel == KNOWN_REL:
        return False
    lay = layer(rel)
    return lay in ("코어", L_CLAUDE) or (lay == "미분류" and rel.startswith((".claude/", "3_시스템/")))  # mf:allow-path


def git_out(A, *args, stdin=None):
    r = subprocess.run(["git", "-C", A, *args], capture_output=True, input=stdin)
    return r.stdout if r.returncode == 0 else None


def build_known(A):
    """배포판 이력과 설치 태그의 모든 커밋에서 코어 자리의 판을 모아 표를 쓴다 → (경로 수, 판 수).
    태그는 설치 태그 꼴만 — 배포판 worktree 는 제작자 저장소와 .git 을 나눠 쓰므로 다른 태그의 파일 이름이 새지 않게."""
    revs = (git_out(A, "rev-list", "HEAD", "--tags=v*-template") or b"").split()
    if not revs:
        raise SystemExit("git 이력이 없다: %s" % A)
    blobs = {}
    for rev in revs:
        for ent in (git_out(A, "ls-tree", "-r", "-z", rev.decode()) or b"").split(b"\0"):
            if ent:
                meta, path = ent.split(b"\t", 1)
                _, kind, blob = meta.decode().split()
                path = path.decode("utf-8", "replace")
                if kind == "blob" and core_zone(path):
                    blobs.setdefault(path, set()).add(blob)
    ids = sorted({b for s in blobs.values() for b in s})
    raw = git_out(A, "cat-file", "--batch", stdin=("\n".join(ids) + "\n").encode())
    data, i = {}, 0
    for blob in ids:
        j = raw.index(b"\n", i)
        size = int(raw[i:j].split()[2])
        data[blob] = raw[j + 1:j + 1 + size]
        i = j + 1 + size + 1
    table = {p: {key_of(p, data[b]): b[:16] for b in sorted(s)} for p, s in sorted(blobs.items())}
    write_text(os.path.join(A, KNOWN_REL), json.dumps({"schema": 1, "rev": revs[0].decode()[:12], "paths": table},
                                                      ensure_ascii=False, indent=0, sort_keys=True) + "\n")
    return len(table), sum(len(v) for v in table.values())


def load_known(A):
    try:
        with open(os.path.join(A, KNOWN_REL), encoding="utf-8") as f:
            return json.load(f)["paths"]
    except (OSError, ValueError, KeyError):
        return None


def closest_base(A, rel, mine, vers, new):
    """사용자 판과 가장 가까운 과거 판 = 합치기 기준 → (기준, 닮은 정도). 배포판 저장소에 없으면(얕은 복제) (None, 0).
    새 판은 기준에서 뺀다 — 기준으로 삼으면 «배포판이 안 바꿨다»가 되어 새 판의 변경을 버린다(한 줄 더한 판이 새 판과 더 닮아 보였다).
    표에 새 판 하나뿐일 때만 새 판이 기준이다(그 판에서 사용자가 고친 것)."""
    ml = mine.decode("utf-8", "replace").splitlines()

    def likeness(data):
        return difflib.SequenceMatcher(None, ml, data.decode("utf-8", "replace").splitlines(), autojunk=False).ratio()

    vers = vers or {}
    if set(vers) == {key_of(rel, new)}:
        return new, likeness(new)
    best, best_r = None, 0.0
    for blob in sorted(set(vers.values())):
        data = git_out(A, "cat-file", "blob", blob)
        if data is not None:
            data = body(rel, data)
            r = likeness(data)
            if data != new and (best is None or r > best_r):
                best, best_r = data, r
    return best, best_r


def json3(base, mine, new):
    """값 단위 3자 합치기 — 사용자가 더한 키·목록 항목을 살리고, 둘 다 바꾼 값은 사용자 것을 쓴다."""
    if mine == base:
        return new
    if new == base or mine == new:
        return mine
    if isinstance(mine, dict) and isinstance(new, dict):
        b = base if isinstance(base, dict) else {}
        out = {}
        for k in list(new) + [k for k in mine if k not in new]:
            v = json3(b.get(k, MISSING), mine.get(k, MISSING), new.get(k, MISSING))
            if v is not MISSING:
                out[k] = v
        return out
    if isinstance(mine, list) and isinstance(new, list):
        b = base if isinstance(base, list) else []
        return [x for x in new if x in mine or x not in b] + [x for x in mine if x not in b and x not in new]
    return mine


def merge_file(mine, base, new, union=False):
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, data in (("mine", mine), ("base", base), ("new", new)):
            paths.append(os.path.join(d, name))
            with open(paths[-1], "wb") as f:
                f.write(data)
        r = subprocess.run(["git", "merge-file", "-p"] + (["--union"] if union else []) + paths, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def added_only(mine, base):
    """사용자 변경이 줄 추가뿐이면 더한 줄들, 고치거나 지운 곳이 있으면 None."""
    ml, bl = mine.split(b"\n"), base.split(b"\n")
    lines = []
    for tag, _, _, j1, j2 in difflib.SequenceMatcher(None, bl, ml, autojunk=False).get_opcodes():
        if tag == "insert":
            lines += ml[j1:j2]
        elif tag != "equal":
            return None
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines or None


def merge3(A, rel, mine, new, vers):
    """사용자가 고친 파일 = 사용자 변경 + 배포판 변경 → (합친 내용, None) · 못 합치면 (None, 까닭). 못 합친 파일은 건드리지 않는다."""
    base, like = closest_base(A, rel, mine, vers, new)
    if rel in LINE_FILES:
        out = merge_file(mine, base if base is not None else b"", new, union=True)
        return (out, None) if out is not None else (None, "합치기 실패")
    if base is None:
        return None, "기준 판이 없다(사용자가 같은 이름으로 만든 파일이거나 얕은 복제)"
    if like < MIN_LIKENESS:
        return None, "같은 이름의 다른 파일로 보인다"
    if rel.endswith(".json"):
        try:
            merged = json3(json.loads(base), json.loads(mine), json.loads(new))
        except ValueError:
            return None, "JSON 을 못 읽는다"
        return (json.dumps(merged, ensure_ascii=False, indent=2) + "\n").encode("utf-8"), None
    out = merge_file(mine, base, new)
    if out is None and rel.endswith(".md"):
        # 규칙 글에 줄만 더한 것이 가장 흔한 수정이다 — 배포판이 근처를 고쳤어도 잃지 않게 새 판 끝에 붙인다
        lines = added_only(mine, base)
        if lines:
            return new.rstrip(b"\n") + b"\n\n" + b"\n".join(lines) + b"\n", None
    if out is None:
        return None, "같은 곳을 양쪽이 고쳤다"
    if rel.endswith(".py"):
        try:
            compile(out, rel, "exec")
        except (SyntaxError, ValueError):
            return None, "합친 결과가 파이썬 문법에 어긋난다"
    return out, None


def update_plan(A, B):
    """업데이트 계획 = fileops update 의 입력(P1 · 2026-10-29 R3 · 판 해시 표 2026-11-03).
    코어: 없으면 넣음 · 표에 있는 판(안 고침)이면 새 판 · 표에 없으면(사용자가 고침) 합치고, 못 합치면 그대로 두고 conflicts 로 알린다.
    규약 파일 L_CLAUDE: 배포판 본문 + 대상 §0 · §0 밖을 고쳤으면 같은 방식으로 합침.
    배포판이 뺀 파일: 표에 있는 판이면 휴지통 · 고쳤으면 남김 · 표에 없는 경로(사용자가 만든 것)는 손대지 않는다.
    씨앗: 없는 것만 넣는다(뿌리 칸만 — 내용 층은 fileops 가 막는다) · 배포 플러그인 = --apply-plugins 몫.
    이 함수는 계획·합본을 `_index/dist-sync/`(모듈 상태 칸)에만 쓴다 — 코어를 바꾸는 것은 코어 fileops(ADR-018) + 게이트 한 번."""
    fa, fb = walk(A), walk(B)
    known = load_known(A)
    head = {"source": os.path.abspath(A), "version": dist_version(A)}
    if known is None:
        return dict(head, error="배포판에 판 해시 표(`%s`)가 없다 — 고친 파일을 가릴 수 없어 계획을 내지 않는다." % KNOWN_REL)
    state = os.path.join(B, "3_시스템", "_index", "dist-sync")
    ops, notes, conflicts, kept = [], [], [], []
    # 이미 합친 결과 — 사용자 판·새 판이 그대로면 다시 합치지 않는다(다시 돌려도 계획 0건)
    done_p = os.path.join(state, "합본.json")
    try:
        with open(done_p, encoding="utf-8") as f:
            done = json.load(f)
    except (OSError, ValueError):
        done = {}

    def stash(kind, rel, data):
        p = os.path.join(state, kind, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
        return os.path.abspath(p)

    def merged_before(rel):
        return done.get(rel) == [key_of(rel, read_bytes(fb[rel])), key_of(rel, read_bytes(fa[rel]))]

    for r in sorted(fa):
        if any(r.startswith(d) for d in DIST_PLUGINS):
            continue
        lay = layer(r)
        if lay == "코어":
            if r not in fb:
                ops.append({"op": "put", "rel": r, "src": os.path.abspath(fa[r]), "why": WHY_NEW})
            elif sha(fa[r]) == sha(fb[r]):
                continue
            elif r == KNOWN_REL or sha(fb[r]) in known.get(r, {}):
                ops.append({"op": "put", "rel": r, "src": os.path.abspath(fa[r]), "why": WHY_REPLACE})
            elif r in KEEP_IF_MODIFIED:
                kept.append(r)
            elif not merged_before(r):
                mine, new = body(r, read_bytes(fb[r])), read_bytes(fa[r])
                out, why = merge3(A, r, mine, body(r, new), known.get(r))
                if out is None:
                    conflicts.append({"rel": r, "new": stash("충돌", r, new), "why": why})
                elif out != mine:
                    ops.append({"op": "put", "rel": r, "src": stash("합본", r, out), "why": WHY_MERGED})
                    done[r] = [key_of(r, out), key_of(r, new)]
        elif lay == L_CLAUDE:
            merged = merge_claude(fa[r], fb.get(r))
            if merged is None:
                notes.append("%s §0 을 한쪽에서 못 찾음 — 넣지 않음(손으로)" % L_CLAUDE)
                continue
            why = WHY_NEW
            if r in fb:
                why = WHY_REPLACE
                mine, new = body(r, read_bytes(fb[r])), body(r, read_bytes(fa[r]))
                if merged_before(r):
                    continue
                if mine != new and key_of(r, mine) not in known.get(r, {}):     # §0 밖을 사용자가 고쳤다
                    out, wh = merge3(A, r, mine, new, known.get(r))
                    if out is None:
                        conflicts.append({"rel": r, "new": stash("충돌", r, merged.encode("utf-8")), "why": wh})
                        continue
                    s0 = RX_S0.search(read_bytes(fb[r]).replace(b"\r\n", b"\n").decode("utf-8")).group(0)
                    merged, why = out.decode("utf-8").replace(S0_MARK, s0, 1), WHY_MERGED
                    done[r] = [key_of(r, out), key_of(r, new)]
            cur = None
            if r in fb:
                with open(fb[r], encoding="utf-8") as f:
                    cur = f.read()
            if cur != merged:
                out = os.path.join(state, L_CLAUDE.replace(".md", ".merged.md"))
                write_text(out, merged)
                ops.append({"op": "put", "rel": r, "src": os.path.abspath(out), "why": why})
        elif lay == "씨앗" and r not in fb and os.path.dirname(r) in (KNOWLEDGE, "3_시스템"):  # mf:allow-path
            ops.append({"op": "put", "rel": r, "src": os.path.abspath(fa[r]), "why": WHY_SEED})
        elif lay in ("씨앗", "미분류") and (r not in fb or sha(fa[r]) != sha(fb[r])):
            notes.append("%s 층이라 넣지 않음: %s" % (lay, r))
    for r, vers in sorted(known.items()):
        if r not in fa and r in fb:
            if sha(fb[r]) in vers:
                ops.append({"op": "remove", "rel": r, "why": WHY_REMOVED})
            else:
                kept.append(r + " (배포판이 뺐지만 사용자가 고쳤다)")
    write_text(done_p, json.dumps(done, ensure_ascii=False, indent=1) + "\n")
    return dict(head, ops=ops, notes=notes, conflicts=conflicts, kept=kept)


def write_text(path, text):
    # ④ 쓰기는 encoding 명시 + newline="\n" 고정
    #    (CRLF churn 방지 — incident-2026-07-04-writer-crlf-eol-churn)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser(description="두 볼트의 코어 괴리를 층별로 진단하고 업데이트 계획을 낸다")
    ap.add_argument("--a", help="원본 볼트 경로(가져올 쪽)")
    ap.add_argument("--b", help="대상 볼트 경로(받을 쪽)")
    ap.add_argument("--mode", choices=["update", "publish"])
    ap.add_argument("--out", help="리포트 저장 경로(생략 시 stdout)")
    ap.add_argument("--apply-plugins", action="store_true",
                    help="배포 플러그인 교체를 실행한다(update 리포트의 계획을 승인한 뒤에만)")
    ap.add_argument("--plan-out", help="(update) 업데이트 계획 JSON 저장 경로 — 실행은 배포판의 fileops.py update 가 한다")
    ap.add_argument("--build-known", metavar="배포판", help="(publish) 배포판 이력에서 판 해시 표를 만든다")
    a = ap.parse_args()
    if a.build_known:
        n_paths, n_vers = build_known(os.path.abspath(a.build_known))
        print("판 해시 표: 경로 %d · 판 %d" % (n_paths, n_vers))
        return 0
    if not (a.a and a.b):
        ap.error("--a 와 --b 가 필요하다")
    if not (a.mode or a.apply_plugins):
        ap.error("--mode 또는 --apply-plugins 가 필요하다")

    for p in (a.a, a.b):
        if not os.path.isdir(p):
            print("경로 없음: %s" % p, file=sys.stderr)
            return 2

    if a.apply_plugins:
        if obsidian_running():
            print("옵시디언이 켜져 있다 — 닫고 다시 돌린다(켜 둔 옵시디언은 플러그인 목록을 자기 기억으로 다시 쓴다).",
                  file=sys.stderr)
            return 3
        log, ok = plugins(os.path.abspath(a.a), os.path.abspath(a.b), dry=False)
        for x in log:
            print("%s %s" % x)
        return 0 if ok else 1

    plan = update_plan(os.path.abspath(a.a), os.path.abspath(a.b)) if a.mode == "update" else None
    text, (n_add, n_chg, n_del) = report(os.path.abspath(a.a), os.path.abspath(a.b), a.mode, plan)

    # ⑤ 실측 게이트 — "산출물 존재 ≠ 완료". 괴리 0이면 그렇다고 자백한다.
    if n_add + n_chg + n_del == 0:
        print("괴리 0 — 두 볼트의 코어가 같다.", file=sys.stderr)

    if a.out:
        write_text(a.out, text)
        print("작성: %s (새 %d · 다름 %d · 대상에만 %d)" % (a.out, n_add, n_chg, n_del))
    else:
        print(text)
    if a.plan_out:
        if a.mode != "update":
            print("--plan-out 은 --mode update 에서만", file=sys.stderr)
            return 2
        if plan.get("error"):
            print(plan["error"], file=sys.stderr)
            return 2
        write_text(a.plan_out, json.dumps(plan, ensure_ascii=False, indent=1) + "\n")
        print("계획: %s (바꾸기·넣기·빼기 %d · 못 합침 %d · 사용자 판 남김 %d · 손으로 %d · 배포판 %s)"
              % (a.plan_out, len(plan["ops"]), len(plan["conflicts"]), len(plan["kept"]), len(plan["notes"]), plan["version"] or "?"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
