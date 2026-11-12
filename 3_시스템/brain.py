"""외부뇌 행위 실행기 — 볼트 개혁 R4(행위 층 최소형). 외부뇌가 할 수 있는 일을 이름 붙은 행위 하나로 부른다.

같은 행위를 Claude 셸 · 터미널 · 예약 작업 · 옵시디언(바탕 플러그인) · 폰(나중)에서 똑같이 부르고, 부른 것은 같은 꼴로 장부에 남는다.
행위 선언 = 3_시스템/actions.json(코어) + 켜진 모듈 module.json 의 contributes.actions. 대본은 그대로 두고 감싸기만 한다.

사용:
  py -3 3_시스템/brain.py list [--json]                    # 할 수 있는 일
  py -3 3_시스템/brain.py run <행위> [이름=값 …] [--json]   # 예: run search q=전자기 · run files.move src=… dst=… why=…
  py -3 3_시스템/brain.py doctor [--json]                  # 건강 한 줄씩(claude 판 · 옵시디언 CLI · git 잠금 · 일정 · 색인 · 휴지통 · 받은함 · 따라가기 · 행위 선언 · 모듈마다)
  py -3 3_시스템/brain.py run collect.lms -- --dry         # `--` 뒤는 대본에 그대로(rest 를 선언한 행위만)
  py -3 3_시스템/brain.py home                             # 홈 화면 JSON(받은함·마감·수집 마지막·휴지통·장부 최근·주제) — 읽기만 · 장부에 안 남김
  py -3 3_시스템/brain.py modules [--json] [--no-claude] [--sync]   # 모듈 목록(판·스킬·행위·디스크·마지막 실행 · 켜짐·상시 토큰) — 켜기·끄기는 옵시디언 홈에서 사람이 · --sync = 설명서 사본 맞춤
  --by <누가>  장부의 «누가»(기본 = Claude 셸이면 claude, 아니면 user · 옵시디언은 obsidian · 예약은 schedule)
  --yes        send(밖으로 보냄)·usage(Claude 사용량) 행위를 실제로 돌린다

장부 = 3_시스템/ledger/actions.jsonl(덧붙이기만) — {ts, action, by, args, code, seconds}.
"""
import argparse, datetime as dt, json, os, re, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
CORE = os.path.join(HERE, "actions.json")
LOG = os.path.join(HERE, "ledger", "actions.jsonl")
NEEDS_YES = {"send", "usage"}


def detect_by():
    return "claude" if os.environ.get("CLAUDECODE") == "1" else "user"


def module_list(on_only=True):
    """모듈 등록부(roles.py) — 꺼진 모듈은 행위·건강·기록·화면에 안 나온다(ADR-035)"""
    sys.path.insert(0, HERE)
    import roles
    return roles.modules(on_only=on_only)


def load_actions():
    """[(행위, 출처)] · 문제 목록 — 코어 먼저, 켜진 모듈은 뒤. 같은 id 는 먼저 온 것만."""
    out, problems, seen = [], [], set()
    srcs = [(CORE, "core")] + [(os.path.join(m["dir"], "module.json"), "module:" + m["id"]) for m in module_list()]
    for path, owner in srcs:
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except (OSError, ValueError) as e:
            problems.append("%s 못 읽음(%s)" % (os.path.relpath(path, VAULT), type(e).__name__))
            continue
        acts = d.get("actions") if owner == "core" else (d.get("contributes") or {}).get("actions") or []
        for a in acts or []:
            if not a.get("id") or not (a.get("run") or a.get("builtin")):
                problems.append("%s: id·run 없는 행위" % owner)
                continue
            if a["id"] in seen:
                problems.append("%s: 행위 id 겹침 %s" % (owner, a["id"]))
                continue
            missing = [tok for tok in a.get("run") or [] if tok.endswith((".py", ".ps1")) and not os.path.isfile(os.path.join(VAULT, tok))]
            if missing and a.get("optional"):   # 배포판에 없는 수집 대본(LMS·웹 공지) — 행위가 안 보일 뿐 고장이 아니다
                continue
            for tok in missing:
                problems.append("%s: %s 의 대본 없음 %s" % (owner, a["id"], tok))
            seen.add(a["id"])
            out.append((a, owner))
    return out, problems


def log(entry):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def last_runs():
    last = {}
    try:
        with open(LOG, encoding="utf-8") as f:
            for ln in f:
                try:
                    e = json.loads(ln)
                    last[e["action"]] = e
                except (ValueError, KeyError):
                    pass
    except OSError:
        pass
    return last


def builtin_inbox():
    sys.path.insert(0, HERE)
    import roles
    d = roles.abs("inbox")
    items = sorted(p for p in os.listdir(d) if not p.startswith((".", "_"))) if os.path.isdir(d) else []
    days = [(time.time() - os.path.getmtime(os.path.join(d, p))) / 86400 for p in items]
    old = (" · 가장 오래된 것 %d일" % max(days)) if days else ""
    return 0, ("받은함 %d개%s" % (len(items), old)) + "".join("\n- %s (%d일)" % (p, x) for p, x in zip(items, days))


def cmd_list(a):
    acts, problems = load_actions()
    last = last_runs()
    if a.json:
        print(json.dumps({"actions": [dict(x, owner=o, last=last.get(x["id"])) for x, o in acts], "problems": problems}, ensure_ascii=False))
        return 0
    for x, o in acts:
        args = " ".join("%s=…" % g["name"] for g in x.get("args", [])) + (" [%s…]" % x["rest"]["name"] if x.get("rest") else "")
        lr = last.get(x["id"])
        print("%-17s %-6s %s%s%s" % (x["id"], x.get("risk", "?"), x.get("name", ""), ("  · " + args) if args else "",
                                    ("  · 마지막 %s %s" % (lr["ts"][5:16].replace("T", " "), "✓" if lr.get("code") == 0 else "✗")) if lr else ""))
    for p in problems:
        print("⚠ " + p)
    return 0


def cmd_run(a):
    acts, _ = load_actions()
    found = next(((x, o) for x, o in acts if x["id"] == a.action), None)
    if not found:
        off = next((m["id"] for m in module_list(on_only=False) if not m["on"] and a.action.startswith(m["id"] + ".")), None)
        print(("모듈 %s 이(가) 꺼져 있음: %s — 켜기 = 옵시디언 홈 «모듈»" % (off, a.action)) if off else ("모르는 행위: %s — brain.py list" % a.action), file=sys.stderr)
        return 2
    x, owner = found
    if x.get("risk") in NEEDS_YES and not a.yes:
        print("%s 은(는) %s 행위 — 정말 돌리려면 --yes" % (x["id"], x["risk"]), file=sys.stderr)
        return 3
    kv, rest = {}, []
    for t in a.params:
        m = re.match(r"^([A-Za-z_][\w]*)=(.*)$", t, re.S)
        (kv.__setitem__(m.group(1), m.group(2)) if m else rest.append(t))
    if rest and not x.get("rest"):
        print("%s 은(는) 덧붙일 인자를 받지 않음: %s" % (x["id"], " ".join(rest)), file=sys.stderr)
        return 2
    by = a.by or detect_by()
    t0 = time.time()
    if x.get("builtin") == "inbox":
        code, out, err = (*builtin_inbox(), "")
    else:
        need = [g["name"] for g in x.get("args", []) if g["name"] not in kv]
        if need:
            print("인자 모자람: %s — 예: brain.py run %s %s" % (", ".join(need), x["id"], " ".join("%s=…" % n for n in need)), file=sys.stderr)
            return 2
        sub = dict(kv, py=sys.executable, by=by, vault=VAULT)
        argv = [re.sub(r"\{(\w+)\}", lambda m: sub.get(m.group(1), m.group(0)), tok) for tok in x["run"]]
        argv = [os.path.join(VAULT, t) if t.endswith((".py", ".ps1")) and not os.path.isabs(t) else t for t in argv]
        if x.get("rest"):
            argv += rest
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        if a.json or x.get("empty"):  # empty 를 선언한 행위는 출력을 봐야 한다 — 받아서 그대로 다시 내보낸다
            r = subprocess.run(argv, cwd=VAULT, capture_output=True, env=env)
            code, out, err = r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
            if not a.json:
                sys.stdout.write(out) if sys.stdout else None
                sys.stderr.write(err) if sys.stderr else None
        else:
            code, out, err = subprocess.run(argv, cwd=VAULT, env=env).returncode, "", ""
    secs = round(time.time() - t0, 1)
    ts = dt.datetime.now().isoformat(timespec="seconds")
    if code == 0 and x.get("empty") and re.search(x["empty"], out, re.M):
        if by != "schedule":    # 예약은 15분마다 돈다 — 받은 것 없음을 하루 96줄 쌓지 않는다
            log({"ts": ts, "action": x["id"], "by": by, "code": 0, "empty": True})  # 받은 것 없음 — 짧게 적고 끝(사용자 10-30)
    else:
        log({"ts": ts, "action": x["id"], "owner": owner, "by": by, "args": kv or None, "rest": rest or None, "code": code, "seconds": secs})
    if a.json:
        print(json.dumps({"ok": code == 0, "action": x["id"], "code": code, "seconds": secs, "by": by, "out": out[-4000:], "err": err[-2000:]}, ensure_ascii=False))
    elif x.get("builtin"):
        print(out)
    return code


# ── 건강 ──
HEALTH = os.path.join(HERE, "_index", "health.json")  # 마지막 잼 — 세션 시작 주입(hooks/session-notice.py)이 읽는다


def chk(name, status, line):
    return {"name": name, "status": status, "line": line}


def save_health(res):
    """잴 때마다 남긴다 — 옵시디언은 30분마다 재도 메모리에만 들고 있어 Claude 세션이 몰랐다(11-12 사용자 «세션에 주입»)"""
    tmp = "%s.%d.tmp" % (HEALTH, os.getpid())  # 옵시디언 재기와 손 실행이 겹쳐도 서로 덮지 않게
    try:
        os.makedirs(os.path.dirname(HEALTH), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"at": time.time(), "rows": res}, f, ensure_ascii=False)
        os.replace(tmp, HEALTH)
    except OSError:
        pass


def doctor_checks():
    res = []
    try:
        sys.path.insert(0, HERE)
        import claude_bin
        c = claude_bin.candidates()
        if not c:
            res.append(chk("claude", "bad", "claude 실행 파일 없음"))
        else:
            top = c[0]
            stale = [x for x in c if x[2] == "독립 설치" and x[0] < top[0]]
            res.append(chk("claude", "warn" if stale else "ok", "%s(%s)%s" % (".".join(map(str, top[0])), top[2],
                       (" · 독립 설치는 %s — `claude update`" % ".".join(map(str, stale[0][0]))) if stale else "")))
    except Exception as e:  # noqa: BLE001 — 건강 검사는 멈추지 않는다
        res.append(chk("claude", "bad", "확인 실패(%s)" % type(e).__name__))
    exe = shutil.which("obsidian")
    if not exe:
        res.append(chk("옵시디언 CLI", "warn", "등록 안 됨 — 이동은 자체 엔진"))
    else:
        try:
            out = subprocess.run([exe, "vault"], capture_output=True, timeout=5).stdout.decode("utf-8", "replace")
            m = re.search(r"^path\t(.+)$", out, re.M)
            same = m and os.path.normcase(os.path.abspath(m.group(1).strip())) == os.path.normcase(VAULT)
            res.append(chk("옵시디언 CLI", "ok" if same else "warn", "이 볼트를 열고 있음 — 이동은 옵시디언이" if same else "이 볼트가 안 열려 있음 — 이동은 자체 엔진"))
        except (OSError, subprocess.TimeoutExpired):
            res.append(chk("옵시디언 CLI", "warn", "응답 없음(옵시디언 꺼짐?) — 이동은 자체 엔진"))
    lock = os.path.join(VAULT, ".git", "index.lock")
    if os.path.exists(lock):
        age = (time.time() - os.path.getmtime(lock)) / 60
        res.append(chk("git 잠금", "bad" if age > 10 else "warn", "index.lock %d분 — git 이 안 돌면 자동 커밋이 막힌다(incident 2026-09-19)" % age))
    else:
        res.append(chk("git 잠금", "ok", "없음"))
    try:
        r = subprocess.run([sys.executable, os.path.join(HERE, "schedule.py"), "check"], cwd=VAULT, capture_output=True, timeout=60, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        bad = [l for l in r.stdout.decode("utf-8", "replace").splitlines() if l.strip()]
        res.append(chk("일정", "ok" if r.returncode == 0 else "warn", "형식 맞음" if r.returncode == 0 else (bad[-1] if bad else "check 실패")[:120]))
    except (OSError, subprocess.TimeoutExpired):
        res.append(chk("일정", "warn", "check 를 못 돌림"))
    emb = os.path.join(HERE, "_index", "embeddings.json")
    if os.path.exists(emb):
        days = (time.time() - os.path.getmtime(emb)) / 86400
        res.append(chk("찾기 색인", "warn" if days > 7 else "ok", "%.0f일 전 · 다시 = brain.py run search.reindex" % days if days > 7 else "%.1f일 전" % days))
    else:
        res.append(chk("찾기 색인", "warn", "없음 — brain.py run search.reindex"))
    # 볼트 개혁 R8 — 휴지통 크기·나이(비우기는 사람) · 받은함 머무름(설계안 §13 B5) · 날 수 = 보존 일정표(2_지식/보존.md) · 정리 후보는 cleanup.py
    import roles
    t_days, i_days = roles.retention("휴지통"), roles.retention("받은함")  # None(무기한) = 알리지 않음
    t_days = float("inf") if t_days is None else t_days
    i_days = float("inf") if i_days is None else i_days
    try:
        import fileops
        items = fileops.trash_items(fileops.Ctx(VAULT))
        size = sum(x[3] for x in items)
        old = [x for x in items if x[1] >= t_days]
        res.append(chk("휴지통", "warn" if size > 1 << 30 or old else "ok", "%d항목 · %.1f MB%s" % (len(items), size / 1e6,
                       " · %d일 넘은 것 %d — 비우기 = 사람 `fileops purge --older %d`" % (t_days, len(old), t_days) if old else "")))
    except Exception as e:  # noqa: BLE001
        res.append(chk("휴지통", "warn", "확인 실패(%s)" % type(e).__name__))
    _, inbox = builtin_inbox()
    m = re.search(r"가장 오래된 것 (\d+)일", inbox.split("\n")[0])
    late = m and int(m.group(1)) > i_days
    res.append(chk("받은함", "warn" if late else "ok", inbox.split("\n")[0] + (" — %d일 넘김: inbox.py" % i_days if late else "")))
    # 작업 폴더 원칙(진행 중인 것만 · 끝나면 승격·삭제 — 사용자 10-31) — 끝난 과제가 남아 있으면 △
    try:
        import work
        w = work.summary(work.status())
        bad = w["끝남"] + w["멈춤"]
        res.append(chk("작업 폴더", "warn" if bad else "ok", "진행 %d%s" % (w["진행"], (" · 끝난 것 %d(결과물 없음 %d) · 멈춤 %d — 정리 계획 = brain.py run work.plan" % (
            w["끝남"], w["결과물없음"], w["멈춤"])) if bad else "")))
    except Exception as e:  # noqa: BLE001
        res.append(chk("작업 폴더", "warn", "확인 실패(%s)" % type(e).__name__))
    # 따라가기(설계안 §19.3) — 바깥에서 옮기거나 지운 것 · 답 기다리는 것(사라진 LMS 원본·행방 모름·한꺼번에 사라짐)
    try:
        import follow
        f = follow.status()
        wait = (["답 기다림 %d — follow.py pending" % len(f["items"])] if f["items"] else []) + (["한꺼번에 사라짐 %d — follow.py --accept" % f["held"]] if f["held"] else [])
        res.append(chk("따라가기", "warn" if wait or not f["ready"] else "ok", " · ".join(wait) if wait else "마지막 비교 %s" % (f["last"] or "")[5:16].replace("T", " ") if f["ready"] else "사진 없음 — brain.py run follow.run"))
    except Exception as e:  # noqa: BLE001
        res.append(chk("따라가기", "warn", "확인 실패(%s)" % type(e).__name__))
    # 기능 단계(옵션 설계 §3-4·§4-4) — 고른 값 파일 깨짐 · PC 가 바뀜 · 노트가 3배(빈 볼트 값으로 추천했음) → «옵션 추천 다시»
    try:
        import options
        s = options.show()
        why = [p for p in s["problems"] if p.startswith("고른 값 파일")][:1]
        why += ["PC 가 바뀜 — «옵션 추천 다시»"] if s["machine"]["changed"] else []
        why += ["노트가 3배 — «옵션 추천 다시»"] if s["machine"]["renotes"] else []
        low = [f["name"] for f in s["features"] if f["ready"] and s["now"].get(f["id"], "high") != "high"]
        res.append(chk("기능 단계", "warn" if why else "ok", " · ".join(why) if why else "낮춤 %d(%s)" % (len(low), "·".join(low)) if low
                       else "전부 높음" + ("" if s["file"] == "ok" else " · 추천 안 받음(«옵션 추천 다시»)")))
    except Exception as e:  # noqa: BLE001
        res.append(chk("기능 단계", "warn", "확인 실패(%s)" % type(e).__name__))
    _, problems = load_actions()
    res.append(chk("행위 선언", "bad" if problems else "ok", "; ".join(problems)[:200] if problems else "문제 없음"))
    return res + module_checks()


RANK = {"ok": 0, "warn": 1, "bad": 2}


def module_checks():
    """켜진 모듈마다 한 줄 — 판 · 정적 검사(module-forge check · 모듈과 무관한 볼트 경고는 뺌) · 모듈이 선언한 contributes.doctor.
    doctor 대본 계약: 마지막 줄 = 건강 한 줄 · 종료 코드 0 ok · 1 warn · 그 밖 bad · 20초 안."""
    mods = module_list()
    if not mods:
        return []
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    static = {}
    check_py = os.path.join(VAULT, ".claude", "skills", "module-forge", "scripts", "check.py")
    if os.path.isfile(check_py) and any(m["id"] == "module-forge" for m in mods):  # module-forge 를 끄면 정적 검사만 빠진다
        try:
            r = subprocess.run([sys.executable, check_py, "--all", "--no-registry"], cwd=VAULT, capture_output=True, timeout=60, env=env)
            static = json.loads(r.stdout.decode("utf-8", "replace")).get("modules") or {}
        except (OSError, subprocess.TimeoutExpired, ValueError):
            static = None
    res = []
    for m in mods:
        d, name, mj = m["dir"], m["id"], m["json"]
        if mj is None:
            res.append(chk("모듈 " + name, "bad", "module.json 못 읽음"))
            continue
        try:
            with open(os.path.join(d, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
                ver = json.load(f).get("version") or "판 ?"
        except (OSError, ValueError):
            ver = "plugin.json 없음"
        st, parts = "ok", [ver]
        s = static.get(name) if static else None
        if static is None:
            st, part = "warn", "정적 검사 못 돌림"
        elif s is None:
            part = "정적 검사 없음"
        elif s.get("blocks"):
            st, part = "bad", "검사 막힘 %d — %s" % (len(s["blocks"]), s["blocks"][0][:60])
        else:
            mine = [w for w in s.get("warns", []) if "무관" not in w]
            st, part = ("warn", "검사 경고 %d — %s" % (len(mine), mine[0][:60])) if mine else ("ok", "검사 통과")
        parts.append(part)
        doc = (mj.get("contributes") or {}).get("doctor") if isinstance(mj.get("contributes"), dict) else None
        if doc:
            argv = [sys.executable if t == "{py}" else (os.path.join(VAULT, t) if t.endswith((".py", ".ps1")) and not os.path.isabs(t) else t) for t in doc]
            try:
                r = subprocess.run(argv, cwd=VAULT, capture_output=True, timeout=20, env=env)
                line = (r.stdout.decode("utf-8", "replace").strip().splitlines() or ["(출력 없음)"])[-1]
                ds = {0: "ok", 1: "warn"}.get(r.returncode, "bad")
            except (OSError, subprocess.TimeoutExpired):
                line, ds = "doctor 를 못 돌림", "warn"
            st = max(st, ds, key=RANK.get)
            parts.append(line[:120])
        res.append(chk("모듈 " + name, st, " · ".join(parts)))
    return res


def cmd_doctor(a):
    res = doctor_checks()
    save_health(res)
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        mark = {"ok": "✓", "warn": "△", "bad": "✗"}
        for r in res:
            print("%s %-10s %s" % (mark[r["status"]], r["name"], r["line"]))
    return 1 if any(r["status"] == "bad" for r in res) else 0


# ── 홈·모듈 화면(볼트 개혁 R7) — 옵시디언 «외부뇌 홈»이 그린다 · 읽기만(행위가 아니라 장부에 안 남김) ──
def tail_jsonl(path, n):
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()[-n * 3:]
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            out.append(json.loads(ln))
        except ValueError:
            pass
    return out[-n:]


def home_data():
    sys.path.insert(0, HERE)
    import roles, topic, fileops
    today = dt.datetime.now(topic.KST).date()
    d = roles.abs("inbox")
    items = sorted(p for p in os.listdir(d) if not p.startswith((".", "_"))) if os.path.isdir(d) else []
    ages = {p: int((time.time() - os.path.getmtime(os.path.join(d, p))) / 86400) for p in items}
    up = topic.upcoming(today)
    acts = {x["id"]: x for x, _ in load_actions()[0]}
    runs = last_runs()
    try:
        tr = fileops.trash_items(fileops.Ctx(VAULT))
        t_days = roles.retention("휴지통")
        t_days = float("inf") if t_days is None else t_days
        trash = {"count": len(tr), "mb": round(sum(x[3] for x in tr) / 1e6, 1), "old": sum(1 for x in tr if x[1] >= t_days)}
    except Exception as e:  # noqa: BLE001 — 홈은 멈추지 않는다
        trash = {"error": type(e).__name__}
    sugg = {}
    if items:                                   # 받은함 제안(inbox.py · §13.3 B3 ③ «홈에서 한 번 눌러 확정») — 머문 것이 있을 때만 잰다
        try:
            import inbox
            cx = fileops.Ctx(VAULT, dry=True)
            sugg = {p: inbox.classify_one(p, cx) for p in items[:8]}
        except Exception:  # noqa: BLE001 — 제안이 깨져도 홈은 그린다
            sugg = {}
    topics = []
    for t in roles.topics():
        nxt = next((r for r in up if r["topic"] == t["이름"]), None)
        dirs = topic.topic_dirs(t)
        mt = max([os.path.getmtime(f) for _, p in dirs for f in topic.walk_files(os.path.join(VAULT, *p.split("/")))] or [0])
        topics.append({"이름": t["이름"], "영역": t.get("영역"), "별칭": t.get("별칭") or [], "상태": t.get("상태"),
                       "next": {k: nxt[k] for k in ("date", "wd", "time", "end", "text", "days")} if nxt else None, "mtime": mt or None})
    try:  # 작업 폴더 작업 상태(work.py — 끝남·결과물 없음·멈춤) · 탐색기 배지·홈 카드가 쓴다
        import work
        wk = work.summary(work.status())
    except Exception as e:  # noqa: BLE001 — 홈은 멈추지 않는다
        wk = {"error": type(e).__name__}
    try:  # 따라가기 — 사라진 LMS 원본·행방 모름 · 한꺼번에 사라짐(있을 때만 홈에 묶음)
        import follow
        fl = follow.status()
    except Exception:  # noqa: BLE001 — 홈은 멈추지 않는다
        fl = {"items": [], "held": 0}
    try:  # 볼트 밖 후보(§13.3 B2②) — 내려받기·바탕화면의 볼트에 없는 문서 · 옮기지 않음 · 절대 경로는 안 내보냄
        import outside
        ot = [{k: x[k] for k in ("key", "name", "place", "days")} for x in outside.candidates()]
    except Exception:  # noqa: BLE001 — 홈은 멈추지 않는다
        ot = []
    return {"today": today.isoformat(),
            "work": wk,
            "follow": fl,
            "outside": ot,
            "inbox": {"count": len(items), "oldest": max(ages.values()) if ages else None, "path": roles.path("inbox"),
                      "items": [dict({"name": p, "days": ages[p]}, **{k: sugg[p][k] for k in ("dst", "sure", "why", "dup", "act", "n") if p in sugg}) for p in items[:8]]},
            "deadlines": up[:6],
            "collect": collect_alerts() + [dict(runs[i], name=acts.get(i, {}).get("name", i)) for i in sorted(runs) if i.startswith("collect.")],
            "trash": trash,
            "ops": tail_jsonl(os.path.join(HERE, "ledger", "ops.jsonl"), 5),
            "topics": topics}


def collect_alerts():
    """홈 «수집» 칸에 열린 대기열을 빨갛게(code 1) — 끊긴 로그인이 조용히 지나가지 않게(10-27~11-03 8회 실측)."""
    try:
        with open(os.path.join(HERE, "_index", "수집-대기열.md"), encoding="utf-8") as f:
            lines = [ln for ln in f.read().splitlines() if ln.startswith("- [ ] ")]
    except OSError:
        return []
    when = lambda ln: ln[6:25].replace(" ", "T")
    login = [ln for ln in lines if "mylms 로그인 만료" in ln]
    rest = [ln for ln in lines if "mylms 로그인 만료" not in ln]
    return ([{"name": "mylms 로그인 필요", "ts": when(login[-1]), "code": 1}] if login else []) + \
           ([{"name": "수집 대기열 %d건" % len(rest), "ts": when(rest[-1]), "code": 1}] if rest else [])


def modules_data(ask_claude=True):
    """모듈마다(꺼진 것도 — 켤 스위치가 있어야 한다) — 판·설명·스킬·행위·디스크·마지막 실행·켜짐 · (claude 가 있으면) 상시 토큰(`plugin details`)."""
    sys.path.insert(0, HERE)
    runs = tail_jsonl(LOG, 2000)
    out = []
    for m in module_list(on_only=False):
        d, mid, mj = m["dir"], m["id"], m["json"] or {}
        try:
            with open(os.path.join(d, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
                pj = json.load(f)
        except (OSError, ValueError):
            pj = {}
        size = 0
        for root in [d] + [os.path.join(VAULT, *t.rstrip("/").split("/")) for t in mj.get("touches", []) if isinstance(t, str)]:
            for dp, _, fns in os.walk(root):
                size += sum(os.path.getsize(os.path.join(dp, f)) for f in fns)
        mine = [e for e in runs if e.get("owner") == "module:" + mid]
        con = mj.get("contributes") if isinstance(mj.get("contributes"), dict) else {}
        out.append({"id": mid, "plugin": mid + "@skills-dir", "version": pj.get("version"), "description": pj.get("description", ""),
                    "skills": (mj.get("surfaces") or {}).get("skills", []), "actions": [a.get("id") for a in con.get("actions", [])],
                    "doctor": bool(con.get("doctor")), "mb": round(size / 1e6, 1), "last": mine[-1] if mine else None,
                    "enabled": m["on"], "always_on": None})
    if ask_claude and out:
        import claude_bin
        from concurrent.futures import ThreadPoolExecutor
        exe = claude_bin.newest()
        env = dict(os.environ)
        for k in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY"):  # 10-02 게이트웨이 사고 — 전역 변수를 물려주지 않는다
            env.pop(k, None)

        def run(*args):
            try:
                return subprocess.run([exe, "plugin", *args], cwd=VAULT, capture_output=True, timeout=60, env=env).stdout.decode("utf-8", "replace")
            except (OSError, subprocess.TimeoutExpired):
                return ""
        with ThreadPoolExecutor(max_workers=len(out)) as ex:
            det = {m["id"]: ex.submit(run, "details", m["plugin"]) for m in out}
            for m in out:
                g = re.search(r"Always-on:\s*~?([\d,]+)\s*tok", det[m["id"]].result())
                m["always_on"] = int(g.group(1).replace(",", "")) if g else None
    return out


# 모듈 설명서 사본(ADR-035) — 옵시디언은 점 폴더를 안 본다. 켜진 모듈의 장을 보이는 자리에 두어야 검색·빠른 전환·링크·Claude 가 찾는다.
DOC_MARK = "%% 모듈 설명서 사본"


def _retry(fn, *args):
    """켜진 옵시디언이 쥔 파일은 잠깐 WinError 5 — 0.1초 간격 30번"""
    for i in range(30):
        try:
            return fn(*args)
        except PermissionError:
            if i == 29:
                raise
            time.sleep(0.1)


def module_chapters(m):
    """모듈이 선언한 설명서 장 — [(사본 이름, 원본)] · 모듈 밖·없는 파일은 건너뜀(module-forge check 가 막는다)"""
    out = []
    for ch in ((m["json"] or {}).get("contributes") or {}).get("manual") or []:
        rel = ch.get("file") if isinstance(ch, dict) else None
        src = os.path.join(VAULT, *str(rel).split("/")) if rel else ""
        if rel and os.path.normcase(os.path.abspath(src)).startswith(os.path.normcase(m["dir"]) + os.sep) and os.path.isfile(src):
            out.append((os.path.basename(src), src))
    return out


def sync_module_docs():
    """켜진 모듈의 장 → 3_시스템/설명서/_index/ · 꺼진 모듈 것은 치운다(사본표가 달린 파일만 · 다시 켜면 또 만든다). 쓸 것이 없으면 안 쓴다."""
    dst = os.path.join(HERE, "설명서", "_index")
    want, wrote, gone = {}, [], []
    for m in module_list():
        for name, src in module_chapters(m):
            with open(src, encoding="utf-8") as f:
                text = f.read()
            rel = os.path.relpath(src, VAULT).replace(os.sep, "/")
            mark = "%s — 원본 = %s · 고치려면 원본을 고친다 · 모듈을 끄면 이 파일은 사라진다 %%%%\n" % (DOC_MARK, rel)
            g = re.match(r"---\r?\n.*?\r?\n---\r?\n", text, re.S)
            want[name] = text[:g.end()] + mark + text[g.end():] if g else mark + text
    if want:
        os.makedirs(dst, exist_ok=True)
    for name, body in want.items():
        p = os.path.join(dst, name)
        try:
            with open(p, encoding="utf-8", newline="") as f:
                if f.read() == body:
                    continue
        except OSError:
            pass
        tmp = os.path.join(dst, ".%s.tmp" % name)
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(body)
        _retry(os.replace, tmp, p)
        wrote.append(name)
    for name in sorted(os.listdir(dst)) if os.path.isdir(dst) else []:
        p = os.path.join(dst, name)
        if name in want or not name.endswith(".md") or not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8", errors="replace") as f:
            if DOC_MARK not in f.read(2000):
                continue  # 사본이 아닌 파일은 손대지 않는다
        _retry(os.remove, p)
        gone.append(name)
    return {"want": sorted(want), "wrote": wrote, "gone": gone}


def cmd_home(a):
    print(json.dumps(home_data(), ensure_ascii=False))
    return 0


def cmd_modules(a):
    if a.sync:
        print(json.dumps(sync_module_docs(), ensure_ascii=False))
        return 0
    ms = modules_data(not a.no_claude)
    if a.json:
        print(json.dumps(ms, ensure_ascii=False))
        return 0
    for m in ms:
        st = {True: "켜짐", False: "꺼짐", None: "?"}[m["enabled"]]
        print("%-14s %-8s %s · 스킬 %d · 행위 %d · %.1f MB%s" % (m["id"], m["version"] or "?", st, len(m["skills"]), len(m["actions"]), m["mb"],
                                                            " · 상시 %d 토큰" % m["always_on"] if m["always_on"] is not None else ""))
    return 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    common = argparse.ArgumentParser(add_help=False)          # 명령 뒤에 붙인다: brain.py list --json
    common.add_argument("--json", action="store_true", help="묻지 않고 JSON 한 줄")
    common.add_argument("--by", help="장부의 «누가»")
    common.add_argument("--yes", action="store_true", help="send·usage 행위를 실제로")
    ap = argparse.ArgumentParser(prog="brain", description="외부뇌 행위 실행기(R4)")
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("list", parents=[common])
    p = sp.add_parser("run", parents=[common])
    p.add_argument("action")
    p.add_argument("params", nargs="*", help="이름=값 … (그 밖은 rest 인자)")
    sp.add_parser("doctor", parents=[common])
    sp.add_parser("home", parents=[common])
    p = sp.add_parser("modules", parents=[common])
    p.add_argument("--no-claude", action="store_true", help="상시 토큰을 claude 에 묻지 않음(빠름)")
    p.add_argument("--sync", action="store_true", help="켜진 모듈의 설명서 사본을 맞춤(옵시디언이 켤 때·모듈을 켜고 끌 때 부름)")
    argv = list(sys.argv[1:] if argv is None else argv)
    tail = []
    if "--" in argv:                                          # `-- --sleep-after` 처럼 대본 선택을 넘김 — 3.11 argparse 는 하위 명령 뒤 `--` 를 못 넘겨 직접 가른다
        i = argv.index("--")
        argv, tail = argv[:i], argv[i + 1:]
    a = ap.parse_args(argv)
    if a.cmd == "run":
        a.params += tail
    return {"list": cmd_list, "run": cmd_run, "doctor": cmd_doctor, "home": cmd_home, "modules": cmd_modules}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
