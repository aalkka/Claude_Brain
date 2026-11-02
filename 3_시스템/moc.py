#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""MOC — 등록부(2_지식/MOC.md)와 주제별 지도(볼트 개혁 B10 · 사용자 승인 10-31·11-02).

  py -3 3_시스템/moc.py <주제>     그 주제의 지도(등재 줄 + 안 실린 노트 제목). 파일을 만들지 않는다 — 늘 지금 값.
  py -3 3_시스템/moc.py check      150자 넘는 줄 · 못 찾는 링크 · 미등재 수
  py -3 3_시스템/moc.py rebuild [--out 파일]   MOC.md 를 영역·주제별로 다시 묶고 한 줄 150자로(기본 = 미리 보기만)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import roles  # noqa: E402
import topic as topic_mod  # noqa: E402

VAULT = os.path.dirname(HERE)
MOC = os.path.join(VAULT, roles.path("moc"))
LIMIT = 150
LINK = re.compile(r"\[\[([^\]|#]+)")
LAST = "## 진행 → [[open-loops]]"


def rel(p):
    return os.path.relpath(p, VAULT).replace(os.sep, "/")


def md_files():
    out = {}
    for base in (roles.path("knowledge"), roles.path("system") + "/_ref"):
        for d, _, fs in os.walk(os.path.join(VAULT, base)):
            for f in fs:
                if f.endswith(".md"):
                    out.setdefault(f[:-3], rel(os.path.join(d, f)))
    return out


def read_moc():
    with open(MOC, encoding="utf-8", newline="") as h:
        return h.read().replace("\r\n", "\n").split("\n")


def entries(lines):
    """등재 줄(첫 링크가 그 줄의 노트) — 같은 노트가 두 번이면 앞의 것"""
    seen, out = set(), []
    for ln in lines:
        ln = ln.strip()
        m = LINK.search(ln) if ln.startswith("- ") else None
        if m and m.group(1).strip() not in seen:
            seen.add(m.group(1).strip())
            out.append((m.group(1).strip(), ln.rstrip()))
    return out


def clip(line, n=LIMIT):
    if len(line) <= n:
        return line
    cut = line[: n - 1]
    i = max(cut.rfind(x) for x in (" · ", ". ", ", ", " — ", " "))
    if i > n * 0.6:
        cut = cut[:i]
    return cut.rstrip(" ·,—:(*") + "…"


def where(path, fm_topic_of=None):
    """(영역, 주제) — 속성 «주제» 먼저 · 없으면 자리 · 층 바깥이면 (묶음, None)"""
    if path.startswith(roles.path("system") + "/_ref"):
        return ("시스템 진단", None)
    t = fm_topic(path)
    parts = path.split("/")
    k = roles.path("knowledge").split("/")
    sub = parts[len(k):]
    area = sub[0] if len(sub) > 1 else "기타"
    if not t and len(sub) > 2:
        t = sub[1]
    return (area, t)


def fm_topic(path):
    """속성 «주제» 첫 값(주제: [가, 나] · 주제: 가 · 줄 목록)"""
    fm = topic_mod.fm_of(os.path.join(VAULT, path))
    m = re.search(r"^주제:[ \t]*(.*(?:\n[ \t]*- .*)*)", fm, re.M)
    if not m:
        return None
    v = re.split(r"[,\n]", m.group(1).strip().strip("[]"))[0]
    v = v.strip().lstrip("- ").strip("[]\"' ")
    return v if v and v != "null" else None


def rebuild():
    lines = read_moc()
    files = md_files()
    head = []
    for ln in lines:
        head.append(ln)
        if ln.startswith("# "):
            break
    groups, lost = {}, []
    for name, ln in entries(lines):
        if name == "open-loops":
            continue
        p = files.get(name)
        if not p:
            lost.append(clip(ln))
            continue
        a, t = where(p)
        groups.setdefault(a, {}).setdefault(t or "", []).append(clip(ln))
    order = ["배움", "일", "생활", "분야", "modules", "시스템 진단", "기타"]
    out = list(head)
    for a in sorted(groups, key=lambda x: (order.index(x) if x in order else 99, x)):
        out.append(f"## {a}")
        for t in sorted(groups[a]):
            if t:
                out.append(f"### {t}")
            out.extend(sorted(groups[a][t]))
    if lost:
        out.append("## 못 찾는 링크")
        out.extend(lost)
    out.append(LAST)
    return "\n".join(out) + "\n", lost


def show(arg):
    name = topic_mod.resolve(arg)
    t = next((x for x in roles.topics() if x["이름"] == name), None)
    if not t:
        return print(f"주제 없음: {arg}") or 1
    names = set(topic_mod.names(t))
    files = md_files()
    dirs = [x[1] for x in topic_mod.topic_dirs(t)]
    lines = entries(read_moc())
    listed = {n for n, _ in lines}
    print(f"# {name}")
    for n, ln in lines:
        p = files.get(n)
        if p and (fm_topic(p) in names or any(p.startswith(d + "/") for d in dirs)):
            print(ln)
    k = roles.path("knowledge") + "/"
    extra = [n for n, p in files.items() if n not in listed and p.startswith(k) and (fm_topic(p) in names or any(p.startswith(d + "/") for d in dirs))]
    for n in sorted(extra):
        print(f"- [[{n}]]")
    return 0


def check():
    lines = read_moc()
    files = md_files()
    long_ = [ln for ln in lines if ln.startswith("- ") and len(ln) > LIMIT]
    es = entries(lines)
    lost = [n for n, _ in es if n not in files and n != "open-loops"]
    print(f"등재 {len(es)} · 150자 넘음 {len(long_)} · 못 찾는 링크 {len(lost)}")
    for x in lost:
        print("  못 찾음:", x)
    return 0


def main(argv):
    if not argv:
        return print(__doc__) or 1
    if argv[0] == "check":
        return check()
    if argv[0] == "rebuild":
        text, lost = rebuild()
        out = argv[argv.index("--out") + 1] if "--out" in argv else None
        before = "\n".join(read_moc())
        print(f"{len(before)}자 → {len(text)}자 · {text.count(chr(10))}줄 · 못 찾는 링크 {len(lost)}")
        if out:
            with open(out, "w", encoding="utf-8", newline="") as h:
                h.write(text)
        return 0
    return show(" ".join(argv))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
