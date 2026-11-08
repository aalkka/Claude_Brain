# -*- coding: utf-8 -*-
"""코어 게이트 앞단 — PreToolUse(Edit|Write|Bash|PowerShell) 고침안(11-06 perf-system).

왜: core-gate.ps1 은 호출의 대부분(코어와 무관)을 정규식 몇 개로 바로 통과시키는데, 그 판정에 앞서
PowerShell 5.1 기동만 0.44초가 든다(11-06 실측 · 평소 경로 0.53초 · 14일 게이트 대상 22,659회 ≈ 3.3시간 대기).
이 앞단은 core-gate.ps1 의 «값싼 1차»(2·2.5·3절)를 같은 정규식으로 파이썬에서 먼저 본다.
  · 하나라도 걸리면 → 받은 입력 바이트를 그대로 core-gate.ps1 에 넘기고 그 stdout·stderr·종료 코드를 그대로 돌려준다
    (판정·준수사항·로그는 지금 게이트가 한다 — 판정부를 옮기지 않는다).
  · 아무것도 안 걸리면 → 출력 없이 종료 0(지금 게이트가 «exit 0» 하는 바로 그 경우).
정규식은 PS 판과 같게 옮기고 대소문자를 가리지 않는다(PS -match 기본). 어긋날 여지가 있는 곳은 넓게(넘기는 쪽으로) 잡는다.
어떤 예외든 게이트로 넘긴다(앞단 고장이 게이트를 끄지 않게).

v2(11-06 perf-system-2 · 치명 경우 대조 뒤):
  · OBS·INSTALL 끝의 \\b 를 뺐다 — .NET 과 파이썬의 «글자» 범위가 달라(파이썬은 ²·① 같은 숫자 기호도 글자) PS 는 잡고
    앞단은 놓치는 꼴이 생겼다(`obsidian eval²`). \\b 를 빼면 앞단이 PS 의 넓은 쪽을 늘 덮는다(더 넘길 뿐).
  · PS 판정이 TIMEOUT 초 안에 안 끝나면 막는다(종료 2 + 까닭). 지금 PS 판은 Claude Code 시간 제한에 걸리면 통과다.
  · 파이썬이 없거나 이 파일이 없으면 훅 명령(bash)이 PS 판을 바로 부른다 — 앞단이 게이트를 끄지 않는다(settings diff).

v3(11-06 perf-system-3 · 보스가 본 틈):
  · PS 판정이 0·2 밖의 값(core-gate.ps1 구문 오류 1 · [Environment]::Exit · PS 기동 실패 등)으로 끝나면 그 값을 PS_ERROR(3)로
    바꿔 돌려준다. PS 를 못 띄운 경우도 3. (판정부의 throw·exit 1 은 PS 가 0 으로 끝나 여기 안 온다 — 11-06 잼)
    까닭: v2 는 그 값을 그대로 냈고, 훅 명령(bash)은 0·2 가 아니면 «앞단이 못 떴다»로 읽어 PS 를 한 번 더 불렀다.
    stdin 은 앞단이 이미 다 읽었으니 둘째 PS 는 빈 입력을 받는다 → 입력에 따라 죽은 경우는 종료 0(조용한 통과)으로 바뀌고,
    늘 죽는 경우(구문 오류)는 같은 1 이지만 PS 를 두 번 띄웠다.
    훅 명령은 0·2·3 이면 그대로 끝낸다(settings diff). Claude Code 에게 3 은 1 과 같은 «막지 않는 오류»라 PS 판만 쓸 때와 뜻이 같다.
  · 앞단이 못 뜬 경우(SyntaxError 1 · 파이썬 없음 127 · 런처 103)는 stdin 을 안 읽었으니 bash 가 PS 판을 부르는 지금 그대로다.

v4(11-06 perf-system-4 · 보스): PS_ERROR(3) 를 낼 때 core-gate.log 에 GATE-BROKEN 한 줄을 남긴다.
  · 3 은 «막지 않는 오류» = 판정 없이 통과다. core-gate.ps1 이 판정부가 없을 때 하는 대로(74~82행) 통과하되 조용히는 아니게 —
    줄 꼴도 같다(`날짜 시각 [-] GATE-BROKEN(까닭) 도구 -`). weekly.py 가 세어 최우선으로 보고한다(weekly-review 5절).
  · 로그를 못 써도 끝 코드는 그대로 3(로그 실패가 판정을 바꾸지 않는다).
"""
import os
import re
import sys
# subprocess 는 넘길 때만 들인다 · 훅 명령은 `py -3 -S`(site 생략) — 평소 경로 382ms → 287ms(파이썬 기동 바닥 273ms · 11-06 같은 부하)

# 앞단이 PS 판정을 기다리는 한도. Claude Code 의 훅 시간 제한(이 볼트 기록에 211초를 기다린 Stop 훅이 있어 60초가 아니다)보다
# 짧아야 «시간 초과 = 통과»가 «시간 초과 = 막음»으로 바뀐다. 평소 PS 판정 0.5~1초.
TIMEOUT = 150
# PS 판정이 0(판정 그대로)·2(막음) 밖으로 끝났을 때 앞단이 내는 값. 훅 명령(bash)은 이 값이면 PS 를 다시 부르지 않는다.
# 파이썬·py 런처가 스스로 내는 값(1 · 2 · 101~110 · 127)과 겹치지 않는다.
PS_ERROR = 3

I = re.I
TOOL = re.compile(r'"tool_name"\s*:\s*"([^"]+)"', I)
FILEP = re.compile(r'"file_path"\s*:\s*"((?:[^"\\]|\\.)*)"', I)
CMD = re.compile(r'"command"\s*:\s*"((?:[^"\\]|\\.)*)"', I)
QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
VERB = re.compile(r"(^|[\s;&|({])(rm|mv|rmdir|unlink|del|Remove-Item|Move-Item|Rename-Item)(?=\s)", I)
PYDEL = re.compile(r"os\.(remove|unlink|rename|rmdir)\(|shutil\.(rmtree|move)\(|IO\.(File|Directory)\]::(Delete|Move)\(", I)
PLACE = re.compile(r"(0_작업|1_수집|2_지식|\.trash|3_시스템/(?!_index/|__pycache__))", I)
OBS = re.compile(r"(^|[\s;&|(/\"'])obsidian(\.com|\.exe)?[\"']?\s+(eval|move|rename|delete)", I)
APPLY = re.compile(r"fileops\.py[^;&|]*\s(update|migrate)\s[^;&|]*--apply", I)
INSTALL = re.compile(r"(^|[\s;&|(/\"'])node(\.exe)?[\"']?\s+(\S*/)?install\.mjs", I)
# PS 판 $core 의 꼬리 문자 칸([^\s",;|&'<>)]*)은 일치를 늘리기만 한다 — 있는지 없는지는 머리로 정해진다
CORE = re.compile(r"CLAUDE\.md|3_시스템/hooks/|3_시스템/search\.py|3_시스템/conventions\.md|\.claude/settings\.json"
                  r"|3_시스템/_index/\.core-token|\.obsidian/plugins/", I)


def needs_gate(s):
    m = TOOL.search(s)
    if not m:
        return False
    tool = m.group(1)
    if tool.lower() in ("read", "grep", "glob", "notebookread"):
        return False
    shell = tool.lower() in ("bash", "powershell")
    if tool.lower() in ("edit", "write", "notebookedit", "multiedit"):
        m = FILEP.search(s)
    elif shell:
        m = CMD.search(s)
    else:
        return False
    probe = m.group(1) if m else ""
    if not probe.strip():
        return False
    p = probe.replace('\\"', '"').replace("\\\\", "/").replace("\\", "/")
    if shell:
        if (VERB.search(QUOTED.sub(" Q ", p)) or PYDEL.search(p)) and PLACE.search(p):
            return True
        if OBS.search(p) or APPLY.search(p) or INSTALL.search(p):
            return True
    return bool(CORE.search(p))


def broken(raw, why):
    """판정 없이 통과(3)할 때 core-gate.log 에 한 줄 — core-gate.ps1 의 «decide 없음» 줄과 같은 꼴."""
    try:
        import time
        m = TOOL.search(raw.decode("utf-8", "replace"))
        vault = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(vault, "3_시스템", "_index", "core-gate.log"), "ab") as f:
            f.write("{} [-] GATE-BROKEN({}) {} -\n".format(time.strftime("%Y-%m-%d %H:%M:%S"), why,
                                                         m.group(1) if m else "?").encode("utf-8"))
    except Exception:
        pass


def main():
    raw = sys.stdin.buffer.read()
    try:
        if not needs_gate(raw.decode("utf-8", "replace")):
            return 0
    except Exception:
        pass                                        # 모르면 게이트로
    import subprocess
    ps1 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "core-gate.ps1")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1], input=raw,
                           capture_output=True, timeout=TIMEOUT, creationflags=0x08000000 if os.name == "nt" else 0)
    except subprocess.TimeoutExpired:
        sys.stderr.buffer.write("⛔ 코어 게이트 판정이 {}초 안에 끝나지 않아 막았다(PC 가 몹시 바쁨). 잠시 뒤 다시 시도한다."
                                .format(TIMEOUT).encode("utf-8"))
        return 2
    except Exception as e:                          # PS 를 못 띄움(powershell 없음 · 기동 실패) — stdin 은 이미 읽었으니 bash 대체는 빈 입력이 된다
        sys.stderr.buffer.write("⚠ 코어 게이트 판정부(core-gate.ps1)를 띄우지 못했다: {}".format(e).encode("utf-8", "replace"))
        broken(raw, "판정부 못 띄움")
        return PS_ERROR
    sys.stdout.buffer.write(r.stdout)
    sys.stderr.buffer.write(r.stderr)
    if r.returncode in (0, 2):
        return r.returncode
    sys.stderr.buffer.write("\n⚠ 코어 게이트 판정부가 종료 코드 {} 로 끝났다(앞단이 {} 로 바꿔 냄).".format(r.returncode, PS_ERROR).encode("utf-8"))
    broken(raw, "판정부 끝 코드 {}".format(r.returncode))
    return PS_ERROR


if __name__ == "__main__":
    sys.exit(main())
