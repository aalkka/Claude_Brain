# -*- coding: utf-8 -*-
"""외부뇌 Stop 훅 — stop-check.ps1 을 같은 판정으로 옮긴 파이썬판(고침안 · 11-06 perf-system).

왜: PowerShell 판이 턴마다 볼트 전체(지식·_ref 495개 · 6.5만 줄)를 한 줄씩 객체로 읽어 검사만 3.1~4.0초 +
기동 0.45초 + git 1.2초 이상이 걸렸다(11-06 실측 · 대화 기록 14일 중앙 4.7초 · p90 11.5초 · 1361턴 합 2.5시간).
판정·출력·커밋 순서는 PS 판과 같다. 다른 점 둘:
  ① 같은 검사를 파이썬으로(파일 읽기·정규식) — 기동 0.14초 · 검사 수백 ms
  ② 커밋 전에 `git status --porcelain`(잠금 안 잡음) 한 번 — 바뀐 것이 없으면 add·diff·commit 다섯 번을 띄우지 않는다
계약(공식): stdout 에 {"decision":"block","reason":...} + 종료 0 · 그 밖엔 출력 없음 · 어떤 예외에도 종료 0(fail-open).

  py -3 3_시스템/hooks/stop-check.py            (Stop 훅 · stdin = 훅 입력)
  py -3 stop-check.py --check-only --vault <V>   (재기·대조용 — git·가드·받은함 쓰기 없음 · 판정과 걸린 시간만)
  py -3 stop-check.py --commit-only [--vault <V>] (서버 — 마지막 커밋이 24시간 넘으면 «외부뇌 서버»가 부른다 · 11-12 사용자 안 A)
      검사·가드·받은함 없이 아래 autocommit 만 · index.lock 이 있으면 건너뜀 · push 없음 · pre-commit(비밀값·프론트매터) 그대로
      stdout = {"result": "없음|커밋|막힘|잠금|add 실패"} 한 줄

v2(11-06 perf-system-2 · 치명 경우 대조 뒤):
  · add·commit 에 시간 제한을 두지 않는다(PS 판과 같음). v1 은 git 한 번에 120초 — pre-commit 이 파일마다 0.36초
    (10-25 실측 178파일 64초)라 330파일쯤 넘는 커밋을 매번 죽여 자동 커밋이 영영 안 되고, add 를 죽이면 index.lock 이 남는다.
  · 검사가 예외로 죽어도 커밋은 한다(hooks.log 에 한 줄). v1 은 roles.json 칸이 하나 빠져도 검사·커밋을 모두 건너뛰었다
    (PS 판은 빠진 칸을 빈 값으로 읽고 계속 간다 · roles.json 을 못 읽으면 PS 판도 커밋을 건너뛴다 — 이것도 막음).
  · 숨김에 더해 시스템 속성 파일도 뺀다(Get-ChildItem -Force 없음과 같게) · 받은함 «이미 알림» 비교는 대소문자 무시(-notcontains 와 같게)
  · status 는 --untracked-files=normal 을 밝혀 둔다(설정 status.showUntrackedFiles=no 가 새 파일 커밋을 막지 않게)
"""
import datetime as dt
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time

NOWIN = 0x08000000 if os.name == "nt" else 0
HIDDEN = getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 2) | getattr(stat, "FILE_ATTRIBUTE_SYSTEM", 4)
MOC_RX_CACHE = {}
DD = re.compile(r"^\s*\$\$.*\$\$\s*$")
LINKS = re.compile(r"^\s*links:", re.I)
LINES = re.compile(r"\r\n|\n|\r")          # Get-Content 의 줄 나눔(CR·LF·CRLF)


def md_files(root):
    """Get-ChildItem -Filter *.md -File -Recurse (‑Force 없음) 와 같은 범위 — 숨김 파일·숨김 폴더는 뺀다."""
    out = []
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            it = list(os.scandir(d))        # 정렬하지 않는다 — scandir 도 FindNextFile 이라 Get-ChildItem 과 같은 차례(NTFS 색인 차례)
        except OSError:
            continue
        sub = []
        for e in it:
            try:
                st = e.stat(follow_symlinks=False)
            except OSError:
                continue
            if getattr(st, "st_file_attributes", 0) & HIDDEN:
                continue
            if e.is_dir(follow_symlinks=False):
                sub.append(e.path)
            elif e.name.lower().endswith(".md"):
                out.append(e.path)
        stack.extend(reversed(sub))
    return out


def read(p):
    try:
        with open(p, "rb") as f:
            b = f.read()
    except OSError:
        return None
    t = b.decode("utf-8", "replace")
    return t[1:] if t.startswith("﻿") else t


def git(vault, *args, timeout=None):
    """시간 제한은 status 에만(잠금을 안 잡아 죽여도 남는 것이 없다). add·commit 은 PS 판처럼 끝까지 기다린다."""
    try:
        r = subprocess.run(["git", "-C", vault] + list(args), capture_output=True, creationflags=NOWIN, timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, b""


def commit_later(vault):
    """기능 단계 «자동 커밋»이 하옵이고 마지막 커밋(HEAD 이동) 뒤 min_gap_minutes 가 안 지났으면 True.
    어떤 오류도 False(= 지금처럼 커밋). 옵션 파일이 없으면 options 를 열기만 하고 끝난다."""
    try:
        sys.path.insert(0, os.path.join(vault, "3_시스템"))
        import options
        if options.level("git.autocommit", vault=vault) != "low":
            return False
        gap = float(options.params("git.autocommit", "low", vault=vault).get("min_gap_minutes") or 5) * 60
        return time.time() - os.stat(os.path.join(vault, ".git", "logs", "HEAD")).st_mtime < gap
    except Exception:
        return False


def autocommit(vault, hlog, tag="Stop"):
    """바뀐 것이 있으면 볼트 커밋(Claude) → 1_수집 커밋(User) — Stop 훅과 서버가 같이 쓴다. push 없음.
    돌려줌 = "없음"(바뀐 것 없음) · "커밋" · "막힘"(pre-commit 이 막아 스테이지가 남음) · «add 실패»"""
    rc, out = git(vault, "--no-optional-locks", "status", "--porcelain", "--untracked-files=normal", timeout=300)
    if rc == 0 and not out.strip():
        return "없음"
    today = dt.date.today().isoformat()            # 바뀐 것이 있거나 status 를 못 읽으면 PS 판과 같은 순서로
    rc, _ = git(vault, "add", "-A", "--", ":!1_수집")
    if rc != 0:
        log(hlog, tag + " git add 실패 — 자동 커밋 안 됨(잠금 확인)")
    if git(vault, "diff", "--cached", "--quiet")[0] != 0:
        git(vault, "commit", "-m", "session: " + today, "--author=Claude <claude@local>")
    git(vault, "add", "1_수집")
    if git(vault, "diff", "--cached", "--quiet")[0] != 0:
        git(vault, "commit", "-m", "user: " + today, "--author=User <user@local>")
    if git(vault, "diff", "--cached", "--quiet")[0] != 0:
        log(hlog, tag + " commit BLOCKED by pre-commit - staged remain")
        return "막힘"
    return "add 실패" if rc != 0 else "커밋"


def log(path, msg):
    try:
        with open(path, "a", encoding="utf-8", newline="") as f:
            f.write("{} {}\r\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def check(vault):
    """(위반 다섯 목록, 걸린 초, 센 파일 수) — PS 판 ①②③④ 와 같은 판정."""
    t0 = time.perf_counter()
    moc = os.path.join(vault, "2_지식", "MOC.md")
    if not os.path.exists(moc):
        return None
    moc_text = read(moc) or ""
    rj = json.load(open(os.path.join(vault, "3_시스템", "roles.json"), encoding="utf-8-sig"))
    dirs = [rj["roles"][g].replace("/", "\\") for g in rj["groups"]["moc_notes"]]
    exempt = {rj["roles"]["modules"].replace("/", "\\")}
    no_fm, no_moc, bad_links = [], [], []
    n = 0
    for d in dirs:
        p = os.path.join(vault, d)
        if not os.path.isdir(p):
            continue
        for f in md_files(p):
            rel_dir = os.path.dirname(f)[len(vault):]
            if "\\_" in rel_dir or "/_" in rel_dir:
                continue
            n += 1
            name = os.path.basename(f)
            stem = name[:-3]
            txt = read(f)
            if not (txt and txt.startswith("---")):
                no_fm.append(name)
            if d not in exempt and not re.search(r"\[\[" + re.escape(stem) + r"[\]|#]", moc_text, re.I):
                no_moc.append(name)
            if txt:
                fm = txt.split("\n---", 1)[0]
                for ln in fm.split("\n"):
                    if LINKS.match(ln) and "[[" in ln and '"[[' not in ln:
                        bad_links.append(name)
                        break
    all_md = md_files(os.path.join(vault, "2_지식")) + md_files(os.path.join(vault, "3_시스템", "_ref"))
    seen, first = {}, {}
    for f in all_md:
        b = os.path.basename(f)[:-3]
        k = b.casefold()                                  # Group-Object BaseName 은 대소문자를 가리지 않는다
        seen[k] = seen.get(k, 0) + 1
        first.setdefault(k, b)                            # 묶음 이름 = 처음 나온 이름(PS 와 같음)
    dup = [first[k] for k in first if seen[k] > 1]        # 묶음 차례 = 처음 나온 차례(Group-Object 와 같음 · 11-06 대조 5c)
    math = []
    for f in all_md:
        txt = read(f)
        if not txt:
            continue
        prev = False
        hits = 0
        for ln in LINES.split(txt):
            dd = bool(DD.match(ln))
            if dd and prev:
                hits += 1
            prev = dd
        if hits:
            math.append("{}({})".format(os.path.basename(f), hits))
    return (no_fm, no_moc, dup, bad_links, math), time.perf_counter() - t0, n + len(all_md), rj


def main():
    check_only = "--check-only" in sys.argv
    vault = sys.argv[sys.argv.index("--vault") + 1] if "--vault" in sys.argv else \
        os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="")
    except Exception:
        pass
    if "--commit-only" in sys.argv:                # 서버(11-12) — 검사·가드·받은함 없이 커밋만 · 잠금이 있으면 건너뜀(커밋이 도는 중)
        hlog = os.path.join(vault, "3_시스템", "_index", "hooks.log")
        res = "잠금" if os.path.exists(os.path.join(vault, ".git", "index.lock")) else autocommit(vault, hlog, "서버")
        sys.stdout.write(json.dumps({"result": res}, ensure_ascii=False))
        return 0
    inp = {}
    if not check_only:
        try:
            inp = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
        except Exception:
            inp = {}
        if not isinstance(inp, dict):
            inp = {}
        if inp.get("stop_hook_active"):
            return 0
    idx = os.path.join(vault, "3_시스템", "_index")
    guard = os.path.join(idx, ".stopcheck-guard")
    hlog = os.path.join(idx, "hooks.log")
    try:
        res = check(vault)
    except Exception as e:
        if check_only:
            return 0
        # 검사를 못 해도 커밋은 한다 — 검사 실패가 자동 커밋까지 조용히 멈추면 안 된다(08-02·09-19·09-28 커밋 멎음 사고들의 결)
        log(hlog, "stop-check 검사 못 함({}: {}) — 커밋만 함".format(type(e).__name__, str(e)[:80]))
        res = (([], [], [], [], []), 0.0, 0, None)
    if res is None:
        return 0                                   # MOC 없음(초기 상태) = 통과(PS 판과 같음)
    (no_fm, no_moc, dup, bad_links, math), secs, nfiles, rj = res
    if check_only:
        print(json.dumps({"secs": round(secs, 3), "files": nfiles, "noFm": no_fm, "noMoc": no_moc, "dup": dup,
                          "badLinks": bad_links, "math": math}, ensure_ascii=False))
        return 0
    if rj is None:
        try:
            rj = json.load(open(os.path.join(vault, "3_시스템", "roles.json"), encoding="utf-8-sig"))
        except Exception:
            rj = {}
    if not (no_fm or no_moc or dup or bad_links or math):
        try:
            os.remove(guard)
        except OSError:
            pass
        # 죽은 잠금 — 10분 넘은 빈 잠금 + 도는 git 없음일 때만 옮긴다(지우지 않음)
        for ln in ("index.lock", "AUTO_MERGE.lock"):
            lk = os.path.join(vault, ".git", ln)
            try:
                s = os.stat(lk)
            except OSError:
                continue
            if s.st_size == 0 and time.time() - s.st_mtime >= 600:
                try:
                    tl = subprocess.run(["tasklist", "/FI", "IMAGENAME eq git.exe", "/NH"], capture_output=True,
                                        creationflags=NOWIN, timeout=60).stdout.decode("utf-8", "replace").lower()
                except (OSError, subprocess.SubprocessError):
                    tl = "git.exe"                 # 못 보면 «도는 git 있음»으로 — 잠금을 옮기지 않는다
                if "git.exe" not in tl:
                    try:
                        os.replace(lk, lk + ".stale-" + time.strftime("%Y%m%d%H%M%S"))
                        log(hlog, "stop-check 죽은 잠금 격리: " + ln)
                    except OSError:
                        pass
        # 기능 단계 «자동 커밋» 하옵 = 마지막 커밋 뒤 몇 분 안이면 이번 턴은 status·커밋을 건너뜀(세션 끝 훅이 몰아서 남김)
        if not commit_later(vault):
            autocommit(vault, hlog)                # 커밋 순서·장부 줄은 함수로 옮기기 전과 같다(서버도 같은 함수 · 11-12)
        # 받은함 되먹임 — 이 세션 도구 호출이 건드린 받은함 항목이 남았으면 항목당 세션 한 번
        ib_role = (rj.get("roles") or {}).get("inbox")
        try:
            ib = [e.name for e in os.scandir(os.path.join(vault, ib_role.replace("/", "\\")))
                  if not e.name.startswith((".", "_"))] if ib_role else []
        except OSError:
            ib = []
        sid, tp = inp.get("session_id"), inp.get("transcript_path")
        if ib and sid and tp and os.path.exists(tp):
            leaf = ib_role.split("/")[-1]
            nudged = os.path.join(idx, ".inbox-nudged")
            try:
                seen = set(x.lower() for x in open(nudged, encoding="utf-8-sig").read().splitlines())
            except OSError:
                seen = set()
            left = []
            with open(tp, encoding="utf-8", errors="replace") as fh:
                for l in fh:
                    if '"tool_use"' not in l:
                        continue
                    for nm in ib:                  # PS 의 -notcontains 는 대소문자를 가리지 않는다 · .Contains 는 가린다
                        if nm.lower() not in (x.lower() for x in left) and "{}\t{}".format(sid, nm).lower() not in seen and \
                                ("{}/{}".format(leaf, nm) in l or "{}\\\\{}".format(leaf, nm) in l):
                            left.append(nm)
            if left:
                os.makedirs(idx, exist_ok=True)
                with open(nudged, "a", encoding="utf-8", newline="") as f:
                    for nm in left:
                        f.write("{}\t{}\r\n".format(sid, nm))
                reason = ("받은함 항목을 확인하고 그대로 둠: " + ", ".join(left) + " → 필요한 곳으로 옮겨 받은함을 비운다"
                          "(py -3 3_시스템/inbox.py --take <이름> <자리> · --do <이름>). 작업에 쓰는 재료면 작업 폴더로 옮긴 뒤 "
                          "그 경로를 쓴다. 애매하면 사용자에게 묻는다.")
                sys.stdout.write(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
        return 0
    # 순환 서킷브레이커 — 같은 위반 집합으로 두 번 막았으면 풀고 기록
    os.makedirs(idx, exist_ok=True)
    sig = ",".join(no_moc) + "||" + ",".join(no_fm) + "||" + ",".join(dup) + "||" + ",".join(bad_links) + "||" + ",".join(math)
    h = hashlib.sha1(sig.encode("utf-8")).hexdigest().upper()
    count = 0
    try:
        prev = open(guard, encoding="ascii").read().strip().split("|")
        if len(prev) >= 2 and prev[0] == h:
            count = int(prev[1])
    except (OSError, ValueError):
        pass
    if count >= 2:
        log(hlog, "stop-check 순환차단 해제 — 미해결 위반 잔존: MOC[{}] FM[{}] LINKS[{}] MATH[{}]".format(
            ",".join(no_moc), ",".join(no_fm), ",".join(bad_links), ",".join(math)))
        try:
            os.remove(guard)
        except OSError:
            pass
        return 0
    try:
        open(guard, "w", encoding="ascii").write("{}|{}\r\n".format(h, count + 1))
    except OSError:
        pass
    parts = []
    if no_moc:
        parts.append("MOC.md 미등재: " + ", ".join(no_moc) + " → 2_지식/MOC.md의 그 영역(##)·주제(###) 칸에 [[파일명]] 150자 이하 한 줄로 등재(세션로그·_ref·_접두 하위폴더는 대상 아님)")
    if no_fm:
        parts.append("프론트매터 누락(선두 '---' 없음): " + ", ".join(no_fm) + " → 3_시스템/conventions.md 스키마로 추가")
    if dup:
        parts.append("중복 파일명(위키링크 [[name]] 모호): " + ", ".join(dup) + " → 하나를 고유 basename으로 개명")
    if bad_links:
        parts.append("links 프론트매터 깨짐(무따옴표 위키링크=YAML 파싱오류): " + ", ".join(bad_links) + ' → 따옴표 배열(links: ["[[노트명]]"])로')
    if math:
        parts.append("블록수식 연속(Obsidian서 수식이 날것 노출 — 깨짐): " + ", ".join(math) + " → 연속된 $$…$$ 사이에 빈 줄(괄호 안 숫자=위반 건수)")
    sys.stdout.write(json.dumps({"decision": "block", "reason": "규약 위반 — 종료 전 조치 필요.\n" + "\n".join(parts)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
