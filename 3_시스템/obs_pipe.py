#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""옵시디언 링크 파이프 주인 — 누가 `\\.\pipe\obsidian-cli-<OS 사용자>` 를 쥐었나(창 없이 · 읽기만).

왜(사고 incident-2026-11-23-볼트링크-시험옵시디언이-cli파이프-쥠): 옵시디언 1.15 는 이미 떠 있을 때 들어온 obsidian:// 링크(크롬·Claude 앱 링크)를
OS 사용자당 하나뿐인 이 파이프로 넘긴다. 프로필과 상관없이 먼저 뜬 옵시디언 하나만 쥐고 못 쥔 쪽은 다시 시도하지 않는다 —
격리 시험 옵시디언(--user-data-dir)이 사용자 옵시디언보다 먼저 떠 있으면 링크가 시험 창으로 가서 사용자 창엔 아무것도 안 뜬다.

  py -3 3_시스템/obs_pipe.py            한 줄(주인 · 사용자 옵시디언인가)
  py -3 3_시스템/obs_pipe.py --json     {pipe, state: owner|none|busy, pid, user, cmd}
  py -3 3_시스템/obs_pipe.py --holders  + 파이프 핸들을 쥔 Obsidian.exe 전부(핸들 훑기 · 몇 초)

state: owner = 주인 pid 를 잼 · none = 듣는 주인 없음(사용자 옵시디언 꺼짐 · 또는 주인이 멈춤) · busy = 주인이 있으나 지금 다 바쁨.
user = 주인 명령 줄에 --user-data-dir 이 없음(= 사용자가 켠 옵시디언 · 시험 틀은 늘 --user-data-dir 로 띄움).
잇기만 하고 쓰지 않는다 — 옵시디언은 5초 뒤 «머리 없음»으로 그 연결을 버린다(링크·명령으로 처리되지 않음).
"""
import ctypes
import getpass
import json
import os
import sys
from ctypes import wintypes as w

PIPE = os.environ.get('BRAIN_OBS_PIPE') or r'\\.\pipe\obsidian-cli-' + getpass.getuser()   # BRAIN_OBS_PIPE = 시험용 다른 이름
k = ctypes.WinDLL('kernel32', use_last_error=True)
nt = ctypes.WinDLL('ntdll')
k.CreateFileW.restype = w.HANDLE
k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
k.OpenProcess.restype = w.HANDLE
k.CloseHandle.argtypes = [w.HANDLE]
k.GetNamedPipeServerProcessId.argtypes = [w.HANDLE, ctypes.POINTER(w.ULONG)]
INVALID = w.HANDLE(-1).value


def cmdline(pid):
    """프로세스 명령 줄(NtQueryInformationProcess 60 · 윈도 8.1+) — 못 읽으면 ''."""
    h = k.OpenProcess(0x1000, False, pid)            # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ''
    try:
        size = 4096
        while size <= 1 << 20:
            buf = ctypes.create_string_buffer(size)
            ret = w.ULONG()
            st = nt.NtQueryInformationProcess(w.HANDLE(h), 60, buf, size, ctypes.byref(ret)) & 0xFFFFFFFF
            if st == 0:
                ln = ctypes.c_ushort.from_buffer(buf, 0).value
                ptr = ctypes.c_void_p.from_buffer(buf, ctypes.sizeof(ctypes.c_void_p)).value
                return ctypes.wstring_at(ptr, ln // 2) if ptr else ''
            if st not in (0xC0000004, 0x80000005, 0xC0000023):   # 길이 모자람이 아니면 그만
                return ''
            size *= 4
        return ''
    finally:
        k.CloseHandle(h)


def owner():
    h = k.CreateFileW(PIPE, 0x80000000 | 0x40000000, 0, None, 3, 0, None)   # GENERIC_READ|WRITE · OPEN_EXISTING
    if h in (None, INVALID):
        e = ctypes.get_last_error()
        return {'pipe': PIPE, 'state': 'busy' if e == 231 else 'none', 'pid': None, 'user': None, 'cmd': '', 'err': e}
    try:
        pid = w.ULONG()
        k.GetNamedPipeServerProcessId(h, ctypes.byref(pid))
    finally:
        k.CloseHandle(h)
    c = cmdline(pid.value)
    return {'pipe': PIPE, 'state': 'owner', 'pid': pid.value, 'user': bool(c) and '--user-data-dir' not in c, 'cmd': c[:300]}


def holders():
    """파이프 핸들을 쥔 Obsidian.exe(pid 목록) — 주인이 멈춰 none 으로 보일 때 누가 쥐었나."""
    import threading

    class E(ctypes.Structure):
        _fields_ = [('Object', ctypes.c_void_p), ('UniqueProcessId', ctypes.c_size_t), ('HandleValue', ctypes.c_size_t),
                    ('GrantedAccess', w.ULONG), ('CreatorBackTraceIndex', w.USHORT), ('ObjectTypeIndex', w.USHORT),
                    ('HandleAttributes', w.ULONG), ('Reserved', w.ULONG)]
    k.DuplicateHandle.argtypes = [w.HANDLE, w.HANDLE, w.HANDLE, ctypes.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD]
    k.GetFileType.argtypes = [w.HANDLE]
    k.GetCurrentProcess.restype = w.HANDLE
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    nt.NtQueryObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.ULONG, ctypes.POINTER(w.ULONG)]
    size = 1 << 24
    while True:
        buf = ctypes.create_string_buffer(size)
        if nt.NtQuerySystemInformation(64, buf, size, ctypes.byref(w.ULONG())) == 0:
            break
        size *= 2
    n = ctypes.c_size_t.from_buffer(buf, 0).value
    arr = ctypes.cast(ctypes.addressof(buf) + 2 * ctypes.sizeof(ctypes.c_size_t), ctypes.POINTER(E))
    me = k.GetCurrentProcess()
    exe, procs, out = {}, {}, {}

    def is_obs(pid):
        if pid not in exe:
            exe[pid] = False
            h = k.OpenProcess(0x1000, False, pid)
            if h:
                b = ctypes.create_unicode_buffer(520)
                ln = w.DWORD(520)
                if k.QueryFullProcessImageNameW(h, 0, b, ctypes.byref(ln)):
                    exe[pid] = b.value.lower().endswith('\\obsidian.exe')
                k.CloseHandle(h)
        return exe[pid]

    def name_of(h):
        res = {}

        def run():
            b = ctypes.create_string_buffer(2048)
            if nt.NtQueryObject(h, 1, b, 2048, ctypes.byref(w.ULONG())) == 0:
                ln = ctypes.c_ushort.from_buffer(b, 0).value
                ptr = ctypes.c_void_p.from_buffer(b, ctypes.sizeof(ctypes.c_void_p)).value
                if ptr:
                    res['n'] = ctypes.wstring_at(ptr, ln // 2)
        t = threading.Thread(target=run, daemon=True)
        t.start()
        t.join(0.2)                                  # 동기 파이프는 이름 묻기가 멈출 수 있다
        return res.get('n')

    tail = PIPE.rsplit('\\', 1)[-1]
    for i in range(n):
        e = arr[i]
        pid = e.UniqueProcessId
        if not is_obs(pid):
            continue
        if pid not in procs:
            procs[pid] = k.OpenProcess(0x0040, False, pid)    # PROCESS_DUP_HANDLE
        if not procs[pid]:
            continue
        d = w.HANDLE()
        if not k.DuplicateHandle(procs[pid], w.HANDLE(e.HandleValue), me, ctypes.byref(d), 0, False, 2):
            continue
        if k.GetFileType(d) == 3 and (name_of(d) or '').endswith(tail):
            out[pid] = out.get(pid, 0) + 1
        k.CloseHandle(d)
    for h in procs.values():
        if h:
            k.CloseHandle(h)
    return [{'pid': p, 'handles': c, 'cmd': cmdline(p)[:300]} for p, c in sorted(out.items())]


def main():
    r = owner()
    if '--holders' in sys.argv:
        r['holders'] = holders()
    if '--json' in sys.argv:
        print(json.dumps(r, ensure_ascii=False))
        return
    if r['state'] == 'owner':
        print(f"링크 파이프 주인 = pid {r['pid']} · {'사용자 옵시디언' if r['user'] else '격리(시험) 옵시디언 — 링크가 사용자 창에 안 감'} · {r['cmd'][:160]}")
    else:
        print(f"링크 파이프 주인 {'바쁨(있음)' if r['state'] == 'busy' else '없음(사용자 옵시디언 꺼짐 · 또는 주인이 멈춤)'} · 오류 {r['err']}")
    for x in r.get('holders', []):
        print(f"  핸들 쥠 pid {x['pid']} ×{x['handles']} · {x['cmd'][:160]}")


if __name__ == '__main__':
    sys.exit(main())
