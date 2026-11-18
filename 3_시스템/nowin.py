#!/usr/bin/env python3
"""콘솔 없는 프로세스(pythonw · 작업 스케줄러 · 폰 서버)가 띄우는 자식이 보이는 창을 만들지 않게 한다.

  import nowin; nowin.install()   # 진입점 main() 첫머리 · 콘솔이 있으면 아무것도 안 한다
  nowin.FLAGS                     # 개별 호출에 직접 줄 값(CREATE_NO_WINDOW)

왜(11-17): 콘솔 없는 부모가 플래그 없이 콘솔 프로그램(git·py·powershell)을 띄우면 Windows 가 새 콘솔을 만들고,
기본 터미널이 Windows Terminal 이면 그것이 보이는 창으로 떠 전경을 가져간다(폰 서버 /v1/home → git 9번 → 창 9개).
콘솔이 있는 부모의 자식은 그 콘솔(Claude 훅·셸이면 숨은 콘솔)을 물려받아 창이 안 생기므로 손대지 않는다.

install() 이 하는 일(콘솔 없는 프로세스에서만):
- subprocess.Popen(run·call·check_output 도 이것을 쓴다)의 creationflags 기본값에 CREATE_NO_WINDOW 를 더한다.
  CREATE_NEW_CONSOLE·DETACHED_PROCESS·CREATE_NO_WINDOW 를 직접 준 호출은 그대로 둔다(일부러 콘솔을 띄우는 길).
- 자식 프로그램이 자기 자신(pythonw.exe)이면 같은 자리 python.exe 로 바꾼다 — pythonw 자식은 다시 콘솔이 없어
  그 아래 손자가 또 창을 만든다. python.exe + CREATE_NO_WINDOW 는 숨은 콘솔을 하나 갖고 손자 전체가 그것을 물려받는다.
GUI 프로그램(크롬·옵시디언)에는 CREATE_NO_WINDOW 가 무시된다.
"""
import os
import subprocess
import sys

FLAGS = 0x08000000 if os.name == "nt" else 0            # CREATE_NO_WINDOW
_KEEP = 0x00000010 | 0x00000008 | 0x08000000            # CREATE_NEW_CONSOLE | DETACHED_PROCESS | CREATE_NO_WINDOW
_FLAGS_POS = 13                                          # Popen(args, bufsize, executable, …, startupinfo, creationflags, …)


def has_console():
    if os.name != "nt":
        return True
    import ctypes
    buf = (ctypes.c_uint32 * 1)()
    return ctypes.windll.kernel32.GetConsoleProcessList(buf, 1) != 0


def _console_twin():
    """pythonw.exe 로 돌면 옆의 python.exe · 아니면 None."""
    exe = sys.executable or ""
    if os.path.basename(exe).lower() != "pythonw.exe":
        return None
    twin = os.path.join(os.path.dirname(exe), "python.exe")
    return twin if os.path.isfile(twin) else None


def install():
    """콘솔 없는 프로세스면 subprocess 기본값을 창 없이로 · 바꿨으면 True."""
    if os.name != "nt" or getattr(subprocess.Popen, "_nowin", False) or has_console():
        return False
    base, twin = subprocess.Popen, _console_twin()
    me = os.path.normcase(sys.executable or "")

    class Popen(base):
        _nowin = True

        def __init__(self, args, *a, **k):
            if len(a) < _FLAGS_POS:                       # creationflags 를 자리 인자로 준 호출은 없다고 보고 키워드만 본다
                fl = k.get("creationflags", 0) or 0
                if not fl & _KEEP:
                    k["creationflags"] = fl | FLAGS
            if twin and isinstance(args, (list, tuple)) and args and os.path.normcase(str(args[0])) == me:
                args = [twin, *args[1:]]
            super().__init__(args, *a, **k)

    subprocess.Popen = Popen
    return True
