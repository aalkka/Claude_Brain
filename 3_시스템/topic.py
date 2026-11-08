# -*- coding: utf-8 -*-
"""**topic** — 주제 카드: 한 주제(과목·프로젝트)의 마감·작업 중·원본·노트·기록·지난 대화를 한 장에 (볼트 개혁 R7 · 2026-10-30).

왜: 과목 파일 하나를 열면 그 과목의 마감·작업·원본·노트가 한 패널에 있어야 한다(설계안 §5.1). 같은 카드를
Claude 에게도 넘긴다(§17.3 — 경로만 · 파일 내용은 넣지 않음 · Claude 가 필요한 것만 읽는다). 옵시디언 패널 · 대화창 ·
Claude 셸이 같은 엔진을 쓰도록 여기 한 곳에서 만든다(자리는 roles.json · 이름은 주제 등록부 · 마감은 일정 파일).

  py -3 3_시스템/topic.py card <주제|별칭>             → 카드 글(Claude 에게 넘기는 꼴 · 1~2k 토큰)
  py -3 3_시스템/topic.py card <볼트 상대 경로>          → 그 파일의 주제 카드(경로도 받는다)
  py -3 3_시스템/topic.py card <주제> --json           → 패널용 JSON(카드 글은 "card" 칸)
  행위: brain.py run topic.card topic=<주제>

읽기만 한다(LLM 0 · 쓰는 파일 없음).
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import roles  # noqa: E402

KST = timezone(timedelta(hours=9))
WD = "월화수목금토일"
# 일정 한 줄 — schedule.py LINE 과 같은 문법(session-start.ps1 $rx 와도 같음 · 바꾸면 셋 다)
LINE = re.compile(
    r"^\s*- \[([ xX])\] (\d{4}-\d{2}-\d{2})"
    r"(?: \(\S{1,3}\))?"
    r"(?: (\d{1,2}:\d{2})(?:~(\d{1,2}:\d{2}))?)?"
    r" (.+?)(?: \^([A-Za-z0-9-]+))?\s*$")
FM = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)
STUB_META = re.compile(r"^기간 (\S+) (\S+?)~(\S+).*?최대컨텍스트 ([\d,]+)tok", re.M)
SKIP_DIRS = {".git", ".obsidian", ".trash", "node_modules", "__pycache__"}
N = {"deadlines": 3, "work": 8, "notes": 12, "records": 5, "chats": 5, "recent": 10, "status": 12, "todos": 12, "ops": 5}
TODO = re.compile(r"^\s*- \[ \] (.+?)\s*$")


def rel(p):
    return os.path.relpath(p, roles.VAULT).replace("\\", "/")


def day(ts):
    return datetime.fromtimestamp(ts, KST).strftime("%m-%d")


def entry(t):
    """등록부 줄 — 없으면 이름만(자리로 안 주제도 카드는 만든다)."""
    for x in roles.topics():
        if x["이름"] == t:
            return x
    return {"이름": t, "별칭": []}


def names(t):
    return [t["이름"]] + list(t.get("별칭") or [])


def resolve(arg):
    """주제 이름·별칭 · 볼트 상대 경로 → 정식 이름(모르면 None)."""
    c = roles.canon(arg)
    if c:
        return c
    p = arg.replace("\\", "/").strip("/")
    if os.path.isabs(arg):
        p = rel(arg)
    return roles.topic_of(p)


def walk_files(d):
    for dp, dns, fns in os.walk(d):
        dns[:] = [x for x in dns if x not in SKIP_DIRS and not x.startswith(".")]
        for f in fns:
            yield os.path.join(dp, f)


def tree_mtime(p):
    if os.path.isfile(p):
        return os.path.getmtime(p)
    ts = [os.path.getmtime(f) for f in walk_files(p)]
    return max(ts) if ts else os.path.getmtime(p)


def topic_dirs(t):
    """주제 자리(topic_roots)마다 정식 이름·별칭 폴더 가운데 있는 것 → [(자리 역할, 볼트 상대 경로)]."""
    out = []
    for root in roles.config().get("topic_roots", []):
        for n in names(t):
            p = os.path.join(roles.VAULT, *root.split("/"), n)
            if os.path.isdir(p):
                out.append((root, rel(p)))
    return out


def module_entries(t):
    """모듈 자리(2_지식/modules/<모듈>/) 바로 아래 · 이름이 주제인 폴더·md(예: <모듈>/<주제>/ · <모듈>/과목-<주제>.md).
    이름 앞 «낱말-» 하나는 떼고도 본다(과목-·실험- 같은 머리) — 모듈마다 칸을 박지 않는다."""
    base = roles.abs("modules")
    out = []
    if not os.path.isdir(base):
        return out
    want = {n.lower() for n in names(t)}
    for mod in sorted(os.listdir(base)):
        md = os.path.join(base, mod)
        if not os.path.isdir(md) or mod.startswith((".", "_")):
            continue
        for e in sorted(os.listdir(md)):
            stem = e[:-3] if e.lower().endswith(".md") else e
            if not (e.lower().endswith(".md") or os.path.isdir(os.path.join(md, e))):
                continue
            cands = {stem.lower()} | ({stem.split("-", 1)[1].lower()} if "-" in stem else set())
            if cands & want:
                out.append(rel(os.path.join(md, e)))
    return out


def fm_of(path, size=3000):
    try:
        with open(path, encoding="utf-8") as f:
            m = FM.match(f.read(size))
    except (OSError, UnicodeDecodeError):
        return ""
    return m.group(1) if m else ""


def fm_mentions(fm, want):
    """속성 `주제:` 또는 `tags:` 에 주제 이름·별칭이 있나."""
    for key in ("주제", "tags"):
        m = re.search(r"^%s:\s*(.*)$" % key, fm, re.M)
        if not m:
            continue
        v = m.group(1).strip()
        if not v:  # 목록 꼴(줄마다 - x)
            tail = fm[m.end():]
            v = " ".join(re.findall(r"^\s*-\s*(.+)$", tail.split("\n\n")[0], re.M))
        toks = {x.strip().strip("\"'[]#").lower() for x in re.split(r"[,\[\]\s]+", v) if x.strip()}
        if toks & want:
            return True
    return False


def passed(dd, time, end, now=None):
    """그 일정 줄이 지났나 — 날짜가 어제 이전이면 지남 · 오늘이면 시각(끝 시각이 있으면 끝)이 지났을 때만 지남(시각 없으면 그날 안은 안 지남)."""
    now = now or datetime.now(KST)
    if dd < now.date():
        return True
    t = end or time
    return bool(t) and dd == now.date() and now.strftime("%H:%M") >= t.zfill(5)


def upcoming(today, now=None):
    """일정 파일 전부의 열린 줄(오늘부터 · 오늘이면 시각이 아직 안 지난 것) — 날짜·시각 순. topic = 줄 머리(«과목 · …»)의 정식 이름(모르면 None)."""
    d = roles.abs("schedule")
    rows = []
    if not os.path.isdir(d):
        return rows
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(d, fn), encoding="utf-8") as fh:
            for i, ln in enumerate(fh.read().splitlines(), 1):
                m = LINE.match(ln)
                if not m or m.group(1) != " ":
                    continue
                try:
                    dd = datetime.strptime(m.group(2), "%Y-%m-%d").date()
                except ValueError:
                    continue
                if dd < today or passed(dd, m.group(3), m.group(4), now):
                    continue
                text = m.group(5)
                head = text.split(" · ", 1)[0].strip()
                clean, src = clean_line(text)
                rows.append({"date": m.group(2), "wd": WD[dd.weekday()], "time": m.group(3) or "", "end": m.group(4) or "", "text": clean,
                             "days": (dd - today).days, "file": rel(os.path.join(d, fn)), "line": i,
                             "src": src, "head": head, "topic": roles.canon(head)})
    rows.sort(key=lambda r: (r["date"], r["time"].zfill(5)))
    return rows


def clean_line(text):
    """일정 줄 글 → (링크 뺀 글, 원본 경로) — «[[…|원본]]» 은 떼어 원본으로."""
    clean = re.sub(r"\[\[[^\]]*\|원본\]\]|\[원본\]\([^)]*\)", "", text)
    clean = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", clean)
    clean = " ".join(re.sub(r"\[\[([^\]]*)\]\]", r"\1", clean).split())
    src = re.search(r"\[\[([^\]|]+)\|원본\]\]", text)
    return clean, src.group(1) if src else ""


def status(t, today, back=30, now=None):
    """마감·제출 현황(설계안 §19.4) — 이 주제 일정 줄을 지난 back 일부터 · 체크 = 냄(LMS 마감은 «내 제출»으로 [x]) ·
    지났는데(날짜 · 오늘이면 시각까지) 체크 없으면 «놓침» · 아직이면 «남음»."""
    d = roles.abs("schedule")
    want = {n.lower() for n in names(t)}
    rows = []
    for fn in (sorted(os.listdir(d)) if os.path.isdir(d) else []):
        if not fn.endswith(".md"):
            continue
        with open(os.path.join(d, fn), encoding="utf-8") as fh:
            for i, ln in enumerate(fh.read().splitlines(), 1):
                m = LINE.match(ln)
                if not m:
                    continue
                try:
                    dd = datetime.strptime(m.group(2), "%Y-%m-%d").date()
                except ValueError:
                    continue
                head = m.group(5).split(" · ", 1)[0].strip()
                if (dd - today).days < -back or (head.lower() not in want and roles.canon(head) != t["이름"]):
                    continue
                clean, src = clean_line(m.group(5))
                done = m.group(1) != " "
                rows.append({"date": m.group(2), "wd": WD[dd.weekday()], "time": m.group(3) or "", "end": m.group(4) or "", "text": clean, "days": (dd - today).days,
                             "state": "냄" if done else ("놓침" if passed(dd, m.group(3), m.group(4), now) else "남음"), "file": rel(os.path.join(d, fn)), "line": i, "src": src})
    rows.sort(key=lambda r: (r["date"], r["time"].zfill(5)))
    # 지난 것은 가까운 것만 · 앞으로 것은 모두(위 N 안에서)
    past = [r for r in rows if r["days"] < 0][-N["status"] // 2:]
    return past + [r for r in rows if r["days"] >= 0][:N["status"] - len(past)]


def todos(t, dirs, notes_list):
    """할 일(설계안 §19.4) — open-loops 의 열린 줄 가운데 이 주제 이름·별칭이 든 것 + 이 주제 작업·노트(최근 바뀐 것부터)의 «- [ ]» 줄."""
    want = [n.lower() for n in names(t) if len(n) >= 2]
    out = []

    def scan(a, pick):
        try:
            lines = open(a, encoding="utf-8").read().splitlines()
        except OSError:
            return
        for i, ln in enumerate(lines, 1):
            m = TODO.match(ln)
            if m and pick(m.group(1)):
                out.append({"text": " ".join(re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", m.group(1)).split())[:200], "file": rel(a), "line": i})
            if len(out) >= N["todos"]:
                return

    try:
        ol = roles.abs("open_loops")
    except KeyError:                                   # 역할 표에 없는 볼트(배포판 초기·시험 볼트)
        ol = ""
    if ol and os.path.isfile(ol):
        scan(ol, lambda x: any(n in x.lower() for n in want))
    files = [f for _, p in dirs if not p.startswith(roles.path("sources") + "/")
             for f in walk_files(os.path.join(roles.VAULT, *p.split("/"))) if f.endswith(".md")]
    files += [os.path.join(roles.VAULT, *n["path"].split("/")) for n in notes_list if n["path"].endswith(".md")]
    for f in sorted(set(files), key=lambda f: -os.path.getmtime(f))[:40]:
        if len(out) >= N["todos"]:
            break
        scan(f, lambda x: True)
    return out[:N["todos"]]


def ledger(dirs):
    """장부 최근(설계안 §19.4 «최근») — fileops 장부에서 이 주제 자리를 지나간 옮김·지움(최근 것부터)."""
    try:
        a = os.path.join(roles.abs("system"), "ledger", "ops.jsonl")
    except KeyError:
        return []
    roots = [p for _, p in dirs]
    if not roots or not os.path.isfile(a):
        return []
    with open(a, encoding="utf-8") as fh:
        lines = fh.readlines()[-600:]
    out = []
    for ln in reversed(lines):
        try:
            e = json.loads(ln)
        except ValueError:
            continue
        ps = [e.get("src") or "", e.get("dst") or ""]
        if any(x == r or x.startswith(r + "/") for x in ps for r in roots):
            out.append({"ts": (e.get("ts") or "")[:16].replace("T", " "), "op": e.get("op"), "src": e.get("src"), "dst": e.get("dst"), "by": e.get("by")})
            if len(out) >= N["ops"]:
                break
    return out


def deadlines(t, today):
    want = {n.lower() for n in names(t)}
    return [r for r in upcoming(today) if r["head"].lower() in want or r["topic"] == t["이름"]][:N["deadlines"]]


def work(dirs):
    out = []
    for root, p in dirs:
        w = roles.path("work")
        if root != w and not root.startswith(w + "/"):    # R9 뒤 작업 자리 = 0_작업/<영역>
            continue
        a = os.path.join(roles.VAULT, *p.split("/"))
        for e in os.listdir(a):
            if e.startswith("."):
                continue
            q = os.path.join(a, e)
            out.append({"path": rel(q), "dir": os.path.isdir(q), "mtime": tree_mtime(q)})
    out.sort(key=lambda x: -x["mtime"])
    return out[:N["work"]]


def sources(dirs):
    """원본 묶음(1_수집/<…>/<주제>/<묶음>) — 개수만 · 짝메모 md(같은 이름의 원본이 있는 md)는 세지 않는다."""
    out = []
    for root, p in dirs:
        if not p.startswith(roles.path("sources") + "/"):
            continue
        a = os.path.join(roles.VAULT, *p.split("/"))
        groups = {}
        for f in walk_files(a):
            r = os.path.relpath(f, a).replace("\\", "/")
            g = r.split("/")[0] if "/" in r else "(바로 아래)"
            groups.setdefault(g, []).append(f)
        for g, fs in sorted(groups.items()):
            stems = {}
            for f in fs:
                s, ext = os.path.splitext(f)
                stems.setdefault(s, set()).add(ext.lower())
            n = sum(1 for exts in stems.values() if exts != {".md"} or len(exts) == 1)
            latest = max(os.path.getmtime(f) for f in fs)
            out.append({"name": g, "path": p if g == "(바로 아래)" else p + "/" + g, "count": n, "mtime": latest})
    return out


def notes(t, dirs, mods):
    want = {n.lower() for n in names(t)}
    seen, out = set(), []

    def add(a):
        r = rel(a)
        if r in seen or not r.lower().endswith((".md", ".canvas", ".sheet")):
            return
        seen.add(r)
        out.append({"path": r, "mtime": os.path.getmtime(a)})

    know = roles.path("knowledge") + "/"
    for _, p in dirs:
        if p.startswith(know):
            for f in walk_files(os.path.join(roles.VAULT, *p.split("/"))):
                add(f)
    for m in mods:
        a = os.path.join(roles.VAULT, *m.split("/"))
        for f in (walk_files(a) if os.path.isdir(a) else [a]):
            add(f)
    for g in roles.group("moc_notes"):  # 자리 밖이어도 속성 `주제:`·태그로 단 노트
        for f in walk_files(os.path.join(roles.VAULT, *g.split("/"))):
            if f.endswith(".md") and rel(f) not in seen and fm_mentions(fm_of(f), want):
                add(f)
    out.sort(key=lambda x: -x["mtime"])
    return out[:N["notes"]], len(out)


def records(t):
    want = {n.lower() for n in names(t)}
    d = roles.abs("sessions")
    out = []
    if not os.path.isdir(d):
        return out
    for fn in os.listdir(d):
        if not fn.endswith(".md"):
            continue
        fm = fm_of(os.path.join(d, fn))
        if fm and fm_mentions(fm, want):
            tt = re.search(r"^title:\s*(.+)$", fm, re.M)
            out.append({"path": rel(os.path.join(d, fn)), "title": (tt.group(1).strip().strip("\"'") if tt else fn[:-3])[:80], "date": fn[:10]})
    out.sort(key=lambda x: x["path"], reverse=True)
    return out[:N["records"]]


def stub_dir():
    return os.path.join(roles.abs("system"), "_index", "stubs")


def chats(t, dirs, mods, since_days=60):
    """지난 대화 색인(Stop 훅 스텁)에서 이 주제를 다룬 것 — 주제 폴더 경로가 나오거나 사용자 요청(U:)에 이름·별칭이 나옴.
    W4: 맥락(최대컨텍스트)이 작으면 이어 가기 · 크면 새 대화 + 스텁 넘김을 패널이 고른다."""
    d = stub_dir()
    if not os.path.isdir(d):
        return []
    keys = [p for _, p in dirs] + mods
    keys = [k for k in keys] + [k.replace("/", "\\") for k in keys]
    want = [n.lower() for n in names(t) if len(n) >= 2]
    cut = time.time() - since_days * 86400
    out = []
    for fn in os.listdir(d):
        if not fn.endswith(".md") or fn.endswith(".save.md"):
            continue
        a = os.path.join(d, fn)
        mt = os.path.getmtime(a)
        if mt < cut:
            continue
        try:
            with open(a, encoding="utf-8") as f:
                s = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        asks = re.findall(r"^\S*\s*U: (.+?)(?: \[L\d+\])?$", s, re.M)
        # 경로가 한 번 스친 대화(다른 일 하다 예로 든 것)는 뺀다 — 요청에 이름이 나오면 3점 · 경로는 1점씩 · 2점부터(10-30 실측: 1점짜리 5개 모두 딴 일)
        hits = sum(s.count(k) for k in keys) + 3 * sum(1 for u in asks for w in want if w in u.lower())
        if hits < 2:
            continue
        m = STUB_META.search(s)
        sid = re.search(r"projects\\[^\\]+\\([0-9a-f-]{36})\.jsonl", s)
        out.append({"path": rel(a), "id": sid.group(1) if sid else fn[:-3], "mtime": mt, "hits": hits,
                    "when": ("%s %s" % (m.group(1)[5:], m.group(2))) if m else day(mt),
                    "ctx": int(m.group(4).replace(",", "")) if m else None,
                    "first": (asks[0] if asks else "")[:80]})
    out.sort(key=lambda x: -x["mtime"])
    return out[:N["chats"]]


def recent(dirs, mods):
    fs = []
    for _, p in dirs:
        fs += list(walk_files(os.path.join(roles.VAULT, *p.split("/"))))
    for m in mods:
        a = os.path.join(roles.VAULT, *m.split("/"))
        fs += list(walk_files(a)) if os.path.isdir(a) else [a]
    fs = set(fs)
    stems = {os.path.splitext(f)[0] for f in fs if not f.lower().endswith(".md")}
    fs = sorted((f for f in fs if not (f.lower().endswith(".md") and os.path.splitext(f)[0] in stems)),  # 원본 옆 짝 메모는 원본이 대신
                key=lambda f: -os.path.getmtime(f))
    return [{"path": rel(f), "mtime": os.path.getmtime(f)} for f in fs[:N["recent"]]]


def build(name):
    t = entry(name)
    today = datetime.now(KST).date()
    dirs = topic_dirs(t)
    mods = module_entries(t)
    nl, n_notes = notes(t, dirs, mods)
    c = {"topic": {k: t.get(k) for k in ("이름", "영역", "학기", "상태", "별칭", "단추")}, "registered": t in roles.topics(),
         "dirs": [{"root": r, "path": p} for r, p in dirs], "modules": mods,
         "deadlines": deadlines(t, today), "work": work(dirs), "sources": sources(dirs),
         "notes": nl, "notes_total": n_notes, "records": records(t), "chats": chats(t, dirs, mods),
         "recent": recent(dirs, mods), "today": today.isoformat(),
         "status": status(t, today), "todos": todos(t, dirs, nl), "ops": ledger(dirs)}
    c["card"] = card_text(c)
    return c


def card_text(c):
    t = c["topic"]
    meta = " · ".join(x for x in [("별칭 " + "·".join(t["별칭"])) if t.get("별칭") else "", t.get("영역") or "", t.get("학기") or "", t.get("상태") or ""] if x)
    L = ["[주제 카드 — %s%s · 파일 내용은 넣지 않았다 — 필요한 것만 읽어라 · 경로는 이 볼트 안]" % (t["이름"], " (%s)" % meta if meta else "")]
    if c["dirs"]:
        L.append("자리: " + " · ".join(d["path"] for d in c["dirs"]))
    if c["deadlines"]:
        L.append("다가오는 마감:")
        L += ["- %s (%s)%s %s%s" % (d["date"][5:], d["wd"], " " + d["time"] if d["time"] else "", d["text"], " — 원본 " + d["src"] if d["src"] else "") for d in c["deadlines"]]
    if c["work"]:
        L.append("작업 중: " + " · ".join("%s%s (%s)" % (w["path"], "/" if w["dir"] else "", day(w["mtime"])) for w in c["work"][:5]))
    if c["sources"]:
        L.append("원본: " + " · ".join("%s %d" % (s["path"], s["count"]) for s in c["sources"]))
    if c["modules"]:
        L.append("기록 파일(모듈): " + " · ".join(c["modules"]))
    if c["notes"]:
        L.append("노트(최근 %d · 모두 %d): " % (min(5, len(c["notes"])), c["notes_total"]) + " · ".join(n["path"] for n in c["notes"][:5]))
    miss = [x for x in c.get("status", []) if x["state"] == "놓침"]
    if miss:
        L.append("지난 마감 중 체크 없음(놓쳤거나 안 표시): " + " · ".join("%s %s" % (x["date"][5:], x["text"]) for x in miss[:5]))
    if c.get("todos"):
        L.append("할 일(열린 체크 줄): " + " · ".join("%s (%s:%d)" % (x["text"][:60], x["file"], x["line"]) for x in c["todos"][:5]))
    if c["recent"]:
        L.append("최근 바뀐 파일:")
        L += ["- %s (%s)" % (r["path"], day(r["mtime"])) for r in c["recent"]]
    if c["records"]:
        L.append("세션 노트: " + " · ".join(r["path"] for r in c["records"][:3]))
    if c["chats"]:
        L.append("지난 대화 색인(스텁 — 이어서 하는 일이면 필요한 만큼만): " + " · ".join("%s (%s)" % (x["path"], x["when"]) for x in c["chats"][:3]))
    return "\n".join(L)


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    a = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in a
    a = [x for x in a if x != "--json"]
    if len(a) < 2 or a[0] != "card":
        print(__doc__.strip().split("\n\n")[1])
        return 2
    arg = " ".join(a[1:])
    name = resolve(arg)
    if not name:
        msg = "주제를 모름: %s — 등록부 `roles.py topics` · 자리 `roles.json` topic_roots" % arg
        print(json.dumps({"error": msg}, ensure_ascii=False) if as_json else msg)
        return 1
    c = build(name)
    print(json.dumps(c, ensure_ascii=False) if as_json else c["card"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
