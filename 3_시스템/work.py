# -*- coding: utf-8 -*-
"""**work** — 작업 폴더(0_작업)의 작업마다 «끝났나 · 결과물이 보관됐나»를 판정하고, 끝난 것의 정리 계획을 낸다 (2026-10-31 · 11-02 보편화).

왜: 작업 폴더 원칙 = 진행 중인 것만 두고, 끝나면 승격(결과물 → 원본 층 `보냄/` · 앎 → 2_지식)하거나 지운다.
끝남을 사람 기억이 아니라 기록으로 판정한다. 10-31 판은 학교 과제만 상정했다(LMS 제출 · 제출 자리 · 실험 재료) —
11-02 사용자 «보편화» → 작업 하나 = «결과물이 어디로 나가 끝나는가»(설계안 §19.8). 끝남 근거는 `3_시스템/work.json` 의 표(데이터)를
위에서부터 본다 — 표시(작업.md 속성) · lms(내 제출) · git(가지 병합) · 일정(마감 지남) · 멈춤(묻기).
보낸 결과물이 원본 층 `<영역>/<주제>/보냄/`(학교 과목은 `제출/`)에도, 작업 안에도, 볼트 밖에도 없으면 «결과물 없음» —
지우는 계획을 내지 않는다(결과물을 보관하기 전엔 작업 파일을 지우지 않는다).

  py -3 3_시스템/work.py [--json]            작업마다 상태(읽기만)
  py -3 3_시스템/work.py plan [--json]       끝난 작업마다 정리 계획 → 3_시스템/_index/cleanup/작업-<날짜>-<작업>.json
                                             (승인한 것만 `fileops.py plan <계획> --apply`)
  py -3 3_시스템/work.py sweep               보냄·끝냄은 승인 없이 바로 비움(door.py sweep 이 볼트를 켤 때 부른다 · 휴지통·장부로 되돌림)
  py -3 3_시스템/work.py finish <작업 경로> [--by 누가]   사람이 체크한 작업을 바로 비움(홈 · 탐색기 우클릭) · 끝 줄 = JSON

정리 계획 꼴(끝난 작업 하나 · 규칙 = work.json):
  보낸 파일이 있는 보냄 → 결과물 → `보냄/`(밖에서 찾은 것은 들임) · 재료(사진·측정·회로) → `보냄/<작업>/` · md → 2_지식 ·
                          나머지(초안·다른 판 문서 · 다시 만들 수 있는 것) → 휴지통
  그 밖(끝냄·마감 지남·멈춤·저장소로 보냄) → 다시 만들 수 있는 것(대본·만든 그림·md 에서 내보낸 문서) → 휴지통 ·
                          나머지(md·그림·재료·md 원본 없는 문서) → `2_지식/<영역>/<주제>/<작업>/`(다시 못 만드는 것은 남긴다)
  보고서(학교 · work.json «보고서» · 사용자 11-03): 위와 같되 재료 = 휴지통(1회용) · docx = PDF 로 바꿔 PDF 만(이미 PDF 가 있으면 지우기만)
"""
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from urllib.parse import unquote_plus

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import roles  # noqa: E402

VAULT = os.path.dirname(HERE)
SUBMITTED = ("submitted", "graded", "pending_review")
OUTSIDE = [os.path.join(os.path.expanduser("~"), d) for d in ("Downloads", "Desktop")]  # 볼트 밖 후보(설계안 §11 11 · 10-31 허용)
MARK = "작업.md"  # 작업 폴더의 사람 표시(속성) — 탐색기 우클릭 «끝냄»이 적는다
DONE = ("보냄", "마감 지남", "끝냄")  # 끝남(멈춤은 «묻기»라 따로)
SURE = ("보냄", "끝냄")  # 근거가 확실한 끝남 = 저절로 비운다(sweep) · 마감 지남·멈춤은 아직 하는 중일 수 있어 후보로 남는다
# work.json 이 없거나 칸이 빠졌을 때(11-02 값)
RULES = {
    "근거": [{"id": "표시"}, {"id": "lms", "영역": ["배움"]}, {"id": "git"}, {"id": "일정"}, {"id": "멈춤"}],
    "보냄_자리": {"기본": "보냄", "종류": {"학교": "제출"}},
    "결과물_확장자": [".pdf", ".docx", ".doc", ".pptx", ".ppt", ".hwp", ".hwpx", ".xlsx", ".zip"],
    "재료_확장자": [".png", ".jpg", ".jpeg", ".heic", ".gif", ".bmp", ".webp", ".csv", ".xlsx", ".xls", ".tsv", ".dat", ".v", ".sv", ".vhd", ".vhdl"],
    "보고서": {"종류": ["학교"]},
    "다시_만듦": {"확장자": [".py", ".js", ".ts", ".mjs", ".ps1", ".sh", ".bat", ".ipynb", ".log", ".aux", ".pyc", ".tmp", ".bak"],
              "자리": ["fig", "out", "build", "__pycache__", "node_modules", ".ipynb_checkpoints"],
              "사진": [".jpg", ".jpeg", ".heic"], "내보냄": [".docx", ".pdf", ".html", ".pptx"], "제작_원본": [".typ", ".tex"]},
}
_RULES = None


def rules():
    global _RULES
    if _RULES is None:
        try:
            got = json.load(open(os.path.join(HERE, "work.json"), encoding="utf-8"))
        except (OSError, ValueError):
            got = {}
        _RULES = {k: got.get(k, v) for k, v in RULES.items()}
    return _RULES


def rel(a):
    return os.path.relpath(a, VAULT).replace("\\", "/")


def norm(s):
    """비교용 — 확장자·공백·기호 빼고 소문자(한글·영숫자만 · 한글은 NFC 로 모음)."""
    return re.sub(r"[^0-9a-z가-힣]", "", unicodedata.normalize("NFC", os.path.splitext(s)[0]).lower())


def same_name(a, b):
    """같은 파일로 볼 이름 — 확장자가 같고 정규화한 이름이 같거나 앞머리가 길게 같다(LMS 가 겹친 이름에 «-1»을 붙임 · 학번 오타)."""
    if os.path.splitext(a)[1].lower() != os.path.splitext(b)[1].lower():
        return False
    x, y = norm(a), norm(b)
    return bool(x and y) and (x == y or common(x, y) >= max(10, min(len(x), len(y)) - 6))


def common(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def files_of(p):
    if os.path.isfile(p):
        return [p]
    out = []
    for dp, dns, fns in os.walk(p):
        dns[:] = [d for d in dns if not d.startswith(".")]
        out += [os.path.join(dp, f) for f in fns if not f.startswith(".")]
    return out


def front(path):
    """md 첫 머리 속성(YAML 의 «키: 값» · «키: [a, b]» 만 — 꾸러미 없이)."""
    try:
        text = open(path, encoding="utf-8", errors="ignore").read()
    except OSError:
        return {}
    m = re.match(r"﻿?---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
    out = {}
    for ln in (m.group(1).splitlines() if m else []):
        k, sep, v = ln.partition(":")
        if not sep or ln[:1] in " \t-#":
            continue
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
        else:
            v = v.strip("\"'")
        out[k.strip()] = v
    return out


def meta(topic):
    return next((x for x in roles.topics() if x["이름"] == topic), {"이름": topic, "별칭": []})


def is_report(topic):
    """재료 = 1회용 · docx = PDF 만을 따르는 주제인가(work.json «보고서»)."""
    return meta(topic).get("종류") in rules()["보고서"]["종류"]


# ── 근거(work.json «근거» 표의 id 마다 하나) ───────────────────────────

def lms_submissions():
    """수집 원시 JSON(1_수집/_lms/lms-canvas-*.json)의 «내 제출» → {주제: [{과제, 파일[], 때}]} — 과제마다 가장 새 수집."""
    try:
        courses = json.load(open(os.path.join(HERE, "lms", "courses.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    raw = sorted(glob.glob(os.path.join(roles.abs("sources"), "_lms", "lms-canvas-*.json")), key=os.path.getmtime)
    by = {}
    for f in raw:
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for c in d.get("courses") or []:
            name = courses.get(str(c.get("id")))
            if not name:
                continue
            topic = roles.canon(name) or name
            for a in c.get("assignments") or []:
                s = a.get("submission") or {}
                if s.get("workflow_state") not in SUBMITTED:
                    continue
                files = [x.get("display_name") or unquote_plus(x.get("filename") or "") for x in s.get("attachments") or []]
                by.setdefault(topic, {})[a.get("id")] = {"과제": a.get("name") or "", "파일": [x for x in files if x], "때": s.get("submitted_at") or ""}
    return {t: list(v.values()) for t, v in by.items()}


def by_mark(t, ctx):
    """사람 표시 — 작업 폴더의 작업.md(낱파일 md 는 그 노트) «단계: 끝|제출» · «보냄:» · «결과물:»."""
    a = os.path.join(VAULT, *t["path"].split("/"))
    p = os.path.join(a, MARK) if t["dir"] else (a if a.lower().endswith(".md") else None)
    fm = front(p) if p and os.path.isfile(p) else {}
    t["mark"] = fm
    step, sent = str(fm.get("단계", "")).strip(), fm.get("보냄")
    if not (step in ("끝", "제출") or sent):
        return None
    out = fm.get("결과물") or []
    out = [out] if isinstance(out, str) else out
    if not out and isinstance(sent, str) and os.path.splitext(sent)[1].lower() in rules()["결과물_확장자"]:
        out = [sent]  # «보냄: 보고서.pdf» = 보낸 파일 이름(«보냄: 메일 · 여행사» 는 이름이 아님)
    if step == "제출" or sent:
        if not out:  # 적지 않았으면 작업 맨 위의 문서(보낸 꼴의 파일)
            top = [f for f in t.get("_files", []) if os.path.dirname(f) == (a if t["dir"] else os.path.dirname(a))]
            out = [os.path.basename(f) for f in top if os.path.splitext(f)[1].lower() in rules()["결과물_확장자"]]
        return {"state": "보냄", "why": "표시 «보냄: %s»" % (sent or "제출"), "deliver": out}
    return {"state": "끝냄", "why": "표시 «단계: 끝»"}


def by_lms(t, ctx):
    """LMS 내 제출 — 제출한 파일 이름과 작업 안 파일 이름이 길게 같다."""
    stems = [norm(os.path.basename(f)) for f in t["_files"]] + [norm(t["name"])]
    if "lms" not in ctx:
        ctx["lms"] = lms_submissions()
    for s in ctx["lms"].get(t["topic"], []):
        for n in s["파일"]:
            w = norm(n)
            if w and any(x and common(x, w) >= max(8, min(len(w), len(x)) - 6) for x in stems):
                return {"state": "보냄", "why": "LMS 내 제출 «%s» %s" % (s["과제"], (s["때"] or "")[:10]), "deliver": s["파일"]}
    return None


def git_merged(repo, branch):
    """가지가 원격 기본 가지에 들어갔나(병합) — 로컬 가지가 지워졌으면 원격 가지로 · 모르면 None."""
    def g(*a):
        r = subprocess.run(["git", "-C", repo, *a], capture_output=True, text=True, encoding="utf-8", timeout=15)
        return r.returncode, r.stdout.strip()
    try:
        code, head = g("symbolic-ref", "--short", "refs/remotes/origin/HEAD")
        bases = [head] if code == 0 and head else ["origin/main", "origin/master"]
        for base in bases:
            if g("rev-parse", "--verify", "-q", base)[0]:
                continue
            for ref in ("refs/heads/" + branch, "refs/remotes/origin/" + branch):
                if g("rev-parse", "--verify", "-q", ref)[0] == 0:
                    return g("merge-base", "--is-ancestor", ref, base)[0] == 0
        return None
    except (OSError, subprocess.SubprocessError):
        return None


def by_git(t, ctx):
    fm = t.get("mark") or {}
    repo, branch = fm.get("저장소"), fm.get("가지")
    if not (repo and branch):
        return None
    repo = repo if os.path.isabs(repo) else os.path.join(VAULT, *repo.split("/"))
    if git_merged(repo, branch):
        return {"state": "보냄", "why": "저장소 가지 «%s» 병합됨" % branch, "deliver": [], "kept": "저장소 " + os.path.basename(repo.rstrip("/\\"))}
    return None


def schedule_lines(topic):
    """이 주제의 일정 줄(지난 60일부터) — topic.py 와 같은 문법."""
    try:
        import topic as T
        return T.status(meta(topic), dt.datetime.now(T.KST).date(), back=60)
    except Exception:  # noqa: BLE001 — 일정이 없거나 깨져도 판정은 이어 간다
        return []


def tokens(name):
    """작업 이름의 낱말 — «1차발표» → [1차, 발표] · «실험5» → [실험5] · «7주차» → [7주차]."""
    s = os.path.splitext(name)[0]
    return [t for t in re.findall(r"\d+\s*(?:차|주차|장|회)|실험\s*\d+|[가-힣]{2,}|[A-Za-z]{3,}", s) if t]


def by_schedule(t, ctx):
    """일정 줄 — 작업 이름 낱말이 모두 들어 있고 날짜가 지남(또는 체크됨)."""
    tk = [x.replace(" ", "") for x in tokens(t["name"])]
    for ln in schedule_lines(t["topic"]) if tk else []:
        txt = ln["text"].replace(" ", "")
        if all(x in txt for x in tk) and (ln["days"] < 0 or ln["state"] == "냄"):
            return {"state": "마감 지남", "why": "일정 «%s» %s" % (ln["text"][:50], ln["date"])}
    return None


def by_idle(t, ctx):
    stop = ctx.get("stop")
    if stop is not None and t["idle"] >= stop:
        return {"state": "멈춤", "why": "%d일 안 바뀜(보존 일정표 «작업멈춤» %d일) — 끝났으면 정리" % (t["idle"], stop)}
    return None


EVIDENCE = {"표시": by_mark, "lms": by_lms, "git": by_git, "일정": by_schedule, "멈춤": by_idle}


# ── 자리 ──────────────────────────────────────────────────────────────

def sent_dirs(topic):
    """원본 층의 그 주제 «보냄» 자리(학교 과목 = «제출») — 있는 주제 자리(정식 이름·별칭) + 하위 · 없으면 등록부 영역으로 지을 자리 하나."""
    m = meta(topic)
    sub = rules()["보냄_자리"].get("종류", {}).get(m.get("종류") or "", rules()["보냄_자리"].get("기본", "보냄"))
    src = roles.path("sources")
    out = []
    for r in roles.config().get("topic_roots", []):
        if not r.startswith(src + "/"):
            continue
        for n in [topic] + list(m.get("별칭") or []):
            d = os.path.join(VAULT, *r.split("/"), n)
            if os.path.isdir(d):
                out.append(os.path.join(d, sub))
    if not out and m.get("영역"):
        out.append(os.path.join(VAULT, *src.split("/"), m["영역"], topic, sub))
    return out


def find_kept(names, dirs):
    """결과물이 보냄 자리에 있나 — 이름(정규화) 앞머리가 길게 같으면 같은 것으로."""
    for d in dirs:
        for f in files_of(d) if os.path.isdir(d) else []:
            if any(same_name(os.path.basename(f), n) for n in names):
                return rel(f)
    return None


def find_outside(names):
    """볼트 밖(내려받기·바탕화면) 바로 아래에서 같은 이름 — 이름·크기만 본다(내용은 열지 않음)."""
    for d in OUTSIDE:
        if not os.path.isdir(d):
            continue
        for n in names:
            for f in os.listdir(d):
                if os.path.isfile(os.path.join(d, f)) and same_name(f, n):
                    return os.path.join(d, f)
    return None


def knowledge_dir(topic):
    k = roles.path("knowledge")
    for d in roles.config().get("topic_roots", []):
        if d.startswith(k + "/") and os.path.isdir(os.path.join(VAULT, *d.split("/"), topic)):
            return d + "/" + topic
    area = meta(topic).get("영역")
    return "%s/%s/%s" % (k, area, topic) if area else roles.path("notes") + "/" + topic


# ── 판정 ──────────────────────────────────────────────────────────────

def tasks():
    """작업 층의 작업 — `<작업 층>/<영역>/<주제>/<작업>`(폴더 또는 낱파일) · 영역 없는 옛 자리 `<작업 층>/<주제>/<작업>` 도."""
    w = roles.path("work")
    roots = [r for r in roles.config().get("topic_roots", []) if r == w or r.startswith(w + "/")]
    out = []
    for r in roots:
        a = os.path.join(VAULT, *r.split("/"))
        if not os.path.isdir(a):
            continue
        area = r.split("/")[-1] if r != w else None
        for tn in sorted(os.listdir(a)):
            td = os.path.join(a, tn)
            if not os.path.isdir(td) or tn.startswith((".", "_")):
                continue
            topic = roles.canon(tn) or tn
            for k in sorted(os.listdir(td)):
                if k.startswith("."):
                    continue
                out.append({"topic": topic, "area": area, "path": rel(os.path.join(td, k)), "name": k, "dir": os.path.isdir(os.path.join(td, k))})
    return out


def judge(t, ctx, now=None):
    now = now or time.time()
    a = os.path.join(VAULT, *t["path"].split("/"))
    fs = files_of(a)
    t["_files"] = fs
    last = max((os.path.getmtime(f) for f in fs), default=os.path.getmtime(a))
    t.update(files=len(fs), idle=int((now - last) / 86400))
    hit = None
    for ev in rules()["근거"]:
        fn = EVIDENCE.get(ev.get("id"))
        if not fn or (ev.get("영역") and t.get("area") and t["area"] not in ev["영역"]):
            continue
        if ev.get("id") != "표시" and "mark" not in t:
            by_mark(t, ctx)  # git 근거가 표시 속성(저장소·가지)을 읽는다
        hit = fn(t, ctx)
        if hit:
            break
    t.update(hit or {"state": "진행", "why": ""})
    t.setdefault("deliver", [])
    if t["state"] == "보냄" and t["deliver"] and not t.get("kept"):
        dirs = sent_dirs(t["topic"])
        t["kept"] = find_kept(t["deliver"], dirs)
        here = [rel(f) for f in fs if any(same_name(os.path.basename(f), n) for n in t["deliver"])]
        t["here"] = here
        if not t["kept"] and not here:
            t["outside"] = find_outside(t["deliver"])
    t["missing"] = t["state"] == "보냄" and bool(t["deliver"]) and not (t.get("kept") or t.get("here") or t.get("outside"))
    t.pop("_files", None)
    return t


def status():
    ctx = {"stop": roles.retention("작업멈춤")}
    return [judge(t, ctx) for t in tasks()]


# ── 정리 계획 ──────────────────────────────────────────────────────────

def linked_from_knowledge(stem, skip):
    """지식 층(노트·기록)에서 이 이름을 위키링크로 가리키는 노트가 있나 — 장부 보기 같은 생성 파일·작업 폴더 안은 뺀다."""
    k = roles.abs("knowledge")
    gen = {roles.abs(r) for r in ("ledger_view", "moc") if roles.config()["roles"].get(r)}
    pat = re.compile(r"\[\[(?:[^\]|#]*/)?" + re.escape(stem) + r"(?:\.md)?(?:[|#\]])")
    for dp, dns, fns in os.walk(k):
        dns[:] = [d for d in dns if not d.startswith(".")]
        for f in fns:
            a = os.path.join(dp, f)
            if not f.endswith(".md") or a in gen or a.startswith(skip):
                continue
            try:
                if pat.search(open(a, encoding="utf-8", errors="ignore").read()):
                    return rel(a)
            except OSError:
                continue
    return None


def regenerable(f, base, md_stems):
    """다시 만들 수 있나(work.json «다시_만듦») — 대본·빌드·임시 · 만든 그림 자리 안(사진 빼고) · md 에서 내보낸 문서 → 이유 · 아니면 None."""
    R = rules()["다시_만듦"]
    ext = os.path.splitext(f)[1].lower()
    parts = os.path.relpath(f, base).replace("\\", "/").split("/")[:-1]
    if os.path.basename(f).startswith("~$"):
        return "잠금 파일"
    if ext in R["확장자"]:
        return "대본·빌드·임시"
    if ext not in R["사진"] and any(p in R["자리"] for p in parts):
        return "만든 자리(%s/)" % next(p for p in parts if p in R["자리"])
    if ext in R["내보냄"] and os.path.splitext(f)[0] in md_stems:
        return "같은 이름 md 가 원본"
    if ext in R.get("제작_원본", ()) and made_pdf(f, base):  # 사용자 11-05 «제작에 사용한 파일은 제작 종료시 제작폴더에서 삭제»
        return "제작에 쓴 파일(결과 PDF 있음)"
    return None


def made_pdf(f, base):
    """제작 원본의 결과 PDF 가 있나 — 같은 폴더(하위 폴더의 원본이면 작업 폴더 전체)에서 이 파일 뒤에 만들어진 PDF 만 친다(고치고 아직 안 만든 원본은 남긴다)."""
    t = os.path.getmtime(f)
    here = os.path.dirname(f)
    where = [(here, None, os.listdir(here))] if os.path.samefile(here, base) else os.walk(base)
    return any(n.lower().endswith(".pdf") and os.path.getmtime(os.path.join(d, n)) >= t for d, _, ns in where for n in ns)


def docx_to_pdf_ops(r, pdf_rel, why, twin=None):
    """docx 하나 → PDF 만 남기는 계획 줄 — PDF 먼저(실패하면 거기서 멈춰 docx 를 안 지운다) · 같은 PDF 가 이미 있으면(twin) 지우기만."""
    keep = [] if twin else [{"op": "pdf", "src": r, "dst": pdf_rel, "why": "PDF 만 남김 — " + why}]
    rm = {"op": "rm", "src": r, "why": "docx — PDF 만 남김(%s) — %s" % (twin or pdf_rel, why)}
    if r.startswith(roles.path("sources") + "/"):
        rm["user_asked"] = True  # 원본 층 지우기 — 계획은 사용자 승인 뒤에만 돈다
    return keep + [rm]


def plan_of(t):
    """끝난 작업 하나 → fileops 계획 ops(승인 뒤 --apply) · 보낸 결과물을 보관 못 하면 지우지 않는다."""
    a = os.path.join(VAULT, *t["path"].split("/"))
    fs = files_of(a)
    base = a if t["dir"] else os.path.dirname(a)
    stem = os.path.splitext(t["name"])[0]
    md_stems = {os.path.splitext(f)[0] for f in fs if f.lower().endswith(".md")}
    sub = lambda f: os.path.relpath(f, base).replace("\\", "/") if t["dir"] else os.path.basename(f)  # noqa: E731
    ops = []
    files = t["state"] == "보냄" and bool(t.get("deliver"))
    report = is_report(t["topic"])
    mat = set(rules()["재료_확장자"])
    pdf_name = lambda n: os.path.splitext(n)[0] + ".pdf"  # noqa: E731
    if files:  # 보낸 파일이 있는 작업 — 결과물은 보냄 자리, 재료는 그 옆(보고서 = 휴지통)
        dirs = sent_dirs(t["topic"])
        if not dirs:
            return [], "원본 층에 이 주제 자리가 없고 등록부 영역도 없어 결과물 둘 곳 없음"
        sd = rel(dirs[0])
        twin = lambda n: find_kept([pdf_name(n)], dirs)  # noqa: E731 — 같은 이름 PDF 가 이미 보관됐나
        kept = t.get("kept") or ""
        if not kept and not t.get("here"):
            out = t.get("outside")
            if out and report and out.lower().endswith(".docx"):  # 볼트 밖 원본은 사용자 것 — 변환해 들이기만
                if not twin(os.path.basename(out)):
                    ops.append({"op": "pdf", "src": out, "dst": sd + "/" + pdf_name(os.path.basename(out)), "why": "결과물 보관(볼트 밖 docx → PDF) — " + t["why"]})
            elif out:
                ops.append({"op": "cp", "src": out, "dst": sd + "/", "why": "결과물 보관 — %s(볼트 밖에서 들임)" % t["why"]})
            else:
                return [], "결과물 없음 — LMS 수집이 «내 제출»을 받게 하거나(확장 다시 읽기 뒤 수집) 받은함·작업 폴더에 두기 · 그때까지 지우지 않음"
        elif report and kept.lower().endswith(".docx"):  # 제출 자리에 docx 로 보관된 것(LMS 내 제출 등)
            base_name = os.path.basename(kept)
            ops += docx_to_pdf_ops(kept, kept.rsplit("/", 1)[0] + "/" + pdf_name(base_name), t["why"], twin(base_name))
        docs = set(rules()["결과물_확장자"])
        for f in fs:
            r, ext, name = rel(f), os.path.splitext(f)[1].lower(), os.path.basename(f)
            if name == MARK:
                ops.append({"op": "rm", "src": r, "why": "작업 표시 — 판정 끝"})
            elif r in (t.get("here") or []):
                if kept:
                    ops.append({"op": "rm", "src": r, "why": "결과물 사본(보관됨 %s)" % kept})
                elif report and ext == ".docx":
                    ops += docx_to_pdf_ops(r, sd + "/" + pdf_name(name), t["why"], twin(name))
                else:
                    ops.append({"op": "mv", "src": r, "dst": sd + "/" + name, "why": "결과물 보관 — " + t["why"]})
            elif report and ext == ".docx" and not kept and twin(name):
                ops.append({"op": "rm", "src": r, "why": "docx — PDF 만 남김(%s) — %s" % (twin(name), t["why"])})
            elif ext == ".md":  # 노트는 다시 못 만든다 — 지식으로(지식 노트가 가리키면 그 까닭을 적음)
                by = linked_from_knowledge(os.path.splitext(name)[0], a)
                ops.append({"op": "mv", "src": r, "dst": "%s/%s/%s" % (knowledge_dir(t["topic"]), stem, sub(f)),
                            "why": "지식으로 승격(%s) — %s" % ("%s 가 가리킴" % by if by else "작업 노트", t["why"])})
            elif ext in mat and not regenerable(f, base, md_stems):
                if report:
                    ops.append({"op": "rm", "src": r, "why": "보고서 재료 = 1회용 — " + t["why"]})
                else:
                    ops.append({"op": "mv", "src": r, "dst": "%s/%s/%s" % (sd, stem, sub(f)), "why": "재료 승격(결과물 옆) — " + t["why"]})
            else:
                why = regenerable(f, base, md_stems) or ("초안·다른 판(보낸 판이 보관됨)" if ext in docs else "작업 노트·파일")
                ops.append({"op": "rm", "src": r, "why": "%s — %s" % (why, t["why"])})
    else:  # 끝냄·마감 지남·멈춤·저장소로 보냄 — 다시 만들 수 있는 것만 지우고 나머지는 지식으로
        kd = knowledge_dir(t["topic"])
        for f in fs:
            r, name, ext = rel(f), os.path.basename(f), os.path.splitext(f)[1].lower()
            why = "작업 표시 — 판정 끝" if name == MARK else regenerable(f, base, md_stems)
            dst = "%s/%s/%s" % (kd, stem, sub(f)) if t["dir"] else kd + "/" + name
            if why:
                ops.append({"op": "rm", "src": r, "why": "%s — %s" % (why, t["why"])})
            elif report and ext in mat:
                ops.append({"op": "rm", "src": r, "why": "보고서 재료 = 1회용 — " + t["why"]})
            elif report and ext == ".docx":
                ops += docx_to_pdf_ops(r, os.path.splitext(dst)[0] + ".pdf", t["why"])
            else:
                ops.append({"op": "mv", "src": r, "dst": dst, "why": "지식으로 승격(다시 못 만듦) — " + t["why"]})
    if ops:  # 폴더째 비운다(사용자 11-02 «하위 폴더가 없도록») — 안쪽 폴더부터 · 작업 폴더 · 이 작업 하나만 있던 주제·영역 폴더까지
        if t["dir"]:  # fileops rmdir 은 파일이 없으면 빈 하위 폴더째 지운다
            ops.append({"op": "rmdir", "path": t["path"], "why": "끝난 작업 폴더 — 안을 다 승격·휴지통한 뒤 비었을 때만(빈 하위 폴더째)"})
        top = os.path.dirname(a)
        w = roles.abs("work")
        while os.path.abspath(top) != os.path.abspath(w) and [c for c in os.listdir(top) if not c.startswith(".")] == [os.path.basename(a)]:
            ops.append({"op": "rmdir", "path": rel(top), "why": "이 작업만 있던 폴더 — 작업 층에 빈 폴더를 남기지 않음"})
            a, top = top, os.path.dirname(top)
    return ops, ""


def write_plans(st):
    day = dt.date.today().isoformat()
    out_dir = os.path.join(HERE, "_index", "cleanup")
    os.makedirs(out_dir, exist_ok=True)
    res = []
    for t in st:
        if t["state"] == "진행":
            continue
        ops, note = plan_of(t)
        item = {"path": t["path"], "state": t["state"], "why": t["why"], "ops": len(ops), "note": note}
        if ops:
            p = os.path.join(out_dir, "작업-%s-%s.json" % (day, re.sub(r"[^0-9A-Za-z가-힣_-]", "_", t["path"].split("/", 1)[-1])))
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"title": "끝난 작업 정리 — %s (%s) · %s 승인 뒤에만 --apply" % (t["path"], t["state"], roles.me()), "ops": ops}, f, ensure_ascii=False, indent=1)
            item["plan"] = rel(p)
        res.append(item)
    return res


SWEPT = os.path.join(HERE, "_index", "work-swept.json")  # 한 번 비운 작업 — 되돌려져 돌아오면 저절로 다시 비우지 않는다(사람이 되살린 것)


def load_swept():
    try:
        return json.load(open(SWEPT, encoding="utf-8"))
    except (OSError, ValueError):
        return []


def save_swept(swept):
    os.makedirs(os.path.dirname(SWEPT), exist_ok=True)
    with open(SWEPT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(swept, f, ensure_ascii=False, indent=0)


def finish(path, by="script:work"):
    """사람이 끝냄을 체크함(홈 · 탐색기 우클릭 · 사용자 11-03) → 바로 비운다 → {path, batch} · 못 하면 {error}.
    사람이 끝났다고 했으니 근거를 묻지 않는다 — 보낸 결과물이 어딘가에 있으면 그 계획대로 · 아니면 끝냄 계획(다시 못 만드는 것은 2_지식으로)."""
    import fileops
    t = next((x for x in status() if x["path"] == path), None)
    if not t:
        return {"error": "작업 폴더의 작업이 아님: " + path}
    if t["state"] != "보냄" or t.get("missing"):
        t.update(state="끝냄", why="사람이 체크", deliver=[], missing=False)
    ops, note = plan_of(t)
    if not ops:
        return {"error": note or "비울 것 없음"}
    ctx = fileops.Ctx(VAULT, by=by)
    err = None
    try:
        fileops.run_ops(ctx, ops, lenient=False)
    except fileops.Stop as e:
        err = str(e)
    if ctx.events:
        fileops.write_view(ctx)
        swept = load_swept()
        if path not in swept:
            save_swept(swept + [path])
    out = {"path": path, "batch": ctx.batch if ctx.events else None}
    if err:
        out["error"] = err
    return out


def sweep():
    """끝난 작업 비우기(사용자 11-03 «작업이 진행 중일 때만 남아있고 끝나면 무조건 비운다») → 비운 작업 [{path, batch}] · door.py sweep 이 볼트를 켤 때 부른다.
    결과물을 보관 못 하면 계획이 없어 그대로다(지우지 않는다) · 비운 작업이 되돌려져 돌아오면 다시 안 비운다."""
    import fileops
    swept = load_swept()
    out = []
    for t in status():
        if t["state"] not in SURE or t["path"] in swept:
            continue
        ops = plan_of(t)[0]
        if not ops:
            continue
        ctx = fileops.Ctx(VAULT, by="script:work")
        try:
            fileops.run_ops(ctx, ops, lenient=False)
        except fileops.Stop as e:
            print("못 비움 %s — %s" % (t["path"], e))
        if ctx.events:
            fileops.write_view(ctx)
            swept.append(t["path"])
            out.append({"path": t["path"], "batch": ctx.batch})
    if out:
        save_swept(swept)
    return out


def summary(st):
    """건강·홈용 — 끝남(보냄·마감 지남·끝냄) · 결과물 없음 · 멈춤 · 진행."""
    return {"끝남": sum(1 for t in st if t["state"] in DONE), "결과물없음": sum(1 for t in st if t.get("missing")),
            "멈춤": sum(1 for t in st if t["state"] == "멈춤"), "진행": sum(1 for t in st if t["state"] == "진행"),
            "items": [{k: t.get(k) for k in ("path", "topic", "state", "why", "kept", "here", "outside", "missing", "idle")} for t in st]}


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    a = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in a
    a = [x for x in a if x != "--json"]
    if a and a[0] == "finish":
        print(json.dumps(finish(a[1], a[a.index("--by") + 1] if "--by" in a else "script:work"), ensure_ascii=False))
        return 0
    if a and a[0] == "sweep":
        for r in sweep():
            print("비움 %s · 되돌리기 = fileops.py undo %s" % (r["path"], r["batch"]))
        return 0
    st = status()
    if a and a[0] == "plan":
        res = write_plans(st)
        if as_json:
            print(json.dumps(res, ensure_ascii=False))
            return 0
        for r in res:
            print("%s · %s · %s%s" % (r["path"], r["state"], r["why"], (" → 계획 %s(%d건)" % (r["plan"], r["ops"])) if r.get("plan") else ""))
            if r["note"]:
                print("    " + r["note"])
        print("적용(승인 뒤만): py -3 3_시스템/fileops.py plan <계획> --apply" if any(r.get("plan") for r in res) else "정리할 끝난 작업 없음")
        return 0
    if as_json:
        print(json.dumps(summary(st), ensure_ascii=False))
        return 0
    for t in st:
        extra = ""
        if t["state"] == "보냄" and t["deliver"]:
            extra = " · 결과물 " + ("보관됨 " + t["kept"] if t.get("kept") else "작업 안 " + ", ".join(t["here"]) if t.get("here") else
                                 "볼트 밖에 있음 " + t["outside"] if t.get("outside") else "없음")
        print("%-6s %s — %s%s" % (t["state"], t["path"], t["why"] or "%d일 전 바뀜" % t["idle"], extra))
    return 0


if __name__ == "__main__":
    sys.exit(main())
