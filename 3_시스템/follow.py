# -*- coding: utf-8 -*-
"""**따라가기** — 옵시디언 밖(윈도 탐색기·다른 앱)에서 옮기거나 지운 파일을 알아채고 뒤처리한다 (설계안 §19.3 · ADR-021 개정).

왜: 옵시디언 안 이동·삭제는 장부에 남지만(R5.5) 바깥에서 한 것은 장부·링크·색인·짝 메모·LMS 목록이 못 따라간다(옵시디언도 «지움 + 생김»으로 본다).
내용 칸 파일마다 사진(경로·크기·시각·파일번호·sha256)을 두고 지금과 견준다 — 사라진 경로의 파일번호·해시가 새 경로에 있으면 옮김,
어디에도 없으면 바깥에서 지움. 장부에 이미 적힌 일(fileops·옵시디언·수집 대본)은 사진에 먼저 반영해 «바깥»으로 치지 않는다.

  py -3 3_시스템/follow.py [--dry] [--json] [--accept]   비교 → 적용 → 사진 갱신 (처음 = 사진만 · --accept = 한꺼번에 사라진 것도 지움으로)
  py -3 3_시스템/follow.py --hook                        세션 시작용 — 알릴 것이 있을 때만 한 줄 · 해시는 한 번에 300MB 까지
  py -3 3_시스템/follow.py pending [--json]              답을 기다리는 것(사라진 LMS 원본 · 행방 모름)
  py -3 3_시스템/follow.py refetch <경로…>|--all         LMS 목록에서 빼서 다음 수집 때 다시 받는다
  py -3 3_시스템/follow.py keep <경로…>|--all            그대로 둔다(의도한 삭제 · 행방 모름 확인) — 목록에서 뺌

사진 = 3_시스템/_index/follow/snapshot.json(git 밖) · 장부 줄 = ops.jsonl 의 `outside: true` + `via: follow`(되돌리기 = fileops undo <묶음>).
"""
import argparse
import contextlib
import datetime as dt
import glob
import io
import json
import os
import posixpath
import subprocess
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileops  # noqa: E402 — 장부·링크 고치기는 fileops 한 벌을 쓴다
import roles  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "_index", "follow")
SNAP = os.path.join(OUT, "snapshot.json")
PENDING = os.path.join(OUT, "pending.json")
LOCK = os.path.join(OUT, ".lock")
MANIFEST = os.path.join(HERE, "_index", "lms", "manifest.json")
COLLECT = os.path.join(HERE, "_index", "collect")   # 웹 수집 상태(*.json)
ARCH = os.path.join(COLLECT, "archive")             # 웹 수집 보관 칸 — 볼트와 같은 상대 경로의 거울(web-collect 가 옮김 · 장부 밖)
SCHEMA = 1
HOOK_BUDGET = 300 * 1024 * 1024                     # 세션 시작을 붙들지 않게 — 남은 해시는 다음 비교 때
MIN_HASH = 64                                       # 이보다 작은 파일은 내용이 같아도 같은 파일로 치지 않는다(빈 틀·한 줄 메모)
STALE_LOCK = 300
WHY = "바깥에서 직접(따라가기)"
IGNORE_END = (".tmp", ".crdownload", ".part", ".~fileops")
IGNORE_NAME = ("desktop.ini", "thumbs.db")


def mass(n):
    """한꺼번에 이만큼 넘게 사라지면 지움으로 치지 않고 묻는다 — 폴더 잠김·복원·디스크 문제일 수 있다(색인을 지우기 전에 사람이 본다)."""
    return max(100, n // 5)


def under(p, roots):
    return any(p == r or p.startswith(r + "/") for r in roots)


def ignored(name):
    low = name.lower()
    return name.startswith((".", "~")) or low in IGNORE_NAME or low.endswith(IGNORE_END)


def content_roots():
    return [roles.path("work"), roles.path("sources"), roles.path("knowledge")]


def machine_dirs():
    """내용 칸 안의 기계 파생물 — ingest·수집 대본이 스스로 옮기고 지운다."""
    return {roles.path("source_index"), roles.path("sources") + "/_lms"}


def in_scope(p):
    if not under(p, content_roots()) or under(p, machine_dirs()):
        return False
    parts = p.split("/")
    return not any(x.startswith(".") for x in parts[:-1]) and not ignored(parts[-1])


def load_json(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_json(p, obj, indent=None):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
    os.replace(tmp, p)


@contextlib.contextmanager
def locked():
    """세션 시작·옵시디언이 함께 돌려도 한 번만 — 잡지 못하면 그냥 끝낸다(다른 쪽이 하는 중)."""
    os.makedirs(OUT, exist_ok=True)
    try:
        if time.time() - os.path.getmtime(LOCK) > STALE_LOCK:
            os.remove(LOCK)
    except OSError:
        pass
    try:
        fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except OSError:
        yield False
        return
    os.close(fd)
    try:
        yield True
    finally:
        try:
            os.remove(LOCK)
        except OSError:
            pass


# ── 사진 ─────────────────────────────────────────────────────────────────

def scan(base, budget=None):
    """내용 칸 파일 → ({경로: [크기, 시각, 파일번호, sha256]}, 못 읽은 폴더). 크기·시각이 같으면 base 값을 그대로 쓴다(해시는 새로 본 파일만).
    못 읽은 폴더는 «지움»이 아니다 — 부르는 쪽이 그 아래를 있던 그대로 둔다."""
    files, blind = {}, []
    left = budget
    skip = machine_dirs()
    stack = content_roots()
    while stack:
        d = stack.pop()
        try:
            entries = list(os.scandir(os.path.join(VAULT, *d.split("/"))))
        except FileNotFoundError:
            continue
        except OSError:
            blind.append(d)
            continue
        for e in entries:
            r = d + "/" + e.name
            try:
                if e.is_dir(follow_symlinks=False):
                    if not e.name.startswith(".") and r not in skip:
                        stack.append(r)
                    continue
                if ignored(e.name) or not e.is_file(follow_symlinks=False):
                    continue
                st = e.stat(follow_symlinks=False)
            except OSError:
                if r in base:
                    files[r] = base[r]
                continue
            b = base.get(r)
            same = b and b[0] == st.st_size and b[1] == st.st_mtime_ns
            ino = b[2] if same and b[2] else 0
            sha = b[3] if same and b[3] else ""
            if not ino:
                try:
                    ino = e.inode()
                except OSError:
                    ino = 0
            if not sha and st.st_size and (left is None or st.st_size <= left):
                try:
                    sha = fileops.sha256(e.path)
                    left = None if left is None else left - st.st_size
                except OSError:             # 잠긴 파일(Word 등) — 다음 비교 때
                    sha = ""
            files[r] = [st.st_size, st.st_mtime_ns, ino, sha]
    return files, blind


def ledger_end(ctx):
    try:
        return os.path.getsize(ctx.abs(fileops.OPS))
    except OSError:
        return 0


def ledger_since(ctx, pos, ts):
    """pos 뒤에 장부에 적힌 일 → (행위들, 새 끝). 장부가 줄었으면(git 되돌림 등) 시각으로 가른다."""
    end = ledger_end(ctx)
    if end < pos:
        return [e for e in fileops.load_events(ctx) if e.get("ts", "") >= ts], end
    try:
        with open(ctx.abs(fileops.OPS), "rb") as f:
            f.seek(pos)
            data = f.read()
    except OSError:
        return [], pos
    data = data[:data.rfind(b"\n") + 1]     # 적는 중인 마지막 줄은 다음 번에
    out = []
    for ln in data.decode("utf-8", "replace").splitlines():
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out, pos + len(data)


def replay(old, events):
    """장부에 적힌 일 = 바깥이 아니다 → 사진을 그 뒤 모습으로 먼저 고친다."""
    for e in events:
        op, s, d = e.get("op"), e.get("src") or "", e.get("dst") or ""
        if not s or not (op in ("mv", "rename", "rm", "out") or (op == "cp" and e.get("moved"))):
            continue
        low = s.lower()
        hit = [k for k in old if k.lower() == low or k.lower().startswith(low + "/")]
        for k in hit:
            v = old.pop(k)
            if op in ("mv", "rename") and d and in_scope(d + k[len(s):]):
                old[d + k[len(s):]] = v


# ── 판정 ─────────────────────────────────────────────────────────────────

def judge(old, cur, blind=(), expected=()):
    """→ (옮김 [(옛, 새)], 지움 {경로: 값}, 행방 모름 [{path, candidates}]). 같은 내용이 둘 이상이면 고르지 않는다."""
    exp_s, exp_d = [x[0] for x in expected], [x[1] for x in expected]
    gone = {p: e for p, e in old.items() if p not in cur and not under(p, blind) and not under(p, exp_s)}
    new = {p: e for p, e in cur.items() if p not in old and not under(p, exp_d)}
    moved, unknown = [], []

    def pair(o, n):
        moved.append((o, n))
        del gone[o]
        del new[n]

    # ① 파일번호 — 같은 디스크 안 이동·이름 바꿈에 그대로(고친 뒤 옮겨도 같다)
    by_ino = defaultdict(list)
    for p, e in new.items():
        if e[2]:
            by_ino[e[2]].append(p)
    for p, e in list(gone.items()):
        c = by_ino.get(e[2]) if e[2] else None
        if c and len(c) == 1:
            pair(p, c[0])
    # ② 해시 — 복사 후 지움 · 다른 드라이브를 거침 · 옮기며 새 파일로 쓰는 프로그램
    g_sha, n_sha = defaultdict(list), defaultdict(list)
    for p, e in gone.items():
        if e[3] and e[0] >= MIN_HASH:
            g_sha[e[3]].append(p)
    for p, e in new.items():
        if e[3] and e[0] >= MIN_HASH:
            n_sha[e[3]].append(p)
    base = lambda x: posixpath.basename(x).lower()  # noqa: E731
    for sha, olds in g_sha.items():
        news = n_sha.get(sha)
        if not news:
            continue
        for o in list(olds):                # 이름까지 같은 짝이 하나씩이면 그것부터
            a = [x for x in olds if base(x) == base(o)]
            b = [x for x in news if base(x) == base(o)]
            if len(a) == 1 and len(b) == 1:
                pair(o, b[0])
                olds.remove(o)
                news.remove(b[0])
        if len(olds) == 1 and len(news) == 1:
            pair(olds[0], news[0])
        elif olds and news:
            for o in olds:
                unknown.append({"path": o, "candidates": list(news)})
                del gone[o]
    return moved, gone, unknown


def collapse(ctx, pairs):
    """파일 짝 → 장부 줄 {(옛, 새): [짝…]}. 폴더째 옮긴 것은 한 줄 — 옛 폴더가 더는 없고 새 폴더 안이 전부 이 묶음일 때만(되돌리기가 다른 것을 끌고 가지 않게)."""
    out = {}
    for o, n in pairs:
        ou, nu = o.split("/"), n.split("/")
        best, k = (o, n), 0
        while k + 1 < min(len(ou), len(nu)) - 1 and ou[-1 - k] == nu[-1 - k]:
            k += 1
            ro, rn = "/".join(ou[:-k]), "/".join(nu[:-k])
            if os.path.exists(ctx.abs(ro)):
                break
            best = (ro, rn)
        out.setdefault(best, []).append((o, n))
    done = {}
    for (ro, rn), group in out.items():
        if (ro, rn) in group or len(fileops.files_under(ctx.abs(rn))) == len(group):
            done[(ro, rn)] = group
        else:
            for o, n in group:
                done[(o, n)] = [(o, n)]
    return done


def collapse_gone(ctx, paths):
    """사라진 파일 → 장부 줄 {뿌리: [파일…]} — 폴더째 지운 것은 한 줄(층 바로 아래까지)."""
    out = {}
    for p in paths:
        parts, root = p.split("/"), p
        for i in range(len(parts) - 1, 1, -1):
            d = "/".join(parts[:i])
            if os.path.exists(ctx.abs(d)):
                break
            root = d
        out.setdefault(root, []).append(p)
    return out


# ── 뒤처리 ───────────────────────────────────────────────────────────────

def index_of(r):
    """ingest.index_path 와 같은 꼴(볼트 상대)."""
    return roles.path("source_index") + r[len(roles.path("sources")):] + ".색인.md"


def is_source(r):
    return under(r, [roles.path("sources")]) and not r.lower().endswith(".md")


def dup_after(ctx, pairs):
    """볼트에 둘 이상 있는 이름(소문자) — 이미 옮겨진 뒤라 옛 이름을 더해 센다. 이름을 바꾼 파일의 옛 이름이 다른 파일에도 있으면
    `[[옛 이름]]` 이 어느 쪽인지 모른다 → 손대지 않는다(fileops.dup_bases 는 옮기기 전에 재므로 그대로 못 쓴다)."""
    c = Counter()
    for b in [posixpath.basename(r) for r in fileops.walk_vault(ctx, skip_rel=(fileops.LEDGER_DIR + "/",))] + [posixpath.basename(o) for o, _ in pairs]:
        c[b.lower()] += 1
        if b.lower().endswith(".md"):
            c[b[:-3].lower()] += 1
    return {b for b, k in c.items() if k > 1}


def partners(ctx, moved):
    """한쪽만 옮긴 짝 → [(옛, 새)] — 원본 → 옆 메모(원본 층) · 시트 ↔ md. brain-source followRename 과 같은 규칙."""
    out = []
    for o, n in moved:
        so, eo = posixpath.splitext(o)
        sn = posixpath.splitext(n)[0]
        if eo.lower() == ".md":
            s, t = so + ".sheet", sn + ".sheet"
            if os.path.isfile(ctx.abs(s)) and not os.path.exists(ctx.abs(t)):
                out.append((s, t))
            continue
        if eo.lower() != ".sheet" and not is_source(o):
            continue
        for old, new in fileops.pair_memos(ctx, o, n):
            # «X.md» 는 옛 자리에 남은 같은 이름의 다른 원본의 짝일 수 있다 — 그러면 건드리지 않는다
            if old == so + ".md" and any(posixpath.splitext(f)[0] == posixpath.basename(so) and not f.lower().endswith(".md")
                                         for f in os.listdir(ctx.abs(posixpath.dirname(o)))):
                continue
            out.append((old, new))
    return list(dict.fromkeys(out))


def fix_data_paths(moved):
    """경로를 글자로 든 수집 기록(LMS 목록·웹 수집 상태) — 링크가 아니라 fileops 가 못 고친다 → 고친 수."""
    mp = {o.lower(): n for o, n in moved if under(o, [roles.path("sources")])}
    if not mp:
        return 0
    total = 0
    for f in [MANIFEST] + sorted(glob.glob(os.path.join(COLLECT, "*.json"))):
        d = load_json(f)
        if d is None:
            continue
        k = 0

        def fix(x):
            nonlocal k
            if isinstance(x, dict):
                for key, v in x.items():
                    if key in ("path", "md") and isinstance(v, str):
                        hit = mp.get(v.replace("\\", "/").lower())
                        if hit:
                            x[key] = hit.replace("/", "\\") if "\\" in v else hit
                            k += 1
                    else:
                        fix(v)
            elif isinstance(x, list):
                for v in x:
                    fix(v)
        fix(d)
        if k:
            save_json(f, d, indent=1)
            total += k
    return total


def apply_moved(ctx, moved, cur, rep, later):
    """옮김 뒤처리 — 색인 거울 · 링크 · 장부 · 수집 기록 · 짝. 파일은 이미 옮겨져 있다."""
    mirrors = []
    for o, n in moved:
        if is_source(o) and is_source(n):
            io_, in_ = index_of(o), index_of(n)
            if os.path.exists(ctx.abs(io_)) or os.path.exists(ctx.abs(in_)):
                mirrors.append((io_, in_))
            later["paths"].append(n)
        elif is_source(o):
            later["prune"] = True           # 원본 층을 떠남 — 색인은 고아
        elif is_source(n):
            later["paths"].append(n)
    if not ctx.dry:
        for io_, in_ in mirrors:            # 노트가 색인을 전체 경로로 잇는다(10-31 사본 시험) — 거울째 옮겨 링크가 따라가게
            a, b = ctx.abs(io_), ctx.abs(in_)
            if os.path.exists(a) and not os.path.exists(b):
                try:
                    os.makedirs(os.path.dirname(b), exist_ok=True)
                    os.replace(a, b)
                except OSError as e:
                    rep["warn"].append("색인을 못 옮김(%s): %s" % (e.strerror or type(e).__name__, io_))
    pairs = moved + mirrors
    moves = fileops.Moves(pairs, dup_after(ctx, pairs))
    rel_fix = fileops.fix_moved_relative(ctx, moved, ctx.dry)
    ch = fileops.rewrite_links(ctx, moves, ctx.dry)
    links = sum(k for _, k in ch) + rel_fix
    rep["moved"] = len(moved)
    rep["links"] = links
    if moves.blocked:
        rep["warn"].append("같은 이름이 볼트에 여럿 — 이름만 쓴 링크는 손대지 않음: %s" % ", ".join(moves.blocked))
    roots = collapse(ctx, moved)
    refs, nref = fileops.code_refs(ctx, [ro for ro, _ in list(roots)[:20]])
    if nref:
        rep["warn"].append("코드·설정에 옛 경로 %d곳(고치지 않음): %s" % (nref, " · ".join(refs)))
    first = True
    for (ro, rn), group in roots.items():
        isdir = (ro, rn) not in group
        rep["lines"].append("옮김 %s → %s%s" % (ro, rn, " (파일 %d)" % len(group) if isdir else ""))
        if ctx.dry:
            continue
        info = {"kind": "dir", "n": len(group), "size": sum(cur[n][0] for _, n in group)} if isdir else {"kind": "file", "size": cur[rn][0], "sha": cur[rn][3] or None}
        kind = "rename" if posixpath.dirname(ro) == posixpath.dirname(rn) else "mv"
        ctx.add(kind, src=ro, dst=rn, why=WHY, outside=True, via="follow", links=links if first else None,
                linkfiles=[f for f, _ in ch][:20] if first else None, **info)
        first = False
    if ctx.dry:
        return
    rep["data"] = fix_data_paths(moved)
    sub = fileops.Ctx(VAULT, by="script:follow")
    sub.batch = ctx.batch                   # 같은 묶음 — 되돌리면 짝도 함께
    for old, new in partners(ctx, moved):
        try:
            fileops.op_mv(sub, old, new, "짝 따라감(바깥 이동)")
            rep["lines"].append("짝 %s → %s" % (old, new))
        except fileops.Stop as e:
            rep["warn"].append("짝을 못 옮김: %s" % e)
    ctx.events += sub.events


def lms_keys(man, path, sha):
    """사라진 파일의 LMS 목록 항목 — [칸, 키](게시판은 [«board», 강좌, 글 키])."""
    low = path.lower()
    norm = lambda v: (v or "").replace("\\", "/").lower()  # noqa: E731
    out = [["files", k] for k, v in man.get("files", {}).items() if norm(v.get("path")) == low or (sha and v.get("sha") == sha)]
    out += [["items", k] for k, v in man.get("items", {}).items() if norm(v.get("path")) == low]
    for c, b in man.get("board", {}).items():
        out += [["board", c, k] for k, v in b.items() if norm(v.get("md")) == low]
    return out


def apply_gone(ctx, gone, unknown, cur, rep, later, pending):
    """지움 뒤처리 — 장부 · LMS 원본은 다시 받을지 묻기 · 색인 고아 정리(나중에). 파일을 만지지 않는다."""
    man = load_json(MANIFEST) or {}
    alive = {e[3]: p for p, e in cur.items() if e[3]}
    now = fileops.now().isoformat(timespec="seconds")
    for x in unknown:
        rep["lines"].append("행방 모름 %s — 후보 %s" % (x["path"], " · ".join(x["candidates"])))
        if ctx.dry:
            continue
        ctx.add("rm", src=x["path"], why="행방 모름(따라가기) — 후보 " + " · ".join(x["candidates"][:3]), trash="gone", outside=True, kind="file")
        pending.append({"kind": "모호", "path": x["path"], "candidates": x["candidates"], "ts": now})
    rep["unknown"] = len(unknown)
    rep["gone"] = len(gone)
    for root, group in collapse_gone(ctx, sorted(gone)).items():
        one = group == [root]
        elsewhere = alive.get(gone[root][3]) if one and gone[root][3] else None
        rep["lines"].append("지움 %s%s%s" % (root, "" if one else " (파일 %d)" % len(group), " — 같은 내용이 %s 에 있음" % elsewhere if elsewhere else ""))
        if ctx.dry:
            continue
        info = {"kind": "file", "size": gone[root][0], "sha": gone[root][3] or None} if one else {"kind": "dir", "n": len(group), "size": sum(gone[p][0] for p in group)}
        ctx.add("rm", src=root, why=WHY + (" · 같은 내용이 %s 에 있음" % elsewhere if elsewhere else ""), trash="gone", outside=True,
                user_asked=True if under(root, [roles.path("sources")]) else None, **info)
    for p in sorted(gone):
        if is_source(p):
            later["prune"] = True
        if ctx.dry or not under(p, [roles.path("sources")]) or (gone[p][3] and gone[p][3] in alive):
            continue
        keys = lms_keys(man, p, gone[p][3])
        if keys:                            # 목록엔 «이미 받음»이라 다시 안 받는다 — 의도한 삭제면 그대로 · 실수면 되받음
            pending.append({"kind": "lms", "path": p, "keys": keys, "ts": now})
            rep["lines"].append("LMS 원본 사라짐 %s — 되받을지 답 기다림" % p)


def ingest_later(later):
    """색인 다시 잇기·고아 정리 — 뒤에서(세션 시작을 붙들지 않게 · 큰 PDF 추출은 수십 초). 그림 읽기는 하지 않는다."""
    if os.environ.get("FOLLOW_NO_INGEST") == "1" or not os.path.isfile(os.path.join(HERE, "ingest.py")):
        return
    argv = [sys.executable, os.path.join(HERE, "ingest.py")]
    if later["prune"] or len(later["paths"]) > 30:   # --prune 은 전체를 돌 때만 듣는다
        argv += ["--prune"] if later["prune"] else []
    elif later["paths"]:
        argv += [os.path.join(VAULT, *p.split("/")) for p in later["paths"]]
    else:
        return
    try:
        subprocess.Popen(argv, cwd=VAULT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    except OSError:
        pass


# ── 답 기다리는 것 ───────────────────────────────────────────────────────

def load_pending():
    p = load_json(PENDING) or {}
    p.setdefault("items", [])
    p.setdefault("held", 0)
    return p


def status():
    """건강·홈이 읽는다(읽기만)."""
    p = load_pending()
    return {"ready": os.path.exists(SNAP), "last": p.get("last"), "held": p["held"], "items": p["items"]}


def pick(items, paths, everything, kinds=None):
    ctx = fileops.Ctx(VAULT)
    want = {fileops.to_rel(ctx, s)[0].lower() for s in paths}
    return [x for x in items if (everything or x["path"].lower() in want) and (not kinds or x["kind"] in kinds)]


def cmd_refetch(paths, everything):
    p = load_pending()
    todo = pick(p["items"], paths, everything, ("lms",))
    if not todo:
        print("다시 받을 것 없음")
        return 1
    man = load_json(MANIFEST) or {}
    for x in todo:
        for k in x["keys"]:
            if k[0] == "board":
                man.get("board", {}).get(k[1], {}).pop(k[2], None)
                continue
            man.get(k[0], {}).pop(k[1], None)
            if k[0] == "files" and k[1].startswith("board:"):   # 게시판 첨부 = 글을 다시 열어야 받는다(확장은 known 의 글을 건너뜀)
                _, cid, post = k[1].split(":", 3)[:3]
                b = man.get("board", {}).get(cid, {})
                for key in [key for key, v in b.items() if v.get("path") == post]:
                    del b[key]
    save_json(MANIFEST, man, indent=1)
    auto = os.path.join(HERE, "lms-auto.py")
    if os.path.isfile(auto):                # 확장이 읽는 «이미 받은 것» — 목록에서 다시 만든다
        subprocess.run([sys.executable, auto, "--known"], cwd=VAULT, capture_output=True, timeout=60)
    p["items"] = [x for x in p["items"] if x not in todo]
    save_json(PENDING, p, indent=1)
    print("다음 LMS 수집 때 다시 받음 %d: %s" % (len(todo), " · ".join(x["path"] for x in todo)))
    return 0


def cmd_keep(paths, everything):
    p = load_pending()
    todo = pick(p["items"], paths, everything)
    p["items"] = [x for x in p["items"] if x not in todo]
    save_json(PENDING, p, indent=1)
    print("그대로 둠 %d" % len(todo))
    return 0 if todo else 1


# ── 비교 ─────────────────────────────────────────────────────────────────

def follow(dry=False, accept=False, budget=None):
    """비교 → 적용 → 사진 갱신. 결과 dict — 같은 일을 또 하지 않게 사진은 끝에 쓴다(도중에 멈추면 다음에 처음부터 · 링크 고치기는 두 번 해도 같다)."""
    ctx = fileops.Ctx(VAULT, by="user", dry=dry)
    rep = {"first": False, "moved": 0, "gone": 0, "links": 0, "data": 0, "unknown": 0, "held": 0, "pending": 0, "lines": [], "warn": []}
    snap = load_json(SNAP)
    pend = load_pending()
    pend["items"] = [x for x in pend["items"] if not os.path.exists(ctx.abs(x["path"]))]    # 도로 나타난 것
    if not snap or snap.get("schema") != SCHEMA:
        pos = ledger_end(ctx)
        files, _ = scan({}, budget)
        rep["first"] = True
        rep["lines"].append("사진 처음 만듦 — 파일 %d" % len(files))
        if not dry:
            save_json(SNAP, {"schema": SCHEMA, "ts": fileops.now().isoformat(timespec="seconds"), "pos": pos, "files": files})
            pend.update(last=fileops.now().isoformat(timespec="seconds"), held=0)
            save_json(PENDING, pend, indent=1)
        return rep
    old = snap["files"]
    events, pos = ledger_since(ctx, snap.get("pos", 0), snap.get("ts", ""))
    replay(old, events)
    cur, blind = scan(old, budget)
    replay(old, ledger_since(ctx, pos, snap.get("ts", ""))[0])      # 훑는 사이에 끝난 일
    expected = [(x[0], x[1]) for x in fileops.expect_read(ctx)]     # fileops 가 옮기는 중(장부 줄은 링크를 고친 뒤에 적힌다)
    moved, gone, unknown = judge(old, cur, blind, expected)
    gone = {p: e for p, e in gone.items() if not os.path.exists(os.path.join(ARCH, *p.split("/")))}     # 웹 수집이 보관 칸으로 옮긴 것
    held = {}
    if len(gone) > mass(len(old)) and not accept:
        held, gone = gone, {}
        rep["held"] = len(held)
        rep["warn"].append("한꺼번에 %d개가 사라짐 — 지움으로 치지 않음(폴더 잠김·복원일 수 있다) · 맞으면 `follow.py --accept`" % len(held))
    later = {"paths": [], "prune": False}
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):       # fileops 의 출력이 세션 시작 입력·JSON 에 섞이지 않게
        if moved:
            apply_moved(ctx, moved, cur, rep, later)
        if gone or unknown:
            apply_gone(ctx, gone, unknown, cur, rep, later, pend["items"])
    rep["lines"] += [x for x in buf.getvalue().splitlines() if x.strip()]
    rep["pending"] = len(pend["items"])
    if dry:
        return rep
    if ctx.events:
        fileops.write_view(ctx)
    end = ledger_end(ctx)
    final, blind2 = scan(cur, budget)
    for p, e in old.items():                    # 못 읽은 폴더·묻는 중인 것은 있던 그대로
        if p not in final and (under(p, blind + blind2) or p in held):
            final[p] = e
    save_json(SNAP, {"schema": SCHEMA, "ts": fileops.now().isoformat(timespec="seconds"), "pos": end, "files": final})
    pend.update(last=fileops.now().isoformat(timespec="seconds"), held=len(held))
    save_json(PENDING, pend, indent=1)
    ingest_later(later)
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(prog="follow", description="옵시디언 밖에서 옮기거나 지운 파일 따라가기")
    ap.add_argument("cmd", nargs="?", choices=["pending", "refetch", "keep"])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--all", action="store_true", help="refetch·keep — 목록 전부")
    ap.add_argument("--dry", action="store_true", help="미리 보기 — 아무것도 바꾸지 않는다")
    ap.add_argument("--accept", action="store_true", help="한꺼번에 사라진 것도 지움으로")
    ap.add_argument("--hook", action="store_true", help="세션 시작 — 알릴 것이 있을 때만 한 줄")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "pending":
        s = status()
        if a.json:
            print(json.dumps(s, ensure_ascii=False))
        else:
            for x in s["items"]:
                print("%s · %s%s" % (x["kind"], x["path"], " — 후보 " + " · ".join(x["candidates"]) if x.get("candidates") else ""))
            if s["held"]:
                print("한꺼번에 사라짐 %d — `follow.py --accept`" % s["held"])
            if not s["items"] and not s["held"]:
                print("답 기다리는 것 없음")
        return 0
    if a.cmd == "refetch":
        return cmd_refetch(a.paths, a.all)
    if a.cmd == "keep":
        return cmd_keep(a.paths, a.all)
    with locked() as got:
        if not got:
            if a.json:
                print(json.dumps({"busy": True}))
            elif not a.hook:
                print("다른 쪽이 비교하는 중")
            return 0
        try:
            rep = follow(dry=a.dry, accept=a.accept, budget=HOOK_BUDGET if a.hook else None)
        except Exception as e:  # noqa: BLE001 — 세션 시작·옵시디언을 멈추지 않는다 · 사진을 안 썼으니 다음에 다시
            if a.json:
                print(json.dumps({"error": "%s: %s" % (type(e).__name__, e)}, ensure_ascii=False))
            else:
                print("[따라가기] 실패(%s: %s) — 다음 비교 때 다시" % (type(e).__name__, str(e)[:120]))
            return 0 if a.hook else 1
    if a.json:
        print(json.dumps(rep, ensure_ascii=False))
        return 0
    if a.hook:
        if rep["first"]:
            return 0
        bits = []
        if rep["moved"] or rep["gone"] or rep["unknown"]:
            bits.append("바깥에서 옮김 %d · 지움 %d%s%s" % (rep["moved"], rep["gone"], " · 행방 모름 %d" % rep["unknown"] if rep["unknown"] else "",
                                                     " · 링크 %d곳 고침" % rep["links"] if rep["links"] else ""))
        if rep["held"]:
            bits.append("⚠ 한꺼번에 사라짐 %d(지움으로 안 침 · 확인 뒤 `follow.py --accept`)" % rep["held"])
        if rep["pending"]:
            bits.append("답 기다림 %d(`follow.py pending`)" % rep["pending"])
        rest = [w for w in rep["warn"] if not w.startswith("한꺼번에")]
        if rest:
            bits.append("⚠ %s%s" % (rest[0][:120], " 외 %d" % (len(rest) - 1) if len(rest) > 1 else ""))
        if bits:
            print("[따라가기] " + " · ".join(bits))
        return 0
    for x in rep["lines"] + ["⚠ " + w for w in rep["warn"]]:
        print(x)
    if rep["first"]:
        return 0
    if rep["moved"] or rep["gone"] or rep["unknown"]:
        print("== %s옮김 %d · 지움 %d · 링크 %d곳 · 수집 기록 %d곳" % ("미리 보기 · " if a.dry else "", rep["moved"], rep["gone"], rep["links"], rep["data"]))
    elif not rep["warn"]:
        print("바뀐 것 없음")
    if rep["pending"]:
        print("답 기다림 %d — follow.py pending" % rep["pending"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
