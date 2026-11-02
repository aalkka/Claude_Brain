"""md 표 깨짐 검사·고치기 — 옵시디언에서 표가 깨지는 원인을 찾아 줄 단위로 보고한다.

사용:
  py -3 3_시스템/mdtable.py check [경로...]        # 기본 = 볼트 전체(.obsidian·.git·_색인 제외) · 원인별 개수 + 예
  py -3 3_시스템/mdtable.py check --all            # _색인 포함
  py -3 3_시스템/mdtable.py fix <파일·폴더...> [--dry]  # 고칠 수 있는 원인만 그 자리에서 고침
  py -3 3_시스템/mdtable.py hook                   # PostToolUse(Write|Edit) 훅 — 방금 쓴 md 를 고침(.claude/settings.json)

원인(2026-11-01 격리 옵시디언 1.14.5 실측 — 읽기 화면 / 실시간 미리 보기):
  no-blank   표 바로 윗줄이 글·목록(빈 줄 아님) → 두 화면 모두 표를 안 그리고 | 글자로 둠   (fix: 빈 줄 넣기)
             제목(#) 바로 아래는 표로 그림 → 문제 아님
  pipe-link  [[노트|별칭]]·![[그림|300]] 의 | → 읽기는 정상 · 실시간에서 칸이 하나 더 생김  (fix: \\| )
  pipe-code  `a|b` 코드 안 |   → 읽기는 정상 · 실시간에서 칸이 쪼개짐                 (fix: \\| — 코드 안에 \\ 가 보임)
  pipe-math  $|x|$ 수식 안 |    → 읽기는 정상 · 실시간에서 칸이 쪼개짐                 (fix: \\vert )
  cols       칸 수가 머리 줄과 다름(위 원인 아닌 것)
             넘침 → 옵시디언이 넘친 칸을 버려 내용이 사라짐  (fix: 글 속 |Δ| 막기 · 남는 칸은 마지막 칸에 « · » 로)
             모자람 → 옵시디언이 빈 칸으로 채움(머리와 어긋났으면 손으로)                 (보고만)
fix 는 1_수집/(원본 층)·3_시스템/_index/(기계 파생물)을 건드리지 않는다.
"""
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".obsidian", ".git", ".trash", "node_modules", ".claude"}
SEP_RE = re.compile(r"^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$")


def is_row(line: str) -> bool:
    s = line.strip()
    return s.startswith("|") or (s.count("|") >= 1 and SEP_RE.match(s) is not None)


def protected_spans(line: str):
    """[[..]] · `..` · $..$ 구간 [(시작, 끝, 종류)] — 그 안의 | 는 글쓴이가 칸 나누기로 쓴 것이 아니다"""
    spans = []
    for m in re.finditer(r"!?\[\[[^\]]*\]\]", line):
        spans.append((m.start(), m.end(), "link"))
    for m in re.finditer(r"(`+)(.+?)\1", line):
        spans.append((m.start(), m.end(), "code"))
    for m in re.finditer(r"(?<![\\$])\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\d)", line):
        spans.append((m.start(), m.end(), "math"))
    return spans


def raw_pipes(line: str):
    """GFM 이 칸 나누기로 보는 | 자리(역슬래시로 막지 않은 것)"""
    out = []
    i = 0
    while i < len(line):
        c = line[i]
        if c == "\\":
            i += 2
            continue
        if c == "|":
            out.append(i)
        i += 1
    return out


def cells(line: str, pipes) -> int:
    s = line.strip()
    n = len(pipes) + 1
    if s.startswith("|"):
        n -= 1
    if s.endswith("|") and not s.endswith("\\|"):
        n -= 1
    return n


def in_code_fence(lines):
    """줄마다 코드 울타리 안인가"""
    inside = False
    out = []
    for l in lines:
        if re.match(r"^\s*(```|~~~)", l):
            out.append(True)
            inside = not inside
            continue
        out.append(inside)
    return out


def scan(text: str):
    """표마다 문제 [(줄 번호, 원인, 줄 글)]"""
    lines = text.split("\n")
    fence = in_code_fence(lines)
    probs = []
    i = 0
    # 앞머리(프론트매터)는 건너뜀
    if lines and lines[0].strip() == "---":
        for k in range(1, len(lines)):
            if lines[k].strip() == "---":
                i = k + 1
                break
    while i < len(lines) - 1:
        if fence[i] or not is_row(lines[i]) or not SEP_RE.match(lines[i + 1].strip()) or fence[i + 1]:
            i += 1
            continue
        head = i
        j = i + 2
        while j < len(lines) and not fence[j] and lines[j].strip() and "|" in lines[j]:
            j += 1
        prev = lines[head - 1] if head > 0 else ""
        if head > 0 and prev.strip() and not re.match(r"^\s*(>|#{1,6}\s|(---|___|\*\*\*)\s*$)", prev):
            # 머리 줄 바로 위가 글·목록 → 옵시디언이 읽기·실시간 미리 보기 모두 표 대신 글자로 둔다(11-01 실측 · 제목 바로 아래는 표로 그림)
            probs.append((head + 1, "no-blank", prev))
        want = cells(lines[head + 1], raw_pipes(lines[head + 1]))
        for k in range(head, j):
            if k == head + 1:
                continue
            l = lines[k]
            ps = raw_pipes(l)
            spans = protected_spans(l)
            bad = {}
            for p in ps:
                for a, b, kind in spans:
                    if a < p < b:
                        bad[kind] = bad.get(kind, 0) + 1
                        break
            for kind in bad:
                probs.append((k + 1, "pipe-" + kind, l))
            if not bad and cells(l, ps) != want:
                probs.append((k + 1, "cols", l))
        i = j
    return probs


def header_cells(lines, k: int) -> int:
    """k 줄이 속한 표의 머리 칸 수(구분 줄 기준)"""
    while k > 0 and not SEP_RE.match(lines[k].strip()):
        k -= 1
    return cells(lines[k], raw_pipes(lines[k]))


def fix_cols(l: str, want: int) -> str:
    """머리보다 칸이 많은 줄 — ①글 속 절댓값 |Δ| 의 | 를 막고 ②그래도 넘치는 칸은 마지막 칸에 « · » 로 붙인다
    (옵시디언은 넘치는 칸을 버려 그 내용이 화면에서 사라진다 — 덧붙인 내용이 새 칸으로 들어간 줄)"""
    l = re.sub(r"(?<=\s)\|([^\s|]{1,8})\|(?=\s)", r"\\|\1\\|", l)
    ps = raw_pipes(l)
    if cells(l, ps) <= want:
        return l
    s = l.rstrip()
    lead = 1 if s.lstrip().startswith("|") else 0
    inner = ps[lead:]  # 칸 사이 | 들(맨 끝 | 포함일 수 있음)
    # want 번째 칸 뒤의 칸 나누기들을 « · » 로
    cut = inner[want - 1 :]
    if s.endswith("|"):
        cut = cut[:-1]
    out = l
    for p in reversed(cut):
        out = out[:p].rstrip() + " · " + out[p + 1 :].lstrip()
    out = re.sub(r"·\s+·", "·", out)  # 붙인 칸이 « · » 로 시작했으면 겹친 점 하나로
    return out


def fix_text(text: str, merge: bool = True, left: list | None = None):
    """merge=False(훅) — 넘친 칸 합치기는 하지 않고 그 줄 번호를 left 에 담는다: 넘친 | 가 줄 끝 덧붙임인지
    칸 가운데 실수인지 기계가 가를 수 없다(11-01 실측: 가운데 | 를 끝 칸에 합쳐 «30곳» 이 옆 칸으로 밀림)"""
    lines = text.split("\n")
    probs = scan(text)
    changed = 0
    blank_before = set()
    for ln, kind, _ in probs:
        k = ln - 1
        l = lines[k]
        if kind == "no-blank":
            blank_before.add(k)
            continue
        if kind == "cols":
            want = header_cells(lines, k)
            if cells(l, raw_pipes(l)) > want:
                if not merge:
                    if left is not None:
                        left.append(ln)
                    continue
                nl = fix_cols(l, want)
                if nl != l:
                    lines[k] = nl
                    changed += 1
            continue
        if kind not in ("pipe-link", "pipe-code", "pipe-math"):
            continue
        spans = [s for s in protected_spans(l) if "pipe-" + s[2] == kind]
        out = []
        last = 0
        for a, b, sk in sorted(spans):
            seg = l[a:b]
            if sk == "math":
                new = re.sub(r"(?<!\\)\|", r"\\vert ", seg)
            else:
                new = re.sub(r"(?<!\\)\|", r"\\|", seg)
            out.append(l[last:a] + new)
            last = b
        out.append(l[last:])
        nl = "".join(out)
        if nl != l:
            lines[k] = nl
            changed += 1
    for k in sorted(blank_before, reverse=True):
        lines.insert(k, "\r" if lines[k - 1].endswith("\r") else "")  # CRLF 파일은 CRLF 빈 줄
        changed += 1
    return "\n".join(lines), changed


def files(args, include_index: bool):
    roots = [Path(a) for a in args] or [VAULT]
    for r in roots:
        r = r if r.is_absolute() else VAULT / r
        if r.is_file():
            yield r
            continue
        for p in r.rglob("*.md"):
            rel = p.relative_to(VAULT).parts
            if any(d in SKIP_DIRS for d in rel):
                continue
            if not include_index and rel[:2] == ("1_수집", "_색인"):
                continue
            yield p


def fixable(p: Path) -> bool:
    try:
        rel = p.resolve().relative_to(VAULT).parts
    except ValueError:
        return False
    return p.suffix == ".md" and rel[:1] != ("1_수집",) and rel[:2] != ("3_시스템", "_index") and not any(d in SKIP_DIRS for d in rel)


def limit_msgs(p: Path) -> list:
    """상시로 읽히는 파일(기억 색인·MOC·recent·open-loops·CLAUDE.md)이 상한을 넘으면 쓰는 순간 알린다.
    드물게 점검해서는 808자 줄·188k MOC 가 될 때까지 몰랐다(11-02). 훅을 새로 달지 않으려고 여기서 함께 잰다."""
    if p.suffix != ".md":
        return []
    try:
        import drift
        return [f"상한: {w} — {t}. 줄여라(이력은 본문으로)." for _, w, t in drift.limits_of(str(p))][:5]
    except Exception:
        return []


def hook() -> int:
    """PostToolUse(Write|Edit) — 방금 쓴 md 의 표를 그 자리에서 고친다(Claude 가 «설명:» 바로 아래 표를 쓰는 버릇의 재발 막기).
    고쳤으면 Claude 에게 알린다(다시 Edit 하려면 Read 먼저). 실패해도 도구 결과를 막지 않는다."""
    import json

    try:
        data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
        fp = (data.get("tool_input") or {}).get("file_path") or ""
        p = Path(fp)
        if not fp or not p.is_file():
            return 0
        msg = limit_msgs(p)
        if fixable(p):
            t = p.read_text(encoding="utf-8")
            left: list = []
            nt, n = fix_text(t, merge=False, left=left)
            if n:
                p.write_text(nt, encoding="utf-8", newline="")
                msg.append(f"mdtable: {p.name} 의 md 표 {n}곳을 고쳤다(표 위 빈 줄 · 칸 안 | 막기). 이 파일을 다시 Edit 하려면 먼저 Read.")
            if left:
                # 고친 뒤 줄 번호(빈 줄을 넣었으면 밀림) — 고친 글에서 다시 잰다
                left2: list = []
                fix_text(nt, merge=False, left=left2)
                msg.append(f"mdtable: {p.name} 줄 {', '.join(map(str, left2 or left))} 이 머리보다 칸이 많다 — 옵시디언은 넘친 칸을 버린다. 글 속 | 는 \\| 로 막거나 칸을 합쳐라.")
        if not msg:
            return 0
        msg = " ".join(msg)
        sys.stdout.buffer.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}, ensure_ascii=False).encode("utf-8"))
    except Exception:
        pass
    return 0


def main():
    argv = sys.argv[1:]
    if argv[:1] == ["hook"]:
        return hook()
    if not argv or argv[0] not in ("check", "fix"):
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    include_index = "--all" in rest
    dry = "--dry" in rest
    paths = [a for a in rest if not a.startswith("--")]
    if cmd == "check":
        total = {}
        nfiles = 0
        ntables = 0
        examples = {}
        for p in files(paths, include_index):
            try:
                t = p.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            ntables += sum(1 for l in t.split("\n") if SEP_RE.match(l.strip()) and "-" in l)
            pr = scan(t)
            if not pr:
                continue
            nfiles += 1
            for ln, kind, l in pr:
                total[kind] = total.get(kind, 0) + 1
                examples.setdefault(kind, []).append(f"{p.relative_to(VAULT)}:{ln}  {l.strip()[:110]}")
        print(f"표 {ntables}개 · 문제 있는 파일 {nfiles}개")
        for kind, n in sorted(total.items(), key=lambda x: -x[1]):
            print(f"  {kind}: {n}")
            for e in examples[kind][:4]:
                print(f"     {e}")
        return 0
    if not paths:
        print("fix 는 파일을 적어야 합니다")
        return 2
    for p in files(paths, True):
        if not fixable(p):
            continue
        t = p.read_text(encoding="utf-8")
        nt, n = fix_text(t)
        if n:
            print(f"{'(미리 보기) ' if dry else ''}{p.relative_to(VAULT)}: {n}곳")
            if not dry:
                p.write_text(nt, encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
