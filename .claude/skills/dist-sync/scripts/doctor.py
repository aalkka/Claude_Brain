"""dist-sync 건강 검사 — 외부뇌 brain.py doctor 가 부른다(module.json contributes.doctor).

마지막 줄 = 건강 한 줄 · 종료 0 = 배포판 길 있음 · 1 = 원격·git 없음(update·publish 가 첫 단계에서 멈춤) 또는 배포판 어긋남.
제작자 볼트(배포판 worktree 가 있음)면 «배포판 최신 점검»(dist-check.py)을 붙인다 — 어긋나면 무엇이 몇 건·할 일을 한 줄로.
  점검은 6시간 담아 둔다(배포판 커밋·원격·받기가 바뀌면 바로 다시) · 원격 받기는 하루 한 번 창 없이 따로 돌고 기다리지 않는다.
제작자 볼트가 아니면 네트워크를 쓰지 않는다 — 원격 주소와 마지막으로 받아 둔 dist/main 만 본다(받기는 update 스킬이).
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))  # .claude/skills/dist-sync/scripts → 볼트 루트
CACHE = os.path.join(VAULT, "3_시스템", "_index", "dist-sync", "check.json")  # mf:allow-path  (점검 담아 둠 · 개인 층)
CACHE_AGE = 6 * 3600


def git(*args):
    r = subprocess.run(["git", "-C", VAULT, *args], capture_output=True, timeout=10,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return r.returncode, r.stdout.decode("utf-8", "replace").strip()


def dist_line():
    """(줄, 어긋남 수) · 배포판 worktree 가 없으면 (None, 0)."""
    spec = importlib.util.spec_from_file_location("dist_check", os.path.join(HERE, "dist-check.py"))
    dc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dc)
    B = dc.find_dist(VAULT)
    if not B:
        return None, 0
    dc.fetch_later(B)
    key = [dc.git(B, "rev-parse", "HEAD", "@{upstream}")[1].split(), dc.fetch_age(B)]
    try:
        with open(CACHE, encoding="utf-8") as f:
            c = json.load(f)
        if c.get("key") == key and time.time() - c.get("at", 0) < CACHE_AGE:
            return c["line"], c["n"]
    except (OSError, ValueError, KeyError):
        pass
    r = dc.check(VAULT, B)
    line, n = dc.summary(r), dc.total(r)
    try:
        os.makedirs(os.path.dirname(CACHE), exist_ok=True)
        with open(CACHE, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"key": key, "at": time.time(), "line": line, "n": n}, f, ensure_ascii=False)
    except OSError:
        pass
    return line, n


def external_line():
    """필수 볼트 밖 설정(파이썬 꾸러미·git 훅·API 키 변수 등) 가운데 안 된 것 — 하루 한 번 따로 잰 것을 읽기만."""
    spec = importlib.util.spec_from_file_location("dist_external", os.path.join(HERE, "external.py"))
    ex = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ex)
    ex.VAULT, ex.CACHE = VAULT, os.path.join(VAULT, "3_시스템", "_index", "dist-sync", "external-check.json")  # mf:allow-path
    return ex.health()


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
    try:
        ext, en = external_line()
    except Exception as e:  # 확인이 깨져도 건강 줄의 원래 칸은 나온다
        ext, en = "볼트 밖 설정 확인 못 돎(%s)" % type(e).__name__, 1
    try:
        line, n = dist_line()
    except Exception as e:
        line, n = "배포판 점검 못 돎(%s)" % type(e).__name__, 1
    if ext and line:
        line = ext + " · " + line
    elif ext:
        line, n = ext, 0
    if line:
        print(line)        # 홈 건강 줄은 120자에서 자른다 — 무엇이 몇 건·할 일을 앞에 둔다
        return 1 if n or en else 0
    url = re.sub(r"^https?://|\.git$", "", re.sub(r"//[^@/]+@", "//", url))  # 주소에 든 토큰은 보이지 않게
    code, day = git("log", "-1", "--format=%cs", "dist/main")
    print("원격 %s · 받아 둔 dist/main %s" % (url, day if code == 0 and day else "없음(아직 안 받음)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
