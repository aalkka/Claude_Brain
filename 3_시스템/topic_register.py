# -*- coding: utf-8 -*-
"""**topic_register** — 이미 볼트에 있는 파일의 주제를 등록부에 올리고, 주제 없는 노트에 «주제:» 를 붙인다(첫 설치·업데이트 때 · 사용자 11-27).

왜: 파일의 주제 = md «주제:» 속성 또는 자리(roles.json topic_roots 바로 아래 폴더)인데, 둘 다 등록부(2_지식/주제.md)에
있는 이름만 주제로 친다(roles.canon). 옛 볼트·다른 데서 옮겨 온 볼트는 폴더는 있는데 등록부가 비어 주제 카드·홈·주제 고르기에
안 나온다. 사람이 따로 시키지 않아도 업데이트·첫 설치 흐름 안에서 등록까지 한다.

  py -3 3_시스템/topic_register.py scan [--json]           등록 안 된 주제 자리 폴더 · 등록 안 된 «주제:» 값 · 주제 없는 노트 수(읽기만)
  py -3 3_시스템/topic_register.py add [--dry]             등록 안 된 주제 자리 폴더를 등록부에 더함(영역 = 그 뿌리 · 상태 진행 · LLM 0)
  py -3 3_시스템/topic_register.py add --name <이름> --area <영역> [--alias a,b] [--dry]   이름 하나(«주제:» 값 · Claude 가 고른 새 주제)
  py -3 3_시스템/topic_register.py loose [--limit 200] [--json]   주제 없는 노트(경로 · 제목 · 첫 줄) — Claude 가 주제를 고를 재료
  py -3 3_시스템/topic_register.py tag <계획.json> [--dry]     {"<볼트 상대 경로>": "<등록된 주제>"} → 그 노트 머리의 «주제:» 만 씀(본문 그대로)

쓰기는 전부 fileops 덮어쓰기(옛 판은 휴지통) 한 묶음 — 되돌리기 = `py -3 3_시스템/fileops.py undo <묶음 id>`.
노트 내용(본문)은 바꾸지 않는다. 1_수집(원본 층)은 «주제:» 를 쓰지 않는다(자리로만). 주제 없는 노트가 많으면 limit 만큼만 내고 남은 수를 말한다.
"""
import argparse
import io
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import roles  # noqa: E402

AREAS = ("배움", "일", "생활", "분야")
SKIP_NAMES = {"MOC.md", "주제.md", "recent.md", "open-loops.md", "profile.md", "장부.md", "보존.md"}
FM = re.compile(r"\A(﻿?)---(\r?\n)(.*?)(\r?\n)---", re.S)


def area_of(root):
    for a in AREAS:
        if root.rstrip("/").endswith("/" + a):
            return a
    return None


def folders():
    """주제 자리 바로 아래 폴더 → {이름: {영역, 자리[], 파일 수}} (점·밑줄 폴더 뺌)."""
    out = {}
    for root in roles.config()["topic_roots"]:
        a = os.path.join(VAULT, *root.split("/"))
        if not os.path.isdir(a):
            continue
        for e in sorted(os.scandir(a), key=lambda x: x.name):
            if not e.is_dir() or e.name.startswith((".", "_", "@")):
                continue
            n = sum(len(fs) for _, _, fs in os.walk(e.path))
            r = out.setdefault(e.name, {"영역": area_of(root), "자리": [], "파일": 0})
            r["자리"].append(root + "/" + e.name)
            r["파일"] += n
            if not r["영역"]:
                r["영역"] = area_of(root)
    return out


def notes():
    """주제를 매길 노트 — 지식 층 md(시스템 노트·일정·모듈 설명 뺌)."""
    out = []
    for d in roles.group("knowledge_notes"):
        a = os.path.join(VAULT, *d.split("/"))
        for dp, ds, fs in os.walk(a):
            ds[:] = [x for x in ds if not x.startswith((".", "_"))]
            for f in fs:
                if f.endswith(".md") and f not in SKIP_NAMES:
                    out.append(os.path.relpath(os.path.join(dp, f), VAULT).replace("\\", "/"))
    return sorted(out)


def scan():
    known = {t["이름"] for t in roles.topics()}
    unreg = {k: v for k, v in folders().items() if not roles.canon(k)}
    vals, loose = {}, []
    for rel in notes():
        fm = roles._fm_topics(os.path.join(VAULT, *rel.split("/")))
        bad = [t for t in fm if not roles.canon(t)]
        for t in bad:
            vals.setdefault(t, []).append(rel)
        if not roles.topic_of(rel):
            loose.append(rel)
    return {"등록된 주제": sorted(known), "등록 안 된 폴더": unreg, "등록 안 된 «주제:» 값": {k: len(v) for k, v in vals.items()},
            "주제 없는 노트": len(loose)}


def registry_text(topics):
    p = roles.abs("topics")
    t = io.open(p, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in t else "\n"
    block = "```json" + nl + '{"topics": [' + nl + ("," + nl).join("  " + json.dumps(x, ensure_ascii=False) for x in topics) + nl + "]}" + nl + "```"
    new, n = re.subn(r"```json\s*\n.*?\n```", lambda m: block, t, count=1, flags=re.S)
    if not n:
        new = t.rstrip() + nl + nl + block + nl
    return new


def write_files(files, why, dry):
    """{볼트 상대 경로: 새 글} → fileops 덮어쓰기 한 묶음 · 묶음 id 를 낸다."""
    import fileops
    ctx = fileops.Ctx(VAULT, by=os.environ.get("BRAIN_BY") or "claude", dry=dry)
    tmpd = tempfile.mkdtemp(prefix="topicreg-")
    for rel, text in files.items():
        tp = os.path.join(tmpd, os.path.basename(rel))
        io.open(tp, "w", encoding="utf-8", newline="").write(text)
        fileops.op_replace(ctx, tp, rel, why)
    if ctx.events:
        fileops.write_view(ctx)
        print("묶음 %s — 되돌리기: py -3 3_시스템/fileops.py undo %s" % (ctx.batch, ctx.batch))
    return ctx


def cmd_add(a):
    topics = list(roles.topics())
    have = {t["이름"].lower() for t in topics} | {x.lower() for t in topics for x in t.get("별칭", [])}
    add = []
    if a.name:
        if a.area not in AREAS:
            raise SystemExit("영역은 %s 중 하나" % "·".join(AREAS))
        if a.name.lower() in have:
            print("이미 등록됨: %s" % a.name)
            return 0
        add.append({"이름": a.name, "영역": a.area, "별칭": [x.strip() for x in (a.alias or "").split(",") if x.strip()], "상태": "진행"})
    else:
        for name, r in sorted(folders().items()):
            if name.lower() not in have and r["영역"]:
                add.append({"이름": name, "영역": r["영역"], "별칭": [], "상태": "진행"})
    if not add:
        print("더할 주제 없음(등록 안 된 주제 자리 폴더 0)")
        return 0
    for x in add:
        print("%s 등록: %s · 영역 %s" % ("미리 보기 ·" if a.dry else "", x["이름"], x["영역"]))
    write_files({roles.path("topics"): registry_text(topics + add)}, "주제 등록(이미 있는 파일의 주제 · topic_register)", a.dry)
    return 0


def first_line(a):
    try:
        t = io.open(a, encoding="utf-8").read(3000)
    except (OSError, UnicodeDecodeError):
        return "", ""
    m = FM.match(t)
    body = t[m.end():] if m else t
    title = next((ln.lstrip("# ").strip() for ln in body.splitlines() if ln.startswith("#")), "")
    line = next((ln.strip() for ln in body.splitlines() if ln.strip() and not ln.startswith("#")), "")
    return title, line[:80]


def cmd_loose(a):
    rows = [r for r in notes() if not roles.topic_of(r)]
    rows.sort(key=lambda r: -os.path.getmtime(os.path.join(VAULT, *r.split("/"))))
    shown = rows[:a.limit]
    out = []
    for r in shown:
        title, line = first_line(os.path.join(VAULT, *r.split("/")))
        out.append({"경로": r, "제목": title, "첫 줄": line})
    if a.json:
        print(json.dumps({"주제": [t["이름"] for t in roles.topics()], "노트": out, "남음": len(rows) - len(shown)}, ensure_ascii=False))
    else:
        for x in out:
            print("%s · %s · %s" % (x["경로"], x["제목"], x["첫 줄"]))
        print("주제 없는 노트 %d%s" % (len(rows), " · 이번에 %d · 남음 %d" % (len(shown), len(rows) - len(shown)) if len(rows) > len(shown) else ""))
    return 0


def with_topic(text, topic):
    """머리에 «주제:» 만 넣거나 빈 칸을 채운다 — 본문·다른 칸은 그대로. 이미 값이 있으면 None."""
    m = FM.match(text)
    if not m:
        nl = "\r\n" if "\r\n" in text else "\n"
        bom = "﻿" if text.startswith("﻿") else ""
        return bom + "---" + nl + "주제: " + topic + nl + "---" + nl + text[len(bom):]
    bom, nl1, fm, nl2 = m.group(1), m.group(2), m.group(3), m.group(4)
    one = re.search(r"^주제:[ \t]*(.*)$", fm, re.M)
    if one and one.group(1).strip() and one.group(1).strip() not in ("[]", '""', "''"):
        return None
    if one:
        fm2 = fm[:one.start()] + "주제: " + topic + fm[one.end():]
    else:
        fm2 = fm + nl1 + "주제: " + topic
    return text[:m.start(3)] + fm2 + text[m.end(3):]


def cmd_tag(a):
    plan = json.load(io.open(a.plan, encoding="utf-8"))
    files, skip = {}, []
    for rel, topic in plan.items():
        rel = rel.replace("\\", "/").strip("/")
        c = roles.canon(topic or "")
        if not c:
            skip.append((rel, "등록 안 된 주제 «%s» — 먼저 add" % topic)); continue
        if rel.startswith(roles.path("sources") + "/") or not rel.endswith(".md"):
            skip.append((rel, "원본 층·md 아님 — 자리로만")); continue
        p = os.path.join(VAULT, *rel.split("/"))
        try:
            t = io.open(p, encoding="utf-8", newline="").read()
        except (OSError, UnicodeDecodeError):
            skip.append((rel, "못 읽음")); continue
        new = with_topic(t, c)
        if new is None:
            skip.append((rel, "이미 «주제:» 있음")); continue
        files[rel] = new
    for rel, why in skip:
        print("  · 건너뜀 %s — %s" % (rel, why))
    if not files:
        print("붙일 것 없음")
        return 0
    print("%s«주제:» 붙임 %d" % ("미리 보기 · " if a.dry else "", len(files)))
    write_files(files, "주제 붙임(머리 «주제:» 만 · topic_register)", a.dry)
    return 0


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="topic_register", description="이미 있는 파일의 주제 등록·붙이기")
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("scan"); s.add_argument("--json", action="store_true")
    s = sp.add_parser("add"); s.add_argument("--name"); s.add_argument("--area"); s.add_argument("--alias"); s.add_argument("--dry", action="store_true")
    s = sp.add_parser("loose"); s.add_argument("--limit", type=int, default=200); s.add_argument("--json", action="store_true")
    s = sp.add_parser("tag"); s.add_argument("plan"); s.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "scan":
        r = scan()
        if a.json:
            print(json.dumps(r, ensure_ascii=False))
        else:
            print("등록된 주제 %d · 등록 안 된 주제 자리 폴더 %d%s" % (len(r["등록된 주제"]), len(r["등록 안 된 폴더"]),
                  "(" + " · ".join("%s %s 파일 %d" % (k, v["영역"], v["파일"]) for k, v in r["등록 안 된 폴더"].items()) + ")" if r["등록 안 된 폴더"] else ""))
            print("등록 안 된 «주제:» 값 %d%s" % (len(r["등록 안 된 «주제:» 값"]), (" — " + " · ".join("%s(%d)" % kv for kv in r["등록 안 된 «주제:» 값"].items())) if r["등록 안 된 «주제:» 값"] else ""))
            print("주제 없는 노트 %d" % r["주제 없는 노트"])
        return 0
    return {"add": cmd_add, "loose": cmd_loose, "tag": cmd_tag}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
