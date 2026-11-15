# -*- coding: utf-8 -*-
"""pre-commit 묶음 검사 — `pre-commit` 의 sh 검사와 같은 판정을 `git cat-file --batch` 한 번으로 한다.

왜(11-06 시스템 재기 §3-2·6): sh 검사는 스테이지 파일마다 git 5~6번 + grep·head 를 띄워 파일당 0.36~1.1초다.
  400파일 커밋이 3.5~7.6분 — 훅 시간 제한에 닿을 수 있다. 여기서는 커밋마다 git 4번(+ 내릴 민감 노트마다 1번).
판정은 sh 판 그대로: 비밀 의심 = 막음 · sensitive: true = 스테이지에서 내림(못 내리면 막음) ·
  2_지식 = 앞머리 없음·links 따옴표 없음 막음 · 1_수집 = 앞머리 없음 경고 · 마지막에 민감 노트가 다시 올라왔으면 막음.
민감 노트는 내리기 전에 `.git/info/exclude` 에 적는다(11-15) — 내리기만으로는 마지막 확인 뒤 ~ 커밋이 스테이지를 다시 읽기 전 틈에
  다른 세션의 `git add -A` 가 다시 올려 샜다(격리 재현 134회 중 24 · 적으면 149회 중 0). 적은 뒤로는 `add -A` 가 아예 올리지 않는다.
  이 대본이 적은 줄(EX_MARK 다음 줄)만 다루고, 노트가 없어졌거나 더는 민감이 아니면 다음 커밋 때 지운다 · 내림·제외·풀림은 hooks.log 에 한 줄.
끝 코드: 0 = 통과 · 3 = 막음 · 그 밖(예외·파이썬 없음) = pre-commit 의 sh 검사가 처음부터 다시 한다.
"""
import os
import re
import subprocess
import sys
import time

# sh 판의 grep -E 와 같은 뜻(줄 단위 = [^-] 가 줄을 넘지 않게 \n 을 뺌 · 바이트 = C 로캘 \b)
SECRET = re.compile(rb"(\bsk-[A-Za-z0-9_-]{16,}|\bghp_[A-Za-z0-9]{16,}|\bAKIA[0-9A-Z]{16}|-----BEGIN[^-\n]*PRIVATE KEY-----)")
SENSITIVE = re.compile(rb"^sensitive:[ \t\r\v\f]*true[ \t\r\v\f]*$", re.M)
OUT = sys.stdout.buffer
EX_MARK = "# 외부뇌 민감 노트(pre-commit) — 노트에서 sensitive: true 를 빼거나 지우면 다음 커밋 때 이 두 줄이 지워진다"
LOG = "3_시스템/_index/hooks.log"  # 훅은 저장소 뿌리에서 돈다


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
    """sh 판 unstage 와 같음 — 다른 세션의 git 이 index.lock 을 쥐면 1초씩 다섯 번.
    경로는 글자 그대로(--literal-pathspecs) — 아니면 «[2026-2] 세미나.md» 의 [..] 가 글자 묶음이 되어 «2 세미나.md» 까지 내린다(11-15 격리 시험)."""
    for _ in range(5):
        cmd = ["--literal-pathspecs"] + (["reset", "-q", "HEAD", "--", path] if has_head() else ["rm", "--cached", "-q", "--", path])
        if git(*cmd).returncode == 0:
            return True
        time.sleep(1)
    return False


def log(msg):
    """hooks.log 한 줄 — 11-15 전에는 성공한 내리기를 안 적어 어느 커밋에서 경합에 졌는지 잴 수 없었다."""
    try:
        with open(LOG, "a", encoding="utf-8", newline="") as f:
            f.write("{} pre-commit {}\r\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def ex_pat(path):
    """경로 → exclude 줄 — 뿌리에 고정(/)하고 와일드카드·역슬래시·끝 공백은 역슬래시로 막는다(«[2026-2] 세미나» 가 글자 묶음이 되지 않게)."""
    p = re.sub(r"([\\*?\[])", r"\\\1", path)
    tail = len(p) - len(p.rstrip(" "))
    return "/" + (p[:len(p) - tail] + "\\ " * tail if tail else p)


def ex_raw(line):
    """exclude 줄 → 경로(ex_pat 의 거꾸로) · 뿌리 고정 줄이 아니면 None."""
    return re.sub(r"\\(.)", r"\1", line[1:]) if line.startswith("/") else None


def still_sensitive(path):
    try:
        with open(path, "rb") as f:
            return bool(SENSITIVE.search(f.read()))
    except OSError:
        return False


def exclude_sync(add):
    """민감 노트(add)를 `.git/info/exclude` 에 적고, 이 대본이 적은 줄 중 노트가 없어졌거나 더는 민감이 아닌 것은 지운다.
    사람이 적은 줄은 그대로 · 쓰기는 임시 파일 → 바꿔치기(반쯤 쓴 exclude 를 git 이 읽지 않게)."""
    r = git("rev-parse", "--git-path", "info/exclude")
    if r.returncode:
        return
    ep = r.stdout.strip().decode("utf-8")
    try:
        with open(ep, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        lines = []
    out, have, i = [], set(), 0
    while i < len(lines):
        if lines[i] == EX_MARK and i + 1 < len(lines):
            raw = ex_raw(lines[i + 1])
            if raw is not None and (raw in add or still_sensitive(raw)):
                if raw not in have:
                    out += lines[i:i + 2]
                    have.add(raw)
            else:
                log("민감 노트 제외 풀림(없어졌거나 민감 아님): " + (raw or lines[i + 1]))
            i += 2
            continue
        out.append(lines[i])
        i += 1
    for p in add:
        if p not in have:
            out += [EX_MARK, ex_pat(p)]
            have.add(p)
    if out != lines:
        os.makedirs(os.path.dirname(ep) or ".", exist_ok=True)
        tmp = "{}.tmp-{}".format(ep, os.getpid())
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(out) + "\n")
        os.replace(tmp, ep)


def exclude(add):
    """exclude_sync 가 실패해도(잠김 등) 검사는 이어 간다 — 그때는 내리기만 한다(11-15 전과 같음)."""
    try:
        exclude_sync(add)
    except Exception as e:  # noqa: BLE001
        log("민감 노트 제외 못 함({}): {}".format(type(e).__name__, ", ".join(add)[:120]))


def main():
    fail = False
    excluded = False
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
            exclude([f])  # 내리기 전에 — 적은 뒤로는 다른 세션의 add -A 가 다시 올리지 못한다
            excluded = True
            if unstage(f):
                say("⚠ sensitive 노트 unstage: {} (push 제외)".format(shown))
                log("민감 노트 내림·제외: " + shown)
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
    if not excluded:
        exclude([])  # 지울 줄만 본다(노트가 없어졌거나 sensitive 를 뺌) — 적은 줄 몇 개를 읽는 값
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
