# -*- coding: utf-8 -*-
"""R9 사본 시험 — 본 볼트를 임시 폴더에 복사(.git·node_modules 빼고)해 그 사본의 restructure.py 로
분류표 → 이전 파일 → 적용 → 점검을 돌리고 앞뒤를 견준다(본 볼트는 읽기만). 10-30 손으로 한 사본 시험을 대본으로(10-31).

  py -3 3_시스템/_eval/r9_copy_check.py --table <분류표.md> [--sources <원본 층 표.md>]  (10-31 본 볼트 적용 끝 — 다음 이전 때 표를 준다) [--keep]

분류표에 «고를 것» 줄이 있으면 사본에서는 `그대로`로 바꿔 돌린다(시험만 — 본 볼트 표는 손대지 않음).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(os.path.dirname(HERE))
PY = sys.executable
SKIP = {".git", "node_modules", "__pycache__"}

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def run(cv, *args, timeout=900):
    t = time.time()
    r = subprocess.run([PY, os.path.join(cv, "3_시스템", "restructure.py"), *args], cwd=cv, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip(), time.time() - t


def table_copy(cv, rel):
    """사본 안 표 — «고를 것» 줄은 시험만 «그대로»로."""
    a = os.path.join(cv, *rel.split("/"))
    t = open(a, encoding="utf-8").read()
    n = len(re.findall(r"\| `고를 것` \|", t))
    open(a, "w", encoding="utf-8", newline="").write(t.replace("| `고를 것` |", "| `그대로` |"))
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="3_시스템/_index/restructure/적용표-R9-2026-10-31.md")
    ap.add_argument("--sources", default="")
    ap.add_argument("--keep", action="store_true", help="사본 폴더를 지우지 않음")
    ap.add_argument("--clean", action="store_true", help="--keep 으로 남긴 지난 사본(임시 폴더 r9copy-*)만 지우고 끝")
    a = ap.parse_args()
    if a.clean:
        for d in sorted(os.listdir(tempfile.gettempdir())):
            if re.fullmatch(r"r9copy-\d+", d):
                shutil.rmtree(os.path.join(tempfile.gettempdir(), d), ignore_errors=True)
                print("지난 사본 지움 " + d)
        return 0
    cv = os.path.join(tempfile.gettempdir(), "r9copy-%d" % int(time.time()))
    t0 = time.time()
    shutil.copytree(VAULT, cv, ignore=lambda d, names: [n for n in names if n in SKIP])
    print("사본 %s · %.0f초" % (cv, time.time() - t0))
    res = {}
    try:
        code, out, s = run(cv, "check", "--save", "before.json")
        print("점검(앞) 코드 %d · %.0f초 · %s" % (code, s, out.splitlines()[-1] if out else ""))
        steps = [("R9", a.table)] + ([("R9-b", a.sources)] if a.sources else [])
        # 표 파일도 0_작업 안이라 R9 가 옮긴다 — 먼저 기계 칸으로 복사해 그 사본으로 돈다
        safe = []
        for name, rel in steps:
            src = os.path.join(cv, *rel.split("/"))
            if not os.path.exists(src):
                print("%s 표 없음 %s — 건너뜀" % (name, rel))
                continue
            dst = "3_시스템/_index/restructure/시험표-%s.md" % name
            os.makedirs(os.path.dirname(os.path.join(cv, *dst.split("/"))), exist_ok=True)
            shutil.copyfile(src, os.path.join(cv, *dst.split("/")))
            safe.append((name, dst))
        for name, rel in safe:
            picked = table_copy(cv, rel)
            plan = "3_시스템/_index/restructure/이전-%s-시험.json" % name
            code, out, s = run(cv, "plan", rel, "--out", plan)
            print("%s 계획 코드 %d · «고를 것»→그대로 %d · %s" % (name, code, picked, out.splitlines()[0] if out else ""))
            if code:
                print(out)
                res[name] = False
                break
            code, out, s = run(cv, "apply", plan, "--yes")
            warn = [x for x in out.splitlines() if "⚠" in x]
            print("%s 적용 코드 %d · %.0f초 · 경고 %d" % (name, code, s, len(warn)))
            for x in warn[:8]:
                print("   " + x.strip())
            if code:
                print("\n".join(out.splitlines()[-10:]))
                res[name] = False
                break
            res[name] = True
        code, out, s = run(cv, "check", "--compare", "before.json")
        print("점검(뒤) 코드 %d · %.0f초" % (code, s))
        print("\n".join("   " + x for x in out.splitlines()[-14:]))
        res["check"] = code == 0 and "새로 깨짐 0 " in out and "⚠" not in out
        roles = json.load(open(os.path.join(cv, "3_시스템", "roles.json"), encoding="utf-8"))
        miss = [k for k, v in roles["roles"].items() if not os.path.exists(os.path.join(cv, *v.split("/")))]
        print("roles 자리 없음 %d %s" % (len(miss), " ".join(miss[:8])))
        print("topic_roots %s" % " · ".join(roles.get("topic_roots", [])))
    finally:
        if not a.keep:
            shutil.rmtree(cv, ignore_errors=True)
    print("결과 %s" % json.dumps(res, ensure_ascii=False))
    return 0 if res and all(res.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
