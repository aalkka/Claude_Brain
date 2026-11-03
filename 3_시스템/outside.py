# -*- coding: utf-8 -*-
"""**볼트 밖 후보** — 내려받기·바탕화면의 문서 중 볼트에 없는 것을 목록으로 보여 준다(설계안 §13.3 B2② · §11 11 · 사용자 10-31 허용).

왜: 사람이 받은 문서는 볼트 밖에서 멈춘다(10-29 실측 볼트 밖에만 있는 문서 26). 볼트 밖은 사용자 것이라 저절로 옮기지 않는다 — 목록만 보이고 «받은함으로»를 눌렀을 때만 들인다.
11-03(«복사라 받은 파일을 또 지워야 한다»): 들이기 = 옮기기.
이름·크기·해시만 보고 내용은 해석하지 않는다. 볼트 밖 경로는 어디에도 적지 않는다(해시 캐시의 열쇠도 경로의 해시 · 장부에는 «내려받기/이름»).

  py -3 3_시스템/outside.py [--json] [--days 60]    후보 목록(최근 60일 · 바로 아래 · 문서만)
  py -3 3_시스템/outside.py take <열쇠|이름>         받은함으로 옮김(같은 내용이 볼트에 있으면 거절)
  py -3 3_시스템/outside.py hide <열쇠|이름>         목록에서 뺌(내용 해시로 기억 · 파일은 그대로)
"""
import argparse
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fileops  # noqa: E402
import follow  # noqa: E402
import roles  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
OUT = os.path.join(HERE, "_index", "outside")
CACHE = os.path.join(OUT, "cache.json")
HIDDEN = os.path.join(OUT, "hidden.json")
DOCS = {".pdf", ".docx", ".doc", ".hwp", ".hwpx", ".pptx", ".ppt", ".xlsx", ".xls"}
BIG = 300 * 1024 * 1024         # 이보다 큰 문서는 해시를 재지 않는다(홈을 붙들지 않게) — 이름·크기로만 보인다
HOME = os.path.expanduser("~")
PLACES = [("내려받기", os.path.join(HOME, "Downloads")), ("바탕화면", os.path.join(HOME, "Desktop"))]


def places():
    """시험은 OUTSIDE_DIRS(이름=경로;이름=경로)로 바꾼다."""
    env = os.environ.get("OUTSIDE_DIRS")
    if env:
        return [tuple(x.split("=", 1)) for x in env.split(";") if "=" in x]
    return PLACES


def vault_hashes():
    """볼트 내용 칸의 해시 집합 — 따라가기 사진을 지금 모습으로(바뀐 파일만 해시). 사진이 없으면 None(13초 걸리는 첫 사진을 여기서 찍지 않는다)."""
    snap = follow.load_json(follow.SNAP)
    if not snap or not snap.get("files"):
        return None
    files, _ = follow.scan(snap["files"])
    return {e[3] for e in files.values() if e[3]}


def candidates(days=60):
    """→ [{key, name, place, size, days, a}] 새것 먼저 · a(절대 경로)는 메모리 안에서만. 볼트 사진이 없으면 []."""
    have = vault_hashes()
    if have is None:
        return []
    hidden = set(follow.load_json(HIDDEN) or [])
    old = follow.load_json(CACHE) or {}
    cache, out = {}, []
    now = time.time()
    for label, d in places():
        try:
            entries = list(os.scandir(d))
        except OSError:
            continue
        for e in entries:
            try:
                if not e.is_file(follow_symlinks=False) or os.path.splitext(e.name)[1].lower() not in DOCS or e.name.startswith(("~", ".")):
                    continue
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            age = (now - st.st_mtime) / 86400
            if age > days:
                continue
            k = hashlib.sha1(os.path.normcase(e.path).encode("utf-8")).hexdigest()[:16]
            c = old.get(k)
            sha = c[2] if c and c[0] == st.st_size and c[1] == st.st_mtime_ns else ""
            if not sha and st.st_size <= BIG:
                try:
                    sha = fileops.sha256(e.path)
                except OSError:         # 받는 중·잠김 — 다음에
                    continue
            cache[k] = [st.st_size, st.st_mtime_ns, sha]
            if sha in have or sha in hidden:
                continue
            out.append({"key": k, "name": e.name, "place": label, "size": st.st_size, "days": int(age), "sha": sha, "a": e.path})
    if cache != old:
        follow.save_json(CACHE, cache)
    return sorted(out, key=lambda x: x["days"])


def pick(rows, key):
    hit = [x for x in rows if x["key"] == key or x["name"] == key]
    if len(hit) != 1:
        print("후보에 없음(또는 같은 이름이 둘): %s" % key)
        return None
    return hit[0]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="outside", description="내려받기·바탕화면의 볼트에 없는 문서")
    ap.add_argument("cmd", nargs="?", choices=["take", "hide"])
    ap.add_argument("key", nargs="?")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--by", default=None, help="장부의 «누가»")
    a = ap.parse_args(argv)
    rows = candidates(a.days)
    if a.cmd:
        x = pick(rows, a.key or "")
        if not x:
            return 1
        if a.cmd == "hide":
            hidden = follow.load_json(HIDDEN) or []
            if x["sha"]:
                follow.save_json(HIDDEN, hidden + [x["sha"]])
            print("목록에서 뺌: %s" % x["name"])
            return 0
        ctx = fileops.Ctx(VAULT, by=a.by)
        try:
            fileops.op_cp(ctx, x["a"], roles.path("inbox") + "/" + x["name"], "볼트 밖 후보를 받은함으로(사람이 고름)", src_label="%s/%s" % (x["place"], x["name"]), move=True)
        except fileops.Stop as e:
            print("✗ %s" % e)
            return 1
        fileops.write_view(ctx)
        return 0
    if a.json:
        print(json.dumps([{k: x[k] for k in ("key", "name", "place", "size", "days")} for x in rows], ensure_ascii=False))
        return 0
    for x in rows:
        print("%s · %s · %.1fMB · %d일 · %s" % (x["name"], x["place"], x["size"] / 1e6, x["days"], x["key"]))
    print("볼트 밖 후보 %d" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
