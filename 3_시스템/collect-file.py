# -*- coding: utf-8 -*-
"""로그인 가족 파일화(어댑터 canvas·learningx 의 원시) — 확장이 다운로드 폴더에 떨군 원시 JSON·첨부를 볼트로 옮긴다(결정적 · Claude 가 본문을 만지지 않음).
조리법 칸 filer = collect-file.py 인 출처를 collect-browser.py 가 부른다(11-16 S7 · 옛 개인 층 학교 전용 파일화 대본을 본체로). 자리·머리·이름은 로그인 조리법(collect/browser/<id>.json)에서.

    py -3.11 3_시스템/collect-file.py --source <id> --run <run> --since <epoch> [--course <과목 번호>]

- 원시 JSON → 원본 층 원시 칸(조리법 raw_dir · 진짜 원본, git 제외) · 원시 이름 머리 = 조리법 raw_prefix.
- 공지·과제·첨부 없는 게시글 → `<units_root 역할>/<과목>/<공지|과제>/<날짜> <제목>.md` · 수업계획서 → `<과목>/강의자료/` — 본문은 받은 글자 그대로.
  과목 바로 밑 종류 폴더(강의자료·과제·공지·시험·제출)에 둔다 — 수집 전용 폴더를 따로 만들지 않는다(10-25 결정).
- 첨부 → 받은 파일 검사(본체 filecheck) → `<units_root 역할>/<과목>/<이름>` + 옆 짝메모 `<basename>.md`(그 글 원본 그대로). 종류 폴더로는 정리 때 옮긴다.
  같은 해시가 이미 있으면 들이지 않고, 기존 원본 옆에 짝메모가 없을 때만 쓴다(있으면 그 옆 `<basename> (짝메모).md`).
- 받은 항목은 조리법 manifest(파일화 장부)에 남겨 다음 수집 때 건너뛴다. 원본은 덮어쓰지 않는다(바뀌면 새 파일).
- 받은 뒤 수정된 게시판 글(`rev`)은 새 파일로 다시 받는다 · 모듈의 외부 도구 항목(대체 강의 등)은 `<과목>/강의자료/<모듈> <제목>.md` 한 편.
조리법 칸 뜻 = collect-browser.py 머리글.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import unicodedata

VAULT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYS = os.path.join(VAULT, "3_시스템")
sys.path.insert(0, SYS)
import collectlib as cl  # noqa: E402 — 로그인 조리법 읽기(S6)
import filecheck as intake  # noqa: E402 — 받은 파일 검사(본체 · 11-16 · 옛 개인 lms-intake 가 같은 이름을 내주던 것)
import fileops  # noqa: E402 — 볼트에 들이는 것은 장부에(볼트 개혁 R6.3 · by script:collect-file)
import roles  # noqa: E402 — 학교 원본 자리는 역할(school)로 — 구조를 옮겨도 따라감(R9-b)
MANIFEST = COURSES = RAW = SCHOOL = ""     # configure() 가 조리법에서 채운다
SID, PREFIX, LABEL = "", "", ""


def configure(sid=None):
    """로그인 조리법에서 자리를 읽는다 — manifest(파일화 장부) · units(단위 지도) · raw_dir(원본 층 원시 칸) · units_root(단위 폴더 역할) · raw_prefix · name.
    sid 가 없으면 조리법이 하나일 때만 그것(둘 이상이면 --source 를 받아야 한다)."""
    global MANIFEST, COURSES, RAW, SCHOOL, SID, PREFIX, LABEL
    rs = [r for r in cl.browser_recipes(SYS) if not sid or r.get("id") == sid]
    if len(rs) != 1:
        raise SystemExit(f"로그인 조리법 {'없음' if not rs else '여럿 — --source 를 준다'}: {sid or 'collect/browser/*.json'}")
    rc = rs[0]
    SID = rc["id"]
    MANIFEST = cl.rpath(rc.get("manifest") or f"_index/{SID}/manifest.json", SYS)
    COURSES = cl.rpath(rc.get("units") or f"collect/browser/{SID}/units.json", SYS)
    RAW = roles.abs("sources", rc.get("raw_dir") or "_" + SID)
    SCHOOL = roles.abs(rc.get("units_root") or "school")
    PREFIX = rc.get("raw_prefix") or SID + "-"
    LABEL = f"{rc.get('name') or SID} 수집"


def h(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def safe(name: str, n: int = 120) -> str:
    s = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", (name or "").strip()).strip(". ")
    return (s or "제목없음")[:n]


def y(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def ledger(entry: dict):
    """행위 장부(brain.py 와 같은 파일 · 덧붙이기만) — 조용히 빠진 일을 한 줄 남긴다."""
    os.makedirs(os.path.join(SYS, "ledger"), exist_ok=True)
    with open(os.path.join(SYS, "ledger", "actions.jsonl"), "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "by": "script:collect-file", **entry}, ensure_ascii=False) + "\n")


def write_new(path: str, text: str) -> str:
    """원본 불변: 이미 있으면 덮지 않고 « (n)» 을 붙인 새 파일."""
    base, ext = os.path.splitext(path)
    p, i = path, 1
    while os.path.exists(p):
        i += 1
        p = f"{base} ({i}){ext}"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return p


def md(front: dict, title: str, body: str, links=None, attachments=None) -> str:
    lines = ["---", f"created: {time.strftime('%Y-%m-%d')}", "source: 수집"]  # source = user|claude|수집(10-30) · 어디서 = lms 칸
    lines += [f"{k}: {y(v)}" for k, v in front.items() if v not in (None, "", [], {})]
    lines += ["---", f"# {title}", "", body or ""]
    if attachments:
        lines += ["", "## 첨부", *[f"- {a}" for a in attachments]]
    if links:
        lines += ["", "## 원문 링크", *[f"- {l.get('text', '')} — {l.get('href', '')}" for l in links]]
    return "\n".join(lines).rstrip() + "\n"


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s or "")


def lsig(links) -> str:
    """본문 속 링크 주소들의 지문 — 파일 링크의 verifier 는 받을 때마다 바뀔 수 있어 뺀다. 링크가 없으면 빈 글자."""
    hs = sorted({re.sub(r"[?&]verifier=[^&#]*", "", (l or {}).get("href") or "") for l in links or []})
    return h("\n".join(hs)) if hs else ""


def variants(name: str):
    b, e = os.path.splitext(nfc(name))
    return re.compile(r"^" + re.escape(b) + r"(?:-\d+| \(\d+\))?" + re.escape(e) + r"$", re.I)


def find_download(dl_dir, since, names, size=None, taken=set()):
    # Canvas 파일명은 NFD(맥에서 올린 한글)일 수 있고 디스크는 NFC — 둘 다 NFC 로 비교(10-25 과목D 9개 누락)
    pats = [variants(n) for n in names if n]
    for p in sorted(glob.glob(os.path.join(dl_dir, "*")), key=os.path.getmtime):
        if p in taken or not os.path.isfile(p) or os.path.getmtime(p) < since or p.endswith((".crdownload", ".tmp")):
            continue
        fn = nfc(os.path.basename(p))
        if size is not None and os.path.getsize(p) != size:
            continue
        if any(pt.match(fn) for pt in pats):
            return p
    return None


class Run:
    def __init__(self, a):
        self.a = a
        self.courses = json.load(open(COURSES, encoding="utf-8"))
        self.man = json.load(open(MANIFEST, encoding="utf-8")) if os.path.exists(MANIFEST) else {}
        for k in ("items", "files", "board"):
            self.man.setdefault(k, {})
        self.q = os.path.join(os.environ.get("TEMP", "."), "collect-quarantine", SID, a.run)
        self.known_hash = intake.vault_hashes()
        self.taken = set()
        self.rep = {"run": a.run, "md": 0, "md_changed": 0, "files_in": 0, "files_dup": 0, "files_quarantined": [],
                    "files_missing": [], "memos": 0, "memo_elsewhere": 0, "courses": {}}

    def folder(self, cid, cname=""):
        return os.path.join(SCHOOL, self.courses.get(str(cid)) or safe(cname or str(cid)))

    def item(self, key, content_hash, path_fn, text, links=None):
        """links = 본문 속 링크 주소의 지문(lsig) — 글자는 그대로고 링크만 고친 글(줌 주소 등)을 다시 쓴다(11-06). 옛 장부(lh 칸 없음)는 쓰지 않고 칸만 채운다."""
        old = self.man["items"].get(key)
        if old and old.get("hash") == content_hash:
            if links is None or old.get("lh") == links:
                return None
            if "lh" not in old:
                old["lh"] = links
                return None
        p = write_new(path_fn(), text)
        self.man["items"][key] = {"hash": content_hash, "path": os.path.relpath(p, VAULT), "run": self.a.run, **({"lh": links} if links is not None else {})}
        self.rep["md_changed" if old else "md"] += 1
        return p

    def take_file(self, cid, src, name, memo_text, fkey, sub=None, body=None):
        """검사 → 들임(또는 중복·격리) → 짝메모. fkey = manifest 파일 키 · sub = 과목 아래 칸(내 제출 = «제출») · body = 다시 받은 글의 본문(이미 같은 본문의 짝메모가 있으면 또 쓰지 않는다)."""
        os.makedirs(self.q, exist_ok=True)
        q = os.path.join(self.q, os.path.basename(src))
        try:
            shutil.move(src, q)
        except OSError as e:                   # 잠긴 파일 하나가 전체를 세우지 않게 — 받기 대상에 남겨 다음에 다시
            self.rep["files_missing"].append({"course": cid, "name": name, "error": str(e)[:80]})
            return False
        ext = os.path.splitext(name)[1].lower()
        problems = []
        with open(q, "rb") as f:
            head = f.read(8)
        if ext in intake.EXEC_EXT:
            problems.append("실행 파일·스크립트")
        if ext in intake.MAGIC and not any(head.startswith(m) for m in intake.MAGIC[ext]):
            problems.append("형식 불일치")
        if ext == ".pdf":
            with open(q, "rb") as f:
                if intake.pdf_risks(f.read())["risky"]:
                    problems.append("PDF 위험 요소")
        if head.startswith(b"PK\x03\x04"):
            z = intake.zip_risks(q)
            if z.get("exec") or z.get("traversal") or z.get("bad_zip") or z.get("macro"):
                problems.append("압축·매크로 위험")
        sha = intake.sha256(q)
        if problems:
            self.rep["files_quarantined"].append({"name": name, "problems": problems, "at": q})
            if fkey.startswith("canvas:"):     # 같은 파일은 다시 받아도 또 걸린다 — 받은 목록에 적어 받기마다 다시 내려받지 않게(11-06 · path 칸 비움 = 볼트에 들인 것 아님). 다시 받으려면 이 키를 장부에서 지운다
                self.man["files"][fkey] = {"sha": sha, "path": "", "quarantined": True, "run": self.a.run}
            return
        dest_dir = os.path.join(self.folder(cid), sub) if sub else self.folder(cid)
        if sha in self.known_hash:
            existing = os.path.join(VAULT, self.known_hash[sha])
            self.rep["files_dup"] += 1
            memo = os.path.splitext(existing)[0] + ".md"
            os.remove(q)                       # 같은 내용이 볼트에 있다 — 격리 사본은 버린다
            target = existing
        else:
            os.makedirs(dest_dir, exist_ok=True)
            target = os.path.join(dest_dir, safe(nfc(name), 150))
            if os.path.exists(target):
                b, e = os.path.splitext(target)
                # 콜론 금지 — Windows 에서 «이름:나머지» 는 파일이 아니라 숨은 데이터 스트림이 된다(10-25 열역학Ⅰ 과제 3개)
                target = f"{b} (lms {re.sub(r'[^0-9A-Za-z_-]', '_', fkey)}){e}"
            fileops.intake(q, target, LABEL, "script:collect-file")
            self.known_hash[sha] = os.path.relpath(target, VAULT)
            self.rep["files_in"] += 1
            memo = os.path.splitext(target)[0] + ".md"
        if body and os.path.exists(memo) and body.strip() in open(memo, encoding="utf-8").read():
            pass                               # 첨부만 다시 받았다 — 글은 그대로
        elif os.path.exists(memo):             # 사람 메모(또는 이전 짝메모)는 덮지 않는다
            memo = write_new(os.path.splitext(memo)[0] + " (짝메모).md", memo_text)
            self.rep["memo_elsewhere"] += 1
        else:
            write_new(memo, memo_text)
            self.rep["memos"] += 1
        self.man["files"][fkey] = {"sha": sha, "path": os.path.relpath(target, VAULT), "run": self.a.run}

    # ── Canvas ──
    def canvas(self, data):
        for c in data.get("courses", []):
            cid = c["id"]
            if self.a.course and str(cid) != str(self.a.course):
                continue
            cname = (c.get("course") or {}).get("name", "")
            base = self.folder(cid, cname)
            cr = self.rep["courses"].setdefault(str(cid), {"name": cname})
            fr = {"course": cname, "course_id": cid}
            syl = c.get("syllabus") or {}
            if syl.get("text"):
                self.item(f"syl:{cid}", h(syl["text"]), lambda: os.path.join(base, "강의자료", "수업계획서.md"),
                          md({**fr, "lms": "canvas-syllabus", "수집": self.a.run}, "수업계획서", syl["text"],
                             links=None))
            texts = {}
            for x in c.get("announcements", []):
                body = md({**fr, "lms": "canvas-announcement", "id": x.get("id"), "url": x.get("html_url"),
                           "posted_at": x.get("posted_at"), "author": (x.get("author") or {}).get("display_name"),
                           "수집": self.a.run}, x.get("title", ""), x.get("_text", ""), x.get("_links"),
                          [f.get("display_name") for f in x.get("attachments") or []])
                texts[("announcement", x.get("id"))] = body
                self.item(f"ann:{x.get('id')}", h(x.get("title", "") + x.get("_text", "")),
                          lambda x=x: os.path.join(base, "공지", f"{(x.get('posted_at') or '')[:10]} {safe(x.get('title'))}.md"), body, lsig(x.get("_links")))
            for x in c.get("assignments", []):
                body = md({**fr, "lms": "canvas-assignment", "id": x.get("id"), "url": x.get("html_url"),
                           "due_at": x.get("due_at"), "unlock_at": x.get("unlock_at"), "lock_at": x.get("lock_at"),
                           "points_possible": x.get("points_possible"), "submission_types": x.get("submission_types"),
                           "updated_at": x.get("updated_at"), "수집": self.a.run}, x.get("name", ""), x.get("_text", ""), x.get("_links"))
                texts[("assignment", x.get("id"))] = body
                self.item(f"asg:{x.get('id')}", h(x.get("name", "") + x.get("_text", "") + str(x.get("due_at"))),
                          lambda x=x: os.path.join(base, "과제", f"{safe(x.get('name'))}.md"), body, lsig(x.get("_links")))
            for fid, f in (c.get("files") or {}).items():
                fkey = f"canvas:{fid}"
                if fkey in self.man["files"]:
                    continue
                meta = f["meta"]
                src = find_download(self.a.downloads, self.a.since, [meta.get("display_name"), meta.get("filename")],
                                    meta.get("size"), self.taken)
                if not src:
                    self.rep["files_missing"].append({"course": cid, "name": meta.get("display_name")})
                    continue
                self.taken.add(src)
                parts = []
                sub = "제출" if any(r.get("kind") == "submission" for r in f.get("refs", [])) else None  # 내 제출 → <과목>/제출/(10-31)
                for r in f.get("refs", []):
                    if r.get("kind") == "submission" and ("assignment", r.get("id")) in texts:
                        parts.append(texts[("assignment", r.get("id"))])
                    elif r.get("kind") == "module":
                        parts.append(md({**fr, "lms": "canvas-module-file", "module": r.get("module"), "item": r.get("item"),
                                         "file_id": meta.get("id"), "수집": self.a.run}, meta.get("display_name", ""), ""))
                    elif (r.get("kind"), r.get("id")) in texts:
                        parts.append(texts[(r.get("kind"), r.get("id"))])
                memo = "\n\n".join(dict.fromkeys(parts)) or md({**fr, "file_id": meta.get("id"), "수집": self.a.run}, meta.get("display_name", ""), "")
                self.take_file(cid, src, meta.get("display_name") or os.path.basename(src), memo, fkey, sub)
            tools = []
            for m in c.get("modules") or []:   # 파일·과제는 위에서 받는다 — 나머지(외부 도구·링크·쪽)는 항목 정보 한 편(내용은 그 도구 안에 있다 · 열지 않는다)
                for it in m.get("items") or []:
                    if it.get("type") in ("File", "Assignment", "SubHeader") or not it.get("id"):
                        continue
                    tools.append(it["id"])
                    body = md({**fr, "lms": "canvas-module-item", "type": it.get("type"), "module": m.get("name"), "id": it.get("id"), "url": it.get("html_url"),
                               "external_url": it.get("external_url"), "content_details": it.get("content_details"), "수집": self.a.run}, it.get("title", ""), "")
                    self.item(f"modi:{it['id']}", h(f"{it.get('type')}|{it.get('title')}|{it.get('external_url')}|{m.get('name')}"),   # 완료 여부처럼 나만의 칸은 뺀다
                              lambda m=m, it=it: os.path.join(base, "강의자료", f"{safe(m.get('name'), 40)} {safe(it.get('title'))}.md"), body)
            if tools:
                self.man.setdefault("tool_items", {})[str(cid)] = tools
            cr.update({"공지": len(c.get("announcements", [])), "과제": len(c.get("assignments", [])), "파일": len(c.get("files") or {})})

    # ── LearningX 게시판 ──
    def board(self, data):
        cid = data.get("course")
        base = self.folder(cid)
        bk = self.man["board"].setdefault(str(cid), {})
        cr = self.rep["courses"].setdefault(str(cid), {})
        self.xn_probe(cid, data.get("xn"), data.get("capturedAt"))
        for b in data.get("boards", []):
            if "\n" in b["name"] or len(b["name"]) > 40 or (b.get("error") and not b.get("posts")):
                continue                       # 화면 글자를 게시판으로 잘못 짚은 후보(열리지 않음)
            cr.setdefault("게시판", {})[b["name"]] = "건너뜀(학생 게시판)" if b.get("skipped") else f"글 {b.get('seen', 0)} · 새로 {len(b.get('posts', []))}"
            for p in b.get("posts", []):
                if p.get("error"):
                    continue
                m = p.get("meta") or {}          # 화면 라벨 그대로(한국어·영어 화면)
                body = md({"course_id": cid, "lms": "learningx-board", "board": b["name"], "path": p.get("path"),
                           "author": m.get("작성자") or m.get("Name"),  # 게시자 = author(10-30 결정 · Canvas 쪽과 같은 키) — 화면 라벨 원문은 아래에 그대로
                           **m, "목록 등록일시": p.get("list_date"), "수집": self.a.run},
                          p.get("title", ""), p.get("text", ""), p.get("links"), p.get("attachments"))
                atts = p.get("attachments") or []
                rev = p.get("rev")             # 받은 뒤 수정된 글 — 원본은 두고 새 파일로(원본 불변)
                old = bk.get(p["key"]) or {}
                if not atts and old.get("md") and not rev:
                    continue                   # 다시 처리(--rejson)할 때 이미 쓴 글은 건너뜀
                if rev and not atts and old.get("md") and os.path.exists(os.path.join(VAULT, old["md"])) \
                        and (p.get("text") or "").strip() in open(os.path.join(VAULT, old["md"]), encoding="utf-8").read():
                    old["run"], old["at"] = self.a.run, data.get("capturedAt")   # 수정 시각만 바뀌고 글은 그대로 — 다시 열지 않게 시각만 올린다
                    continue
                if not atts:
                    date = (p.get("list_date") or m.get("등록일시") or m.get("Created Date") or "")[:10]
                    kind = "과제" if "과제" in b["name"] else "공지"   # 첨부 없는 글 = 알림(강의자료실 글 포함)
                    pth = write_new(os.path.join(base, kind, f"{date} {safe(p.get('title'))}.md"), body)
                    self.rep["md_changed" if rev else "md"] += 1
                else:
                    pth = None
                    missing = False
                    for name in atts:
                        if f"board:{cid}:{p.get('path')}:{name}" in self.man["files"] and not rev:
                            continue
                        src = find_download(self.a.downloads, self.a.since, [name], None, self.taken)
                        if not src:
                            self.rep["files_missing"].append({"course": cid, "name": name})
                            missing = True
                            continue
                        self.taken.add(src)
                        if self.take_file(cid, src, name, body, f"board:{cid}:{p.get('path')}:{name}", body=p.get("text") if rev else None) is False:
                            missing = True
                    if missing:                # 받은 글로 적지 않는다 — 적으면 다시 열지 않아 첨부가 영영 안 온다(11-03 검토) · 지워진 첨부에 끝없이 매달리지 않게 세 번까지
                        tries = self.man.setdefault("board_tries", {})
                        tries[p["key"]] = tries.get(p["key"], 0) + 1
                        if tries[p["key"]] < 3:
                            continue
                bk[p["key"]] = {"path": p.get("path"), "run": self.a.run, "at": data.get("capturedAt"), "md": os.path.relpath(pth, VAULT) if pth else old.get("md")}

    def xn_probe(self, cid, xn, captured=None):
        """LearningX 모듈 목록 탐침 결과(capture-board) — 원본은 원시 JSON 에 있다. 잰 항목을 적어 다시 재지 않게(새 외부 도구 항목이 생기면 learningx 어댑터가 다시 부른다).
        lectures = 추적하는 항목(대체 강의 등)의 기한·완료 — 일정(schedule.py)과 «완료되기 전까지 다시 재기»(collect-adapters/learningx.py xn_needed)가 읽는다(11-06)."""
        if not xn:
            return
        rec = self.man.setdefault("xn_probe", {}).setdefault(str(cid), {})
        status = {k: (v or {}).get("status") for k, v in xn.items() if isinstance(v, dict)}
        rec.update(at=self.a.run, status=status, items=self.man.get("tool_items", {}).get(str(cid), []),
                   ok=200 in status.values(), tries=0 if 200 in status.values() else rec.get("tries", 0) + 1)
        mods = xn.get("modules") or {}
        if mods.get("status") == 200 and isinstance(mods.get("body"), list):   # 모듈 목록을 제대로 받은 때만 — 실패한 탐침이 기록을 지우지 않게
            lec = []
            for m in mods["body"]:
                for it in (m or {}).get("module_items") or []:
                    c = it.get("content_data") or {}
                    if not it.get("module_item_id") or not c.get("due_at"):
                        continue
                    if c.get("omit_progress") and not c.get("use_attendance"):
                        continue               # 진도·출석을 안 따지는 선택 항목 — 일정에 안 올린다
                    lec.append({"id": it["module_item_id"], "title": it.get("title") or c.get("title") or "", "due": c["due_at"], "lock": c.get("lock_at"),
                                "done": it.get("completed") is True or it.get("attendance_status") == "attendance"})
            rec["lectures"] = lec
            rec["snap"] = captured
        if not rec["ok"]:
            ledger({"action": "collect.xn_probe", "course": cid, "code": 1, "status": status or xn})

    def finish(self):
        os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
        with open(MANIFEST + ".tmp", "w", encoding="utf-8", newline="\n") as f:
            json.dump(self.man, f, ensure_ascii=False, indent=1)
        os.replace(MANIFEST + ".tmp", MANIFEST)
        self.rep["defender"] = intake.defender(self.q) if os.path.isdir(self.q) and os.listdir(self.q) else "격리 비어 있음"
        print(json.dumps(self.rep, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", metavar="출처", help="로그인 조리법 id(조리법이 하나면 빼도 됨)")
    ap.add_argument("--run", required=True)
    ap.add_argument("--since", type=float, required=True, help="이 시각(epoch) 뒤에 생긴 다운로드만")
    ap.add_argument("--course", help="이 강좌 번호만")
    ap.add_argument("--downloads", default=os.path.join(os.path.expanduser("~"), "Downloads"))
    ap.add_argument("--rejson", action="store_true", help="원본 층 원시 칸(조리법 raw_dir)에 보관한 이 수집의 원시 JSON 을 다시 처리")
    ap.add_argument("--known", help="강좌 번호 → 게시판에서 이미 받은 글 키 목록을 출력(capture-board CFG.known)")
    a = ap.parse_args()
    configure(a.source)
    r = Run(a)
    if a.known:
        print(json.dumps(sorted(r.man["board"].get(a.known, {})), ensure_ascii=False))
        return
    os.makedirs(RAW, exist_ok=True)
    jsons = sorted(glob.glob(os.path.join(a.downloads, f"{PREFIX}*-{a.run}*.json")))
    if a.rejson:                               # 이미 보관한 원시 JSON 을 다시 처리(누락분만 — manifest 가 이미 받은 것을 건너뜀)
        jsons = sorted(glob.glob(os.path.join(RAW, f"{PREFIX}*-{a.run}*.json")))
    try:
        for jp in jsons:
            if a.course and f"-{a.course}-" not in os.path.basename(jp) and f"{PREFIX}canvas-" not in os.path.basename(jp):
                continue
            data = json.load(open(jp, encoding="utf-8"))
            (r.canvas if data.get("kind") == "canvas" else r.board)(data)
            if a.rejson:
                continue
            if not a.course or f"{PREFIX}board-" in os.path.basename(jp):
                shutil.move(jp, os.path.join(RAW, os.path.basename(jp)))
    finally:                                   # 도중에 죽어도 그때까지 받은 것은 manifest 에 남긴다
        r.rep["json"] = [os.path.basename(j) for j in jsons]
        r.finish()


if __name__ == "__main__":
    main()
