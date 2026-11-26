#!/usr/bin/env python3
"""폰 승인 - 게이트 코어 묶음을 폰 지문 서명이나 PC 콘솔 y 로 붙이는 검증·적용기(게이트 코어 · 3_시스템/hooks/approve/).  # mf:allow-path
설계 = 제작자 설계 노트(배포판에 없음 · 11-17). 소스·시험 = 제작자 저장소(배포판에 없음).  # mf:allow-path

  approve.py status [--json]                대기 수 · 가장 오래 기다린 분 · 동결 (서버 -> 폰 알림·홈 단추 배지)
  approve.py challenge <run> [--json]       폰에 보낼 볼트 묶음 + 도전값(장부에 적음 · 30분)
  approve.py apply-signed [<파일>|-]        폰 서명 {"message","sig"}(base64) -> 다 재고 붙임 · 결과 JSON 한 줄
  approve.py apply-console <run> [--yes]    PC y 길 - 콘솔에서 직접 친 y 만 받는다(pending.py apply 가 부른다)
  approve.py enroll <공개 키 base64> [--label 글]   폰 키 등록 요청을 받아 둔다(등록은 아님)
  approve.py register                       받아 둔 요청 -> 짝 숫자 6자리 -> 콘솔 y -> 키 목록에 한 줄
  approve.py revoke <키 id>                 키 목록에서 뺀다(콘솔 y)
  approve.py keys [--json]                  키 목록 · 줄 수 · 목록 지문(weekly-review)
  approve.py recent [--n 20]                최근 붙임·동결·등록 기록 JSON(승인 앱 «내 키 아닌 서명» 표시)
  approve.py reject <run> --all <sha> [--why 글]   폰 «거절» 기록(붙이는 길 아님)
  approve.py freeze [--why 글]              «내가 안 시킴» - 폰 승인을 전부 멈춘다(누구나 · 안전 쪽)
  approve.py unfreeze                       동결 풀기(콘솔 y)
  approve.py challenge-cmd <run> <NN> [--json]   명령 승인(사용자 권한 한 줄) 하나 + 도전값 · 명령에 이름이 나온 파일 내용째
  approve.py run-exec <서명 파일>           (적용기가 스스로 부름) 서명을 다시 재고 명령을 창 없이 돌려 결과를 적는다
  approve.py result <run> <NN>              명령 승인의 상태·결과 JSON
  approve.py reject-cmd <run> <NN> [--why 글]    폰 «거절» - 명령 요청을 닫는다

목적·사유(11-20 approve-all): 모든 승인(묶음 meta · 명령 요청)에 purpose(목적 40자)·reason(사유 80자)이 한 줄씩 있어야 한다 · 비면 거절.
명령 승인 = 사용자 권한 PowerShell 한 줄(관리자 승격·숨긴 명령·게이트 코어 경로 거절) · 서명 글이 명령 글·작업 폴더·이름이 나온 파일 sha 를 덮는다.

믿음: 폰 승인의 근거는 키 목록(keys.txt · 이 폴더)에 있는 폰 Keystore 키의 서명 하나뿐이다. 서버 토큰·서버·pending.py 는 나르기만 한다.
서명 글 = 용도 · 저장소 · run · 항목(번호 · diff sha · meta sha) · 이어 붙인 sha · 적용 전 파일 상태 sha · 도전값 · 폰 시각 · 키 id.
적용기는 지금 상태로 같은 글을 다시 만들어 바이트로 견주고, 그 서명을 잰 뒤, 잠금 안에서 잰 diff 바이트를 그대로 git apply 에 넘긴다.
실패 방향: 서명·해시·상태를 못 재면 안 붙인다(fail-closed). PC y 길은 남는다.
자기 제외: 이 폴더 · core-gate* · .claude/settings(.local).json · .core-token 이 든 묶음은 폰으로 못 붙인다(PC y 만).
수준: 실수·과잉 자율(수준 1)을 막는다. 같은 사용자로 도는 프로그램이 일부러 돌아가는 것(수준 2)은 못 막는다(설계 §0 · §5 E).
묶음 꼴(run/pending/NN-이름.diff + .json · applied/)과 잠금(.lock)은 pending.py 와 같다. 이 파일은 비코어 대본을 가져오지 않는다.
사람이 PowerShell 5.1(cp949) 창에서 친다 - 출력은 짧은 한국어 · cp949 에 없는 글자를 안 쓴다 · 인코딩을 바꾸지 않는다.
"""
import argparse
import base64
import binascii
import contextlib
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
KEYS = os.path.join(HERE, "keys.txt")
# 장부(비코어 · git 밖). APPROVE_STATE = 시험용 자리 - 장부를 지우는 것과 같은 무게(설계 T5: 30분 안 되돌린 묶음 재전송만 열림).
STATE = os.environ.get("APPROVE_STATE") or os.path.join(VAULT, "3_시스템", "_index", "approve")  # mf:allow-path
LEDGER = os.path.join(STATE, "ledger.jsonl")
REQ_DIR = os.path.join(STATE, "register")
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
PURPOSE = "brain-approve/1 apply"
PAST, FUTURE = 30 * 60, 2 * 60      # 폰 시각 창(초) · 지금 -30분 ~ +2분
CHALLENGE_TTL = 30 * 60            # 도전값 수명(초)
MAX_IN = 64 * 1024                 # 서명 요청 글 상한(바이트)
MAX_REQ = 5                        # 받아 두는 등록 요청 수 상한
TOKEN_NAME = ".core-token"
# 게이트 코어 = 3_시스템/hooks/core-gate.ps1 의 $core 와 같은 자리(볼트 뿌리 기준 · 대소문자 무시) · pending.py 와 같다.  # mf:allow-path
GATE_CORE = re.compile(r"(^|/)CLAUDE\.md$|^3_시스템/hooks/|^3_시스템/search\.py$|^3_시스템/conventions\.md$"  # mf:allow-path
                       r"|^\.claude/settings\.json$|^\.obsidian/plugins/", re.I)
# 자기 제외 = 폰으로 못 붙이는 자리(승인 장치 · 게이트 자신 · 훅 등록) - PC y 로만.
SELF = re.compile(r"^3_시스템/hooks/approve/|^3_시스템/hooks/core-gate[^/]*$|^\.claude/settings(\.local)?\.json$"  # mf:allow-path
                  r"|(^|/)\.core-token[. ]*$", re.I)
# 목적·사유 · 명령 승인(11-20 approve-all · 설계 §9)
RUN_PURPOSE = "brain-approve/1 run"
PURPOSE_MAX, REASON_MAX = 40, 80   # 글자 수(NFC)
CMD_MAX = 2000                     # 명령 한 줄 상한(글자)
REQ_TTL = 12 * 3600                # 명령 요청 시효(초) - 올린 뒤 12시간
RUN_DEFAULT, RUN_MAX = 10 * 60, 30 * 60   # 명령 시간 상한(초)
FILE_MAX, FILES_MAX = 256 * 1024, 8       # 명령에 이름이 나온 파일 - 하나 상한 · 수 상한
OUT_MAX = 1024 * 1024              # 남기는 출력 상한(바이트)
ELEVATE = re.compile(r"-verb\s*:?\s*['\"]?runas|\brunas(\.exe)?\b|\bg?sudo(\.exe)?\b|\bstart-process\b[^;|]*-verb\b", re.I)
HIDDEN = re.compile(r"(?<!\S)[-/](e|ec|en|enc|enco\w*|encodedcommand)(?!\S)|frombase64string|invoke-expression|(?<![\w-])iex(?![\w-])"
                    r"|\[scriptblock\]::create|-encodedarguments", re.I)
# 명령 글에 나오면 안 되는 자리(게이트 코어 · 자기 제외 · 승인 장치) - 백슬래시를 / 로 바꾸고 대소문자 무시로 본다
CMD_NO = ("claude.md", "3_시스템/hooks", "3_시스템/search.py", "3_시스템/conventions.md", ".claude/settings",  # mf:allow-path
          ".obsidian/plugins", ".core-token", "core-gate", "approve.py", "pending.py apply", "_index/approve")  # mf:allow-path
SPKI_P256 = bytes.fromhex("3059301306072a8648ce3d020106082a8648ce3d030107034200")


class Refuse(Exception):
    """안 붙이는 까닭(사람에게 보이는 짧은 글)."""


# ── 바탕 ─────────────────────────────────────────────────
def sha(data):
    return hashlib.sha256(data).hexdigest()


def now_iso():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def bb_root():
    return os.environ.get("BIGBOSS_STATE") or os.path.join(VAULT, "3_시스템", "_index", "bigboss")  # mf:allow-path


def pend_dir(run):
    return os.path.join(bb_root(), re.sub(r"[^\w.-]", "-", run), "pending")


def git(repo, *args, data=None):
    """(코드, stdout 바이트, stderr 글)"""
    cmd = ["git"] + (["-C", repo] if repo else []) + list(args)
    try:
        r = subprocess.run(cmd, input=data, capture_output=True, creationflags=NO_WINDOW)
    except OSError as e:
        return 127, b"", f"git 을 못 돌림: {e}"
    return r.returncode, r.stdout, r.stderr.decode("utf-8", "replace")


def repo_root(path):
    if not path or not os.path.isdir(path):
        return None
    rc, out, _ = git(path, "rev-parse", "--show-toplevel")
    if rc:
        return None
    return os.path.normpath(out.decode("utf-8", "replace").strip())


def same(a, b):
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


def err_line(err):
    lines = [x.strip()[7:] if x.strip().startswith("error: ") else x.strip() for x in err.splitlines() if x.strip()]
    return " / ".join(lines[:2])[:200] or "까닭 모름"


def joined(diffs):
    return b"".join(d if d.endswith(b"\n") else d + b"\n" for d in diffs)


def load_json(path):
    for _ in range(50):
        try:
            with open(path, "rb") as f:
                return f.read()
        except PermissionError:
            time.sleep(0.1)
        except OSError:
            return None
    return None


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    move(tmp, path)


def move(src, dst):
    for i in range(50):
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if i == 49:
                raise
            time.sleep(0.1)


def out_json(obj):
    print(json.dumps(obj, ensure_ascii=True, separators=(",", ":")))


# ── 콘솔 ─────────────────────────────────────────────────
def console_in():
    """표준 입력이 사람이 치는 콘솔인가. 파이프·파일·NUL 은 아니다(윈도: 콘솔 입력 버퍼만 GetNumberOfConsoleInputEvents 가 된다)."""
    if sys.stdin is None:
        return False
    if os.name != "nt":
        try:
            return os.isatty(sys.stdin.fileno())
        except (OSError, ValueError, AttributeError):
            return False
    import ctypes
    import msvcrt
    from ctypes import wintypes
    try:
        h = msvcrt.get_osfhandle(sys.stdin.fileno())
    except (OSError, ValueError, AttributeError):
        return False
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.GetConsoleMode.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.GetNumberOfConsoleInputEvents.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    mode, n = wintypes.DWORD(), wintypes.DWORD()
    return bool(k.GetConsoleMode(h, ctypes.byref(mode)) and k.GetNumberOfConsoleInputEvents(h, ctypes.byref(n)))


def flush_typeahead():
    """묻기 전에 미리 쌓인 키를 버린다 - 묻는 말을 보고 친 것만 센다."""
    if os.name != "nt":
        return
    import ctypes
    import msvcrt
    from ctypes import wintypes
    try:
        k = ctypes.WinDLL("kernel32")
        k.FlushConsoleInputBuffer.argtypes = [wintypes.HANDLE]
        k.FlushConsoleInputBuffer(msvcrt.get_osfhandle(sys.stdin.fileno()))
    except Exception:
        pass


def is_yes(raw):
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    ans = ""
    for enc in (getattr(sys.stdin, "encoding", None) or "utf-8", "utf-8", "cp949"):
        try:
            ans = raw.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    return ans.strip().lower() in ("y", "yes", "ㅛ")  # ㅛ = 한글 자판에서 y


def ask(prompt="계속할까요? [y/N] "):
    """콘솔에서 직접 친 y 만 참. 파이프·파일 입력은 묻지도 않고 거짓."""
    if not console_in():
        print("안 붙임 - y 는 터미널에서 직접 친 것만 받는다(파이프·파일 입력은 거절)")
        return False
    flush_typeahead()
    print(prompt, end="", flush=True)
    try:
        raw = sys.stdin.buffer.readline()
    except Exception:
        raw = b""
    if not raw:
        print("(입력 없음)")
        return False
    return is_yes(raw)


def need_console(what):
    if console_in():
        return True
    print(f"안 함 - {what}: 사람이 터미널에서 직접 친다(파이프·파일 입력은 거절)")
    return False


# ── 장부 ─────────────────────────────────────────────────
def ledger():
    try:
        with open(LEDGER, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            j = json.loads(ln)
        except ValueError:
            continue
        if isinstance(j, dict):
            out.append(j)
    return out


def note(ev, **kw):
    os.makedirs(STATE, exist_ok=True)
    j = {"t": now_iso(), "at": int(time.time()), "ev": ev, **kw}
    with open(LEDGER, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(j, ensure_ascii=False, separators=(",", ":")) + "\n")


def frozen(led=None):
    """마지막 동결 기록이 마지막 풀기보다 뒤면 그 기록 · 아니면 None."""
    last = None
    for j in led if led is not None else ledger():
        if j.get("ev") == "freeze":
            last = j
        elif j.get("ev") == "unfreeze":
            last = None
    return last


# ── 묶음 (pending.py 와 같은 꼴) ─────────────────────────
def files_of(diff, repo=None):
    """[(경로들, +줄, -줄)] · git 이 읽은 대로(`git apply --numstat -z`) · 못 읽으면 (None, 까닭)."""
    rc, out, err = git(repo, "apply", "--numstat", "-z", data=diff)
    if rc:
        return None, err_line(err)
    toks, i, res = out.split(b"\0"), 0, []
    while i < len(toks):
        t = toks[i]
        i += 1
        parts = t.split(b"\t", 2)
        if len(parts) < 3:
            continue
        add, rem, p = parts
        if p:
            paths = [p]
        else:
            paths = toks[i:i + 2]
            i += 2
        res.append(([x.decode("utf-8", "replace") for x in paths], int(add) if add.isdigit() else 0, int(rem) if rem.isdigit() else 0))
    return res, ""


def bad_path(p):
    q = unicodedata.normalize("NFC", p)
    if not q or q.startswith(("/", "\\")) or "\\" in q or ":" in q:
        return f"저장소 밖·절대 경로: {p}"
    parts = q.split("/")
    if ".." in parts:
        return f"저장소 밖 경로(..): {p}"
    names = [x.rstrip(". ").casefold() for x in parts]
    if any(x == ".git" or x.startswith("git~") for x in names):
        return f".git 안 경로: {p}"
    if names[-1] == TOKEN_NAME:
        return f"토큰 파일은 도구가 고치지 않음: {p}"
    return None


def blocks_of(diff, repo):
    if not diff.strip():
        return ["빈 diff"]
    files, why = files_of(diff, repo)
    if files is None:
        return [f"diff 로 못 읽음 - {why}"]
    if not files:
        return ["바뀌는 파일이 없음"]
    out = [b for paths, _, _ in files for b in (bad_path(p) for p in paths) if b]
    rc, summ, _ = git(repo, "apply", "--summary", data=diff)
    if rc == 0 and re.search(rb"\b(120000|160000)\b", summ):
        out.append("링크·서브모듈을 만드는 diff")
    return out


def items(d, applied=False):
    out = []
    for f in [d] + ([os.path.join(d, "applied")] if applied else []):
        try:
            names = os.listdir(f)
        except OSError:
            continue
        for n in names:
            m = re.match(r"(\d+)-.*\.json$", n)
            if not m:
                continue
            raw = load_json(os.path.join(f, n))
            try:
                j = json.loads(raw.decode("utf-8")) if raw is not None else None
            except ValueError:
                j = None
            if not isinstance(j, dict) or j.get("state") not in ("pending", "applied"):
                continue
            j["_json"], j["_diff"], j["_nn"], j["_meta"] = os.path.join(f, n), os.path.join(f, n[:-5] + ".diff"), int(m.group(1)), raw
            out.append(j)
    return sorted(out, key=lambda j: j["_nn"])


def waiting(d):
    return [j for j in items(d) if j.get("state") == "pending"]


def read_diff(it):
    try:
        with open(it["_diff"], "rb") as f:
            return f.read()
    except OSError:
        return None


def by_repo(its):
    groups = {}
    for it in its:
        groups.setdefault(os.path.normcase(os.path.normpath(it.get("repo") or "")), []).append(it)
    return list(groups.values())


def alive(pid):
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes
    from ctypes import wintypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenProcess.restype = wintypes.HANDLE
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    h = k.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ctypes.get_last_error() == 5  # 접근 거부 = 있는 프로세스
    try:
        code = wintypes.DWORD()
        return not k.GetExitCodeProcess(h, ctypes.byref(code)) or code.value == 259  # STILL_ACTIVE
    finally:
        k.CloseHandle(h)


@contextlib.contextmanager
def locked(d):
    """pending.py 와 같은 잠금 파일(.lock) - 넣기·붙이기가 섞이지 않게."""
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, ".lock")
    for _ in range(100):
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                with open(p, encoding="utf-8") as f:
                    owner = int(f.read().strip() or 0)
                if not alive(owner):
                    os.remove(p)
                    continue
            except (OSError, ValueError):
                pass
            time.sleep(0.1)
    else:
        raise Refuse("묶음이 잠겨 있음(다른 pending.py·approve.py 가 도는 중) - 잠시 뒤 다시")
    try:
        yield
    finally:
        try:
            os.remove(p)
        except OSError:
            pass


def verify(its):
    """한 저장소 묶음을 붙이기 전에 잰다 · (저장소 뿌리, [diff], 까닭 또는 None)"""
    repo = its[0].get("repo") or ""
    root = repo_root(repo)
    if not root or not same(root, repo):
        return None, [], f"git 저장소가 아님: {repo}"
    diffs = []
    for it in its:
        data = read_diff(it)
        if data is None:
            return root, [], f"{it['_nn']:02d} diff 파일이 없음"
        if sha(data) != it.get("sha256"):
            return root, [], f"{it['_nn']:02d} sha 불일치 - 넣은 뒤 diff 가 바뀜(다시 넣을 것)"
        b = blocks_of(data, root)
        if b:
            return root, [], f"{it['_nn']:02d} 막음 - {b[0]}"
        diffs.append(data)
    return root, diffs, None


def stack_check(root, diffs):
    if not diffs:
        return -1, ""
    rc, _, err = git(root, "apply", "--check", data=joined(diffs))
    if rc == 0:
        return -1, ""
    for i in range(len(diffs)):
        rc, _, err = git(root, "apply", "--check", data=joined(diffs[:i + 1]))
        if rc:
            why = err_line(err)
            if git(root, "apply", "--check", "-R", data=diffs[i])[0] == 0:
                why += " (이미 붙어 있는 듯)"
            return i, why
    return len(diffs) - 1, err_line(err)


def mark_applied(d, it, by):
    j = {k: v for k, v in it.items() if not k.startswith("_")}
    j["state"], j["applied_at"], j["applied_by"] = "applied", now_iso(), by
    save_json(it["_json"], j)  # 먼저 상태를 적는다 · 옮기기가 막혀도 다시 붙이지 않는다
    to = os.path.join(d, "applied")
    os.makedirs(to, exist_ok=True)
    for p in (it["_diff"], it["_json"]):
        try:
            move(p, os.path.join(to, os.path.basename(p)))
        except OSError:
            pass


def paths_of(diffs, root):
    files, _ = files_of(joined(diffs), root)
    return sorted({p for paths, _, _ in files or [] for p in paths})


def pre_state(root, diffs):
    """적용 전 파일 상태 = 닿는 경로마다 '경로 TAB 지금 blob(없으면 -)' 줄(경로 순) · 바이트."""
    paths = paths_of(diffs, root)
    have = [p for p in paths if os.path.isfile(os.path.join(root, *p.split("/")))]
    blobs = {}
    if have:
        rc, out, err = git(root, "hash-object", "--no-filters", "--stdin-paths", data="".join(p + "\n" for p in have).encode("utf-8"))
        if rc:
            raise Refuse(f"파일 상태를 못 잼 - {err_line(err)}")
        got = out.decode("ascii", "replace").split()
        if len(got) != len(have):
            raise Refuse("파일 상태를 못 잼 - 해시 수가 다름")
        blobs = dict(zip(have, got))
    return "".join(f"{p}\t{blobs.get(p, '-')}\n" for p in paths).encode("utf-8")


# ── 서명 글 ──────────────────────────────────────────────
def message(root, run, group, diffs, pre, challenge, ms, key):
    lines = [PURPOSE, f"repo: {root}", f"run: {run}"]
    lines += [f"item: {it['_nn']} {sha(d)} {sha(it['_meta'])}" for it, d in zip(group, diffs)]
    lines += [f"all: {sha(joined(diffs))}", f"pre: {sha(pre)}", f"challenge: {challenge}", f"time: {ms}", f"key: {key}"]
    return ("\n".join(lines) + "\n").encode("utf-8")


def parse_message(msg):
    try:
        text = msg.decode("utf-8")
    except UnicodeDecodeError:
        raise Refuse("서명 글이 UTF-8 이 아님")
    lines = text.split("\n")
    if not text.endswith("\n") or lines[0] != PURPOSE:
        raise Refuse("서명 글의 용도가 다름")
    f = {}
    for ln in lines[1:-1]:
        k, sep, v = ln.partition(": ")
        if not sep:
            raise Refuse("서명 글 꼴이 다름")
        if k != "item":
            if k in f:
                raise Refuse(f"서명 글에 {k} 가 둘")
            f[k] = v
    for k in ("repo", "run", "all", "pre", "challenge", "time", "key"):
        if k not in f:
            raise Refuse(f"서명 글에 {k} 가 없음")
    if not re.fullmatch(r"[0-9a-f]{64}", f["challenge"]) or not re.fullmatch(r"\d{1,16}", f["time"]) or not re.fullmatch(r"[0-9a-f]{16}", f["key"]):
        raise Refuse("서명 글의 값 꼴이 다름")
    if not ok_run(f["run"]):
        raise Refuse("서명 글의 run 꼴이 다름")
    return f


def ok_run(run):
    return bool(re.fullmatch(r"[\w-][\w.-]{0,63}", run or "")) and ".." not in run


def line_why(name, text, cap):
    """한 줄 글(목적·사유) 검사 · 까닭 또는 None."""
    if not isinstance(text, str) or not text.strip():
        return f"{name}이 비었음"
    t = unicodedata.normalize("NFC", text)
    if any(unicodedata.category(c).startswith("C") for c in t):
        return f"{name}에 줄바꿈·제어 글자"
    if t != t.strip():
        return f"{name} 앞뒤에 빈칸"
    if len(t) > cap:
        return f"{name}이 {cap}자를 넘음({len(t)}자)"
    return None


def pr_why(purpose, reason):
    """목적(40자)·사유(80자) - 모든 승인(묶음 meta · 명령 요청)에 든다 · 비거나 넘으면 거절(11-20 사용자 «승인은 짧은 목적 및 사유를 담아줘»)."""
    return line_why("목적", purpose, PURPOSE_MAX) or line_why("사유", reason, REASON_MAX)


# ── 키 ───────────────────────────────────────────────────
def key_id(spki):
    return sha(spki)[:16]


def pair_code(spki):
    """짝 숫자 6자리 - 폰 승인 앱이 같은 식으로 잰다(공개 키 sha256 앞 8바이트의 수 % 1000000)."""
    return f"{int.from_bytes(hashlib.sha256(spki).digest()[:8], 'big') % 1000000:06d}"


def check_spki(spki):
    if len(spki) != 91 or not spki.startswith(SPKI_P256) or spki[26] != 4:
        raise Refuse("공개 키가 EC P-256 X.509 꼴이 아님")
    return spki


def read_keys():
    """{키 id: (spki, 등록 때, 이름)} · 줄 꼴 = <키 id> <spki base64> <등록 때(YYYY-MM-DDTHH:MM:SS)> <이름…>"""
    try:
        with open(KEYS, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return {}
    out = {}
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split(" ", 3)
        if len(parts) < 3:
            continue
        try:
            spki = check_spki(base64.b64decode(parts[1], validate=True))
        except (Refuse, binascii.Error, ValueError):
            continue
        if key_id(spki) != parts[0]:
            continue
        out[parts[0]] = (spki, parts[2], parts[3] if len(parts) > 3 else "")
    return out


def write_keys(lines):
    tmp = f"{KEYS}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    move(tmp, KEYS)


def der_to_rs(sig):
    """ECDSA DER(안드로이드 Signature 가 내는 꼴) -> r‖s 64바이트(CNG 가 받는 꼴)."""
    if len(sig) < 8 or len(sig) > 72 or sig[0] != 0x30 or sig[1] != len(sig) - 2:
        raise Refuse("서명 꼴(DER)이 다름")
    i, out = 2, b""
    for _ in range(2):
        if i + 2 > len(sig) or sig[i] != 0x02:
            raise Refuse("서명 꼴(DER)이 다름")
        n = sig[i + 1]
        v = sig[i + 2:i + 2 + n]
        i += 2 + n
        if n == 0 or n > 33 or len(v) != n or v[0] & 0x80 or (n > 1 and v[0] == 0 and not v[1] & 0x80):
            raise Refuse("서명 꼴(DER)이 다름")
        v = v.lstrip(b"\0")
        if not v or len(v) > 32:
            raise Refuse("서명 값이 범위 밖")
        out += v.rjust(32, b"\0")
    if i != len(sig):
        raise Refuse("서명 꼴(DER)이 다름")
    return out


def ecdsa_ok(spki, msg, sig_der):
    """P-256 ECDSA(SHA-256) 검증 - 윈도 CNG(bcrypt.dll) · 외부 의존성 없음. 못 재면 Refuse(안 붙임)."""
    if os.name != "nt":
        raise Refuse("서명을 잴 수 없음(윈도 CNG 없음)")
    import ctypes
    from ctypes import wintypes
    rs = der_to_rs(sig_der)
    pt = check_spki(spki)[27:]
    blob = (0x31534345).to_bytes(4, "little") + (32).to_bytes(4, "little") + pt  # BCRYPT_ECDSA_PUBLIC_P256_MAGIC · cbKey
    digest = hashlib.sha256(msg).digest()
    b = ctypes.WinDLL("bcrypt.dll")
    H = ctypes.c_void_p
    b.BCryptOpenAlgorithmProvider.argtypes = [ctypes.POINTER(H), wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.ULONG]
    b.BCryptImportKeyPair.argtypes = [H, H, wintypes.LPCWSTR, ctypes.POINTER(H), ctypes.c_char_p, wintypes.ULONG, wintypes.ULONG]
    b.BCryptVerifySignature.argtypes = [H, H, ctypes.c_char_p, wintypes.ULONG, ctypes.c_char_p, wintypes.ULONG, wintypes.ULONG]
    b.BCryptDestroyKey.argtypes = [H]
    b.BCryptCloseAlgorithmProvider.argtypes = [H, wintypes.ULONG]
    for f in (b.BCryptOpenAlgorithmProvider, b.BCryptImportKeyPair, b.BCryptVerifySignature, b.BCryptDestroyKey, b.BCryptCloseAlgorithmProvider):
        f.restype = ctypes.c_long
    alg, key = H(), H()
    if b.BCryptOpenAlgorithmProvider(ctypes.byref(alg), "ECDSA_P256", None, 0) != 0:
        raise Refuse("서명을 잴 수 없음(CNG 열기)")
    try:
        if b.BCryptImportKeyPair(alg, None, "ECCPUBLICBLOB", ctypes.byref(key), blob, len(blob), 0) != 0:
            raise Refuse("공개 키를 못 읽음(CNG)")
        try:
            st = b.BCryptVerifySignature(key, None, digest, len(digest), rs, len(rs), 0)
        finally:
            b.BCryptDestroyKey(key)
    finally:
        b.BCryptCloseAlgorithmProvider(alg, 0)
    if st == 0:
        return True
    if st & 0xFFFFFFFF == 0xC000A000:  # STATUS_INVALID_SIGNATURE
        return False
    raise Refuse(f"서명을 잴 수 없음(CNG {st & 0xFFFFFFFF:08x})")


# ── 볼트 묶음 고르기 ────────────────────────────────────
def vault_group(run):
    """이 run 의 볼트 저장소 대기 항목(번호 순) · 볼트 아니면 폰 승인 대상이 아님."""
    root = repo_root(VAULT)
    if not root:
        raise Refuse("볼트가 git 저장소가 아님")
    group = [it for it in waiting(pend_dir(run)) if same(it.get("repo") or "", root)]
    return root, group


def bundle(run):
    """(뿌리, 항목, diff, 자기 제외 경로, 코어 경로) · 못 붙는 묶음이면 Refuse."""
    root, group = vault_group(run)
    if not group:
        raise Refuse("볼트 대기 없음")
    root2, diffs, why = verify(group)
    if why:
        raise Refuse(why)
    for it in group:
        w = pr_why(it.get("purpose"), it.get("reason"))
        if w:
            raise Refuse(f"{it['_nn']:02d} {w} - pending.py fill 로 채움")
    i, why = stack_check(root, diffs)
    if i >= 0:
        raise Refuse(f"{group[i]['_nn']:02d} 에서 막힘 - {why}")
    paths = paths_of(diffs, root)
    return root, group, diffs, [p for p in paths if SELF.search(p)], [p for p in paths if GATE_CORE.search(p)]


# ── 명령 승인(사용자 권한 한 줄 · 11-20 approve-all · 설계 §9.3) ─────────
# 요청 = <bigboss>/<run>/commands/NN-이름.json (pending.py cmd 가 쓴다 · 비코어 · 안 믿음) - 믿는 것은 이 파일이 서명 글을 다시 만들어 견주는 것뿐.
def cmd_dir(run):
    return os.path.join(bb_root(), re.sub(r"[^\w.-]", "-", run), "commands")


def cmd_items(run):
    d, out = cmd_dir(run), []
    try:
        names = os.listdir(d)
    except OSError:
        return []
    for n in names:
        m = re.match(r"(\d+)-.*\.json$", n)
        if not m:
            continue
        raw = load_json(os.path.join(d, n))
        try:
            j = json.loads(raw.decode("utf-8")) if raw is not None else None
        except (ValueError, UnicodeDecodeError):
            j = None
        if isinstance(j, dict):
            j["_json"], j["_nn"], j["_raw"] = os.path.join(d, n), int(m.group(1)), raw
            out.append(j)
    return sorted(out, key=lambda j: j["_nn"])


def cmd_item(run, nn):
    for j in cmd_items(run):
        if j["_nn"] == nn:
            return j
    raise Refuse(f"명령 요청 {nn:02d} 이 없음")


def cmd_waiting(run, now=None):
    now = now or time.time()
    return [j for j in cmd_items(run) if j.get("state") == "pending" and now - int(j.get("added_at") or 0) <= REQ_TTL]


def cmd_text_why(cmd, cwd):
    """명령 글·작업 폴더 검사 · 까닭 또는 None(pending.py 가 넣을 때도 같은 규칙을 쓴다 · 믿는 쪽은 여기)."""
    if not isinstance(cmd, str) or not cmd.strip():
        return "명령이 비었음"
    if any(unicodedata.category(c).startswith("C") for c in cmd):
        return "명령에 줄바꿈·제어 글자(한 줄만)"
    if cmd != cmd.strip():
        return "명령 앞뒤에 빈칸"
    if len(cmd) > CMD_MAX:
        return f"명령이 {CMD_MAX}자를 넘음({len(cmd)}자)"
    if ELEVATE.search(cmd):
        return "관리자 승격이 든 명령(관리자 일은 정해 둔 조리법만)"
    if HIDDEN.search(cmd):
        return "숨긴 명령(인코딩·동적 실행) - 그대로 읽히는 글만"
    low = cmd.replace("\\", "/").lower()
    bad = next((x for x in CMD_NO if x in low), None)
    if bad:
        return f"게이트 코어·승인 장치 자리가 든 명령({bad}) - 코어는 묶음으로"
    # 글자 대조를 비켜 가는 꼴(검증 11-20 (c)): 와일드카드·글 이어 붙이기가 경로 꼴과 함께 나오면 거절
    pathy = bool(re.search(r"[\\/]|\.\.|\b[A-Za-z]:", cmd))
    for rx, why in SNEAK:     # 글자 검사를 비켜 가는 꼴(재검증 11-20) - 다 막지는 못함 · 사후 sha 표시가 뒤를 받침
        if rx.search(cmd) and (pathy or rx is not SNEAK[1][0]):
            return why
    if pathy and WILD.search(cmd):
        return "경로와 와일드카드(* ? [ ])가 함께 든 명령 - 경로를 그대로 적음"
    if pathy and JOIN.search(cmd):
        return "경로와 글 이어 붙이기(+ · -join · -f · -replace · Join-Path)가 함께 든 명령 - 경로를 그대로 적음"
    if not isinstance(cwd, str) or not os.path.isabs(cwd) or not os.path.isdir(cwd):
        return "작업 폴더가 없음(절대 경로)"
    lowd = os.path.normpath(cwd).replace("\\", "/").lower() + "/"
    bad = next((x for x in CMD_NO if x.rstrip("/") + "/" in lowd or lowd.endswith("/" + x + "/")), None)
    if bad:
        return f"작업 폴더가 게이트 코어·승인 장치 자리({bad})"
    for t in cmd_tokens(cmd):  # 작업 폴더 기준 상대 경로로 코어를 가리킴(cwd=3_시스템 · hooks/x)
        p = os.path.normpath(t if os.path.isabs(t) else os.path.join(cwd, t))
        rel = os.path.relpath(p, VAULT).replace("\\", "/") if same(os.path.splitdrive(p)[0], os.path.splitdrive(VAULT)[0]) else ""
        if rel and not rel.startswith("..") and (GATE_CORE.search(rel) or SELF.search(rel) or GATE_CORE.search(rel + "/x")):
            return f"게이트 코어·승인 장치 자리를 가리키는 명령({rel}) - 코어는 묶음으로"
    return None


TOKEN = re.compile(r'"([^"]*)"|\'([^\']*)\'|(\S+)')
WILD = re.compile(r"[*?]|\[[^\]]*\](?!::)")                 # [Type]:: 는 .NET 형식(와일드카드 아님)
JOIN = re.compile(r"[\"')]\s*\+|\+\s*[\"'($]|\$\w+\s*\+|-join\b|-f\b|-replace\b|\bjoin-path\b|\[io\.path\]::combine", re.I)
SNEAK = [
    (re.compile(r"\w`\w|\w(?:''|\"\")\w"), "낱말 안에 백틱·빈 따옴표(글자 검사 비켜 가기) - 그대로 적음"),
    (re.compile(r"\$\{?\w+\}?\s*=(?!=)"), "경로와 변수 대입이 함께 든 명령 - 경로를 그대로 적음"),
    (re.compile(r"(?<![\w-])(cd|chdir|sl|pushd|popd|set-location|push-location)(?![\w-])|\bgit\b[^;|&]*\s-C\s", re.I),
     "작업 폴더를 바꾸는 명령(cd·Set-Location·pushd·git -C) - 작업 폴더를 --cwd 로"),
    (re.compile(r"\bmklink\b|-itemtype\s+['\"]?(junction|symboliclink|hardlink)\b|\bnew-item\b[^;|]*\b(junction|symboliclink|hardlink)\b", re.I),
     "접합점·링크 만들기(mklink · Junction · SymbolicLink)"),
    (re.compile(r"\w~\d"), "8.3 짧은 이름 꼴(~숫자) - 긴 경로를 그대로 적음"),
]
SCRIPT_EXT = (".ps1", ".psm1", ".psd1", ".py", ".pyw", ".cmd", ".bat", ".js", ".mjs", ".cjs", ".vbs", ".sh")
DIR_FILES, DIR_BYTES = 300, 8 * 1024 * 1024   # 대본 폴더 통째 묶음 상한


def cmd_tokens(cmd):
    out = []
    for m in TOKEN.finditer(cmd):
        t = next(g for g in m.groups() if g is not None).strip().rstrip(";,)")
        if re.match(r"-\w+:", t):  # -File:경로
            t = t.split(":", 1)[1]
        if t and len(t) <= 260 and not any(c in t for c in '<>|*?"'):
            out.append(t.lstrip("&.") if t.startswith(("&.\\", "&./")) else t)
    return out


INTERP = {"py": (".py", ".pyw"), "python": (".py", ".pyw"), "pythonw": (".py", ".pyw"), "python3": (".py",),
          "node": (".js", ".mjs", ".cjs"), "bash": (".sh",), "sh": (".sh",), "wscript": (".vbs", ".js"), "cscript": (".vbs", ".js"),
          "&": (".ps1", ".cmd", ".bat"), ".": (".ps1",)}


def interp_args(cmd):
    """[(대본 자리 낱말, 후보 확장자)] - 실행기마다 정한 자리만 본다(값 인자를 대본으로 오인하지 않게):
    py·python·node·bash 는 플래그 뒤 첫 낱말(-m·-c·-e 면 없음) · powershell·pwsh 는 -File 뒤 · cmd 는 /c·/k 뒤 · & · . 는 바로 뒤."""
    toks = [next(g for g in m.groups() if g is not None) for m in TOKEN.finditer(cmd)]
    out = []
    for i, t in enumerate(toks):
        name = os.path.basename(t.lower())
        name = name[:-4] if name.endswith(".exe") else name
        if name in ("powershell", "pwsh"):
            for j in range(i + 1, len(toks) - 1):
                if toks[j].lower() in ("-file", "-f"):
                    out.append((toks[j + 1], (".ps1",)))
                    break
        elif name == "cmd":
            for j in range(i + 1, len(toks) - 1):
                if toks[j].lower() in ("/c", "/k"):
                    out.append((toks[j + 1], (".cmd", ".bat")))
                    break
        elif name in INTERP and (i == 0 or toks[i - 1].endswith((";", "|", "&&", "||"))):
            j = i + 1
            while j < len(toks) and toks[j].startswith("-") and name not in ("&", "."):
                if toks[j] in ("-m", "-c", "-e", "--eval", "-p", "--print"):
                    j = len(toks)
                    break
                j += 1
            if j < len(toks) and not toks[j].startswith(("-", "$", "(")) and re.fullmatch(r"[^;|&<>]+", toks[j]):
                out.append((toks[j], INTERP[name]))
    return out


def script_dir_files(d):
    """대본이 있는 폴더(하위 포함)의 대본 파일들 · _·. 로 시작하는 폴더·__pycache__·node_modules 는 뺌 · 상한 넘으면 Refuse."""
    out, total = [], 0
    for root, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if not x.startswith(("_", ".")) and x != "node_modules")
        for f in sorted(files):
            if f.lower().endswith(SCRIPT_EXT):
                p = os.path.join(root, f)
                total += os.path.getsize(p)
                out.append(p)
                if len(out) > DIR_FILES or total > DIR_BYTES:
                    raise Refuse(f"대본 폴더가 커서 묶지 못함({d} · {DIR_FILES}개·{DIR_BYTES // 1048576}MB 상한)")
    return out


def cmd_files(cmd, cwd):
    """서명 글이 내용 sha 를 덮는 파일들 [(절대 경로, 바이트, 이름이 나왔나)] (검증 11-20 (a)):
    명령에 이름이 나온 파일 + 그것이 대본이면 그 폴더(하위 포함)의 대본 전부(dot-source·import 로 부르는 파일).
    대본 꼴(확장자) 이름인데 파일이 없으면 거절 - 승인 뒤에 만든 내용이 돌 수 있다."""
    named = []
    for t in cmd_tokens(cmd):
        p = os.path.normpath(t if os.path.isabs(t) else os.path.join(cwd, t))
        try:
            isf = os.path.isfile(p)
        except (OSError, ValueError):
            isf = False
        if isf:
            if not any(same(p, q) for q in named):
                named.append(p)
        elif t.lower().endswith(SCRIPT_EXT) and re.search(r"[\\/]|^[\w.-]+\.\w+$", t):
            raise Refuse(f"명령에 나온 대본이 없음({t}) - 있는 대본만 승인")
    for t, exts in interp_args(cmd):   # 실행기 뒤 확장자 없는 대본(node x · py x · cmd /c x) - 후보 확장자를 붙여 찾고, 없으면 거절
        p = os.path.normpath(t if os.path.isabs(t) else os.path.join(cwd, t))
        if os.path.isfile(p):
            continue
        hit = next((p + e for e in exts if os.path.isfile(p + e)), None)
        if not hit:
            raise Refuse(f"실행기 뒤 대본을 못 찾음({t}) - 있는 대본만 승인")
        if not any(same(hit, q) for q in named):
            named.append(hit)
    if len(named) > FILES_MAX:
        raise Refuse(f"이름이 나온 파일이 {FILES_MAX}개를 넘음")
    allp = list(named)
    for p in named:
        if p.lower().endswith(SCRIPT_EXT):
            for q in script_dir_files(os.path.dirname(p)):
                if not any(same(q, x) for x in allp):
                    allp.append(q)
    out = []
    for p in allp:
        with open(p, "rb") as f:
            data = f.read(FILE_MAX + 1 if p in named else DIR_BYTES + 1)
        if p in named and len(data) > FILE_MAX:
            raise Refuse(f"이름이 나온 파일이 {FILE_MAX // 1024}KB 를 넘음: {os.path.basename(p)}")
        out.append((p, data, p in named))
    return out


@contextlib.contextmanager
def hold(paths):
    """파일을 «읽기만 함께 · 쓰기·지우기·이름 바꾸기 금지»로 열어 둔다(검증 11-20 (a)②: 잰 뒤 실행 전에 바꿔치기 막기).
    잡는 동안 재고(run_verify) 돌리고, 명령이 끝날 때까지 놓지 않는다 · 하나라도 못 잡으면 Refuse."""
    hs = []
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateFileW.restype = wintypes.HANDLE
        k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        try:
            for p in paths:
                h = k.CreateFileW(p, 0x80000000, 0x1, None, 3, 0, None)  # GENERIC_READ · FILE_SHARE_READ 만 · OPEN_EXISTING
                if h in (None, wintypes.HANDLE(-1).value):
                    raise Refuse(f"묶을 파일을 못 잠금({os.path.basename(p)} · 다른 프로그램이 쓰는 중?)")
                hs.append(h)
            yield
        finally:
            for h in hs:
                k.CloseHandle(h)
    else:
        yield


USED = os.path.join(HERE, "used")   # 쓴 명령 도전값 기록(자기 제외 폴더 안 · 게이트 코어 · 검증 11-20 (b))


def mark_used(challenge, rec):
    """도전값 하나를 한 번만 쓴다 - used/<도전값> 을 배타 생성(있으면 Refuse) · 자리가 없으면(지워짐) 실행 거절."""
    if not os.path.isdir(USED) or not os.path.isfile(os.path.join(USED, ".gitignore")):
        raise Refuse("쓴 도전값 기록 자리가 없음(3_시스템/hooks/approve/used) - 실행 안 함")  # mf:allow-path
    try:
        fd = os.open(os.path.join(USED, challenge), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise Refuse("이미 쓴 도전값(한 번만)")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False))


def used(challenge):
    return os.path.exists(os.path.join(USED, challenge))


def req_timeout(it):
    t = it.get("timeout", RUN_DEFAULT)
    return t if isinstance(t, int) and not isinstance(t, bool) and 1 <= t <= RUN_MAX else None


def req_why(it, now=None):
    now = now or time.time()
    if it.get("state") != "pending":
        return f"명령 요청이 대기가 아님({it.get('state')})"
    if now - int(it.get("added_at") or 0) > REQ_TTL:
        return f"명령 요청이 시효({REQ_TTL // 3600}시간)를 넘김 - 다시 올림"
    if it.get("shell") != "powershell":
        return "셸이 powershell 이 아님"
    if req_timeout(it) is None:
        return f"시간 상한 꼴이 다름(1~{RUN_MAX}초)"
    return pr_why(it.get("purpose"), it.get("reason")) or cmd_text_why(it.get("cmd"), it.get("cwd"))


def run_message(run, nn, it, files, challenge, ms, key):
    lines = [RUN_PURPOSE, f"run: {run}", f"id: {nn}", f"purpose: {it['purpose']}", f"reason: {it['reason']}",
             "shell: powershell", f"cwd: {it['cwd']}", f"cmd: {it['cmd']}"]
    lines += [f"file: {sha(d)} {p}" for p, d, _ in files]
    lines += [f"timeout: {req_timeout(it)}", f"req: {sha(it['_raw'])}", f"challenge: {challenge}", f"time: {ms}", f"key: {key}"]
    return ("\n".join(lines) + "\n").encode("utf-8")


def parse_run_message(msg):
    try:
        text = msg.decode("utf-8")
    except UnicodeDecodeError:
        raise Refuse("서명 글이 UTF-8 이 아님")
    lines = text.split("\n")
    if not text.endswith("\n") or lines[0] != RUN_PURPOSE:
        raise Refuse("서명 글의 용도가 다름")
    f = {}
    for ln in lines[1:-1]:
        k, sep, v = ln.partition(": ")
        if not sep:
            raise Refuse("서명 글 꼴이 다름")
        if k != "file":
            if k in f:
                raise Refuse(f"서명 글에 {k} 가 둘")
            f[k] = v
    for k in ("run", "id", "purpose", "reason", "shell", "cwd", "cmd", "timeout", "req", "challenge", "time", "key"):
        if k not in f:
            raise Refuse(f"서명 글에 {k} 가 없음")
    if not re.fullmatch(r"[0-9a-f]{64}", f["challenge"]) or not re.fullmatch(r"\d{1,16}", f["time"]) \
            or not re.fullmatch(r"[0-9a-f]{16}", f["key"]) or not re.fullmatch(r"\d{1,4}", f["id"]):
        raise Refuse("서명 글의 값 꼴이 다름")
    if not ok_run(f["run"]):
        raise Refuse("서명 글의 run 꼴이 다름")
    return f


def run_verify(msg, sig):
    """명령 승인 서명을 끝까지 잰다 · (글 칸, 요청, 파일, 서명 sha). 실행 직전(run-exec)에도 처음부터 다시 잰다."""
    f = parse_run_message(msg)
    keys = read_keys()
    if f["key"] not in keys:
        raise Refuse("키 목록에 없는 키")
    if not ecdsa_ok(keys[f["key"]][0], msg, sig):
        raise Refuse("서명이 맞지 않음")
    ms, now = int(f["time"]), time.time()
    if not (now - PAST <= ms / 1000 <= now + FUTURE):
        raise Refuse("폰 시각이 창 밖(지금 -30분 ~ +2분) - 다시 받아 승인")
    led = ledger()
    if frozen(led):
        raise Refuse("폰 승인 얼어 있음('내가 안 시킴') - PC 에서 approve.py unfreeze")
    sigsha, nn = sha(sig), int(f["id"])
    if used(f["challenge"]) or any(j.get("ev") == "run-start" and (j.get("sig") == sigsha or j.get("challenge") == f["challenge"]) for j in led):
        raise Refuse("이미 쓴 서명·도전값(한 번만)")
    ch = [j for j in led if j.get("ev") == "challenge" and j.get("challenge") == f["challenge"]]
    if not ch:
        raise Refuse("PC 가 낸 도전값이 아님")
    c = ch[-1]
    if c.get("kind") != "run" or c.get("run") != f["run"] or c.get("id") != nn:
        raise Refuse("도전값이 이 명령 요청 것이 아님")
    if now - int(c.get("at") or 0) > CHALLENGE_TTL:
        raise Refuse("도전값이 만료됨(30분) - 다시 받아 승인")
    it = cmd_item(f["run"], nn)
    why = req_why(it, now)
    if why:
        raise Refuse(why)
    if c.get("req") != sha(it["_raw"]):
        raise Refuse("도전값을 낸 뒤 명령 요청이 바뀜")
    files = cmd_files(it["cmd"], it["cwd"])
    want = run_message(f["run"], nn, it, files, f["challenge"], f["time"], f["key"])
    if want != msg:
        got_l, want_l = msg.decode("utf-8").split("\n"), want.decode("utf-8").split("\n")
        diff_k = next((w.split(":")[0] for g, w in zip(got_l, want_l) if g != w), "파일 수")
        raise Refuse(f"승인한 것과 지금 명령이 다름({diff_k})")
    return f, it, files, sigsha


def b64(b):
    return base64.b64encode(b).decode()


def cmd_challenge_cmd(a):
    if not ok_run(a.run):
        out_json({"ok": False, "why": "run 꼴이 다름"})
        return 1
    led = ledger()
    fz = bool(frozen(led))
    try:
        it = cmd_item(a.run, a.nn)
        why = req_why(it)
        if why:
            raise Refuse(why)
        files = cmd_files(it["cmd"], it["cwd"])
    except Refuse as e:
        out_json({"ok": False, "why": str(e), "frozen": fz})
        return 1
    obj = {"ok": True, "purpose": RUN_PURPOSE, "run": a.run, "id": a.nn, "frozen": fz, "req": b64(it["_raw"]),
           "files": [dict({"path": p, "sha": sha(d)}, **({"data": b64(d)} if nm else {})) for p, d, nm in files],
           "rejected_before": any(j.get("ev") == "reject-cmd" and j.get("req") == sha(it["_raw"]) for j in led)}
    if not fz:
        ch = secrets.token_hex(32)
        note("challenge", kind="run", run=a.run, id=a.nn, req=sha(it["_raw"]), challenge=ch)
        obj.update(challenge=ch, expires=int(time.time()) + CHALLENGE_TTL)
    out_json(obj)
    return 0


def cmd_check_cmd(a):
    """pending.py cmd 가 올린 직후 부른다 - 도전값 없이 같은 규칙만 잰다(폰에 보내기 전 거르기)."""
    try:
        it = cmd_item(a.run, a.nn)
        why = req_why(it)
        if why:
            raise Refuse(why)
        files = cmd_files(it["cmd"], it["cwd"])
    except Refuse as e:
        out_json({"ok": False, "why": str(e)})
        return 1
    out_json({"ok": True, "files": [p for p, _, nm in files if nm], "bound": len(files)})
    return 0


def save_req(it, **kw):
    j = {k: v for k, v in it.items() if not k.startswith("_")}
    j.update(kw)
    save_json(it["_json"], j)


def run_signed(msg, sig):
    """폰 서명 → 재고 → 서명을 남기고 실행기(run-exec)를 창 없이 띄운다 · 실행기가 처음부터 다시 잰다."""
    f, it, files, sigsha = run_verify(msg, sig)
    nn = int(f["id"])
    sd = os.path.join(STATE, "signed")
    os.makedirs(sd, exist_ok=True)
    path = os.path.join(sd, f"{f['run']}-{nn:02d}-{sigsha[:16]}.json")
    save_json(path, {"message": b64(msg), "sig": b64(sig)})
    note("run-ok", run=f["run"], id=nn, challenge=f["challenge"], sig=sigsha, key=f["key"])
    args = [sys.executable, os.path.abspath(__file__), "run-exec", path]
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True, cwd=VAULT)
    flags = NO_WINDOW | 0x00000200  # 새 프로세스 묶음 - 서버가 답을 받고 끝나도 산다
    try:
        subprocess.Popen(args, creationflags=flags | 0x01000000, **kw)  # 작업 개체 밖으로(되면)
    except OSError:
        subprocess.Popen(args, creationflags=flags, **kw)
    return {"ok": True, "started": True, "run": f["run"], "id": nn, "key": f["key"]}


CORE_ARGS = ["CLAUDE.md", "3_시스템/hooks", "3_시스템/search.py", "3_시스템/conventions.md", ".claude/settings.json", ".obsidian/plugins"]  # mf:allow-path


CORE_WALK = ["3_시스템/hooks", ".obsidian/plugins"]  # mf:allow-path  폴더째(하위 · 무시 파일 포함)
CORE_ONE = ["CLAUDE.md", "3_시스템/search.py", "3_시스템/conventions.md", ".claude/settings.json"]  # mf:allow-path
CORE_MAX = 512 * 1024 * 1024   # 재는 바이트 상한(넘으면 나머지는 이름·크기·시각만)


def walk_error(e):
    raise e


def core_state():
    """게이트 코어 여섯 자리의 파일 목록 + 내용 sha 를 git 없이 직접 잰다(재검증 11-20 · .gitignore 가 가리는
    .obsidian/plugins·hooks/__pycache__ 까지) - 명령 앞뒤로 견주어 바뀌면 결과 맨 위 + 폰 급알림. 못 재면 None(= 바뀜으로 봄)."""
    files = [os.path.join(VAULT, *r.split("/")) for r in CORE_ONE]
    try:
        rc, out, _ = git(VAULT, "ls-files", "-z", "-c", "-o", "--", ":(glob)**/CLAUDE.md")
        if rc == 0:
            files += [os.path.join(VAULT, *x.decode("utf-8", "replace").split("/")) for x in out.split(b"\0") if x]
        for r in CORE_WALK:
            top = os.path.join(VAULT, *r.split("/"))
            if not os.path.isdir(top):
                continue
            for root, dirs, fs in os.walk(top, onerror=walk_error):   # 읽기 오류 = 못 잼 = «바뀜»(11-20 · 조용히 건너뛰지 않음)
                dirs.sort()
                files += [os.path.join(root, f) for f in sorted(fs)]
        h, done = hashlib.sha256(), 0
        for fp in sorted(set(os.path.normcase(os.path.normpath(x)) for x in files)):
            if not os.path.isfile(fp):
                continue
            st = os.stat(fp)
            h.update(f"{fp}\0{st.st_size}\0".encode("utf-8"))
            if done + st.st_size <= CORE_MAX:
                with open(fp, "rb") as fh:
                    h.update(hashlib.sha256(fh.read()).digest())
                done += st.st_size
            else:
                h.update(str(st.st_mtime_ns).encode())
        return h.hexdigest()
    except OSError:
        return None


def decode_out(b):
    for enc in ("utf-8", "cp949"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def kill_tree(pid):
    try:
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True, creationflags=NO_WINDOW, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        pass


def cmd_run_exec(a):
    try:
        with open(a.file, "rb") as fh:
            j = json.loads(fh.read(MAX_IN * 2).decode("utf-8"))
        msg, sig = base64.b64decode(j["message"], validate=True), base64.b64decode(j["sig"], validate=True)
    except (OSError, ValueError, KeyError, TypeError, binascii.Error, UnicodeDecodeError):
        note("run-refuse", why="서명 파일을 못 읽음")
        return 1
    held = contextlib.ExitStack()
    try:
        ff = parse_run_message(msg)
        it0 = cmd_item(ff["run"], int(ff["id"]))
        why = req_why(it0)
        if why:
            raise Refuse(why)
        # 묶을 파일을 먼저 잠그고(쓰기·지우기 금지) 그 상태에서 처음부터 다시 잰다 - 잰 내용 = 도는 내용(검증 11-20 (a)②)
        held.enter_context(hold([q for q, _, _ in cmd_files(it0["cmd"], it0["cwd"])]))
        f, it, files, sigsha = run_verify(msg, sig)
        nn = int(f["id"])
        with locked(cmd_dir(f["run"])):
            it = cmd_item(f["run"], nn)
            if req_why(it) or sha(it["_raw"]) != f["req"]:
                raise Refuse("재는 사이 명령 요청이 바뀜")
            mark_used(f["challenge"], {"t": now_iso(), "run": f["run"], "id": nn, "req": f["req"], "sig": sigsha, "key": f["key"]})
            note("run-start", run=f["run"], id=nn, challenge=f["challenge"], sig=sigsha, key=f["key"], req=f["req"])
            save_req(it, state="running", started=now_iso(), approved_by="phone:" + f["key"])
    except Refuse as e:
        held.close()
        try:
            ff = parse_run_message(msg)
            note("run-refuse", run=ff["run"], id=int(ff["id"]), why=str(e))
        except Refuse:
            note("run-refuse", why=str(e))
        return 1
    with held:
        od = os.path.join(STATE, "out")
        os.makedirs(od, exist_ok=True)
        out_path = os.path.join(od, f"{f['run']}-{nn:02d}.log")
        before, t0, state = core_state(), time.time(), "done"
        try:
            with open(out_path, "wb") as fo:
                p = subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", it["cmd"]], cwd=it["cwd"],
                                     stdin=subprocess.DEVNULL, stdout=fo, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
                try:
                    rc = p.wait(timeout=req_timeout(it))
                except subprocess.TimeoutExpired:
                    kill_tree(p.pid)
                    rc, state = -1, "timeout"
        except OSError as e:
            rc, state = -2, "failed"
            with open(out_path, "ab") as fo:
                fo.write(f"\n[못 돌림: {e}]\n".encode("utf-8"))
        after = core_state()
    if state == "done" and rc != 0:
        state = "failed"
    secs = round(time.time() - t0, 1)
    with open(out_path, "rb") as fh:
        data = fh.read(OUT_MAX + 1)
    if len(data) > OUT_MAX:
        with open(out_path, "r+b") as fh:
            fh.truncate(OUT_MAX)
    tail = decode_out(data[-2000:]).strip()[-400:]
    core = before is None or after is None or before != after
    note("run-end", run=f["run"], id=nn, rc=rc, state=state, secs=secs, core=core, key=f["key"], tail=tail)
    try:
        save_req(cmd_item(f["run"], nn), state=state, rc=rc, secs=secs, ended=now_iso(), core_changed=core, tail=tail, out=out_path)
    except (Refuse, OSError):
        pass
    if core:
        core_alert(f["run"], nn, it.get("purpose") or "")
    return 0


def core_alert(run, nn, purpose):
    """명령 앞뒤로 게이트 코어 자리가 바뀜 → 폰 알림(검증 11-20 (c)) · 알림 대본(비코어)은 나르기만 · 못 보내도 결과·장부엔 남음."""
    al = os.path.join(VAULT, ".claude", "skills", "mobility", "scripts", "alert.py")
    if not os.path.isfile(al) or os.environ.get("APPROVE_NO_ALERT"):
        return
    try:
        subprocess.run([sys.executable, al, "now", "명령 승인 · 코어 바뀜", "--urgent",
                        "--text", f"{run} {nn:02d} '{purpose}' 앞뒤로 게이트 코어 자리가 바뀜 - PC 에서 git status"],
                       capture_output=True, creationflags=NO_WINDOW, timeout=60, cwd=VAULT)
    except (OSError, subprocess.TimeoutExpired):
        pass


def cmd_result(a):
    try:
        it = cmd_item(a.run, a.nn)
    except Refuse as e:
        out_json({"ok": False, "why": str(e)})
        return 1
    obj = {k: v for k, v in it.items() if not k.startswith("_")}
    refused = [j for j in ledger() if j.get("ev") == "run-refuse" and j.get("run") == a.run and j.get("id") == a.nn]
    if refused and obj.get("state") == "pending":
        obj["refused"] = refused[-1].get("why")
    obj.update(ok=True, run=a.run, id=a.nn)
    out_json(obj)
    return 0


def cmd_reject_cmd(a):
    try:
        it = cmd_item(a.run, a.nn)
    except Refuse as e:
        out_json({"ok": False, "why": str(e)})
        return 1
    with locked(cmd_dir(a.run)):
        it = cmd_item(a.run, a.nn)
        if it.get("state") != "pending":
            out_json({"ok": False, "why": f"대기가 아님({it.get('state')})"})
            return 1
        note("reject-cmd", run=a.run, id=a.nn, req=sha(it["_raw"]), why=" ".join((a.why or "").split())[:200])
        save_req(it, state="rejected", ended=now_iso(), why_rejected=" ".join((a.why or "").split())[:200])
    out_json({"ok": True})
    return 0


# ── 명령 ─────────────────────────────────────────────────
def runs():
    try:
        return sorted(n for n in os.listdir(bb_root())
                      if os.path.isdir(os.path.join(bb_root(), n, "pending")) or os.path.isdir(os.path.join(bb_root(), n, "commands")))
    except OSError:
        return []


def age_min(it, now):
    try:
        return max(0, int((now - time.mktime(time.strptime(it.get("added") or "", "%Y-%m-%d %H:%M:%S"))) // 60))
    except (ValueError, OverflowError):
        return 0


def cmd_status(a):
    now, res, total, oldest = time.time(), [], 0, 0
    for r in runs():
        w, c = waiting(pend_dir(r)), cmd_waiting(r, now)
        if not w and not c:
            continue
        o = max(age_min(it, now) for it in w + c)
        res.append({"run": r, "n": len(w) + len(c), "bundles": len(w), "oldest_min": o,
                    "cmds": [{"id": it["_nn"], "purpose": it.get("purpose"), "age_min": age_min(it, now)} for it in c]})
        total, oldest = total + len(w) + len(c), max(oldest, o)
    fz = frozen()
    obj = {"ok": True, "waiting": total, "oldest_min": oldest, "frozen": bool(fz), "frozen_at": (fz or {}).get("t"), "runs": res, "keys": len(read_keys())}
    if a.json:
        out_json(obj)
    else:
        print(f"승인 대기 {total} · 가장 오래 {oldest}분" + (" · 폰 승인 얼어 있음" if fz else "") + f" · 키 {obj['keys']}")
        for r in res:
            print(f"  {r['run']}: {r['n']} · {r['oldest_min']}분")
    return 0


def cmd_challenge(a):
    if not ok_run(a.run):
        out_json({"ok": False, "why": "run 꼴이 다름"})
        return 1
    led = ledger()
    try:
        root, group, diffs, selfp, corep = bundle(a.run)
    except Refuse as e:
        out_json({"ok": False, "why": str(e), "frozen": bool(frozen(led))})
        return 1
    allsha = sha(joined(diffs))
    obj = {"ok": True, "purpose": PURPOSE, "run": a.run, "repo": root, "frozen": bool(frozen(led)),
           "rejected_before": any(j.get("ev") == "reject" and j.get("all") == allsha for j in led),
           "self": selfp, "core": corep,
           "items": [{"nn": it["_nn"], "meta": base64.b64encode(it["_meta"]).decode(), "diff": base64.b64encode(d).decode()} for it, d in zip(group, diffs)]}
    if not selfp and not obj["frozen"]:
        try:
            pre = pre_state(root, diffs)
        except Refuse as e:
            out_json({"ok": False, "why": str(e)})
            return 1
        ch = secrets.token_hex(32)
        note("challenge", run=a.run, repo=root, all=allsha, pre=sha(pre), challenge=ch, items=[it["_nn"] for it in group])
        obj.update(challenge=ch, pre=base64.b64encode(pre).decode(), expires=int(time.time()) + CHALLENGE_TTL)
    out_json(obj)
    return 0


def apply_signed(req):
    """서명 요청 하나를 재고 붙인다 · 결과 dict. 하나라도 어긋나면 Refuse."""
    try:
        msg = base64.b64decode(req.get("message") or "", validate=True)
        sig = base64.b64decode(req.get("sig") or "", validate=True)
    except (binascii.Error, ValueError, AttributeError):
        raise Refuse("요청 꼴이 다름(base64)")
    if msg.split(b"\n", 1)[0] == RUN_PURPOSE.encode():
        return run_signed(msg, sig)
    f = parse_message(msg)
    keys = read_keys()
    if f["key"] not in keys:
        raise Refuse("키 목록에 없는 키")
    if not ecdsa_ok(keys[f["key"]][0], msg, sig):
        raise Refuse("서명이 맞지 않음")
    ms = int(f["time"])
    now = time.time()
    if not (now - PAST <= ms / 1000 <= now + FUTURE):
        raise Refuse("폰 시각이 창 밖(지금 -30분 ~ +2분) - 다시 받아 승인")
    d = pend_dir(f["run"])
    with locked(d):
        led = ledger()
        if frozen(led):
            raise Refuse("폰 승인 얼어 있음('내가 안 시킴') - PC 에서 approve.py unfreeze")
        sigsha = sha(sig)
        if any(j.get("ev") == "apply" and j.get("sig") == sigsha for j in led):
            raise Refuse("이미 쓴 서명")
        ch = [j for j in led if j.get("ev") == "challenge" and j.get("challenge") == f["challenge"]]
        if not ch:
            raise Refuse("PC 가 낸 도전값이 아님")
        if any(j.get("ev") == "apply" and j.get("challenge") == f["challenge"] for j in led):
            raise Refuse("이미 쓴 도전값")
        c = ch[-1]
        if now - int(c.get("at") or 0) > CHALLENGE_TTL:
            raise Refuse("도전값이 만료됨(30분) - 다시 받아 승인")
        if c.get("run") != f["run"]:
            raise Refuse("도전값의 run 이 다름")
        root, group, diffs, selfp, _ = bundle(f["run"])
        if not same(root, f["repo"]) or root != c.get("repo"):
            raise Refuse("저장소가 다름")
        if selfp:
            raise Refuse("자기 제외 경로가 든 묶음(PC y 로만): " + " · ".join(selfp[:3]))
        pre = pre_state(root, diffs)
        want = message(root, f["run"], group, diffs, pre, f["challenge"], f["time"], f["key"])
        if want != msg:
            got_l, want_l = msg.decode("utf-8").split("\n"), want.decode("utf-8").split("\n")
            diff_k = next((w.split(":")[0] for g, w in zip(got_l, want_l) if g != w), "항목 수")
            raise Refuse(f"승인한 것과 지금 묶음이 다름({diff_k})")
        allsha = sha(joined(diffs))
        if c.get("all") != allsha:
            raise Refuse("도전값을 낸 묶음과 다름")
        data = joined(diffs)  # 잰 그 바이트를 그대로 붙인다(파일을 다시 읽지 않음)
        rc, _, err = git(root, "apply", "--check", data=data)
        if rc:
            raise Refuse(f"안 붙음 - {err_line(err)}")
        rc, _, err = git(root, "apply", data=data)
        if rc:
            note("fail", by="phone", run=f["run"], all=allsha, why=err_line(err), key=f["key"])
            raise Refuse(f"붙이다 실패 - {err_line(err)} · git status 로 볼 것")
        note("apply", by="phone", run=f["run"], repo=root, all=allsha, challenge=f["challenge"], sig=sigsha, key=f["key"],
             items=[it["_nn"] for it in group], time=ms)
        for it in group:
            mark_applied(d, it, "phone:" + f["key"])
    return {"ok": True, "applied": [it["_nn"] for it in group], "all": allsha[:16], "key": f["key"]}


def cmd_apply_signed(a):
    try:
        if a.file in (None, "-"):
            raw = sys.stdin.buffer.read(MAX_IN + 1)
        else:
            with open(a.file, "rb") as fh:
                raw = fh.read(MAX_IN + 1)
        if len(raw) > MAX_IN:
            raise Refuse("요청이 너무 큼")
        try:
            req = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise Refuse("요청 꼴이 다름(JSON)")
        if not isinstance(req, dict):
            raise Refuse("요청 꼴이 다름(JSON)")
        res = apply_signed(req)
    except Refuse as e:
        try:
            note("refuse", by="phone", why=str(e))
        except OSError:
            pass
        out_json({"ok": False, "why": str(e)})
        return 1
    except Exception as e:  # 못 재면 안 붙임
        out_json({"ok": False, "why": f"검증기 오류 - 안 붙임 ({type(e).__name__})"})
        return 1
    out_json(res)
    return 0


def counts(diff, root):
    files, _ = files_of(diff, root)
    files = files or []
    return files, sum(x for _, x, _ in files), sum(r for _, _, r in files)


def cmd_apply_console(a):
    d = pend_dir(a.run)
    for it in items(d):  # 붙였다고 적었는데 못 옮긴 것 - 마저 옮긴다
        if it.get("state") == "applied":
            mark_applied(d, it, it.get("applied_by") or "")
    its = waiting(d)
    if not its:
        print("대기 없음")
        return 0
    if a.yes:  # y 를 안 치는 길로 게이트 코어를 붙이면 게이트를 건너뛴다
        need = sorted({p for it in its for p in (paths_of([read_diff(it) or b""], repo_root(it.get("repo"))) or []) if GATE_CORE.search(p)})
        if need:
            print("안 붙임 - 게이트 코어가 섞인 묶음은 --yes 로 못 붙인다. 사용자가 터미널에서 y 로 붙인다:")
            print("  " + " · ".join(need))
            return 2
    elif frozen():
        fz = frozen()
        print(f"폰 승인이 얼어 있음('내가 안 시킴' {fz.get('t')}" + (f" · {fz.get('why')}" if fz.get("why") else "") + ")")
        if not ask("풀고 계속할까요? [y/N] "):
            print("안 붙임 - 얼어 있는 채로 둠")
            return 1
        note("unfreeze", by="console")
    done, fails = 0, []
    for group in by_repo(its):
        repo = group[0].get("repo") or "?"
        name = os.path.basename(repo)
        root, diffs, why = verify(group)
        if why is None:
            why = next((f"{it['_nn']:02d} {w} - pending.py fill 로 채움" for it in group
                        for w in [pr_why(it.get("purpose"), it.get("reason"))] if w), None)
        if why is None:
            i, why = stack_check(root, diffs)
            if i >= 0:
                why = f"{group[i]['_nn']:02d} 에서 막힘 - {why}"
        if why:
            fails.append((name, why + " · 이 저장소는 하나도 안 붙임"))
            continue
        print(f"\n[{name}] {repo}")
        tot_f, tot_a, tot_r = set(), 0, 0
        for it, data in zip(group, diffs):
            files, add, rem = counts(data, root)
            crlf = " · 경고: CRLF" if b"\r\n" in data else ""
            print(f"  {it['_nn']:02d} 목적: {it.get('purpose')}")
            print(f"     사유: {it.get('reason')} · sha {it['sha256'][:16]}{' · ' + it['by'] if it.get('by') else ''}{crlf}")
            for paths, fa, fr in files:
                print(f"     {' -> '.join(paths)} +{fa} -{fr}")
                tot_f.update(paths[-1:])
            tot_a, tot_r = tot_a + add, tot_r + rem
        print(f"  합계 diff {len(group)} · 파일 {len(tot_f)} · +{tot_a} -{tot_r} · sha {sha(joined(diffs))[:16]}")
        if not a.yes and not ask():
            fails.append((name, "y 가 아니라 건너뜀"))
            continue
        try:
            with locked(d):
                root2, diffs2, why = verify(group)  # 묻는 사이에 바뀌었나
                if why or diffs2 != diffs:
                    fails.append((name, (why or "묻는 사이 diff 가 바뀜") + " · 이 저장소는 하나도 안 붙임"))
                    continue
                rc, _, err = git(root, "apply", data=joined(diffs))
                if rc:
                    none = stack_check(root, diffs)[0] < 0
                    fails.append((name, f"붙이다 실패 - {err_line(err)} · " + ("하나도 안 붙음" if none else "일부만 붙었을 수 있음 - git status 로 볼 것")))
                    continue
                by = "yes" if a.yes else "console"
                note("apply", by=by, run=a.run, repo=root, all=sha(joined(diffs)), items=[it["_nn"] for it in group])
                for it in group:
                    mark_applied(d, it, by)
                done += len(group)
                print(f"  붙임 {len(group)}")
        except Refuse as e:
            fails.append((name, str(e)))
    left = len(waiting(d))
    print(f"\n붙임 {done} · 남음 {left}")
    for name, why in fails:
        print(f"  실패 {name}: {why}")
    return 0 if left == 0 else 1


def cmd_enroll(a):
    try:
        spki = check_spki(base64.b64decode(a.pub, validate=True))
    except (binascii.Error, ValueError):
        out_json({"ok": False, "why": "공개 키 꼴이 다름(base64)"})
        return 1
    except Refuse as e:
        out_json({"ok": False, "why": str(e)})
        return 1
    kid = key_id(spki)
    if kid in read_keys():
        out_json({"ok": True, "key": kid, "registered": True})
        return 0
    os.makedirs(REQ_DIR, exist_ok=True)
    reqs = [n for n in os.listdir(REQ_DIR) if n.endswith(".json")]
    if f"{kid}.json" not in reqs and len(reqs) >= MAX_REQ:
        out_json({"ok": False, "why": f"등록 요청이 {MAX_REQ}개 넘게 쌓임 - PC 에서 register 로 정리"})
        return 1
    label = re.sub(r"[^\w .-]", "", " ".join((a.label or "").split()))[:40]
    save_json(os.path.join(REQ_DIR, f"{kid}.json"), {"key": kid, "spki": base64.b64encode(spki).decode(), "label": label, "at": now_iso()})
    note("enroll", key=kid, label=label)
    out_json({"ok": True, "key": kid, "registered": False})
    return 0


def cmd_register(a):
    if not need_console("키 등록"):
        return 2
    try:
        names = sorted(n for n in os.listdir(REQ_DIR) if n.endswith(".json"))
    except OSError:
        names = []
    if not names:
        print("등록 요청 없음 - 폰 승인 앱에서 '키 만들기'를 먼저")
        return 1
    keys, added = read_keys(), 0
    for n in names:
        p = os.path.join(REQ_DIR, n)
        try:
            with open(p, encoding="utf-8") as f:
                j = json.load(f)
            spki = check_spki(base64.b64decode(j.get("spki") or "", validate=True))
        except (OSError, ValueError, binascii.Error, Refuse):
            print(f"  {n}: 못 읽는 요청 - 지움")
            os.remove(p)
            continue
        kid = key_id(spki)
        if kid in keys:
            print(f"  {kid}: 이미 등록됨 - 요청 지움")
            os.remove(p)
            continue
        code = pair_code(spki)
        print(f"\n등록 요청 키 {kid} · {j.get('label') or '이름 없음'} · 받은 때 {j.get('at')}")
        print(f"  짝 숫자 {code[:3]} {code[3:]} - 폰 승인 앱 화면의 숫자와 같을 때만 y")
        if not ask("이 키를 등록할까요? [y/N] "):
            print("  안 함 - 요청은 남김(지우려면 폰에서 다시 만들거나 이 파일을 지움)")
            continue
        try:
            with open(KEYS, encoding="utf-8") as f:
                lines = f.read().splitlines()
        except OSError:
            lines = ["# 폰 승인 키 목록 - 게이트 코어 · 더하기 = approve.py register · 빼기 = approve.py revoke (둘 다 콘솔 y)"]
        lines.append(f"{kid} {base64.b64encode(spki).decode()} {time.strftime('%Y-%m-%dT%H:%M:%S')} {j.get('label') or '-'}")
        write_keys(lines)
        os.remove(p)
        note("register", key=kid, label=j.get("label") or "")
        keys[kid] = (spki, "", "")
        added += 1
        print(f"  등록함 {kid}")
    print(f"\n등록 {added} · 키 {len(read_keys())}")
    return 0


def cmd_revoke(a):
    if not need_console("키 폐기"):
        return 2
    keys = read_keys()
    if a.key not in keys:
        print(f"키 목록에 없음: {a.key}")
        return 1
    print(f"키 {a.key} · {keys[a.key][2]} · 등록 {keys[a.key][1]} - 빼면 이 키의 서명은 안 받는다")
    if not ask("뺄까요? [y/N] "):
        print("안 함")
        return 1
    with open(KEYS, encoding="utf-8") as f:
        lines = [ln for ln in f.read().splitlines() if not ln.startswith(a.key + " ")]
    write_keys(lines)
    note("revoke", key=a.key)
    print(f"뺌 {a.key} · 남은 키 {len(read_keys())}")
    return 0


def keys_print(a):
    keys = read_keys()
    try:
        with open(KEYS, "rb") as f:
            fp = sha(f.read())[:16]
    except OSError:
        fp = "-"
    if a.json:
        out_json({"ok": True, "n": len(keys), "fingerprint": fp, "keys": [{"key": k, "at": v[1], "label": v[2]} for k, v in keys.items()]})
    else:
        print(f"키 {len(keys)} · 목록 지문 {fp}")
        for k, v in keys.items():
            print(f"  {k} · {v[2]} · 등록 {v[1]}")
    return 0


def cmd_recent(a):
    """최근 붙인 것(폰·콘솔) - 승인 앱이 «내 키가 아닌 서명»을 가려 보인다(설계 T3 사후 감지)."""
    keys = read_keys()
    ev = [j for j in ledger() if j.get("ev") in ("apply", "freeze", "unfreeze", "register", "revoke", "run-start", "run-end", "run-refuse")][-max(1, min(a.n, 100)):]
    out_json({"ok": True, "keys": sorted(keys), "events": [{k: j.get(k) for k in ("t", "ev", "by", "run", "all", "items", "key", "id", "rc", "state", "secs", "core", "why")
                                                            if j.get(k) is not None} for j in ev]})
    return 0


def cmd_reject(a):
    if not ok_run(a.run) or not re.fullmatch(r"[0-9a-f]{16,64}", a.all or ""):
        out_json({"ok": False, "why": "sha 꼴이 다름"})
        return 1
    note("reject", run=a.run, all=a.all, why=" ".join((a.why or "").split())[:200])
    out_json({"ok": True})
    return 0


def cmd_freeze(a):
    note("freeze", why=" ".join((a.why or "").split())[:200])
    out_json({"ok": True, "frozen": True})
    return 0


def cmd_unfreeze(a):
    if not need_console("동결 풀기"):
        return 2
    fz = frozen()
    if not fz:
        print("얼어 있지 않음")
        return 0
    print(f"폰 승인이 얼어 있음 · {fz.get('t')}" + (f" · {fz.get('why')}" if fz.get("why") else ""))
    if not ask("풀까요? [y/N] "):
        print("안 함")
        return 1
    note("unfreeze", by="console")
    print("풂")
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # 인코딩은 콘솔 것(cp949) 그대로
    ap = argparse.ArgumentParser(description="폰 승인 - 게이트 코어 묶음 검증·적용기")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("status")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("challenge")
    p.add_argument("run")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_challenge)
    p = sub.add_parser("apply-signed")
    p.add_argument("file", nargs="?")
    p.set_defaults(fn=cmd_apply_signed)
    p = sub.add_parser("apply-console")
    p.add_argument("run")
    p.add_argument("--yes", action="store_true", help="y/N 을 묻지 않음 · 게이트 코어가 섞이면 거절")
    p.set_defaults(fn=cmd_apply_console)
    p = sub.add_parser("enroll")
    p.add_argument("pub")
    p.add_argument("--label", default="")
    p.set_defaults(fn=cmd_enroll)
    p = sub.add_parser("register")
    p.set_defaults(fn=cmd_register)
    p = sub.add_parser("revoke")
    p.add_argument("key")
    p.set_defaults(fn=cmd_revoke)
    p = sub.add_parser("keys")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=keys_print)
    p = sub.add_parser("recent")
    p.add_argument("--n", type=int, default=20)
    p.set_defaults(fn=cmd_recent)
    p = sub.add_parser("reject")
    p.add_argument("run")
    p.add_argument("--all", required=True)
    p.add_argument("--why", default="")
    p.set_defaults(fn=cmd_reject)
    p = sub.add_parser("freeze")
    p.add_argument("--why", default="")
    p.set_defaults(fn=cmd_freeze)
    p = sub.add_parser("unfreeze")
    p.set_defaults(fn=cmd_unfreeze)
    p = sub.add_parser("challenge-cmd")
    p.add_argument("run")
    p.add_argument("nn", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_challenge_cmd)
    p = sub.add_parser("check-cmd")
    p.add_argument("run")
    p.add_argument("nn", type=int)
    p.set_defaults(fn=cmd_check_cmd)
    p = sub.add_parser("run-exec")
    p.add_argument("file")
    p.set_defaults(fn=cmd_run_exec)
    p = sub.add_parser("result")
    p.add_argument("run")
    p.add_argument("nn", type=int)
    p.set_defaults(fn=cmd_result)
    p = sub.add_parser("reject-cmd")
    p.add_argument("run")
    p.add_argument("nn", type=int)
    p.add_argument("--why", default="")
    p.set_defaults(fn=cmd_reject_cmd)
    a = ap.parse_args()
    try:
        return a.fn(a)
    except Refuse as e:
        print(f"안 함 - {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
