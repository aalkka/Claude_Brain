#!/usr/bin/env python3
"""모듈 내보내기 — 볼트의 모듈 폴더(.claude/skills/<id>/)를 그 모듈 저장소 사본으로 옮겨 쓰고 익명화·개인 값 검사를 한다(LLM 0 · 쓰기 = 저장소 폴더만).

  py -3 3_시스템/module_ship.py <모듈 id> <저장소 폴더>          # 옮겨 쓰기 + 검사(종료 0 = 걸림 0)
  py -3 3_시스템/module_ship.py <모듈 id> <저장소 폴더> --check  # 쓰지 않고 저장소 폴더만 검사

- 빼는 것 = 모듈 폴더의 .gitignore 줄(끝 / = 폴더 · fnmatch) + __pycache__ · *.pyc. 저장소에만 있는 파일은 지운다(.git 은 그대로).
- 익명화 = 글 파일(.py .md .json .html .ps1 .css .js .mjs .txt .sh)에 «바꿈 짝»을 차례로 — 짝 파일은 git 밖
  3_시스템/_index/dist-sync/anon-pairs.txt(«찾을 글<TAB>바꿀 글» · 위에서부터 · 조사 붙은 꼴을 먼저 적는다). 이 대본에는 값을 적지 않는다.
- 검사 = dist-diff 의 LEAK + 볼트 leak-patterns.txt + mobility-leak.txt(있으면) + 짝 파일의 «찾을 글» + 기계 치환 흔적(BROKEN).
  «세션 id 후보»는 오탐이 많아 경고로만 센다(걸림에 안 듦).
- git 커밋·push 는 하지 않는다(사람 몫).
"""
import fnmatch
import importlib.util
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
LOCAL = os.path.join(HERE, "_index", "dist-sync")
TEXT = (".py", ".md", ".json", ".html", ".ps1", ".css", ".js", ".mjs", ".txt", ".sh")
ALWAYS_OUT = ("__pycache__/", "*.pyc")


def dist_diff():
    p = os.path.join(VAULT, ".claude", "skills", "dist-sync", "scripts", "dist-diff.py")
    spec = importlib.util.spec_from_file_location("dist_diff", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def tab_file(name):
    p = os.path.join(LOCAL, name)
    out = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for ln in f:
                ln = ln.rstrip("\n")
                if ln.strip() and not ln.startswith("#"):
                    a, _, b = ln.partition("\t")
                    out.append((a, b))
    return out


def ignores(src):
    pats = list(ALWAYS_OUT)
    gi = os.path.join(src, ".gitignore")
    if os.path.exists(gi):
        with open(gi, encoding="utf-8") as f:
            pats += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    return pats


def skipped(rel, pats):
    segs = rel.split("/")
    for p in pats:
        if p.endswith("/"):
            if p.rstrip("/") in segs[:-1]:
                return True
        elif fnmatch.fnmatch(rel, p) or fnmatch.fnmatch(segs[-1], p):
            return True
    return False


def walk(root, pats=()):
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d != ".git"]
        for fn in fns:
            rel = os.path.relpath(os.path.join(dp, fn), root).replace(os.sep, "/")
            if not skipped(rel, pats):
                out[rel] = os.path.join(dp, fn)
    return out


def anon(text, pairs):
    for a, b in pairs:
        text = text.replace(a, b)
    return text


def ship(mid, repo):
    src = os.path.join(VAULT, ".claude", "skills", mid)
    if not os.path.isfile(os.path.join(src, "module.json")):
        raise SystemExit("모듈 아님: " + src)
    pairs = tab_file("anon-pairs.txt")
    files = walk(src, ignores(src))
    os.makedirs(repo, exist_ok=True)
    wrote = 0
    for rel, full in files.items():
        dst = os.path.join(repo, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(full, "rb") as f:
            b = f.read()
        if rel.endswith(TEXT):
            b = anon(b.decode("utf-8"), pairs).replace("\r\n", "\n").encode("utf-8")
        old = open(dst, "rb").read() if os.path.exists(dst) else None
        if old != b:
            with open(dst, "wb") as f:
                f.write(b)
            wrote += 1
    gone = [rel for rel in walk(repo) if rel not in files]
    for rel in gone:
        os.remove(os.path.join(repo, *rel.split("/")))
    for dp, dns, fns in sorted(os.walk(repo), key=lambda x: -len(x[0])):
        if ".git" not in dp.split(os.sep) and dp != repo and not dns and not fns:
            shutil.rmtree(dp, ignore_errors=True)
    return len(files), wrote, gone


def check(repo):
    dd = dist_diff()
    rules = list(dd.LEAK) + (dd.load_local_leaks(VAULT) or [])
    rules += [(rx, lb or "개인 값") for rx, lb in tab_file("mobility-leak.txt")]
    rules += [(re.escape(a), "익명화 안 된 글") for a, _ in tab_file("anon-pairs.txt")]
    files = walk(repo)
    hits = dd.scan_leaks(files, rules)
    broken = dd.scan_broken(files)
    hard = [h for h in hits if not h[2].startswith("세션 id")]
    soft = [h for h in hits if h[2].startswith("세션 id")]
    return files, hard, soft, broken


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    mid, repo = argv[0], os.path.abspath(argv[1])
    if "--check" not in argv:
        n, wrote, gone = ship(mid, repo)
        print("옮겨 씀: 파일 %d · 바뀜 %d · 지움 %d%s" % (n, wrote, len(gone), (" (" + " · ".join(gone[:5]) + ")") if gone else ""))
    files, hard, soft, broken = check(repo)
    print("검사: 파일 %d · 걸림 %d · 깨진 치환 %d · 경고(세션 id 후보) %d" % (len(files), len(hard), len(broken), len(soft)))
    for rel, i, lb, line in hard[:40]:
        print("  걸림 %s:%d [%s] %s" % (rel, i, lb, line[:80]))
    for rel, i, line in broken[:20]:
        print("  깨짐 %s:%d %s" % (rel, i, line[:80]))
    return 1 if hard or broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
