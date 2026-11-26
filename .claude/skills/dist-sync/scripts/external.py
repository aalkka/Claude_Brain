"""볼트 밖 설정 — 이 볼트가 PC 에 기대는 설정(작업 스케줄러·레지스트리·브라우저·앱 설정·설치 프로그램)을 재고 안내한다(LLM 0).

  py -3 .claude/skills/dist-sync/scripts/external.py check [--json] [--all]   # 이 PC 에서 됐나 · 안 된 것의 할 일(Claude 명령 또는 사람 단계)
  py -3 .claude/skills/dist-sync/scripts/external.py view                    # 기본 세팅 화면(brain-base)이 읽는 한 벌 — 줄 + 사람 확인 + 새 줄 + 승인 · 늘 종료 0
  py -3 .claude/skills/dist-sync/scripts/external.py did <id> [--undo]       # 화면 «했어요» — 못 재는 줄을 사람이 했다고 적음(잰 «됨»과 갈라 둠)
  py -3 .claude/skills/dist-sync/scripts/external.py scan [--root 경로]…      # 추적: 코어가 볼트 밖을 건드리는데 목록에 없는 곳
  py -3 .claude/skills/dist-sync/scripts/external.py scan --module <id>       # 추적: 그 모듈 대본이 볼트 밖을 건드리는데 모듈 목록에 없는 곳

목록 = 같은 폴더의 ../external.json (항목마다 종류·쓰는 곳·필수·확인·하기(Claude)·안내(사람 단계)).
check 는 이 볼트에 «쓰는 곳» 파일이 있는 항목만 본다(끈 모듈·없는 기능은 묻지 않는다). 확인 명령은 읽기만 한다.
  켜진 모듈의 `contributes.outside`(모듈 안 JSON)도 합친다(11-17 · M6) — 쓰는 곳 없이 켜져 있으면 잰다 · 끄면 사라진다.
  모듈 항목은 «기기»(pc·폰)와 «재기» 하나를 단다: 명령(종료 0 됨 · 1 안 됨 · 2 모름) · 파일(볼트 상대 · 있으면 됨) ·
  레지스트리({키, 값, 기대} 읽기만) · 앱(모듈 report 명령이 낸 JSON 한 벌에서 그 id · 모듈마다 한 번) · 화면(못 잼 · 사람 확인 말).
  줄 차례 = 필수 PC → 필수 폰 → 선택 · 모듈 줄 앞에 «묶음 이름(모듈)».
scan 은 코어 파일에서 볼트 밖을 건드리는 낱말(종류마다 정규식)을 찾아, 그 파일·종류를 덮는 항목이 없으면 «안내 없음»으로 낸다.
  새 기능이 볼트 밖 설정을 더하면 여기 잡힌다 → 항목을 더하고(확인·하기 또는 안내) 다시 잰다.
  --module 은 그 모듈 폴더의 대본만 보고, 모듈 항목의 «종류»가 덮으면 된 것으로 친다(모듈 항목은 쓰는 곳이 없다 · 모듈 전체를 덮음).
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
    "망(Tailscale)": r"\btailscale(?:\.exe)?\b['\"]?(?:,\s*['\"]|\s+)(?:serve|up|status|cert|ip)\b|Tailscale[\\/]+tailscale\.exe",
}
MEASURES = ("명령", "파일", "레지스트리", "앱", "화면")     # 모듈 항목 «재기» — module-forge ⑪ 과 같은 목록
DEVICE_ORDER = {"pc": 0, "폰": 1}
CODE = (".py", ".ps1", ".psm1", ".mjs", ".cjs", ".ts", ".sh", ".bat", ".cmd")
# 볼 곳: 코어 대본 + Claude 가 따라 하는 스킬 글 · 안 볼 곳: 진단 기록·시험(가짜 등록을 일부러 부른다)·번들
SKIP = ["3_시스템/_ref/*", "3_시스템/_eval/*", ".obsidian/*", "*/node_modules/*", "*/test_*.py", "*/tests/*",
        ".claude/skills/dist-sync/scripts/external.py"]  # mf:allow-path  (읽기 전용 · 낱말 목록 자신)


def load():
    with open(LIST, encoding="utf-8") as f:
        return json.load(f)["항목"]


def hit(path, globs):
    return any(fnmatch.fnmatch(path, g) for g in globs)


def run(cmd, timeout=15, cwd=VAULT, three=False):
    """확인 명령 — PowerShell 한 줄(종료 0 = 됨). 창 없이. three = 모듈 «재기 명령»(1 = 안 됨 · 2 = 모름 → None)."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd], cwd=cwd,
                           capture_output=True, timeout=timeout, creationflags=NOWIN)
        if three and r.returncode == 2:
            return None
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return None


def module_items(root):
    """켜진 모듈의 contributes.outside → [항목 + {모듈, 묶음, _report}] · 못 읽는 모듈은 빠짐(module-forge ⑪ 이 막는다)."""
    sys.path.insert(0, os.path.join(VAULT, "3_시스템"))
    try:
        import roles  # noqa: E402 — 켬·끔은 코어 한 곳
        mods = roles.modules(on_only=True, vault=root)
    except (ImportError, OSError, KeyError, ValueError):
        return []
    out = []
    for m in mods:
        rel = ((m.get("json") or {}).get("contributes") or {}).get("outside") if isinstance(m.get("json"), dict) else None
        if not isinstance(rel, str):
            continue
        try:
            with open(os.path.join(root, *rel.replace("\\", "/").split("/")), encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        group = "%s(%s)" % (d.get("이름") or m["id"], m["id"])
        for it in d.get("항목") or []:
            if isinstance(it, dict) and it.get("id"):
                out.append(dict(it, 모듈=m["id"], 묶음=group, _report=d.get("report")))
    return out


def report_of(argv, root, timeout=30):
    """모듈 report 명령(기기 보고 · JSON 한 벌 {id: 참|거짓|null}) — 못 읽으면 {}(모든 앱 항목 = 모름)."""
    if not (isinstance(argv, list) and argv):
        return {}
    cmd = [sys.executable if t == "{py}" else t.replace("{vault}", root) for t in argv]
    try:
        r = subprocess.run(cmd, cwd=root, capture_output=True, timeout=timeout, creationflags=NOWIN)
        d = json.loads(r.stdout.decode("utf-8", "replace").strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        return {}
    return d if isinstance(d, dict) else {}


def registry(v):
    """{키: 'HKCU\\…', 값: 이름, 기대: 값?} — 읽기만. 기대가 없으면 있기만 하면 됨."""
    try:
        import winreg
    except ImportError:
        return None
    hive, _, sub = str(v.get("키", "")).partition("\\")
    root = {"HKCU": winreg.HKEY_CURRENT_USER, "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
            "HKLM": winreg.HKEY_LOCAL_MACHINE, "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE}.get(hive.upper())
    if root is None:
        return None
    try:
        with winreg.OpenKey(root, sub) as k:
            got, _ = winreg.QueryValueEx(k, v.get("값") or "")
    except OSError:
        return False
    return True if "기대" not in v else got == v["기대"]


def measure(it, root, reports):
    """모듈 항목 하나 → 참(됨) · 거짓(안 됨) · None(모름·화면으로 볼 것)."""
    m = it.get("재기") if isinstance(it.get("재기"), dict) else {}
    kind = next(iter(m), None)
    v = m.get(kind)
    if kind == "명령":
        return run(v, cwd=root, three=True)
    if kind == "파일":
        return os.path.exists(os.path.join(root, *str(v).replace("\\", "/").split("/")))
    if kind == "레지스트리":
        return registry(v) if isinstance(v, dict) else None
    if kind == "앱":
        got = reports.get(it["모듈"], {}).get(v)
        return got if isinstance(got, bool) else None
    return None


def row(it, ok):
    m = it.get("재기") if isinstance(it.get("재기"), dict) else {}
    eye = it.get("화면 확인") or m.get("화면")
    if ok is None and m.get("앱"):
        eye = eye or "기기 보고가 없음 — 먼저 그 기기를 짝짓고 앱을 한 번 연다"
    return {"id": it["id"], "이름": it["이름"], "필수": it.get("필수", False), "됨": ok,
            "누가": "Claude" if it.get("하기") else "사람", "하기": it.get("하기"), "안내": it.get("안내", []),
            "까닭": it.get("까닭", ""), "화면 확인": eye, "기기": it.get("기기", "pc"), "묶음": it.get("묶음"), "모듈": it.get("모듈"),
            "누름": it.get("누름", [])}


def click_text(c):
    """누름 칸 하나 → «앱 › 화면 › «누를 글»» · 못 잰 것은 «확인 필요: …»(지어내지 않음)."""
    path = " › ".join([c.get("앱", "")] + list(c.get("길") or []))
    if c.get("누름") is None or c.get("확인 필요"):
        return "%s%s  [확인 필요: %s]" % (path, " › «%s»" % c["누름"] if c.get("누름") else "", c.get("확인 필요") or "글 안 잼")
    return "%s › «%s»" % (path, c["누름"])


def click_bad(it):
    """사람 단계가 있는 줄의 누름 칸 꼴 — 칸마다 앱·근거 · 못 잰 것은 «확인 필요» (잰 근거를 남기기 · 11-21 사용자 «실제로 눌러야 하는 것과 안내가 달라서»)."""
    out = []
    if it.get("하기") or it.get("할 일 없음") or len(it.get("안내", [])) < 2:
        return out
    cs = it.get("누름")
    if not cs:
        return ["사람 단계가 있는데 누름 칸(앱 › 화면 › 누를 글 · 근거)이 없음"]
    for i, c in enumerate(cs, 1):
        if not c.get("앱") or not c.get("근거"):
            out.append("누름 %d: 앱·근거 없음" % i)
        if c.get("누름") is None and not c.get("확인 필요"):
            out.append("누름 %d: 누를 글이 없는데 «확인 필요» 까닭도 없음" % i)
    return out


def check(root=VAULT, everything=False):
    """이 볼트에 쓰는 곳이 있는 코어 항목 + 켜진 모듈 항목마다 확인을 함께 돌린다(창 없이 · 하나 15초 안).
    «앱» 재기는 모듈마다 report 를 한 번만 부른다. 줄 차례 = 필수 PC → 필수 폰 → 선택(같은 칸 안은 목록 차례)."""
    from concurrent.futures import ThreadPoolExecutor
    items = [it for it in load() if everything or present(it, root)]
    mods = module_items(root)
    need = {}
    for it in mods:
        if isinstance(it.get("재기"), dict) and "앱" in it["재기"]:
            need.setdefault(it["모듈"], it.get("_report"))
    with ThreadPoolExecutor(max_workers=8) as ex:
        reps = dict(zip(need, ex.map(lambda a: report_of(a, root), need.values())))
        oks = list(ex.map(lambda it: run(it["확인"], cwd=root) if it.get("확인") else None, items))
        moks = list(ex.map(lambda it: measure(it, root, reps), mods))
    rows = [row(it, ok) for it, ok in zip(items, oks)] + [row(it, ok) for it, ok in zip(mods, moks)]
    return sorted(rows, key=lambda r: (not r["필수"], DEVICE_ORDER.get(r["기기"], 2) if r["필수"] else 0))


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


def check_text(rows):
    L = []
    todo = [r for r in rows if r["됨"] is False]
    eye = [r for r in rows if r["됨"] is None]
    L.append("볼트 밖 설정 %d개 — 됨 %d · 안 됨 %d · 화면으로 볼 것 %d" % (len(rows), len(rows) - len(todo) - len(eye), len(todo), len(eye)))
    for r in rows:
        mark = {True: "✓", False: "✗", None: "?"}[r["됨"]]
        where = ("[%s%s] " % (r["묶음"], " · 폰" if r.get("기기") == "폰" else "")) if r.get("묶음") else ""
        L.append("%s %s%s%s" % (mark, where, r["이름"], "" if r["필수"] else " (선택)"))
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
        for c in r.get("누름") or []:
            L.append("   누름: " + click_text(c))
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
    gaps, seen, mods = [], set(), {}
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
                if kind in declared_kinds(root, rel, mods):
                    continue      # 모듈 폴더 대본은 그 모듈 바깥 설정 칸(contributes.outside)이 덮는다 — scan --module 과 같은 기준(11-21 self_sleep 이 ④ 에 남음)
                if not any(kind in it.get("종류", []) and hit(rel, it["쓰는 곳"]) for it in items):
                    gaps.append((rel, kind, n))
    bad = []
    for it in items:
        if not it.get("확인") and not it.get("화면 확인"):
            bad.append((it["id"], "확인 명령도 화면 확인 말도 없음"))
        if not it.get("하기") and len(it.get("안내", [])) < 2 and not it.get("할 일 없음"):
            bad.append((it["id"], "Claude 명령도 사람 단계(2단계 이상)도 없음"))
        bad += [(it["id"], w) for w in click_bad(it)]
    return gaps, bad


def declared_kinds(root, rel, cache):
    """rel 이 모듈 폴더(.claude/skills/<모듈>/) 안이면 그 모듈 바깥 설정 항목의 «종류» 모음 — 켬·끔과 상관없이 선언을 읽는다 · 시험 대본은 빈 모음."""
    m = re.match(r"\.claude/skills/([^/]+)/", rel)
    if not m:
        return set()
    base = rel.rsplit("/", 1)[-1]
    if base.endswith("_check.py") or base.startswith("test_"):
        return set(KINDS)          # 시험은 가짜 등록을 일부러 부른다(scan_module 과 같음)
    key = (root, m.group(1))
    if key not in cache:
        kinds = set()
        try:
            with open(os.path.join(root, ".claude", "skills", m.group(1), "module.json"), encoding="utf-8") as f:
                out = ((json.load(f).get("contributes") or {}).get("outside"))
            if isinstance(out, str):
                with open(os.path.join(root, *out.split("/")), encoding="utf-8") as f:
                    kinds = {k for it in (json.load(f).get("항목") or []) for k in (it.get("종류") or [])}
        except (OSError, ValueError, AttributeError):
            pass
        cache[key] = kinds
    return cache[key]


def scan_module(mid, root=VAULT):
    """--module — 그 모듈 폴더 대본이 볼트 밖을 건드리는데 모듈 항목 «종류»가 안 덮는 곳 [(파일, 종류, 줄)] · 항목 결함 [(id, 말)].
    모듈 항목에는 쓰는 곳이 없다 — 켜진 동안 모듈 전체를 덮는다. 시험(*_check.py · test_*)은 가짜 등록을 일부러 부르니 뺀다."""
    d = os.path.join(root, ".claude", "skills", mid)
    items = [it for it in module_items(root) if it.get("모듈") == mid]
    kinds = {k for it in items for k in it.get("종류", [])}
    pats = {k: re.compile(v) for k, v in KINDS.items()}
    gaps = []
    for dp, dns, fns in os.walk(d):
        dns[:] = [x for x in dns if x not in ("__pycache__", "node_modules")]
        for fn in fns:
            if not (fn.endswith(CODE) or fn == "SKILL.md") or fn.endswith("_check.py") or fn.startswith("test_"):
                continue
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root).replace("\\", "/")
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    lines = f.read().splitlines()
            except OSError:
                continue
            for kind, rx in pats.items():
                n = next((i for i, ln in enumerate(lines, 1) if rx.search(ln)), None)
                if n is not None and kind not in kinds:
                    gaps.append((rel, kind, n))
    bad = []
    for it in items:
        m = it.get("재기")
        if not (isinstance(m, dict) and len(m) == 1 and next(iter(m)) in MEASURES):
            bad.append((it["id"], "재기가 %s 중 하나가 아님" % "·".join(MEASURES)))
        if not it.get("하기") and len(it.get("안내", [])) < 2 and not it.get("할 일 없음"):
            bad.append((it["id"], "Claude 명령도 사람 단계(2단계 이상)도 없음"))
        bad += [(it["id"], w) for w in click_bad(it)]
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


HUMAN = os.path.join(VAULT, "3_시스템", "_index", "dist-sync", "setup-human.json")  # mf:allow-path  («했어요» 기록 · 개인 층)
SEEN = os.path.join(VAULT, "3_시스템", "_index", "dist-sync", "setup-seen.json")    # mf:allow-path  (줄을 처음 본 때 · 업데이트로 생긴 줄 = 7일 «새»)
NEW_DAYS = 7
ASK = re.compile(r"승인|winget|pip install|npm |install|Register-|schtasks|--install")


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _write(path, d):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def view(root=VAULT, now=None, human_path=None, seen_path=None):
    """기본 세팅 화면 한 벌. 줄마다 check 의 칸 + «했어요»(사람 확인 때 · 잰 «됨»은 바꾸지 않음) + «새»(업데이트로 생김 · 7일)
    + «승인»(Claude 가 하되 내려받기·예약이라 사람 승인 = 폰 승인 길). 처음 연 볼트는 모두 바탕으로 적고 «새»를 안 붙인다."""
    import time
    now = now or time.time()
    human_path, seen_path = human_path or HUMAN, seen_path or SEEN
    rows = check(root)
    human = _read(human_path)
    first = not os.path.exists(seen_path)
    seen = _read(seen_path)
    grew = False
    for r in rows:
        if r["id"] not in seen:
            seen[r["id"]] = 0 if first else now
            grew = True
        r["새"] = bool(seen[r["id"]]) and now - seen[r["id"]] < NEW_DAYS * 86400
        r["했어요"] = human.get(r["id"]) if r["됨"] is not True else None
        r["승인"] = bool(r["하기"] and ASK.search(r["하기"]))
    if grew:
        _write(seen_path, seen)
    return {"at": now, "rows": rows}


def did(rid, undo=False, human_path=None):
    import time
    human_path = human_path or HUMAN
    d = _read(human_path)
    if undo:
        d.pop(rid, None)
    else:
        d[rid] = time.strftime("%Y-%m-%d %H:%M")
    _write(human_path, d)
    return d.get(rid)


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
    sp.add_parser("view")
    d = sp.add_parser("did")
    d.add_argument("id")
    d.add_argument("--undo", action="store_true")
    s = sp.add_parser("scan")
    s.add_argument("--root", action="append", help="잴 저장소(여럿 가능 · 기본 = 이 볼트)")
    s.add_argument("--module", help="그 모듈 폴더 대본만(모듈 항목 «종류»가 덮나)")
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
    if a.cmd == "view":
        print(json.dumps(view(), ensure_ascii=False))
        return 0
    if a.cmd == "did":
        print(json.dumps({"id": a.id, "했어요": did(a.id, a.undo)}, ensure_ascii=False))
        return 0
    if a.module:
        gaps, bad = scan_module(a.module)
    else:
        gaps, bad = scan([os.path.abspath(r) for r in (a.root or [VAULT])], layer=core_layer())
    for rel, kind, n in gaps:
        print("안내 없음: %s:%d — %s" % (rel, n, kind))
    for i, msg in bad:
        print("항목 결함: %s — %s" % (i, msg))
    print("볼트 밖 설정 추적 — 안내 없는 곳 %d · 항목 결함 %d" % (len(gaps), len(bad)))
    return 1 if gaps or bad else 0


if __name__ == "__main__":
    sys.exit(main())
