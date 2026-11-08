# -*- coding: utf-8 -*-
"""pre-commit 묶음 검사 — `pre-commit` 의 sh 검사와 같은 판정을 `git cat-file --batch` 한 번으로 한다.

왜(11-06 시스템 재기 §3-2·6): sh 검사는 스테이지 파일마다 git 5~6번 + grep·head 를 띄워 파일당 0.36~1.1초다.
  400파일 커밋이 3.5~7.6분 — 훅 시간 제한에 닿을 수 있다. 여기서는 커밋마다 git 4번(+ 내릴 민감 노트마다 1번).
판정은 sh 판 그대로: 비밀 의심 = 막음 · sensitive: true = 스테이지에서 내림(못 내리면 막음) ·
  2_지식 = 앞머리 없음·links 따옴표 없음 막음 · 1_수집 = 앞머리 없음 경고 · 마지막에 민감 노트가 다시 올라왔으면 막음.
끝 코드: 0 = 통과 · 3 = 막음 · 그 밖(예외·파이썬 없음) = pre-commit 의 sh 검사가 처음부터 다시 한다.
"""
import re
import subprocess
import sys
import time

# sh 판의 grep -E 와 같은 뜻(줄 단위 = [^-] 가 줄을 넘지 않게 \n 을 뺌 · 바이트 = C 로캘 \b)
SECRET = re.compile(rb"(\bsk-[A-Za-z0-9_-]{16,}|\bghp_[A-Za-z0-9]{16,}|\bAKIA[0-9A-Z]{16}|-----BEGIN[^-\n]*PRIVATE KEY-----)")
SENSITIVE = re.compile(rb"^sensitive:[ \t\r\v\f]*true[ \t\r\v\f]*$", re.M)
OUT = sys.stdout.buffer


def say(msg):
    OUT.write(msg.encode("utf-8") + b"\n")
    OUT.flush()


def git(*a, inp=None):
    return subprocess.run(["git", *a], input=inp, capture_output=True)


def staged(*spec):
    r = git("-c", "core.quotepath=false", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", *spec)
    if r.returncode:
        raise RuntimeError("git diff --cached")
    return [p for p in r.stdout.split(b"\0") if p]


def blobs(paths):
    """{경로: 스테이지 판 내용} — 스테이지에 없는 것(경합으로 빠짐)은 뺀다(sh 판 `cat-file -e` 와 같음)."""
    paths = [p for p in paths if b"\n" not in p]
    if not paths:
        return {}
    r = git("cat-file", "--batch", inp=b"".join(b":" + p + b"\n" for p in paths))
    if r.returncode:
        raise RuntimeError("git cat-file --batch")
    out, i, res = r.stdout, 0, {}
    for p in paths:
        j = out.index(b"\n", i)
        head = out[i:j].split(b" ")
        i = j + 1
        if head[-1] == b"missing" or len(head) != 3:
            continue
        if head[1] != b"blob":
            raise RuntimeError("blob 아님: " + p.decode("utf-8", "replace"))
        n = int(head[2])
        res[p] = out[i:i + n]
        i += n + 1
    return res


def has_head():
    return git("rev-parse", "--verify", "HEAD").returncode == 0


def unstage(path):
    """sh 판 unstage 와 같음 — 다른 세션의 git 이 index.lock 을 쥐면 1초씩 다섯 번."""
    for _ in range(5):
        cmd = ["reset", "-q", "HEAD", "--", path] if has_head() else ["rm", "--cached", "-q", "--", path]
        if git(*cmd).returncode == 0:
            return True
        time.sleep(1)
    return False


def main():
    fail = False
    names = staged()
    data = blobs(names)
    for p in names:
        if p not in data:
            continue
        b = data[p]
        f = p.decode("utf-8", "surrogateescape")
        shown = f.encode("utf-8", "surrogateescape").decode("utf-8", "replace")
        if SECRET.search(b):
            say("❌ secret 의심: {} (커밋 차단)".format(shown))
            fail = True
        if not f.endswith(".md"):
            continue
        if SENSITIVE.search(b):
            if unstage(f):
                say("⚠ sensitive 노트 unstage: {} (push 제외)".format(shown))
            else:
                say("❌ sensitive 노트를 못 내림(잠금?): {} (커밋 차단)".format(shown))
                fail = True
            continue
        first = b.split(b"\n", 1)[0]
        if f.startswith("2_지식/"):
            if first != b"---":
                say("❌ frontmatter 없음: {} (커밋 차단)".format(shown))
                fail = True
            lk = b"\n".join(l for l in b.split(b"\n") if l.startswith(b"links:"))
            if lk and b"[[" in lk and b'"[[' not in lk:
                say('❌ links 프론트매터 깨짐(따옴표 배열 "[[x]]" 필요): {} (커밋 차단)'.format(shown))
                fail = True
        elif f.startswith("1_수집/"):
            if first != b"---":
                say("⚠ frontmatter 없음: {} (경고)".format(shown))
    # 마지막 확인 — 내린 사이 다른 세션의 git add -A 가 다시 올린 민감 노트
    again = staged("--", "*.md")
    for p, b in blobs(again).items():
        if SENSITIVE.search(b):
            say("❌ sensitive 노트가 다시 스테이지됨: {} (커밋 차단)".format(p.decode("utf-8", "replace")))
            fail = True
    return 3 if fail else 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # 판정을 못 했다 → sh 검사에 맡긴다(막지도 통과시키지도 않음)
        try:
            sys.stderr.write("pre-commit-scan: {!r} — sh 검사로\n".format(e))
        except Exception:
            pass
        code = 4
    sys.exit(code)
