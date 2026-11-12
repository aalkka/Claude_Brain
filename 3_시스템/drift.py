#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""상시 문서가 볼트 현실과 어긋났는지 잰다(볼트 개혁 · 2026-11-02 · ADR-026).

왜: 구조를 옮겨도 코어·기억·스킬 글 속 옛 이름은 따라오지 않았고(_eval/hardpaths.py 는 코드만 보고 기억을 뺀다),
상시로 읽히는 파일은 상한 없이 자랐다(기억 색인 한 줄 808자 · MOC 188k). 사람이 드물게 점검해서는 늘 뒤늦다.

  py -3 3_시스템/drift.py            전체 리포트(줄마다 종류 · 파일:줄 · 내용)
  py -3 3_시스템/drift.py --brief    종류별 건수 한 줄
  py -3 3_시스템/drift.py --ops      운영 위험만(세션 시작용) — 없으면 출력 없음

쓰는 곳: weekly.py(전수) · mdtable.py hook(쓰는 순간 그 파일 상한) · hooks/session-notice.py(운영 위험).
새 옛 이름은 RETIRED 에 더한다. 이력을 적은 줄(옛·철회 등)과 `drift:ok` 가 붙은 줄은 세지 않는다.
"""
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
MEM = os.path.join(HERE, "_claude-memory")
LOCK_MIN = 10            # 이보다 오래된 index.lock 은 죽은 잠금으로 본다
COMMIT_H = 24

RETIRED = [
    (r"Documents[\\/]+Claude", "0_작업/<영역>/<주제>"),
    (r"(?:1_수집|_색인)[\\/]+학교", "1_수집/배움 · _색인/배움"),
    (r"2_지식[\\/]+(?:notes|sessions|decisions|_canvas|과목)(?![\w가-힣])", "roles.py path <역할>"),
    (r"(?<![\w./\\`_-])(?:notes|sessions|decisions)/", "역할 이름 — roles.py"),
    (r"session-close", "session-record"),
    (r"\bimportance\b", "10-30 폐지"),
    (r"caveman 모드", "출력 규약 lean"),
    (r"inbox-sort|module-forge:new|study-helper:organize|`organize`|`ingest-vision`|`search` |검색 스킬", "11-02 제거 — ADR-026"),
]
RETIRED = [(re.compile(a), b) for a, b in RETIRED]
HISTORY = re.compile(r"옛|구 |구\)|(?<![가-힣])전 |철회|폐기|폐지|기각|이력|당시|이전|대체|뺐다|drift:ok")
PATH = re.compile(r"(?<![~/\\])(?:0_작업|1_수집|2_지식|3_시스템|\.claude)[/\\][^\s`'\"<>|*,;()\[\]{}«»…]+")
ABS = re.compile(r"[A-Z]:\\[^\s`'\"<>|*,;()\[\]{}«»…]+")
HANGUL = re.compile(r"[가-힣]$")
SKIP_PATH = re.compile(r"실험N|어떤노트|2_지식/참조|_index|\$|%|YYYY|XX|\.\.\.|plugins/<|NN|Program(?: Files)?$")
INDEX_LINK = re.compile(r"^- \[[^\]]+\]\(([^)]+)\)", re.M)


def rel(p):
    return os.path.relpath(p, VAULT).replace(os.sep, "/")


def read(p):
    with open(p, encoding="utf-8-sig", errors="replace") as h:
        return h.read()


def docs():
    """상시·지침 문서 — 모델이 믿고 따르는 글"""
    out = [os.path.join(VAULT, "CLAUDE.md"), os.path.join(VAULT, "README.md"), os.path.join(HERE, "conventions.md")]
    # 사람·Claude 가 믿는 시스템 문서 — 안 봐서 설명서 206줄이 «어긋남 0» 인 채 낡았다(11-03)
    out += glob.glob(os.path.join(VAULT, "2_지식", "**", "설계노트.md"), recursive=True) + glob.glob(os.path.join(VAULT, "2_지식", "**", "사용자설명서.md"), recursive=True)
    out += sorted(glob.glob(os.path.join(HERE, "tutorial", "*.md")) + glob.glob(os.path.join(HERE, "vault-chat", "*.md")))
    out += sorted(glob.glob(os.path.join(MEM, "*.md")))
    out += glob.glob(os.path.expanduser("~/.claude/scheduled-tasks/*/SKILL.md"))    # 무인 실행 지시문도 낡으면 그대로 따른다
    for p in glob.glob(os.path.join(VAULT, ".claude", "skills", "**", "*.md"), recursive=True):
        if os.sep + "references" + os.sep not in p and os.sep + "templates" + os.sep not in p:
            out.append(p)
    return out


def hooks():
    return [p for p in glob.glob(os.path.join(HERE, "hooks", "*")) if os.path.isfile(p)]


def exists_loose(p, base=VAULT):
    """글 속 경로 뒤에 조사가 붙을 수 있다 — 끝 글자를 세 번까지 떼어 본다"""
    p = p.rstrip(".:·-/\\")
    for _ in range(4):
        if os.path.exists(os.path.join(base, p)):
            return True
        if not HANGUL.search(p):
            return False
        p = p[:-1].rstrip(".:·-/\\")
    return False


def retired_rows():
    rows = []
    for p in docs() + hooks():
        for i, ln in enumerate(read(p).split("\n"), 1):
            if HISTORY.search(ln):
                continue
            for rx, new in RETIRED:
                m = rx.search(ln)
                if m:
                    rows.append(("옛 이름", f"{rel(p)}:{i}", f"{m.group(0)} → {new}"))
    return rows


def path_rows():
    rows = []
    for p in docs():
        for i, ln in enumerate(read(p).split("\n"), 1):
            if HISTORY.search(ln):
                continue
            for m in PATH.finditer(ln):
                t = m.group(0)
                if not SKIP_PATH.search(t) and not exists_loose(t):
                    rows.append(("없는 경로", f"{rel(p)}:{i}", t))
            for m in ABS.finditer(ln):
                t = m.group(0)
                if not SKIP_PATH.search(t) and not exists_loose(t, ""):
                    rows.append(("없는 경로", f"{rel(p)}:{i}", t))
    return rows


def limits_of(p):
    """한 파일의 상한 위반 — 대상이 아니면 빈 목록(쓰기 훅이 부른다)"""
    p = os.path.normpath(p)
    name = os.path.basename(p)
    parent = os.path.normpath(os.path.dirname(p))
    know = os.path.join(VAULT, "2_지식")
    out = []
    try:
        if parent == os.path.normpath(MEM) and (name == "MEMORY.md" or name.startswith("index-")):
            t, n, what = read(p), 150, "기억 색인"
        elif parent == os.path.normpath(know) and name == "MOC.md":
            t, n, what = read(p), 150, "MOC"
        elif parent == os.path.normpath(know) and name == "recent.md":
            t, n, what = read(p), 150, "recent"
            items = [x for x in t.split("\n") if x.startswith("- ")]
            if len(items) > 9:
                out.append(("상한", rel(p), f"recent {len(items)}줄(9줄까지)"))
        elif parent == os.path.normpath(know) and name == "open-loops.md":
            t, n, what = read(p), 300, "open-loops"
            size = len(t.encode("utf-8"))
            if size > 6144:
                out.append(("상한", rel(p), f"open-loops {size}바이트(6KB까지)"))
        elif os.path.normpath(p) == os.path.join(VAULT, "CLAUDE.md"):
            t = read(p)
            if t.count("\n") > 200:
                out.append(("상한", rel(p), f"CLAUDE.md {t.count(chr(10))}줄(200줄까지)"))
            return out
        else:
            return out
    except OSError:
        return out
    for i, ln in enumerate(t.split("\n"), 1):
        if ln.startswith("- ") and len(ln) > n:
            out.append(("상한", f"{rel(p)}:{i}", f"{what} 줄 {len(ln)}자({n}자까지): {ln[:40]}…"))
    return out


def limit_rows():
    rows = []
    for p in (os.path.join(MEM, "MEMORY.md"), *glob.glob(os.path.join(MEM, "index-*.md")),
              os.path.join(VAULT, "2_지식", "MOC.md"), os.path.join(VAULT, "2_지식", "recent.md"),
              os.path.join(VAULT, "2_지식", "open-loops.md"), os.path.join(VAULT, "CLAUDE.md")):
        rows += limits_of(p)
    for p in glob.glob(os.path.join(VAULT, ".claude", "skills", "**", "SKILL.md"), recursive=True):
        m = re.search(r"^description:\s*(.*)$", read(p), re.M)
        if m and len(m.group(1)) > 250:
            rows.append(("상한", rel(p), f"스킬 설명 {len(m.group(1))}자(250자까지 · 늘 입력에 든다)"))
    return rows


def memory_rows():
    """색인 ↔ 기억 파일"""
    rows, seen = [], set()
    idx = [os.path.join(MEM, "MEMORY.md")] + glob.glob(os.path.join(MEM, "index-*.md"))
    for p in idx:
        if not os.path.exists(p):
            continue
        for m in INDEX_LINK.finditer(read(p)):
            f = m.group(1)
            seen.add(f)
            if not os.path.exists(os.path.join(MEM, f)):
                rows.append(("기억 색인", rel(p), f"없는 파일: {f}"))
    linked_subs = {os.path.basename(p) for p in idx}
    for p in glob.glob(os.path.join(MEM, "*.md")):
        b = os.path.basename(p)
        if b not in seen and b not in linked_subs:
            rows.append(("기억 색인", b, "색인에 없음"))
    return rows


def ops_rows():
    """운영 위험 — 조용히 일을 망치는 것(전부 실제로 겪음: 잠금 3회 · 게이트웨이 10-02)"""
    rows = []
    lock = os.path.join(VAULT, ".git", "index.lock")
    if os.path.exists(lock):
        age = (time.time() - os.path.getmtime(lock)) / 60
        if age >= LOCK_MIN:
            rows.append(("운영", ".git/index.lock", f"{int(age)}분째 남은 잠금 — 자동 커밋이 멈춘다"))
    try:
        r = subprocess.run(["git", "-C", VAULT, "log", "-1", "--format=%ct"], capture_output=True, text=True, timeout=5)
        h = (time.time() - int(r.stdout.strip())) / 3600
        if h >= COMMIT_H:
            rows.append(("운영", "git", f"마지막 커밋 {int(h)}시간 전 — 자동 커밋 확인"))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    # 민감 노트가 추적되면 자동 push 로 원격에 간다 — pre-commit 은 스테이지 순간만 보고 이미 든 것은 못 뺀다(11-05 실측 7건)
    try:
        r = subprocess.run(["git", "-C", VAULT, "grep", "-lE", r"^sensitive:[[:space:]]*true[[:space:]]*$", "HEAD", "--", "*.md"],
                           capture_output=True, timeout=5)
        n = len(r.stdout.splitlines())
        if n:
            rows.append(("운영", "민감 노트", f"{n}건이 git 추적 중 — 자동 push 로 원격에 간다 · .gitignore 에 넣고 추적 해제"))
    except (OSError, subprocess.SubprocessError):
        pass
    # Stop 훅이 커밋 뒤 스테이지가 남으면 적는 줄 — 세션 시작에 안 보여 쌓이기만 했다(07-30~11-03 157줄)
    try:
        with open(os.path.join(HERE, "_index", "hooks.log"), "rb") as h:
            h.seek(0, os.SEEK_END)
            h.seek(max(0, h.tell() - 500_000))
            log = h.read().decode("utf-8", "replace")
        now = time.time()
        hits = []
        for line in log.splitlines():
            if "BLOCKED" in line:
                try:
                    t = time.mktime(time.strptime(line[:19], "%Y-%m-%d %H:%M:%S"))
                except ValueError:
                    continue
                if now - t < COMMIT_H * 3600:
                    hits.append(line[11:16])
        if hits:
            rows.append(("운영", "자동 커밋", f"{COMMIT_H}시간 안에 {len(hits)}회 막힘(마지막 {hits[-1]}) — 3_시스템/_index/hooks.log · 스테이지에 남은 파일 확인"))
    except OSError:
        pass
    # 앱이 자기 프로세스에 BASE_URL=api.anthropic.com 을 넣고, 사용자 범위에 빈 값이 남기도 한다 — 값이 있고 공식 주소가 아닐 때만 위험
    found = set()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            for n in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"):
                try:
                    v = winreg.QueryValueEx(k, n)[0]
                except OSError:
                    continue
                if v and "api.anthropic.com" not in v:
                    found.add(n)
    except (ImportError, OSError):
        pass
    for n in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"):
        if os.environ.get(n):
            found.add(n)
    if "api.anthropic.com" not in os.environ.get("ANTHROPIC_BASE_URL", "api.anthropic.com"):
        found.add("ANTHROPIC_BASE_URL")
    if found:
        rows.append(("운영", "환경 변수", " · ".join(sorted(found)) + " 있음 — claude -p 가 구독을 벗어나 과금될 수 있다"))
    try:                                # 서버 자동 커밋(11-12 안 A) — 막힘은 위 «자동 커밋»(hooks.log BLOCKED)이 센다 · 그 밖의 실패만
        a = json.load(open(os.path.join(HERE, "_index", "server", "autocommit.json"), encoding="utf-8"))
        if a.get("fail_at") and a.get("result") != "막힘":
            rows.append(("운영", "자동 커밋(서버)", f"{a.get('result')} — {time.strftime('%m-%d %H:%M', time.localtime(a['fail_at']))} · 3_시스템/_index/server/server.log"))
    except (OSError, ValueError, KeyError):
        pass
    try:                                # 구독 끊김(11-11 · claude_bin 상태 파일) — 적혀 있을 때만 다시 잰다(다시 구독했으면 여기서 풀림 · 평소 비용 0)
        import claude_bin
        bare = {k: v for k, v in os.environ.items() if not re.match(r"CLAUDECODE|CLAUDE_CODE|CLAUDE_AGENT|ANTHROPIC_", k)}   # 세션 안이면 앱이 넣은 BASE_URL 이 «과금 길»로 읽혀 끊김이 안 풀린다
        if claude_bin.lapsed() and not claude_bin.check(bare)["ok"] and claude_bin.lapsed():
            d = claude_bin.lapsed()
            rows.append(("운영", "구독", f"{d.get('kind')} — {time.strftime('%m-%d %H:%M', time.localtime(d.get('since') or 0))}부터 · 구독이 필요한 기능 멈춤(대화창·그림 읽기·공지 판정·폰 RC) · 다시 구독·로그인하면 풀림"))
    except Exception:                   # 건강 점검이 이것 때문에 죽지 않게
        pass
    return rows


def props_rows():
    """규약 글의 속성 표 ↔ roles.json props — 표가 플러그인에만 있고 규약 글과 갈라져 Claude 노트가 옛 꼴로 남았다(ADR-027)"""
    conv = os.path.join(HERE, "conventions.md")
    try:
        table = json.load(open(os.path.join(HERE, "roles.json"), encoding="utf-8")).get("props", {})
        m = re.search(r"^# 프론트매터 스키마\n.*?```yaml\n(.*?)\n```", read(conv), re.S | re.M)
    except (OSError, ValueError):
        return []
    if not table or not m:
        return [("속성 표", rel(conv), "규약 글에서 표를 못 찾음")]
    doc, now = {}, None
    for ln in m.group(1).split("\n"):
        head = re.match(r"# (\S+)", ln)
        if head:
            now = doc.setdefault(head.group(1), [])
        elif now is not None and re.match(r"[^\s#:]+:", ln):
            now.append(ln.split(":")[0])
    roles_ = json.load(open(os.path.join(HERE, "roles.json"), encoding="utf-8"))["roles"]
    return [("속성 표", rel(conv), f"{roles_[r]} 표가 roles.json props 와 다름: {doc.get(roles_[r])} ≠ {keys}")
            for r, keys in table.items() if not r.startswith("_") and doc.get(roles_[r]) != keys]


def all_rows():
    return retired_rows() + path_rows() + limit_rows() + memory_rows() + ops_rows() + props_rows()


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    if "--ops" in argv:
        for k, w, t in ops_rows():
            print(f"{w}: {t}")
        return 0
    rows = all_rows()
    if "--brief" in argv:
        c = {}
        for k, _, _ in rows:
            c[k] = c.get(k, 0) + 1
        print("어긋남 0" if not rows else "어긋남 " + " · ".join(f"{k} {v}" for k, v in c.items()))
        return 0
    if not rows:
        print("어긋남 0")
    for k, w, t in rows:
        print(f"{k} | {w} | {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
