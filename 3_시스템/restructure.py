# -*- coding: utf-8 -*-
"""**restructure** — 볼트 개혁 R9 구조 이전: 분류표 초안 → (사람이 고침) → 이전 파일 → 적용·점검 (2026-10-30).

왜: 지금 층 안은 «notes 뿌리 노트 + 과목 폴더 + sessions + decisions» 로 흩어져 한 과목이 꼭대기 4곳에 있다
(설계안 §1·§8). 층 × 영역 × 주제(§1.1)로 옮기되 «무엇을 어디로»는 대본이 초안을 내고 사람이 고친다(§1.3).
옮기기는 fileops 계획(링크 고침·장부·되돌리기)으로만, 자리 이름은 roles.json 새 판으로만 바꾼다(R6 — 코드는 역할을 묻는다).

  py -3 3_시스템/restructure.py classify [--out <분류표.md>]           분류표 초안(md 표 — «새 자리» 칸을 고친다 · `그대로` = 안 옮김)
  py -3 3_시스템/restructure.py plan <분류표.md> [--out <이전.json>]     분류표 → 이전 파일(fileops 계획 꼴 + roles 새 판 + 설정 고침)
  py -3 3_시스템/restructure.py apply <이전.json> --yes                 적용 = fileops 계획 → roles.json → 설정 → 빈 폴더 정리
  py -3 3_시스템/restructure.py check [--save <json>] [--compare <json>]  못 찾는 링크·박힌 경로·세션 시작 훅·일정·주제 카드·건강

`apply` 는 이 대본이 든 볼트에 한다(사본 시험 = 사본의 3_시스템/restructure.py 를 부름). 본 볼트 적용은 사람이 분류표를
검토하고 백업 위치를 정한 뒤에만(로드맵 R9 · 사용자 몫). 되돌리기 = `fileops undo <묶음 id>` + `git checkout 3_시스템/roles.json`.
원본 층(1_수집)은 따로 표를 낸다(`classify --sources` — `1_수집/학교` → `1_수집/배움` · 별칭 폴더 → 정식 이름 · 색인·수집 상태가 함께 움직임 · 10-31 승인).
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import roles  # noqa: E402

PY = sys.executable
OUT_DIR = "3_시스템/_index/restructure"
# 영역(설계안 §19.2 · 10-31 사용자 확정) — 세 층 공통 둘째 단 · 2_지식에만 기록 · «노트» 같은 남는 칸 없음(못 가르면 사람이 고름)
AREAS = ["배움", "일", "생활", "분야"]
OLD_AREA = {"학교": "배움", "프로젝트": "일"}                       # 10-31 전 등록부 값
AREA_ROLE = {"배움": "learn_notes", "일": "doing_notes", "생활": "life_notes", "분야": "field_notes"}
NEW = {"sessions": "2_지식/기록", "fields": "2_지식/분야"}
PICK = "고를 것"                                                  # 분류표 «새 자리» — plan 이 멈추고 사람이 고르게
# ADR 은 모두 외부뇌 결정 — 등록부와 무관하게 고정(배포판 볼트엔 «외부뇌» 주제가 없을 수 있다)
DECISIONS_DIR = "2_지식/일/외부뇌/결정"
# 태그 → 주제(첫째는 주제 이름·별칭이 먼저 맞춘다 — 여기는 이름이 아닌 낱말만) · 등록부에 없는 주제면 건너뜀
TAG_TOPIC = {"여행": "여행", "돈": "돈", "재무": "돈", "주식": "돈", "투자": "돈", "운동": "건강", "건강": "건강",
             "미술": "취미", "전시": "취미", "과외": "부업", "수익": "부업", "원격근무": "부업", "프리랜서": "부업",
             "LLM": "컴퓨터·AI", "통찰": "사고·방법", "메타패턴": "사고·방법", "메타": "사고·방법", "학습": "사고·방법",
             "인지과학": "사고·방법", "리서치": "사고·방법"}
TAG_AREA = {"공부": "배움", "학업": "배움"}       # 여러 주제에 걸친 것 → 영역 바로 아래
FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`")
WIKI = re.compile(r"!?\[\[([^\[\]|#\n]+)")
SKIP = {".git", ".obsidian", ".trash", "node_modules", "__pycache__"}
# conventions «핵심파일 이동 금지»(MOC·recent·open-loops·설계노트·사용자설명서) 가운데 notes 안에 있는 둘 — 폴더 이름만 따라간다
CORE_DOCS = {"설계노트", "사용자설명서"}
# 볼트 경로를 정답·값으로 든 데이터 — 링크가 아니라 fileops 가 못 고친다(10-30 사본 시험: 골든셋 30줄)
DATA_REWRITE = ["3_시스템/_eval/golden.jsonl", "3_시스템/_eval/golden-paraphrase.jsonl"]
# 원본 층을 옮길 때만: 수집 상태(항목 경로가 윈도 꼴 역슬래시) · 보관 칸 거울(web-collect ARCH)
COLLECT_STATE = "3_시스템/_index/collect"
COLLECT_ARCH = COLLECT_STATE + "/archive"


def rel(a):
    return os.path.relpath(a, VAULT).replace("\\", "/")


def absv(r):
    return os.path.join(VAULT, *r.split("/"))


def fm(path):
    """프론트매터의 tags 목록(한 줄 [..] 꼴만 — 이 볼트 규약)."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            head = f.read(3000)
    except OSError:
        return []
    m = re.match(r"---\s*\n(.*?)\n---", head, re.S)
    if not m:
        return []
    t = re.search(r"^tags:\s*\[(.*?)\]", m.group(1), re.M)
    return [x.strip().strip("\"'") for x in t.group(1).split(",")] if t else []


def module_ids():
    d = os.path.join(VAULT, ".claude", "skills")
    return sorted(x for x in os.listdir(d) if os.path.isfile(os.path.join(d, x, "module.json"))) if os.path.isdir(d) else []


def names_longest():
    """(글자, 정식 이름) — 정식 이름·별칭, 긴 것부터(앞머리 맞추기에서 짧은 별칭이 먼저 먹지 않게)."""
    out = []
    for t in roles.topics():
        for n in [t["이름"]] + list(t.get("별칭") or []):
            out.append((n, t["이름"]))
    return sorted(out, key=lambda x: -len(x[0]))


def topic_dir(layer, name):
    """주제의 새 자리 — layer = '2_지식' · '0_작업' · 등록부 영역을 모르면 None(사람이 고름)."""
    t = next((x for x in roles.topics() if x["이름"] == name), None)
    area = (t or {}).get("영역") or ""
    area = OLD_AREA.get(area, area)
    return "%s/%s/%s" % (layer, area, name) if area in AREAS else None


def guess_note(base, tags, mods, names):
    """뿌리 노트 하나 → (새 자리 폴더, 까닭, 확신)."""
    low = base.lower()
    for n, c in names:                                     # ① 이름 앞머리 = 주제(물성전자-… · 디사경 … · brain-…)
        nl = n.lower()
        if low == nl or (low.startswith(nl) and low[len(nl)] in "-_ "):
            return topic_dir("2_지식", c), "이름 앞머리 «%s»" % n, "높음"
    for g in tags:                                         # ② 태그가 주제 이름·별칭
        c = roles.canon(g)
        if c:
            return topic_dir("2_지식", c), "태그 «%s»" % g, "높음"
    for n, c in names:                                     # ③ 이름 안에 주제 이름(앞머리 아님)
        if len(n) >= 3 and n.lower() in low:
            return topic_dir("2_지식", c), "이름 안 «%s»" % n, "낮음"
    for m in mods + ["모듈"]:                              # ④ 이름에 모듈 이름(또는 «모듈») = 외부뇌 부품
        if m.lower() in low and topic_dir("2_지식", "외부뇌"):
            return topic_dir("2_지식", "외부뇌"), "이름에 모듈 «%s»" % m, "낮음"
    for g in tags:                                         # ⑤ 태그 낱말 → 생활·분야·일의 고정 주제
        d = TAG_TOPIC.get(g) and topic_dir("2_지식", TAG_TOPIC[g])
        if d:
            return d, "태그 «%s» → %s" % (g, TAG_TOPIC[g]), "보통"
    for g in tags:                                         # ⑥ 여러 주제에 걸친 것 → 영역 바로 아래
        if g in TAG_AREA:
            return "2_지식/" + TAG_AREA[g], "태그 «%s» → %s(여러 주제에 걸침)" % (g, TAG_AREA[g]), "보통"
    return PICK, "갈래 못 정함 — 사람이 고름(남는 칸 없음 · 설계안 §19.2)", "낮음"


def work_groups(folder):
    """0_작업/<주제> 바로 아래 낱파일 → 과제 폴더(§1.1 R4 «과제마다 폴더 하나»). 같은 머리 2개 이상만 묶는다."""
    a = absv(folder)
    files = [f for f in os.listdir(a) if os.path.isfile(os.path.join(a, f))]
    topic = posixpath_base(folder)
    pre = [n for n, c in names_longest() if c == roles.canon(topic)]
    heads = {}
    for f in files:
        stem = os.path.splitext(f)[0]
        for n in pre:                                      # «디지털사유와정치경제_중간과제» → «중간과제»
            if stem.lower().startswith(n.lower()) and len(stem) > len(n) and stem[len(n)] in "-_ ":
                stem = stem[len(n) + 1:]
                break
        heads[f] = re.split(r"[-_ ]", stem, maxsplit=1)[0]
    cnt = Counter(heads.values())
    dirs = {d for d in os.listdir(a) if os.path.isdir(os.path.join(a, d))}
    return {f: h for f, h in heads.items() if h and (cnt[h] >= 2 or h in dirs)}


def posixpath_base(r):
    return r.rstrip("/").rsplit("/", 1)[-1]


# ── 분류표 ──────────────────────────────────────────────────────────────

def classify_sources():
    """원본 층(따로 승인 — ADR-023 4 · 10-31 사용자 승인): 학교 원본 자리 → `1_수집/배움`(새 영역 이름) ·
    그 안 «별칭» 폴더 → 정식 이름(별칭 → 정식). 안쪽 줄의 «새 자리»는 바깥 폴더가 옮겨진 뒤 자리."""
    rows = []
    school = roles.path("school")
    new = roles.path("sources") + "/배움"
    if school != new:
        rows.append({"src": school, "dst": new, "kind": "dir", "sure": "높음",
                     "why": "원본 층 영역 = 배움(설계안 §19.2) · 수집 상태·보관 칸·색인·LMS 목록 함께"})
    for d in sorted(os.listdir(absv(school))):
        c = roles.canon(d)
        if os.path.isdir(absv(school + "/" + d)) and c and c != d:
            rows.append({"src": school + "/" + d, "dst": new + "/" + c, "kind": "dir", "sure": "높음",
                         "why": "원본 폴더 이름 = 주제 정식 이름(별칭 → %s) · 색인·수집 상태·보관 칸 함께" % c})
    return rows


def classify():
    rows = []
    add = lambda s, d, why, sure, kind="file": rows.append({"src": s, "dst": d, "why": why, "sure": sure, "kind": kind})
    names, mods = names_longest(), module_ids()
    notes = roles.path("notes")
    # 1. 2_지식/notes 아래 폴더 = 주제 폴더
    for d in sorted(os.listdir(absv(notes))):
        a = os.path.join(absv(notes), d)
        if not os.path.isdir(a):
            continue
        c = roles.canon(d)
        if c and topic_dir("2_지식", c):
            add(notes + "/" + d, topic_dir("2_지식", c), "주제 폴더(%s)" % ("정식 이름" if c == d else "별칭 → " + c), "높음", "dir")
        else:
            add(notes + "/" + d, PICK, "주제 등록부에 없는 폴더(또는 영역 모름) — 사람이 고름", "낮음", "dir")
    # 2. 2_지식/notes 뿌리 노트
    for f in sorted(os.listdir(absv(notes))):
        a = os.path.join(absv(notes), f)
        if not os.path.isfile(a):
            continue
        if f.startswith("."):                              # .gitkeep 같은 자리 표시 — notes 역할의 새 자리로
            add(notes + "/" + f, NEW["fields"] + "/" + f, "자리 표시 파일", "높음")
            continue
        base = os.path.splitext(f)[0]
        if base in CORE_DOCS and topic_dir("2_지식", "외부뇌"):
            add(notes + "/" + f, topic_dir("2_지식", "외부뇌") + "/" + f,
                "핵심 파일 — 이름으로 찾음(ADR-021) → 외부뇌 주제(conventions «이동 금지» 문구는 코어 승인으로 고침)", "높음")
            continue
        d, why, sure = guess_note(base, fm(a) if f.endswith(".md") else [], mods, names)
        add(notes + "/" + f, PICK if d == PICK else d + "/" + f, why, sure)
    # 3. 기록·결정·캔버스
    add(roles.path("sessions"), NEW["sessions"], "세션 노트 = 기록(§1.3)", "높음", "dir")
    add(roles.path("decisions"), DECISIONS_DIR, "ADR = 외부뇌 결정(§1.3 · §11 3)", "보통", "dir")
    cv = roles.path("canvas")
    if os.path.isdir(absv(cv)):
        for f in sorted(os.listdir(absv(cv))):
            stem = f.split(".")[0]
            d, why, sure = guess_note(stem, [], mods, names)
            add(cv + "/" + f, PICK if d == PICK else d + "/" + f, "캔버스는 주제 폴더로(§1.3) · " + why, sure)
    # 4. 0_작업/<주제> → 0_작업/<영역>/<주제> · 낱파일은 과제 폴더로
    work = roles.path("work")
    for d in sorted(os.listdir(absv(work))):
        a = os.path.join(absv(work), d)
        if not os.path.isdir(a) or d in AREAS:
            continue
        c = roles.canon(d)
        new = c and topic_dir("0_작업", c)
        if not new:
            add(work + "/" + d, PICK, "주제 등록부에 없는 작업 폴더 — 사람이 고름", "낮음", "dir")
            continue
        add(work + "/" + d, new, "작업 폴더 → 영역 아래(§1.3 · §11 2)", "높음", "dir")
        for f, h in sorted(work_groups(work + "/" + d).items()):
            add(work + "/" + d + "/" + f, new + "/" + h + "/" + f, "과제마다 폴더(§1.1 R4) · 머리 «%s»" % h, "보통")
    return rows


def table_md(rows, sources=False):
    today = dt.date.today().isoformat()
    by = Counter(r["dst"].rsplit("/", 1)[0] if r["kind"] == "file" else r["dst"] for r in rows if r["dst"] != r["src"])
    low = sum(1 for r in rows if r["sure"] == "낮음")
    if sources:
        L = ["# R9-b 원본 층 이전 표 (%s · `restructure.py classify --sources`)" % today, "",
             "> 원본 층(1_수집) 폴더 이름을 주제 정식 이름으로. CLAUDE.md §2 원본 규칙(시스템이 하는 일 넷) 밖의 이동이라 **" + roles.me() + " 승인으로만** 한다. "
             "함께 바뀌는 것 = 원본을 가리키는 링크 · 역할(`school_notice`) · 수집 상태 항목 경로 · 수집 보관 칸 거울 · 색인(해시로 다시 이음). "
             "근거 = [[ADR-023-구조이전-restructure-분류표-역할묶음-원본층제외]] 4.", "",
             "| # | 지금 | 새 자리 | 까닭 | 확신 |", "|---|---|---|---|---|"]
        for i, r in enumerate(rows, 1):
            L.append("| %d | `%s/` | `%s/` | %s | %s |" % (i, r["src"], r["dst"], r["why"], r["sure"]))
        return "\n".join(L) + "\n"
    L = ["# R9 분류표 초안 (%s · `restructure.py classify`)" % today, "",
         "> 볼트 개혁 R9 구조 이전 — **무엇을 어디로**. 대본이 초안을 냈다. «새 자리» 칸을 고치면 된다(`그대로` = 안 옮김). "
         "다 고친 뒤 Claude 에게 «분류표 확정»이라고 하면 `restructure.py plan` → 사본 시험 → 본 볼트 적용(백업 뒤). "
         "근거 = [[외부뇌-볼트개혁-설계안]] §1 · [[외부뇌-볼트개혁-로드맵]] R9.", "",
         "## 정해진 것 (10-31 사용자 · 설계안 §19.2)",
         "1. 영역 = `배움`·`일`·`생활`·`분야`(세 층 공통) + 2_지식의 `기록`(세션 노트) · «노트» 같은 남는 칸 없음 — 못 가른 줄은 «새 자리»가 `%s`(먼저 볼 것)." % PICK,
         "2. 0_작업도 영역 아래(`0_작업/배움/<과목>/<과제>/`) · 학교·학기는 주제 등록부 속성(폴더 단 아님).",
         "3. `sessions` → `기록` · `decisions` → `2_지식/일/외부뇌/결정` · modules 는 그대로(ADR-005).",
         "4. 원본 층(`1_수집/학교` → `1_수집/배움` · 별칭 폴더 → 정식 이름)은 같은 체계로 옮기기로 승인 — 표는 따로(`R9b-원본-이전표.md`).",
         "5. 백업 = `C:/백업/Claude_Brain-<날짜>`(적용 직전 1회).", "",
         "## 적용 때 함께 (Claude)",
         "- 대본이 함께: 링크 · `roles.json` 새 판 · 옵시디언 그래프 색 묶음 · 찾기 골든셋 정답 경로 · 빈 옛 폴더.",
         "- 글로 고칠 것: conventions(«notes/·decisions/» 문장 → 역할 묶음) · 기억(작업 자리 `0_작업/<과목>` → `0_작업/학교/<과목>` 등) · 찾기 색인 다시.",
         "- " + roles.me() + ": `.claude/settings.local.json` 허용 규칙 글자 3곳(게이트 자신 — 토큰으로도 못 고침) · 옵시디언 화면.", "",
         "## 요약",
         "- 줄 %d · 확신 낮음 %d(먼저 볼 것) · 새 자리 폴더 %d" % (len(rows), low, len(by)), "",
         "## 표", "",
         "| # | 지금 | 새 자리 | 까닭 | 확신 |", "|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        tail = "/" if r["kind"] == "dir" else ""
        dst = "`그대로`" if r["dst"] == r["src"] else "`%s%s`" % (r["dst"], tail)
        L.append("| %d | `%s%s` | %s | %s | %s |" % (i, r["src"], tail, dst, r["why"], r["sure"]))
    return "\n".join(L) + "\n"


def parse_table(path):
    rows = []
    for line in open(path, encoding="utf-8-sig"):
        m = re.match(r"\|\s*\d+\s*\|\s*`([^`]+)`\s*\|\s*(.+?)\s*\|", line)
        if not m:
            continue
        src, dst = m.group(1), m.group(2).strip().strip("`").strip()
        kind = "dir" if src.endswith("/") else "file"
        src = src.rstrip("/")
        dst = src if dst in ("그대로", "") else dst.rstrip("/")
        rows.append({"src": src, "dst": dst, "kind": kind})
    return rows


# ── 이전 파일 ───────────────────────────────────────────────────────────

def next_roles(cur):
    """R9 뒤 roles.json — 자리만 바꾼다(역할 이름·묶음 이름은 그대로 · 코드가 묻는 이름이 같게)."""
    r = json.loads(json.dumps(cur))
    R = r["roles"]
    R["notes"] = NEW["fields"]                               # 주제 모를 때 기본 자리(옛 notes 역할을 묻던 코드용) — 남는 칸이 아니라 «분야»
    R["sessions"] = NEW["sessions"]
    R["decisions"] = DECISIONS_DIR
    R["canvas"] = NEW["fields"]                              # 주제 없는 새 캔버스 자리(주제 것은 주제 폴더에)
    for k in ("school_notes", "project_notes"):              # 10-30 R9 준비의 옛 영역 역할 이름
        R.pop(k, None)
    for a, k in AREA_ROLE.items():
        R[k] = "2_지식/" + a
    areas = list(AREA_ROLE.values())                         # notes(= 분야)는 field_notes 와 같은 자리 — 두 번 넣지 않는다
    G = r["groups"]
    G["note_areas"] = areas
    G["moc_notes"] = areas + ["modules"]                      # decisions 는 doing_notes 안 — 두 번 넣으면 두 번 훑는다
    G["knowledge_notes"] = areas + ["sessions", "modules"]
    G["content"] = areas + ["sessions", "modules"]
    r["topic_roots"] = [cur["roles"]["school"]] + ["%s/%s" % (L, a) for L in ("1_수집", "0_작업", "2_지식") for a in AREAS
                                                   if not (L == "1_수집" and a == "배움")]
    r["_topic_roots"] = "이 자리 바로 아래 폴더 이름 = 주제(정식 이름 또는 별칭 · 설계안 §19.2 · R9 이전 뒤 · 원본 학교 자리는 R9-b 가 배움으로)"
    return r


def plan(table, out):
    rows = parse_table(table)
    pick = [r["src"] for r in rows if r["dst"] == PICK]
    if pick:
        print("분류표에 «%s» %d줄 — 새 자리를 정한 뒤 다시(설계안 §19.2 · 남는 칸 없음)" % (PICK, len(pick)))
        for x in pick[:20]:
            print("  " + x)
        return 1
    moves = [r for r in rows if r["dst"] != r["src"]]
    # fileops 는 원본 옆 `<이름>.md`·`<이름> (<확장자>).md` 를 짝 메모로 함께 옮긴다 — 그 줄을 따로 두면 «없음»으로 멈춘다
    # (10-30 사본 시험: 0_작업 의 `1차발표-대본.docx` 가 `1차발표-대본.md` 를 데려감). 같은 자리로 가면 빼고, 다른 자리면 오류.
    lead = {}
    for r in moves:
        if r["kind"] == "file" and not r["src"].lower().endswith(".md"):
            s, e = os.path.splitext(r["src"])
            d = os.path.splitext(r["dst"])[0]
            lead[(s + ".md").lower()] = d + ".md"
            lead[("%s (%s).md" % (s, e[1:])).lower()] = "%s (%s).md" % (d, e[1:])
    follow = [r for r in moves if r["kind"] == "file" and r["src"].lower() in lead]
    clash = [r["src"] for r in follow if r["dst"].lower() != lead[r["src"].lower()].lower()]
    moves = [r for r in moves if r not in follow]
    dirs = [r for r in moves if r["kind"] == "dir"]
    files = [r for r in moves if r["kind"] == "file"]
    if clash:
        print("분류표 오류 — 짝 메모가 원본과 다른 자리로 감 %d(원본을 따라가게 고칠 것)" % len(clash))
        for x in clash[:10]:
            print("  " + x)
        return 1
    errs = [r["src"] for r in moves if not os.path.exists(absv(r["src"]))]
    dup = [d for d, n in Counter(r["dst"].lower() for r in moves).items() if n > 1]
    if errs or dup:
        print("분류표 오류 — 없는 것 %d · 새 자리 겹침 %d" % (len(errs), len(dup)))
        for x in errs[:10] + dup[:10]:
            print("  " + x)
        return 1

    def after_dirs(p, among=None):
        """폴더를 먼저 옮기므로 그 안 것의 «지금» 은 폴더가 옮겨진 뒤 자리로 읽는다(안쪽 폴더 줄도 — 1_수집/학교 → 배움 안의 별칭 폴더)."""
        for d in sorted(among if among is not None else dirs, key=lambda x: -len(x["src"])):
            if p.lower().startswith(d["src"].lower() + "/"):
                return d["dst"] + p[len(d["src"]):]
        return p

    dirs.sort(key=lambda x: len(x["src"]))                   # 바깥 폴더 먼저
    ops = [{"op": "mv", "src": after_dirs(d["src"], dirs[:i]), "dst": d["dst"], "why": "R9 구조 이전 — 폴더"} for i, d in enumerate(dirs)]
    ops += [{"op": "mv", "src": after_dirs(f["src"]), "dst": f["dst"], "why": "R9 구조 이전"} for f in files]
    cur = roles.config()
    src_root = roles.path("sources") + "/"
    smoves = [r for r in moves if r["src"].startswith(src_root)]      # 원본 층(따로 승인 — ADR-023 4)
    kmoves = [r for r in moves if not r["src"].startswith(src_root)]
    settings, emptied, data = [], [], list(DATA_REWRITE)
    if kmoves:
        nr = next_roles(cur)
        old_notes = cur["roles"]["notes"]
        q = " OR ".join("path:" + nr["roles"][a] for a in nr["groups"]["note_areas"])
        settings = [{"file": ".obsidian/graph.json", "old": "path:" + old_notes, "new": "(" + q + ")"},
                    {"file": ".obsidian/graph.json", "old": "path:" + cur["roles"]["sessions"], "new": "path:" + nr["roles"]["sessions"]}]
        emptied = sorted({cur["roles"]["notes"], cur["roles"]["canvas"]} |
                         {d["src"].rsplit("/", 1)[0] for d in dirs if d in kmoves} - {roles.path("knowledge"), roles.path("work")})
    else:
        nr = json.loads(json.dumps(cur))
    sdirs = sorted((r for r in smoves if r["kind"] == "dir"), key=lambda x: len(x["src"]))

    def remap(v):
        """원본 자리를 가리키는 값(역할·주제 자리) — 가장 안쪽으로 맞는 줄을 따라간다."""
        for r in sorted(smoves, key=lambda x: -len(x["src"])):
            if v == r["src"] or v.startswith(r["src"] + "/"):
                return r["dst"] + v[len(r["src"]):]
        return v
    nr["roles"] = {k: remap(v) for k, v in nr["roles"].items()}
    nr["topic_roots"] = list(dict.fromkeys(remap(v) for v in nr.get("topic_roots", [])))
    for i, r in enumerate(sdirs):
        # 수집 보관 칸은 볼트와 같은 상대 경로의 거울 — 함께 옮겨야 되살리기가 새 자리로 간다
        if os.path.isdir(absv(COLLECT_ARCH + "/" + r["src"])):
            ops.append({"op": "mv", "src": COLLECT_ARCH + "/" + after_dirs(r["src"], sdirs[:i]), "dst": COLLECT_ARCH + "/" + r["dst"],
                        "why": "R9 원본 층 이전 — 수집 보관 칸 거울"})
    # 원본 색인(_색인)도 원본과 같은 상대 경로의 거울 — 노트가 색인을 전체 경로로 잇는다(노트 → `_색인/학교/…pdf.색인`).
    # 해시로 다시 만들기만 하면 그 링크가 안 고쳐진다(10-31 사본 시험 9개) → fileops 로 거울째 옮겨 링크를 고친다
    idx = roles.path("source_index")
    mir = [{"src": idx + "/" + r["src"][len(src_root):], "dst": idx + "/" + r["dst"][len(src_root):]} for r in sdirs]
    for i, m in enumerate(mir):
        if os.path.isdir(absv(m["src"])):
            ops.append({"op": "mv", "src": after_dirs(m["src"], mir[:i]), "dst": m["dst"], "why": "R9 원본 층 이전 — 원본 색인 거울(링크 고침)"})
    # 수집 보관 칸 안에도 색인 거울이 있다(되살리기가 원본 자리에서 색인 자리를 계산 — web-collect arch_paths · 10-31 본 볼트에서 빠뜨려 손으로 옮김)
    for i, m in enumerate(mir):
        if os.path.isdir(absv(COLLECT_ARCH + "/" + m["src"])):
            ops.append({"op": "mv", "src": COLLECT_ARCH + "/" + after_dirs(m["src"], mir[:i]), "dst": COLLECT_ARCH + "/" + m["dst"],
                        "why": "R9 원본 층 이전 — 수집 보관 칸 안 색인 거울"})
    if smoves:
        data += sorted(rel(x) for x in glob.glob(absv(COLLECT_STATE) + "/*.json")) + ["3_시스템/_index/lms/manifest.json"]  # LMS 목록 경로 — 10-31 R9 때 빠뜨려 옛 자리로 남았다(11-03 고침)
    # 옛 경로 → 새 경로(긴 것부터) — 경로를 글자로 든 데이터(찾기 골든셋 정답 칸 · 수집 상태 등)를 같은 표로 고친다
    pmap = sorted({(r["src"], r["dst"]) for r in moves} | {(r["src"], r["dst"]) for r in follow}, key=lambda x: -len(x[0]))
    p = {"title": "R9 구조 이전 (%s)" % dt.date.today().isoformat(), "table": rel(os.path.abspath(table)),
         "ops": ops, "roles": nr, "settings": settings, "rmdir_if_empty": emptied,
         "path_map": [list(x) for x in pmap], "data_rewrite": data,
         "ingest": [r["dst"] for r in smoves]}                         # 원본 색인(_색인)은 해시로 다시 잇는다
    out = out or OUT_DIR + "/이전-%s.json" % dt.date.today().isoformat()
    os.makedirs(os.path.dirname(absv(out)), exist_ok=True)
    with open(absv(out), "w", encoding="utf-8", newline="") as f:
        json.dump(p, f, ensure_ascii=False, indent=1)
    print("이전 파일 %s · 옮김 %d(폴더 %d · 파일 %d · 짝 메모로 따라감 %d) · roles 새 판 · 설정 %d · 빈 폴더 정리 후보 %d" %
          (out, len(ops), len(dirs), len(files), len(follow), len(settings), len(emptied)))
    print("미리 보기 = py -3 3_시스템/fileops.py plan %s · 적용 = restructure.py apply %s --yes" % (out, out))
    return 0


def obsidian_has_vault():
    """옵시디언이 떠 있고 설정(obsidian.json)에 이 볼트가 «열림»인가 — 앱을 띄우지 않는다(«열림»은 앱을 닫아도 남아 둘 다 본다)."""
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/NH"], capture_output=True, timeout=10).stdout
        if b"Obsidian.exe" not in out:
            return False
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        cfg = json.load(open(os.path.join(os.environ.get("APPDATA", ""), "obsidian", "obsidian.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return False
    me = os.path.normcase(os.path.abspath(VAULT))
    return any(v.get("open") and os.path.normcase(os.path.abspath(v.get("path", ""))) == me for v in cfg.get("vaults", {}).values())


def apply(path, yes, allow_open=False, after_moves=False):
    """after_moves = 옮기기는 끝났는데 그 뒤에서 멈췄을 때 2~6 단계만(10-31 본 볼트: 장부 보기 파일 쓰기가 잠깐 잠겨 fileops 가 1 로 끝남)."""
    if not yes:
        print("적용은 --yes 로만(본 볼트는 분류표 검토·백업 뒤 — 로드맵 R9)")
        return 2
    p = json.load(open(absv(path) if not os.path.isabs(path) else path, encoding="utf-8"))
    if obsidian_has_vault() and not allow_open:
        print("옵시디언이 이 볼트를 열고 있다 — 닫고 다시(사본 시험과 같은 조건 · 파일 이동이 옵시디언 CLI 와 섞이지 않게). "
              "그대로 하려면 --allow-open")
        return 2
    # 늘 자체 엔진 — 사본 시험(10-30)이 잰 길. 옵시디언 CLI 는 파일만 옮겨 폴더 이동과 섞이면 시험 밖이 된다.
    env = dict(os.environ, FILEOPS_NO_OBSIDIAN="1")
    left = [o["dst"] for o in p["ops"] if not os.path.exists(absv(o["dst"]))]
    if after_moves and left:
        print("--after-moves 인데 아직 안 옮겨진 것 %d — 멈춤: %s" % (len(left), " · ".join(left[:5])))
        return 1
    # 1. 옮기기 — fileops 계획(링크·장부·되돌리기). 계획 파일은 ops 만 읽는다.
    tmp = absv(OUT_DIR + "/_apply-ops.json")
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump({"title": p["title"], "ops": p["ops"]}, f, ensure_ascii=False)
    r = subprocess.run([PY, os.path.join(HERE, "fileops.py"), "--by", "script:restructure", "plan", tmp, "--apply"] if not after_moves else [PY, "-c", "pass"],
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    lines = (r.stdout + r.stderr).splitlines()
    warn = [x for x in lines if "⚠" in x]
    print("옮기기: 코드 %d · 출력 %d줄 · 경고 %d" % (r.returncode, len(lines), len(warn)))
    for x in warn[:12]:
        print("  " + x.strip())
    if r.returncode:
        print("\n".join(lines[-8:]))
        print("멈춤 — roles.json·설정은 그대로. 되돌리기 = fileops log 의 묶음 id 로 undo")
        return r.returncode
    # 2. roles.json 새 판(코드·훅·플러그인이 묻는 자리)
    with open(os.path.join(HERE, "roles.json"), "w", encoding="utf-8", newline="") as f:
        json.dump(p["roles"], f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("roles.json 새 판")
    # 3. 옵시디언 설정의 글자(그래프 색 묶음 등)
    for s in p.get("settings", []):
        a = absv(s["file"])
        if not os.path.exists(a):
            continue
        t = open(a, encoding="utf-8").read()
        if s["old"] in t:
            open(a, "w", encoding="utf-8", newline="").write(t.replace(s["old"], s["new"]))
            print("설정 %s: %s → %s" % (s["file"], s["old"], s["new"]))
    # 4. 경로를 글자로 든 데이터 — 한 번에 바꾼다(긴 옛 경로부터 · 바뀐 글자를 다시 바꾸지 않게)
    #    경로 꼴 셋: `a/b` · 윈도 `a\b` · JSON 안 윈도 `a\\b`(수집 상태) — 같은 꼴로 바꾼다
    pm = {}
    for o, n in p.get("path_map", []):
        for sep in ("/", "\\", "\\\\"):
            pm[o.replace("/", sep)] = n.replace("/", sep)
    if pm:
        rx = re.compile("(%s)(?=[\"/\\\\])" % "|".join(re.escape(o) for o in sorted(pm, key=len, reverse=True)))
        for f in p.get("data_rewrite", []):
            a = absv(f)
            if not os.path.exists(a):
                continue
            t = open(a, encoding="utf-8").read()
            n = len(rx.findall(t))
            if n:
                open(a, "w", encoding="utf-8", newline="").write(rx.sub(lambda m: pm[m.group(1)], t))
                print("데이터 %s: 경로 %d곳" % (f, n))
    # 5. 비어 남은 옛 폴더 — 비었을 때만(내용이 있으면 손대지 않고 알림)
    for d in p.get("rmdir_if_empty", []):
        a = absv(d)
        if os.path.isdir(a):
            left = [x for x in os.listdir(a)]
            if left:
                print("  ⚠ 옛 폴더에 남은 것 %d: %s — %s" % (len(left), d, " · ".join(left[:5])))
            else:
                os.rmdir(a)
                print("빈 폴더 정리: %s" % d)
    # 6. 원본을 옮겼으면 색인(_색인)을 해시로 다시 잇는다(옛 자리 색인은 ingest 가 지움 · 그림 읽기는 다시 하지 않음)
    if p.get("ingest"):
        r = subprocess.run([PY, os.path.join(HERE, "ingest.py"), *p["ingest"]], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        print("색인 다시 잇기: 코드 %d · %s" % (r.returncode, ((r.stdout + r.stderr).strip().splitlines() or ["(출력 없음)"])[-1]))
    return 0


# ── 점검 ────────────────────────────────────────────────────────────────

def broken_links():
    """못 찾는 위키링크 목록(vault-baseline 과 같은 근사) → {(링크 든 파일 이름, 대상 이름)}."""
    files = []
    for dp, dns, fns in os.walk(VAULT):
        dns[:] = [d for d in dns if d not in SKIP]
        files += [rel(os.path.join(dp, f)) for f in fns]
    low = {f.lower() for f in files}
    noext = {f[:-3].lower() for f in files if f.lower().endswith(".md")}
    base = Counter()
    for f in files:
        b = f.rsplit("/", 1)[-1].lower()
        base[b] += 1
        if b.endswith(".md"):
            base[b[:-3]] += 1
    out = set()
    for f in files:
        if not f.endswith(".md") or f.startswith(("3_시스템/_index/", "1_수집/_색인/")):
            continue
        try:
            text = open(absv(f), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        text = INLINE.sub("", FENCE.sub("", text))
        d = f.rsplit("/", 1)[0] if "/" in f else ""
        for m in WIKI.finditer(text):
            t = m.group(1).strip().replace("\\", "/")
            if not t:
                continue
            tl = t.lower()
            if t.startswith(("./", "../")):
                j = os.path.normpath(os.path.join(d, t)).replace("\\", "/").lower()
                ok = j in low or j in noext
            elif "/" in t:
                ok = tl in low or tl in noext or any(x.endswith("/" + tl) or x.endswith("/" + tl + ".md") for x in low)
            else:
                ok = base.get(tl, 0) > 0
            if not ok:
                out.add((f.rsplit("/", 1)[-1], t.rsplit("/", 1)[-1]))
    return out


def run(args, timeout=120, ps=False):
    try:
        r = subprocess.run(args, capture_output=True, timeout=timeout, input=b"{}" if ps else None)
        return r.returncode, (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired) as e:
        return -1, str(e)


def check(save=None, compare=None):
    out = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "vault": VAULT}
    bl = broken_links()
    out["못찾는링크"] = sorted("%s → %s" % x for x in bl)
    c, t = run([PY, os.path.join(HERE, "_eval", "hardpaths.py"), "--json"])
    try:
        hp = json.loads(t)
        out["박힌경로"] = sum(r["moving"] for r in hp if not r.get("exempt"))
    except ValueError:
        out["박힌경로"] = "실패: " + t[-200:]
    c, t = run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.path.join(HERE, "hooks", "session-start.ps1")], ps=True)
    out["세션시작"] = {"code": c, "줄": len(t.splitlines()), "recent": "recent.md" in t, "일정": "일정 7일" in t,
                     "오류": [x for x in t.splitlines() if re.search(r"^(At |\+ )|CategoryInfo|FullyQualifiedErrorId|Traceback", x)][:3]}
    c, t = run([PY, os.path.join(HERE, "schedule.py"), "week", "7"])
    out["일정7일"] = {"code": c, "줄": len([x for x in t.splitlines() if x.startswith("- ")])}
    tops = {}
    for tp in roles.topics():
        c, t = run([PY, os.path.join(HERE, "topic.py"), "card", tp["이름"], "--json"])
        try:
            j = json.loads(t)
            tops[tp["이름"]] = {"자리": len(j["dirs"]), "노트": j["notes_total"], "작업": len(j["work"]), "원본": len(j["sources"])}
        except (ValueError, KeyError):
            tops[tp["이름"]] = "실패: " + t[-120:]
    out["주제카드"] = tops
    c, t = run([PY, os.path.join(HERE, "brain.py"), "doctor", "--json"])
    try:
        out["건강"] = {d["name"]: d["status"] for d in json.loads(t)}
    except ValueError:
        out["건강"] = "실패: " + t[-200:]
    print("못 찾는 링크 %d · 박힌 경로 %s · 세션 시작 code %s(%d줄 · recent %s · 일정 %s) · 일정 7일 %s줄" % (
        len(bl), out["박힌경로"], out["세션시작"]["code"], out["세션시작"]["줄"], out["세션시작"]["recent"],
        out["세션시작"]["일정"], out["일정7일"]["줄"]))
    for k, v in tops.items():
        print("  주제 %s: %s" % (k, v))
    if isinstance(out["건강"], dict):
        print("  건강: " + " · ".join("%s %s" % (k, v) for k, v in out["건강"].items()))
    if out["세션시작"]["오류"]:
        print("  ⚠ 세션 시작 출력에 오류 낱말: " + " | ".join(out["세션시작"]["오류"]))
    if compare:
        old = json.load(open(compare, encoding="utf-8"))
        new_b = sorted(set(out["못찾는링크"]) - set(old["못찾는링크"]))
        gone = sorted(set(old["못찾는링크"]) - set(out["못찾는링크"]))
        print("비교 — 못 찾는 링크 %d → %d · 새로 깨짐 %d · 나아짐 %d" % (len(old["못찾는링크"]), len(bl), len(new_b), len(gone)))
        for x in new_b[:20]:
            print("  + " + x)
        for k, v in tops.items():
            o = old["주제카드"].get(k)
            # 작업은 첫 단 항목 수라 낱파일을 과제 폴더로 묶으면 준다(잃은 것 아님) — 노트·원본만 경고
            if isinstance(v, dict) and isinstance(o, dict) and any(v[x] < o[x] for x in ("노트", "원본")):
                print("  ⚠ 주제 %s 줄어듦: %s → %s" % (k, o, v))
            elif isinstance(v, dict) and isinstance(o, dict) and v["작업"] < o["작업"]:
                print("  주제 %s 작업 첫 단 %d → %d(과제 폴더로 묶임)" % (k, o["작업"], v["작업"]))
        if isinstance(out["건강"], dict) and isinstance(old.get("건강"), dict):
            for k, v in out["건강"].items():
                if old["건강"].get(k) == "ok" and v != "ok":
                    print("  ⚠ 건강 %s: ok → %s" % (k, v))
        out["비교"] = {"새로깨짐": new_b, "나아짐": len(gone)}
    if save:
        with open(save, "w", encoding="utf-8", newline="") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="볼트 개혁 R9 구조 이전 — 분류표 · 이전 파일 · 적용 · 점검")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("classify")
    p.add_argument("--out")
    p.add_argument("--sources", action="store_true", help="원본 층(1_수집) 별칭 폴더만 — 따로 승인하는 표")
    p = sp.add_parser("plan")
    p.add_argument("table")
    p.add_argument("--out")
    p = sp.add_parser("apply")
    p.add_argument("plan")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--allow-open", action="store_true", help="옵시디언이 이 볼트를 열고 있어도(시험 안 한 길)")
    p.add_argument("--after-moves", action="store_true", help="옮기기는 끝났고 그 뒤에서 멈췄을 때 — roles·설정·데이터·빈 폴더·색인만")
    p = sp.add_parser("check")
    p.add_argument("--save")
    p.add_argument("--compare")
    a = ap.parse_args(argv)
    if a.cmd == "classify":
        rows = classify_sources() if a.sources else classify()
        md = table_md(rows, a.sources)
        if a.out:
            os.makedirs(os.path.dirname(absv(a.out)), exist_ok=True)
            with open(absv(a.out), "w", encoding="utf-8", newline="") as f:
                f.write(md)
            c = Counter(r["sure"] for r in rows)
            print("분류표 %s · %d줄 · 확신 높음 %d · 보통 %d · 낮음 %d" % (a.out, len(rows), c["높음"], c["보통"], c["낮음"]))
        else:
            print(md)
        return 0
    if a.cmd == "plan":
        return plan(a.table, a.out)
    if a.cmd == "apply":
        return apply(a.plan, a.yes, a.allow_open, a.after_moves)
    return check(a.save, a.compare)


if __name__ == "__main__":
    sys.exit(main())
