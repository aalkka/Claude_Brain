#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""privguard — 만드는 것(제품 경로)에 새로 들어가는 개인 값을 그 자리에서 잡는다.

  py -3 privguard.py --staged [--repo-product]        git 스테이지: 파일마다 마지막 커밋 판보다 개인 값이 는 것만 (저장소 뿌리에서)
  py -3 privguard.py --diff <범위> [--repo-product]   git diff <범위> 의 추가된 줄만
  py -3 privguard.py --file <경로> --text <새 글 파일>  파일에 들어갈 새 글(지금 디스크 판에 없는 줄만)
  py -3 privguard.py --tree <폴더>                    폴더의 모든 줄을 «추가된 줄»로 보고 잰다(측정용)
  py -3 privguard.py --hook                           Claude Code 훅(PreToolUse Write·Edit·MultiEdit · 늘면 막음 · 입력 = 표준 입력 JSON)
  py -3 privguard.py install-hook <저장소>              그 저장소 .git/hooks/pre-commit 에 --staged 검사를 건다
  py -3 privguard.py rules [--refresh]                 꼴 수·갈래(값은 안 보임)

왜(incident-2026-11-22 배포판 개인정보 공개이력 96건): 출시 때 한 번 세는 검사는 이미 섞인 뒤에야 본다.
  쓰는 순간·커밋하는 순간에 «늘어난 개인 값»만 보면, 있는 개인 값을 지우거나 곁을 고치는 일은 통과하고 새 누출만 막힌다
  (훅·커밋 = 파일마다 (꼴, 값) 수를 고치기 전·뒤로 셈 · --diff·--file = 추가된 줄 · --tree = 모든 줄).

꼴 = dist-diff.dist_rules(내장 + 볼트 전용 + 자동 꼴) + 지식에서 찾는 꼴(이 대본):
  노트 제목·별칭(지식·작업 칸) · 주제 이름·별칭 · 일정 제목(과목 칸·할 일 글) · 수집 칸 파일·폴더 이름.
  흔한 말은 거른다: 짧은 말 · 볼트가 싣는 이름(모듈·스킬·추적 파일) · 흔한 낱말 표 · 허용 목록(leak-allow.txt).
  지식 꼴은 개인 층(git 밖)에 사람이 읽을 수 있게 적는다 — 빼려면 leak-allow.txt 에 그 값.
대상 = 제품 경로만: .claude/skills/** · 배포 목록(ship.json)에 실린 3_시스템 코어 · 개인 설정에 적은 저장소.
  노트·기록·기억(그 자체가 개인화 파일)과 기능의 «개인화 파트»는 대상이 아니다:
  경로 마디 `personal/` · 가까운 module.json·manifest.json 의 "personal": [glob…](기능 뿌리 기준).
출력 = 파일:줄 · 갈래 · 값(앞 한 글자 + ●) · 끝 코드 0 = 없음 · 1 = 걸림 · 2 = 검사 못 함.

개인화 조리법(이 기능의 개인 값 · 모두 3_시스템/_index/dist-sync/ · git 밖):
  privguard.json = {"repos": [제품 저장소 뿌리…], "hook": "block"(기본)|"alert", "notes_skip": [볼트 상대 폴더…]}
    repos = install-hook 이 채운다 · notes_skip = 이 제품 자체를 설계·기록하는 노트 자리(그 노트 이름은 제품 낱말 · 사람이 적음).
  privguard-auto.txt = 지식 꼴(이 대본이 다시 씀) · privguard-rules.json = 꼴 묶음 캐시(30분) · privguard.log = 훅이 알린 줄(값 없음).
"""
import sys, os, re, json, time, argparse, fnmatch, subprocess, importlib.util

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
_spec = importlib.util.spec_from_file_location("dist_diff", os.path.join(HERE, "dist-diff.py"))
dd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dd)
roles = dd.roles

LOCAL = os.path.join("3_시스템", "_index", "dist-sync")  # mf:allow-path  (이 기능의 개인 층 — module.json touches)
CONF = "privguard.json"
AUTO = "privguard-auto.txt"
CACHE = "privguard-rules.json"
LOG = "privguard.log"
TTL = 1800
MARK = "# privguard pre-commit"
ADVICE = "일반 표현(사용자 · 과목A · 가짜 일정 같은 꼴)으로 바꾸거나, 그 기능의 개인화 파트(personal/ 또는 매니페스트가 밝힌 자리)로 옮길 것"

# 흔한 말 — 노트·파일 이름이어도 꼴로 만들지 않는다(일반 낱말 · 개인 값이 아님)
COMMON = {
    "readme", "index", "notes", "draft", "todo", "template", "example", "settings", "config", "manifest",
    "작업", "결과", "기록", "계획", "설계", "현황", "정리", "요약", "메모", "공지", "과제", "강의", "시험", "보고서",
    "설명서", "사용자", "사용법", "일정", "목록", "색인", "받은함", "원본", "자료", "준비", "확인", "검사", "시험지",
    "해설", "풀이", "답안", "필기", "노트", "실험", "발표", "회의", "프로젝트", "로드맵", "학교", "수업", "학기",
    "중간고사", "기말고사", "강의자료", "강의노트", "실험보고서", "결과보고서", "예비보고서", "과제제출", "공지사항",
    "아이디어", "수업 안내", "과제 안내", "강의 안내",
}
KO = re.compile(r"[가-힣]")
DATE_HEAD = re.compile(r"^\d{4}-\d{2}-\d{2}[ _-]*")
NUMBERED = re.compile(r"[A-Za-z]{1,8}[\d._-]+")    # chap19 · lec03 · hw2-1 — 장·강 번호 꼴은 어느 교재·강의에나 있는 이름
SCHED = re.compile(r"^- \[[ xX]\] \d{4}-\d{2}-\d{2}(?: \([^)]*\))?(?: \d{1,2}:\d{2}(?:~\d{1,2}:\d{2})?)? *(.*)$")


def local(vault, name):
    return os.path.join(vault, LOCAL, name)


def load_conf(vault):
    try:
        with open(local(vault, CONF), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_conf(vault, d):
    os.makedirs(local(vault, ""), exist_ok=True)
    with open(local(vault, CONF), "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")


def norm(p):
    return os.path.abspath(p).replace("\\", "/").rstrip("/")


# ── 지식에서 찾는 꼴 ─────────────────────────────────────────────

def _frontmatter(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            head = f.read(4096)
    except OSError:
        return "", []
    if not head.startswith("---"):
        return "", []
    end = head.find("\n---", 3)
    fm = head[3:end] if end > 0 else ""
    t = re.search(r"^title:\s*(.+?)\s*$", fm, re.M)
    title = t.group(1).strip("\"'") if t else ""
    al = []
    m = re.search(r"^aliases:\s*\[(.*?)\]\s*$", fm, re.M)
    if m:
        al = [x.strip().strip("\"'") for x in m.group(1).split(",")]
    else:
        m = re.search(r"^aliases:\s*\n((?:\s+-\s.*\n?)+)", fm, re.M)
        if m:
            al = [re.sub(r"^\s+-\s*", "", x).strip().strip("\"'") for x in m.group(1).splitlines()]
    return title, [a for a in al if a]


def keep(s, allow, shipped, short_ok=False):
    """꼴로 쓸 값인가 — 흔한 말·짧은 말·싣는 이름·허용 값은 뺀다."""
    s = s.strip()
    k = s.lower()
    if not s or k in allow or k in COMMON or k.replace("_", "-") in shipped or "{{" in s:
        return False
    if re.fullmatch(r"[\d\s._:()\[\]-]+", s) or NUMBERED.fullmatch(s):
        return False
    if KO.search(s):
        return len(re.sub(r"[\s_.#-]", "", s)) >= (3 if short_ok else 5)
    # 한글이 없으면 낱말 하나(영어 낱말)는 흔한 말 — 숫자나 이음표가 든 6자 이상만
    return len(s) >= 6 and bool(re.search(r"[-\d_ ]", s)) and bool(re.search(r"[A-Za-z]", s))


def knowledge_values(vault, allow, shipped, skip=()):
    """[(값, 갈래)] — 노트 제목·별칭 · 주제 · 일정 제목 · 수집 칸 이름.
    skip = 제품 자체를 다루는 자리(볼트 상대 · 개인 설정 notes_skip) — 그 노트 이름은 제품 낱말이라 꼴로 안 만든다.
    배포판에 실리는 노트(씨앗)도 뺀다. 주제는 과목·프로젝트 칸(learn_notes·doing_notes) 것만 — 생활·분야 칸 이름은 흔한 말."""
    out = {}
    skip = tuple(x.replace("\\", "/").strip("/") + "/" for x in skip)
    vn = norm(vault) + "/"

    def skipped(path):
        rel = norm(path)[len(vn):] if norm(path).startswith(vn) else norm(path)
        return rel.startswith(skip) or rel in fixed or (rel.endswith(".md") and dd.layer(rel) != "개인")

    # 제품이 정한 이름의 노트 — 역할이 가리키는 노트(모아보기·장부 보기 등)와 일정 칸(생성기가 이름을 정함)
    rmap = roles.config(vault).get("roles") or {}
    fixed = {v for v in rmap.values() if isinstance(v, str) and v.endswith(".md")}
    skip = skip + (roles.path("schedule", vault=vault).strip("/") + "/",)

    def add(v, lab, short_ok=False):
        v = re.sub(r"\s+", " ", v or "").strip()
        for cand in {v, DATE_HEAD.sub("", v)}:
            if keep(cand, allow, shipped, short_ok) and cand not in out:
                out[cand] = lab

    for role in ("knowledge", "work"):
        base = roles.abs(role, vault=vault)
        for dp, dns, fns in os.walk(base):
            dns[:] = [d for d in dns if not d.startswith((".", "_")) and not skipped(os.path.join(dp, d, ""))]
            for fn in fns:
                if fn.endswith(".md") and not skipped(os.path.join(dp, fn)):
                    add(fn[:-3], "노트 제목·별칭")
                    title, al = _frontmatter(os.path.join(dp, fn))
                    add(title, "노트 제목·별칭")
                    for a in al:
                        add(a, "노트 제목·별칭", short_ok=True)
    areas = {roles.path(r, vault=vault).rsplit("/", 1)[-1] for r in ("learn_notes", "doing_notes")}
    names = {x.rstrip("/").rsplit("/", 1)[-1] for x in skip}
    for t in roles.topics(vault=vault) or []:
        if isinstance(t, dict) and t.get("영역") in areas and t.get("이름") not in names:
            add(str(t.get("이름") or ""), "주제 이름·별칭", short_ok=True)
            for a in t.get("별칭") or []:
                add(str(a), "주제 이름·별칭")   # 별칭은 흔한 낱말이 많다 — 짧은 줄임말은 사람이 적는 꼴(leak-patterns)이 맡는다
    sd = roles.abs("schedule", vault=vault)
    for fn in (os.listdir(sd) if os.path.isdir(sd) else []):
        if not fn.endswith(".md"):
            continue
        try:
            lines = open(os.path.join(sd, fn), encoding="utf-8", errors="replace").read().splitlines()
        except OSError:
            continue
        for ln in lines:
            m = SCHED.match(ln)
            if not m:
                continue
            # 할 일 글은 괄호·줄표·링크·블록 id 앞까지 — 알림 제목처럼 앞부분만 옮겨 쓴 꼴도 잡게(괄호 안 날짜는 옮길 때 바뀜)
            rest = re.split(r"\[\[| — |\s*\(| \^[\w-]+", m.group(1))[0]
            parts = [x.strip() for x in rest.split(" · ")]
            if len(parts) >= 2:
                add(parts[0], "일정 제목")
                task = parts[1]
            else:
                task = parts[0]
            if len(re.sub(r"\s", "", task)) >= 8:      # 할 일 글은 긴 것만(짧은 «휴일» 같은 말 거름)
                add(task, "일정 제목")
    src = roles.abs("sources", vault=vault)
    for dp, dns, fns in os.walk(src):
        dns[:] = [d for d in dns if not d.startswith((".", "_")) and not skipped(os.path.join(dp, d, ""))]
        for d in dns:
            add(d, "수집 칸 이름")
        for fn in fns:
            add(os.path.splitext(fn)[0], "수집 칸 이름")
    return sorted(out.items(), key=lambda x: (x[1], x[0]))


def _alt(values):
    """값 묶음 → 정규식 하나(긴 것 먼저). 영어·숫자 값은 낱말 경계를 본다."""
    vs = sorted(set(values), key=lambda v: (-len(v), v))
    asc = [v for v in vs if not KO.search(v)]
    ko = [v for v in vs if KO.search(v)]
    out = []
    if asc:
        out.append(r"(?<![A-Za-z0-9_-])(?:" + "|".join(re.escape(v) for v in asc) + r")(?![A-Za-z0-9_-]|\.[A-Za-z])")
    if ko:
        out.append("(?:" + "|".join(re.escape(v) for v in ko) + ")")
    return out


def build_rules(vault, refresh=False):
    """[(정규식, 갈래)] + 허용 값 — 캐시(TTL)를 먼저 본다."""
    cp = local(vault, CACHE)
    if not refresh:
        try:
            with open(cp, encoding="utf-8") as f:
                c = json.load(f)
            if time.time() - c.get("built", 0) < TTL:
                return [tuple(r) for r in c["rules"]], set(c["allow"])
        except (OSError, ValueError, KeyError):
            pass
    allow = dd.load_allow(vault)
    shipped = dd._shipped_names(vault)
    rules = list(dd.dist_rules(vault))
    kv = knowledge_values(vault, allow, shipped, load_conf(vault).get("notes_skip") or ())
    by = {}
    for v, lab in kv:
        by.setdefault(lab, []).append(v)
    for lab, vs in by.items():
        rules += [(rx, lab) for rx in _alt(vs)]
    if os.path.isdir(local(vault, "")):
        with open(local(vault, AUTO), "w", encoding="utf-8", newline="\n") as f:
            f.write("# privguard 지식 꼴(개인 층 · 손으로 고치지 않음 — 빼려면 leak-allow.txt 에 값)\n")
            f.writelines("%s\t%s\n" % (lab, v) for v, lab in kv)
        with open(cp, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"built": time.time(), "rules": rules, "allow": sorted(allow)}, f, ensure_ascii=False)
    return rules, allow


def load_rules_file(p):
    """시험·다른 꼴 묶음 — «정규식<TAB>갈래» 줄 · 파일이 없으면 오류(조용히 «꼴 0 = 통과»가 되지 않게)."""
    if not os.path.isfile(p):
        raise FileNotFoundError("꼴 파일 없음: %s" % p)
    return dd._tab_rules(p, "개인 값"), set()


def hook_failed(vault, e):
    """훅이 검사를 못 함 = 통과(끝 코드 0) + 기록 한 줄 + 사람에게 한 줄. 끝 코드 2(막음)는 늘어남을 실제로 센 때만 —
    오류로 2 가 나면 모든 세션의 쓰기가 멈춘다."""
    why = "%s: %s" % (type(e).__name__, str(e)[:120])
    try:
        with open(local(vault, LOG), "a", encoding="utf-8", newline="\n") as f:
            f.write("%s 못 잼 %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), why))
    except OSError:
        pass
    sys.stdout.write(json.dumps({"systemMessage": "privguard: 검사 못 함(통과) — " + why}, ensure_ascii=False) + "\n")
    return 0


# ── 대상 경로 ───────────────────────────────────────────────────

def _manifest_personal(path, stop):
    """가까운 module.json·manifest.json 의 "personal" glob 에 드는가."""
    d = os.path.dirname(path)
    stop = norm(stop) if stop else ""
    while True:
        for mf in ("module.json", "manifest.json"):
            p = os.path.join(d, mf)
            if os.path.isfile(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        pats = json.load(f).get("personal") or []
                except (OSError, ValueError, AttributeError):
                    pats = []
                rel = os.path.relpath(path, d).replace("\\", "/")
                if any(fnmatch.fnmatch(rel, g) or rel.startswith(g.rstrip("*").rstrip("/") + "/") for g in pats):
                    return True
        nd = os.path.dirname(d)
        if nd == d or norm(d) == stop:
            return False
        d = nd


def personal_part(path, root=None):
    segs = norm(path).split("/")
    return "personal" in segs[:-1] or _manifest_personal(path, root)


def product_kind(path, vault, conf, ship=None):
    """제품 경로면 그 뿌리, 아니면 None."""
    p = norm(path)
    v = norm(vault)
    for r in conf.get("repos") or []:
        r = norm(r)
        if p.startswith(r + "/") and "/.git/" not in p[len(r):] + "/":
            return None if personal_part(p, r) else r
    if not p.startswith(v + "/"):
        return None
    rel = p[len(v) + 1:]
    if rel.startswith(".claude/skills/"):  # mf:allow-path
        if "/__pycache__/" in rel or personal_part(p, v + "/.claude/skills"):
            return None
        return v
    if rel.startswith("3_시스템/"):  # mf:allow-path
        if dd.layer(rel) != "코어":
            return None
        if ship is None:
            ship = dd.load_ship(vault)
        return v if dd.shipped(ship, rel) is not None and not personal_part(p, v) else None
    return None


# ── 줄 대 보기 ─────────────────────────────────────────────────

def mask(v):
    return v[:1] + "●" * min(max(len(v) - 1, 1), 5)


def label(lb):
    """갈래 이름만 — 개인 꼴 파일의 이름 칸에 든 보기 값·메모(괄호 · « · » 뒤)는 내보내지 않는다."""
    return re.split(r"[(（]| · ", lb)[0].strip() or "개인 값"


def scan(records, rules, allow):
    """records = [(파일, 줄 번호, 줄)] → [(파일, 줄 번호, 갈래, 가린 값)]"""
    comp = [(re.compile(rx), lb) for rx, lb in rules]
    out = []
    for rel, n, line in records:
        code = not dd.PROSE.search(rel)
        text = dd._unesc(line) if code else line
        for rx, lb in comp:
            if any(lb.startswith(k) and f(rel, code) for k, f in dd.SKIP_IN):
                continue
            hit = next((m.group(0) for m in rx.finditer(text) if m.group(0).lower() not in allow), None)
            if hit:
                out.append((rel, n, label(lb), mask(hit)))
                break
    return out


def added_from_diff(diff):
    """unified diff(-U0) → [(파일, 새 줄 번호, 줄)] — «+» 줄만."""
    recs, cur, n = [], None, 0
    for ln in diff.splitlines():
        if ln.startswith("+++ "):
            t = ln[4:]
            cur = None if t == "/dev/null" else (t[2:] if t.startswith("b/") else t)
        elif ln.startswith("@@"):
            m = re.search(r"\+(\d+)", ln)
            n = int(m.group(1)) if m else 0
        elif ln.startswith("+") and cur is not None:
            recs.append((cur, n, ln[1:]))
            n += 1
        elif ln.startswith(" "):
            n += 1
    return recs


def git_diff(cwd, *args):
    r = subprocess.run(["git", "-c", "core.quotepath=off", "diff", "-U0", "--no-color", "--no-ext-diff",
                        "--diff-filter=ACMR", *args], cwd=cwd, capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip())
    return r.stdout.decode("utf-8", "replace")


def new_lines(old, new):
    """새 글에서 옛 글에 없던 줄(개수까지 본다) → [(줄 번호, 줄)]."""
    pool = {}
    for ln in (old or "").splitlines():
        pool[ln] = pool.get(ln, 0) + 1
    out = []
    for i, ln in enumerate(new.splitlines(), 1):
        if pool.get(ln):
            pool[ln] -= 1
        else:
            out.append((i, ln))
    return out


def read(p):
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def git_head_text(path):
    d = os.path.dirname(os.path.abspath(path))
    r = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "--full-name", "--", os.path.basename(path)],
                       cwd=d, capture_output=True) if os.path.isdir(d) else None
    rel = r.stdout.decode("utf-8", "replace").strip() if r and not r.returncode else ""
    if not rel:
        return ""
    s = subprocess.run(["git", "show", "HEAD:" + rel], cwd=d, capture_output=True)
    return s.stdout.decode("utf-8", "replace") if not s.returncode else ""


def report(hits, out=print):
    for rel, n, lb, v in hits:
        out("%s:%d · %s · %s" % (rel, n, lb, v))


# ── 늘어남 세기(훅·커밋 공통) ───────────────────────────────────
# 줄 단위 «추가된 줄»은 있는 개인 값 줄 곁을 고치기만 해도 걸린다(바뀐 줄 = 추가된 줄) — 제품 트리에 이미 참 걸림이 많으면
# 분리 작업이 멈춘다. 그래서 파일마다 고치기 전·뒤 글의 (꼴, 값) 수를 세어 어느 하나라도 늘 때만 걸린다:
# 지우기·줄 옮기기·곁 고치기 = 통과 · 새 값·같은 값 하나 더·다른 개인 값으로 바꾸기 = 걸림.

def tally(rel, text, comp, allow):
    code = not dd.PROSE.search(rel)
    t = dd._unesc(text) if code else text
    c = {}
    for rx, lb in comp:
        if any(lb.startswith(k) and f(rel, code) for k, f in dd.SKIP_IN):
            continue
        for m in rx.finditer(t):
            v = m.group(0)
            if v.lower() not in allow:
                k = (lb, v.lower())
                c[k] = c.get(k, 0) + 1
    return c


def grown(rel, old, new, comp, allow):
    """[(파일, 줄 번호, 갈래, 가린 값)] — 뒤 글에서 수가 는 (꼴, 값)마다 하나(줄 = 그 값이 처음 나오는 줄)."""
    a, b = tally(rel, old or "", comp, allow), tally(rel, new or "", comp, allow)
    out = []
    low = [ln.lower() for ln in (new if dd.PROSE.search(rel) else dd._unesc(new)).splitlines()]
    for (lb, v), n in sorted(b.items()):
        if n > a.get((lb, v), 0):
            line = next((i for i, ln in enumerate(low, 1) if v in ln), 0)
            out.append((rel, line, label(lb), mask(v)))
    return out


def comp_of(rules):
    return [(re.compile(rx), lb) for rx, lb in rules]


def after_edit(disk, ti):
    """Edit·MultiEdit 를 디스크 글에 대 본 뒤 글 · 못 대면(old_string 없음 = 도구가 실패할 것) None."""
    edits = ti.get("edits") or [{"old_string": ti.get("old_string", ""), "new_string": ti.get("new_string", ""),
                                 "replace_all": ti.get("replace_all", False)}]
    t = disk
    for e in edits:
        old, new = e.get("old_string") or "", e.get("new_string") or ""
        if old and old not in t:
            return None
        t = t.replace(old, new) if e.get("replace_all") else (t.replace(old, new, 1) if old else new + t)
    return t


# ── 훅 ───────────────────────────────────────────────────────

def hook(data, vault, rules_loader, conf):
    """PreToolUse = 고치기 전 디스크 글 ↔ 고친 뒤 글 · 늘면 막음(끝 코드 2 · 설정 hook=alert 면 알림만).
    PostToolUse = 마지막 커밋 판 ↔ 지금 디스크 글 · 늘면 알림."""
    ev = data.get("hook_event_name") or "PreToolUse"
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ""
    if not path or not product_kind(path, vault, conf):
        return 0, None
    disk = read(path)
    if ev == "PreToolUse":
        old = disk
        new = (ti.get("content") or "") if "content" in ti else after_edit(disk, ti)
    else:
        old, new = git_head_text(path), disk
    if new is None or new == old:
        return 0, None
    rules, allow = rules_loader()
    rel = os.path.basename(path) if not norm(path).startswith(norm(vault) + "/") else norm(path)[len(norm(vault)) + 1:]
    hits = grown(rel, old, new, comp_of(rules), allow)
    if not hits:
        return 0, None
    lines = ["%s:%d · %s · %s" % h for h in hits]
    block = ev == "PreToolUse" and conf.get("hook", "block") != "alert"
    msg = "privguard: 제품 경로에 개인 값이 %d가지 늘어남%s — %s\n%s" % (
        len(hits), "(이 고침을 막음)" if block else "", ADVICE, "\n".join(lines[:20]))
    try:
        with open(local(vault, LOG), "a", encoding="utf-8", newline="\n") as f:
            f.write("%s %s %s %s %d가지 %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), ev, "막음" if block else "알림", rel,
                                               len(hits), ",".join(sorted({h[2] for h in hits}))))
    except OSError:
        pass
    if block:
        return 2, msg
    return 0, json.dumps({"systemMessage": msg.split("\n")[0],
                          "hookSpecificOutput": {"hookEventName": ev, "additionalContext": msg}}, ensure_ascii=False)


def staged_files(root):
    """[(옛 경로|None, 새 경로)] — 스테이지의 더함·고침·이름 바꿈."""
    r = subprocess.run(["git", "-c", "core.quotepath=off", "diff", "--cached", "--name-status", "-M", "--diff-filter=ACMR"],
                       cwd=root, capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode("utf-8", "replace").strip())
    out = []
    for ln in r.stdout.decode("utf-8", "replace").splitlines():
        f = ln.split("\t")
        if len(f) >= 2:
            out.append((f[1] if f[0][0] in "RC" else (None if f[0][0] == "A" else f[1]), f[-1]))
    return out


def blob(root, spec):
    r = subprocess.run(["git", "show", spec], cwd=root, capture_output=True)
    if r.returncode or b"\0" in r.stdout[:65536]:
        return None
    return r.stdout.decode("utf-8", "replace")


# ── git 훅 설치 ───────────────────────────────────────────────

def install_hook(repo, vault, conf_vault):
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=repo, capture_output=True)
    if top.returncode:
        print("git 저장소가 아님: %s" % repo)
        return 2
    root = norm(top.stdout.decode("utf-8", "replace").strip())
    if root == norm(conf_vault):
        print("볼트 저장소에는 걸지 않는다(자동 커밋·노트 커밋을 막지 않게) — 볼트 제품 경로는 Claude Code 훅이 본다")
        return 2
    hp = subprocess.run(["git", "rev-parse", "--git-path", "hooks"], cwd=root, capture_output=True).stdout.decode().strip()
    hp = hp if os.path.isabs(hp) else os.path.join(root, hp)
    os.makedirs(hp, exist_ok=True)
    f = os.path.join(hp, "pre-commit")
    if os.path.exists(f) and MARK not in read(f):
        print("다른 pre-commit 이 있음 — 덮지 않음: %s" % f)
        return 2
    me = norm(os.path.abspath(__file__))
    extra = "" if norm(vault) == norm(VAULT) else ' --vault "%s"' % norm(vault)
    body = ("#!/bin/sh\n%s — 제품 저장소에 개인 값이 새로 들어가는 커밋을 막는다(incident-2026-11-22)\n"
            "py -3 \"%s\" --staged --repo-product%s\nr=$?\n"
            "if [ $r -eq 1 ]; then exit 1; fi\n"
            "if [ $r -ne 0 ]; then echo \"privguard: 검사 못 함(끝 코드 $r) — 커밋은 막지 않음\" >&2; fi\nexit 0\n") % (MARK, me, extra)
    with open(f, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body)
    try:
        os.chmod(f, 0o755)
    except OSError:
        pass
    c = load_conf(conf_vault)
    repos = [norm(x) for x in c.get("repos") or []]
    if root not in repos:
        c["repos"] = repos + [root]
        save_conf(conf_vault, c)
    print("걸었음: %s" % f)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="제품 경로에 새로 들어가는 개인 값 검사")
    ap.add_argument("cmd", nargs="?", choices=["install-hook", "rules"])
    ap.add_argument("target", nargs="?")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--diff")
    ap.add_argument("--file")
    ap.add_argument("--text")
    ap.add_argument("--tree")
    ap.add_argument("--hook", action="store_true")
    ap.add_argument("--repo-product", action="store_true", help="저장소 전체가 제품(개인화 파트만 뺌)")
    ap.add_argument("--vault", default=VAULT)
    ap.add_argument("--rules", help="꼴 파일(«정규식<TAB>갈래») — 볼트 꼴 대신(시험)")
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args(argv)
    vault = os.path.abspath(a.vault)
    conf = load_conf(vault)

    def rules_loader():
        return load_rules_file(a.rules) if a.rules else build_rules(vault, a.refresh)

    try:
        if a.cmd == "install-hook":
            return install_hook(a.target or ".", vault, vault)
        if a.cmd == "rules":
            rules, allow = rules_loader()
            by = {}
            for _, lb in rules:
                by[lb] = by.get(lb, 0) + 1
            for lb, c in sorted(by.items()):
                print("%s\t%d" % (lb, c))
            kv = read(local(vault, AUTO)).splitlines()[1:]
            print("지식 값 %d · 허용 %d" % (len(kv), len(allow)))
            return 0
        if a.hook:
            try:
                raw = sys.stdin.buffer.read().decode("utf-8", "replace")
                data = json.loads(raw or "{}")
                if not isinstance(data, dict):
                    raise ValueError("입력이 JSON 객체가 아님")
                code, msg = hook(data, vault, rules_loader, conf)
            except Exception as e:  # noqa: BLE001
                return hook_failed(vault, e)
            if msg:
                (sys.stderr if code == 2 else sys.stdout).write(msg + "\n")
            return code
        recs = []
        if a.staged:
            root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True).stdout.decode("utf-8", "replace").strip() or "."
            todo = []
            for old_rel, rel in staged_files(root):
                full = os.path.join(root, rel)
                if (a.repo_product and not personal_part(full, root)) or (not a.repo_product and product_kind(full, vault, conf)):
                    new = blob(root, ":" + rel)
                    if new is not None:
                        todo.append((rel, (blob(root, "HEAD:" + old_rel) or "") if old_rel else "", new))
            hits = []
            if todo:
                rules, allow = rules_loader()
                comp = comp_of(rules)
                for rel, old, new in todo:
                    hits += grown(rel, old, new, comp, allow)
            report(hits)
            if hits:
                print("privguard: 커밋 거절 — 개인 값이 %d가지 늘어남. %s" % (len(hits), ADVICE), file=sys.stderr)
            return 1 if hits else 0
        if a.diff:
            root = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True).stdout.decode("utf-8", "replace").strip()
            diff = git_diff(root or ".", a.diff)
            for rel, n, ln in added_from_diff(diff):
                full = os.path.join(root, rel)
                if (a.repo_product and not personal_part(full, root)) or (not a.repo_product and product_kind(full, vault, conf)):
                    recs.append((rel, n, ln))
        elif a.file:
            new = read(a.text) if a.text else sys.stdin.read()
            if product_kind(a.file, vault, conf):
                recs = [(a.file, n, ln) for n, ln in new_lines(read(a.file), new)]
        elif a.tree:
            ship = dd.load_ship(vault)
            root = os.path.abspath(a.tree)
            whole = norm(root) in [norm(r) for r in conf.get("repos") or []]
            ls = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-z"], cwd=root, capture_output=True)
            files = [x for x in ls.stdout.decode("utf-8", "replace").split("\0") if x] if not ls.returncode else \
                [os.path.relpath(os.path.join(dp, f), root) for dp, _, fs in os.walk(root) for f in fs]
            for rel in files:
                full = os.path.join(root, rel)
                ok = (not personal_part(full, root)) if whole else bool(product_kind(full, vault, conf, ship))
                if not ok or not dd.text_encoding(full):
                    continue
                recs += [(rel.replace("\\", "/"), i, ln) for i, ln in enumerate(read(full).splitlines(), 1)]
        else:
            ap.print_help()
            return 2
        if not recs:
            return 0
        rules, allow = rules_loader()
        hits = scan(recs, rules, allow)
        report(hits)
        if hits and a.diff:
            print("privguard: 커밋 거절 — 추가된 줄 %d곳에 개인 값. %s" % (len(hits), ADVICE), file=sys.stderr)
        return 1 if hits else 0
    except Exception as e:  # noqa: BLE001 — 훅에서 터지면 «검사 못 함»(2)으로 알린다
        print("privguard: 검사 못 함 — %s" % e, file=sys.stderr)
        return 1 if a.hook else 2     # 훅에서 2 는 «막음»(Claude 에게 오류로 감) — 검사 못 함은 1(사람에게만 보이는 오류)


if __name__ == "__main__":
    if "--hook" in sys.argv:
        # 훅에서는 어떤 끝도 2 가 되지 않게 — 인자 오류(argparse 는 2 로 끝남)·예상 밖 끝은 «못 잼» 통과
        try:
            code = main()
        except SystemExit as e:
            code = hook_failed(VAULT, RuntimeError("인자 오류 %s" % e.code)) if e.code not in (0, None) else 0
        except BaseException as e:  # noqa: BLE001
            code = hook_failed(VAULT, e)
        sys.exit(code if code in (0, 2) else 0)
    sys.exit(main())
