"""가장 새 claude 실행 파일 — 볼트 대본이 claude -p 를 부를 때 쓴다(ingest_vision · notice-filter).

설치된 것 중 판이 가장 높은 것: 데스크톱 앱이 스스로 올리는 판(%LOCALAPPDATA%/Claude-Data/<id>/claude-code/<판>/<해시>/claude.exe)
· 독립 설치(~/.local/bin/claude.exe) · PATH. 없으면 "claude"(PATH 에 맡김).
까닭(10-30 실측): 독립 설치 2.1.287(10-02 뒤 안 올라감)은 별칭 haiku 를 Haiku 4.5 로, 데스크톱 앱 판 2.1.309 는 Haiku 5.5 로 풀었다.
모델은 별칭(opus·sonnet·haiku)으로 넘긴다 — ID 를 박으면 새 모델이 나와도 옛 판에 묶인다(사용자 10-30).
같은 규칙의 플러그인 쪽 = brain-base src/engine.ts findClaudeBin.

사용:  py -3 3_시스템/claude_bin.py      # 고른 경로와 판
"""
import glob, os, re, shutil, subprocess

_cache = None


def _ver(s):
    return tuple(int(x) for x in s.split("."))


def candidates():
    """[(판 튜플, 경로, 어디서)] — 판이 높은 순"""
    out = []
    data = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local"), "Claude-Data")
    for p in glob.glob(os.path.join(data, "*", "claude-code", "*", "*", "claude.exe")):
        v = os.path.basename(os.path.dirname(os.path.dirname(p)))
        if re.fullmatch(r"\d+\.\d+\.\d+", v):
            out.append((_ver(v), p, "데스크톱 앱"))
    own = {os.path.normcase(os.path.abspath(x)) for x in (os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe"), shutil.which("claude")) if x and os.path.isfile(x)}
    for p in own:
        try:
            got = subprocess.run([p, "--version"], capture_output=True, timeout=15).stdout.decode("utf-8", "replace")
        except (OSError, subprocess.TimeoutExpired):
            continue
        m = re.search(r"(\d+\.\d+\.\d+)", got)
        if m:
            out.append((_ver(m.group(1)), p, "독립 설치"))
    return sorted(out, reverse=True)


def newest():
    """가장 새 claude 경로(한 번 고르면 이 프로세스 동안 그대로)"""
    global _cache
    if _cache is None:
        c = candidates()
        _cache = c[0][1] if c else "claude"
    return _cache


if __name__ == "__main__":
    for v, p, where in candidates():
        print(".".join(map(str, v)), where, p)
    print("고름:", newest())
