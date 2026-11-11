"""배포판 최신 점검 — 볼트 코어와 배포판이 어긋난 곳을 잰다(LLM 0 · 읽기와 fetch 만).

  py -3 .claude/skills/dist-sync/scripts/dist-check.py            # 사람 말 보고 · 종료 0 어긋남 없음 · 1 있음 · 2 못 잼
  py -3 .claude/skills/dist-sync/scripts/dist-check.py --fetch    # 원격을 먼저 받아 본다(③ 을 지금 기준으로)
  py -3 .claude/skills/dist-sync/scripts/dist-check.py --json
  py -3 .claude/skills/dist-sync/scripts/dist-check.py --ack <경로>…  # 이 판은 배포판에 안 싣기로 함 — 다시 고칠 때까지 ① 에서 뺀다

세 가지를 센다.
  ① 볼트에서 바뀌었는데 배포판에 안 간 코어 — 내용이 다르고, 볼트 파일이 배포판이 그 파일을 마지막으로 고친 커밋보다 나중에 고쳐졌다.
     배포판이 익명화해 늘 다른 파일(제작자 볼트 실측 등)은 볼트를 다시 고치기 전엔 안 잡힌다. 배포판에 없는 파일은 마지막 배포 커밋 뒤에 생긴 것만.
     볼트에서 지웠는데 배포판에 남은 코어도 센다. 층이 안 정해진 새 파일(«미분류»)도 싣기 전에 정해야 하니 센다.
  ② 배포판 worktree 에 커밋했는데 push 안 한 것(+ 커밋 안 한 고침)
  ③ 원격에만 있는 것(받아 합칠 것) — 마지막으로 받아 둔 원격 기준. --fetch 나 건강 줄의 하루 한 번 받기가 새로 받는다.
  ④ 볼트 밖 설정(작업 스케줄러·레지스트리·브라우저·설치 프로그램 등)을 건드리는 코어인데 안내 목록에 없는 곳 — external.py scan
배포판 worktree = 볼트 저장소의 worktree 가운데 `dist-sync` 가지 · 없으면(제작자 볼트가 아니면) 잴 것이 없다.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
BRANCH = "dist-sync"
ACK = os.path.join("3_시스템", "_index", "dist-sync", "check-ack.json")  # mf:allow-path  (안 싣기로 한 판 · 개인 층)
FETCH_EVERY = 20 * 3600          # 건강 줄이 원격을 다시 받는 간격(초) — 하루 한 번
FETCH_TIMEOUT = 60

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


def unsynced(A, B):
    fa, fb = dd.walk(A), dd.walk(B)
    T, top = last_touch(B)
    ack = load_ack(A)
    revs = None
    out = []
    for rel, p in sorted(fa.items()):
        lay = dd.layer(rel)
        if lay not in ("코어", dd.L_CLAUDE, "미분류"):
            continue
        mine = dd.sha(p)
        if rel in fb and mine == dd.sha(fb[rel]):
            continue
        if ack.get(rel) == mine:
            continue
        t = T.get(rel, top) if rel in fb else top
        m = os.path.getmtime(p)
        if t is None or m <= t:
            continue
        revs = vault_revs(A) if revs is None else revs
        if same_as_before(A, rel, t, mine, revs):
            continue
        what = "층 미정 새 파일" if lay == "미분류" else ("새 파일" if rel not in fb else "고침")
        out.append({"path": rel, "what": what, "vault": stamp(m), "dist": stamp(t if rel in fb else None)})
    only = [r for r in sorted(set(fb) - set(fa)) if dd.layer(r) == "코어"]
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
            if g and g > T.get(rel, 0) and ack.get(rel) != "지움":
                out.append({"path": rel, "what": "볼트에서 지움", "vault": stamp(g), "dist": stamp(T.get(rel))})
    return out, top


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


def check(A=VAULT, B=None, do_fetch=False):
    B = B or find_dist(A)
    if not B:
        return {"dist": None}
    res = {"dist": B, "fetch_error": fetch(B) if do_fetch else None}
    res["unsynced"], top = unsynced(A, B)
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
    res["external"] = external_gaps(A, B)
    return res


def external_gaps(A, B):
    """④ 볼트 밖 설정 추적 — 코어(배포판 + 곧 실릴 볼트 코어)가 볼트 밖을 건드리는데 안내 목록(external.json)에 없는 곳."""
    s = importlib.util.spec_from_file_location("dist_external", os.path.join(HERE, "external.py"))
    ex = importlib.util.module_from_spec(s)
    s.loader.exec_module(ex)
    try:
        gaps, bad = ex.scan([B, A], layer=dd.layer)
    except (OSError, ValueError, KeyError) as e:
        return ["목록 못 읽음(%s)" % type(e).__name__]
    return ["%s:%d — %s" % (rel, n, kind) for rel, kind, n in gaps] + ["항목 %s — %s" % b for b in bad]


def total(r):
    return len(r["unsynced"]) + len(r["unpushed"]) + len(r["uncommitted"]) + len(r["remote_only"]) + len(r.get("external", []))


def todo(r):
    t = []
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
    return " · ".join(t)


def summary(r):
    """건강 줄 한 줄 — 무엇이 몇 건 · 할 일."""
    if not r.get("dist"):
        return "배포판 worktree 없음(점검 안 함)"
    n = total(r)
    note = "" if r["upstream"] else " · 원격 짝(upstream) 없어 push·받을 것은 못 잼"
    if not n:
        return "배포판 최신(어긋남 0 · 원격 받아 본 때 %s)%s" % (r["fetched"], note)
    parts = [("안 올린 고침", len(r["unsynced"])), ("커밋 안 함", len(r["uncommitted"])),
             ("push 안 함", len(r["unpushed"])), ("받을 것", len(r["remote_only"])),
             ("안내 없는 바깥 설정", len(r.get("external", [])))]
    return "배포판 어긋남 %d — %s · 할 일 %s%s" % (n, " · ".join("%s %d" % p for p in parts if p[1]), todo(r), note)


def report(r):
    if not r.get("dist"):
        return summary(r)
    L = ["배포판 점검 — %s · 배포판 %s" % (datetime.datetime.now().strftime("%m-%d %H:%M"), r["dist"]),
         "마지막 배포 커밋 %s · 원격 받아 본 때 %s%s" % (r["last_publish"], r["fetched"],
                                                 " · 받기 실패: %s" % r["fetch_error"] if r.get("fetch_error") else "")]
    L.append("① 볼트에서 바뀌었는데 배포판에 안 간 코어 %d" % len(r["unsynced"]))
    L += ["   - %s (%s · 볼트 %s · 배포판 %s)" % (x["path"], x["what"], x["vault"], x["dist"]) for x in r["unsynced"]]
    L.append("② 배포판에 커밋했는데 push 안 한 것 %d%s" % (len(r["unpushed"]), " · 커밋 안 한 고침 %d" % len(r["uncommitted"]) if r["uncommitted"] else ""))
    L += ["   - " + c for c in r["unpushed"]] + ["   - (커밋 안 함) " + p for p in r["uncommitted"][:20]]
    L.append("③ 원격에만 있는 것(받아 합칠 것) %d" % len(r["remote_only"]))
    L += ["   - " + c for c in r["remote_only"]]
    L.append("④ 볼트 밖 설정인데 안내 목록(external.json)에 없는 곳 %d" % len(r.get("external", [])))
    L += ["   - " + c for c in r.get("external", [])]
    L.append(summary(r))
    return "\n".join(L)


def ack(A, paths):
    """안 싣기로 한 판을 적는다 — 그 파일을 다시 고치면 다시 잡힌다."""
    fa = dd.walk(A)
    cur = load_ack(A)
    done = []
    for p in paths:
        rel = os.path.relpath(os.path.abspath(p), A).replace("\\", "/") if os.path.isabs(p) else p.replace("\\", "/")
        cur[rel] = dd.sha(fa[rel]) if rel in fa else "지움"
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
    a = ap.parse_args()
    A = os.path.abspath(a.a)
    if a.ack:
        print("안 싣기로 적음: " + ", ".join(ack(A, a.ack)))
        return 0
    try:
        r = check(A, os.path.abspath(a.b) if a.b else None, a.fetch)
    except (OSError, subprocess.SubprocessError) as e:
        print("못 잼: %s" % e)
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else report(r))
    return 1 if r.get("dist") and total(r) else 0


if __name__ == "__main__":
    sys.exit(main())
