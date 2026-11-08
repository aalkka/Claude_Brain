#!/usr/bin/env python3
"""전경 창이 바뀌거나 새 창이 뜰 때마다 적는 기록기. 창을 건드리지 않고 토큰도 안 쓴다(ADR-044).

  py -3 winwatch.py watch [--secs N] [--out 파일]   기본 파일 = _index/winwatch/<날짜>.jsonl (git 제외 · 창 제목이 들어 있다)
  py -3 winwatch.py report <파일> [--from HH:MM:SS] [--to HH:MM:SS]

한 줄 = {t, ev: fg|show, pid, exe, cls, title, idle_ms, chain, cmd, above, w, h}
- idle_ms = 사용자의 마지막 입력 뒤 지난 시간. 짧으면 사용자가 바꾼 전경으로 본다.
- above = 새 창이 전경 창 위에서 겹친다(초점을 안 뺏어도 가린다).
"""
import argparse
import ctypes
import ctypes.wintypes as w
import datetime as dt
import json
import os
import re
import sys
import time

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
u32 = ctypes.WinDLL("user32", use_last_error=True)
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_SHOW = 0x0003, 0x8002
WINEVENT_OUTOFCONTEXT, WINEVENT_SKIPOWNPROCESS = 0, 2
OBJID_WINDOW, GA_ROOT, GW_HWNDPREV = 0, 2, 3
GWL_STYLE, WS_CHILD = -16, 0x40000000
USER_INPUT_MS = 1000        # 이보다 짧으면 사용자 입력으로 바뀐 것
MIN_W, MIN_H = 120, 40      # 말풍선·그림자 같은 작은 창은 뺀다
# 볼트 일이 띄운 것으로 보는 표지(명령줄 또는 부모 사슬)
OURS = re.compile(r"obsidian-profile|chrome_pipe|lms_(?:cookie|ext)_check|remote-debugging-p|brain\.py|server\.py|lms-auto|web-collect|winwatch-spike|Claude_Brain\\3_", re.I)

WinEventProc = ctypes.WINFUNCTYPE(None, w.HANDLE, w.DWORD, w.HWND, w.LONG, w.LONG, w.DWORD, w.DWORD)
u32.SetWinEventHook.restype = w.HANDLE
u32.SetWinEventHook.argtypes = [w.DWORD, w.DWORD, w.HMODULE, WinEventProc, w.DWORD, w.DWORD, w.DWORD]
u32.GetAncestor.argtypes, u32.GetAncestor.restype = [w.HWND, w.UINT], w.HWND
u32.GetWindow.argtypes, u32.GetWindow.restype = [w.HWND, w.UINT], w.HWND
u32.GetForegroundWindow.restype = w.HWND
u32.GetWindowLongW.argtypes, u32.GetWindowLongW.restype = [w.HWND, ctypes.c_int], w.LONG


class LASTINPUT(ctypes.Structure):
    _fields_ = [("cbSize", w.UINT), ("dwTime", w.DWORD)]


def idle_ms():
    li = LASTINPUT(ctypes.sizeof(LASTINPUT), 0)
    u32.GetLastInputInfo(ctypes.byref(li))
    return (k32.GetTickCount() - li.dwTime) & 0xFFFFFFFF


def text(fn, hwnd, n=120):
    b = ctypes.create_unicode_buffer(n)
    fn(hwnd, b, n)
    return b.value


def rect(hwnd):
    r = w.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def above_fg(hwnd):
    """hwnd 가 전경 창보다 위에 있고 화면에서 겹치는가."""
    fg = u32.GetForegroundWindow()
    if not fg or fg == hwnd:
        return False
    a, b = rect(hwnd), rect(fg)
    if a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1]:
        return False
    cur, n = u32.GetWindow(fg, GW_HWNDPREV), 0
    while cur and n < 2000:
        if cur == hwnd:
            return True
        cur, n = u32.GetWindow(cur, GW_HWNDPREV), n + 1
    return False


def proc_info(pid):
    exe, chain, cmd = "?", [], ""
    try:
        p = psutil.Process(pid)
        exe = p.name()
        cmd = " ".join(p.cmdline())[:400]
        q, n = p.parent(), 0
        while q and n < 6:
            chain.append(q.name())
            if not cmd or not OURS.search(cmd):
                try:
                    pc = " ".join(q.cmdline())
                    if OURS.search(pc):
                        cmd = (cmd + " <= " + pc)[:400]
                except psutil.Error:
                    pass
            q, n = q.parent(), n + 1
    except psutil.Error:
        pass
    return exe, chain, cmd


def watch(a):
    out = a.out or os.path.join(HERE, "_index", "winwatch", dt.date.today().isoformat() + ".jsonl")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    f = open(out, "a", encoding="utf-8", buffering=1)
    me = os.getpid()
    last_fg = [None]

    def cb(_h, ev, hwnd, obj, child, _th, _t):
        try:
            if not hwnd or obj != OBJID_WINDOW or child != 0:
                return
            if ev == EVENT_OBJECT_SHOW:
                if u32.GetAncestor(hwnd, GA_ROOT) != hwnd or u32.GetWindowLongW(hwnd, GWL_STYLE) & WS_CHILD or not u32.IsWindowVisible(hwnd):
                    return
                l, t, r, b = rect(hwnd)
                if r - l < MIN_W or b - t < MIN_H:
                    return
            elif hwnd == last_fg[0]:
                return
            pid = w.DWORD()
            u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == me:
                return
            exe, chain, cmd = proc_info(pid.value)
            l, t, r, b = rect(hwnd)
            rec = dict(t=dt.datetime.now().isoformat(timespec="milliseconds"), ev="fg" if ev == EVENT_SYSTEM_FOREGROUND else "show",
                       pid=pid.value, exe=exe, cls=text(u32.GetClassNameW, hwnd, 64), title=text(u32.GetWindowTextW, hwnd)[:80],
                       idle_ms=idle_ms(), chain=chain, cmd=cmd, w=r - l, h=b - t, x=l, y=t)
            if ev == EVENT_SYSTEM_FOREGROUND:
                last_fg[0] = hwnd
            else:
                rec["above"] = above_fg(hwnd)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception as e:
            f.write(json.dumps(dict(t=dt.datetime.now().isoformat(timespec="milliseconds"), ev="err", err=repr(e)), ensure_ascii=False) + "\n")

    proc = WinEventProc(cb)
    hooks = [u32.SetWinEventHook(ev, ev, None, proc, 0, 0, WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS) for ev in (EVENT_SYSTEM_FOREGROUND, EVENT_OBJECT_SHOW)]
    if not all(hooks):
        print("훅 실패", ctypes.get_last_error(), file=sys.stderr)
        return 1
    f.write(json.dumps(dict(t=dt.datetime.now().isoformat(timespec="milliseconds"), ev="start", pid=me), ensure_ascii=False) + "\n")
    print("기록 중:", out, flush=True)
    end = time.time() + a.secs if a.secs else None
    msg = w.MSG()
    # PeekMessage 를 돌려야 훅 콜백이 온다. 잠깐씩 자서 CPU 를 안 쓴다.
    while end is None or time.time() < end:
        while u32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))
        u32.MsgWaitForMultipleObjects(0, None, False, 200, 0x04FF)
    return 0


def report(a):
    rows = []
    for line in open(a.file, encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        hms = r.get("t", "")[11:19]
        if (a.from_ and hms < a.from_) or (a.to and hms > a.to):
            continue
        rows.append(r)
    fg = [r for r in rows if r.get("ev") == "fg"]
    show = [r for r in rows if r.get("ev") == "show"]
    ours = lambda r: bool(OURS.search(r.get("cmd", "") or ""))
    unprompted = [r for r in fg if r.get("idle_ms", 0) >= USER_INPUT_MS]
    print(f"구간 {rows[0]['t'][11:19] if rows else '-'} ~ {rows[-1]['t'][11:19] if rows else '-'} · 전경 변경 {len(fg)} · 그중 입력 없이 {len(unprompted)} · 볼트 표지 {sum(map(ours, fg))} · 새 창 {len(show)} · 위로 뜸 {sum(1 for r in show if r.get('above'))} · 볼트 표지 새 창 {sum(map(ours, show))}")
    seen = {}
    for r in rows:
        if r.get("ev") not in ("fg", "show"):
            continue
        if r["ev"] == "fg" and r.get("idle_ms", 0) < USER_INPUT_MS and not ours(r):
            continue
        if r["ev"] == "show" and not (r.get("above") or ours(r)):
            continue
        k = (r["ev"], r["exe"], r["cls"], ours(r))
        s = seen.setdefault(k, dict(n=0, first=r["t"][11:19], chain=r.get("chain", [])[:3], cmd=(r.get("cmd", "") or "")[:90]))
        s["n"] += 1
    for k, s in sorted(seen.items(), key=lambda kv: -kv[1]["n"]):
        print(f"  {k[0]:4} x{s['n']:<3} {k[1]} [{k[2]}] {'볼트' if k[3] else ''} 처음 {s['first']} 부모 {'<'.join(s['chain'])} {s['cmd']}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="c", required=True)
    p = sp.add_parser("watch")
    p.add_argument("--secs", type=float)
    p.add_argument("--out")
    p = sp.add_parser("report")
    p.add_argument("file")
    p.add_argument("--from", dest="from_")
    p.add_argument("--to")
    a = ap.parse_args()
    return {"watch": watch, "report": report}[a.c](a)


if __name__ == "__main__":
    sys.exit(main())
