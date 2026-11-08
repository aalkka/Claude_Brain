# -*- coding: utf-8 -*-
"""**cleanup** — 정리 후보를 찾아 fileops 계획 파일로 남긴다 (볼트 개혁 R8 · 2026-10-30 · 설계안 §4 보존 일정표 · §13 B5·B6).

지우지 않는다. 후보와 까닭만 낸다 → 주간 점검(weekly-review)이 사용자에게 보이고 → 승인한 것만
`py -3 3_시스템/fileops.py plan <계획> --apply`(휴지통 · 장부 · 되살림). 비우기(영구 삭제)는 사람만(`fileops purge`).

  py -3 3_시스템/cleanup.py [--json] [--days 30]

후보(기계로 가를 수 있는 것만 · 설계안 §4 표의 «Claude 제안» 칸):
  ① 같은 내용 사본 — 0_작업·1_수집(색인·LMS 원본 JSON·웹 원본 칸 빼고)의 md 아닌 파일, sha256 이 같은 묶음에서 하나만 남김
     · 남길 것 = 1_수집 제출 > 1_수집 > 0_작업 · 같은 칸이면 먼저 생긴 것
     · 0_작업 파일의 쌍둥이가 1_수집 에 있으면 «제출·승격된 작업 파일» — 마지막 수정이 --days(30)일 지난 것만 후보
  ② 빈 파일(0바이트)  ③ 빈 폴더(역할 자리·주제 폴더·고정 하위 폴더는 뺌)
  ④ 강의자료·공지(학기 끝 + 보존 표의 날) · 웹 수집 보관 칸(학기 끝) · 고아 첨부(어느 노트도 이름을 안 씀)
보고만(지우지 않음): 받은함에 7일 넘게 머문 것(§13 B5) · 휴지통 30일 넘은 것(비우기는 사람).
안 함: 웹 공지 마감+30일·대기 칸(웹 수집 대본이 직접).
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import roles  # noqa: E402
import fileops  # noqa: E402

VAULT = os.path.dirname(HERE)
FIXED_SUB = {"강의자료", "공지", "과제", "제출", "시험", "족보"}           # 설계안 §1.1 R4 — 비어 있어도 둔다
SKIP_NAMES = {".gitkeep", "desktop.ini", "thumbs.db", ".ds_store"}


def rel(a):
    return os.path.relpath(a, VAULT).replace("\\", "/")


def sha256(a):
    h = hashlib.sha256()
    with open(a, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def content_roots():
    machine = {roles.path(r) for r in ("source_index",)} | {roles.path("sources") + "/_lms", roles.path("sources") + "/.web"}
    return [roles.path("work"), roles.path("sources")], machine | {roles.path("inbox")}


def walk(root, skip):
    for dp, dns, fns in os.walk(os.path.join(VAULT, *root.split("/"))):
        r = rel(dp)
        dns[:] = [d for d in dns if not d.startswith(".") and (r + "/" + d) not in skip]
        yield dp, dns, fns


def tier(r):
    s = roles.path("sources") + "/"
    if r.startswith(s) and "/제출/" in r:
        return 0
    return 1 if r.startswith(s) else 2


def find(days):
    roots, skip = content_roots()
    now = time.time()
    by_size = defaultdict(list)
    empty_files, empty_dirs = [], []
    keep_dirs = set(roles.config()["roles"].values()) | set(roles.config().get("topic_roots", []))
    for root in roots:
        for dp, dns, fns in walk(root, skip):
            r = rel(dp)
            files = [f for f in fns if f.lower() not in SKIP_NAMES]
            parent = r.rsplit("/", 1)[0]
            if not dns and not files and r not in keep_dirs and parent not in keep_dirs and os.path.basename(dp) not in FIXED_SUB:
                empty_dirs.append(r)
            for f in files:
                a = os.path.join(dp, f)
                try:
                    st = os.stat(a)
                except OSError:
                    continue
                if st.st_size == 0:
                    empty_files.append(rel(a))
                elif not f.lower().endswith(".md"):
                    by_size[st.st_size].append((a, st.st_mtime, st.st_ctime))
    dup, promoted_work, young = [], [], 0
    for size, xs in by_size.items():
        if len(xs) < 2:
            continue
        by_sha = defaultdict(list)
        for a, m, c in xs:
            by_sha[sha256(a)].append((rel(a), m, c))
        for group in by_sha.values():
            if len(group) < 2:
                continue
            group.sort(key=lambda g: (tier(g[0]), g[2]))
            keep = group[0][0]
            for r, m, c in group[1:]:
                age = (now - m) / 86400
                if r.startswith(roles.path("work") + "/") and tier(keep) < 2:
                    if age >= days:
                        promoted_work.append({"src": r, "keep": keep, "days": int(age)})
                    else:
                        young += 1
                else:
                    dup.append({"src": r, "keep": keep, "size": size})
    inbox = roles.abs("inbox")
    stay = []
    i_days, t_days = (float("inf") if x is None else x for x in (roles.retention("받은함"), roles.retention("휴지통")))  # None(무기한) = 알리지 않음
    if os.path.isdir(inbox):
        for f in os.listdir(inbox):
            if f.startswith((".", "_")):
                continue
            age = (now - os.path.getmtime(os.path.join(inbox, f))) / 86400
            if age > i_days:
                stay.append({"path": rel(os.path.join(inbox, f)), "days": int(age)})
    old_trash = [{"item": d, "days": age, "files": n, "mb": round(sz / 1e6, 1)}
                 for d, age, n, sz in fileops.trash_items(fileops.Ctx(VAULT)) if age >= t_days]
    today = dt.date.today()
    return {"dup": dup, "promoted_work": promoted_work, "promoted_work_young": young, "empty_files": empty_files,
            "empty_dirs": empty_dirs, "inbox_stay": stay, "trash_old": old_trash,
            "lecture_old": lecture_old(today), "archive_old": archive_old(today), "orphan_attach": orphan_attachments()}


def lecture_old(today):
    """보존 일정표 «강의자료» — 학기 끝 + 날이 지난 과목의 강의자료·공지 폴더(과제·제출·시험·족보는 무기한 · 후보일 뿐)."""
    days = roles.retention("강의자료")
    if days is None:
        return []
    out = []
    for t in roles.topics():
        end = roles.semester_end(t.get("학기"))
        if not end or dt.date.fromisoformat(end) + dt.timedelta(days=days) >= today:
            continue
        for sub in ("강의자료", "공지"):
            r = "%s/%s/%s" % (roles.path("school"), t["이름"], sub)
            a = os.path.join(VAULT, *r.split("/"))
            n = sum(len(fns) for _, _, fns in os.walk(a))
            if n:
                out.append({"src": r, "count": n, "end": end})
    return out


def archive_old(today):
    """보존 일정표 «보관칸» — 웹 수집 보관 칸의 글 가운데 넣은 학기가 끝나고 날이 지난 것(글 · 첨부 · 색인 · 원시)."""
    days = roles.retention("보관칸")
    if days is None:
        return []
    ends = sorted(roles.semester_ends().values())
    out = []
    for sp in glob.glob(os.path.join(HERE, "_index", "collect", "*.json")):
        try:
            with open(sp, encoding="utf-8") as f:
                items = json.load(f).get("items") or {}
        except (OSError, ValueError):
            continue
        rid = os.path.splitext(os.path.basename(sp))[0]
        for aid, it in items.items():
            run = (it.get("archived_run") or it.get("run") or "")[:8]
            if not it.get("archived") or not re.fullmatch(r"\d{8}", run):
                continue
            md = "%s-%s" % (run[4:6], run[6:8])
            end = next(("%s-%s" % (run[:4], e) for e in ends if e >= md), "%d-%s" % (int(run[:4]) + 1, ends[0]))
            if dt.date.fromisoformat(end) + dt.timedelta(days=days) >= today:
                continue
            r = it["archived"].replace("\\", "/")
            stem = os.path.splitext(r)[0]
            src = roles.path("sources")
            for x in (r, stem, "%s/%s" % (roles.path("source_index"), stem[len(src) + 1:]), "%s/.web/%s/%s.html" % (src, rid, aid)):
                a = os.path.join(HERE, "_index", "collect", "archive", *x.split("/"))
                if os.path.exists(a):
                    out.append({"src": "3_시스템/_index/collect/archive/" + x, "count": sum(len(fns) for _, _, fns in os.walk(a)) or None, "end": end})
    return out


ATTACH = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".pdf", ".mp3", ".m4a", ".wav", ".mp4", ".webm"}


def orphan_attachments():
    """보존 일정표 «정리후보»의 고아 첨부 — 지식 층·볼트 뿌리의 그림·PDF·소리 가운데 어느 노트·캔버스도 이름을 쓰지 않는 것. 이름 글자가 어디든 나오면 둔다(보수적)."""
    cands = []
    for dp, dns, fns in walk(roles.path("knowledge"), {roles.path("modules")}):
        cands += [os.path.join(dp, f) for f in fns if os.path.splitext(f)[1].lower() in ATTACH]
    cands += [os.path.join(VAULT, f) for f in os.listdir(VAULT) if os.path.isfile(os.path.join(VAULT, f)) and os.path.splitext(f)[1].lower() in ATTACH]
    if not cands:
        return []
    ctx = fileops.Ctx(VAULT, dry=True)
    text = []
    for r in fileops.walk_vault(ctx, exts=(".md", ".canvas")):
        try:
            with open(ctx.abs(r), encoding="utf-8", errors="replace") as f:
                text.append(f.read())
        except OSError:
            pass
    text = "\n".join(text)
    return [rel(a) for a in cands if os.path.basename(a) not in text and urllib.parse.quote(os.path.basename(a)) not in text and os.path.basename(a).replace(" ", "%20") not in text]


def plan_of(c):
    src_root = roles.path("sources") + "/"
    ops = []
    for x in c.get("lecture_old", []):
        ops.append({"op": "rm", "src": x["src"], "count": x["count"], "why": "보존 일정표 강의자료 — 학기 끝 %s + 날 지남" % x["end"], "user_asked": True})
    for x in c.get("archive_old", []):
        ops.append({"op": "rm", "src": x["src"], "count": x["count"], "why": "보존 일정표 보관칸 — 학기 끝 %s 지남" % x["end"]})
    for r in c.get("orphan_attach", []):
        ops.append({"op": "rm", "src": r, "why": "고아 첨부 — 어느 노트·캔버스도 이름을 안 씀"})
    for x in c["dup"]:
        ops.append({"op": "rm", "src": x["src"], "why": "같은 내용 사본 — 남김: %s" % x["keep"], "user_asked": x["src"].startswith(src_root)})
    for x in c["promoted_work"]:
        ops.append({"op": "rm", "src": x["src"], "why": "제출·승격된 작업 파일(%d일) — 남김: %s" % (x["days"], x["keep"])})
    for r in c["empty_files"]:
        ops.append({"op": "rm", "src": r, "why": "빈 파일", "user_asked": r.startswith(src_root)})
    for r in c["empty_dirs"]:
        ops.append({"op": "rm", "src": r, "why": "빈 폴더", "user_asked": r.startswith(src_root)})
    return ops


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(prog="cleanup", description="정리 후보 → fileops 계획 파일(지우지 않음)")
    ap.add_argument("--days", type=int, default=None, help="제출·승격된 작업 파일을 후보로 올리는 날 수(비우면 보존 일정표 «작업산출물»)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.days is None:
        a.days = roles.retention("작업산출물")
        a.days = float("inf") if a.days is None else a.days  # None(무기한) = 후보로 올리지 않음
    c = find(a.days)
    ops = plan_of(c)
    day = dt.date.today().isoformat()
    out = os.path.join(HERE, "_index", "cleanup", "후보-%s.json" % day)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"title": "정리 후보 %s — 사용자 승인 뒤에만 --apply" % day, "ops": ops, "report": c}, f, ensure_ascii=False, indent=1)
    if a.json:
        print(json.dumps({"plan": rel(out), "ops": len(ops), **c}, ensure_ascii=False))
        return 0
    print("정리 후보 %d건 → %s" % (len(ops), rel(out)))
    print("  같은 내용 사본 %d · 제출·승격된 작업 파일 %d(%s 안 된 것 %d) · 빈 파일 %d · 빈 폴더 %d" % (
        len(c["dup"]), len(c["promoted_work"]), "무기한" if a.days == float("inf") else "%d일" % a.days, c["promoted_work_young"], len(c["empty_files"]), len(c["empty_dirs"])))
    print("  강의자료 학기 끝 지남 %d · 보관 칸 학기 끝 지남 %d · 고아 첨부 %d" % (len(c["lecture_old"]), len(c["archive_old"]), len(c["orphan_attach"])))
    for o in ops[:20]:
        print("  - %s — %s" % (o["src"], o["why"]))
    if len(ops) > 20:
        print("  … %d건 더(계획 파일)" % (len(ops) - 20))
    i_days, t_days = (float("inf") if x is None else x for x in (roles.retention("받은함"), roles.retention("휴지통")))
    n = lambda x: "무기한" if x == float("inf") else "%d일" % x  # noqa: E731
    print("보고: 받은함 %s 넘김 %d · 휴지통 %s 넘김 %d항목(비우기 = 사람 `fileops purge --older %s`)" % (
        n(i_days), len(c["inbox_stay"]), n(t_days), len(c["trash_old"]), n(t_days)[:-1] if t_days != float("inf") else "N"))
    if ops:
        print("적용(승인 뒤만): py -3 3_시스템/fileops.py plan %s --apply" % rel(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
