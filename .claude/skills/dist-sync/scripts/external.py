"""볼트 밖 설정 — 이 볼트가 PC 에 기대는 설정(작업 스케줄러·레지스트리·브라우저·앱 설정·설치 프로그램)을 재고 안내한다(LLM 0).

  py -3 .claude/skills/dist-sync/scripts/external.py check [--json] [--all]   # 이 PC 에서 됐나 · 안 된 것의 할 일(Claude 명령 또는 사람 단계)
  py -3 .claude/skills/dist-sync/scripts/external.py scan [--root 경로]…      # 추적: 코어가 볼트 밖을 건드리는데 목록에 없는 곳

목록 = 같은 폴더의 ../external.json (항목마다 종류·쓰는 곳·필수·확인·하기(Claude)·안내(사람 단계)).
check 는 이 볼트에 «쓰는 곳» 파일이 있는 항목만 본다(끈 모듈·없는 기능은 묻지 않는다). 확인 명령은 읽기만 한다.
scan 은 코어 파일에서 볼트 밖을 건드리는 낱말(종류마다 정규식)을 찾아, 그 파일·종류를 덮는 항목이 없으면 «안내 없음»으로 낸다.
  새 기능이 볼트 밖 설정을 더하면 여기 잡힌다 → 항목을 더하고(확인·하기 또는 안내) 다시 잰다.
"""
import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
LIST = os.path.join(HERE, "..", "external.json")
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# 종류 → 코드에서 그 종류를 알아보는 낱말
KINDS = {
    "작업 스케줄러": r"Register-ScheduledTask|New-ScheduledTask|schtasks",
    "레지스트리": r"\bwinreg\b|HKEY_CURRENT_USER|HKCU[:\\]|\breg (add|import)\b",
    "브라우저": r"remote-debugging-port|--load-extension|chrome://extensions|\bchrome\.exe\b|\bmsedge\.exe\b",
    "파이썬 패키지": r"pip install",
    "node 도구": r"npm (i|install) (-g|--global)|\bnpx\b",
    "프로그램 설치": r"\bwinget (install|upgrade)\b|\bchoco install\b",
    "git 설정": r"git config (--global |--system )?core\.|git config --global",
    "전원": r"\bpowercfg\b|WakeToRun",
    "방화벽": r"New-NetFirewallRule|netsh (advfirewall|http)",
    "Claude 사용자 설정": r"autoMemoryDirectory|~[/\\]\.claude[/\\]|USERPROFILE[^\n]{0,20}\.claude",
}
CODE = (".py", ".ps1", ".psm1", ".mjs", ".cjs", ".ts", ".sh", ".bat", ".cmd")
# 볼 곳: 코어 대본 + Claude 가 따라 하는 스킬 글 · 안 볼 곳: 진단 기록·시험(가짜 등록을 일부러 부른다)·번들
SKIP = ["3_시스템/_ref/*", "3_시스템/_eval/*", ".obsidian/*", "*/node_modules/*", "*/test_*.py", "*/tests/*",
        ".claude/skills/dist-sync/scripts/external.py"]  # mf:allow-path  (읽기 전용 · 낱말 목록 자신)


def load():
    with open(LIST, encoding="utf-8") as f:
        return json.load(f)["항목"]


def hit(path, globs):
    return any(fnmatch.fnmatch(path, g) for g in globs)


def run(cmd, timeout=15, cwd=VAULT):
    """확인 명령 — PowerShell 한 줄(종료 0 = 됨). 창 없이."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], cwd=cwd,
                           capture_output=True, timeout=timeout, creationflags=NOWIN)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return None


def present(item, root):
    for g in item["쓰는 곳"]:
        if "*" not in g and "?" not in g:
            if os.path.exists(os.path.join(root, g)):
                return True
            continue
        base = g.split("*")[0].rsplit("/", 1)[0]
        for dp, _, fns in os.walk(os.path.join(root, base) if base else root):
            rel_dir = os.path.relpath(dp, root).replace("\\", "/")
            if any(fnmatch.fnmatch((rel_dir + "/" + fn).lstrip("./"), g) for fn in fns):
                return True
    return False


def check(root=VAULT, everything=False):
    """이 볼트에 쓰는 곳이 있는 항목마다 확인 명령을 함께 돌린다(창 없이 · 하나 15초 안)."""
    from concurrent.futures import ThreadPoolExecutor
    items = [it for it in load() if everything or present(it, root)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        oks = list(ex.map(lambda it: run(it["확인"], cwd=root) if it.get("확인") else None, items))
    return [{"id": it["id"], "이름": it["이름"], "필수": it.get("필수", False), "됨": ok,
             "누가": "Claude" if it.get("하기") else "사람", "하기": it.get("하기"), "안내": it.get("안내", []),
             "까닭": it.get("까닭", ""), "화면 확인": it.get("화면 확인")} for it, ok in zip(items, oks)]


def check_text(rows):
    L = []
    todo = [r for r in rows if r["됨"] is False]
    eye = [r for r in rows if r["됨"] is None]
    L.append("볼트 밖 설정 %d개 — 됨 %d · 안 됨 %d · 화면으로 볼 것 %d" % (len(rows), len(rows) - len(todo) - len(eye), len(todo), len(eye)))
    for r in rows:
        mark = {True: "✓", False: "✗", None: "?"}[r["됨"]]
        L.append("%s %s%s" % (mark, r["이름"], "" if r["필수"] else " (선택)"))
        if r["됨"] is True:
            continue
        if r["화면 확인"]:
            L.append("   화면 확인: " + r["화면 확인"])
        if r["까닭"]:
            L.append("   왜: " + r["까닭"])
        if r["하기"]:
            L.append("   Claude 가 할 수 있음(사람 승인 뒤): " + r["하기"])
        for i, s in enumerate(r["안내"], 1):
            L.append("   %d. %s" % (i, s))
    if todo or eye:
        L.append("안내 방법: 한 번에 한 단계만 말하고, 사람이 «했어요» 하면 확인 명령으로 재고 다음 단계로. 선택 항목은 먼저 쓸지 묻는다.")
    return "\n".join(L)


def tracked(root):
    try:
        r = subprocess.run(["git", "-C", root, "-c", "core.quotepath=false", "ls-files", "-z"], capture_output=True, timeout=30, creationflags=NOWIN)
        files = [p for p in r.stdout.decode("utf-8", "replace").split("\0") if p] if r.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired):
        files = []
    return files


def scan(roots, items=None, layer=None):
    """코어가 볼트 밖을 건드리는데 덮는 항목이 없는 곳 [(파일, 종류, 줄)] · 항목 결함 [(id, 말)]."""
    items = items if items is not None else load()
    gaps, seen = [], set()
    pats = {k: re.compile(v) for k, v in KINDS.items()}
    for root in roots:
        files = tracked(root)
        for rel in files:
            if not (rel.endswith(CODE) or rel.endswith("SKILL.md")) or hit(rel, SKIP):
                continue
            if layer and layer(rel) != "코어":
                continue
            try:
                with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()
            except OSError:
                continue
            for kind, rx in pats.items():
                n = next((i for i, ln in enumerate(lines, 1) if rx.search(ln)), None)
                if n is None or (rel, kind) in seen:
                    continue
                seen.add((rel, kind))
                if not any(kind in it.get("종류", []) and hit(rel, it["쓰는 곳"]) for it in items):
                    gaps.append((rel, kind, n))
    bad = []
    for it in items:
        if not it.get("확인") and not it.get("화면 확인"):
            bad.append((it["id"], "확인 명령도 화면 확인 말도 없음"))
        if not it.get("하기") and len(it.get("안내", [])) < 2 and not it.get("할 일 없음"):
            bad.append((it["id"], "Claude 명령도 사람 단계(2단계 이상)도 없음"))
    return gaps, bad


def core_layer():
    """층 규칙은 dist-diff 한 곳 — 개인 층(빅보스·학교 수집 등)은 배포판에 안 가니 재지 않는다."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("dist_diff", os.path.join(HERE, "dist-diff.py"))
    dd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dd)
    return dd.layer


CACHE = os.path.join(VAULT, "3_시스템", "_index", "dist-sync", "external-check.json")  # mf:allow-path  (건강 줄이 담아 둔 확인 · 개인 층)
CACHE_AGE = 20 * 3600


def health():
    """건강 줄용 (말, 필수 안 됨 수) — 담아 둔 확인을 읽고, 하루가 지났으면 창 없이 따로 다시 재게 하고 기다리지 않는다."""
    import time
    try:
        with open(CACHE, encoding="utf-8") as f:
            c = json.load(f)
    except (OSError, ValueError):
        c = None
    if not c or time.time() - c.get("at", 0) > CACHE_AGE:
        flags = NOWIN | getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            subprocess.Popen([sys.executable, os.path.abspath(__file__), "check", "--vault", VAULT, "--save", CACHE], cwd=VAULT, creationflags=flags,
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        except OSError:
            pass
    if not c:
        return None, 0
    miss = [r["이름"] for r in c["rows"] if r["필수"] and r["됨"] is False]
    if not miss:
        return None, 0
    return "볼트 밖 설정 안 됨 %d(%s) — Claude 에게 «바깥 설정 점검»" % (len(miss), miss[0] + (" 외" if len(miss) > 1 else "")), len(miss)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="볼트 밖 설정 — 확인·안내(check) · 추적(scan)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    c = sp.add_parser("check")
    c.add_argument("--json", action="store_true")
    c.add_argument("--all", action="store_true", help="이 볼트에 없는 기능의 항목도")
    c.add_argument("--vault", default=VAULT, help="잴 볼트(기본 = 이 대본이 든 볼트)")
    c.add_argument("--save", help="결과를 이 JSON 에 담는다(건강 줄이 하루 한 번 따로 부른다)")
    s = sp.add_parser("scan")
    s.add_argument("--root", action="append", help="잴 저장소(여럿 가능 · 기본 = 이 볼트)")
    a = ap.parse_args()
    if a.cmd == "check":
        rows = check(os.path.abspath(a.vault), a.all)
        if a.save:
            os.makedirs(os.path.dirname(os.path.abspath(a.save)), exist_ok=True)
            with open(a.save, "w", encoding="utf-8", newline="\n") as f:
                json.dump({"at": __import__("time").time(), "rows": rows}, f, ensure_ascii=False)
            return 0
        print(json.dumps(rows, ensure_ascii=False, indent=1) if a.json else check_text(rows))
        return 1 if any(r["됨"] is False and r["필수"] for r in rows) else 0
    gaps, bad = scan([os.path.abspath(r) for r in (a.root or [VAULT])], layer=core_layer())
    for rel, kind, n in gaps:
        print("안내 없음: %s:%d — %s" % (rel, n, kind))
    for i, msg in bad:
        print("항목 결함: %s — %s" % (i, msg))
    print("볼트 밖 설정 추적 — 안내 없는 곳 %d · 항목 결함 %d" % (len(gaps), len(bad)))
    return 1 if gaps or bad else 0


if __name__ == "__main__":
    sys.exit(main())
