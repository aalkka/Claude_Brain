# -*- coding: utf-8 -*-
"""**fileops** — 볼트 안 지우기·옮기기·이름 바꾸기의 유일한 실행자 (2026-10-29 · 볼트 개혁 피드백 1).

왜 대본 하나인가(사용자 피드백 10-29): Claude 가 rm·mv 를 그때그때 지어 쓰면 ①방식이 매번 다르고 ②흔적이 없고
③이름을 바꾸면 링크가 깨지고(어떤 노트를 가리키는 파일 수 = 중앙값 3·상위 10% 9·최대 53 — 손으로 고치면
호출 2+2N 번) ④지운 것이 영영 사라진다. 여기로 모으면 호출 1번·출력 몇 줄이고, 모든 행위가 장부에 남고,
지운 것은 휴지통에서 되살아난다. 셸 rm·mv 로 볼트 안을 건드리면 훅(hooks/ops-guard.ps1)이 막고 여기로 돌린다.

  py -3 3_시스템/fileops.py mv <원래> <새 자리> --why "까닭"     옮기기·이름 바꾸기(위키링크·캔버스·짝 메모가 따라감)
  py -3 3_시스템/fileops.py rm <경로> --why "까닭"              휴지통(.trash/<날짜>/<원래 경로>)으로 — 영구 삭제 아님
  py -3 3_시스템/fileops.py restore <id|휴지통 경로> [--to ..]   되살리기
  py -3 3_시스템/fileops.py undo <id>                           행위 하나(또는 한 번에 한 묶음)를 되돌린다
  py -3 3_시스템/fileops.py cp <원본> <볼트 안 자리> --why ..     들이기 — 같은 내용(sha256)이 볼트에 있으면 거절
  py -3 3_시스템/fileops.py replace <새 파일> <자리> --why ..     덮어쓰기 — 옛것은 휴지통으로
  py -3 3_시스템/fileops.py mkdir <폴더> · archive <노트.md> --why ..
  py -3 3_시스템/fileops.py plan <계획.json> [--apply]          여러 행위를 한 묶음으로(기본 = 미리 보기)
  py -3 3_시스템/fileops.py migrate [--apply] [--undo <이전 id>] [--from <이전 폴더>] 3_시스템/migrations/ 의 밀린 이전(업데이터가 부름)
  py -3 3_시스템/fileops.py update <계획.json> [--apply]        배포판 코어 바꾸기(업데이터 전용 · dist-diff --plan-out)
  py -3 3_시스템/fileops.py record rm|mv <원래> [<지금 자리>] [--trash system|none]   밖(옵시디언)에서 이미 한 일 적기
  py -3 3_시스템/fileops.py log [-n 20] [--grep 글자] · where <이름> · trash [--older 일수]
  py -3 3_시스템/fileops.py who <경로>                          이 파일·폴더를 쥔 프로그램(장부에 안 남김)
  py -3 3_시스템/fileops.py purge --older 30                    휴지통 영구 비우기 — 사람만(터미널에서 확인 입력)

경로는 볼트 뿌리 기준 상대(`2_지식/x.md`) 또는 볼트 안 절대 경로. 전역 `--dry` = 미리 보기.
장부 = 3_시스템/ledger/ops.jsonl(덧붙이기만 · git 추적) · 보기 = 2_지식/장부.md(생성 파일 — 고치지 않는다).
"""
import argparse
import datetime as dt
import errno
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from collections import Counter
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import roles  # noqa: E402 — 내용 층 자리는 역할로(볼트 개혁 R6)

# Windows 콘솔 기본 cp949 → 한글 출력 시 크래시(incident-2026-07-04-search-stdout-cp949 계열)
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER_DIR = "3_시스템/ledger"
OPS = LEDGER_DIR + "/ops.jsonl"
MIGRATED = LEDGER_DIR + "/migrations.json"
MIGRATIONS = "3_시스템/migrations"
KNOWN_TABLE = ".claude/skills/dist-sync/known-hashes.json"   # 배포판이 실어 온 파일 목록을 겸한다(dist-diff --build-known)
VIEW = "2_지식/장부.md"
TRASH = ".trash"          # 옵시디언 «Obsidian 휴지통» 과 같은 폴더 — 점 폴더라 탐색기에 안 보인다
VIEW_N = 100
BIG = 30                  # 폴더 지우기에서 파일이 이보다 많으면 --count 로 개수를 맞춰야 한다(대량 삭제를 일부러 하게)
EXPECT_S = 60             # 옵시디언 CLI 에 맡긴 이동을 «우리가 한 것»으로 기억하는 초(record 가 두 번 적지 않게)

# 링크를 고칠 때 읽지 않는 곳 — 기계 파생물·설정·휴지통. _색인 은 ingest.py 가 해시로 다시 잇는다.
SKIP_DIRS = {".git", ".obsidian", TRASH, "node_modules", "__pycache__"}
SKIP_REL = ("3_시스템/_index/", "1_수집/_색인/", LEDGER_DIR + "/")
# 링크 고치기에서 더 빼는 곳 = 코어(스킬·훅·규약). 코어는 고치지 않고 code_refs 가 알린다(코어 수정은 게이트·업데이터 몫).
LINK_SKIP = SKIP_REL + (".claude/", "3_시스템/hooks/")
LINK_SKIP_FILES = {"claude.md", "3_시스템/conventions.md"}
# 평소 행위가 건드리지 않는 곳 — 코어는 업데이터(update)만, 장부는 이 대본만, 금고·옵시디언 설정은 사람만.
PROTECT = (".git/", ".obsidian/", ".claude/", "3_시스템/hooks/", LEDGER_DIR + "/", "3_시스템/vault/", TRASH + "/")
PROTECT_FILES = ("claude.md", "readme.md", ".gitignore", ".gitattributes")
# update 가 써도 되는 곳 = 코어. 내용 층·개인 칸은 계획에 들어 있어도 거절한다(dist-diff 층 분류 다음의 둘째 방어선).
UPDATE_DENY = tuple(p + "/" for p in [roles.path("work"), roles.path("sources")] + roles.group("content")) + (
               "3_시스템/_index/", "3_시스템/_claude-memory/", LEDGER_DIR + "/",
               "3_시스템/vault/", ".git/", TRASH + "/", ".obsidian/")
CODE_EXT = (".py", ".ps1", ".psm1", ".json", ".mjs", ".js", ".ts", ".tsv", ".txt", ".yaml", ".yml", ".sh", ".md")

WIKI = re.compile(r"(!?\[\[)([^\[\]|#\n]+)((?:#[^\[\]|\n]*)?(?:\|[^\[\]\n]*)?\]\])")
MDL = re.compile(r"(\]\()(<[^>\n]+>|[^)\s]+)(\))")
CANVAS = re.compile(r'("file"\s*:\s*")([^"]+)(")')
SCHEME = re.compile(r"^[A-Za-z][\w+.-]*:")

LABEL = {"mv": "옮김", "rename": "이름 바꿈", "rm": "지움(휴지통)", "restore": "되살림", "cp": "들임",
         "mkdir": "폴더 만듦", "rmdir": "빈 폴더 치움", "archive": "보관 표시", "unarchive": "보관 풂", "purge": "영구 삭제",
         "out": "볼트 밖으로"}


class Stop(Exception):
    """사용자에게 보일 거절·실패. 볼트는 이 줄 앞까지의 상태 그대로다."""


def now():
    return dt.datetime.now().astimezone()


def stamp(t):
    return t.strftime("%y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def detect_by():
    # Claude Code 가 도구 셸에 CLAUDECODE=1 을 준다 — 그 밖(터미널·탐색기에서 부른 것)은 사람으로 적는다
    return "claude" if os.environ.get("CLAUDECODE") == "1" else "user"


class Ctx:
    def __init__(self, vault, by=None, dry=False):
        self.vault = os.path.abspath(vault)
        self.by = by or detect_by()
        self.dry = dry
        self.batch = "b" + stamp(now())
        self.sid = os.environ.get("CLAUDE_CODE_SESSION_ID", "")[:8]
        self.events = []
        self.quiet_refs = False     # 옮길 때마다 옛 경로를 알리지 않는다(이전이 끝에 한 번에 알린다)

    def abs(self, rel):
        return os.path.join(self.vault, *rel.split("/")) if rel else self.vault

    def rel(self, a):
        r = os.path.relpath(a, self.vault).replace("\\", "/")
        return "" if r == "." else r

    def add(self, op, **kw):
        if self.dry:
            return None
        t = now()
        ev = {"id": stamp(t), "ts": t.isoformat(timespec="seconds"), "op": op, "by": self.by, "batch": self.batch}
        if self.sid:
            ev["session"] = self.sid
        ev.update({k: v for k, v in kw.items() if v is not None and v != "" and v != []})
        p = self.abs(OPS)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        self.events.append(ev)
        return ev


# ── 경로 ─────────────────────────────────────────────────────────────────

def to_rel(ctx, p, outside_ok=False):
    """→ (볼트 상대 경로 또는 None(볼트 밖), 절대 경로). Git Bash 의 /c/... 꼴도 받는다."""
    p = p.strip().strip('"').strip("'").replace("\\", "/")
    m = re.match(r"^/([A-Za-z])/(.*)$", p)
    if m:
        p = m.group(1).upper() + ":/" + m.group(2)
    a = os.path.abspath(p if os.path.isabs(p) else os.path.join(ctx.vault, p))
    try:
        r = os.path.relpath(a, ctx.vault).replace("\\", "/")
    except ValueError:      # 다른 드라이브
        r = "../"
    if r == ".." or r.startswith("../"):
        if outside_ok:
            return None, a
        raise Stop("볼트 밖 경로: %s" % p)
    return ("" if r == "." else r), a


def guard(r, core_ok=False):
    if not r:
        raise Stop("볼트 뿌리는 다루지 않는다")
    low = r.lower()
    if core_ok:
        if any((low + "/").startswith(x.lower()) for x in UPDATE_DENY):
            raise Stop("업데이터가 쓰지 않는 자리(개인·내용 층): %s" % r)
        return
    if low in PROTECT_FILES or any((low + "/").startswith(x.lower()) for x in PROTECT):
        raise Stop("지켜지는 자리: %s — 코어는 업데이터, 장부는 fileops, 금고·옵시디언 설정은 사람" % r)


def same(a, b):
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


def files_under(a):
    out = []
    for dp, _, fns in os.walk(a):
        out += [os.path.join(dp, f) for f in fns]
    return out


def walk_vault(ctx, exts=None, skip_rel=SKIP_REL):
    for dp, dns, fns in os.walk(ctx.vault):
        rd = ctx.rel(dp)
        dns[:] = [d for d in dns if d not in SKIP_DIRS
                  and not ((rd + "/" + d).lstrip("/") + "/").startswith(skip_rel)]
        for f in fns:
            if exts is None or f.lower().endswith(exts):
                yield (rd + "/" + f).lstrip("/")


def walk_sub(ctx, sub, exts):
    """볼트의 한 갈래만 훑는다(code_refs — 볼트 전체를 돌면 1_수집 수천 파일을 지난다)."""
    a = ctx.abs(sub)
    if os.path.isfile(a):
        return [sub] if sub.lower().endswith(exts) else []
    out = []
    for dp, dns, fns in os.walk(a):
        rd = ctx.rel(dp)
        dns[:] = [d for d in dns if d not in SKIP_DIRS and not (rd + "/" + d + "/").startswith(SKIP_REL)]
        out += [rd + "/" + f for f in fns if f.lower().endswith(exts)]
    return out


def trash_slot(ctx, r):
    """.trash/<오늘>/<원래 상대 경로> — 같은 날 같은 자리가 또 지워지면 « (2)»."""
    base = "%s/%s/%s" % (TRASH, now().strftime("%Y-%m-%d"), r)
    cand, k = base, 2
    stem, ext = posixpath.splitext(base)
    while os.path.exists(ctx.abs(cand)):
        cand = "%s (%d)%s" % (stem, k, ext)
        k += 1
    return cand


def made_dirs(a_d):
    """a_d 를 놓으려고 새로 만들 조상 폴더(깊은 것부터) — 되돌릴 때 비어 있으면 치운다."""
    made, d = [], os.path.dirname(a_d)
    while d and not os.path.exists(d):
        made.append(d)
        d = os.path.dirname(d)
    return made


def holders(a):
    """이 파일(폴더면 안의 파일마다)을 쥔 프로그램 — 윈도 Restart Manager · [(이름, pid, 파일)] · 윈도 밖·못 재면 []."""
    if os.name != "nt":
        return []
    import ctypes
    from ctypes import wintypes as w

    class Proc(ctypes.Structure):
        _fields_ = [("pid", w.DWORD), ("started", w.FILETIME)]

    class Info(ctypes.Structure):
        _fields_ = [("proc", Proc), ("app", w.WCHAR * 256), ("svc", w.WCHAR * 64), ("kind", ctypes.c_int),
                    ("status", w.DWORD), ("sid", w.DWORD), ("restartable", w.BOOL)]

    try:
        rm = ctypes.WinDLL("rstrtmgr")
    except OSError:
        return []
    out = []
    for f in (files_under(a) if os.path.isdir(a) else [a])[:300]:
        h, key = w.DWORD(), ctypes.create_unicode_buffer(64)
        if rm.RmStartSession(ctypes.byref(h), 0, key):
            continue
        try:
            if rm.RmRegisterResources(h, 1, (w.LPCWSTR * 1)(f), 0, None, 0, None):
                continue
            need, n, why = w.UINT(), w.UINT(), w.DWORD()
            if rm.RmGetList(h, ctypes.byref(need), ctypes.byref(n), None, ctypes.byref(why)) not in (0, 234) or not need.value:
                continue
            got = (Info * need.value)()
            n.value = need.value
            if not rm.RmGetList(h, ctypes.byref(need), ctypes.byref(n), got, ctypes.byref(why)):
                out += [(got[i].app, got[i].proc.pid, f) for i in range(n.value)]
        finally:
            rm.RmEndSession(h)
    return out


def held_note(a):
    """쥔 프로그램을 사람 글로 — «Python(pid 36144 · -u slim.py)이 2_3.94.csv 를 쥠» · 못 찾으면 빈 글. 실패 경로에서만 부른다(PowerShell 1초쯤)."""
    hs = holders(a)
    if not hs:
        return ""
    pids = sorted({pid for _, pid, _ in hs})
    cmd = {}
    try:
        q = ("[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); Get-CimInstance Win32_Process -Filter \"%s\" | "
             "ForEach-Object { \"$($_.ProcessId) $($_.CommandLine)\" }") % " or ".join("ProcessId=%d" % p for p in pids)
        r = subprocess.run(["powershell", "-NoProfile", "-Command", q], capture_output=True, encoding="utf-8", errors="replace", timeout=5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in r.stdout.splitlines():
            m = re.match(r"(\d+) (.*)", line.strip())
            if m:
                cmd[int(m.group(1))] = re.sub(r'^"?[^"]*?\.exe"?\s*', "", m.group(2))[:60]   # 실행 파일 경로는 빼고 인자만
    except (OSError, subprocess.SubprocessError):
        pass
    parts = []
    for name, pid in sorted({(n, p) for n, p, _ in hs}, key=lambda x: x[1]):
        fs = [os.path.basename(f) for n, p, f in hs if p == pid]
        parts.append("%s(pid %d%s)이 %s%s 를 쥠" % (name, pid, " · " + cmd[pid] if cmd.get(pid) else "", fs[0], " 외 %d" % (len(fs) - 1) if len(fs) > 1 else ""))
    return " · ".join(parts)


def move(a_s, a_d):
    """볼트 안 옮기기 = 이름 바꾸기 한 번 — 되거나 안 되거나. shutil.move 는 이름 바꾸기가 막히면 복사 + 지우기로 넘어가
    잠긴 파일에서 멈춰 새 자리에 사본 · 옛 자리에 나머지를 남겼다(11-02 받은함 사고 · 장부에도 안 남음)."""
    made = made_dirs(a_d)
    os.makedirs(os.path.dirname(a_d), exist_ok=True)

    def undo_made():
        for d in made:                # 깊은 것부터
            if os.path.isdir(d) and not os.listdir(d):
                os.rmdir(d)

    try:
        if same(a_s, a_d):        # 대소문자만 바꾸기(Windows 는 같은 파일로 본다) — 임시 이름을 거친다
            tmp = a_d + ".~fileops"
            os.rename(a_s, tmp)
            os.rename(tmp, a_d)
        else:
            for i in range(3):    # 백신·미리 보기가 잠깐 쥔 것은 기다린다
                try:
                    os.rename(a_s, a_d)
                    break
                except PermissionError:
                    if i == 2:
                        raise
                    time.sleep(0.2)
    except PermissionError:
        undo_made()
        raise Stop("%s — 옮기지 않았다 · 끝내거나 닫고 다시: %s" % (held_note(a_s) or "다른 프로그램이 쥐고 있다(Word·한글·옵시디언 미리 보기 등)", a_s))
    except OSError as e:
        if (getattr(e, "winerror", None) == 17 or e.errno == errno.EXDEV) and not os.path.isdir(a_s):   # 다른 드라이브 — 파일만(하나라 반쪽이 없다)
            shutil.copy2(a_s, a_d)
            try:
                os.remove(a_s)
            except OSError:         # 원래 것을 못 지우면 사본을 치운다 — 양쪽에 남기지 않는다
                os.remove(a_d)
                undo_made()
                raise Stop("%s — 옮기지 않았다 · 끝내거나 닫고 다시: %s" % (held_note(a_s) or "다른 프로그램이 쥐고 있다", a_s))
            return made
        undo_made()
        raise Stop("옮기지 못함(%s): %s → %s" % (e.strerror or type(e).__name__, a_s, a_d))
    return made


move_file = move  # op_cp 의 인자 move 가 이 이름을 가린다


_OBS = None


def obsidian_running():
    """옵시디언이 떠 있나 — CLI 는 첫 명령이 앱을 켜므로(금고 §15) 묻기 전에 프로세스부터 본다. 못 재면 안 떠 있다고 본다(자체 엔진)."""
    try:
        r = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/NH"], capture_output=True, timeout=5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return b"obsidian" in r.stdout.lower()
    except (OSError, subprocess.SubprocessError):
        return False


def obsidian_cli(ctx):
    """옵시디언이 바로 이 볼트를 열고 있으면 공식 CLI 실행 파일, 아니면 None(한 번만 잰다).
    볼트 개혁 R4(10-30): 옵시디언이 켜져 있으면 이동을 옵시디언에 맡긴다 — 옵시디언이 «이름 바꿈»으로 알아
    열린 탭·책갈피·링크를 스스로 고친다(밖에서 옮기면 지우고 새로 만든 것으로 본다). 꺼져 있거나 다른 볼트면 자체 엔진.
    FILEOPS_NO_OBSIDIAN=1 = 늘 자체 엔진(시험·배포판 업데이터)."""
    global _OBS
    if _OBS is None:
        _OBS = False
        exe = shutil.which("obsidian")
        if exe and os.environ.get("FILEOPS_NO_OBSIDIAN") != "1" and obsidian_running():
            try:
                out = subprocess.run([exe, "vault"], capture_output=True, timeout=5, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.decode("utf-8", "replace")
                m = re.search(r"^path\t(.+)$", out, re.M)
                if m and os.path.normcase(os.path.abspath(m.group(1).strip())) == os.path.normcase(ctx.vault):
                    _OBS = exe
            except (OSError, subprocess.TimeoutExpired):
                pass
    return _OBS or None


def expect_file(ctx):
    h = hashlib.sha1(os.path.normcase(ctx.vault).encode("utf-8")).hexdigest()[:8]
    return os.path.join(tempfile.gettempdir(), "fileops-%s-expect.json" % h)


def expect_read(ctx):
    t = time.time()
    try:
        with open(expect_file(ctx), encoding="utf-8") as f:
            return [x for x in json.load(f) if t - x[2] < EXPECT_S]
    except (OSError, ValueError, TypeError, IndexError):
        return []


def expect(ctx, rs, rd):
    """옵시디언 CLI 에 맡기는 이동을 적어 둔다(R5.5) — 옵시디언 안 brain-base 가 같은 이동을 «밖에서 한 일»로
    또 적으려 할 때 record 가 이것을 보고 건너뛴다. 장부보다 먼저 쓴다(옵시디언 알림이 우리 장부 줄보다 빠르다)."""
    items = expect_read(ctx) + [[rs, rd, time.time()]]
    try:
        with open(expect_file(ctx), "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False)
    except OSError:
        pass


def obsidian_move(ctx, rs, rd):
    """파일 하나를 옵시디언 CLI 로 옮긴다. 옮겨졌으면 True · 손대지 않았으면 False(자체 엔진으로) · 어중간하면 멈춘다."""
    exe = obsidian_cli(ctx)
    a_s, a_d = ctx.abs(rs), ctx.abs(rd)
    if not exe or same(a_s, a_d):
        return False
    expect(ctx, rs, rd)
    try:
        subprocess.run([exe, "move", "path=" + rs, "to=" + rd], capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))    # 서버(pyw)에서 부르면 콘솔이 새로 뜬다
    except (OSError, subprocess.TimeoutExpired):
        pass
    for _ in range(50):                                     # 옵시디언이 끝낼 때까지(최대 5초)
        if os.path.exists(a_d) and not os.path.exists(a_s):
            time.sleep(0.5)                                 # 옵시디언의 링크 고침이 끝나게 — 남은 것만 아래 rewrite_links 가
            return True
        time.sleep(0.1)
    if os.path.exists(a_s) and not os.path.exists(a_d):
        return False
    raise Stop("옵시디언 이동이 어중간하다(옛 자리·새 자리 둘 다 있거나 둘 다 없음): %s → %s" % (rs, rd))


def drop_made(ctx, made):
    for d in made or []:
        a = ctx.abs(d)
        if os.path.isdir(a) and not os.listdir(a):
            os.rmdir(a)


def wants_dir(raw):
    """«…/» 로 끝나면 폴더 뜻 — 아직 없는 폴더라도 그 안으로 넣는다."""
    return raw.rstrip().endswith(("/", "\\"))


def describe(a):
    if os.path.isdir(a):
        fs = files_under(a)
        return {"kind": "dir", "n": len(fs), "size": sum(os.path.getsize(f) for f in fs)}
    return {"kind": "file", "size": os.path.getsize(a), "sha": sha256(a)}


# ── 링크 ─────────────────────────────────────────────────────────────────

def read_text(a):
    raw = open(a, "rb").read()
    bom = raw.startswith(b"\xef\xbb\xbf")
    return raw[3 if bom else 0:].decode("utf-8"), bom


def write_text(a, text, bom):
    with open(a, "wb") as f:
        f.write((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))


class Moves:
    """옮긴 파일 짝(옛 → 새). 링크 대상 글자를 받아 새 글자를 돌려준다(옵시디언 해석 규칙을 따름)."""

    def __init__(self, pairs, dup_bases=()):
        self.pairs = pairs
        self.keys = {}
        for o, n in pairs:
            md = o.lower().endswith(".md")
            self.keys[o.lower()] = (o, n, md)
            if md:
                self.keys[o[:-3].lower()] = (o, n, md)
        # 이름만 쓴 링크는 이름이 바뀐 파일만 고친다 · 같은 이름이 볼트에 둘 이상이면 어느 쪽인지 몰라 손대지 않는다
        self.base, self.blocked = {}, []
        for o, n in pairs:
            ob, nb = posixpath.basename(o), posixpath.basename(n)
            if ob.lower() == nb.lower():
                continue
            if ob.lower() in dup_bases:
                self.blocked.append(o)
                continue
            md = ob.lower().endswith(".md")
            self.base[ob.lower()] = (o, n, md)
            if md:
                self.base[ob[:-3].lower()] = (o, n, md)

    def newpath(self, cur):
        hit = self.keys.get(cur.lower())
        return hit[1] if hit and hit[0].lower() == cur.lower() else None

    def _path(self, t, fd, md_link=False):
        tl = t.lower()
        # 위키링크는 ./ ../ 로 시작할 때만 상대 경로다(옵시디언). 마크다운 링크는 늘 상대 후보.
        if md_link or t.startswith(("./", "../")):
            j = posixpath.normpath(posixpath.join(fd, t)).lower() if fd else posixpath.normpath(t).lower()
            hit = self.keys.get(j)                                    # ①이 노트 폴더 기준 상대
            if hit:
                return hit, "rel"
            if t.startswith(("./", "../")):
                return None, None
        hit = self.keys.get(tl)                                       # ②볼트 뿌리부터
        if hit:
            return hit, "root"
        if md_link:
            return None, None
        for k, v in self.keys.items():                                # ③뒤쪽 일치(«가능하면 최단 경로»)
            if k.endswith("/" + tl):
                return v, "suffix"
        return None, None

    def wiki(self, t, fd):
        tl = t.lower()
        if "/" in t:
            hit, style = self._path(t, fd)
            if not hit:
                return None
            o, n, md = hit
            new = n[:-3] if md and not tl.endswith(".md") else n
            if style == "rel":                      # ./ 를 잃으면 옵시디언이 상대가 아닌 뒤쪽 일치로 읽는다
                new = posixpath.relpath(new, fd or ".")
                new = new if new.startswith(".") else "./" + new
            return new
        hit = self.base.get(tl)
        if not hit:
            return None
        o, n, md = hit
        nb = posixpath.basename(n)
        return nb[:-3] if md and not tl.endswith(".md") else nb

    def mdlink(self, raw, fd):
        angle = raw.startswith("<") and raw.endswith(">")
        t = raw[1:-1] if angle else raw
        if SCHEME.match(t) or t.startswith("#"):
            return None
        path, sep, frag = t.partition("#")
        dec = unquote(path).replace("\\", "/")
        if not dec:
            return None
        hit, style = self._path(dec, fd, md_link=True)
        if not hit:
            return None
        o, n, md = hit
        new = n[:-3] if md and not dec.lower().endswith(".md") else n
        if style == "rel":
            new = posixpath.relpath(new, fd or ".")
        out = "<%s>" % new if angle else new.replace(" ", "%20")
        return out + sep + frag

    def canvas(self, v):
        hit = self.keys.get(v.lower())
        return hit[1] if hit and hit[0].lower() == v.lower() else None


def dup_bases(ctx, moved_old):
    """볼트에 둘 이상 있는 이름(소문자) — 옮긴 파일 자신은 한 번만 센다."""
    c = Counter()
    for r in walk_vault(ctx, skip_rel=(LEDGER_DIR + "/",)):
        b = posixpath.basename(r).lower()
        c[b] += 1
        if b.endswith(".md"):
            c[b[:-3]] += 1
    return {b for b, k in c.items() if k > 1}


def fix_moved_relative(ctx, pairs, dry):
    """옮긴 노트 안의 ./ ../ 상대 링크 — 옛 폴더 기준이던 것을 새 폴더 기준으로 다시 쓴다."""
    newof = {o.lower(): n for o, n in pairs}
    fixed = 0
    for o, n in pairs:
        if not n.lower().endswith(".md"):
            continue
        od, nd = posixpath.dirname(o), posixpath.dirname(n)
        if od == nd:
            continue
        a = ctx.abs(o if dry else n)
        try:
            text, bom = read_text(a)
        except (OSError, UnicodeDecodeError):
            continue
        k = 0

        def sub(m):
            nonlocal k
            t = m.group(2).strip().replace("\\", "/")
            if not t.startswith(("./", "../")):
                return m.group(0)
            tgt = posixpath.normpath(posixpath.join(od, t))            # 옛 폴더 기준으로 가리키던 것
            for c, added_md in ((tgt, False), (tgt + ".md", True)):
                fin = newof.get(c.lower())                              # 함께 옮겨졌으면 새 자리
                if fin is None and os.path.exists(ctx.abs(c)):          # 제자리에 있으면 그대로
                    fin = c
                if fin is None:
                    continue
                if added_md and fin.lower().endswith(".md"):
                    fin = fin[:-3]
                new = posixpath.relpath(fin, nd)
                new = new if new.startswith(".") else "./" + new
                if new == t:
                    return m.group(0)
                k += 1
                return m.group(1) + new + m.group(3)
            return m.group(0)

        out = WIKI.sub(sub, text)
        if k and not dry:
            write_text(a, out, bom)
        fixed += k
    return fixed


def rewrite_links(ctx, moves, dry):
    """볼트의 md·canvas 를 훑어 옮긴 파일을 가리키는 링크를 고친다 → [(파일, 고친 수)]."""
    changed = []
    for fr in walk_vault(ctx, exts=(".md", ".canvas"), skip_rel=LINK_SKIP):
        if fr.lower() in LINK_SKIP_FILES:
            continue
        a = ctx.abs(fr)
        try:
            text, bom = read_text(a)
        except (OSError, UnicodeDecodeError):
            continue
        # 미리 보기에선 옮긴 노트가 아직 옛 자리에 있다 — 새 자리 기준 폴더로 본다(상대 링크)
        fd = posixpath.dirname(moves.newpath(fr) or fr) if dry else posixpath.dirname(fr)
        k = 0
        if fr.lower().endswith(".canvas"):
            def cv(m):
                nonlocal k
                new = moves.canvas(m.group(2))
                if new is None:
                    return m.group(0)
                k += 1
                return m.group(1) + new + m.group(3)
            out = CANVAS.sub(cv, text)
        else:
            def wk(m):
                nonlocal k
                t = m.group(2).strip().replace("\\", "/")
                new = moves.wiki(t, fd) if t else None
                if new is None or new == t:
                    return m.group(0)
                k += 1
                return m.group(1) + new + m.group(3)

            def mk(m):
                nonlocal k
                new = moves.mdlink(m.group(2), fd)
                if new is None or new == m.group(2):
                    return m.group(0)
                k += 1
                return m.group(1) + new + m.group(3)
            out = MDL.sub(mk, WIKI.sub(wk, text))
        if k:
            changed.append((fr, k))
            if not dry:
                write_text(a, out, bom)
    return changed


def count_links_to(ctx, olds):
    """지울 것을 가리키는 링크 수(이름만 쓴 링크 포함) — 지우기 전에 알린다."""
    probe = Moves([(o, o + ".~gone") for o in olds])     # 이름이 «바뀐» 것처럼 만들어 이름 링크까지 센다
    return sum(k for _, k in rewrite_links(ctx, probe, dry=True))


def code_refs(ctx, olds, limit=6):
    """코드·설정·스킬에 옛 경로 글자가 남은 곳 — 고치지 않고 알린다(고칠지는 판단이 필요하다)."""
    pats = set()
    for o in olds:
        pats |= {o, o.replace("/", "\\"), o.replace("/", "\\\\")}
        b = posixpath.basename(o)
        if b.lower().endswith(".md"):            # 코어 문서의 위키링크 — 링크 고치기가 코어는 건너뛴다
            pats |= {"[[%s]]" % b[:-3], "[[%s|" % b[:-3], "[[%s#" % b[:-3]}
    hits = []
    cands = walk_sub(ctx, "3_시스템", CODE_EXT) + walk_sub(ctx, ".claude", CODE_EXT) + walk_sub(ctx, "CLAUDE.md", (".md",))
    cands += walk_sub(ctx, "2_지식", (".base",))
    ob = ctx.abs(".obsidian")
    if os.path.isdir(ob):
        # workspace*.json = 옵시디언이 스스로 다시 쓰는 화면 상태(최근 연 파일 등) — 알릴 것이 아니다(10-30 R4 시험 헛경보)
        cands += [".obsidian/" + f for f in os.listdir(ob) if f.endswith(".json") and not f.startswith("workspace")]
    for r in cands:
        if r == VIEW or r.startswith(MIGRATIONS + "/"):      # 이전 파일은 옛 경로를 적는 것이 본업
            continue
        try:
            with open(ctx.abs(r), encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if any(p in line for p in pats):
                        hits.append("%s:%d" % (r, i))
        except OSError:
            continue
    return hits[:limit], len(hits)


def memo_of(ctx, r):
    """원본 옆 짝 메모(`<이름>.md` · `<이름> (<확장자>).md`) — 있는 것만."""
    if r.lower().endswith(".md"):
        return []
    s, e = posixpath.splitext(r)
    return [m for m in ("%s.md" % s, "%s (%s).md" % (s, e[1:])) if os.path.isfile(ctx.abs(m))]


def pair_memos(ctx, rs, rd):
    """짝 메모도 같이 옮긴다 — brain-source followRename 과 같은 규칙."""
    so, eo = posixpath.splitext(rs)
    sn, en = posixpath.splitext(rd)
    out = []
    for old in memo_of(ctx, rs):
        new = "%s (%s).md" % (sn, en[1:]) if old.endswith(" (%s).md" % eo[1:]) else "%s.md" % sn
        if old.lower() == new.lower():
            continue
        if os.path.exists(ctx.abs(new)):
            print("  ⚠ 짝 메모를 못 옮김(새 자리에 이미 있음): %s" % new)
            continue
        out.append((old, new))
    return out


# ── 행위 ─────────────────────────────────────────────────────────────────

def op_mv(ctx, src, dst, why, lenient=False, by_undo=None, core_ok=False):
    rs, a_s = to_rel(ctx, src)
    guard(rs, core_ok)
    rd, a_d = to_rel(ctx, dst)
    if not os.path.exists(a_s):
        if lenient:
            print("  · 건너뜀(%s): %s" % ("이미 됨" if os.path.exists(a_d) else "없음", rs))
            return None
        raise Stop("없음: %s" % rs)
    if (os.path.isdir(a_d) or wants_dir(dst)) and not same(a_s, a_d):   # mv 관례 — 폴더를 주면 그 안으로
        rd = (rd + "/" + posixpath.basename(rs)).lstrip("/")
        a_d = ctx.abs(rd)
    guard(rd, core_ok)
    if os.path.exists(a_d) and not same(a_s, a_d):
        if lenient:
            print("  · 건너뜀(새 자리에 이미 있음): %s" % rd)
            return None
        raise Stop("이미 있음: %s — 덮어쓰려면 replace" % rd)
    if (rd.lower() + "/").startswith(rs.lower() + "/"):
        raise Stop("폴더를 자기 안으로 옮길 수 없다: %s → %s" % (rs, rd))
    isdir = os.path.isdir(a_s)
    info = describe(a_s)
    if isdir:
        pairs = [(ctx.rel(f), rd + ctx.rel(f)[len(rs):]) for f in files_under(a_s)]
        memos = []
    else:
        memos = pair_memos(ctx, rs, rd)
        pairs = [(rs, rd)] + memos
    moves = Moves(pairs, dup_bases(ctx, rs))
    kind = "rename" if posixpath.dirname(rs) == posixpath.dirname(rd) else "mv"
    if ctx.dry:
        ch = rewrite_links(ctx, moves, dry=True)
        refs, nref = ([], 0) if ctx.quiet_refs else code_refs(ctx, [rs])
        print("미리 보기 · %s %s → %s%s" % (LABEL[kind], rs, rd, " (파일 %d)" % info["n"] if isdir else ""))
        print("  링크 고칠 파일 %d(%d곳)%s" % (len(ch), sum(k for _, k in ch), " · 짝 메모 %d 함께" % len(memos) if memos else ""))
        if nref:
            print("  ⚠ 코드·설정에 옛 경로 %d곳: %s" % (nref, " · ".join(refs)))
        return None
    for o, n in [(rs, rd)] + memos:                         # 장부 줄은 링크를 고친 뒤에 적힌다 — 그 사이 follow.py 가 «바깥 이동»으로 잡지 않게
        expect(ctx, o, n)
    if not isdir and obsidian_cli(ctx):                     # 옵시디언이 이 볼트를 열고 있으면 그에게(파일만 — CLI 가 폴더는 못 옮김)
        made = made_dirs(a_d)
        os.makedirs(os.path.dirname(a_d), exist_ok=True)
        via = "obsidian" if obsidian_move(ctx, rs, rd) else None
        if not via:
            move(a_s, a_d)
        for o, n in memos:
            if not obsidian_move(ctx, o, n):
                move(ctx.abs(o), ctx.abs(n))
    else:
        via = None
        made = move(a_s, a_d)
        for o, n in memos:
            move(ctx.abs(o), ctx.abs(n))
    # 끝났다고 말하기 전에 잰다 — 옮긴 자리에 있고, 옛 자리에 없고, 내용이 같다
    if not os.path.exists(a_d) or (os.path.exists(a_s) and not same(a_s, a_d)):
        raise Stop("옮김 확인 실패: %s → %s" % (rs, rd))
    if not isdir and sha256(a_d) != info["sha"]:
        raise Stop("옮긴 뒤 내용이 다르다(sha256): %s" % rd)
    rel_fix = fix_moved_relative(ctx, pairs, dry=False)
    ch = rewrite_links(ctx, moves, dry=False)
    refs, nref = ([], 0) if ctx.quiet_refs else code_refs(ctx, [rs])
    ev = ctx.add(kind, src=rs, dst=rd, why=why, undo_of=by_undo, links=sum(k for _, k in ch),
                 linkfiles=[f for f, _ in ch][:20], made=[ctx.rel(m) for m in made], **info, **({"via": via} if via else {}))
    for o, n in memos:
        ctx.add("mv", src=o, dst=n, why="짝 메모 따라감", parent=ev["id"])
    print("%s %s → %s%s%s" % (LABEL[kind], rs, rd, " (파일 %d)" % info["n"] if isdir else "", " · 옵시디언이 옮김" if via else ""))
    if ch or memos or rel_fix:
        print("  링크 고침 %d파일(%d곳)%s%s" % (len(ch), sum(k for _, k in ch),
              " · 상대 링크 %d" % rel_fix if rel_fix else "", " · 짝 메모 %d 함께" % len(memos) if memos else ""))
    if moves.blocked:
        print("  ⚠ 같은 이름이 볼트에 여럿 — 이름만 쓴 링크는 손대지 않음: %s" % ", ".join(moves.blocked))
    if nref:
        print("  ⚠ 코드·설정에 옛 경로 %d곳(고치지 않음): %s" % (nref, " · ".join(refs)))
    src_n = sum(1 for o, _ in pairs if o.startswith("1_수집/") and not o.lower().endswith(".md"))
    if src_n:
        print("  · 원본 %d개의 색인은 ingest.py 가 해시로 다시 잇는다(옵시디언이 켜져 있으면 brain-source 가 곧)" % src_n)
    return ev


def op_rm(ctx, src, why, count=None, user_asked=False, lenient=False, by_undo=None, core_ok=False, quiet=False):
    rs, a_s = to_rel(ctx, src)
    guard(rs, core_ok)
    if not os.path.exists(a_s):
        if lenient:
            print("  · 건너뜀(없음): %s" % rs)
            return None
        raise Stop("없음: %s" % rs)
    if rs.startswith("1_수집/") and not rs.startswith("1_수집/_색인/") and not user_asked and not by_undo:
        raise Stop("1_수집 원본 지우기는 사용자 지시·보존 일정표 때만(CLAUDE.md §2) — 해당하면 --user-asked")
    info = describe(a_s)
    if info["kind"] == "dir" and info["n"] > BIG and count != info["n"]:
        print("✗ 폴더 안 파일 %d개 — 정말 지우려면 --count %d" % (info["n"], info["n"]))
        sys.exit(2)
    olds = [ctx.rel(f) for f in files_under(a_s)] if info["kind"] == "dir" else [rs]
    nlink = 0 if quiet else count_links_to(ctx, olds)
    memo = [] if quiet or info["kind"] == "dir" else memo_of(ctx, rs)
    if ctx.dry:
        print("미리 보기 · 지움(휴지통) %s%s · 이것을 가리키는 링크 %d곳" % (rs, " (파일 %d)" % info["n"] if info["kind"] == "dir" else "", nlink))
        return None
    slot = trash_slot(ctx, rs)
    move(a_s, ctx.abs(slot))
    if os.path.exists(a_s) or not os.path.exists(ctx.abs(slot)):
        raise Stop("휴지통으로 옮김 확인 실패: %s" % rs)
    ev = ctx.add("rm", src=rs, dst=slot, why=why, undo_of=by_undo, user_asked=user_asked or None, **info)
    print("지움(휴지통) %s → %s" % (rs, slot))
    if nlink:
        print("  ⚠ 이것을 가리키던 링크 %d곳이 깨진다(되살리면 돌아옴)" % nlink)
    if memo:
        print("  · 짝 메모는 남김(사람 것): %s" % ", ".join(memo))
    return ev


def find_event(ctx, key):
    for ev in reversed(load_events(ctx)):
        if ev.get("id") == key:
            return ev
    return None


def op_restore(ctx, key, to=None, by_undo=None, core_ok=False):
    ev = find_event(ctx, key)
    if ev is not None and ev.get("op") != "rm":
        raise Stop("휴지통에 넣은 기록이 아님: %s (%s)" % (key, ev.get("op")))
    if ev is None:
        r = to_rel(ctx, key)[0]
        for e in reversed(load_events(ctx)):
            if e.get("op") == "rm" and e.get("dst", "").lower() == r.lower():
                ev = e
                break
    if ev is None and not to:
        raise Stop("휴지통 기록을 못 찾음: %s — 장부 밖 항목은 휴지통 경로와 --to <자리>로" % key)
    if ev is not None and not ev.get("dst"):
        raise Stop("%s 기록이라 여기서 못 되살린다: %s" % (TRASH_KIND.get(ev.get("trash"), "휴지통 자리 없는"), ev.get("src")))
    slot = ev["dst"] if ev else to_rel(ctx, key)[0]
    target = to_rel(ctx, to)[0] if to else ev["src"]
    guard(target, core_ok)
    if not os.path.exists(ctx.abs(slot)):
        raise Stop("휴지통에 이미 없음(비워졌거나 되살림): %s" % slot)
    if os.path.exists(ctx.abs(target)):
        raise Stop("원래 자리에 이미 무엇이 있다: %s — --to 로 다른 자리" % target)
    if ctx.dry:
        print("미리 보기 · 되살림 %s → %s" % (slot, target))
        return None
    move(ctx.abs(slot), ctx.abs(target))
    out = ctx.add("restore", src=slot, dst=target, of=ev["id"] if ev else None, undo_of=by_undo)
    print("되살림 %s → %s" % (slot, target))
    return out


TRASH_KIND = {"system": "윈도 휴지통(옵시디언 설정)", "none": "영구 삭제(옵시디언 설정)", "gone": "바깥에서 사라짐(follow.py · 윈도 휴지통을 볼 것)"}


def op_record(ctx, op, src, dst=None, trash=None, why=""):
    """밖(옵시디언 안 지우기·이름 바꾸기 — brain-base 가 부름)에서 이미 한 일을 장부에 적는다(볼트 개혁 R5.5).
    옮기지 않는다 — 옵시디언 휴지통(`.trash/<이름>`, 평평함)에 들어간 것만 우리 칸(`.trash/<날짜>/<원래 경로>`)으로
    다시 놓아 되살리기·나이 재기(purge)가 fileops 로 지운 것과 같게 한다. 링크는 옵시디언이 고쳤다(설정 «링크 자동 갱신»)."""
    rs, a_s = to_rel(ctx, src)
    if not rs:
        raise Stop("볼트 뿌리는 적지 않는다")
    if os.path.exists(a_s) and not (dst and same(a_s, to_rel(ctx, dst)[1])):
        raise Stop("원래 자리에 아직 있다 — 적을 일이 아님: %s" % rs)
    why = why or "옵시디언에서 직접"
    if op == "rm":
        user_asked = rs.startswith("1_수집/") and not rs.startswith("1_수집/_색인/") or None   # 사람이 지운 원본
        if not dst:
            if trash not in TRASH_KIND:
                raise Stop("휴지통 자리가 없으면 --trash system|none")
            if ctx.dry:
                print("미리 보기 · 적기 · 지움(%s) %s" % (TRASH_KIND[trash], rs))
                return None
            ev = ctx.add("rm", src=rs, why=why, trash=trash, outside=True, user_asked=user_asked)
            print("적음 · 지움(%s) %s" % (TRASH_KIND[trash], rs))
            return ev
        rd, a_d = to_rel(ctx, dst)
        if not rd.startswith(TRASH + "/") or not os.path.exists(a_d):
            raise Stop("옵시디언 휴지통에 없음: %s" % rd)
        slot = trash_slot(ctx, rs)
        if ctx.dry:
            print("미리 보기 · 적기 · 지움(휴지통) %s — %s → %s" % (rs, rd, slot))
            return None
        move(a_d, ctx.abs(slot))
        ev = ctx.add("rm", src=rs, dst=slot, why=why, outside=True, user_asked=user_asked, **describe(ctx.abs(slot)))
        print("적음 · 지움(휴지통) %s → %s" % (rs, slot))
        return ev
    if op != "mv" or not dst:
        raise Stop("record 는 rm 또는 mv <원래> <새 자리>")
    rd, a_d = to_rel(ctx, dst)
    if not os.path.exists(a_d):
        raise Stop("새 자리에 없음: %s" % rd)
    low = (rs.lower(), rd.lower())
    if any((x[0].lower(), x[1].lower()) == low for x in expect_read(ctx)):
        print("· 이미 적힘(fileops 가 옵시디언에 맡긴 이동): %s → %s" % (rs, rd))
        return None
    t0 = now() - dt.timedelta(seconds=EXPECT_S * 2)
    for e in load_events(ctx)[-30:]:                    # 알림이 늦게 와서 우리 줄이 먼저 적힌 경우
        if e.get("via") in ("obsidian", "follow") and (e.get("src", "").lower(), e.get("dst", "").lower()) == low \
                and dt.datetime.fromisoformat(e["ts"]) >= t0:
            print("· 이미 적힘(%s): %s → %s" % (e["id"], rs, rd))
            return None
    kind = "rename" if posixpath.dirname(rs) == posixpath.dirname(rd) else "mv"
    if ctx.dry:
        print("미리 보기 · 적기 · %s %s → %s" % (LABEL[kind], rs, rd))
        return None
    ev = ctx.add(kind, src=rs, dst=rd, why=why, outside=True, **describe(a_d))
    print("적음 · %s %s → %s" % (LABEL[kind], rs, rd))
    return ev


def same_content_in_vault(ctx, a, skip_rel=None):
    """같은 크기 파일만 해시를 잰다(전체 해시는 1_수집 657MB 를 다 읽는다)."""
    size = os.path.getsize(a)
    h = None
    for r in walk_vault(ctx, skip_rel=(LEDGER_DIR + "/", "3_시스템/_index/")):
        if r == skip_rel:
            continue
        f = ctx.abs(r)
        try:
            if os.path.getsize(f) != size:
                continue
        except OSError:
            continue
        h = h or sha256(a)
        if sha256(f) == h:
            return r
    return None


def op_cp(ctx, src, dst, why, dup_ok=False, by_undo=None, src_label=None, move=False, quiet=False):
    """들이기. move = 원래 것을 옮겨 들인다(수집 대본의 격리 칸 → 1_수집 · 복사 금지 규약) · quiet = 출력 없음(JSON 을 내는 대본)."""
    rs, a_s = to_rel(ctx, src, outside_ok=True)
    if not os.path.isfile(a_s):
        raise Stop("파일이 아님(폴더 들이기는 아직 안 함): %s" % src)
    rd, a_d = to_rel(ctx, dst)
    if os.path.isdir(a_d) or wants_dir(dst):
        rd = (rd + "/" + os.path.basename(a_s)).lstrip("/")
        a_d = ctx.abs(rd)
    guard(rd)
    if os.path.exists(a_d):
        raise Stop("이미 있음: %s — 덮어쓰려면 replace" % rd)
    if not dup_ok:
        dup = same_content_in_vault(ctx, a_s, skip_rel=rs)
        if dup:
            raise Stop("같은 내용이 이미 볼트에 있다: %s — 들이지 않음(그래도 들이려면 --dup-ok)" % dup)
    label = src_label or rs or a_s
    if ctx.dry:
        print("미리 보기 · 들임 %s → %s" % (label, rd))
        return None
    made = made_dirs(a_d)
    os.makedirs(os.path.dirname(a_d), exist_ok=True)
    h = sha256(a_s)
    if move:
        try:
            move_file(a_s, a_d)     # 이름 바꾸기 한 번 — 잠긴 파일에서 사본을 남기지 않는다(11-03 받는 문 시험)
        except Stop:
            for d in made:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            raise
    else:
        shutil.copy2(a_s, a_d)
    info = describe(a_d)
    if info["sha"] != h:
        raise Stop("들인 뒤 내용이 다르다(sha256): %s" % rd)
    ev = ctx.add("cp", src=label, dst=rd, why=why, undo_of=by_undo, made=[ctx.rel(m) for m in made],
                 moved=True if move else None, **info)
    if not quiet:
        print("들임 %s → %s" % (label, rd))
    return ev


_SCRIPT = {}


def intake(src, dst, why, by, vault=None):
    """수집 대본용 들이기(옮김) — 볼트 개혁 R6.3. 장부에 «들임»(by = script:<이름>) · 되돌리면 휴지통으로.
    중복 검사는 대본이 이미 한다(dup_ok) · 새 자리에 이미 있으면 Stop(대본이 이름을 먼저 고른다).
    장부 보기(2_지식/장부.md)는 대본이 끝날 때 한 번 다시 쓴다(atexit)."""
    ctx = _SCRIPT.get(by)
    if ctx is None:
        if not _SCRIPT:
            import atexit
            atexit.register(lambda: [write_view(c) for c in _SCRIPT.values() if c.events])
        ctx = _SCRIPT[by] = Ctx(vault or os.path.dirname(HERE), by=by)
    return op_cp(ctx, src, dst, why, dup_ok=True, move=True, quiet=True)


def op_pdf(ctx, src, dst, why):
    """docx → PDF 로 들임(계획 전용 · Word · docpdf.py) — 원본은 그대로 두고 같은 계획의 다음 줄이 지운다.
    변환이 실패하면 Stop — 보관하기 전엔 지우지 않는다. 되돌리기 = PDF 는 휴지통(장부 cp)."""
    rs, a_s = to_rel(ctx, src, outside_ok=True)
    rd, a_d = to_rel(ctx, dst)
    guard(rd)
    if not os.path.isfile(a_s):
        raise Stop("없음: %s" % src)
    if os.path.exists(a_d):
        raise Stop("이미 있음: %s" % rd)
    if ctx.dry:
        print("미리 보기 · PDF 로 변환해 들임 %s → %s" % (rs or a_s, rd))
        return None
    import docpdf
    with tempfile.TemporaryDirectory() as d:
        tmp = os.path.join(d, os.path.basename(a_d))
        try:
            docpdf.to_pdf(a_s, tmp)
        except RuntimeError as e:
            raise Stop("PDF 변환 실패 — docx 는 그대로: %s (%s)" % (rs or a_s, e))
        return op_cp(ctx, tmp, rd, why, dup_ok=True, src_label=rs or a_s)


def op_replace(ctx, new, dst, why, user_asked=False):
    rd, a_d = to_rel(ctx, dst)
    guard(rd)
    if rd.startswith("1_수집/") and not rd.startswith("1_수집/_색인/") and not user_asked and os.path.exists(a_d):
        raise Stop("1_수집 원본은 내용을 바꾸지 않는다(CLAUDE.md §2) — 지시를 받았으면 --user-asked")
    rn, a_n = to_rel(ctx, new, outside_ok=True)
    if not os.path.isfile(a_n):
        raise Stop("새 파일 없음: %s" % new)
    if os.path.exists(a_d) and os.path.isfile(a_d) and sha256(a_d) == sha256(a_n):
        print("같은 내용 — 바꿀 것 없음: %s" % rd)
        return None
    if ctx.dry:
        print("미리 보기 · 덮어쓰기 %s ← %s (옛것은 휴지통)" % (rd, rn or a_n))
        return None
    if os.path.exists(a_d):
        op_rm(ctx, rd, "덮어쓰기 전 옛 판: " + (why or ""), user_asked=True, quiet=True)
    if rn is not None:
        return op_mv(ctx, rn, rd, why)
    return op_cp(ctx, a_n, rd, why, dup_ok=True)


def op_mkdir(ctx, path, why=None, lenient=False, by_undo=None):
    r, a = to_rel(ctx, path)
    guard(r)
    if os.path.isdir(a):
        print("  · 이미 있음: %s" % r)
        return None
    if ctx.dry:
        print("미리 보기 · 폴더 만듦 %s" % r)
        return None
    os.makedirs(a)
    print("폴더 만듦 %s" % r)
    return ctx.add("mkdir", src=r, why=why, undo_of=by_undo)


def op_rmdir(ctx, path, why=None):
    """빈 폴더만 치운다(계획 끝 — 안을 다 옮기거나 지운 과제 폴더 · work.py) · 무엇이 남았으면 손대지 않고 알림."""
    r, a = to_rel(ctx, path)
    guard(r)
    if not os.path.isdir(a):
        print("  · 폴더 없음: %s" % r)
        return None
    # 파일이 하나도 없으면 빈 것(안에 빈 하위 폴더만 남은 것 포함 — 과제 폴더의 analysis/·fig/ 를 비운 뒤 · 10-31)
    left = [os.path.relpath(os.path.join(dp, f), a) for dp, dns, fns in os.walk(a) for f in fns if f.lower() not in ("desktop.ini", "thumbs.db")]
    if ctx.dry:
        print("미리 보기 · 빈 폴더 치움 %s%s" % (r, "" if not left else " (지금은 %d개 — 앞 줄들이 비우면)" % len(left)))
        return None
    if left:
        print("  ⚠ 비지 않아 둠: %s — %s" % (r, " · ".join(left[:5])))
        return None
    shutil.rmtree(a)  # 남은 것은 탐색기 숨김 파일뿐
    print("빈 폴더 치움 %s" % r)
    return ctx.add("rmdir", src=r, why=why)


FM = re.compile(r"\A(---\r?\n)(.*?)(\r?\n---\r?\n)", re.S)


def set_status(ctx, r, value, why, op, by_undo=None):
    a = ctx.abs(r)
    text, bom = read_text(a)
    m = FM.match(text)
    if not m:
        raise Stop("프론트매터 없음: %s" % r)
    body = m.group(2)
    sm = re.search(r"^status:\s*(.*)$", body, re.M)
    prev = sm.group(1).strip() if sm else None
    if prev == value:
        print("  · 이미 %s: %s" % (value, r))
        return None
    body = (body[:sm.start()] + "status: " + value + body[sm.end():]) if sm else body + "\nstatus: " + value
    body = re.sub(r"^updated:.*$", "updated: " + now().strftime("%Y-%m-%d"), body, count=1, flags=re.M)
    if ctx.dry:
        print("미리 보기 · %s %s (status %s → %s)" % (LABEL[op], r, prev, value))
        return None
    write_text(a, m.group(1) + body + m.group(3) + text[m.end():], bom)
    print("%s %s (status %s → %s)" % (LABEL[op], r, prev or "없음", value))
    return ctx.add(op, src=r, prev=prev, why=why, undo_of=by_undo)


def op_archive(ctx, path, why):
    r, a = to_rel(ctx, path)
    guard(r)
    if not r.lower().endswith(".md") or not os.path.isfile(a):
        raise Stop("md 노트가 아님: %s" % r)
    return set_status(ctx, r, "archived", why, "archive")


# ── 장부 읽기 ─────────────────────────────────────────────────────────────

def load_events(ctx):
    p = ctx.abs(OPS)
    out = []
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    try:
                        out.append(json.loads(ln))
                    except ValueError:
                        continue
    return out


# 튜토리얼 연습 장부(brain-base E1 · git 밖) — hidden = 연습이 남긴 장부 줄 id(최근 300). ops.jsonl 은 덧붙이기만이라 줄은 그대로 두고,
# brain-base 장부 창·휴지통 창·홈 칸처럼 보기(2_지식/장부.md)·«장부 최근»(log)에서만 뺀다. undo·restore·where 는 그대로 다 본다.
PRACTICE_BOOK = ".obsidian/plugins/brain-base/tutorial-practice.json"


def hidden_ids(ctx):
    try:
        with open(ctx.abs(PRACTICE_BOOK), encoding="utf-8") as f:
            h = json.load(f).get("hidden")
    except (OSError, ValueError, AttributeError):
        return set()
    return {x for x in h if isinstance(x, str)} if isinstance(h, list) else set()


def op_undo(ctx, key):
    evs = load_events(ctx)
    group = [e for e in evs if e.get("id") == key] or [e for e in evs if e.get("batch") == key]
    if not group:
        raise Stop("장부에 없는 id: %s" % key)
    done = {e.get("undo_of") for e in evs if e.get("undo_of")}
    n = 0
    for e in reversed(group):           # 뒤에서부터 — 짝 메모(뒤에 적힘)가 먼저 제자리로 가야 원본을 옮길 때 겹치지 않는다
        if e["id"] in done:
            print("  · 이미 되돌림: %s" % e["id"])
            continue
        op = e["op"]
        core = e.get("by") == "update"  # 업데이트가 바꾼 코어는 되돌릴 때도 코어 자리를 쓴다
        if e.get("cfg"):                # 이전이 고친 옵시디언 설정 — 평소 행위가 안 닿는 자리라 여기서 직접 되돌린다
            if op == "cp":
                slot = trash_slot(ctx, e["dst"])
                move(ctx.abs(e["dst"]), ctx.abs(slot))
                r = ctx.add("rm", src=e["dst"], dst=slot, undo_of=e["id"])
            else:
                move(ctx.abs(e["dst"]), ctx.abs(e["src"]))
                r = ctx.add("restore", src=e["dst"], dst=e["src"], of=e["id"], undo_of=e["id"])
        elif op in ("mv", "rename"):
            r = op_mv(ctx, e["dst"], e["src"], "되돌리기 " + e["id"], by_undo=e["id"], core_ok=core)
            drop_made(ctx, e.get("made"))
        elif op == "rm":
            r = op_restore(ctx, e["id"], by_undo=e["id"], core_ok=core)
        elif op in ("cp", "restore"):
            r = op_rm(ctx, e["dst"], "되돌리기 " + e["id"], by_undo=e["id"], core_ok=core, quiet=True)
            drop_made(ctx, e.get("made"))
        elif op == "mkdir":
            a = ctx.abs(e["src"])
            if os.path.isdir(a) and not os.listdir(a):
                os.rmdir(a)
                r = ctx.add("rmdir", src=e["src"], undo_of=e["id"])
                print("빈 폴더 치움 %s" % e["src"])
            else:
                print("  · 폴더가 비어 있지 않아 둠: %s" % e["src"])
                r = None
        elif op in ("archive", "unarchive"):
            r = set_status(ctx, e["src"], e.get("prev") or "active", "되돌리기 " + e["id"], "unarchive", by_undo=e["id"])
        else:
            print("  · 되돌릴 수 없는 행위: %s %s" % (op, e["id"]))
            r = None
        n += 1 if r else 0
    print("되돌림 %d건" % n)


def short(e):
    t = e.get("ts", "")[5:16].replace("T", " ")
    by = e.get("by", "")
    who = {"claude": "Claude", "user": "사람", "update": "업데이트", "obsidian": "옵시디언"}.get(by, by.replace("migration:", "이전 ").replace("script:", ""))
    op = LABEL.get(e.get("op"), e.get("op"))
    path = e.get("src", "") + (" → " + e["dst"] if e.get("dst") else "")
    extra = []
    if e.get("links"):
        extra.append("링크 %d" % e["links"])
    if e.get("kind") == "dir":
        extra.append("파일 %d" % e.get("n", 0))
    if e.get("trash"):
        extra.append(TRASH_KIND.get(e["trash"], e["trash"]))
    if e.get("why"):
        extra.append("까닭: " + e["why"])
    if e.get("undo_of") and e["undo_of"] not in e.get("why", ""):
        extra.append("되돌리기 " + e["undo_of"])
    return t, who, op, path, extra


def op_log(ctx, n, grep):
    hide = hidden_ids(ctx)
    evs = [e for e in load_events(ctx) if not grep or grep.lower() in json.dumps(e, ensure_ascii=False).lower()]
    shown = [e for e in evs if e.get("id") not in hide]
    for e in shown[-n:]:
        t, who, op, path, extra = short(e)
        print("%s %s %s %s%s · %s" % (t, who, op, path, (" · " + " · ".join(extra)) if extra else "", e.get("batch")))
    if len(shown) < len(evs):
        print("(튜토리얼 연습 줄 %d 가림 — ops.jsonl 에는 있음)" % (len(evs) - len(shown)))
    if not shown:
        print("장부에 해당 기록 없음")


def op_where(ctx, name):
    nl = name.lower().replace("\\", "/")
    hits = [e for e in load_events(ctx)
            if nl in (e.get("src", "") + "|" + e.get("dst", "")).lower()]
    if not hits:
        print("장부에 없음: %s — 장부 밖(탐색기·옵시디언에서 직접)의 이동일 수 있다" % name)
        return
    for e in hits[-8:]:
        t, who, op, path, extra = short(e)
        print("%s %s %s %s · %s" % (t, who, op, path, e["id"]))
    last = hits[-1]
    cur = last.get("dst") if last.get("op") != "purge" else None
    if cur:
        print("지금 자리: %s%s" % (cur, "" if os.path.exists(ctx.abs(cur)) else " (⚠ 그 뒤 장부 밖에서 바뀜)"))


def trash_items(ctx):
    root = ctx.abs(TRASH)
    out = []
    if not os.path.isdir(root):
        return out
    today = now().date()
    for d in sorted(os.listdir(root)):
        a = os.path.join(root, d)
        try:
            day = dt.date.fromisoformat(d)
        except ValueError:
            day = dt.date.fromtimestamp(os.path.getmtime(a))     # 옵시디언이 바로 넣은 것(날짜 폴더 없음)
        fs = files_under(a) if os.path.isdir(a) else [a]
        out.append((d, (today - day).days, len(fs), sum(os.path.getsize(f) for f in fs)))
    return out


def op_trash(ctx, older):
    items = [x for x in trash_items(ctx) if x[1] >= older]
    for d, age, n, size in items:
        print("%s · %d일 · 파일 %d · %.1fMB" % (d, age, n, size / 1e6))
    print("휴지통 %d항목 · 파일 %d · %.1fMB%s" % (len(items), sum(x[2] for x in items), sum(x[3] for x in items) / 1e6,
          " (%d일 이상)" % older if older else ""))


def op_purge(ctx, older):
    # 영구 삭제는 되돌릴 수 없다 — Claude(도구 셸)는 못 하게 막는다: 환경 표지 + 대화형 확인 두 겹
    if os.environ.get("CLAUDECODE") == "1" or not sys.stdin.isatty():
        raise Stop("휴지통 비우기(영구 삭제)는 사람만 — 터미널에서 직접 돌리고 확인 글자를 친다")
    items = [x for x in trash_items(ctx) if x[1] >= older]
    if not items:
        print("%d일 지난 항목 없음" % older)
        return
    op_trash(ctx, older)
    if input("위 항목을 영구 삭제합니다. 맞으면 «비우기» 입력: ").strip() != "비우기":
        print("그만둠")
        return
    for d, age, n, size in items:
        a = ctx.abs(TRASH + "/" + d)
        shutil.rmtree(a) if os.path.isdir(a) else os.remove(a)
        ctx.add("purge", src=TRASH + "/" + d, n=n, size=size, why="%d일 지남" % age)
    print("비움 %d항목" % len(items))


# ── 묶음: 계획·이전·업데이트 ───────────────────────────────────────────────

def run_ops(ctx, ops, lenient):
    for i, o in enumerate(ops, 1):
        k = o.get("op")
        try:
            if k == "mv":
                op_mv(ctx, o["src"], o["dst"], o.get("why", ""), lenient=lenient)
            elif k == "rm":
                op_rm(ctx, o["src"], o.get("why", ""), count=o.get("count"), user_asked=o.get("user_asked", False), lenient=lenient)
            elif k == "mkdir":
                op_mkdir(ctx, o["path"], o.get("why"), lenient=lenient)
            elif k == "rmdir":
                op_rmdir(ctx, o["path"], o.get("why"))
            elif k == "archive":
                op_archive(ctx, o["path"], o.get("why", ""))
            elif k == "cp":
                op_cp(ctx, o["src"], o["dst"], o.get("why", ""), dup_ok=o.get("dup_ok", False))
            elif k == "pdf":
                op_pdf(ctx, o["src"], o["dst"], o.get("why", ""))
            else:
                raise Stop("모르는 행위: %s" % k)
        except Stop as e:
            raise Stop("%d번째(%s)에서 멈춤: %s" % (i, k, e))


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def op_plan(ctx, path, apply):
    plan = load_json(path)
    ops = plan.get("ops", [])
    print("계획 %s · %d건%s" % (plan.get("title", os.path.basename(path)), len(ops), "" if apply else " (미리 보기 — 실행 = --apply)"))
    ctx.dry = not apply
    run_ops(ctx, ops, lenient=False)


def fix_obsidian_settings(ctx, moved, mid):
    """이전이 옮긴 자리를 옵시디언 설정(책갈피·그래프·폴더 설정·열린 탭)에서도 고친다 — 옵시디언을 닫고 돌리므로 옵시디언이 스스로 못 고친다.
    플러그인 data.json 은 사용자 것이라 열지 않는다(남은 옛 경로는 user_refs 가 알린다). 옛 판은 휴지통 · 이전 묶음과 함께 되돌린다."""
    ob = ctx.abs(".obsidian")
    if not moved or not os.path.isdir(ob):
        return
    for f in sorted(os.listdir(ob)):
        a = os.path.join(ob, f)
        if not f.endswith(".json") or not os.path.isfile(a):
            continue
        r = ".obsidian/" + f
        try:
            text, bom = read_text(a)
        except (OSError, UnicodeDecodeError):
            continue
        out = text
        for s, d in moved:      # 파일 이동이 폴더 이동보다 먼저 적혀 있다(이전 파일의 순서)
            out = re.sub(r"(?<![\w/\-])" + re.escape(s) + r'(?=[/"\\)\s]|$)', lambda m, d=d: d, out)
        if out == text:
            continue
        if ctx.dry:
            print("  옵시디언 설정 고칠 것: %s" % r)
            continue
        slot = trash_slot(ctx, r)
        move(a, ctx.abs(slot))
        ctx.add("rm", src=r, dst=slot, why="이전 %s: 옛 경로" % mid, cfg=True, **describe(ctx.abs(slot)))
        write_text(a, out, bom)
        ctx.add("cp", src="migration:" + mid, dst=r, why="이전 %s: 새 경로" % mid, cfg=True, **describe(a))
        print("  옵시디언 설정 고침: %s" % r)


def user_refs(ctx, olds, table):
    """사용자 쪽에 남은 옛 경로(기억·플러그인 설정·사용자가 만든 대본) — 배포판이 실어 온 파일은 뺀다(옛 경로를 적는 것이 본업인 이전 도구·시험 자료)."""
    hits, _ = code_refs(ctx, olds, limit=10 ** 6)
    ob = ctx.abs(".obsidian/plugins")
    pats = set(olds) | {o.replace("/", "\\\\") for o in olds}
    for name in (os.listdir(ob) if os.path.isdir(ob) else []):
        a = os.path.join(ob, name, "data.json")
        try:
            with open(a, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        if any(p in text for p in pats):
            hits.append(".obsidian/plugins/%s/data.json:1" % name)
    try:
        known = load_json(table).get("paths", {})
    except (OSError, ValueError):
        known = {}
    return [h for h in hits if h.rsplit(":", 1)[0] not in known]


def op_migrate(ctx, apply, undo=None, from_dir=None):
    state_p = ctx.abs(MIGRATED)
    state = load_json(state_p) if os.path.exists(state_p) else {"applied": {}}
    if undo:
        rec = state["applied"].get(undo)
        if not rec:
            raise Stop("적용 기록 없는 이전: %s" % undo)
        op_undo(ctx, rec["batch"])
        del state["applied"][undo]
        save_json(state_p, state)
        print("이전 되돌림: %s" % undo)
        return
    if from_dir and apply:
        raise Stop("--from 은 미리 보기 전용이다 — 적용은 업데이트로 들어온 이전 파일로")
    d = from_dir or ctx.abs(MIGRATIONS)      # 업데이트 전 미리 보기 = 아직 볼트에 없는 이전 파일을 배포판에서 읽는다
    files = sorted(f for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []
    pending = [f for f in files if f[:-5] not in state["applied"]]
    if not pending:
        print("밀린 이전 없음(적용 %d)" % len(state["applied"]))
        return
    for f in pending:
        m = load_json(os.path.join(d, f))
        mid = f[:-5]
        ops = m.get("ops", [])
        print("이전 %s — %s · %d건%s" % (mid, m.get("title", ""), len(ops), "" if apply else " (미리 보기)"))
        sub = Ctx(ctx.vault, by="migration:" + mid, dry=not apply)
        sub.quiet_refs = True
        run_ops(sub, ops, lenient=True)
        if apply:
            moved = [(e["src"], e["dst"]) for e in sub.events if e["op"] in ("mv", "rename") and not e.get("parent")]
        else:
            moved = []
            for o in ops:
                if o.get("op") == "mv" and os.path.exists(ctx.abs(o["src"])):
                    t = o["dst"] + "/" + posixpath.basename(o["src"]) if os.path.isdir(ctx.abs(o["dst"])) else o["dst"]
                    moved.append((o["src"], t))
        fix_obsidian_settings(sub, moved, mid)
        table = os.path.join(os.path.abspath(from_dir), "..", "..", *KNOWN_TABLE.split("/")) if from_dir else ctx.abs(KNOWN_TABLE)
        left = user_refs(sub, [s for s, _ in moved], table) if moved else []
        if left:
            print("  ⚠ 사용자 쪽에 옛 경로 %d곳(고치지 않음 · 개인 층이라 사람이 본다):" % len(left))
            for h in left[:30]:
                print("    " + h)
            if len(left) > 30:
                print("    … 외 %d곳" % (len(left) - 30))
        if apply:
            state["applied"][mid] = {"ts": now().isoformat(timespec="seconds"), "batch": sub.batch, "ops": len(sub.events)}
            save_json(state_p, state)
            ctx.events += sub.events
    if not apply:
        print("실행 = migrate --apply · 되돌리기 = migrate --undo <이전 id>")


def op_update(ctx, path, apply):
    """dist-diff --plan-out 이 만든 계획: {"source", "version", "ops": [{"op": "put"|"remove", "rel", "src", "why"}], "conflicts": [...]}.
    옛 판은 휴지통으로 — 업데이트 하나를 묶음 id 하나로 통째 되돌릴 수 있다. conflicts = 못 합친 파일 · 건드리지 않는다."""
    plan = load_json(path)
    ops = plan.get("ops", [])
    ver = plan.get("version", "")
    conflicts = plan.get("conflicts", [])
    ctx.by = "update"
    print("업데이트 %s · %d건%s" % (ver, len(ops), "" if apply else " (미리 보기 — 실행 = --apply)"))
    for o in ops:
        guard(o["rel"], core_ok=True)
        if o["op"] == "put" and not os.path.isfile(o["src"]):
            raise Stop("배포판 파일 없음: %s" % o["src"])
    if not apply:
        for o in ops:
            have = os.path.exists(ctx.abs(o["rel"]))
            print("  %s %s" % (o.get("why") or ("바꿈" if o["op"] == "put" and have else "넣음" if o["op"] == "put" else "뺌(휴지통)"), o["rel"]))
        for c in conflicts:
            print("  ⛔ 못 합침(그대로 둠) %s — %s" % (c["rel"], c.get("why", "")))
        return
    for o in ops:
        r, a = o["rel"], ctx.abs(o["rel"])
        if o["op"] == "put":
            if os.path.isfile(a) and sha256(a) == sha256(o["src"]):
                continue
            if os.path.exists(a):
                slot = trash_slot(ctx, r)
                move(a, ctx.abs(slot))
                ctx.add("rm", src=r, dst=slot, why="업데이트 %s: 옛 판" % ver, **describe(ctx.abs(slot)))
            os.makedirs(os.path.dirname(a), exist_ok=True)
            shutil.copy2(o["src"], a)
            ctx.add("cp", src="dist:" + r, dst=r, why="업데이트 %s" % ver, **describe(a))
        elif o["op"] == "remove" and os.path.exists(a):
            slot = trash_slot(ctx, r)
            move(a, ctx.abs(slot))
            ctx.add("rm", src=r, dst=slot, why="업데이트 %s: 배포판에서 빠짐" % ver, **describe(ctx.abs(slot)))
    print("업데이트 적용 %d건 · 되돌리기 = undo %s" % (len(ctx.events), ctx.batch))
    if conflicts:
        print("⛔ 못 합쳐 그대로 둔 파일 %d개 — 하나씩 정해야 한다: %s" % (len(conflicts), " · ".join(c["rel"] for c in conflicts)))


def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


# ── 보기(2_지식/장부.md) ───────────────────────────────────────────────────

def write_view(ctx):
    hide = hidden_ids(ctx)  # 튜토리얼 연습 줄(위 PRACTICE_BOOK)
    evs = [e for e in load_events(ctx) if e.get("id") not in hide][-VIEW_N:]
    p = ctx.abs(VIEW)
    created = now().strftime("%Y-%m-%d")
    if os.path.exists(p):
        m = re.search(r"^created:\s*(\S+)", open(p, encoding="utf-8").read(), re.M)
        created = m.group(1) if m else created
    L = ["---", "type: episodic", "title: 장부 — 볼트 행위 기록", "created: " + created,
         "updated: " + now().strftime("%Y-%m-%d"), "tags: [생성파일, 장부]", "status: active", "---",
         "# 장부", "",
         "> 생성 파일 — 고치지 않는다(원본 = `%s` · 만드는 이 = `3_시스템/fileops.py`). 최근 %d건 · 새것이 위." % (OPS, VIEW_N),
         "> 되돌리기 `py -3 3_시스템/fileops.py undo <묶음 id>` · 되살리기 `… restore <id>` · 찾기 `… where <이름>`", ""]
    day = None
    for e in reversed(evs):
        d = e.get("ts", "")[:10]
        if d != day:
            day = d
            L += ["", "## " + d]
        t, who, op, path, extra = short(e)
        L.append("- %s · %s · %s `%s`%s · `%s`" % (t[6:], who, op, path.replace(" → ", "` → `"),
                 (" · " + " · ".join(extra)) if extra else "", e.get("batch")))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


# ── 입구 ─────────────────────────────────────────────────────────────────

def main(argv=None):
    ap = argparse.ArgumentParser(prog="fileops", description="볼트 안 지우기·옮기기·이름 바꾸기 — 장부·휴지통·링크 고침")
    ap.add_argument("--vault", default=os.path.dirname(HERE), help="대상 볼트(기본 = 이 대본의 볼트 · 업데이터는 남의 볼트를 준다)")
    ap.add_argument("--by", help="장부의 «누가»(기본 = Claude 셸이면 claude, 아니면 user · 대본은 script:<이름>)")
    ap.add_argument("--dry", action="store_true", help="미리 보기 — 아무것도 바꾸지 않는다")
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("mv", help="옮기기·이름 바꾸기")
    p.add_argument("src"); p.add_argument("dst"); p.add_argument("--why", default="")
    p = sp.add_parser("rm", help="휴지통으로")
    p.add_argument("src"); p.add_argument("--why", default=""); p.add_argument("--count", type=int)
    p.add_argument("--user-asked", action="store_true", help="1_수집 원본 — 사용자 지시가 있을 때만")
    p = sp.add_parser("restore", help="휴지통에서 되살리기")
    p.add_argument("key", help="rm 행위 id 또는 휴지통 경로"); p.add_argument("--to")
    p = sp.add_parser("undo", help="행위·묶음 되돌리기")
    p.add_argument("key")
    p = sp.add_parser("cp", help="들이기(볼트 밖 → 안)")
    p.add_argument("src"); p.add_argument("dst"); p.add_argument("--why", default=""); p.add_argument("--dup-ok", action="store_true")
    p = sp.add_parser("replace", help="덮어쓰기(옛것은 휴지통)")
    p.add_argument("new"); p.add_argument("dst"); p.add_argument("--why", default=""); p.add_argument("--user-asked", action="store_true")
    p = sp.add_parser("mkdir")
    p.add_argument("path"); p.add_argument("--why")
    p = sp.add_parser("archive", help="status: archived")
    p.add_argument("path"); p.add_argument("--why", default="")
    p = sp.add_parser("plan", help="여러 행위를 한 묶음으로")
    p.add_argument("file"); p.add_argument("--apply", action="store_true")
    p = sp.add_parser("migrate", help="밀린 이전(3_시스템/migrations)")
    p.add_argument("--apply", action="store_true"); p.add_argument("--undo")
    p.add_argument("--from", dest="from_dir", help="미리 보기 전용 — 아직 볼트에 없는 이전 파일을 배포판 폴더에서 읽는다")
    p = sp.add_parser("update", help="배포판 코어 바꾸기(업데이터 전용)")
    p.add_argument("file"); p.add_argument("--apply", action="store_true")
    p = sp.add_parser("record", help="밖(옵시디언)에서 이미 한 지우기·옮기기를 장부에 적기")
    p.add_argument("op", choices=["rm", "mv"]); p.add_argument("src"); p.add_argument("dst", nargs="?")
    p.add_argument("--trash", choices=["system", "none"], help="rm 인데 옵시디언 휴지통이 아닐 때"); p.add_argument("--why", default="")
    p = sp.add_parser("log")
    p.add_argument("-n", type=int, default=20); p.add_argument("--grep")
    p = sp.add_parser("where")
    p.add_argument("name")
    p = sp.add_parser("trash")
    p.add_argument("--older", type=int, default=0)
    p = sp.add_parser("purge", help="휴지통 영구 비우기 — 사람만")
    p.add_argument("--older", type=int, default=30)
    p = sp.add_parser("who", help="이 파일·폴더를 쥔 프로그램")
    p.add_argument("path")
    sp.add_parser("view", help="장부 보기(2_지식/장부.md)만 다시 쓰기 — 튜토리얼이 연습 줄을 가린 뒤")
    a = ap.parse_args(argv)

    ctx = Ctx(a.vault, by=a.by, dry=a.dry)
    try:
        c = a.cmd
        if c == "mv":
            op_mv(ctx, a.src, a.dst, a.why)
        elif c == "rm":
            op_rm(ctx, a.src, a.why, count=a.count, user_asked=a.user_asked)
        elif c == "restore":
            op_restore(ctx, a.key, a.to)
        elif c == "undo":
            op_undo(ctx, a.key)
        elif c == "cp":
            op_cp(ctx, a.src, a.dst, a.why, dup_ok=a.dup_ok)
        elif c == "replace":
            op_replace(ctx, a.new, a.dst, a.why, user_asked=a.user_asked)
        elif c == "mkdir":
            op_mkdir(ctx, a.path, a.why)
        elif c == "archive":
            op_archive(ctx, a.path, a.why)
        elif c == "plan":
            op_plan(ctx, a.file, a.apply)
        elif c == "migrate":
            op_migrate(ctx, a.apply, a.undo, a.from_dir)
        elif c == "update":
            op_update(ctx, a.file, a.apply)
        elif c == "record":
            op_record(ctx, a.op, a.src, a.dst, a.trash, a.why)
        elif c == "log":
            op_log(ctx, a.n, a.grep)
        elif c == "where":
            op_where(ctx, a.name)
        elif c == "trash":
            op_trash(ctx, a.older)
        elif c == "purge":
            op_purge(ctx, a.older)
        elif c == "who":
            note = held_note(to_rel(ctx, a.path)[1])
            if note:
                print(note)
        elif c == "view":
            write_view(ctx)
    except Stop as e:
        print("✗ %s" % e)
        if ctx.events:
            print("  (멈추기 전 %d건은 했다 — 되돌리기 = undo %s)" % (len(ctx.events), ctx.batch))
            write_view(ctx)
        return 1
    if ctx.events:
        write_view(ctx)
        if c not in ("update",):
            print("묶음 %s" % ctx.batch)
    return 0


if __name__ == "__main__":
    sys.exit(main())
