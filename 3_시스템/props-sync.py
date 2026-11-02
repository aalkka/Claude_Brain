# -*- coding: utf-8 -*-
"""속성 자동 칸 — 고친 노트의 `updated` 를 파일 수정 날짜로 적는다(사용자 10-30 «updated 는 파일 수정 시간을 그대로»).

손으로 적는 updated 는 믿을 수 없다 → 사람도 Claude 도 손대지 않고, 커밋 직전(pre-commit)에 이 대본이 맞춘다.
  · 대상 = 2_지식/·0_작업/ 의 md 중 프론트매터가 있는 것(1_수집 = 원본 불변 · 3_시스템·생성 파일 제외)
  · `updated:` 줄의 값만 바꾼다(없으면 `created:` 바로 아래에 넣음 · created 도 없으면 = 상시 갱신 핵심 파일 → 건너뜀)
  · 쓴 뒤 수정 시각을 되돌린다(수정 시각이 진실 · 다시 돌려도 같음)
  · 방금(2분 안) 고친 파일은 건너뛴다 — 옵시디언에서 지금 쓰는 중일 수 있다 → 다음 커밋에

새 노트의 속성 표(ADR-027) — 옵시디언 새 노트 표는 빈 노트만 채워서 Claude·대본이 만든 노트는 옛 꼴로 남았다(10-30 뒤 21개 중 0개).
  · 대상 = 이번 커밋에 새로 든 md + 고친 노트 중 created 가 SINCE 뒤인 것(그 전 노트는 고치지 않는다 — ADR-020) · 표 = roles.json `props`
  · 빠진 키를 넣고 표 키를 표 순서로 앞에 놓는다 · 있는 값은 덮지 않는다(옛 source 값만 새 값으로) · 값을 모르면 키만 · 수정 시각을 되돌린다
  · 손대지 않는 것: 속성 없는 md(코어 초안·프롬프트·대본 입력은 바이트가 그대로여야 한다) · 표 키가 하나도 없는 머리(SKILL·marp) · YAML 꼴이 아닌 머리(맨 위 가로줄)

  py -3 3_시스템/props-sync.py --staged      # pre-commit 이 부름 — 고친 파일은 다시 git add
  py -3 3_시스템/props-sync.py <파일…> [--dry]
  py -3 3_시스템/props-sync.py --fill <파일…> [--dry]   # 속성 표만 손으로(이미 커밋한 새 노트)
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
try:
    import roles  # noqa: E402
except Exception:  # noqa: BLE001 — 표를 못 읽어도 updated 는 돈다
    roles = None

ROOTS = ("2_지식/", "0_작업/")
SKIP = {"2_지식/장부.md"}  # fileops 가 만드는 보기(고치지 않는다)
FRESH = 120  # 초
SINCE = "2026-10-30"  # ADR-020 — 이 날부터 만든 노트는 고칠 때도 표를 지킨다
NO_TABLE = ("moc", "recent", "open_loops", "profile", "ledger_view", "topics", "retention")  # 상시 갱신·대본 파일(규약의 created 면제와 같음)
OLD_SOURCE = {"session": "claude", "pdf": "수집", "lms": "수집", "web": "수집"}  # ADR-020 옛 값 — 표를 채우는 노트에만 고친다


def target(rel):
    rel = rel.replace("\\", "/")
    return rel.endswith(".md") and rel.startswith(ROOTS) and rel not in SKIP


def scalar(s):
    """YAML 값 — 글자·숫자와 흔한 기호뿐이면 그대로, 아니면 큰따옴표(제목 안 «: » 가 속성을 깬다 · incident-2026-07-27)."""
    return s if re.fullmatch(r"\w[\w .·()_-]*", s) else json.dumps(s, ensure_ascii=False)


def table_of(rel):
    """이 노트 자리의 표(키 순서) · 표가 없는 자리면 None — brain-base props.ts 의 건너뛰기와 같다(`_`·점 폴더)."""
    rel = rel.replace("\\", "/")
    if any(s.startswith((".", "_")) or s == "node_modules" for s in rel.split("/")[:-1]):
        return None
    if rel in (roles.path(r) for r in NO_TABLE) or rel.startswith(roles.path("schedule") + "/"):
        return None
    if os.path.basename(rel) in ("설계노트.md", "사용자설명서.md"):
        return None
    return roles.props_table(rel)


def fill(path, rel, dry=False):
    """표대로 고쳤으면 넣은 키 목록(순서·옛 값만 고쳤으면 빈 목록) · 그대로면 None."""
    table = table_of(rel)
    if not table:
        return None
    st = os.stat(path)
    with open(path, "rb") as f:
        raw = f.read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig" if bom else "utf-8")
    except UnicodeDecodeError:
        return None
    nl = "\r\n" if "\r\n" in text[:400] else "\n"
    m = re.match(r"---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(\r?\n|$)", text, re.S)
    if not m:
        return None
    lines = re.split(r"\r?\n", m.group(1))
    blocks = []  # (키, 줄들) — 들여 쓴 줄·«- » 줄·주석·빈 줄은 앞 키에 붙는다
    for ln in lines:
        k = re.match(r"([^\s#-][^:]*):(?:[ \t]|$)", ln)
        if k:
            blocks.append((k.group(1).strip(), [ln]))
        elif ln.strip() and ln[0] not in " \t#-":
            return None  # 키도 이어지는 줄도 아니다 — 머리가 아니라 맨 위 가로줄 사이의 글
        elif blocks:
            blocks[-1][1].append(ln)
        else:
            blocks.append((None, [ln]))
    have = {}
    for b in blocks:
        have.setdefault(b[0], b)
    if not any(k in have for k in table):
        return None
    mt = dt.date.fromtimestamp(st.st_mtime).isoformat()
    topic = roles.topic_of(rel, read_md=False)
    topic = scalar(topic) if topic else ""
    val = {"title": scalar(os.path.splitext(os.path.basename(rel))[0]),
           "created": dt.date.fromtimestamp(min(st.st_ctime, st.st_mtime)).isoformat(), "updated": mt,
           "tags": "[]", "aliases": "[]", "links": "[]", "status": "active", "주제": topic}
    added = [k for k in table if k not in have]
    head = [have.get(k) or (k, [f"{k}: {val.get(k, '')}".rstrip()]) for k in table]
    rest = [b for b in blocks if not any(b is h for h in head)]
    new = [ln for _, ls in head + rest for ln in ls]
    for i, ln in enumerate(new):
        s = re.fullmatch(r"source:[ \t]*(\S+)[ \t]*", ln)
        if s and s.group(1) in OLD_SOURCE:
            new[i] = f"source: {OLD_SOURCE[s.group(1)]}"
    if new == lines:
        return None
    if dry:
        return added
    out = "---" + nl + nl.join(new) + nl + "---" + nl + text[m.end():]
    tmp = path + ".~props"  # 임시 파일 뒤 바꿔치기 — 쓰다 멈춰도 본문이 비지 않는다
    try:
        with open(tmp, "wb") as f:
            f.write((b"\xef\xbb\xbf" if bom else b"") + out.encode("utf-8"))
        os.utime(tmp, (st.st_atime, st.st_mtime))
        if os.stat(path).st_mtime != st.st_mtime:
            return None  # 읽는 사이 누가 고쳤다 — 다음 커밋에
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return added


def sync(path, dry=False, now=None):
    """바꿨으면 새 날짜 · 그대로면 None"""
    st = os.stat(path)
    if (now or time.time()) - st.st_mtime < FRESH:
        return None
    with open(path, "rb") as f:
        raw = f.read()
    try:
        text = raw.decode("utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8")
    except UnicodeDecodeError:
        return None
    nl = "\r\n" if "\r\n" in text[:400] else "\n"
    m = re.match(r"---\r?\n(.*?)\r?\n---(\r?\n|$)", text, re.S)
    if not m:
        return None
    fm = m.group(1)
    day = dt.date.fromtimestamp(st.st_mtime).isoformat()
    u = re.search(r"^updated:[ \t]*([^\r\n]*)", fm, re.M)  # 줄 끝 \r 은 남긴다(CRLF 파일)
    if u:
        if u.group(1).strip().strip("'\"") == day:
            return None
        fm2 = fm[: u.start()] + f"updated: {day}" + fm[u.end():]
    else:
        c = re.search(r"^created:[^\r\n]*", fm, re.M)
        if not c:
            return None
        fm2 = fm[: c.end()] + f"{nl}updated: {day}" + fm[c.end():]
    if dry:
        return day
    new = text[: m.start(1)] + fm2 + text[m.end(1):]
    with open(path, "wb") as f:
        f.write((b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + new.encode("utf-8"))
    os.utime(path, (st.st_atime, st.st_mtime))
    return day


def staged(flt="ACM"):
    r = subprocess.run(["git", "-c", "core.quotepath=false", "diff", "--cached", "--name-only", "--diff-filter=" + flt, "-z"], cwd=VAULT, capture_output=True)
    return [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p]


def made_since(rel):
    """속성 created 가 SINCE 부터인가."""
    try:
        with open(os.path.join(VAULT, rel), encoding="utf-8-sig", errors="replace") as f:
            c = re.search(r"^created:[ \t]*['\"]?(\d{4}-\d{2}-\d{2})", f.read(4000), re.M)
    except OSError:
        return False
    return bool(c and c.group(1) >= SINCE)


def fill_all(rels, dry):
    """표를 채운 노트들 — 한 파일이 깨져도 나머지·updated 는 돈다(커밋을 막지 않는다)."""
    done = []
    if roles is None:
        return done
    for rel in rels:
        rel = rel.replace("\\", "/")
        p = os.path.join(VAULT, rel)
        if not (target(rel) and os.path.isfile(p)):
            continue
        try:
            got = fill(p, rel, dry)
        except Exception as e:  # noqa: BLE001
            print(f"표 못 채움({type(e).__name__}) — {rel}")
            continue
        if got is not None:
            done.append(rel)
            print(f"표 +{len(got)} {','.join(got)} — {rel}")
    return done


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="props-sync")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--fill", action="store_true", help="속성 표만(옛 노트를 고르는 것은 사람)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)
    rels = staged() if a.staged else [os.path.relpath(os.path.abspath(p), VAULT) for p in a.files]
    if a.fill:
        fill_all(rels, a.dry)
        return 0
    filled = fill_all(staged("A") + [r for r in staged("M") if target(r) and made_since(r)], a.dry) if a.staged else []
    done = list(filled)
    for rel in rels:
        if not target(rel):
            continue
        p = os.path.join(VAULT, rel)
        if os.path.isfile(p) and (day := sync(p, a.dry)):
            done.append(rel)
            print(f"updated {day} — {rel}")
    if a.staged and done and not a.dry:
        restage(sorted(set(done)))
    return 0


def restage(rels):
    """내용으로 다시 담는다 — `git add` 는 크기·수정 시각이 그대로면(시각을 되돌렸고 날짜 길이도 같다) 안 바뀐 줄 알고 건너뛴다(10-30 격리 시험)"""
    for rel in rels:
        ls = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "-s", "--", rel], cwd=VAULT, capture_output=True).stdout.decode("utf-8", "replace").split()
        sha = subprocess.run(["git", "hash-object", "-w", "--path", rel, "--", rel], cwd=VAULT, capture_output=True).stdout.decode().strip()
        if ls and sha:
            subprocess.run(["git", "update-index", "--cacheinfo", f"{ls[0]},{sha},{rel}"], cwd=VAULT)


if __name__ == "__main__":
    sys.exit(main())
