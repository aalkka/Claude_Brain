#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""상시 문서가 볼트 현실과 어긋났는지 잰다(볼트 개혁 · 2026-11-02 · ADR-026).

왜: 구조를 옮겨도 코어·기억·스킬 글 속 옛 이름은 따라오지 않았고(_eval/hardpaths.py 는 코드만 보고 기억을 뺀다),
상시로 읽히는 파일은 상한 없이 자랐다(기억 색인 한 줄 808자 · MOC 188k). 사람이 드물게 점검해서는 늘 뒤늦다.

  py -3 3_시스템/drift.py            전체 리포트(줄마다 종류 · 파일:줄 · 내용)
  py -3 3_시스템/drift.py --brief    종류별 건수 한 줄
  py -3 3_시스템/drift.py --ops      운영 위험만(세션 시작용) — 없으면 출력 없음
  py -3 3_시스템/drift.py --mem      PC 줄(메모리 넘침·재부팅·NVIDIA 오버레이·남은 시험 프로세스) — 건강 창(brain.py doctor)이 같은 것을 보인다
  py -3 3_시스템/drift.py --kill-test  남은 시험 프로세스 끄기(건강 «고치기»로 고를 때만 · 시험 잠금이 있으면 안 끔)

쓰는 곳: weekly.py(전수) · mdtable.py hook(쓰는 순간 그 파일 상한) · hooks/session-notice.py(운영 위험).
새 옛 이름은 RETIRED 에 더한다. 이력을 적은 줄(옛·철회 등)과 `drift:ok` 가 붙은 줄은 세지 않는다.
"""
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
MEM = os.path.join(HERE, "_claude-memory")
LOCK_MIN = 10            # 이보다 오래된 index.lock 은 죽은 잠금으로 본다
COMMIT_H = 24

RETIRED = [
    (r"Documents[\\/]+Claude", "0_작업/<영역>/<주제>"),
    (r"(?:1_수집|_색인)[\\/]+학교", "1_수집/배움 · _색인/배움"),
    (r"2_지식[\\/]+(?:notes|sessions|decisions|_canvas|과목)(?![\w가-힣])", "roles.py path <역할>"),
    (r"(?<![\w./\\`_-])(?:notes|sessions|decisions)/", "역할 이름 — roles.py"),
    (r"session-close", "session-record"),
    (r"\bimportance\b", "10-30 폐지"),
    (r"caveman 모드", "출력 규약 lean"),
    (r"inbox-sort|module-forge:new|study-helper:organize|`organize`|`ingest-vision`|`search` |검색 스킬", "11-02 제거 — ADR-026"),
]
RETIRED = [(re.compile(a), b) for a, b in RETIRED]
HISTORY = re.compile(r"옛|구 |구\)|(?<![가-힣])전 |철회|폐기|폐지|기각|이력|당시|이전|대체|뺐다|drift:ok")
PATH = re.compile(r"(?<![~/\\])(?:0_작업|1_수집|2_지식|3_시스템|\.claude)[/\\][^\s`'\"<>|*,;()\[\]{}«»…]+")
ABS = re.compile(r"[A-Z]:\\[^\s`'\"<>|*,;()\[\]{}«»…]+")
HANGUL = re.compile(r"[가-힣]$")
SKIP_PATH = re.compile(r"실험N|어떤노트|2_지식/참조|_index|\$|%|YYYY|XX|\.\.\.|plugins/<|NN|Program(?: Files)?$")
INDEX_LINK = re.compile(r"^- \[[^\]]+\]\(([^)]+)\)", re.M)


def rel(p):
    return os.path.relpath(p, VAULT).replace(os.sep, "/")


def read(p):
    with open(p, encoding="utf-8-sig", errors="replace") as h:
        return h.read()


def docs():
    """상시·지침 문서 — 모델이 믿고 따르는 글"""
    out = [os.path.join(VAULT, "CLAUDE.md"), os.path.join(VAULT, "README.md"), os.path.join(HERE, "conventions.md")]
    # 사람·Claude 가 믿는 시스템 문서 — 안 봐서 설명서 206줄이 «어긋남 0» 인 채 낡았다(11-03)
    out += glob.glob(os.path.join(VAULT, "2_지식", "**", "설계노트.md"), recursive=True) + glob.glob(os.path.join(VAULT, "2_지식", "**", "사용자설명서.md"), recursive=True)
    out += sorted(glob.glob(os.path.join(HERE, "tutorial", "*.md")) + glob.glob(os.path.join(HERE, "vault-chat", "*.md")))
    out += sorted(glob.glob(os.path.join(MEM, "*.md")))
    out += glob.glob(os.path.expanduser("~/.claude/scheduled-tasks/*/SKILL.md"))    # 무인 실행 지시문도 낡으면 그대로 따른다
    for p in glob.glob(os.path.join(VAULT, ".claude", "skills", "**", "*.md"), recursive=True):
        if os.sep + "references" + os.sep not in p and os.sep + "templates" + os.sep not in p:
            out.append(p)
    return out


def hooks():
    return [p for p in glob.glob(os.path.join(HERE, "hooks", "*")) if os.path.isfile(p)]


def exists_loose(p, base=VAULT):
    """글 속 경로 뒤에 조사가 붙을 수 있다 — 끝 글자를 세 번까지 떼어 본다"""
    p = p.rstrip(".:·-/\\")
    for _ in range(4):
        if os.path.exists(os.path.join(base, p)):
            return True
        if not HANGUL.search(p):
            return False
        p = p[:-1].rstrip(".:·-/\\")
    return False


def retired_rows():
    rows = []
    for p in docs() + hooks():
        for i, ln in enumerate(read(p).split("\n"), 1):
            if HISTORY.search(ln):
                continue
            for rx, new in RETIRED:
                m = rx.search(ln)
                if m:
                    rows.append(("옛 이름", f"{rel(p)}:{i}", f"{m.group(0)} → {new}"))
    return rows


def path_rows():
    rows = []
    for p in docs():
        for i, ln in enumerate(read(p).split("\n"), 1):
            if HISTORY.search(ln):
                continue
            for m in PATH.finditer(ln):
                t = m.group(0)
                if not SKIP_PATH.search(t) and not exists_loose(t):
                    rows.append(("없는 경로", f"{rel(p)}:{i}", t))
            for m in ABS.finditer(ln):
                t = m.group(0)
                if not SKIP_PATH.search(t) and not exists_loose(t, ""):
                    rows.append(("없는 경로", f"{rel(p)}:{i}", t))
    return rows


def limits_of(p):
    """한 파일의 상한 위반 — 대상이 아니면 빈 목록(쓰기 훅이 부른다)"""
    p = os.path.normpath(p)
    name = os.path.basename(p)
    parent = os.path.normpath(os.path.dirname(p))
    know = os.path.join(VAULT, "2_지식")
    out = []
    try:
        if parent == os.path.normpath(MEM) and (name == "MEMORY.md" or name.startswith("index-")):
            t, n, what = read(p), 150, "기억 색인"
        elif parent == os.path.normpath(know) and name == "MOC.md":
            t, n, what = read(p), 150, "MOC"
        elif parent == os.path.normpath(know) and name == "recent.md":
            t, n, what = read(p), 150, "recent"
            items = [x for x in t.split("\n") if x.startswith("- ")]
            if len(items) > 9:
                out.append(("상한", rel(p), f"recent {len(items)}줄(9줄까지)"))
        elif parent == os.path.normpath(know) and name == "open-loops.md":
            t, n, what = read(p), 300, "open-loops"
            size = len(t.encode("utf-8"))
            if size > 6144:
                out.append(("상한", rel(p), f"open-loops {size}바이트(6KB까지)"))
        elif os.path.normpath(p) == os.path.join(VAULT, "CLAUDE.md"):
            t = read(p)
            if t.count("\n") > 200:
                out.append(("상한", rel(p), f"CLAUDE.md {t.count(chr(10))}줄(200줄까지)"))
            return out
        else:
            return out
    except OSError:
        return out
    for i, ln in enumerate(t.split("\n"), 1):
        if ln.startswith("- ") and len(ln) > n:
            out.append(("상한", f"{rel(p)}:{i}", f"{what} 줄 {len(ln)}자({n}자까지): {ln[:40]}…"))
    return out


def limit_rows():
    rows = []
    for p in (os.path.join(MEM, "MEMORY.md"), *glob.glob(os.path.join(MEM, "index-*.md")),
              os.path.join(VAULT, "2_지식", "MOC.md"), os.path.join(VAULT, "2_지식", "recent.md"),
              os.path.join(VAULT, "2_지식", "open-loops.md"), os.path.join(VAULT, "CLAUDE.md")):
        rows += limits_of(p)
    for p in glob.glob(os.path.join(VAULT, ".claude", "skills", "**", "SKILL.md"), recursive=True):
        m = re.search(r"^description:\s*(.*)$", read(p), re.M)
        if m and len(m.group(1)) > 250:
            rows.append(("상한", rel(p), f"스킬 설명 {len(m.group(1))}자(250자까지 · 늘 입력에 든다)"))
    return rows


def memory_rows():
    """색인 ↔ 기억 파일"""
    rows, seen = [], set()
    idx = [os.path.join(MEM, "MEMORY.md")] + glob.glob(os.path.join(MEM, "index-*.md"))
    for p in idx:
        if not os.path.exists(p):
            continue
        for m in INDEX_LINK.finditer(read(p)):
            f = m.group(1)
            seen.add(f)
            if not os.path.exists(os.path.join(MEM, f)):
                rows.append(("기억 색인", rel(p), f"없는 파일: {f}"))
    linked_subs = {os.path.basename(p) for p in idx}
    for p in glob.glob(os.path.join(MEM, "*.md")):
        b = os.path.basename(p)
        if b not in seen and b not in linked_subs:
            rows.append(("기억 색인", b, "색인에 없음"))
    return rows


def ops_rows():
    """운영 위험 — 조용히 일을 망치는 것(전부 실제로 겪음: 잠금 3회 · 게이트웨이 10-02)"""
    rows = []
    lock = os.path.join(VAULT, ".git", "index.lock")
    if os.path.exists(lock):
        age = (time.time() - os.path.getmtime(lock)) / 60
        if age >= LOCK_MIN:
            rows.append(("운영", ".git/index.lock", f"{int(age)}분째 남은 잠금 — 자동 커밋이 멈춘다"))
    try:
        r = subprocess.run(["git", "-C", VAULT, "log", "-1", "--format=%ct"], capture_output=True, text=True, timeout=5)
        h = (time.time() - int(r.stdout.strip())) / 3600
        if h >= COMMIT_H:
            rows.append(("운영", "git", f"마지막 커밋 {int(h)}시간 전 — 자동 커밋 확인"))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    # 민감 노트가 추적되면 자동 push 로 원격에 간다 — pre-commit 은 스테이지 순간만 보고 이미 든 것은 못 뺀다(11-05 실측 7건)
    try:
        r = subprocess.run(["git", "-C", VAULT, "grep", "-lE", r"^sensitive:[[:space:]]*true[[:space:]]*$", "HEAD", "--", "*.md"],
                           capture_output=True, timeout=5)
        n = len(r.stdout.splitlines())
        if n:
            rows.append(("운영", "민감 노트", f"{n}건이 git 추적 중 — 자동 push 로 원격에 간다 · .gitignore 에 넣고 추적 해제"))
    except (OSError, subprocess.SubprocessError):
        pass
    # 안 보낸 커밋에 민감 노트 — pre-push 가 막으면 자동 push(세션 시작·끝)가 조용히 멈춘다(11-15 · 막힌 push 는 훅 밖에서 안 보임)
    try:
        r = subprocess.run([sys.executable, os.path.join(VAULT, "3_시스템", "hooks", "pre-push-scan.py"), "--check"],
                           cwd=VAULT, capture_output=True, timeout=20)
        hits = json.loads(r.stdout.decode("utf-8", "replace") or "{}").get("hits") or []
        if hits:
            rows.append(("운영", "push 막힘", f"안 보낸 커밋에 민감 노트 {len(hits)}건({hits[0][1]}) — pre-push 가 막아 자동 push 가 멈춤 · Claude 에게 «push 막힘»"))
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    # Stop 훅이 커밋 뒤 스테이지가 남으면 적는 줄 — 세션 시작에 안 보여 쌓이기만 했다(07-30~11-03 157줄)
    # 막힌 뒤 자동 커밋(claude@local·user@local)이 한 번이라도 됐으면 풀린 것 — 그 앞 줄은 세지 않는다.
    # 11-12 잼: 24시간 안 5회 중 4회는 전날 밤 고친 진짜 막힘(옵시디언 CSS 사본 비밀값 오탐 · 23:05 고침), 1회는 Stop 훅 둘이
    # 겹친 경합(같은 초에 다른 쪽이 커밋) — 둘 다 이미 풀려 있었는데 다음 날까지 위험으로 떴다.
    try:
        with open(os.path.join(HERE, "_index", "hooks.log"), "rb") as h:
            h.seek(0, os.SEEK_END)
            h.seek(max(0, h.tell() - 500_000))
            log = h.read().decode("utf-8", "replace")
        now = time.time()
        try:
            r = subprocess.run(["git", "-C", VAULT, "log", "-1", "--format=%ct", "--author=claude@local", "--author=user@local"],
                               capture_output=True, text=True, timeout=5)
            last_auto = int(r.stdout.strip() or 0)
        except (OSError, ValueError, subprocess.SubprocessError):
            last_auto = 0                          # 못 재면 지금처럼 24시간 안 줄을 모두 센다
        hits = []
        for line in log.splitlines():
            if "BLOCKED" in line:
                try:
                    t = time.mktime(time.strptime(line[:19], "%Y-%m-%d %H:%M:%S"))
                except ValueError:
                    continue
                if now - t < COMMIT_H * 3600 and t > last_auto:
                    hits.append(line[11:16])
        if hits:
            rows.append(("운영", "자동 커밋", f"막힌 뒤 자동 커밋 0회 — {len(hits)}회 막힘(마지막 {hits[-1]}) · 3_시스템/_index/hooks.log 의 까닭 · 스테이지에 남은 파일 확인"))
    except OSError:
        pass
    # 앱이 자기 프로세스에 BASE_URL=api.anthropic.com 을 넣고, 사용자 범위에 빈 값이 남기도 한다 — 값이 있고 공식 주소가 아닐 때만 위험
    found = set()
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            for n in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"):
                try:
                    v = winreg.QueryValueEx(k, n)[0]
                except OSError:
                    continue
                if v and "api.anthropic.com" not in v:
                    found.add(n)
    except (ImportError, OSError):
        pass
    for n in ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"):
        if os.environ.get(n):
            found.add(n)
    if "api.anthropic.com" not in os.environ.get("ANTHROPIC_BASE_URL", "api.anthropic.com"):
        found.add("ANTHROPIC_BASE_URL")
    if found:
        rows.append(("운영", "환경 변수", " · ".join(sorted(found)) + " 있음 — claude -p 가 구독을 벗어나 과금될 수 있다"))
    try:                                # 기록 보존 순찰(11-12 안 A · 11-17 코어로 옮김 M8 = 3_시스템/autocommit.py) — 막힘은 위 «자동 커밋»(hooks.log BLOCKED)이 센다 · 그 밖의 실패만
        p = os.path.join(HERE, "_index", "autocommit.json")
        if not os.path.exists(p):       # 옮기기 전 자리(폰 서버가 쓰던 것) — 새 순찰이 한 번 돌면 새 자리만
            p = os.path.join(HERE, "_index", "server", "autocommit.json")
        a = json.load(open(p, encoding="utf-8"))
        if a.get("fail_at") and a.get("result") != "막힘":
            rows.append(("운영", "자동 커밋(순찰)", f"{a.get('result')} — {time.strftime('%m-%d %H:%M', time.localtime(a['fail_at']))} · 3_시스템/_index/hooks.log «기록보존» 줄"))
    except (OSError, ValueError, KeyError):
        pass
    try:                                # 구독 끊김(11-11 · claude_bin 상태 파일) — 적혀 있을 때만 다시 잰다(다시 구독했으면 여기서 풀림 · 평소 비용 0)
        import claude_bin
        bare = {k: v for k, v in os.environ.items() if not re.match(r"CLAUDECODE|CLAUDE_CODE|CLAUDE_AGENT|ANTHROPIC_", k)}   # 세션 안이면 앱이 넣은 BASE_URL 이 «과금 길»로 읽혀 끊김이 안 풀린다
        if claude_bin.lapsed() and not claude_bin.check(bare)["ok"] and claude_bin.lapsed():
            d = claude_bin.lapsed()
            rows.append(("운영", "구독", f"{d.get('kind')} — {time.strftime('%m-%d %H:%M', time.localtime(d.get('since') or 0))}부터 · 구독이 필요한 기능 멈춤(대화창·그림 읽기·공지 판정·폰 RC) · 다시 구독·로그인하면 풀림"))
    except Exception:                   # 건강 점검이 이것 때문에 죽지 않게
        pass
    return rows


# ── PC 메모리(11-18) — 램 13.9GB 에 커밋 29/36GB: 넘친 몫이 페이지 파일로 가 PC 가 느려졌다(claude 27개 11GB · 폰 RC 세션 6개 3.3GB ·
#    NVIDIA 오버레이 1.75GB · 남은 pwsh). 건강 창(brain.py doctor)이 줄로 보인다 · ctypes 만(psutil·PowerShell 없음 · 0.2초 안팎) · 못 잰 줄은 빠진다.
MEM_RATIO, UP_DAYS, BIG_N, BIG_GB, HEAVY_H = 1.5, 7, 3, 0.5, 6
NV_OVERLAY = {"nvidia overlay.exe", "nvidia share.exe", "presentmon_x64.exe"}   # PresentMon = NVIDIA 앱 성능 통계(FrameView) · 11-19 잼 1.9코어 상시
EMU = re.compile(r"^(emulator|qemu-system-[\w.-]+)\.exe$", re.I)
KILL_CMD = "py -3 3_시스템/drift.py --kill-test"


def _cmdline(h):
    """열린 프로세스의 명령 줄(NtQueryInformationProcess 60 · 윈도 8.1~) · 못 읽으면 ''"""
    import ctypes
    from ctypes import wintypes
    nt = ctypes.windll.ntdll
    n = wintypes.ULONG(0)
    for size in (8192, 65536):
        buf = ctypes.create_string_buffer(size)
        if nt.NtQueryInformationProcess(h, 60, buf, size, ctypes.byref(n)) == 0:     # UNICODE_STRING{길이 USHORT · 최대 USHORT · 포인터} + 글
            ln = ctypes.c_ushort.from_buffer(buf, 0).value
            ptr = ctypes.c_void_p.from_buffer(buf, ctypes.sizeof(ctypes.c_void_p)).value
            return ctypes.wstring_at(ptr, ln // 2) if ptr else ""
        if n.value <= size:
            break
    return ""


def processes():
    """{pid: (부모 pid, 이름, 사적 바이트, 명령 줄)} — 명령 줄은 Obsidian.exe 만(격리 옵시디언 가르기) · 못 연 프로세스는 바이트 0"""
    import ctypes
    from ctypes import wintypes

    class PE(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t),
                    ("mod", wintypes.DWORD), ("threads", wintypes.DWORD), ("ppid", wintypes.DWORD), ("pri", ctypes.c_long),
                    ("flags", wintypes.DWORD), ("exe", ctypes.c_wchar * 260)]

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("faults", wintypes.DWORD)] + [(n, ctypes.c_size_t) for n in
                    ("peak_ws", "ws", "qpp", "qp", "qpnp", "qnp", "pf", "peak_pf", "private")]
    k = ctypes.windll.kernel32
    k.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    k.OpenProcess.restype = wintypes.HANDLE
    snap = k.CreateToolhelp32Snapshot(2, 0)
    if not snap or snap == ctypes.c_void_p(-1).value:
        return {}
    rows, e = [], PE()
    e.size = ctypes.sizeof(PE)
    try:
        more = k.Process32FirstW(wintypes.HANDLE(snap), ctypes.byref(e))
        while more:
            rows.append((e.pid, e.ppid, e.exe))
            more = k.Process32NextW(wintypes.HANDLE(snap), ctypes.byref(e))
    finally:
        k.CloseHandle(wintypes.HANDLE(snap))
    out = {}
    for pid, ppid, name in rows:
        priv, cmd = 0, ""
        h = k.OpenProcess(0x1000, False, pid) if pid else None      # PROCESS_QUERY_LIMITED_INFORMATION
        if h:
            try:
                m = PMC()
                m.cb = ctypes.sizeof(PMC)
                if k.K32GetProcessMemoryInfo(wintypes.HANDLE(h), ctypes.byref(m), m.cb):
                    priv = m.private
                if name.lower() == "obsidian.exe":
                    cmd = _cmdline(wintypes.HANDLE(h))
            finally:
                k.CloseHandle(wintypes.HANDLE(h))
        out[pid] = (ppid, name, priv, cmd)
    return out


def machine():
    """{ram, commit (GB) · up_days · procs} — 잴 수 없는 칸은 빠진다(윈도 밖·권한·오류)"""
    out = {}
    if os.name != "nt":
        return out
    import ctypes
    k = ctypes.windll.kernel32
    try:
        class MS(ctypes.Structure):
            _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in ("total", "avail", "tp", "ap", "tv", "av", "ae")]
        m = MS()
        m.len = ctypes.sizeof(MS)
        if k.GlobalMemoryStatusEx(ctypes.byref(m)):
            out["ram"], out["commit"] = m.total / 2 ** 30, (m.tp - m.ap) / 2 ** 30     # 커밋 = 커밋 한도 - 남은 커밋(작업 관리자 «커밋됨»)
    except Exception:  # noqa: BLE001
        pass
    try:
        k.GetTickCount64.restype = ctypes.c_ulonglong
        out["up_days"] = k.GetTickCount64() / 86400000          # 잠든 시간 포함 · 빠른 시작(끄기 = 최대 절전)도 이어서 센다 — 다시 시작만 0
    except Exception:  # noqa: BLE001
        pass
    try:
        out["procs"] = processes()
    except Exception:  # noqa: BLE001
        pass
    return out


def heavy_locked():
    """빅보스 시험 잠금(무거운 자원을 쓰는 중) — 있으면 시험 프로세스는 쓰는 중이다. HEAVY_H 시간 넘은 잠금은 묵은 것(풀기를 잊음)이라 안 센다
    (11-18 잼: 작업세션/heavy.lock 0바이트 11-14 04:07 가 나흘째 남아 있었다 — 세면 이 줄이 영영 안 뜬다)"""
    now = time.time()
    return any(now - os.path.getmtime(p) < HEAVY_H * 3600 for p in glob.glob(os.path.join(HERE, "_index", "bigboss", "*", "heavy.lock")))


def test_procs(procs):
    """[(pid, 종류)] — 시험이 남기는 것: 에뮬레이터(emulator·qemu) · adb 서버 · 격리 옵시디언(기본 프로필이 아닌 --user-data-dir 의 주 프로세스)"""
    home = os.path.normcase(os.path.normpath(os.path.join(os.environ.get("APPDATA", ""), "obsidian")))
    out = []
    for pid, (_pp, name, _b, cmd) in procs.items():
        low = name.lower()
        if EMU.match(name):
            out.append((pid, "에뮬레이터"))
        elif low == "adb.exe":
            out.append((pid, "adb"))
        elif low == "obsidian.exe" and "--type=" not in cmd:
            m = re.search(r'--user-data-dir=(?:"([^"]+)"|(\S+))', cmd)
            if m and os.path.normcase(os.path.normpath(m.group(1) or m.group(2))) != home:
                out.append((pid, "격리 옵시디언"))
    return out


def mem_rows(m=None, locked=None):
    """[(이름, 상태, 줄)] — 건강 창 줄(brain.py doctor). 메모리는 늘 한 줄(✓ 커밋/램) · 나머지는 문제일 때만. 못 잰 줄은 빠진다."""
    m = machine() if m is None else m
    procs = m.get("procs") or {}
    rows = []
    if m.get("ram") and m.get("commit") is not None:
        if m["commit"] > MEM_RATIO * m["ram"]:
            grp = {}
            for _pp, name, b, _c in procs.values():
                g = grp.setdefault(re.sub(r"\.exe$", "", name, flags=re.I), [0, 0])
                g[0] += 1
                g[1] += b
            big = sorted(((n, c, b / 2 ** 30) for n, (c, b) in grp.items() if b / 2 ** 30 >= BIG_GB), key=lambda x: -x[2])[:BIG_N]
            rows.append(("메모리", "warn", f"메모리 넘침 {m['commit']:.0f}/{m['ram']:.1f} GB(커밋/램)" +
                         (" · 큰 것: " + ", ".join(f"{n} {c}개 {gb:.1f}GB" if c > 1 else f"{n} {gb:.1f}GB" for n, c, gb in big) if big else "")))
        else:
            rows.append(("메모리", "ok", f"커밋 {m['commit']:.0f}/{m['ram']:.1f} GB(램의 {m['commit'] / m['ram']:.1f}배)"))
    if m.get("up_days", 0) > UP_DAYS:
        rows.append(("재부팅", "warn", f"켜진 지 {int(m['up_days'])}일 · 재부팅 권함"))
    nv = [b for _pp, name, b, _c in procs.values() if name.lower() in NV_OVERLAY]
    if nv:
        rows.append(("NVIDIA 오버레이", "warn", f"NVIDIA 오버레이 켜짐(약 {sum(nv) / 2 ** 30:.1f}GB) · NVIDIA 앱에서 끔"))
    left = test_procs(procs)
    if left and not (heavy_locked() if locked is None else locked):
        kinds = {}
        for _pid, kind in left:
            kinds[kind] = kinds.get(kind, 0) + 1
        rows.append(("시험 프로세스", "warn", f"남은 시험 프로세스 {len(left)}개({', '.join(f'{k} {n}' for k, n in kinds.items())}) — 끄기 = `{KILL_CMD}`(건강 «고치기»로 · 시험 잠금이 없을 때만)"))
    return rows


def kill_test(procs=None, locked=None):
    """남은 시험 프로세스를 끈다(자식째) — 사용자가 건강 «고치기»로 고를 때만 부른다(자동으로 안 끔). 시험 잠금이 있으면 안 끔."""
    if heavy_locked() if locked is None else locked:
        return None
    procs = processes() if procs is None else procs
    done = []
    for pid, kind in test_procs(procs):
        fam = _family(pid, procs)           # taskkill /T 는 죽은 부모의 pid 를 다시 받은 프로세스 아래 남의 고아까지 끈다 — 시작 시각으로 가른다
        r = subprocess.run(["taskkill", "/F"] + [x for q in fam for x in ("/PID", str(q))], capture_output=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        done.append((pid, kind, r.returncode == 0))
    return done


def _start(pid):
    """프로세스 시작 시각(FILETIME) · 못 열면 None"""
    import ctypes
    from ctypes import wintypes
    k = ctypes.windll.kernel32
    k.OpenProcess.restype = wintypes.HANDLE
    h = k.OpenProcess(0x1000, False, int(pid))
    if not h:
        return None
    try:
        t = (wintypes.FILETIME * 4)()
        if not k.GetProcessTimes(wintypes.HANDLE(h), *[ctypes.byref(x) for x in t]):
            return None
        return (t[0].dwHighDateTime << 32) | t[0].dwLowDateTime
    finally:
        k.CloseHandle(wintypes.HANDLE(h))


def _family(pid, procs):
    """pid 와 그 아래(손주까지) — 부모보다 먼저 뜬 것은 뺀다"""
    sub = {}
    for p, row in procs.items():
        if p != row[0]:
            sub.setdefault(row[0], []).append(p)
    out, todo = [], [pid]
    while todo:
        q = todo.pop()
        if q in out:
            continue
        out.append(q)
        sq = _start(q)
        todo += [c for c in sub.get(q, []) if sq is not None and (_start(c) or 0) >= sq]
    return out


def props_rows():
    """규약 글의 속성 표 ↔ roles.json props — 표가 플러그인에만 있고 규약 글과 갈라져 Claude 노트가 옛 꼴로 남았다(ADR-027)"""
    conv = os.path.join(HERE, "conventions.md")
    try:
        table = json.load(open(os.path.join(HERE, "roles.json"), encoding="utf-8")).get("props", {})
        m = re.search(r"^# 프론트매터 스키마\n.*?```yaml\n(.*?)\n```", read(conv), re.S | re.M)
    except (OSError, ValueError):
        return []
    if not table or not m:
        return [("속성 표", rel(conv), "규약 글에서 표를 못 찾음")]
    doc, now = {}, None
    for ln in m.group(1).split("\n"):
        head = re.match(r"# (\S+)", ln)
        if head:
            now = doc.setdefault(head.group(1), [])
        elif now is not None and re.match(r"[^\s#:]+:", ln):
            now.append(ln.split(":")[0])
    roles_ = json.load(open(os.path.join(HERE, "roles.json"), encoding="utf-8"))["roles"]
    return [("속성 표", rel(conv), f"{roles_[r]} 표가 roles.json props 와 다름: {doc.get(roles_[r])} ≠ {keys}")
            for r, keys in table.items() if not r.startswith("_") and doc.get(roles_[r]) != keys]


def all_rows():
    return retired_rows() + path_rows() + limit_rows() + memory_rows() + ops_rows() + props_rows()


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    if "--ops" in argv:
        for k, w, t in ops_rows():
            print(f"{w}: {t}")
        return 0
    if "--mem" in argv:                 # 건강 창 PC 줄(메모리·재부팅·NVIDIA 오버레이·남은 시험 프로세스) — brain.py doctor 가 같은 것을 부른다
        for n, s, t in mem_rows():
            print(f"{'✓' if s == 'ok' else '△'} {n}: {t}")
        return 0
    if "--kill-test" in argv:           # 건강 «고치기»로 사용자가 고를 때만
        done = kill_test()
        if done is None:
            print("시험 잠금(_index/bigboss/*/heavy.lock)이 있어 안 끔 — 시험이 도는 중")
        else:
            print("끌 것 없음" if not done else "\n".join(f"{'끔' if ok else '못 끔'} {kind} pid {pid}" for pid, kind, ok in done))
        return 0
    rows = all_rows()
    if "--brief" in argv:
        c = {}
        for k, _, _ in rows:
            c[k] = c.get(k, 0) + 1
        print("어긋남 0" if not rows else "어긋남 " + " · ".join(f"{k} {v}" for k, v in c.items()))
        return 0
    if not rows:
        print("어긋남 0")
    for k, w, t in rows:
        print(f"{k} | {w} | {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
