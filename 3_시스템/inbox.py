# -*- coding: utf-8 -*-
"""**inbox** — 받은함 정리(볼트 개혁 R9 · 설계안 §13.3 B3 · 2026-10-30 · 11-02 개정).

왜: 받은함은 08-21 뒤 69일 동안 새로 든 것이 0 이었다(§13.1) — 들어와도 사람이 손으로 옮겨야 해서 받는 길이
막혀 있었다. 들어온 것마다 «같은 내용이 이미 있나 · 어느 주제·어느 하위 칸인가 · 얼마나 확실한가»를 정한다.
11-02(사용자): 보고서 쓰려고 넣은 사진·측정·코드는 1회용이다 — 원본 층에 들이지 않는다 · 폴더를 통째로 옮기지 않고 안을 본다.
  문서(pdf·hwp·pptx …) = 원본 → `<과목>/<칸>` · 재료(사진·측정·코드·영상) = 작업 자리(끝난 작업이 쓴 것이면 휴지통)
  · 같은 내용 = 휴지통 · 빈 폴더 = 치움 · 문서 섞인 폴더 = 풀기 · md 아이디어 승격은 Claude 몫(conventions §원본·색인).
11-03(사용자): 받은함은 정거장이다 — Claude 가 확인했으면 비운다. 휴지통도 Claude 가 한다(되살릴 수 있고 장부에 남는다).
나머지는 «제안»으로 남긴다. 항목 하나 = fileops 계획 한 묶음(한 번에 되돌림).

  py -3 3_시스템/inbox.py [--json]              제안만(아무것도 옮기지 않음)
  py -3 3_시스템/inbox.py --apply [--by 누가]    확신 «높음»을 모두 실행(옮김·휴지통·치움)
  py -3 3_시스템/inbox.py --do <이름> [--by 누가] 한 항목을 제안대로(고른 것이라 확신은 안 본다)
  py -3 3_시스템/inbox.py --take <이름> <새 자리> 고른 자리로(원본이면 색인까지 · 작업에 쓸 재료 = `<작업 폴더>/재료`)

자리는 역할로(받은함 = inbox · 학교 원본 = school · 주제 자리 = topic_roots) — R9 구조 이전 뒤에도 그대로 돈다.
"""
import argparse
import json
import os
import posixpath
import re
import subprocess
import sys
import tempfile
import time
import unicodedata

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import roles  # noqa: E402
import fileops  # noqa: E402
import work  # noqa: E402

PY = sys.executable
DOCS = {".pdf", ".docx", ".doc", ".hwp", ".hwpx", ".pptx", ".ppt", ".html", ".htm", ".zip"}  # 문서 = 받은 원본
# 재료 표는 work.json(재료_확장자 · 다시_만듦) + 여기(소리·영상·글 코드)
MORE_MATERIAL = {".mp4", ".mov", ".avi", ".mkv", ".m4a", ".mp3", ".wav", ".txt", ".c", ".cpp", ".h", ".hpp", ".java", ".m", ".xdc", ".tcl"}
# 사진으로 받아도 원본인 것 — «시험»·«final» 은 뺐다(시험 데이터.csv · ana_final.py 에 걸린다)
KEEP_WORDS = ["족보", "기출", "공지", "중간고사", "기말고사"]
SCHOOL = ("배움", "학교")  # 학교 = 10-31 전 영역 이름(설계안 §19.2)
JUNK = ("desktop.ini", "thumbs.db")  # fileops 빈 폴더 판정과 같은 표
TEXTS = (".py", ".md", ".json", ".txt", ".ipynb", ".ps1", ".mjs", ".js", ".ts", ".sh", ".bat", ".tex", ".m", ".yaml", ".yml", ".toml")
# 원본 묶음의 고정 하위(설계안 §1.1 R4)를 고르는 낱말 — 앞에서부터 먼저 맞는 것(제출본이 «과제»보다 먼저)
SUB_WORDS = [
    ("제출", ["제출", "최종본", "submitted"]),
    ("족보", ["족보", "기출"]),
    ("시험", ["시험", "중간", "기말", "퀴즈", "quiz", "exam", "midterm", "final"]),
    ("과제", ["과제", "숙제", "레포트", "보고서", "report", "assignment", "homework", "hw"]),
    ("공지", ["공지", "안내", "notice"]),
    ("강의자료", ["강의", "주차", "lecture", "slide", "slides", "chap", "chapter", "week"]),
]
LECTURE_NO = re.compile(r"제\s*\d+\s*강|\d+\s*강(?![가-힣])")  # «제11강»·«3강» — 낱말 표(휴강·보강과 겹침)로는 못 잡는다(11-03 «동남아 제11강» 이 받은함에 남음)


def rel(a):
    return os.path.relpath(a, VAULT).replace("\\", "/")


def abspath(r):
    return os.path.join(VAULT, *r.split("/"))


def word_hit(w, s):
    """라틴 낱말은 낱말 경계로(«hw» 가 «hwp» 에 걸리지 않게) · 한글은 들어 있으면."""
    if re.search(r"[a-z]", w):
        return re.search(r"(?<![a-z])%s\d*(?![a-z])" % re.escape(w), s) is not None
    return w in s


def topic_of_text(s):
    """글자 안 주제 이름·별칭(긴 것부터) → (정식 이름, 맞은 글자) · 없으면 (None, None)."""
    s = s.lower()
    pairs = sorted(((n, t["이름"]) for t in roles.topics() for n in [t["이름"]] + list(t.get("별칭") or [])), key=lambda x: -len(x[0]))
    for n, c in pairs:
        if len(n) >= 2 and word_hit(n.lower(), s):
            return c, n
    return None, None


def sub_of(s):
    s = s.lower()
    for sub, words in SUB_WORDS:
        for w in words:
            if word_hit(w.lower(), s):
                return sub, w
    m = LECTURE_NO.search(s)
    return ("강의자료", m.group()) if m else (None, None)


def topic_row(topic):
    return next((x for x in roles.topics() if x["이름"] == topic), {})


def school_dir(topic):
    """학교 원본 자리의 그 주제 폴더 — 있는 이름(정식·별칭) 먼저 · 없으면 정식 이름."""
    school = roles.path("school")
    for n in [topic] + list(topic_row(topic).get("별칭") or []):
        if os.path.isdir(os.path.join(VAULT, *school.split("/"), n)):
            return school + "/" + n
    return school + "/" + topic


def work_dir(topic):
    """작업 자리 — 주제 자리 가운데 작업 층(영역 단이 있으면 그 영역 · R9 뒤)."""
    w = roles.path("work")
    t = topic_row(topic)
    roots = [r for r in roles.config().get("topic_roots", []) if r == w or r.startswith(w + "/")]
    area = [r for r in roots if r.rsplit("/", 1)[-1] == t.get("영역")]
    return (area or roots or [w])[0] + "/" + topic


def peek(a, n=4000):
    try:
        with open(a, encoding="utf-8", errors="replace") as f:
            return f.read(n)
    except OSError:
        return ""


def material_exts():
    r = work.rules()
    return set(r["재료_확장자"]) | set(r["다시_만듦"]["확장자"]) | MORE_MATERIAL


def kind_of(name):
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    if ext == ".md":
        return "md"
    if ext in DOCS or any(w in stem.lower() for w in KEEP_WORDS):
        return "문서"
    return "재료"


class Same:
    """같은 내용 찾기 — 볼트 크기 색인을 한 번만 만들고 같은 크기만 해시를 잰다.
    받은함·휴지통 안은 근거가 못 된다(서로를 근거로 둘 다 지워지는 일을 막는다) · 빈 파일은 같다고 보지 않는다."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.sizes = None
        self.hashes = {}

    def _sha(self, a):
        if a not in self.hashes:
            self.hashes[a] = fileops.sha256(a)
        return self.hashes[a]

    def of(self, a):
        """이 파일과 같은 내용의 볼트 상대 경로 · 없으면 None."""
        if self.sizes is None:
            self.sizes = {}
            skip = (fileops.LEDGER_DIR + "/", "3_시스템/_index/", roles.path("source_index") + "/", roles.path("inbox") + "/")
            for r in fileops.walk_vault(self.ctx, skip_rel=skip):
                try:
                    self.sizes.setdefault(os.path.getsize(self.ctx.abs(r)), []).append(r)
                except OSError:
                    pass
        try:
            size = os.path.getsize(a)
            cands = self.sizes.get(size, []) if size else []
            if not cands:
                return None
            for r in cands:
                if self._sha(self.ctx.abs(r)) == self._sha(a):
                    return r
        except OSError:
            pass
        return None


def arrived(a, files):
    """받은함에 들어온 때 — 만든 때(윈도)와 안 파일의 마지막 수정 가운데 늦은 쪽."""
    return max([os.path.getctime(a)] + [os.path.getmtime(f) for f in files])


def used_by(topic, name, dups, since):
    """이 받은 것을 쓴 작업(그 주제) — 작업 안 글 파일이 받은함 경로를 적었거나, 같은 내용 파일이 작업 안에 있거나 → 판정 붙은 작업들.
    들어오기(since) 전에 쓴 글은 근거가 못 된다 — 같은 이름 폴더를 매주 넣는다(실험 과목: 실험6 대본이 실험7 재료를 버리게 하면 안 된다)."""
    needle = unicodedata.normalize("NFC", roles.path("inbox").rsplit("/", 1)[-1] + "/" + name)
    rx = re.compile(re.escape(needle) + r"(?=$|[/\s'\"`)\],:;])", re.M)
    out = []
    for t in work.tasks():
        if t["topic"] != topic:
            continue
        used = any(d and (d == t["path"] or d.startswith(t["path"] + "/")) for d in dups)
        if not used:
            for f in work.files_of(abspath(t["path"])):
                try:
                    if not f.lower().endswith(TEXTS) or os.path.getsize(f) > 2 << 20 or os.path.getmtime(f) < since:
                        continue
                    with open(f, encoding="utf-8", errors="replace") as h:
                        s = unicodedata.normalize("NFC", h.read()).replace("\\\\", "/").replace("\\", "/")
                except OSError:
                    continue
                if rx.search(s):
                    used = True
                    break
        if used:
            try:
                out.append(work.judge(dict(t), {"stop": roles.retention("작업멈춤")}))
            except Exception:  # noqa: BLE001 — 판정이 깨지면 «끝남»으로 보지 않는다(버리지 않는 쪽)
                out.append(dict(t, state="?", why=""))
    return out


def free(dst, taken=None, isdir=False):
    """비어 있는 자리 — 겹치면 « 2» · taken = 이 계획에서 이미 잡은 자리."""
    taken = set() if taken is None else taken
    stem, ext = (dst, "") if isdir else posixpath.splitext(dst)
    cand, k = dst, 2
    while cand in taken or os.path.exists(abspath(cand)):
        cand = "%s %d%s" % (stem, k, ext)
        k += 1
    taken.add(cand)
    return cand


def op_mv(src, dst, why):
    return {"op": "mv", "src": src, "dst": dst, "why": "받은함 정리 — " + why}


def op_rm(src, why, count=None):
    return {"op": "rm", "src": src, "why": "받은함 정리 — " + why, "user_asked": True, **({"count": count} if count else {})}


def op_rmdir(src, why):
    return {"op": "rmdir", "path": src, "why": "받은함 정리 — " + why}


def place_material(out, name, topic, hit, dups, since, known=True, has_md=False):
    """재료(폴더째 또는 낱파일) — 끝난 작업이 썼으면 휴지통 · 쓰는 중이면 그 작업 안으로 제안 · 쓴 작업이 없으면 작업 자리."""
    src, isdir = out["src"], out["kind"] == "폴더"
    used = used_by(topic, name, dups, since)
    busy = [u for u in used if u.get("state") not in work.DONE]
    done = [u for u in used if u.get("state") in work.DONE]
    if busy:
        b = busy[0]
        dst = free((b["path"] if b.get("dir") else work_dir(topic)) + "/" + name, isdir=isdir)
        why = "재료 — «%s» 쓰는 중" % b["name"]
        out.update(act="재료", dst=dst, sure="보통", why=why, ops=[op_mv(src, dst, why)])
    elif done:
        why = "재료 — «%s» 끝남" % done[0]["name"]
        out.update(act="버림", sure="보통" if has_md else "높음", why=why + (" · md 가 섞임" if has_md else ""),
                   ops=[op_rm(src, why, out["n"] if isdir else None)])
    else:
        dst = free(work_dir(topic) + "/" + name, isdir=isdir)
        why = "이름 «%s» → %s · 재료 → 작업 자리" % (hit, topic)
        out.update(act="재료", dst=dst, sure="높음" if known else "낮음", why=why, ops=[op_mv(src, dst, why)])
    return out


def classify_file(out, name, a, same):
    stem, ext = os.path.splitext(name)
    ext = ext.lower()
    dup = same.of(a)
    if dup:
        why = "같은 내용이 이미 있음"
        out.update(dup=dup, act="버림", sure="높음", why=why, ops=[op_rm(out["src"], why)])
        return out
    kind = kind_of(name)
    if kind == "md":
        topic, hit = topic_of_text(stem + "\n" + peek(a))
        out.update(why="md = %s 적은 아이디어 노트면 승격은 Claude(conventions)" % roles.me("이") + (" · 주제 «%s»" % topic if topic else ""))
        return out
    topic, hit = topic_of_text(stem)
    if not topic:
        out["why"] = "이름에서 주제를 못 찾음"
        return out
    if kind == "재료":
        return place_material(out, name, topic, hit, [], arrived(a, [a]), known=ext in material_exts())
    t = topic_row(topic)
    if t.get("영역") not in SCHOOL:
        dst = free(work_dir(topic) + "/" + name)
        why = "주제 «%s»(%s) — 원본 자리가 없는 영역이라 작업 자리 제안" % (topic, t.get("영역"))
        out.update(act="재료", dst=dst, why=why, ops=[op_mv(out["src"], dst, why)])
        return out
    sub, w = sub_of(stem)
    base = school_dir(topic)
    dst = free("%s/%s/%s" % (base, sub, name) if sub else "%s/%s" % (base, name))
    why = "이름 «%s» → %s · «%s» → %s" % (hit, topic, w, sub) if sub else "이름 «%s» → %s · 하위 칸 못 정함" % (hit, topic)
    out.update(act="원본", dst=dst, sure="높음" if sub else "보통", why=why, ops=[op_mv(out["src"], dst, why)])
    return out


def topic_of_dir(name, files):
    """폴더 이름 먼저 · 없으면 안 파일 이름(한 주제로 모일 때만)."""
    topic, hit = topic_of_text(name)
    if topic:
        return topic, hit
    hits = [topic_of_text(os.path.splitext(os.path.basename(f))[0]) for f in files]
    topics = {t for t, _ in hits if t}
    if len(topics) == 1:
        return next(h for h in hits if h[0])
    return None, None


def classify_dir(out, name, a, same):
    """폴더는 통째로 옮기지 않는다 — 안을 본다(11-02)."""
    src = out["src"]
    files = [f for f in fileops.files_under(a) if os.path.basename(f).lower() not in JUNK]
    out["n"] = len(files)
    if not files:
        out.update(act="지움", sure="높음", why="빈 폴더", ops=[op_rmdir(src, "빈 폴더")])
        return out
    dups = {f: same.of(f) for f in files}
    if all(dups.values()):
        why = "안의 %d개 모두 같은 내용이 이미 있음" % len(files)
        out.update(act="버림", sure="높음", why=why, dup=next(iter(dups.values())), ops=[op_rm(src, why, len(files))])
        return out
    topic, hit = topic_of_dir(name, files)
    if not topic:
        out["why"] = "폴더·안 파일 이름에서 주제를 못 찾음"
        return out
    kinds = {f: kind_of(os.path.basename(f)) for f in files}
    docs = [f for f in files if kinds[f] == "문서"]
    if not docs:
        return place_material(out, name, topic, hit, list(dups.values()), arrived(a, files), has_md="md" in kinds.values())
    t = topic_row(topic)
    if t.get("영역") not in SCHOOL:
        dst = free(work_dir(topic) + "/" + name, isdir=True)
        why = "주제 «%s»(%s) — 원본 자리가 없는 영역이라 작업 자리 제안" % (topic, t.get("영역"))
        out.update(act="재료", dst=dst, why=why, ops=[op_mv(src, dst, why)])
        return out
    # 문서 섞인 폴더 = 풀기 — 문서는 칸으로 평평하게 · 재료는 작업 자리(끝난 작업이 썼으면 휴지통) · 끝에 빈 폴더 치움
    base, folder_sub = school_dir(topic), sub_of(name)[0]
    used = used_by(topic, name, list(dups.values()), arrived(a, files))
    mat_done = bool(used) and all(u.get("state") in work.DONE for u in used)
    busy = next((u for u in used if u.get("state") not in work.DONE and u.get("dir")), None)
    mat_base = free((busy["path"] if busy else work_dir(topic)) + "/" + name, isdir=True)
    ops, taken, sure = [], set(), "높음"
    for f in files:
        r = rel(f)
        if dups[f]:
            ops.append(op_rm(r, "같은 내용이 이미 있음"))
        elif kinds[f] == "문서":
            sub = sub_of(os.path.splitext(os.path.basename(f))[0])[0] or folder_sub
            sure = sure if sub else "보통"
            ops.append(op_mv(r, free("%s/%s%s" % (base, sub + "/" if sub else "", os.path.basename(f)), taken), "폴더 풀기 · 문서 → %s" % (sub or topic)))
        elif mat_done:
            ops.append(op_rm(r, "재료 — 쓴 작업 끝남"))
        else:
            ops.append(op_mv(r, mat_base + r[len(src):], "폴더 풀기 · 재료 → 작업 자리"))
    ops.append(op_rmdir(src, "안을 다 풀었음"))
    out.update(act="풀기", sure=sure if not busy else "보통", why="이름 «%s» → %s · 문서 %d · 재료 %d" % (hit, topic, len(docs), len(files) - len(docs)), ops=ops)
    return out


def classify_one(name, ctx):
    """받은함 항목 하나 → {dst, why, sure, kind, dup, act, n, ops}. 아무것도 옮기지 않는다."""
    inbox = roles.path("inbox")
    a = os.path.join(VAULT, *inbox.split("/"), name)
    isdir = os.path.isdir(a)
    out = {"name": name, "src": inbox + "/" + name, "kind": "폴더" if isdir else (os.path.splitext(name)[1].lower()[1:] or "?"),
           "days": int((time.time() - os.path.getmtime(a)) / 86400), "dst": None, "why": "", "sure": "낮음", "dup": None,
           "act": "그대로", "n": 1, "ops": []}
    same = ctx.__dict__.setdefault("_same", Same(ctx))
    return (classify_dir if isdir else classify_file)(out, name, a, same)


def items():
    """받은함 항목 — 튜토리얼 연습 파일은 뺀다(brain-base 엔진이 해시를 맞춰 바로 지움 · 정리·장부 0 · fileops.practice_paths)."""
    d = roles.abs("inbox")
    if not os.path.isdir(d):
        return []
    base, (tt, _) = roles.path("inbox"), fileops.practice_paths(VAULT)
    return sorted(p for p in os.listdir(d) if not p.startswith((".", "_")) and not fileops.in_practice(base + "/" + p, tt))


def index_sources(dsts):
    src = roles.path("sources") + "/"
    for dst in dsts:
        if dst.startswith(src):
            subprocess.run([PY, os.path.join(HERE, "ingest.py"), dst], capture_output=True)    # 원본 색인(_색인)


def move(src, dst, why, by):
    r = subprocess.run([PY, os.path.join(HERE, "fileops.py"), "--by", by, "mv", src, dst, "--why", why],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = r.returncode == 0
    if ok:
        index_sources([dst])
    return ok, (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]


def run_item(r, by):
    """제안 하나 = fileops 계획 한 묶음(한 번에 되돌림) → (됨?, 실패면 까닭)."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"title": "받은함 " + r["name"], "ops": r["ops"]}, f, ensure_ascii=False)
    try:
        p = subprocess.run([PY, os.path.join(HERE, "fileops.py"), "--by", by, "plan", f.name, "--apply"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    finally:
        os.remove(f.name)
    text = (p.stdout + p.stderr).strip().splitlines()
    if p.returncode != 0:
        return False, " · ".join(x.strip() for x in text if x.startswith("✗") or "멈추기 전" in x) or (text[-1] if text else "fileops 실패")
    index_sources([o["dst"] for o in r["ops"] if o["op"] == "mv"])
    return True, ""


DONE_TAG = {"버림": "휴지통", "지움": "빈 폴더 치움"}


def execute(rows, picked, by):
    """고른 제안을 실행 — 한 항목이 실패해도 다음 항목은 한다 · 요약이 마지막 줄(홈 알림이 끝 줄을 쓴다) → 실패 수."""
    n = {"옮김": 0, "휴지통": 0, "빈 폴더": 0, "실패": 0}
    for r in rows:
        if r["name"] not in picked or not r["ops"]:
            r["tag"] = "남음"
        else:
            ok, why = run_item(r, by)
            r["moved"] = ok
            if ok:
                r["tag"] = DONE_TAG.get(r["act"], "옮김")
                n[{"버림": "휴지통", "지움": "빈 폴더"}.get(r["act"], "옮김")] += 1
            else:
                r["tag"], r["why"] = "실패", why
                n["실패"] += 1
    left = sum(1 for r in rows if r["tag"] == "남음")
    return n, left


def main(argv=None):
    ap = argparse.ArgumentParser(description="받은함 정리 — 제안 · 확실한 것만 실행")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--apply", action="store_true", help="확신 «높음»만 실행한다")
    ap.add_argument("--do", metavar="이름", help="한 항목을 제안대로")
    ap.add_argument("--take", nargs=2, metavar=("이름", "새자리"), help="사람이 고른 자리로")
    ap.add_argument("--by", default="script:inbox", help="장부의 «누가»")
    a = ap.parse_args(argv)
    if a.take:
        name, dst = a.take
        ok, last = move(roles.path("inbox") + "/" + name, dst, "받은함 → 사람이 고른 자리", a.by)
        print(("옮김 " if ok else "실패 ") + last[0])
        return 0 if ok else 1
    ctx = fileops.Ctx(VAULT, by=a.by, dry=True)
    names = items()
    if a.do and a.do not in names:
        print("받은함에 없음: %s" % a.do)
        return 1
    rows = [classify_one(n, ctx) for n in names]
    n, left = None, 0
    if a.do:
        n, left = execute(rows, {a.do}, a.by)
    elif a.apply:
        n, left = execute(rows, {r["name"] for r in rows if r["sure"] == "높음"}, a.by)
    moved = [r["name"] for r in rows if r.get("moved")]
    if a.json:
        print(json.dumps({"count": len(rows), "oldest": max((r["days"] for r in rows), default=None), "moved": moved, "items": rows}, ensure_ascii=False))
        return 1 if n and n["실패"] else 0
    if n is None:
        print("받은함 %d개" % len(rows))
    for r in rows:
        print("- [%s] %s (%d일) → %s · %s" % (r.get("tag") or "%s·%s" % (r["act"], r["sure"]), r["name"], r["days"], r["dst"] or {"버림": "휴지통", "지움": "치움", "풀기": "풀기"}.get(r["act"], "그대로"), r["why"]))
    if n is not None:
        print("받은함 정리 · 옮김 %d · 휴지통 %d · 남음 %d%s%s" % (n["옮김"], n["휴지통"], left, " · 빈 폴더 %d" % n["빈 폴더"] if n["빈 폴더"] else "", " · 실패 %d" % n["실패"] if n["실패"] else ""))
        return 1 if n["실패"] else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
