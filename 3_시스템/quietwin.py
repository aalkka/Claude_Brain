#!/usr/bin/env python3
"""창이 필요한 프로그램을 사용자 화면 밖 Windows 데스크톱에서 돌린다(ADR-044).

  py -3 quietwin.py run [--parent PID] -- <프로그램> [인자…]

별도 데스크톱(CreateDesktop)의 창은 입력 데스크톱의 전경을 가져갈 수 없고 작업 표시줄·Alt+Tab 에도 안 나온다.
자식은 데스크톱을 물려받으므로 node → 크롬처럼 손자까지 같은 자리에서 돈다.
이 대본이 죽으면 자식 전체가 같이 끝난다(작업 개체 · spawn 쪽 proc.kill() 이 그대로 통한다).
--parent = 그 프로세스가 죽으면 같이 끝낸다. 시험이 죽어도 안 보이는 창이 프로필을 쥔 채 남지 않게 한다.
노드 시험은 quietwin.mjs 의 spawnQuiet 를 쓴다.
"""
import ctypes
import ctypes.wintypes as w
import subprocess
import sys

DESKTOP = "brain-quiet"
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)
GENERIC_ALL = 0x10000000
CREATE_SUSPENDED, CREATE_UNICODE_ENVIRONMENT = 0x4, 0x400
STARTF_USESTDHANDLES = 0x100
STD_HANDLES = (-10, -11, -12)
INFINITE, SYNCHRONIZE = 0xFFFFFFFF, 0x00100000
JobObjectExtendedLimitInformation, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 9, 0x2000


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR), ("lpTitle", w.LPWSTR),
                ("dwX", w.DWORD), ("dwY", w.DWORD), ("dwXSize", w.DWORD), ("dwYSize", w.DWORD),
                ("dwXCountChars", w.DWORD), ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD), ("dwFlags", w.DWORD),
                ("wShowWindow", w.WORD), ("cbReserved2", w.WORD), ("lpReserved2", ctypes.c_void_p),
                ("hStdInput", w.HANDLE), ("hStdOutput", w.HANDLE), ("hStdError", w.HANDLE)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", w.HANDLE), ("hThread", w.HANDLE), ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ("r", "wr", "o", "rb", "wb", "ob")]


class BASIC_LIMIT(ctypes.Structure):
    _fields_ = [("a", ctypes.c_longlong), ("b", ctypes.c_longlong), ("LimitFlags", w.DWORD), ("c", ctypes.c_size_t), ("d", ctypes.c_size_t),
                ("e", w.DWORD), ("f", ctypes.c_size_t), ("g", w.DWORD), ("h", w.DWORD)]


class EXT_LIMIT(ctypes.Structure):
    _fields_ = [("basic", BASIC_LIMIT), ("io", IO_COUNTERS), ("p", ctypes.c_size_t), ("q", ctypes.c_size_t), ("r", ctypes.c_size_t), ("s", ctypes.c_size_t)]


u32.CreateDesktopW.restype = w.HANDLE
u32.CreateDesktopW.argtypes = [w.LPCWSTR, w.LPCWSTR, ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.c_void_p]
k32.CreateJobObjectW.restype = w.HANDLE
k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
k32.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
k32.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
k32.ResumeThread.argtypes = [w.HANDLE]
k32.WaitForMultipleObjects.argtypes = [w.DWORD, ctypes.POINTER(w.HANDLE), w.BOOL, w.DWORD]
k32.OpenProcess.restype = w.HANDLE
k32.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k32.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
k32.GetStdHandle.restype = w.HANDLE
k32.CreateProcessW.argtypes = [w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p, w.BOOL, w.DWORD, ctypes.c_void_p, w.LPCWSTR,
                               ctypes.POINTER(STARTUPINFOW), ctypes.POINTER(PROCESS_INFORMATION)]


def run(argv, parent=None):
    desk = u32.CreateDesktopW(DESKTOP, None, None, 0, GENERIC_ALL, None)    # 있으면 그것을 연다
    if not desk:
        raise OSError("CreateDesktop 실패 %d" % ctypes.get_last_error())
    job = k32.CreateJobObjectW(None, None)
    info = EXT_LIMIT()
    info.basic.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not job or not k32.SetInformationJobObject(job, JobObjectExtendedLimitInformation, ctypes.byref(info), ctypes.sizeof(info)):
        raise OSError("작업 개체 실패 %d" % ctypes.get_last_error())
    si = STARTUPINFOW(cb=ctypes.sizeof(STARTUPINFOW), lpDesktop=DESKTOP, dwFlags=STARTF_USESTDHANDLES)
    si.hStdInput, si.hStdOutput, si.hStdError = (k32.GetStdHandle(h) for h in STD_HANDLES)
    pi = PROCESS_INFORMATION()
    line = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
    if not k32.CreateProcessW(None, line, None, None, True, CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT, None, None, ctypes.byref(si), ctypes.byref(pi)):
        raise OSError("실행 실패 %d: %s" % (ctypes.get_last_error(), argv[0]))
    k32.AssignProcessToJobObject(job, pi.hProcess)
    k32.ResumeThread(pi.hThread)
    waits = [pi.hProcess]
    if parent:
        h = k32.OpenProcess(SYNCHRONIZE, False, parent)
        if not h:   # 부모가 이미 죽었다 — 고아를 만들지 않는다
            return 1
        waits.append(h)
    k32.WaitForMultipleObjects(len(waits), (w.HANDLE * len(waits))(*waits), False, INFINITE)
    code = w.DWORD()
    k32.GetExitCodeProcess(pi.hProcess, ctypes.byref(code))
    return code.value


def main():
    a = sys.argv[1:]
    if "--" not in a or a[0] != "run":
        sys.exit(__doc__)
    i = a.index("--")
    head, argv = a[1:i], a[i + 1:]
    if not argv or (head and (len(head) != 2 or head[0] != "--parent")):
        sys.exit(__doc__)
    return run(argv, int(head[1]) if head else None)


if __name__ == "__main__":
    sys.exit(main())
