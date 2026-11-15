# -*- coding: utf-8 -*-
"""pre-push 묶음 검사 — 보낼 커밋들이 더하거나 바꾼 md 가운데 `sensitive: true` 가 든 판이 있으면 push 를 막는다(11-15 · 마지막 그물).

왜: pre-commit 이 민감 노트를 내리고 `.git/info/exclude` 에 적어도 틈이 남는다(처음 찾는 그 커밋 · 손으로 친 --no-verify 커밋).
  커밋은 이 PC 안이라 고칠 수 있지만, 원격에 간 이력은 강제 push 없이는 못 지운다 — 자동 push 가 내보내기 전에 여기서 막는다.
범위(git 이 stdin 으로 주는 «로컬참조 로컬sha 원격참조 원격sha» 줄마다):
  원격 sha 를 이 PC 가 알면 원격sha..로컬sha · 새 가지(원격 sha 0)·모르는 원격 sha 면 로컬sha --not --remotes=<원격 이름>
  (이름 없는 URL 로 보내면 그 쪽이 무엇을 가졌는지 몰라 전 이력) · 로컬 sha 0(가지 지우기)은 볼 것 없음.
  이미 원격에 있는 이력(11-15 전에 샌 것)은 범위 밖이라 평소 push 를 막지 않는다.
끝 코드: 0 = 통과 · 3 = 막음 · 그 밖(예외·파이썬 없음) = pre-push 의 sh 판이 처음부터 다시 한다.

  (pre-push 가 부름)  py -3 3_시스템/hooks/pre-push-scan.py <원격 이름> < 참조 줄
  py -3 3_시스템/hooks/pre-push-scan.py --check   아직 안 보낸 커밋(@{u}..HEAD · 따라가는 가지 없으면 --not --remotes)만 재서
                                                  {"hits": [[커밋, 경로], …]} 한 줄 — drift.py 건강 줄(막힌 push 는 훅 밖에서 안 보인다)
"""
import json
import re
import subprocess
import sys
import time

SENSITIVE = re.compile(rb"^sensitive:[ \t\r\v\f]*true[ \t\r\v\f]*$", re.M)  # pre-commit-scan.py 와 같은 뜻
LOG = "3_시스템/_index/hooks.log"  # 훅은 저장소 뿌리에서 돈다


def git(*a, inp=None):
    return subprocess.run(["git", *a], input=inp, capture_output=True)


def zero(s):
    return bool(s) and set(s) == {"0"}


def ranges(lines, remote):
    """참조 줄 → rev-list 인자 목록들."""
    r = git("remote")
    named = r.returncode == 0 and remote in r.stdout.decode("utf-8", "replace").split()
    for ln in lines:
        parts = ln.split()
        if len(parts) != 4:
            continue
        _lref, lsha, _rref, rsha = parts
        if zero(lsha):
            continue
        if not zero(rsha) and git("cat-file", "-e", rsha + "^{commit}").returncode == 0:
            yield [rsha + ".." + lsha]
        else:
            yield [lsha, "--not", "--remotes=" + remote] if named else [lsha]


def hits(revs):
    """[(커밋 앞 8자, 경로)] — 범위 안 커밋마다 더하거나 바꾼 md(병합은 부모마다)의 그 판에 민감 표시가 든 것."""
    r = git("-c", "core.quotepath=false", "log", "--format=@%H", "--raw", "--no-abbrev", "--no-renames", "-m",
            "--diff-filter=AM", "-z", *revs, "--", "*.md")
    if r.returncode:
        raise RuntimeError("git log " + " ".join(revs))
    toks = [t.lstrip(b"\n") for t in r.stdout.split(b"\0")]
    pairs, commit, i = [], b"", 0
    while i < len(toks):
        t = toks[i]
        if t.startswith(b"@"):
            commit = t[1:]
        elif t.startswith(b":") and i + 1 < len(toks):
            pairs.append((commit, t.split()[3], toks[i + 1]))
            i += 1
        i += 1
    blobs = sorted({b for _, b, _ in pairs})
    if not blobs:
        return []
    r = git("cat-file", "--batch", inp=b"".join(b + b"\n" for b in blobs))
    if r.returncode:
        raise RuntimeError("git cat-file --batch")
    out, j, bad = r.stdout, 0, set()
    for b in blobs:
        k = out.index(b"\n", j)
        head = out[j:k].split(b" ")
        j = k + 1
        if len(head) != 3:
            continue
        n = int(head[2])
        if SENSITIVE.search(out[j:j + n]):
            bad.add(b)
        j += n + 1
    seen, res = set(), []
    for c, b, p in pairs:
        if b in bad and (c, p) not in seen:
            seen.add((c, p))
            res.append((c[:8].decode(), p.decode("utf-8", "replace")))
    return res


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8", newline="") as f:
            f.write("{} {}\r\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def main():
    out = sys.stdout.buffer
    if "--check" in sys.argv:
        up = git("rev-parse", "--verify", "-q", "@{u}")
        revs = ["@{u}..HEAD"] if up.returncode == 0 else ["HEAD", "--not", "--remotes"]
        out.write(json.dumps({"hits": hits(revs)}, ensure_ascii=False).encode("utf-8") + b"\n")
        return 0
    remote = sys.argv[1] if len(sys.argv) > 1 else ""
    lines = sys.stdin.buffer.read().decode("utf-8", "replace").splitlines()
    found = []
    for revs in ranges(lines, remote):
        found += [h for h in hits(revs) if h not in found]
    if not found:
        return 0
    for c, p in found:
        out.write("❌ push 막음 — 보낼 커밋 {} 에 민감 노트: {}\n".format(c, p).encode("utf-8"))
    out.write("   원격에 가면 강제 push 없이는 이력에서 못 지운다 · 고치기 = 안 보낸 커밋에서 그 파일을 빼고 다시 커밋(Claude 에게 «push 막힘»)\n".encode("utf-8"))
    log("pre-push BLOCKED 민감 노트 {}건 → {} · {}".format(len(found), remote, ", ".join(p for _, p in found[:3])))
    out.flush()
    return 3


if __name__ == "__main__":
    try:
        code = main()
    except Exception as e:  # 판정을 못 했다 → sh 판에 맡긴다
        try:
            sys.stderr.write("pre-push-scan: {!r} — sh 검사로\n".format(e))
        except Exception:
            pass
        code = 4
    sys.exit(code)
