#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""주인 장부 — 볼트 일이 띄운 프로세스에 주인(Claude 세션)과 수명을 붙이고, 주인이 끝나거나 수명이 넘은 것을 되찾는다.

왜: 띄운 것에 주인·수명이 없으면 끝나는 길이 «그 세션이 잊지 않고 끔» 하나뿐이다. 제작자 볼트에서 끝난 세션의 배경 작업이
코어 1개를 3일 먹었고 · 시험 에뮬레이터가 이틀 · 고아 찾기 명령이 1시간 남았다. 그리고 Claude 가 남의 프로세스를 끄면 자동 모드
분류기가 막는다 → 끄는 것은 이 대본의 tick(예약 작업 · Claude 밖)과 사람 누름뿐이다. 설명서 = 3_시스템/설명서/되찾기.md

  py -3 3_시스템/own.py run --kind <종류> [--ttl 3h] [--keep] -- <명령…>   Job 안에서 띄움 · 주인이 죽거나 수명이 넘으면 자식째 끝
  py -3 3_시스템/own.py list [--json]       지금 프로세스를 주인별로(주인 · 쉼 · 종류 · 코어 · 사유 MB · 판정)
  py -3 3_시스템/own.py tick [--dry]        되찾기 한 번(예약 작업이 10분마다 · --dry = 끌 것만 보임)
  py -3 3_시스템/own.py end [<세션 id 앞 8자>]  그 세션의 장부·시험 프로세스 끝(비우면 조상 세션 · SessionEnd 훅용)
  py -3 3_시스템/own.py kill-tests          남은 시험 프로세스 끄기(건강 «고치기» · 사람이 고를 때 · drift.py --kill-test 가 부름)
  py -3 3_시스템/own.py install | remove | status | installed   예약 작업 «외부뇌 되찾기»(볼트 밖 설정 — 사람이 허락)

주인 = 가장 가까운 조상 claude.exe 의 세션 장부(~/.claude/sessions/<pid>.json · 앱이 씀 · 세션 id·이름·쉼/일함).
일한 때 = 그 세션 대화 기록(.jsonl)의 수정 시각 · 지금 «busy» 면 지금.
규칙마다 기능 단계 하나(켬 = high · 끔 = off · 문턱 = 그 선언의 params · 기본 = 다 켬 · 사용자 11-19 «기능별로 나눌 것»):
  R1 proc.reclaim.owner — 장부에 있고 주인 세션이 죽었거나 수명이 넘음(--keep 이면 주인이 살아 있는 동안 둠)
  R2 proc.reclaim.test — 시험 종류(시험 AVD 에뮬레이터 · 격리 옵시디언 · 머리 없는 크롬) · 시험 잠금 없음 · 주인 없음 또는 test_idle_hours 넘게 쉼
  R3 proc.reclaim.background — 주인 세션 아래 배경 작업(claude.exe 자신·훅 제외)이 주인 bg_idle_hours 넘게 일 없는 동안 직전 tick 부터 bg_core 코어 넘게 먹음
     — 오래 걸릴 계산은 `own.py run --keep --ttl …` 로 띄운다(장부에 든 것은 R3 에서 빠짐)
  R4 proc.reclaim.session — Claude 세션 자신이 session_close_hours 넘게 일 없음 → 닫음(앞서 폰 알림 «닫음: 이름» — 모바일 연결이 있을 때 · 다시 열면 이어짐 · 캐시는 새로)
  압박 proc.reclaim.pressure — 남은 램 < press_avail_gb 또는 커밋 > 램 × press_commit_ratio 이면 R2·R3 의 쉼 문턱을 press_idle_hours 로.
끄지 않는 것: 사용자 옵시디언·크롬·터미널 · 상주(서버·예약 작업) · 볼트 밖 → list·doctor 에 보이기만.
이 PC 값 = 3_시스템/own.local.json(git 밖 · 선택 · 없으면 시험 AVD 없음·기본 잠금으로 돎): {"test_avds": [시험 AVD 이름], "locks": [시험 잠금 glob · 볼트 상대]}.
  만들기·고치기 = py -3 3_시스템/own.py local [--avd 이름…] [--lock glob…] [--clear]   (인자 없이 = 지금 값 보기)
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
DIR = os.path.join(HERE, "_index", "own")
LEDGER = os.path.join(DIR, "run")            # <pid>-<시작>.json — run 이 쓰고 끝나면 지움
STATE = os.path.join(DIR, "tick.json")       # 직전 tick 의 CPU 초(R3 평균)
LOG = os.path.join(DIR, "reclaim.jsonl")     # 끈 것·판정 기록
SESS = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude"), "sessions")
PROJ = os.path.join(os.path.dirname(SESS), "projects")
TASK = "외부뇌 되찾기"
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# 기능 단계 선언(options.registry.json «proc.reclaim.*» params)이 없을 때의 값
DEFAULTS = {"test_idle_hours": 2.0, "bg_idle_hours": 6.0, "bg_core": 0.5, "session_close_hours": 72,
            "press_avail_gb": 1.5, "press_commit_ratio": 2.0, "press_idle_hours": 0.5}
LOCAL = os.path.join(HERE, "own.local.json")
LOCKS = ["3_시스템/_index/*/heavy.lock", "3_시스템/_index/*/*/heavy.lock"]   # 무거운 시험 자원을 쥔 표시(있으면 시험 프로세스는 쓰는 중)
HEAVY_H = 6                                  # drift.py 와 같음 — 이보다 오래된 시험 잠금은 묵은 것(풀기를 잊음)
NEVER = re.compile(r"^(claude|explorer|windowsterminal|openconsole|conhost|dwm|svchost|system|registry|csrss|winlogon|lsass|services|smss|"
                   r"msmpeng|code|devenv)\.exe$", re.I)
FEATURES = {"R1": "proc.reclaim.owner", "R2": "proc.reclaim.test", "R3": "proc.reclaim.background",
            "R4": "proc.reclaim.session", "press": "proc.reclaim.pressure"}


def _sys_rel():
    try:
        sys.path.insert(0, HERE)
        import roles
        return roles.path("system")
    except Exception:  # noqa: BLE001
        return os.path.basename(HERE)


HOOK = re.compile(re.escape(_sys_rel()) + r"[/\\]hooks[/\\]|session-stub\.py|idle-save\.py", re.I)


def levels():
    """{규칙: high|off} — options 가 없거나 못 읽으면 high(켬)"""
    out = {}
    try:
        sys.path.insert(0, HERE)
        import options
    except Exception:  # noqa: BLE001
        return {r: "high" for r in FEATURES}
    for r, fid in FEATURES.items():
        try:
            out[r] = options.level(fid)
        except Exception:  # noqa: BLE001
            out[r] = "high"
    return out


def cfg(lv=None):
    """문턱(규칙마다 선언 params[단계] → 기본값) + 켬/끔 + 이 PC 값(own.local.json)"""
    lv = levels() if lv is None else lv
    c = dict(DEFAULTS)
    try:
        import options
        for r, fid in FEATURES.items():
            if lv.get(r, "high") != "off":
                c.update({k: v for k, v in (options.params(fid, lv.get(r, "high")) or {}).items() if k in DEFAULTS})
    except Exception:  # noqa: BLE001
        pass
    loc = {}
    try:
        with open(LOCAL, encoding="utf-8") as h:
            loc = json.load(h)
    except (OSError, ValueError):
        pass
    c["test_avds"] = set(x for x in loc.get("test_avds", []) if isinstance(x, str)) if isinstance(loc, dict) else set()
    c["locks"] = LOCKS + [x for x in (loc.get("locks", []) if isinstance(loc, dict) else []) if isinstance(x, str)]
    c["on"] = {r: lv.get(r, "high") != "off" for r in FEATURES}
    return c


CFG = None


def C():
    global CFG
    if CFG is None:
        CFG = cfg()
    return CFG


def alert_script():
    """모바일 연결 모듈의 알림 대본 — 모듈이 꺼졌거나 없으면 None"""
    p = os.path.join(VAULT, ".claude", "skills", "mobility", "scripts", "alert.py")
    try:
        import roles
        if not roles.module_on("mobility"):
            return None
    except Exception:  # noqa: BLE001
        pass
    return p if os.path.exists(p) else None


try:
    import psutil
except ImportError:          # 없으면 list·tick 는 아무것도 안 함(run 은 됨)
    psutil = None


def _now():
    return time.time()


def _mkdirs():
    os.makedirs(LEDGER, exist_ok=True)


# ── 세션 장부 ────────────────────────────────────────────────────────────
def _proj_dir(cwd):
    return os.path.join(PROJ, re.sub(r"[^A-Za-z0-9]", "-", cwd or ""))


def sessions():
    """{pid: {sid, name, kind, busy, last, alive}} — 앱의 세션 장부 · 일한 때 = 대화 기록 수정 시각(busy 면 지금)"""
    out = {}
    for f in glob.glob(os.path.join(SESS, "*.json")):
        try:
            with open(f, encoding="utf-8") as h:
                d = json.load(h)
            pid = int(d["pid"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        alive = bool(psutil and psutil.pid_exists(pid))
        if alive:
            try:
                p = psutil.Process(pid)
                alive = p.name().lower() == "claude.exe" and abs(p.create_time() * 1000 - (d.get("startedAt") or 0)) < 120000
            except Exception:  # noqa: BLE001
                alive = False
        sid = d.get("sessionId") or ""
        tx = os.path.join(_proj_dir(d.get("cwd")), sid + ".jsonl")
        last = os.path.getmtime(tx) if os.path.exists(tx) else (d.get("updatedAt") or 0) / 1000
        busy = d.get("status") == "busy"
        out[pid] = {"sid": sid, "short": sid[:8], "name": d.get("name") or "", "entry": d.get("entrypoint") or "", "busy": busy,
                    "last": _now() if busy else last, "alive": alive}
    return out


# ── 프로세스 표 ───────────────────────────────────────────────────────────
CAND = re.compile(r"^(emulator|qemu-system-[\w.-]+|obsidian|chrome|msedge|chrome-headless-shell)\.exe$", re.I)


def table(sess=None):
    """{pid: {ppid, name, cmd, start, cpu, priv}} — 목록은 Toolhelp 한 번(drift.processes · 0.05초 · psutil 의 부모 찾기는 프로세스마다
    목록을 다시 떠 400개에 9초 · 11-19 잼) · 명령 줄·CPU 는 주인 세션 아래이거나 시험 종류 이름인 것만"""
    out = {}
    if not psutil:
        return out
    sys.path.insert(0, HERE)
    import drift
    snap = drift.processes()
    for pid, (ppid, name, priv, _cmd) in snap.items():
        ft = drift._start(pid) if pid else None
        out[pid] = {"ppid": ppid, "name": name or "", "start": ft / 1e7 - 11644473600 if ft else 0, "cmd": "", "cpu": None, "priv": priv}
    sess = sessions() if sess is None else sess
    for pid, r in out.items():
        if not (CAND.match(r["name"]) or owner_of(pid, out, sess)):
            continue
        try:
            p = psutil.Process(pid)
            r["cmd"] = " ".join(p.cmdline())
            r["cpu"] = sum(p.cpu_times()[:2])
        except Exception:  # noqa: BLE001
            pass
    return out


def owner_of(pid, procs, sess):
    """가장 가까운 조상 Claude 세션 pid(부모가 자식보다 늦게 떴으면 pid 재사용 = 끊긴 줄) · 없으면 None"""
    seen, cur = set(), pid
    while cur in procs and cur not in seen:
        seen.add(cur)
        pp = procs[cur]["ppid"]
        if pp in sess and sess[pp]["alive"] and cur != pp:
            return pp
        if pp not in procs or procs[pp]["start"] > procs[cur]["start"] + 1:
            return None
        cur = pp
    return None


def kind_of(row):
    """시험 종류 · 없으면 ''"""
    n, c = row["name"].lower(), row["cmd"]
    if re.match(r"^(emulator|qemu-system-[\w.-]+)\.exe$", n):
        m = re.search(r"-avd\s+(\S+)", c)
        return "에뮬레이터" if m and m.group(1) in C()["test_avds"] else ""
    if n == "obsidian.exe" and "--type=" not in c:
        m = re.search(r'--user-data-dir=(?:"([^"]+)"|(\S+))', c)
        home = os.path.normcase(os.path.normpath(os.path.join(os.environ.get("APPDATA", ""), "obsidian")))
        if m and os.path.normcase(os.path.normpath(m.group(1) or m.group(2))) != home:
            return "격리 옵시디언"
    if n in ("chrome.exe", "msedge.exe", "chrome-headless-shell.exe") and "--type=" not in c and ("--headless" in c or "ms-playwright" in c.lower()):
        return "머리 없는 크롬"
    return ""


def heavy_locked():
    return any(_now() - os.path.getmtime(p) < HEAVY_H * 3600 for g in C()["locks"] for p in glob.glob(os.path.join(VAULT, *g.split("/"))))


def ledger():
    """{pid: 항목} — 죽은 pid 의 항목은 지움(시작 시각이 다르면 pid 재사용)"""
    out = {}
    for f in glob.glob(os.path.join(LEDGER, "*.json")):
        try:
            with open(f, encoding="utf-8") as h:
                e = json.load(h)
        except (OSError, ValueError):
            continue
        ok = psutil and psutil.pid_exists(e["pid"])
        if ok:
            try:
                ok = abs(psutil.Process(e["pid"]).create_time() - e["start"]) < 2
            except Exception:  # noqa: BLE001
                ok = False
        if ok:
            e["_file"] = f
            out[e["pid"]] = e
        else:
            try:
                os.remove(f)
            except OSError:
                pass
    return out


def family(pid, procs):
    """pid 와 그 아래(부모보다 먼저 뜬 것은 뺌 — pid 재사용)"""
    sub = {}
    for p, r in procs.items():
        sub.setdefault(r["ppid"], []).append(p)
    out, todo = [], [pid]
    while todo:
        q = todo.pop()
        if q in out or q not in procs:
            continue
        out.append(q)
        todo += [c for c in sub.get(q, []) if c != q and procs[c]["start"] >= procs[q]["start"] - 1]
    return out


def machine():
    try:
        vm = psutil.virtual_memory()
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [(n, ctypes.c_ulonglong) for n in ("total", "avail", "tp", "ap", "tv", "av", "ae")]
        m = MS()
        m.len = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return {"ram": vm.total / 2 ** 30, "avail": vm.available / 2 ** 30, "commit": (m.tp - m.ap) / 2 ** 30}
    except Exception:  # noqa: BLE001
        return {}


# ── 판정 ──────────────────────────────────────────────────────────────────
def judge(procs=None, sess=None, prev=None, now=None):
    """[(pid, 규칙, 까닭, 행)] 끌 것 · 그리고 보일 것 목록 rows"""
    sess = sessions() if sess is None else sess
    procs = table(sess) if procs is None else procs
    now = _now() if now is None else now
    prev = prev or {}
    c = C()
    m = machine()
    press = c["on"]["press"] and bool(m) and (m["avail"] < c["press_avail_gb"] or m["commit"] > c["press_commit_ratio"] * m["ram"])
    t_idle = c["press_idle_hours"] if press else c["test_idle_hours"]
    b_idle = c["press_idle_hours"] if press else c["bg_idle_hours"]
    led = ledger()
    locked = heavy_locked()
    kill, rows = [], []
    span = now - prev.get("t", now)
    for pid, r in procs.items():
        if not pid or NEVER.match(r["name"]):
            continue
        o = owner_of(pid, procs, sess)
        s = sess.get(o) if o else None
        idle_h = (now - s["last"]) / 3600 if s else None
        k = kind_of(r)
        core = None
        pv = prev.get("cpu", {}).get(str(pid))
        if pv and r["cpu"] is not None and span > 60 and abs(pv[1] - r["start"]) < 2:
            core = (r["cpu"] - pv[0]) / span
        e = led.get(pid)
        why = None
        if e:
            # 주인 없이 띄운 것(사람·예약 작업)은 수명으로만 · --keep 은 주인이 살아 있는 동안 수명을 안 봄
            dead = e.get("owner") is not None and not (e["owner"] in sess and sess[e["owner"]]["alive"])
            over = e.get("ttl") and now - e["start"] > e["ttl"]
            if dead or (over and not (e.get("keep") and e.get("owner") is not None)):
                why = ("R1", "장부 · " + ("주인 끝남" if dead else "수명 %.1f시간 넘음" % (e["ttl"] / 3600)))
        # 주인 없음 = 분리 실행(Start-Process 등)으로 부모 줄이 끊긴 것도 든다 — 쓰는 중일 수 있어 띄운 지 쉼 문턱만큼은 둔다
        # (11-20 01:45·01:55 잼: 하위 세션이 분리 실행해 쓰던 에뮬레이터를 띄운 지 4분·9분에 두 번 끔 · 시험 잠금도 없었음)
        elif k and not locked and ((s is None and (now - r["start"]) / 3600 > t_idle) or (s is not None and not s["busy"] and idle_h > t_idle)):
            why = ("R2", "%s · %s" % (k, "주인 없음" if s is None else "주인 %.1f시간 쉼" % idle_h))
        elif s and not s["busy"] and idle_h > b_idle and core is not None and core > c["bg_core"] and not HOOK.search(r["cmd"]) and r["name"].lower() != "claude.exe":
            why = ("R3", "배경 작업 %.1f코어 · 주인 «%s» %.1f시간 일 없음" % (core, s["name"][:20], idle_h))
        if o or k or e:
            rows.append({"pid": pid, "name": r["name"], "kind": k or (e or {}).get("kind", ""), "owner": (s or {}).get("name", "")[:24],
                         "owner_short": (s or {}).get("short", ""), "idle_h": idle_h, "core": core, "priv_mb": r["priv"] >> 20,
                         "age_h": (now - r["start"]) / 3600, "rule": why[0] if why else "", "why": why[1] if why else ""})
        if why:
            kill.append((pid, why[0], why[1], r))
    for pid, s in sess.items():
        if s["alive"] and not s["busy"] and pid in procs and now - s["last"] > c["session_close_hours"] * 3600:
            kill.append((pid, "R4", "Claude 세션 «%s» %d시간 일 없음" % (s["name"][:30], (now - s["last"]) / 3600), procs[pid]))
    info_hold = [k for k in kill if not c["on"].get(k[1], True)]       # 꺼 둔 규칙 = 끄지 않고 보이기만
    kill = [k for k in kill if k not in info_hold]
    # 가족째 끌 것 가운데 이미 다른 것의 아래에 든 것은 뺌
    top = {p for p, *_ in kill}
    kill = [x for x in kill if not any(x[0] in family(q, procs) and q != x[0] for q in top)]
    return kill, rows, {"press": press, **m, "sessions": sum(1 for s in sess.values() if s["alive"]), "on": [r for r, v in c["on"].items() if v],
                        "held": [(p, r, w) for p, r, w, _x in info_hold]}


def notify(title, text):
    """폰 알림 한 줄(mobility 가 있을 때) · 실패해도 계속"""
    a = alert_script()
    if a:
        try:
            subprocess.run([sys.executable, a, "now", title, "--text", text, "--system", "되찾기"], capture_output=True, timeout=30, creationflags=NOWIN)
        except Exception:  # noqa: BLE001
            pass


def reclaim(kill, procs, dry=False):
    done = []
    for pid, rule, why, r in kill:
        fam = family(pid, procs)
        ok = None
        if not dry:
            if rule == "R4":
                notify("닫음: " + why.split("«")[-1].split("»")[0], why + " · 다시 열면 이어짐")
            for q in reversed(fam):
                try:
                    psutil.Process(q).kill()
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(0.5)
            ok = not psutil.pid_exists(pid)
        done.append({"t": dt.datetime.now().isoformat(timespec="seconds"), "pid": pid, "name": r["name"], "rule": rule, "why": why,
                     "n": len(fam), "priv_mb": sum(procs[q]["priv"] for q in fam if q in procs) >> 20, "cmd": r["cmd"][:160], "ok": ok, "dry": dry})
    if done and not dry:
        _mkdirs()
        with open(LOG, "a", encoding="utf-8") as h:
            for d in done:
                h.write(json.dumps(d, ensure_ascii=False) + "\n")
    return done


def tick(dry=False):
    _mkdirs()
    sess = sessions()
    procs = table(sess)
    sf = STATE + ".dry" if dry else STATE       # 미리 보기는 따로 적는다 — doctor 가 «되찾기 돎»으로 읽지 않게(기준선 재기 11-19)
    try:
        with open(sf, encoding="utf-8") as h:
            prev = json.load(h)
    except (OSError, ValueError):
        prev = {}
    now = _now()
    kill, rows, info = judge(procs, sess, prev, now)
    done = reclaim(kill, procs, dry)
    held = info.get("held") or []
    st = {"t": now, "cpu": {str(p): [r["cpu"], r["start"]] for p, r in procs.items() if r["cpu"] is not None},
          "summary": {"at": dt.datetime.now().isoformat(timespec="seconds"), "avail_gb": round(info.get("avail", 0), 2),
                      "commit_gb": round(info.get("commit", 0), 1), "press": info["press"], "killed": len([d for d in done if d["ok"]]),
                      "killed_mb": sum(d["priv_mb"] for d in done if d["ok"]), "owned": len(rows), "dry": dry,
                      "orphans": sum(1 for r in rows if r["kind"] and not r["owner"]),   # 주인 없는 시험 프로세스(하루 실측 «주인 없는 것 0»)
                      "on": info.get("on"), "held": len(held)}}
    tmp = sf + ".tmp"
    with open(tmp, "w", encoding="utf-8") as h:
        json.dump(st, h)
    os.replace(tmp, sf)
    if True:                                    # tick 마다 한 줄(하루 실측 = 남은 램·주인 붙은 수·끈 것 · 미리 보기는 dry.jsonl)
        with open(os.path.join(DIR, "dry.jsonl" if dry else "ticks.jsonl"), "a", encoding="utf-8") as h:
            h.write(json.dumps({**st["summary"], "would": [{k: d[k] for k in ("pid", "name", "rule", "why", "priv_mb", "ok")} for d in done],
                                "commit_gb": round(info.get("commit", 0), 1)}, ensure_ascii=False) + "\n")
    return done, rows, info, st["summary"]


# ── 감싸개 ────────────────────────────────────────────────────────────────
def _job():
    """KILL_ON_JOB_CLOSE Job 손잡이 · 못 만들면 None"""
    import ctypes
    import ctypes.wintypes as w

    class BASIC(ctypes.Structure):
        _fields_ = [("a", ctypes.c_int64), ("b", ctypes.c_int64), ("LimitFlags", w.DWORD), ("c", ctypes.c_size_t), ("d", ctypes.c_size_t),
                    ("e", w.DWORD), ("f", ctypes.c_size_t), ("g", w.DWORD), ("h", w.DWORD)]

    class IO(ctypes.Structure):
        _fields_ = [(n, ctypes.c_uint64) for n in "abcdef"]

    class EXT(ctypes.Structure):
        _fields_ = [("basic", BASIC), ("io", IO), ("p", ctypes.c_size_t), ("q", ctypes.c_size_t), ("r", ctypes.c_size_t), ("s", ctypes.c_size_t)]
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateJobObjectW.restype = w.HANDLE
    k.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    k.OpenProcess.restype = w.HANDLE
    k.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    job = k.CreateJobObjectW(None, None)
    info = EXT()
    info.basic.LimitFlags = 0x2000
    if not job or not k.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):
        return None, k
    return job, k


def _ttl(s):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)([smhd]?)", s or "")
    if not m:
        raise SystemExit("--ttl 꼴: 90m · 3h · 1d")
    return float(m.group(1)) * {"s": 1, "m": 60, "h": 3600, "d": 86400, "": 60}[m.group(2)]


def run(kind, ttl, keep, argv):
    """Job 안에서 띄우고 장부에 적는다 · 주인이 끝나거나 수명이 넘으면 Job 을 닫아 자식째 끝낸다 · 자식 종료 코드를 돌려준다"""
    _mkdirs()
    sess = sessions()
    procs = table(sess)
    me = os.getpid()
    o = owner_of(me, procs, sess) if procs else None
    job, k = _job()
    p = subprocess.Popen(argv)
    if job:
        h = k.OpenProcess(0x1F0FFF, False, p.pid)
        if h:
            k.AssignProcessToJobObject(job, h)
            k.CloseHandle(h)
    try:
        start = psutil.Process(p.pid).create_time() if psutil else _now()
    except Exception:  # noqa: BLE001
        start = _now()
    e = {"pid": p.pid, "start": start, "kind": kind, "ttl": ttl, "keep": keep, "owner": o, "owner_sid": (sess.get(o) or {}).get("sid", ""),
         "owner_name": (sess.get(o) or {}).get("name", ""), "cmd": " ".join(argv)[:300], "wrapper": me,
         "at": dt.datetime.now().isoformat(timespec="seconds")}
    f = os.path.join(LEDGER, "%d-%d.json" % (p.pid, int(start)))
    with open(f, "w", encoding="utf-8") as h:
        json.dump(e, h, ensure_ascii=False)
    why = None
    try:
        while p.poll() is None:
            time.sleep(2)
            if o and not (psutil and psutil.pid_exists(o)):
                why = "주인 끝남"
            elif ttl and _now() - start > ttl:
                why = "수명 넘음"
            if why:
                break
    except KeyboardInterrupt:
        why = "멈춤"
    finally:
        if why or p.poll() is None:
            if job:
                k.TerminateJobObject(job, 1)
            else:
                p.kill()
            with open(LOG, "a", encoding="utf-8") as h:
                h.write(json.dumps({"t": dt.datetime.now().isoformat(timespec="seconds"), "pid": p.pid, "rule": "run", "why": why or "감싸개 끝",
                                    "kind": kind, "cmd": e["cmd"][:160], "ok": True}, ensure_ascii=False) + "\n")
        if job:
            k.CloseHandle(job)
        try:
            os.remove(f)
        except OSError:
            pass
    return p.returncode if p.returncode is not None else 1


def end(short):
    """그 세션의 장부 항목 + 그 세션 아래 시험 종류(에뮬레이터·격리 옵시디언·머리 없는 크롬)를 끝냄(SessionEnd 훅).
    short = 세션 id 앞 8자 · "--self" = 이 프로세스의 조상 Claude 세션(훅이 부를 때). 그 밖의 배경 작업은 tick 이 맡음
    (훅이 띄운 재색인 같은 것을 같이 끄지 않게)."""
    sess = sessions()
    procs = table(sess)
    if short == "--self":
        o = owner_of(os.getpid(), procs, sess)
        if not o:
            return []
        short = sess[o]["short"]
    mine = {p for p, s in sess.items() if s["short"] == short}
    kill = [(pid, "end", "세션 끝(%s)" % short, procs[pid]) for pid, e in ledger().items()
            if ((e.get("owner_sid") or "")[:8] == short or e.get("owner") in mine) and pid in procs]
    kill += [(pid, "end", "세션 끝(%s) · %s" % (short, kind_of(r)), r) for pid, r in procs.items()
             if kind_of(r) and owner_of(pid, procs, sess) in mine and pid not in {k[0] for k in kill}]
    top = {p for p, *_ in kill}
    kill = [x for x in kill if not any(x[0] in family(q, procs) and q != x[0] for q in top)]
    return reclaim(kill, procs)


# ── 예약 작업 ─────────────────────────────────────────────────────────────
def _schtasks(*args):
    try:
        r = subprocess.run(["schtasks", *args], capture_output=True, creationflags=NOWIN, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    for enc in ("utf-8", "cp949", "utf-16"):
        try:
            return r.returncode, (r.stdout + r.stderr).decode(enc)
        except UnicodeDecodeError:
            continue
    return r.returncode, ""


def task_xml():
    import shutil
    from xml.sax.saxutils import escape
    start = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(_now() + 120))
    pyw = shutil.which("pyw") or r"C:\Windows\pyw.exe"
    args = f'-3 "{os.path.abspath(__file__)}" tick'
    return ('<?xml version="1.0" encoding="UTF-16"?>\n<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">'
            f'<RegistrationInfo><Description>{escape("외부뇌 되찾기: 주인이 끝났거나 수명이 넘은 볼트 시험·배경 프로세스를 끈다 · 3_시스템/own.py")}</Description></RegistrationInfo>'
            f'<Triggers><TimeTrigger><Repetition><Interval>PT10M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>'
            f'<StartBoundary>{start}</StartBoundary><Enabled>true</Enabled></TimeTrigger></Triggers>'
            '<Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>'
            '<Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>'
            '<StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><StartWhenAvailable>true</StartWhenAvailable>'
            '<ExecutionTimeLimit>PT5M</ExecutionTimeLimit><Priority>7</Priority>'
            '<IdleSettings><StopOnIdleEnd>false</StopOnIdleEnd><RestartOnIdle>false</RestartOnIdle></IdleSettings></Settings>'
            f'<Actions Context="Author"><Exec><Command>{escape(pyw)}</Command><Arguments>{escape(args)}</Arguments><WorkingDirectory>{escape(VAULT)}</WorkingDirectory></Exec></Actions></Task>')


def install():
    import tempfile
    fd, tmp = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    try:
        with open(tmp, "w", encoding="utf-16") as f:
            f.write(task_xml())
        rc, out = _schtasks("/Create", "/TN", TASK, "/XML", tmp, "/F")
    finally:
        os.remove(tmp)
    print(f"{TASK}: " + ("10분마다" if rc == 0 else "못 등록 " + out.strip()[-200:]))
    return rc


# ── 보이기 ────────────────────────────────────────────────────────────────
def doctor_row():
    """(상태, 줄) — 건강 창 «되찾기» 줄: 마지막 tick · 끈 것 · 예약 작업 유무"""
    try:
        with open(STATE, encoding="utf-8") as h:
            s = json.load(h)["summary"]
    except (OSError, ValueError, KeyError):
        return "warn", "되찾기 안 돎 — 예약 작업 «%s» 없음(`py -3 3_시스템/own.py install` · 사람 허락)" % TASK
    age = (_now() - dt.datetime.fromisoformat(s["at"]).timestamp()) / 60
    n = 0
    try:
        cut = _now() - 86400
        with open(LOG, encoding="utf-8") as h:
            n = sum(1 for ln in h if ln.strip() and dt.datetime.fromisoformat(json.loads(ln)["t"]).timestamp() > cut)
    except (OSError, ValueError):
        pass
    if age > 30:
        return "warn", "되찾기 %d분째 안 돎(예약 작업 확인 · own.py status)" % age
    return "ok", "되찾기 %d분 전 · 남은 램 %.1fGB%s · 하루 동안 끔 %d" % (age, s["avail_gb"], " · 압박" if s["press"] else "", n)


IDLE_SESSION_H = 24


def kill_tests(procs=None, check_lock=True):
    """남은 시험 프로세스를 자식째 끈다 — 사람이 건강 «고치기»로 고를 때만(drift.py --kill-test 가 부름) · 시험 잠금이 있으면 안 끔(None).
    사람이 고른 것이라 주인·쉼은 보지 않는다. 에뮬레이터는 AVD 이름과 상관없이 · adb 서버도."""
    if check_lock and heavy_locked():
        return None
    procs = table(sessions()) if procs is None else procs
    kill = []
    for pid, r in procs.items():
        n = r["name"].lower()
        if not r["cmd"] and (n == "adb.exe" or re.match(r"^(emulator|qemu-system-[\w.-]+)\.exe$", n)):
            try:
                r["cmd"] = " ".join(psutil.Process(pid).cmdline())
            except Exception:  # noqa: BLE001
                pass
        k = "에뮬레이터" if re.match(r"^(emulator|qemu-system-[\w.-]+)\.exe$", n) else "adb" if n == "adb.exe" else kind_of(r)
        if k:
            kill.append((pid, "고치기", k, r))
    top = {p for p, *_ in kill}
    kill = [x for x in kill if not any(x[0] in family(q, procs) and q != x[0] for q in top)]
    return reclaim(kill, procs)


def doctor_rows():
    """[(이름, 상태, 줄)] — drift.mem_rows 가 건강 창에 붙인다. 문제일 때만(되찾기가 돌면 늘 한 줄)."""
    rows = []
    if not any(C()["on"].values()):
        return rows
    sess = sessions()
    procs = table(sess)
    if os.path.exists(STATE):
        rows.append(("되찾기",) + doctor_row())
    else:
        kill, _r, _i = judge(procs, sess)
        if kill:
            mb = sum(sum(procs[q]["priv"] for q in family(p, procs) if q in procs) for p, *_ in kill) >> 20
            rows.append(("되찾기", "warn", "주인이 끝났거나 쉬는데 남은 프로세스 %d개(%dMB) — 되찾기 예약 작업 없음 · 미리 보기 `py -3 3_시스템/own.py tick --dry`" % (len(kill), mb)))
    now = _now()
    idle = [(p, s) for p, s in sess.items() if s["alive"] and not s["busy"] and now - s["last"] > IDLE_SESSION_H * 3600]
    if idle:
        gb = sum(sum(procs[q]["priv"] for q in family(p, procs) if q in procs) for p, _s in idle) / 2 ** 30
        rows.append(("쉬는 세션", "warn", "하루 넘게 쉬는 Claude 세션 %d개(%.1fGB · %s) — %s" % (
            len(idle), gb, " · ".join("«%s» %d시간" % (s["name"][:16], (now - s["last"]) / 3600) for _p, s in idle[:3]),
            "%d시간 넘으면 되찾기가 닫음" % C()["session_close_hours"] if C()["on"]["R4"] else "닫을지는 사용자(기능 단계 «쉬는 세션 닫기» 끔)")))
    return rows


def fmt_rows(rows):
    out = []
    for r in sorted(rows, key=lambda x: (x["owner"], -x["priv_mb"])):
        out.append("%-7s %6d %-28s %-12s 주인=%-24s 쉼=%s 코어=%s 사유=%5dMB 나이=%5.1fh %s" % (
            r["rule"] or "-", r["pid"], r["name"][:28], r["kind"][:12], r["owner"] or "(없음)",
            "%.1fh" % r["idle_h"] if r["idle_h"] is not None else "-", "%.2f" % r["core"] if r["core"] is not None else "-",
            r["priv_mb"], r["age_h"], r["why"]))
    return out


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["run"]:
        if "--" not in argv:
            raise SystemExit("own.py run --kind <종류> [--ttl 3h] [--keep] -- <명령…>")
        i = argv.index("--")
        ap = argparse.ArgumentParser(prog="own.py run")
        ap.add_argument("--kind", default="배경")
        ap.add_argument("--ttl", default=None)
        ap.add_argument("--keep", action="store_true", help="주인이 살아 있는 동안은 수명이 넘어도 둠")
        a = ap.parse_args(argv[1:i])
        return run(a.kind, _ttl(a.ttl) if a.ttl else None, a.keep, argv[i + 1:])
    ap = argparse.ArgumentParser(prog="own.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("tick")
    p.add_argument("--dry", action="store_true")
    p = sub.add_parser("end")
    p.add_argument("short", nargs="?", default="--self", help="세션 id 앞 8자 · 비우면 이 프로세스의 조상 세션(훅)")
    sub.add_parser("kill-tests")
    p = sub.add_parser("local", help="이 PC 값 own.local.json 보기·더하기")
    p.add_argument("--avd", nargs="*", default=[], help="시험 AVD 이름(에뮬레이터를 시험 종류로 셈)")
    p.add_argument("--lock", nargs="*", default=[], help="시험 잠금 glob(볼트 상대)")
    p.add_argument("--clear", action="store_true", help="비우고 시작")
    sub.add_parser("installed")
    sub.add_parser("install")
    sub.add_parser("remove")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if not psutil and a.cmd in ("list", "tick", "end", "kill-tests"):
        print("psutil 없음 — 되찾기 안 함")
        return 0
    if a.cmd == "list":
        try:
            with open(STATE, encoding="utf-8") as h:
                prev = json.load(h)
        except (OSError, ValueError):
            prev = {}
        kill, rows, info = judge(prev=prev)
        if a.json:
            print(json.dumps({"info": info, "rows": rows}, ensure_ascii=False, default=str))
            return 0
        print("남은 램 %.1fGB · 커밋 %.1f/%.1fGB%s · 살아 있는 세션 %d · 주인 붙은/시험 프로세스 %d · 끌 것 %d" % (
            info.get("avail", 0), info.get("commit", 0), info.get("ram", 0), " · 압박" if info["press"] else "", info["sessions"], len(rows), len(kill)))
        print("\n".join(fmt_rows(rows)))
        return 0
    if a.cmd == "tick":
        done, rows, info, s = tick(a.dry)
        for d in done:
            print("%s %s %d %s · %s · 가족 %d · %dMB%s" % ("미리 보기" if d["dry"] else ("끔" if d["ok"] else "못 끔"), d["rule"], d["pid"], d["name"], d["why"],
                                                       d["n"], d["priv_mb"], "" if d["dry"] else ""))
        print("tick: 남은 램 %.1fGB%s · 끔 %d(%dMB)" % (s["avail_gb"], " · 압박" if s["press"] else "", s["killed"], s["killed_mb"]))
        return 0
    if a.cmd == "end":
        for d in end(a.short):
            print("끔" if d["ok"] else "못 끔", d["pid"], d["name"], d["why"])
        return 0
    if a.cmd == "local":
        d = {"test_avds": [], "locks": []}
        if not a.clear:
            try:
                with open(LOCAL, encoding="utf-8") as h:
                    d.update({k: v for k, v in json.load(h).items() if k in d and isinstance(v, list)})
            except (OSError, ValueError, AttributeError):
                pass
        if a.avd or a.lock or a.clear:
            d["test_avds"] = list(dict.fromkeys(d["test_avds"] + a.avd))
            d["locks"] = list(dict.fromkeys(d["locks"] + a.lock))
            tmp = LOCAL + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="\n") as h:
                json.dump(d, h, ensure_ascii=False, indent=2)
                h.write("\n")
            os.replace(tmp, LOCAL)
        print("%s: 시험 AVD %s · 잠금 %s" % (os.path.relpath(LOCAL, VAULT).replace(os.sep, "/"), d["test_avds"] or "없음", d["locks"] or "기본만"))
        return 0
    if a.cmd == "kill-tests":
        done = kill_tests()
        if done is None:
            print("시험 잠금이 있어 안 끔")
        for d in done or []:
            print("끔" if d["ok"] else "못 끔", d["pid"], d["name"], d["why"])
        return 0
    if a.cmd == "installed":                # 바깥 설정 확인(external.json) — 0 = 됨 · 1 = 안 됨
        rc, _ = _schtasks("/Query", "/TN", TASK)
        print("됨" if rc == 0 else "안 됨")
        return 0 if rc == 0 else 1
    if a.cmd == "install":
        return install()
    if a.cmd == "remove":
        rc, out = _schtasks("/Delete", "/TN", TASK, "/F")
        print(f"{TASK}: " + ("지움" if rc == 0 else "못 지움 " + out.strip()[-200:]))
        return rc
    if a.cmd == "status":
        rc, _ = _schtasks("/Query", "/TN", TASK)
        st, line = doctor_row()
        print(f"{TASK}: " + ("있음" if rc == 0 else "없음") + " · " + line)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
