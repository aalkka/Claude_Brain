#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dist-sync — 두 볼트의 코어 괴리를 층별로 진단한다 (P0: 읽기 전용).

  py -3 dist-diff.py --a <원본볼트> --b <대상볼트> --mode update|publish [--out <파일>]

**파일을 고치지 않는다.** 무엇이 다르고 무엇이 바뀔 것인지만 낸다.
적용은 P1 이후이고, 그때도 이 리포트가 입력이 된다.

층 분류 근거 → 제작자 볼트의 dist-sync 설계 노트(배포판 미포함).
module-forge 스캐폴드 보일러플레이트 ①~⑤는 실측 인시던트 대응이라 지우지 말 것.
"""
import sys, os, re, argparse, hashlib, fnmatch, datetime

# ① stdout/stderr UTF-8 강제 — Windows 콘솔 기본 cp949 → 한글 출력 시 크래시.
#    (incident-2026-07-04-search-stdout-cp949 계열)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# ② 플러그인 루트 = 이 파일 기준 상대. ${CLAUDE_PLUGIN_ROOT}와 동형(이식성).
HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.abspath(os.path.join(HERE, ".."))

# ── 층 분류. 위에서부터 먼저 맞는 것을 쓴다 ───────────────────────────────
# 개인: 읽지도 않는다. 목록조차 만들지 않는다.
PERSONAL = [
    "1_수집/*", "2_지식/notes/*", "2_지식/sessions/*", "2_지식/decisions/*",  # mf:allow-path
    "2_지식/modules/*", "2_지식/_canvas/*", "3_시스템/_index/*",  # mf:allow-path
    "3_시스템/_claude-memory/*", ".obsidian/*", ".git/*", "__pycache__/*",  # mf:allow-path
    # DoD 검증(2026-09-12)이 잡은 결함 — settings.local.json 은 개인 권한 설정이고
    # gitignore 대상인데 `.claude/skills/*` 형제라 코어로 분류됐다. 적용 단계였다면 유출.
    ".claude/settings.local.json", "_변환본/*",  # mf:allow-path
]
# 예외 — 개인 폴더 안이지만 제작자가 배포하는 것
PERSONAL_EXCEPT = ["2_지식/notes/설계노트.md", "2_지식/notes/사용자설명서.md"]  # mf:allow-path

# 씨앗: 머리말(제작자 규약) + 항목(사용자 데이터)이 한 파일에 섞여 있다.
SEED = [
    "2_지식/recent.md", "2_지식/open-loops.md", "2_지식/MOC.md",  # mf:allow-path
    "2_지식/profile.md", "3_시스템/config.json",  # mf:allow-path
    "2_지식/notes/설계노트.md", "2_지식/notes/사용자설명서.md",  # mf:allow-path
]
# CLAUDE.md 는 단독 층 — §0(개인) + 나머지(코어)가 한 파일이다.
# 경로 «세그먼트» 제외 — 글로브는 중첩 경로를 못 잡는다.
#   DoD 검증(2026-09-12)에서 `.claude/skills/*/scripts/__pycache__/*.pyc` 가 새어 들어왔고
#   worktree 의 `.git` 은 디렉터리가 아니라 **파일**이라 «지워질 파일» 목록에 올랐다.
#   적용 단계였다면 저장소를 지울 뻔했다.
EXCLUDE_SEG = {"__pycache__", ".git", ".obsidian", "_index", "_claude-memory", "node_modules"}
EXCLUDE_EXT = (".pyc", ".pyo", ".lock", ".tmp")

L_CLAUDE = "CLAUDE.md"  # mf:allow-path  (층 라벨 겸 경로 — 리터럴은 여기 한 곳뿐)
SPECIAL = [L_CLAUDE]

# 코어: 통째로 교체 가능
CORE = [
    ".claude/skills/*", ".claude/settings.json", ".claude/output-styles/*",  # mf:allow-path
    "3_시스템/hooks/*", "3_시스템/search.py", "3_시스템/session-stub.py",  # mf:allow-path
    "3_시스템/tokens.py", "3_시스템/conventions.md", "3_시스템/_ref/*",  # mf:allow-path
    "3_시스템/_eval/*", "README.md", ".gitattributes", ".gitignore",  # mf:allow-path
]

# publish 방향에서 배포판에 새어 나가면 안 되는 것 (2026-08-03 전수검사 계열)
# 실명·호칭·개인 저장소 이름은 여기 적지 않는다 — 이 스크립트도 배포되므로 패턴 자체가 샌다.
# 볼트마다 LEAK_LOCAL(gitignore)에 «정규식<TAB>이름» 을 한 줄씩 적는다. 없으면 리포트가 경고한다.
LEAK_LOCAL = os.path.join("3_시스템", "_index", "dist-sync", "leak-patterns.txt")
LEAK = [
    (r"[\w.+-]+@[\w-]+\.[\w.-]+", "이메일"),
    (r"C--[\w-]+", "Claude 프로젝트 폴더 이름"),
    (r"C:[\\/]Users[\\/][^\s\"')]+", "사용자 홈 경로"),
    (r"\b[0-9a-f]{8}\b(?![0-9a-f])", "세션 id 후보(⚠ PubMed·DOI 오탐 가능)"),
]
# 기계 치환이 깬 흔적 (2026-08-03 일괄치환이 남긴 `사용자이` 계열)
BROKEN = [r"사용자이\s", r"사용자은\s", r"사용자을\s", r"사용자가가", r"사용자이가"]


# ⚠ 위 목록 줄의 `mf:allow-path`는 **P0(읽기 전용)에서만 정당하다.**
#   check.py 의 I1 은 «언급»과 «접근»을 구분하지 못해 분류표를 코어 수정으로 읽는다.
#   check.py 자신도 같은 이유로 자기 CORE_PATHS 에 같은 escape 를 달았다.
#   ⛔ P1 에서 쓰기를 열면 이 escape 가 **진짜 위반을 가린다.** 그때는 escape 를 걷고
#      module-forge 가드레일과의 충돌을 정면으로 푼다(설계 미결).


def layer(rel):
    """경로 → 층. 제외가 가장 강하고, 그다음 개인, 예외가 개인보다 강하다."""
    p = rel.replace("\\", "/")
    segs = p.split("/")
    if EXCLUDE_SEG & set(segs) or p.endswith(EXCLUDE_EXT):
        return "제외"
    if p in PERSONAL_EXCEPT:
        return "씨앗"
    for g in PERSONAL:
        if fnmatch.fnmatch(p, g) or p.startswith(g.rstrip("*")):
            return "개인"
    if p in SPECIAL:
        return L_CLAUDE
    if p in SEED:
        return "씨앗"
    for g in CORE:
        if fnmatch.fnmatch(p, g) or p.startswith(g.rstrip("*")):
            return "코어"
    return "미분류"


def sha(path):
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            # 줄바꿈 차이를 괴리로 세지 않는다 — .gitattributes 가 LF 고정이라
            # CRLF 는 노이즈다(오늘 status 의 4건이 전부 이것이었다).
            h.update(f.read().replace(b"\r\n", b"\n"))
    except OSError:
        return None
    return h.hexdigest()[:12]


def walk(root):
    """개인 층은 들어가지도 않는다."""
    out = {}
    for dp, dns, fns in os.walk(root):
        rel_dir = os.path.relpath(dp, root).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        dns[:] = [d for d in dns
                  if layer((rel_dir + "/" + d).lstrip("/") + "/x") not in ("개인", "제외")]
        for fn in fns:
            rel = (rel_dir + "/" + fn).lstrip("/")
            if layer(rel) in ("개인", "제외"):
                continue
            out[rel] = os.path.join(dp, fn)
    return out


def scan_leaks(files):
    hits = []
    for rel, full in sorted(files.items()):
        if not re.search(r"\.(md|py|ps1|json|sh|tsv|txt)$", rel):
            continue
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    for rx, label in LEAK:
                        if re.search(rx, line):
                            hits.append((rel, i, label, line.strip()[:90]))
                            break
        except OSError:
            continue
    return hits


def scan_broken(files):
    hits = []
    for rel, full in sorted(files.items()):
        if not re.search(r"\.(md|py|ps1)$", rel):
            continue
        try:
            with open(full, encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    for rx in BROKEN:
                        if re.search(rx, line):
                            hits.append((rel, i, line.strip()[:90]))
                            break
        except OSError:
            continue
    return hits


def load_local_leaks(vault):
    """볼트 전용 패턴(실명·호칭·개인 저장소 이름). 파일이 없으면 None."""
    p = os.path.join(vault, LEAK_LOCAL)
    if not os.path.exists(p):
        return None
    out = []
    with open(p, encoding="utf-8") as f:
        for ln in f:
            ln = ln.rstrip("\n")
            if ln.strip() and not ln.startswith("#"):
                rx, _, label = ln.partition("\t")
                out.append((rx, label.strip() or "개인 패턴"))
    return out


def report(A, B, mode):
    fa, fb = walk(A), walk(B)
    added = sorted(set(fa) - set(fb))       # A 에만 = B 에 새로 들어갈 것
    # ⛔ B 에만 있는 것 ≠ «배포판이 지운 것». 대상 볼트가 스스로 만든 파일이 전부 여기 섞인다.
    #   실측(2026-09-12): 공통 조상 기준 0건인데 단순 집합차로는 51건이 나왔다.
    #   정확히 가르려면 공통 조상과의 3자 비교가 필요하다(P1 과제).
    removed = sorted(set(fb) - set(fa))
    common = sorted(set(fa) & set(fb))
    changed = [r for r in common if sha(fa[r]) != sha(fb[r])]

    L = []
    w = L.append
    w("# dist-sync 진단 — %s" % datetime.date.today())
    w("")
    w("- 방향: **%s**  (A=%s → B=%s)" % (mode, A, B))
    w("- A 추적 %d파일 · B 추적 %d파일 (개인 층은 열지 않았다)" % (len(fa), len(fb)))
    w("")
    w("## 층별 요약")
    w("")
    w("| 층 | 새로 들어감 | 내용 다름 | **지워짐** |")
    w("|---|---:|---:|---:|")
    for lay in ("코어", "씨앗", L_CLAUDE, "미분류"):
        w("| %s | %d | %d | %d |" % (
            lay,
            sum(1 for r in added if layer(r) == lay),
            sum(1 for r in changed if layer(r) == lay),
            sum(1 for r in removed if layer(r) == lay)))
    w("")

    if removed:
        w("## ⛔ 대상 볼트에만 있는 파일 — **지울 목록이 아니다**")
        w("")
        w("여기에는 두 가지가 섞여 있다 — ⑴배포판이 제거한 것 ⑵**대상 볼트가 스스로 만든 것.**")
        w("이 진단은 둘을 **구분하지 못한다**(공통 조상 3자 비교가 P1 과제).")
        w("실제로 지울 것은 git 으로 따로 뽑는다 — **설치 시점을 기준으로**:")
        w("")
        w("```bash")
        w("BASE=$(git merge-base HEAD dist/main) && git diff --name-status $BASE dist/main | grep '^D'")
        w("```")
        w("")
        for r in removed:
            w("- `%s`  (%s 층)" % (r, layer(r)))
        w("")

    for lay, note in (("코어", "통째 교체 가능"),
                      ("씨앗", "**머리말만 갱신 · 항목 보존** — Claude 판단 구간"),
                      (L_CLAUDE, "**§0 보존 · 나머지 교체** — Claude 판단 구간"),
                      ("미분류", "⚠ 층 규칙에 없다. 분류를 정하기 전에는 옮기지 않는다")):
        items = [r for r in added if layer(r) == lay] + [r for r in changed if layer(r) == lay]
        if not items:
            continue
        w("## %s — %s" % (lay, note))
        w("")
        for r in sorted(set(items)):
            w("- `%s`%s" % (r, "  *(새 파일)*" if r in added else ""))
        w("")

    if mode == "publish":
        local = load_local_leaks(A)
        if local:
            LEAK.extend(local)
        leaks = scan_leaks({r: fa[r] for r in (added + changed) if r in fa})
        w("## 익명화 후보 — %d건" % len(leaks))
        w("")
        if local is None:
            w("⚠ `%s` 가 없어 **실명·호칭은 검사하지 않았다.** «정규식<TAB>이름» 을 한 줄씩 적고 다시 돌린다."
              % LEAK_LOCAL.replace(os.sep, "/"))
            w("")
        w("스크립트는 **찾기만** 한다. 실제 문구는 사람·Claude 가 쓴다 —")
        w("기계 일괄치환이 `<호칭>님이`를 `사용자이`로 만든 전례가 있다(2026-08-03).")
        w("")
        for rel, i, label, txt in leaks[:60]:
            w("- `%s:%d` — %s: `%s`" % (rel, i, label, txt))
        if len(leaks) > 60:
            w("- … 외 %d건" % (len(leaks) - 60))
        w("")
        broken = scan_broken(fb)
        w("## 대상 볼트의 치환 파손 — %d건" % len(broken))
        w("")
        for rel, i, txt in broken:
            w("- `%s:%d` — `%s`" % (rel, i, txt))
        w("")

    w("## 이 리포트가 하지 않은 것")
    w("")
    w("- 파일을 **하나도 고치지 않았다**(P0 = 진단 전용).")
    w("- 개인 층(`1_수집/`·`notes|sessions|decisions/`·`_index/`·`_claude-memory/`)은 **열지 않았다.**")
    w("- 씨앗 파일의 «머리말과 항목의 경계»는 재지 않았다 — 사람·Claude 가 읽어야 한다.")
    w("- 대상 볼트가 코어를 **직접 고쳤는지**, 그리고 «대상에만 있는 파일»이 배포판이 지운 것인지 대상이 만든 것인지 — 둘 다 **구분하지 못한다.** 공통 조상 3자 비교가 필요하다(P1).")
    return "\n".join(L) + "\n", (len(added), len(changed), len(removed))


def write_text(path, text):
    # ④ 쓰기는 encoding 명시 + newline="\n" 고정
    #    (CRLF churn 방지 — incident-2026-07-04-writer-crlf-eol-churn)
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser(description="두 볼트의 코어 괴리를 층별로 진단한다(읽기 전용)")
    ap.add_argument("--a", required=True, help="원본 볼트 경로(가져올 쪽)")
    ap.add_argument("--b", required=True, help="대상 볼트 경로(받을 쪽)")
    ap.add_argument("--mode", choices=["update", "publish"], required=True)
    ap.add_argument("--out", help="리포트 저장 경로(생략 시 stdout)")
    a = ap.parse_args()

    for p in (a.a, a.b):
        if not os.path.isdir(p):
            print("경로 없음: %s" % p, file=sys.stderr)
            return 2

    text, (n_add, n_chg, n_del) = report(os.path.abspath(a.a), os.path.abspath(a.b), a.mode)

    # ⑤ 실측 게이트 — "산출물 존재 ≠ 완료". 괴리 0이면 그렇다고 자백한다.
    if n_add + n_chg + n_del == 0:
        print("괴리 0 — 두 볼트의 코어가 같다.", file=sys.stderr)

    if a.out:
        write_text(a.out, text)
        print("작성: %s (새 %d · 다름 %d · 삭제 %d)" % (a.out, n_add, n_chg, n_del))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
