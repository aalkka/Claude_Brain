"""배포판 후보 파일을 3방향 합치기로 만든다 — 볼트 판을 «그대로 복사»하면 배포판에만 있는 손 익명화가 되돌아가는데 유출 검사는 그 꼴을 다 못 잡는다(11-26).

파일마다:
  배포판 = 지난 공개판(--old)의 그 파일(손 익명화가 든 판)
  기준   = 볼트 이력에서 배포판 판과 가장 닮은 판(배포 커밋 시각의 볼트 판을 쓰면 볼트의 새 기능이 «배포판이 지운 것»으로 읽혀 빠진다)
  볼트   = 지금 볼트 판
기준 = 배포판(손 고침 없음) → 볼트 판 · 기준 = 볼트(볼트 안 바뀜) → 배포판 판 · 그 밖 = git merge-file.
볼트 git 이 그 파일을 안 따르면(이력 0 · 예: 플러그인 styles.css) 기준을 못 고른다 — 볼트 판으로 덮지 않고 배포판 판을 둔 채 «기준 없음»으로 낸다(11-28 · 손 익명화가 되돌아간 뿌리).
충돌 칸: 줄 수가 같고 닮았으면(«같은 줄의 두 익명화») 이미 공개·검토된 배포판 글 · 아니면 배포판 글을 두고 «읽을 것»으로 낸다.
글 아닌 파일(실행 파일·그림)은 판정을 맨 먼저 하고 바이트 그대로 — 줄끝을 바꾸지 않는다(새 파일 포함 · 11-26 실행 파일 넷이 깨진 뿌리).

  py -3 pub_merge.py <파일 목록.txt> --dist <배포판 worktree> [--old <공개판 rev · 기본 dist/main>] [--write] [--show <경로 조각|all>]

볼트가 낱말을 한꺼번에 바꾼 적이 있으면(예: 호칭 → «사용자») 개인화 파트 personal/renames.json {"옛 낱말": "새 낱말"} 에 적는다 —
기준을 고를 때 그 바꿈만 있는 줄을 «볼트가 안 바꾼 줄»로 보아 배포판의 손 익명화가 이긴다. 없으면 바꿈 없음.
"""
import argparse
import difflib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
TEXT = (".md", ".py", ".ps1", ".psm1", ".json", ".mjs", ".cjs", ".js", ".ts", ".tsv", ".txt", ".html", ".css", ".sh", ".yml", ".yaml",
        ".gitattributes", ".gitignore", ".tmpl", ".toml", ".ini", ".cfg")  # mf:allow-path  (글 파일 끝 이름 — 읽기만)
NOHIST = object()   # 볼트 git 이력에 그 파일이 없음
SEM = re.compile(r"\n*>[ \t]*\[!info\]-[ \t]*관련 노트[ \t]*%%sl%%(?:\n>[^\n]*)*".encode("utf-8"))   # 찾기 색인이 쓰는 칸 — 싣지 않는다


def git(repo, *a):
    r = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=off", *a], capture_output=True)
    return r.returncode, r.stdout


def is_text(rel, data):
    return (rel.endswith(TEXT) or os.path.basename(rel).startswith(".git")) and b"\0" not in data[:8000]


def lf(b, strip):
    if b is None:
        return None
    b = b.replace(b"\r\n", b"\n")
    return SEM.sub(b"", b) if strip else b


def renames():
    p = os.path.join(os.path.dirname(HERE), "personal", "renames.json")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [(k.encode("utf-8"), v.encode("utf-8")) for k, v in json.load(f).items() if isinstance(v, str)]


def pick_base(rel, mine, strip, rn):
    """볼트 이력에서 배포판 판과 가장 닮은 판 · 이력이 하나도 없으면 NOHIST(«손 고침 없음»과 가른다)."""
    _, hs = git(V, "log", "-30", "--format=%H", "HEAD", "--", rel)
    if not hs.split():
        return NOHIST
    ml = mine.split(b"\n")
    cands = []
    for h in hs.decode().split():
        c, o = git(V, "show", "%s:%s" % (h, rel))
        if c:
            continue
        o = lf(o, strip)
        for a, b in rn:
            o = o.replace(a, b)
        cands.append((difflib.SequenceMatcher(None, ml, o.split(b"\n"), autojunk=False).quick_ratio(), o))
    best, base = -1.0, None
    for _, c in sorted(cands, key=lambda x: -x[0])[:3]:
        r0 = difflib.SequenceMatcher(None, ml, c.split(b"\n"), autojunk=False).ratio()
        if r0 > best:
            best, base = r0, c
    return base


def merge3(mine, base, new):
    with tempfile.TemporaryDirectory() as td:
        ps = []
        for n, data in (("mine", mine), ("base", base), ("theirs", new)):
            p = os.path.join(td, n)
            open(p, "wb").write(data)
            ps.append(p)
        r = subprocess.run(["git", "merge-file", "-p", "-L", "배포판", "-L", "기준", "-L", "볼트", *ps], capture_output=True)
    if r.returncode == 0:
        return r.stdout, []
    txt = r.stdout.decode("utf-8", "replace").split("\n")
    out, left, i = [], [], 0
    while i < len(txt):
        if txt[i].startswith("<<<<<<< "):
            m = next(k for k in range(i, len(txt)) if txt[k] == "=======")
            e = next(k for k in range(m, len(txt)) if txt[k].startswith(">>>>>>> "))
            a, b = txt[i + 1:m], txt[m + 1:e]
            sim = difflib.SequenceMatcher(None, "\n".join(a), "\n".join(b)).ratio()
            out += a
            if not (len(a) == len(b) and sim >= 0.5):
                left.append((len(out), a, b, sim))
            i = e + 1
        else:
            out.append(txt[i])
            i += 1
    return "\n".join(out).encode("utf-8"), left


def main():
    ap = argparse.ArgumentParser(description="배포판 후보 파일을 3방향 합치기로 만든다")
    ap.add_argument("list", help="볼트 상대 경로 목록 파일(한 줄에 하나)")
    ap.add_argument("--dist", required=True, help="배포판 worktree")
    ap.add_argument("--old", default="dist/main", help="지난 공개판 rev(손 익명화가 든 판)")
    ap.add_argument("--write", action="store_true", help="배포판 worktree 에 씀(없으면 갈래만 셈)")
    ap.add_argument("--show", default="", help="읽을 것 충돌을 보일 경로 조각 · all")
    a = ap.parse_args()
    rn = renames()
    out = {k: [] for k in ("글 아님(바이트 그대로)", "새 파일", "바뀐 것 없음", "그대로(손 고침 없음)", "손 고침만(볼트 안 바뀜)", "합침", "읽을 것", "기준 없음(배포판 판 둠)")}
    for rel in [x.strip() for x in io.open(a.list, encoding="utf-8") if x.strip() and not x.startswith("#")]:
        raw = open(os.path.join(V, *rel.split("/")), "rb").read()
        if not is_text(rel, raw):                                  # 맨 먼저 — 새 파일이어도 줄끝을 건드리지 않는다
            out["글 아님(바이트 그대로)"].append(rel)
            res = raw
        else:
            strip = rel.endswith(".md")
            new = lf(raw, strip)
            c, mine = git(a.dist, "show", "%s:%s" % (a.old, rel))
            mine = lf(mine, strip) if c == 0 else None
            if mine is None:
                out["새 파일"].append(rel)
                res = new
            elif mine == new:
                out["바뀐 것 없음"].append(rel)
                res = mine
            else:
                base = pick_base(rel, mine, strip, rn)
                if base is NOHIST or base is None:
                    # 이력이 없거나(NOHIST) 있어도 읽을 판이 없으면(None) 기준을 못 고른다 — 볼트 판으로 덮으면 배포판에만 있는 손 익명화가 되돌아간다 — 배포판 판을 두고 사람이 바뀐 줄을 읽어 옮긴다
                    d = [t for t in difflib.unified_diff(mine.decode("utf-8", "replace").split("\n"), new.decode("utf-8", "replace").split("\n"), lineterm="", n=0)
                         if t[:1] in "+-" and not t.startswith(("+++", "---"))]
                    out["기준 없음(배포판 판 둠)"].append("%s (바뀐 줄 %d)" % (rel, len(d)))
                    if a.show and (a.show == "all" or a.show in rel):
                        print("### %s — 기준 없음 · 배포판(-) ↔ 볼트(+)" % rel)
                        print("\n".join("  " + t[:200] for t in d[:40]))
                    res = mine
                elif base == mine:
                    out["그대로(손 고침 없음)"].append(rel)
                    res = new
                elif base == new:
                    out["손 고침만(볼트 안 바뀜)"].append(rel)
                    res = mine
                else:
                    res, left = merge3(mine, base, new)
                    if left:
                        out["읽을 것"].append("%s (%d곳)" % (rel, len(left)))
                        if a.show and (a.show == "all" or a.show in rel):
                            for at, x, y, sim in left:
                                print("### %s @%d (닮음 %.2f)" % (rel, at, sim))
                                print("\n".join("  배| " + t[:200] for t in x[:12]))
                                print("\n".join("  볼| " + t[:200] for t in y[:12]))
                    else:
                        out["합침"].append(rel)
        if a.write:
            dst = os.path.join(a.dist, *rel.split("/"))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, "wb").write(res)
    for k, v in out.items():
        print("== %s %d" % (k, len(v)))
        if k in ("합침", "읽을 것", "손 고침만(볼트 안 바뀜)", "기준 없음(배포판 판 둠)"):
            for x in v:
                print("   ", x)
    return 1 if out["읽을 것"] or out["기준 없음(배포판 판 둠)"] else 0


if __name__ == "__main__":
    sys.exit(main())
