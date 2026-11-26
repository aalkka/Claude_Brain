#!/usr/bin/env python3
"""출시 때 한 번 «개인 맥락 읽기» — push 될 diff 의 더한 줄을 Claude 가 읽고 꼴로 못 잡는 개인 맥락을 줄 단위로 표시한다(11-22).

  py -3 .claude/skills/dist-sync/scripts/context_read.py                 # 배포판 worktree: 원격 짝..HEAD + 커밋 안 한 고침
  py -3 .claude/skills/dist-sync/scripts/context_read.py --range A..B    # 커밋 범위
  py -3 .claude/skills/dist-sync/scripts/context_read.py --diff <파일>    # 만든 diff(시험)
  py -3 .claude/skills/dist-sync/scripts/context_read.py --dry           # 읽을 줄 수·글자 수만(부르지 않음 · 사용량 0)
  옵션: --model sonnet(기본 · 별칭만) · --out <md> · --json

- 사용량이 드는 대본이다 — publish 절차의 «push 전» 한 단계에서만 부른다(자동 예약·건강 줄에서 부르지 않음).
- 읽는 줄 = 더한 줄 가운데 한글이 든 줄(설명·주석·글) · 동봉 플러그인 번들(.obsidian/plugins/*/*.js·css)과 판 해시 표는 뺀다(꼴 검사 몫 · dist-diff scan_leaks).
- 결과 = «사람 확인 목록»(md) — 표시만 하고 고치지 않는다. 고칠지·문구는 사람이 정한다.
- 모델은 별칭(opus·sonnet·haiku)만 받는다 — ID 를 박으면 새 모델이 나와도 옛 판에 묶인다. 실행 파일·구독 확인 = 3_시스템/claude_bin.py.
- 볼트 밖 임시 폴더에서 부른다(볼트 훅·볼트 지시문이 끼지 않게) · 도구 0 · 프롬프트 캐시 끔(덩이마다 본문이 다름).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(VAULT, "3_시스템"))
OUT_DIR = os.path.join(VAULT, "3_시스템", "_index", "dist-sync")  # mf:allow-path  (확인 목록 · 개인 층)
SKIP = re.compile(r"^\.obsidian/plugins/[^/]+/[^/]+\.(js|mjs|css)$|known-hashes\.json$|\.min\.(js|css)$")
HANGUL = re.compile(r"[가-힣]")
ALIASES = ("opus", "sonnet", "haiku")
CHUNK = 350           # 덩이 하나의 줄 수(한 줄 평균 ~90자 → ~3만 자)
TIMEOUT = 600
KINDS = ("사람 말 인용", "일정", "과목·학교", "사람 이름", "기기·장소", "개인 사정")

SYSTEM = """너는 공개 배포판에 실릴 변경 줄을 검토한다. 이 배포판은 한 사람(제작자)이 자기 개인 지식 시스템에서 떼어 내 남에게 나눠 주는 범용 도구다.
줄마다 «제작자 개인 맥락이 남에게 드러나는가»를 본다. 드러나면 표시한다. 고치지 않는다.

표시할 종류(kind) — 이 여섯 가운데 하나:
- 사람 말 인용: 제작자(또는 «사용자»·«<이름>님» 같은 호칭으로 가린 사람)가 한 말을 따옴표(«…»·"…")로 옮긴 것. 호칭을 «사용자»로 바꿨어도 말 자체가 그 사람의 말이면 표시.
- 일정: 제작자 삶의 일정(시험·면접·제출 마감·수업·알바·여행·약속 날짜). 개발 기록의 날짜(«11-20 잼», «(11-18)», 판 번호)는 표시하지 않는다.
- 과목·학교: 듣는 과목·학교·학과·캠퍼스·교수·강의실 이름이나 줄임말, 학교 게시판·포털 이름.
- 사람 이름: 실명·별명·가족·친구·교수 이름.
- 기기·장소: 제작자 기기의 구체 이름(«내 폰», «<이름>의 탭», PC 이름·모델과 그 사람 소유 표시)·집·동네·가게·Wi-Fi 이름.
- 개인 사정: 건강·돈·일자리·가족·진로·성적·학적 같은 그 사람 사정.

표시하지 않을 것: 범용 설명, 코드, 가짜 예시 값(과목A·example.com·x 같은 자리표), 제품·꾸러미·남의 회사 이름, «제작자 볼트에서 잰 값» 같은 익명 설명, 개발 날짜.
애매하면 표시하되 why 에 «애매»를 붙인다.

답은 JSON 배열 하나만: [{"id": 줄 번호, "kind": "종류", "why": "20자 안팎 까닭"}] · 없으면 [] · 다른 말 금지."""


def git(root, *args, timeout=60):
    r = subprocess.run(["git", "-C", root, "-c", "core.quotepath=off", *args], capture_output=True, timeout=timeout,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode, r.stdout.decode("utf-8", "replace")


def find_dist():
    code, out = git(VAULT, "worktree", "list", "--porcelain")
    path = None
    for ln in out.splitlines():
        if ln.startswith("worktree "):
            path = ln[9:].strip()
        elif ln.strip() == "branch refs/heads/dist-sync":
            return path
    return None


def added_lines(diff):
    """unified diff → [(경로, 새 줄 번호, 글)] — 읽을 줄만(더한 줄 · 한글 · 번들·판 해시 표 빼고)."""
    out, cur, n = [], None, 0
    for ln in diff.splitlines():
        if ln.startswith("+++ "):
            p = ln[4:].strip()
            cur = None if p == "/dev/null" else (p[2:] if p.startswith("b/") else p)
            continue
        if ln.startswith("@@"):
            m = re.search(r"\+(\d+)", ln)
            n = int(m.group(1)) if m else 0
            continue
        if cur is None or ln.startswith("---"):
            continue
        if ln.startswith("+"):
            t = ln[1:]
            if not SKIP.search(cur) and HANGUL.search(t):
                out.append((cur, n, t.strip()[:400]))
            n += 1
        elif not ln.startswith("-") and not ln.startswith("\\"):
            n += 1
    return out


def collect(args):
    if args.diff:
        with open(args.diff, encoding="utf-8", errors="replace") as f:
            return f.read(), args.diff
    B = args.b or find_dist()
    if not B:
        raise SystemExit("배포판 worktree 없음(dist-sync 가지)")
    if args.range:
        _, d = git(B, "diff", "--unified=0", args.range)
        return d, "%s %s" % (B, args.range)
    code, up = git(B, "rev-parse", "--abbrev-ref", "@{upstream}")
    up = up.strip() if code == 0 else None
    _, d1 = git(B, "diff", "--unified=0", "%s..HEAD" % up) if up else (0, "")
    _, d2 = git(B, "diff", "--unified=0", "HEAD")
    return d1 + "\n" + d2, "%s %s..HEAD + 커밋 안 한 고침" % (B, up or "(짝 없음)")


def run_claude(model, text):
    """claude -p 한 번 → (답 글, {in, out, cost}, 오류 글)."""
    import claude_bin
    why = claude_bin.subscription()
    if why:
        return "", {}, "멈춤: " + why
    cmd = [claude_bin.newest(), "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
           "--model", model, "--effort", "low", "--tools", "", "--system-prompt", SYSTEM, "--strict-mcp-config",
           "--setting-sources", "user", "--settings", '{"alwaysThinkingEnabled":false}', "--no-session-persistence", "--disable-slash-commands"]
    payload = (json.dumps({"type": "user", "message": {"role": "user", "content": text}}, ensure_ascii=False) + "\n").encode("utf-8")
    with tempfile.TemporaryDirectory(prefix="context-read-") as cwd:
        try:
            r = subprocess.run(cmd, cwd=cwd, input=payload, capture_output=True, timeout=TIMEOUT,
                               env=dict(os.environ, DISABLE_PROMPT_CACHING="1"), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except subprocess.TimeoutExpired:
            return "", {}, "시간 초과 %ds" % TIMEOUT
    out, usage, err, source, kind = "", {}, "", None, ""
    for ln in r.stdout.decode("utf-8", "replace").splitlines():
        try:
            d = json.loads(ln) if ln.startswith("{") else None
        except ValueError:
            d = None
        if not d:
            continue
        if d.get("type") == "system" and d.get("subtype") == "init":
            source = d.get("apiKeySource")
        elif d.get("type") == "assistant" and d.get("error"):
            kind = str(d["error"])
        elif d.get("type") == "result":
            out = d.get("result") or ""
            u = d.get("usage") or {}
            usage = {"in": u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0),
                     "out": u.get("output_tokens", 0), "cost": d.get("total_cost_usd") or 0.0, "model": ",".join((d.get("modelUsage") or {}).keys())}
            if d.get("is_error"):
                err = str(d.get("api_error_status") or d.get("result") or "is_error")
    if source not in (None, "none"):
        return "", usage, "구독 아님(apiKeySource=%s) — 멈춤" % source
    failed = bool(kind or err or not out)
    claude_bin.note_call(not failed, kind, (err or out or r.stderr.decode("utf-8", "replace")[-300:]) if failed else "", err)
    if failed and not err:
        err = kind or (r.stderr.decode("utf-8", "replace").strip()[-300:] or "빈 답")
    return out, usage, err


def parse(text, n):
    t = text.strip()
    arr = None
    for i in [m.start() for m in re.finditer(r"\[", t)][:5]:     # 첫 배열을 그 자리에서 읽는다(뒤에 말·배열이 더 붙어도 · 11-22 sonnet 덩이 하나를 «JSON 아님»으로 버림)
        try:
            arr = json.JSONDecoder().raw_decode(t[i:])[0]
            break
        except ValueError:
            continue
    if not isinstance(arr, list):
        return None
    out = []
    for x in arr if isinstance(arr, list) else []:
        if isinstance(x, dict) and isinstance(x.get("id"), int) and 1 <= x["id"] <= n:
            out.append({"id": x["id"], "kind": str(x.get("kind") or "?")[:12], "why": str(x.get("why") or "")[:60]})
    return out


def read(lines, model, log=print):
    """[(경로, 줄, 글)] → (표시 [{path, line, text, kind, why}], 합계 {calls, in, out, cost, secs, errors})."""
    marks, tot = [], {"calls": 0, "in": 0, "out": 0, "cost": 0.0, "secs": 0.0, "errors": [], "model": ""}
    t0 = time.time()
    for s in range(0, len(lines), CHUNK):
        part = lines[s:s + CHUNK]
        body = "\n".join("%d\t%s:%d\t%s" % (i, p, ln, t) for i, (p, ln, t) in enumerate(part, 1))
        text, usage, err = run_claude(model, "줄 번호<TAB>자리<TAB>글 — 아래 %d줄을 검토한다.\n\n%s" % (len(part), body))
        tot["calls"] += 1
        for k in ("in", "out", "cost"):
            tot[k] += usage.get(k) or 0
        tot["model"] = usage.get("model") or tot["model"]
        got = None if err else parse(text, len(part))
        if got is None:
            tot["errors"].append("덩이 %d: %s" % (s // CHUNK + 1, (err or "JSON 아님: " + text[:120])[:200]))
            if err.startswith(("멈춤", "구독 아님")):
                break
            continue
        seen = {}
        for x in got:                       # 한 줄에 종류 여럿을 달면 하나로(첫 종류 · 까닭은 잇는다 · 11-22 haiku 견본 10줄에 16표시)
            if x["id"] in seen:
                seen[x["id"]]["why"] = (seen[x["id"]]["why"] + " / " + x["kind"])[:80]
                continue
            p, ln, t = part[x["id"] - 1]
            seen[x["id"]] = {"path": p, "line": ln, "text": t, "kind": x["kind"], "why": x["why"]}
        got = list(seen.values())
        marks += got
        log("  덩이 %d/%d · 표시 %d · $%.4f" % (s // CHUNK + 1, (len(lines) + CHUNK - 1) // CHUNK, len(got), usage.get("cost") or 0))
    tot["secs"] = round(time.time() - t0, 1)
    return marks, tot


def report(src, lines, marks, tot):
    L = ["# 사람 확인 목록 — 출시 전 개인 맥락 읽기", "",
         "- 잰 때 %s · 자리 %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), src),
         "- 읽은 줄 %d(더한 줄 · 한글 · 번들 뺌) · 부름 %d · 모델 %s · 입력 %d · 출력 %d 토큰 · $%.4f · %.1f초"
         % (len(lines), tot["calls"], tot["model"] or "?", tot["in"], tot["out"], tot["cost"], tot["secs"]),
         "- 표시만 했다 — 고칠지·문구는 사람이 정한다. 꼴 검사(dist-check ⑨⑩)가 잡는 값은 여기서 또 세지 않을 수 있다.", ""]
    if tot["errors"]:
        L += ["## 못 읽은 덩이 %d" % len(tot["errors"]), ""] + ["- " + e for e in tot["errors"]] + [""]
    by = {}
    for m in marks:
        by.setdefault(m["kind"], []).append(m)
    L.append("## 표시 %d줄" % len(marks))
    for k in sorted(by, key=lambda k: (KINDS.index(k) if k in KINDS else 99, k)):
        L += ["", "### %s — %d" % (k, len(by[k]))]
        L += ["- [ ] `%s:%d` — %s · %s" % (m["path"], m["line"], m["why"], m["text"][:120].replace("`", "'")) for m in by[k]]
    return "\n".join(L) + "\n"


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="출시 전 개인 맥락 읽기(사용량 듦 · 출시 때만)")
    ap.add_argument("--b", help="배포판 worktree(기본 = dist-sync 가지)")
    ap.add_argument("--range", help="커밋 범위 A..B")
    ap.add_argument("--diff", help="diff 파일")
    ap.add_argument("--model", default="sonnet", choices=ALIASES)
    ap.add_argument("--out", help="확인 목록 md(기본 = 3_시스템/_index/dist-sync/context-<날짜>.md)")
    ap.add_argument("--dry", action="store_true", help="읽을 줄만 세고 부르지 않음")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    diff, src = collect(a)
    lines = added_lines(diff)
    chars = sum(len(t) for _, _, t in lines)
    if a.dry or not lines:
        print("읽을 줄 %d · 글자 %d · 덩이 %d%s" % (len(lines), chars, (len(lines) + CHUNK - 1) // CHUNK, "" if lines else " — 부를 것 없음"))
        return 0
    print("읽을 줄 %d · 글자 %d · 모델 %s" % (len(lines), chars, a.model))
    marks, tot = read(lines, a.model)
    md = report(src, lines, marks, tot)
    out = a.out or os.path.join(OUT_DIR, "context-%s.md" % datetime.datetime.now().strftime("%Y-%m-%d-%H%M"))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(md)
    if a.json:
        print(json.dumps({"marks": marks, "total": tot, "lines": len(lines)}, ensure_ascii=False, indent=1))
    print("표시 %d · 부름 %d · $%.4f · %.1f초 · 목록 %s" % (len(marks), tot["calls"], tot["cost"], tot["secs"], out))
    return 2 if tot["errors"] else (1 if marks else 0)


if __name__ == "__main__":
    sys.exit(main())
