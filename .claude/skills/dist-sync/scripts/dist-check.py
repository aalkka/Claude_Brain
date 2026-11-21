"""배포판 최신 점검 — 볼트 코어와 배포판이 어긋난 곳을 잰다(LLM 0 · 읽기와 fetch 만).

  py -3 .claude/skills/dist-sync/scripts/dist-check.py            # 사람 말 보고 · 종료 0 어긋남 없음 · 1 있음 · 2 못 잼
  py -3 .claude/skills/dist-sync/scripts/dist-check.py --fetch    # 원격을 먼저 받아 본다(③ 을 지금 기준으로)
  py -3 .claude/skills/dist-sync/scripts/dist-check.py --json
  py -3 .claude/skills/dist-sync/scripts/dist-check.py --ack <경로>… --why "까닭"  # 이 판은 배포판에 안 싣기로 함 — 다시 고칠 때까지 ① 에서 뺀다
  py -3 .claude/skills/dist-sync/scripts/dist-check.py --acks      # 안 싣기로 적은 것과 까닭
  py -3 .claude/skills/dist-sync/scripts/dist-check.py --ack <경로>… --always --why "까닭"   # 판과 상관없이 안 싣는다(자리째)
  py -3 .claude/skills/dist-sync/scripts/dist-check.py --ack <배포판 파일>… --ref --why "까닭" # ⑥ 가리킴을 확인함(선택 갈래 등)
  py -3 .claude/skills/dist-sync/scripts/dist-check.py --ship <초안>   # 배포 목록 초안으로 미리 잰다

네 가지를 센다.
  ① 볼트에서 바뀌었는데 배포판에 안 간 코어 — 내용이 다르고, 볼트 파일이 배포판이 그 파일을 마지막으로 고친 커밋보다 나중에 고쳐졌다.
     배포판이 익명화해 늘 다른 파일(제작자 볼트 실측 등)은 볼트를 다시 고치기 전엔 안 잡힌다. 배포판에 없는 새 파일은 생긴 때와 상관없이 늘 센다 —
     안 싣기로 한 것은 --ack 로만 빠진다(시각으로 거르면 배포 커밋보다 먼저 생기고 그 배포에 안 실은 파일이 조용히 빠진다).
     볼트에서 지웠는데 배포판에 남은 코어도 센다. 층이 안 정해진 새 파일(«미분류»)도 싣기 전에 정해야 하니 센다.
     층 규칙이 안 보는 자리도 센다(알리기만 · 옮기는 것은 publish) — 배포판에 손으로 넣은 옵시디언 설정 · 스니펫 · 새 플러그인 ·
     씨앗 머리말(항목은 사용자 것) · 시스템 문서. 옵시디언은 켤 때마다 설정을 다시 써서 시각을 못 믿으니 이 자리는 내용(ack 판)으로만 가른다.
     항목마다 가를 까닭을 붙인다 — «필요»(배포판 코어가 부름) · «익명화할 곳» · «안내 없는 바깥 설정». 안 싣기로 적었는데
     배포판 코어가 부르는 것은 다시 올린다.
  ② 배포판 worktree 에 커밋했는데 push 안 한 것(+ 커밋 안 한 고침)
  ③ 원격에만 있는 것(받아 합칠 것) — 마지막으로 받아 둔 원격 기준. --fetch 나 건강 줄의 하루 한 번 받기가 새로 받는다.
  ④ 볼트 밖 설정(작업 스케줄러·레지스트리·브라우저·설치 프로그램 등)을 건드리는 코어인데 안내 목록에 없는 곳 — external.py scan
  ⑤ 범위(배포 목록 ship.json 이 있을 때) — 목록 밖 새 코어 = «정할 것»(① 에 안 넣는다 · 싣기 = 목록에 더함 · 안 싣기 = --ack --always) ·
     배포판에 있는데 목록 밖 = «빼기 후보» · 여러 기능이 같이 쓰는 자리를 폴더째 적은 줄 = «목록 잘못»
  ⑥ 배포판 글(진단 기록·시험 포함)이 배포판에 없는 것을 가리킴 — 볼트에만 있는 코드 파일 · 배포판에 없는 모듈 ·
     not-shipped.txt(개인 층 · «정규식<TAB>이름»)의 이름. 선택 갈래·안내 글이면 --ack <배포판 파일> --ref --why 로 확인함을 적는다(새 이름이 나오면 다시 뜬다)
  ⑦ 만드는 길 없는 개인 파일(배포 목록 «개인» 칸)
  ⑧ 모듈 계약 — 이 볼트 모듈(꺼진 것·배포판에 안 싣는 것까지)이 쓰는 코어 이름(module.json uses_core)이 배포판에 없음 —
     그 모듈을 배포판 꼴 볼트에 붙이면 깨진다(contracts.py names --core <배포판> · 11-17 mobility 범용화)
배포판 worktree = 볼트 저장소의 worktree 가운데 `dist-sync` 가지 · 없으면(제작자 볼트가 아니면) 잴 것이 없다.
"""
import argparse
import ast
import collections
import difflib
import datetime
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
BRANCH = "dist-sync"
ACK = os.path.join("3_시스템", "_index", "dist-sync", "check-ack.json")  # mf:allow-path  (안 싣기로 한 판 · 개인 층)
FETCH_EVERY = 20 * 3600          # 건강 줄이 원격을 다시 받는 간격(초) — 하루 한 번
FETCH_TIMEOUT = 60
OBS = ".obsidian"  # mf:allow-path  (층 규칙이 안 보는 자리 — 읽고 알리기만)
PLUG, SNIP = OBS + "/plugins/", OBS + "/snippets/"
ENTRY = re.compile(r"^(- |\* |\d+\. |\||```|\{|\[)")        # 씨앗에서 항목(사용자 것)이 시작하는 줄
# 글 파일 가름 = dd.text_encoding(확장자 무관 · 11-21 · 옛 TEXT 확장자 목록은 .html·.svg·.yml 등을 빠뜨렸다)
# «부름»으로 안 치는 글 — 진단 기록·시험(가짜 경로)·층 규칙 목록(경로를 규칙으로 적을 뿐)
REF_SKIP = ["3_시스템/_ref/*", "3_시스템/_eval/*", "*/test_*", "*/known-hashes.json",  # mf:allow-path
            ".claude/skills/dist-sync/scripts/*", ".claude/skills/dist-sync/external.json"]  # mf:allow-path

_spec = importlib.util.spec_from_file_location("dist_diff", os.path.join(HERE, "dist-diff.py"))
dd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dd)          # 층 규칙·walk·sha 는 한 곳(dist-diff)


def git(root, *args, timeout=30, env=None):
    r = subprocess.run(["git", "-C", root, "-c", "core.quotepath=false", *args], capture_output=True, timeout=timeout, env=env,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")


def find_dist(A):
    """볼트 저장소의 worktree 가운데 dist-sync 가지가 걸린 곳."""
    code, out, _ = git(A, "worktree", "list", "--porcelain")
    if code:
        return None
    path = None
    for ln in out.splitlines():
        if ln.startswith("worktree "):
            path = ln[9:].strip()
        elif ln.strip() == "branch refs/heads/" + BRANCH and path and os.path.isdir(path):
            return os.path.abspath(path)
    return None


def load_ack(A):
    try:
        with open(os.path.join(A, ACK), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


ALWAYS = "자리째"   # 판과 상관없이 안 싣는다(--always) — 판 해시 ack 는 고칠 때마다 풀려 다시 «싣기»로 밀었다(11-15)


def ack_key(v):
    """적은 판 — 옛 꼴(문자열) · 새 꼴({"판", "까닭"})."""
    return v.get("판") if isinstance(v, dict) else v


def acked(ack, rel, key):
    k = ack_key(ack.get(rel))
    return k == key or (k == ALWAYS and key != "지움")


def unshipped(A, B, ack, rel):
    """배포판에 없고 볼트의 지금 판을 안 싣기로 적은 파일."""
    pa = os.path.join(A, *rel.split("/"))
    return not os.path.exists(os.path.join(B, *rel.split("/"))) and os.path.isfile(pa) and acked(ack, rel, dd.sha(pa))


def seed_key(rel, p):
    """씨앗의 견줄 판 — 시스템 문서(설계노트·사용자설명서)는 본문 전체 · 그 밖은 항목 앞 머리말만(frontmatter·빈 줄 빼고)."""
    if rel in dd.PERSONAL_EXCEPT:
        return dd.sha(p)
    try:
        with open(p, encoding="utf-8", errors="replace") as f:
            lines = f.read().replace("\r\n", "\n").split("\n")
    except OSError:
        return None
    if lines and lines[0] == "---":
        end = next((i for i, ln in enumerate(lines[1:], 1) if ln == "---"), 0)
        lines = lines[end + 1:]
    head = []
    for ln in lines:
        if ENTRY.match(ln):
            break
        if ln.strip():
            head.append(ln.rstrip())
    return "머리:" + hashlib.sha256("\n".join(head).encode("utf-8")).hexdigest()[:12]


def blind(A, B, ack, T):
    """층 규칙이 안 보는 자리 — 배포판에 손으로 넣은 옵시디언 설정 · 스니펫 · 새 플러그인 · 씨앗 머리말 · 시스템 문서."""
    out = []

    def row(rel, what, p, t=None):
        out.append({"path": rel, "what": what, "vault": stamp(os.path.getmtime(p)), "dist": stamp(t)})

    ob = os.path.join(B, OBS)
    for f in sorted(os.listdir(ob)) if os.path.isdir(ob) else []:
        rel, pa, pb = OBS + "/" + f, os.path.join(A, OBS, f), os.path.join(ob, f)
        if os.path.isfile(pa) and os.path.isfile(pb) and dd.sha(pa) != dd.sha(pb) and not acked(ack, rel, dd.sha(pa)):
            row(rel, "옵시디언 설정 다름", pa, T.get(rel))
    sd = os.path.join(A, *SNIP.rstrip("/").split("/"))
    for f in sorted(os.listdir(sd)) if os.path.isdir(sd) else []:
        rel = SNIP + f
        pa, pb = os.path.join(sd, f), os.path.join(B, *rel.split("/"))
        if f.endswith(".css") and dd.sha(pa) != dd.sha(pb) and not acked(ack, rel, dd.sha(pa)):
            row(rel, "스니펫 고침" if os.path.isfile(pb) else "새 스니펫", pa, T.get(rel))
    pd = os.path.join(A, *PLUG.rstrip("/").split("/"))
    ours = {d.rstrip("/").rsplit("/", 1)[-1] for d in dd.DIST_PLUGINS}
    for pid in sorted(os.listdir(pd)) if os.path.isdir(pd) else []:
        man, rel = os.path.join(pd, pid, "manifest.json"), PLUG + pid + "/"
        if pid not in ours and os.path.isfile(man) and not acked(ack, rel, "플러그인"):
            row(rel, "새 플러그인", man)
    for rel in dd.SEED:
        pa, pb = os.path.join(A, *rel.split("/")), os.path.join(B, *rel.split("/"))
        if not (os.path.isfile(pa) and os.path.isfile(pb)):
            continue          # 배포판에 없는 씨앗은 publish 가 넣는다
        k = seed_key(rel, pa)
        if k != seed_key(rel, pb) and not acked(ack, rel, k):
            row(rel, "씨앗 머리말 다름" if k.startswith("머리:") else "시스템 문서 다름", pa, T.get(rel))
    return out


def tracked(B):
    code, out, _ = git(B, "ls-files")
    return [r for r in out.splitlines() if r] if code == 0 else []


def drops(B, ship):
    """⑤ 배포판에 있는데 배포 목록 밖인 코어 — 빼기 후보. 한 번 잘못 실린 것이 고칠 때마다 다시 실리던 고리를 여기서 끊는다(11-15)."""
    if ship is None:
        return []
    return [{"path": r, "what": "목록 밖인데 배포판에 있음"} for r in sorted(tracked(B)) if dd.layer(r) in ("코어", "미분류") and dd.shipped(ship, r) is None]


# ⑥ 배포판 글이 «배포판에 없는 것»을 가리키나 — 파일 단위 목록이 못 보는 것(실린 파일 안의 개인 기능 갈래·없는 모듈 안내·시험의 개인 의존)
CODE = (".py", ".ps1", ".psm1", ".js", ".mjs", ".cjs", ".cmd", ".bat", ".sh", ".cs")
NOT_SHIPPED = os.path.join("3_시스템", "_index", "dist-sync", "not-shipped.txt")  # mf:allow-path  (안 싣는 이름 «정규식<TAB>이름» · 개인 층 — 이름은 대본에 적지 않는다)
SCAN_SKIP = {"_index", "_claude-memory", "__pycache__", ".trash", "node_modules", ".git"}
RULE_FILES = [".claude/skills/dist-sync/scripts/*", ".claude/skills/dist-sync/external.json", ".claude/skills/dist-sync/ship.json", "*/known-hashes.json"]  # mf:allow-path  층 규칙 목록 — 경로를 규칙으로 적을 뿐
REF_PREFIX = "가리킴 "


def ref_rules(A, B, files):
    """가리키면 안 되는 것 [(정규식, 이름)] — 볼트에만 있는 코드 파일 · 배포판에 없는 모듈 · not-shipped.txt 의 이름(개인 앱·노트)."""
    names = {r.rsplit("/", 1)[-1] for r in files}
    rules, seen = [], set()
    for top in ("3_시스템", ".claude"):  # mf:allow-path
        for dp, dns, fns in os.walk(os.path.join(A, top)):
            dns[:] = [d for d in dns if d not in SCAN_SKIP]
            for fn in fns:
                if fn.endswith(CODE) and fn not in names and len(fn) >= 7 and fn not in seen:
                    seen.add(fn)
                    rx = r"(?<![\w.-])" + re.escape(fn) + r"(?![\w-])"
                    stem, lits = fn[:-3], (fn,)
                    if fn.endswith(".py") and stem.isidentifier() and len(stem) >= 4:      # 부르는 꼴(import server — 11-12 구독 시험이 서버를 불렀다)
                        rx += r"|^\s*(?:import|from)\s+%s\b" % re.escape(stem)
                        lits = (fn, stem)
                    rules.append((lits, rx, "볼트에만 있는 " + fn))
    sk = os.path.join(A, ".claude", "skills")
    for m in sorted(os.listdir(sk)) if os.path.isdir(sk) else []:
        if os.path.isdir(os.path.join(sk, m)) and m[:1] not in "_." and not os.path.isdir(os.path.join(B, ".claude", "skills", m)):
            e = re.escape(m)
            kind = "모듈" if os.path.isfile(os.path.join(sk, m, "module.json")) else "스킬"     # 모듈 = module.json 이 있는 것만(스킬 폴더 ≠ 모듈)
            rules.append(((m,), r"/%s:|(?<![\w-])%s:[a-z]|skills/%s(?![\w-])|모듈 %s(?![\w-])|\(%s\)" % (e, e, e, e, e), "배포판에 없는 %s %s" % (kind, m)))
    try:
        with open(os.path.join(A, NOT_SHIPPED), encoding="utf-8") as f:
            for ln in f:
                ln = ln.rstrip("\n")
                if ln.strip() and not ln.startswith("#"):
                    rx, _, label = ln.partition("\t")
                    rules.append(((rx,) if re.fullmatch(r"[\w .-]+", rx) else None, rx, "안 싣는 이름 " + (label.strip() or rx)))
    except OSError:
        pass
    # 글자 그대로의 낱말(lits)이 글에 없으면 정규식을 안 돌린다 — 큰 번들(sheet.js 1,340만 자)에 앞쪽 경계 정규식 75개가 94초 걸렸다(11-16)
    return [(lits, re.compile(rx, re.M), label) for lits, rx, label in rules]


def pointers(A, B, ack):
    """⑥ [{path, what, why: [이름…]}] — 진단 기록·시험도 본다(11-15 에 실린 개인 기록·서버 시험이 거기 있었다). 적은(ack) 이름은 뺀다."""
    files = tracked(B)
    rules = ref_rules(A, B, files)
    out = []
    for rel in sorted(files):
        if dd.layer(rel) not in ("코어", dd.L_CLAUDE, "씨앗") or not dd.text_encoding(os.path.join(B, *rel.split("/"))) or any(fnmatch.fnmatch(rel, g) for g in RULE_FILES):
            continue
        try:
            with open(os.path.join(B, *rel.split("/")), encoding="utf-8", errors="replace") as f:
                t = f.read()
        except OSError:
            continue
        if rel.endswith((".js", ".mjs", ".cjs")):
            t = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), t)
        got = sorted({label for lits, rx, label in rules if (lits is None or any(x in t for x in lits)) and rx.search(t)})
        seen = set((ack_key(ack.get(REF_PREFIX + rel)) or "").split("|"))
        new = [g for g in got if g not in seen]
        if new:
            out.append({"path": rel, "what": "배포판에 없는 것을 가리킴", "why": new, "all": got})
    return out


def dist_texts(B):
    """배포판 코어 글(진단 기록·시험·층 규칙 목록 빼고) — «배포판이 부르는데 없는 것»을 가린다. 번들의 \\uXXXX 는 풀어서."""
    out = {}
    for rel, p in dd.walk(B).items():
        if dd.layer(rel) != "코어" or not dd.text_encoding(p) or any(fnmatch.fnmatch(rel, g) for g in REF_SKIP):
            continue
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                t = f.read()
        except OSError:
            continue
        if rel.endswith((".js", ".mjs", ".cjs")):
            t = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), t)
        out[rel] = t.replace("\\", "/")
    return out


def needed_by(rel, texts):
    keys = {rel.rstrip("/")} | ({rel[:-3]} if rel.endswith(".md") else set())
    return sorted(src for src, t in texts.items() if src != rel and any(k in t for k in keys))


def annotate(A, B, rows, texts, gaps, ack):
    """① 항목마다 가를 까닭(기계) — 필요(배포판 코어가 부름) · 익명화할 곳 · 안내 없는 바깥 설정.
    안 싣기로 적었는데 배포판 코어가 부르는 것(배포판에 없는 것만)도 ① 에 다시 올린다."""
    rules = [r for r in dd.LEAK if not r[1].startswith("세션 id")] + (dd.load_local_leaks(A) or [])
    # 익명화할 곳은 통째로 실릴 층만 — 씨앗(항목)·옵시디언 설정은 늘 개인 값이 들어 있어 셀 뜻이 없다.
    # 동봉 플러그인 번들은 센다 — 소스의 CSS 주석이 번들 문자열에 \uXXXX 로 남는다(11-21 brain-source 0.36.30 main.js 호칭 2곳을 못 셈)
    files = {x["path"]: os.path.join(A, *x["path"].split("/")) for x in rows
             if dd.layer(x["path"]) in ("코어", dd.L_CLAUDE, "미분류")
             and (not x["path"].startswith(OBS + "/") or any(x["path"].startswith(d) for d in dd.DIST_PLUGINS))}
    plug = {k for k in files if k.startswith(OBS + "/")}      # 번들은 볼트 전용 패턴만 — 내장 이메일 꼴은 남의 라이선스 고지에 수백 개
    leaks = collections.Counter(h[0] for h in dd.scan_leaks({k: v for k, v in files.items() if os.path.isfile(v) and k not in plug}, rules))
    if plug and dd.load_local_leaks(A):
        leaks.update(h[0] for h in dd.scan_leaks({k: files[k] for k in plug if os.path.isfile(files[k])}, dd.load_local_leaks(A)))
    outside = collections.Counter(rel for rel, _, _ in gaps)

    def first(need):
        return "%s%s" % (need[0], " 외 %d" % (len(need) - 1) if len(need) > 1 else "")

    for x in rows:
        gone = x["what"] == "볼트에서 지움"
        in_dist = os.path.exists(os.path.join(B, *x["path"].rstrip("/").split("/")))
        need, why = needed_by(x["path"], texts) if gone or not in_dist else [], []     # «필요»는 배포판에 없는 것만 뜻이 있다
        if need:
            why.append(("배포판 코어가 아직 부름 ← " if x["what"] == "볼트에서 지움" else "필요 ← ") + first(need))
        if leaks.get(x["path"]):
            why.append("익명화할 곳 %d" % leaks[x["path"]])
        if outside.get(x["path"]):
            why.append("안내 없는 바깥 설정 %d" % outside[x["path"]])
        x["why"] = why
    seen = {x["path"] for x in rows}
    for rel, v in sorted(ack.items()):
        pa = os.path.join(A, *rel.rstrip("/").split("/"))
        if rel in seen or ack_key(v) == "지움" or not os.path.exists(pa) or os.path.exists(os.path.join(B, *rel.rstrip("/").split("/"))):
            continue
        need = needed_by(rel, texts)
        if need:
            why = v.get("까닭") if isinstance(v, dict) else None
            rows.append({"path": rel, "what": "안 싣기로 했는데 배포판이 부름", "vault": stamp(os.path.getmtime(pa)), "dist": "?",
                         "why": ["필요 ← " + first(need)] + (["적은 까닭: " + why] if why else [])})
    return rows


def last_touch(B):
    """배포판 가지에서 경로마다 마지막으로 고친 커밋 시각 · 맨 마지막 커밋 시각."""
    code, out, _ = git(B, "log", "--format=@%ct", "--name-only", "HEAD", timeout=60)
    T, cur, top = {}, None, None
    for ln in out.splitlines() if code == 0 else []:
        if ln.startswith("@"):
            cur = int(ln[1:])
            top = top or cur
        elif ln and ln not in T:
            T[ln] = cur
    return T, top


def stamp(t):
    return datetime.datetime.fromtimestamp(t).strftime("%m-%d %H:%M") if t else "?"


def vault_revs(A):
    """볼트 커밋 [(시각, 해시)] — 새것부터(첫 부모 줄기만)."""
    code, out, _ = git(A, "log", "--first-parent", "--format=%ct %H", "HEAD", timeout=60)
    return [(int(t), h) for t, h in (ln.split() for ln in out.splitlines() if ln.strip())] if code == 0 else []


def same_as_before(A, rel, t, now_sha, revs):
    """t 이전 볼트 커밋의 판과 지금 판이 같으면 고친 것이 아니라 시각만 바뀐 것(checkout 등)."""
    rev = next((h for ct, h in revs if ct <= t), None)
    if not rev:
        return False
    r = subprocess.run(["git", "-C", A, "show", "%s:%s" % (rev, rel)], capture_output=True, timeout=20,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode:
        return False
    return hashlib.sha256(r.stdout.replace(b"\r\n", b"\n")).hexdigest()[:12] == now_sha


def unsynced(A, B, ship=None, undecided=None):
    """① — 배포 목록(ship)이 있으면 목록 밖 코어는 ① 이 아니라 undecided(정할 것)로 · 배포판에 이미 있으면 ⑤(빼기 후보)가 센다."""
    fa, fb = dd.walk(A), dd.walk(B)
    T, top = last_touch(B)
    ack = load_ack(A)
    revs = rules = None
    out = []
    for rel, p in sorted(fa.items()):
        lay = dd.layer(rel)
        if lay not in ("코어", dd.L_CLAUDE, "미분류"):
            continue
        listed = lay not in ("코어", "미분류") or dd.shipped(ship, rel) is not None    # 미분류도 목록이 정한다(층에서 빼도 숨지 않게)
        if not listed and rel in fb:
            continue          # 배포판에 있는데 목록 밖 = ⑤
        mine = dd.sha(p)
        if rel in fb and mine == dd.sha(fb[rel]):
            continue
        if acked(ack, rel, mine):
            continue
        m = os.path.getmtime(p)
        early = False
        if rel in fb:      # 시각 비교는 고친 파일에만 — 새 파일은 ack 로만 빠진다
            t = T.get(rel, top)
            if t is None or m <= t:
                # 배포판이 이 파일을 다른 까닭(익명화 등)으로 고친 커밋이 볼트의 앞선 고침을 빼먹으면 시각으로는 영영 안 뜬다
                # (11-21 web_expire_check.py — 볼트 10:17 고침을 배포판 12:22 «개인 값 빼기» 커밋이 옛 판으로 덮음)
                rules = leak_rules(A) if rules is None else rules
                if t is None or not hidden_edit(p, fb[rel], rules):
                    continue
                early = True
            revs = vault_revs(A) if revs is None else revs
            if not early and same_as_before(A, rel, t, mine, revs):
                continue
        what = "층 미정 새 파일" if lay == "미분류" else ("새 파일" if rel not in fb else "고침")
        if early:
            what = "고침(배포판 손댐보다 먼저 고친 줄 · 익명화 줄 아님)"
        row = {"path": rel, "what": what, "vault": stamp(m), "dist": stamp(t if rel in fb else None)}
        if not listed:
            if undecided is not None:
                undecided.append(dict(row, what="목록 밖 " + what))
            continue
        out.append(row)
    only = [r for r in sorted(set(fb) - set(fa)) if dd.layer(r) == "코어" and dd.shipped(ship, r) is not None]
    if only:      # 볼트에서 지운 때 — 배포판이 그 파일을 마지막으로 고친 뒤만 본다(긴 이력을 다 훑지 않게 한 번에)
        since = min(T.get(r, 0) for r in only)
        code, log, _ = git(A, "log", "--diff-filter=D", "--format=@%ct", "--name-only", "--since=%d" % since, "HEAD", "--", *only, timeout=60)
        gone, cur = {}, None
        for ln in log.splitlines() if code == 0 else []:
            if ln.startswith("@"):
                cur = int(ln[1:])
            elif ln and ln not in gone:
                gone[ln] = cur
        for rel in only:
            g = gone.get(rel)
            if g and g > T.get(rel, 0) and not acked(ack, rel, "지움"):
                out.append({"path": rel, "what": "볼트에서 지움", "vault": stamp(g), "dist": stamp(T.get(rel))})
    return out + blind(A, B, ack, T) + merge_marks(A, B, ship, ack), top


def leak_rules(A):
    """익명화 줄을 가르는 패턴 — 내장(이메일·홈 경로 등 · 세션 id 빼고) + 볼트 전용(leak-patterns.txt)."""
    return [re.compile(rx) for rx, label in dd.LEAK + (dd.load_local_leaks(A) or []) if not label.startswith("세션 id")]


ANON_WORDS = re.compile(r"사용자|제작자|배포판|개인|\[\[|%%")    # 배포판 쪽에 이 말이 있으면 익명화로 바꾼 줄로 본다


def hidden_edit(pa, pb, rules):
    """볼트 판과 배포판 판의 다른 덩어리 가운데 «익명화 줄이 아닌 것»이 있나 — 어느 쪽에도 개인 패턴이 없고,
    익명화 말(사용자·제작자·배포판·개인·링크 꼬리)도 없고, 빈 줄만도 아닌 덩어리. 익명화로 늘 다른 파일은 안 잡는다."""
    try:
        with open(pa, encoding="utf-8", errors="replace") as f:
            a = f.read().replace("\r\n", "\n").split("\n")
        with open(pb, encoding="utf-8", errors="replace") as f:
            b = f.read().replace("\r\n", "\n").split("\n")
    except OSError:
        return False
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, b, a, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        chunk = b[i1:i2] + a[j1:j2]
        if not "".join(chunk).strip():
            continue
        if any(r.search(ln) for ln in chunk for r in rules) or any(ANON_WORDS.search(ln) for ln in chunk):
            continue
        return True
    return False


def merge_marks(A, B, ship, ack):
    """배포판 py 에 같은 이름 최상위 정의가 두 번 — 합치기 흔적(11-21 follow.py practice() 두 번 · «익명화 판» ack 가 숨김).
    ack 와 상관없이 센다(ack 는 볼트 판을 적은 것이라 배포판 쪽 흔적을 못 가린다) · 일부러면 --ack <경로> --why 대신 고친다."""
    out = []
    for rel in tracked(B):
        if not rel.endswith(".py") or (ship is not None and dd.layer(rel) in ("코어", "미분류") and dd.shipped(ship, rel) is None):
            continue
        p = os.path.join(B, *rel.split("/"))
        try:
            with open(p, encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (OSError, SyntaxError, ValueError, UnicodeDecodeError):
            continue
        names = collections.Counter(n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
        dup = sorted(k for k, v in names.items() if v > 1)
        if dup:
            out.append({"path": rel, "what": "배포판 합치기 흔적(같은 이름 정의 두 번: %s)" % ", ".join(dup),
                        "vault": "?", "dist": stamp(os.path.getmtime(p))})
    return out


def commits(B, rng):
    code, out, _ = git(B, "log", "--format=%h %s", rng)
    return [ln for ln in out.splitlines() if ln.strip()] if code == 0 else None


def fetch_age(B):
    code, d, _ = git(B, "rev-parse", "--git-path", "FETCH_HEAD")     # worktree 마다 따로 있다
    if code:
        return None
    p = d.strip() if os.path.isabs(d.strip()) else os.path.join(B, d.strip())
    try:
        return os.path.getmtime(p)
    except OSError:
        return None


FETCH_ENV = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
FETCH_ARGS = ["-c", "credential.helper=", "-c", "http.lowSpeedLimit=1000", "-c", "http.lowSpeedTime=20", "fetch", "--quiet"]


def fetch(B):
    """원격을 받는다 — 묻는 창이 뜨지 않게(로그인 도우미 끔)."""
    try:
        code, _, err = git(B, *FETCH_ARGS, timeout=FETCH_TIMEOUT, env=FETCH_ENV)
    except subprocess.TimeoutExpired:
        return "시간 넘김"
    return None if code == 0 else (err.strip().splitlines() or ["실패"])[-1][:80]


def fetch_later(B):
    """건강 줄용 — 하루가 지났으면 창 없이 따로 받고 기다리지 않는다(다음 재기가 결과를 본다)."""
    age = fetch_age(B)
    if age and datetime.datetime.now().timestamp() - age < FETCH_EVERY:
        return False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        subprocess.Popen(["git", "-C", B, *FETCH_ARGS], env=FETCH_ENV, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    except OSError:
        return False
    return True


def check(A=VAULT, B=None, do_fetch=False, ship_path=None):
    B = B or find_dist(A)
    if not B:
        return {"dist": None}
    res = {"dist": B, "fetch_error": fetch(B) if do_fetch else None}
    ship = dd.load_ship(A, ship_path)
    res["ship"] = None if ship is None else {"줄": len(ship), "잘못": dd.ship_problems(ship)}
    res["undecided"] = []
    res["unsynced"], top = unsynced(A, B, ship, res["undecided"])
    res["drops"] = drops(B, ship)
    res["pointers"] = pointers(A, B, load_ack(A)) if ship is not None else []
    res["make"] = make_paths(A, ship_path) if ship is not None else None
    res["last_publish"] = stamp(top)
    code, up, _ = git(B, "rev-parse", "--abbrev-ref", "@{upstream}")
    res["upstream"] = up.strip() if code == 0 else None
    if res["upstream"]:
        res["unpushed"] = commits(B, "@{upstream}..HEAD") or []
        res["remote_only"] = commits(B, "HEAD..@{upstream}") or []
    else:
        res["unpushed"], res["remote_only"] = [], []
    code, st, _ = git(B, "status", "--porcelain")
    res["uncommitted"] = [ln[3:] for ln in st.splitlines() if ln.strip()] if code == 0 else []
    res["fetched"] = stamp(fetch_age(B))
    ack = load_ack(A)
    gaps, res["external"] = external_gaps(A, B, ack)
    annotate(A, B, res["unsynced"], dist_texts(B), gaps, ack)
    res["contracts"] = contract_gaps(A, B)
    return res


def contract_gaps(A, B):
    """⑧ 이 볼트 모듈이 쓰는 코어 이름(uses_core)이 배포판에 없음 → ["모듈 → 파일 이름 없음 …"]. 꺼진 모듈·안 싣는 모듈도 잰다."""
    s = importlib.util.spec_from_file_location("dist_contracts", os.path.join(HERE, "contracts.py"))
    c = importlib.util.module_from_spec(s)
    s.loader.exec_module(c)
    try:
        broken, _ = c.names(A, B, on_only=False)
    except (OSError, ValueError, KeyError, ImportError) as e:
        return ["못 잼(%s)" % type(e).__name__]
    return ["%s → %s %s" % (b["module"], b["file"], "파일 없음" if b["missing"] is None else "이름 없음 " + ", ".join(b["missing"])) for b in broken]


def make_paths(A, ship_path=None):
    """⑦ 개인 파일마다 «만드는 길»(11-16 S6 사용자 «배포판에 개인 파일을 만드는 법이 나와있어야함») — 배포 목록 «개인» 칸을 읽는다.
    잡는 것: 살필 곳의 볼트 개인 파일이 어느 종류(자리 glob · 로그인 조리법이 가리키는 칸)에도 안 듦 · 종류에 길이 없음 · 예시가 볼트에 없거나 배포 목록 밖.
    돌려줌 = [{path, why}] · 칸이 없으면 None(옛 목록 — 안 잼)."""
    p = ship_path or os.path.join(A, *dd.SHIP_REL.split("/"))
    try:
        reg = (json.load(open(p, encoding="utf-8")) or {}).get("개인")
    except (OSError, ValueError):
        return None
    if not isinstance(reg, dict):
        return None
    ship = dd.load_ship(A, ship_path) or {}
    shipped = lambda rel: rel in ship or any(x.endswith("/") and rel.startswith(x) for x in ship)  # noqa: E731
    kinds = [k for k in reg.get("종류") or [] if isinstance(k, dict)]
    out = []
    for k in kinds:
        if not k.get("길"):
            out.append({"path": k.get("이름") or "?", "why": "만드는 길 없음(종류에 «길» 칸 없음)"})
        ex = k.get("예시")
        if ex and (not os.path.exists(os.path.join(A, *ex.split("/"))) or not shipped(ex)):
            out.append({"path": ex, "why": "예시(빈 틀)가 볼트에 없거나 배포 목록 밖 — %s" % (k.get("이름") or "?")})
    import glob
    named = set()                    # 로그인 조리법이 칸으로 가리키는 자리(단위 지도·설정 — 옛 자리에 있어도 그 종류)
    for rp in glob.glob(os.path.join(A, *"3_시스템/collect/browser".split("/"), "*.json")):
        try:
            rc = json.load(open(rp, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for k in kinds:
            for f in k.get("조리법칸") or []:
                if isinstance(rc, dict) and isinstance(rc.get(f), str):
                    named.add("3_시스템/" + rc[f])  # mf:allow-path  (조리법 칸이 가리키는 자리 이름 · 파일을 열지 않음)
    pats = [g for k in kinds for g in k.get("자리") or []]
    seen = set()
    for g in reg.get("살필") or []:
        for f in glob.glob(os.path.join(A, *g.split("/")), recursive=True):
            rel = os.path.relpath(f, A).replace("\\", "/")
            if not os.path.isfile(f) or rel in seen or rel in named or "/__pycache__/" in rel:
                continue
            seen.add(rel)
            if not any(fnmatch.fnmatch(rel, x) for x in pats):
                out.append({"path": rel, "why": "개인 파일인데 종류(만드는 길)가 없음 — 배포 목록 «개인» 칸에 더하거나 자리를 옮김"})
    return out


def external_gaps(A, B, ack=None):
    """④ 볼트 밖 설정 추적 — 코어(배포판 + 곧 실릴 볼트 코어)가 볼트 밖을 건드리는데 안내 목록(external.json)에 없는 곳 → ([(파일, 종류, 줄)], 말).
    배포판에 없고 지금 판을 안 싣기로 적은(ack) 파일은 뺀다 — 안 실리니 받는 사람에게 안내할 것이 없다(11-14 gpu_guard 가 ack 뒤에도 남았다). 다시 고치면 다시 잡힌다."""
    s = importlib.util.spec_from_file_location("dist_external", os.path.join(HERE, "external.py"))
    ex = importlib.util.module_from_spec(s)
    s.loader.exec_module(ex)
    try:
        gaps, bad = ex.scan([B, A], layer=dd.layer)
    except (OSError, ValueError, KeyError) as e:
        return [], ["목록 못 읽음(%s)" % type(e).__name__]
    ack = ack or {}
    gaps = [g for g in gaps if not unshipped(A, B, ack, g[0])]
    return gaps, ["%s:%d — %s" % (rel, n, kind) for rel, kind, n in gaps] + ["항목 %s — %s" % b for b in bad]


def scope(r):
    """범위 칸 — 정할 것(목록 밖 새 코어) · 빼기 후보 · 가리킴 · 목록의 잘못."""
    return len(r.get("undecided", [])) + len(r.get("drops", [])) + len(r.get("pointers", [])) + len((r.get("ship") or {}).get("잘못", [])) + len(r.get("make") or [])


def total(r):
    return len(r["unsynced"]) + len(r["unpushed"]) + len(r["uncommitted"]) + len(r["remote_only"]) + len(r.get("external", [])) + len(r.get("contracts", [])) + scope(r)


def todo(r):
    t = []
    if scope(r):
        t.append("싣기·안 싣기·빼기 정하기")
    if r["unsynced"]:
        t.append("«배포판 적용»")
    if r["uncommitted"]:
        t.append("배포판 worktree 커밋")
    if r["unpushed"]:
        t.append("push 승인")
    if r["remote_only"]:
        t.append("원격 받아 합치기")
    if r.get("external"):
        t.append("바깥 설정 안내 채우기")
    if r.get("contracts"):
        t.append("모듈 계약 맞추기(코어 이름을 싣거나 모듈을 고침)")
    return " · ".join(t)


def summary(r):
    """건강 줄 한 줄 — 무엇이 몇 건 · 할 일."""
    if not r.get("dist"):
        return "배포판 worktree 없음(점검 안 함)"
    n = total(r)
    note = "" if r["upstream"] else " · 원격 짝(upstream) 없어 push·받을 것은 못 잼"
    if not n:
        return "배포판 최신(어긋남 0 · 원격 받아 본 때 %s)%s" % (r["fetched"], note)
    parts = [("정할 것", len(r.get("undecided", []))), ("빼기 후보", len(r.get("drops", []))),
             ("없는 것을 가리킴", len(r.get("pointers", []))), ("배포 목록 잘못", len((r.get("ship") or {}).get("잘못", []))),
             ("만드는 길 없는 개인 파일", len(r.get("make") or [])),
             ("안 올린 고침", len(r["unsynced"])), ("커밋 안 함", len(r["uncommitted"])),
             ("push 안 함", len(r["unpushed"])), ("받을 것", len(r["remote_only"])),
             ("안내 없는 바깥 설정", len(r.get("external", []))), ("모듈 계약 어긋남", len(r.get("contracts", [])))]
    if r.get("ship", 0) is None:
        note += " · 배포 목록 없음(옛 동작 — 코어 자리의 새 파일이 기본으로 실린다)"
    return "배포판 어긋남 %d — %s · 할 일 %s%s" % (n, " · ".join("%s %d" % p for p in parts if p[1]), todo(r), note)


def report(r):
    if not r.get("dist"):
        return summary(r)
    L = ["배포판 점검 — %s · 배포판 %s" % (datetime.datetime.now().strftime("%m-%d %H:%M"), r["dist"]),
         "마지막 배포 커밋 %s · 원격 받아 본 때 %s%s" % (r["last_publish"], r["fetched"],
                                                 " · 받기 실패: %s" % r["fetch_error"] if r.get("fetch_error") else "")]
    L.append("① 볼트에서 바뀌었는데 배포판에 안 간 코어 %d" % len(r["unsynced"]))
    L += ["   - %s (%s · 볼트 %s · 배포판 %s)%s" % (x["path"], x["what"], x["vault"], x["dist"], " — " + " · ".join(x["why"]) if x.get("why") else "")
          for x in r["unsynced"]]
    L.append("② 배포판에 커밋했는데 push 안 한 것 %d%s" % (len(r["unpushed"]), " · 커밋 안 한 고침 %d" % len(r["uncommitted"]) if r["uncommitted"] else ""))
    L += ["   - " + c for c in r["unpushed"]] + ["   - (커밋 안 함) " + p for p in r["uncommitted"][:20]]
    L.append("③ 원격에만 있는 것(받아 합칠 것) %d" % len(r["remote_only"]))
    L += ["   - " + c for c in r["remote_only"]]
    L.append("④ 볼트 밖 설정인데 안내 목록(external.json)에 없는 곳 %d" % len(r.get("external", [])))
    L += ["   - " + c for c in r.get("external", [])]
    if r.get("ship") is None:
        L.append("⑤⑥ 배포 목록(%s)이 없어 범위는 안 잼 — 코어 자리의 새 파일이 기본으로 실린다" % dd.SHIP_REL)
    else:
        bad = r["ship"]["잘못"]
        L.append("⑤ 정할 것(목록 밖 새 코어) %d · 빼기 후보(배포판에 있는데 목록 밖) %d%s" % (
            len(r["undecided"]), len(r["drops"]), " · 목록 잘못(폴더째 적은 자리) %d" % len(bad) if bad else ""))
        L += ["   - %s (%s · 볼트 %s)" % (x["path"], x["what"], x["vault"]) for x in r["undecided"]]
        L += ["   - %s (빼기 후보)" % x["path"] for x in r["drops"]]
        L += ["   - %s (목록 잘못 — 낱개 경로로)" % x for x in bad]
        L.append("⑥ 배포판 글이 배포판에 없는 것을 가리킴 %d" % len(r["pointers"]))
        L += ["   - %s — %s" % (x["path"], " · ".join(x["why"])) for x in r["pointers"]]
        mk = r.get("make")
        L.append("⑦ 만드는 길 없는 개인 파일 %s" % ("— 배포 목록에 «개인» 칸 없음(안 잼)" if mk is None else len(mk)))
        L += ["   - %s — %s" % (x["path"], x["why"]) for x in mk or []]
    L.append("⑧ 모듈이 쓰는 코어 이름이 배포판에 없음 %d" % len(r.get("contracts", [])))
    L += ["   - " + c for c in r.get("contracts", [])]
    L.append(summary(r))
    return "\n".join(L)


def ack(A, paths, why=None, always=False, ref_of=None):
    """안 싣기로 한 판을 적는다 — 그 파일을 다시 고치면 다시 잡힌다. 새 플러그인은 폴더째(판을 올려도 안 깨어남) · 씨앗은 머리말 판.
    까닭(why)을 함께 적으면 «안 실음»과 «아직»·«잊음»이 갈린다(--acks).
    always = 판과 상관없이 안 싣는다(까닭 필수) · ref_of = ⑥ 배포판 파일이 지금 가리키는 이름들을 «확인함»으로 적는다(선택 갈래·안내 글 등 · 까닭 필수)."""
    if (always or ref_of is not None) and not why:
        raise ValueError("--always·--ref 는 까닭(--why)이 있어야 한다")
    cur = load_ack(A)
    done = []
    for p in paths:
        rel = (os.path.relpath(os.path.abspath(p), A) if os.path.isabs(p) else p).replace("\\", "/")
        full = os.path.join(A, *rel.rstrip("/").split("/"))
        if ref_of is not None:
            hit = next((x for x in ref_of if x["path"] == rel), None)
            if hit:
                cur[REF_PREFIX + rel] = {"판": "|".join(hit["all"]), "까닭": why}
                done.append(rel)
            continue
        if always:
            cur[rel] = {"판": ALWAYS, "까닭": why}
            done.append(rel)
            continue
        if rel.startswith(PLUG) and os.path.isdir(full):
            rel, key = PLUG + rel[len(PLUG):].strip("/").split("/")[0] + "/", "플러그인"
        elif not os.path.isfile(full):
            key = "지움"
        elif rel in dd.SEED:
            key = seed_key(rel, full)
        else:
            key = dd.sha(full)
        cur[rel] = {"판": key, "까닭": why} if why else key
        done.append(rel)
    path = os.path.join(A, ACK)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(cur, f, ensure_ascii=False, indent=1)
        f.write("\n")
    try:
        os.remove(os.path.join(os.path.dirname(path), "check.json"))     # 건강 줄이 담아 둔 점검 — 바로 다시 재게
    except OSError:
        pass
    return done


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="배포판 최신 점검(볼트 코어 ↔ 배포판 worktree ↔ 원격)")
    ap.add_argument("--a", default=VAULT, help="볼트(기본 = 이 대본이 든 볼트)")
    ap.add_argument("--b", help="배포판 worktree(기본 = dist-sync 가지가 걸린 worktree)")
    ap.add_argument("--fetch", action="store_true", help="원격을 먼저 받는다")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ack", nargs="+", metavar="경로", help="이 판은 안 싣기로 함(① 에서 뺌)")
    ap.add_argument("--why", help="--ack 의 까닭(개인·특정 PC·실험 등)")
    ap.add_argument("--always", action="store_true", help="--ack 를 판과 상관없이(자리째) · 까닭 필수")
    ap.add_argument("--ref", action="store_true", help="--ack 경로 = ⑥ 의 배포판 파일 — 지금 가리키는 이름들을 확인함으로 적음 · 까닭 필수")
    ap.add_argument("--ship", metavar="파일", help="배포 목록 초안으로 미리 잰다(기본 = %s)" % dd.SHIP_REL)
    ap.add_argument("--acks", action="store_true", help="안 싣기로 적은 것과 까닭")
    a = ap.parse_args()
    A = os.path.abspath(a.a)
    if a.ack:
        ref_of = None
        if a.ref:
            B = os.path.abspath(a.b) if a.b else find_dist(A)
            ref_of = pointers(A, B, {}) if B else []
        try:
            print("안 싣기로 적음: " + ", ".join(ack(A, a.ack, a.why, a.always, ref_of)))
        except ValueError as e:
            print(e)
            return 2
        return 0
    if a.acks:
        rows = sorted(load_ack(A).items())
        for rel, v in rows:
            print("%s — %s" % (rel, (v.get("까닭") if isinstance(v, dict) else None) or "까닭 없음"))
        print("%d건 · 까닭 없음 %d" % (len(rows), sum(not (isinstance(v, dict) and v.get("까닭")) for _, v in rows)))
        return 0
    try:
        r = check(A, os.path.abspath(a.b) if a.b else None, a.fetch, a.ship)
    except (OSError, subprocess.SubprocessError) as e:
        print("못 잼: %s" % e)
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else report(r))
    return 1 if r.get("dist") and total(r) else 0


if __name__ == "__main__":
    sys.exit(main())
