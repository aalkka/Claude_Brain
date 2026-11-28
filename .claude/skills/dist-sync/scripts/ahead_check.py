"""볼트 앞섬 검사(첫 판 · 11-28) — 볼트가 배포판보다 앞선 것을 찾아, 저마다 «실음/넘김 + 까닭» 판정이 적혀 있는지 본다.

왜: 11-28 열째 판을 낸 뒤 보니 볼트 설치본 플러그인(brain-base·brain-source)·fileops.py 등 앞선 것이 후보에 빠져 있었다.
배포 직전에 «무엇이 앞섰고 그것을 실을지 넘길지» 를 사람이 정한 기록이 없으면 막는다.

  py -3 .claude/skills/dist-sync/scripts/ahead_check.py --dist <배포판 worktree> [--old <공개판 rev · 기본 dist/main>] [--json]

① 플러그인: 볼트 `.obsidian/plugins/<id>/manifest.json` 판 > 공개판의 그 판 → «앞섬»(공개판에 없는 플러그인은 안 봄 · 싣는지는 ship.json 몫)
② 파일: 공개판이 싣는 파일 가운데 볼트 판이 다른 것을 `pub_merge.py` 마른 돌림으로 가름 — «손 고침만»·«바뀐 것 없음» 은 앞섬 아님 ·
   «그대로»·«합침»·«읽을 것»·«기준 없음» = 앞섬. 개인 층(0_·1_·2_ 폴더 · .obsidian 맨 위 설정)은 배포판 견본과 다른 것이 맞아 뺀다.
③ 판정 표 `3_시스템/_index/dist/ahead.json` {"<열쇠>": {"판정": "실음"|"넘김", "까닭": "…"}} — 열쇠 = `plugin:<id>@<볼트 판>` 또는 파일 경로.
   앞섬마다 판정이 있으면 종료 0 · 없는 것이 하나라도 있으면 종료 1(그 목록을 냄) · 판정이 «실음»·«넘김» 밖이면 없는 것으로 본다.
아직 안 하는 것: 설치본 커밋이 소스 줄기에 있는지(다음 판) · ship.json 에 새로 넣은(공개판에 아직 없는) 파일 · dist-check 에 잇기.
읽기만 한다(배포판·볼트에 안 씀).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
TABLE = os.path.join(V, "3_시스템", "_index", "dist", "ahead.json")
PLUG = ".obsidian/" + "plug" + "ins/"
PERSONAL = ("0_", "1_", "2_")
SEM = re.compile(r"\n*>[ \t]*\[!info\]-[ \t]*관련 노트[ \t]*%%sl%%(?:\n>[^\n]*)*".encode("utf-8"))
AHEAD = ("그대로(손 고침 없음)", "합침", "읽을 것", "기준 없음(배포판 판 둠)", "새 파일")


def git(repo, *a):
    r = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", *a], capture_output=True)
    return r.returncode, r.stdout


def ver(s):
    return tuple(int(x) if x.isdigit() else 0 for x in re.split(r"[.\-+]", str(s or "0")))


def personal(rel):
    if rel.startswith(PERSONAL):
        return True
    return rel.startswith(".obsidian/") and not rel.startswith(PLUG) and rel.count("/") == 1


def plugins(dist, old):
    out = []
    d = os.path.join(V, *PLUG.strip("/").split("/"))
    for pid in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        mf = os.path.join(d, pid, "manifest.json")
        if not os.path.isfile(mf):
            continue
        c, o = git(dist, "show", "%s:%s%s/manifest.json" % (old, PLUG, pid))
        if c:
            continue
        try:
            mine, pub = json.load(open(mf, encoding="utf-8")).get("version"), json.loads(o.decode("utf-8")).get("version")
        except Exception:
            continue
        if ver(mine) > ver(pub):
            out.append(("plugin:%s@%s" % (pid, mine), "플러그인 %s %s > 공개판 %s" % (pid, mine, pub)))
            t = trunk(pid, mine)
            if t:
                out.append(("trunk:%s@%s" % (pid, mine), t))
    return out


def trunk(pid, version):
    """④ 앞선 플러그인 판을 낸 소스 커밋(manifest 가 처음 그 판이 된 커밋)이 소스 줄기에 있나 — 있으면 None · 없거나 모르면 까닭(막음).
    소스 자리 = 개인화 파트 personal/sources.json {"<id>": {"repo", "manifest", "trunk"}}."""
    try:
        src = json.load(open(os.path.join(os.path.dirname(HERE), "personal", "sources.json"), encoding="utf-8")).get(pid)
    except (OSError, ValueError):
        src = None
    if not isinstance(src, dict) or not os.path.isdir(os.path.join(src.get("repo", ""), ".git")):
        return "줄기 모름 — %s 의 소스 저장소가 personal/sources.json 에 없음" % pid
    repo, mf, tr = src["repo"], src.get("manifest", "manifest.json"), src.get("trunk", "main")
    _, hs = git(repo, "log", "--all", "--format=%H", "--reverse", "-S", '"version": "%s"' % version, "--", mf)
    first = None
    for h in hs.decode().split():
        c, o = git(repo, "show", "%s:%s" % (h, mf))
        try:
            if not c and json.loads(o.decode("utf-8")).get("version") == version:
                first = h
                break
        except ValueError:
            continue
    if not first:
        return "줄기 모름 — %s 의 manifest 가 %s 인 커밋을 소스(%s)에서 못 찾음" % (pid, version, repo)
    c, _ = git(repo, "merge-base", "--is-ancestor", first, tr)
    return None if c == 0 else "가지에만 있음 — %s %s 를 낸 커밋 %s 가 줄기 %s 에 없음(%s)" % (pid, version, first[:7], tr, repo)


def files(dist, old):
    _, t = git(dist, "ls-tree", "-r", "--name-only", old)
    diff = []
    for rel in [x for x in t.decode("utf-8").split("\n") if x]:
        if personal(rel):
            continue
        vp = os.path.join(V, *rel.split("/"))
        if not os.path.isfile(vp):
            continue
        a = open(vp, "rb").read().replace(b"\r\n", b"\n")
        _, b = git(dist, "show", "%s:%s" % (old, rel))
        b = b.replace(b"\r\n", b"\n")
        if rel.endswith(".md"):
            a, b = SEM.sub(b"", a), SEM.sub(b"", b)
        if a != b:
            diff.append(rel)
    if not diff:
        return []
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
        f.write("\n".join(diff) + "\n")
        lst = f.name
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "pub_merge.py"), lst, "--dist", dist, "--old", old],
                           capture_output=True, encoding="utf-8", errors="replace")
    finally:
        os.unlink(lst)
    cat, got, out = None, set(), []
    for ln in r.stdout.split("\n"):
        m = re.match(r"== (.+) \d+$", ln)
        if m:
            cat = m.group(1)
            continue
        m = re.match(r"    (\S+)", ln)
        if m and cat:
            got.add(m.group(1))
            if cat in AHEAD:
                out.append((m.group(1), "파일 · %s%s" % (cat, ln[4 + len(m.group(1)):])))
    for rel in diff:                        # pub_merge 가 이름을 안 찍는 칸(«그대로»·«새 파일») — 가른 나머지
        if rel not in got:
            out.append((rel, "파일 · 그대로(손 고침 없음 · 볼트 판이 앞섬)"))
    return out


def main():
    ap = argparse.ArgumentParser(description="볼트 앞섬 검사")
    ap.add_argument("--dist", required=True, help="배포판 worktree")
    ap.add_argument("--old", default="dist/main", help="견줄 공개판 rev")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    try:
        table = json.load(open(TABLE, encoding="utf-8"))
    except (OSError, ValueError):
        table = {}
    rows = plugins(a.dist, a.old) + files(a.dist, a.old)
    res = []
    for key, what in rows:
        d = table.get(key) if isinstance(table.get(key), dict) else {}
        ok = d.get("판정") in ("실음", "넘김") and bool(str(d.get("까닭", "")).strip())
        res.append({"열쇠": key, "무엇": what, "판정": d.get("판정") if ok else None, "까닭": d.get("까닭") if ok else None})
    miss = [x for x in res if not x["판정"]]
    if a.json:
        print(json.dumps({"앞섬": res, "판정 없음": len(miss)}, ensure_ascii=False, indent=1))
    else:
        print("볼트 앞섬 %d · 판정 있음 %d · 판정 없음 %d (공개판 %s · 판정 표 %s)" % (len(res), len(res) - len(miss), len(miss), a.old, os.path.relpath(TABLE, V)))
        for x in res:
            print("  %s %s — %s%s" % ("✓" if x["판정"] else "✗", x["열쇠"], x["무엇"], " · %s: %s" % (x["판정"], x["까닭"]) if x["판정"] else ""))
        if miss:
            print("판정 없는 앞섬이 있다 — 저마다 «실음»(이번 판에 싣는다) 또는 «넘김»(까닭)을 판정 표에 적는다.")
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main())
