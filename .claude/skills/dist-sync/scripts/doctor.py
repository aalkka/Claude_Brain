"""dist-sync 건강 검사 — 외부뇌 brain.py doctor 가 부른다(module.json contributes.doctor).

마지막 줄 = 건강 한 줄 · 종료 0 = 배포판 길 있음 · 1 = 원격·git 없음(update·publish 가 첫 단계에서 멈춤).
네트워크는 쓰지 않는다 — 원격 주소와 마지막으로 받아 둔 dist/main 만 본다(받기는 update 스킬이).
"""
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))  # .claude/skills/dist-sync/scripts → 볼트 루트


def git(*args):
    r = subprocess.run(["git", "-C", VAULT, *args], capture_output=True, timeout=10)
    return r.returncode, r.stdout.decode("utf-8", "replace").strip()


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not shutil.which("git"):
        print("git 없음 — update·publish 를 못 돎")
        return 1
    code, url = git("remote", "get-url", "dist")
    if code:
        print("원격 dist 없음 — update 스킬이 처음에 더한다")
        return 1
    url = re.sub(r"^https?://|\.git$", "", re.sub(r"//[^@/]+@", "//", url))  # 주소에 든 토큰은 보이지 않게
    code, day = git("log", "-1", "--format=%cs", "dist/main")
    print("원격 %s · 받아 둔 dist/main %s" % (url, day if code == 0 and day else "없음(아직 안 받음)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
