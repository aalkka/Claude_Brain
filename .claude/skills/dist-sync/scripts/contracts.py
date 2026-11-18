"""모듈 계약 — 볼트 모듈이 쓰는 코어 이름(module.json `uses_core`)이 코어에 있나 재고, 켜진 모듈의 업데이트 시험(`contributes.update_check`)을 돌린다(LLM 0).

  py -3 .claude/skills/dist-sync/scripts/contracts.py names [--core <코어 뿌리>] [--all] [--json]   # 이름만(빠름 · 불러오지 않고 ast)
  py -3 -u .claude/skills/dist-sync/scripts/contracts.py run [--json]                               # 이름 + 켜진 모듈의 update_check(하나 상한 10분 · 창 없음)

dist-sync:update 4단계 «적용 뒤»가 run 을 부른다 — 깨지면 업데이트 보고 맨 위에 «<모듈> 계약 깨짐» + 되돌리기(보고 5단계의 undo).
dist-check ⑧ 이 names(--core = 배포판 worktree · 꺼진 모듈·배포판에 안 싣는 모듈까지)를 부른다 — 이 볼트 모듈이 쓰는 코어 이름이 배포판에 없음.
--core 를 주면 코어 파일을 그 뿌리에서 읽는다(모듈 선언은 늘 이 볼트). 종료 0 = 깨짐 없음 · 1 = 깨짐.
"""
import argparse
import ast
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LIMIT = 600                       # 시험 하나 상한(초) — 계획서 §6.2 · mobility 전부 55초(11-17 잼)


def top_names(path):
    """코어 파일 맨 위 이름(함수·클래스·값·불러온 이름) — 불러오지 않고 ast 로만. 못 읽으면 None.
    module-forge check.py 에 같은 함수가 있다(모듈끼리 서로 기대지 않게 — 하나를 고치면 다른 쪽도)."""
    try:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return None
    names = set()

    def grab(t):
        if isinstance(t, ast.Name):
            names.add(t.id)
        elif isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                grab(e)

    def walk(body):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(n.name)
            elif isinstance(n, ast.Assign):
                for t in n.targets:
                    grab(t)
            elif isinstance(n, (ast.AnnAssign, ast.AugAssign)):
                grab(n.target)
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    names.add((a.asname or a.name).split(".")[0])
            elif isinstance(n, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                for part in ("body", "orelse", "finalbody"):
                    walk(getattr(n, part, None) or [])
                for h in getattr(n, "handlers", None) or []:
                    walk(h.body)
    walk(tree.body)
    return names


def modules(vault, on_only=True):
    """볼트의 모듈 [{id, json, on}] — 켬·끔은 코어 roles 한 곳(그 볼트의 설정 층)."""
    sys.path.insert(0, os.path.join(VAULT, "3_시스템"))
    import roles  # noqa: E402
    return [m for m in roles.modules(on_only=on_only, vault=vault) if isinstance(m.get("json"), dict)]


def names(vault=VAULT, core=None, on_only=True):
    """깨진 계약 [{module, file, missing: [이름…] | None(파일 없음)}] · 잰 수 {파일, 이름}."""
    core = core or vault
    broken, n_files, n_names = [], 0, 0
    for m in modules(vault, on_only):
        uc = m["json"].get("uses_core")
        if not isinstance(uc, dict):
            continue
        for rel, want in uc.items():
            if not isinstance(want, list):
                continue
            n_files += 1
            n_names += len(want)
            full = os.path.join(core, *str(rel).replace("\\", "/").split("/"))
            if not os.path.isfile(full):
                broken.append({"module": m["id"], "file": rel, "missing": None})
                continue
            if not want or not str(rel).endswith(".py"):
                continue
            have = top_names(full)
            miss = [x for x in want if have is None or x not in have]
            if miss:
                broken.append({"module": m["id"], "file": rel, "missing": miss})
    return broken, {"파일": n_files, "이름": n_names}


def fill(argv, vault):
    out = []
    for t in argv:
        out.append(sys.executable if t == "{py}" else t.replace("{vault}", vault))
    return out


def run_checks(vault=VAULT, limit=LIMIT):
    """켜진 모듈의 update_check 를 차례로(하나씩 — 시험끼리 문·임시 볼트가 안 겹치게). [{module, cmd, code, secs, tail}]."""
    rows = []
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
    for m in modules(vault, True):
        u = (m["json"].get("contributes") or {}).get("update_check")
        if not u:
            continue
        cmds = u if isinstance(u, list) and all(isinstance(c, list) for c in u) else [u]
        for c in cmds:
            if not (isinstance(c, list) and all(isinstance(t, str) for t in c)):
                rows.append({"module": m["id"], "cmd": str(c), "code": None, "secs": 0, "tail": "명령줄 꼴이 아님"})
                continue
            argv, t0 = fill(c, vault), time.time()
            try:
                r = subprocess.run(argv, cwd=vault, capture_output=True, timeout=limit, creationflags=NOWIN, env=env)
                code, out = r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")
            except subprocess.TimeoutExpired as e:
                code, out = None, ((e.stdout or b"") + (e.stderr or b"")).decode("utf-8", "replace") + "\n상한 %d초 넘음" % limit
            except OSError as e:
                code, out = None, "못 띄움: %s" % e
            tail = [ln for ln in out.splitlines() if ln.strip()][-6:]
            rows.append({"module": m["id"], "cmd": " ".join(c), "code": code, "secs": round(time.time() - t0, 1), "tail": "\n".join(tail)})
    return rows


def text(broken, counted, rows=None):
    L = []
    bad_runs = [r for r in rows or [] if r["code"] != 0]
    for b in broken:
        what = "코어 파일 없음" if b["missing"] is None else "이름 없음: " + ", ".join(b["missing"])
        L.append("⛔ %s 계약 깨짐 — %s · %s" % (b["module"], b["file"], what))
    for r in bad_runs:
        L.append("⛔ %s 계약 깨짐 — 시험 실패(종료 %s · %s초) %s" % (r["module"], r["code"], r["secs"], r["cmd"]))
        L += ["   " + x for x in r["tail"].splitlines()]
    if broken or bad_runs:
        L.append("되돌리기 = 업데이트 묶음 undo(update 5단계 명령) · 또는 모듈을 새 코어에 맞게 고친 뒤 다시 잰다")
    ok_runs = [r for r in rows or [] if r["code"] == 0]
    L.append("모듈 계약 — 코어 %d파일 · 이름 %d개 중 깨짐 %d%s" % (
        counted["파일"], counted["이름"], len(broken),
        "" if rows is None else " · 시험 %d개 통과 %d(%.0f초)" % (len(rows), len(ok_runs), sum(r["secs"] for r in rows))))
    return "\n".join(L)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="모듈 계약 — 코어 이름(uses_core) · 업데이트 시험(update_check)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    n = sp.add_parser("names")
    n.add_argument("--core", help="코어 파일을 읽을 뿌리(기본 = 이 볼트 · 배포판 worktree 를 주면 새 판 기준)")
    n.add_argument("--all", action="store_true", help="꺼진 모듈도")
    n.add_argument("--json", action="store_true")
    r = sp.add_parser("run")
    r.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "names":
        broken, counted = names(VAULT, os.path.abspath(a.core) if a.core else None, not a.all)
        print(json.dumps({"broken": broken, "counted": counted}, ensure_ascii=False, indent=1) if a.json else text(broken, counted))
        return 1 if broken else 0
    broken, counted = names(VAULT)
    rows = run_checks(VAULT)
    print(json.dumps({"broken": broken, "counted": counted, "runs": rows}, ensure_ascii=False, indent=1) if a.json else text(broken, counted, rows))
    return 1 if broken or any(x["code"] != 0 for x in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
