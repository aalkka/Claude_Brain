"""구독 해지 대비 시험(11-11 · 구독 해지 대비) — 가짜 claude 로 «끊김 흉내»를 걸고 기능마다 잰다.

  py -3 3_시스템/_eval/subguard_check.py           # 흉내 3갈래(lapsed·callfail·nologin) × 기능 + 흉내 걷음 → 표 · 사용량 0
  py -3 3_시스템/_eval/subguard_check.py --real    # + 진짜 claude 로 오탐 0(auth status + 작은 호출 1번 · haiku · 구독 사용량 아주 조금)

시험 볼트(임시 폴더)에서 돈다 — 진짜 볼트의 상태 파일·대기열·알림을 건드리지 않는다. 윈도 알림은 띄우지 않고(BRAIN_SUB_NO_TOAST) 장부 줄로 센다.
가짜 claude = _eval/subguard/fake_claude.cs 를 csc 로 만든 claude.exe + fake_claude.py(갈래 = fake_claude.mode).
"""
import json, os, shutil, subprocess, sys, tempfile, textwrap, time

HERE = os.path.dirname(os.path.abspath(__file__))
SYS = os.path.dirname(HERE)
VAULT = os.path.dirname(SYS)
CSC = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
sys.path.insert(0, SYS)
import claude_bin  # noqa: E402

REAL = "--real" in sys.argv
rows, fails = [], []


def ok(name, cond, got=""):
    rows.append((name, "통과" if cond else "실패", str(got)[:160]))
    if not cond:
        fails.append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + ("" if cond else f"  — {str(got)[:300]}"), flush=True)


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items() if not (k.startswith("ANTHROPIC_") or k.startswith("CLAUDE_CODE") or k in ("CLAUDECODE",))}
    env.update(PYTHONIOENCODING="utf-8", FILEOPS_NO_OBSIDIAN="1", BRAIN_SUB_NO_TOAST="1", **extra)
    return env


def main():
    root = tempfile.mkdtemp(prefix="subguard-")
    fake = os.path.join(root, "fake")
    os.makedirs(fake)
    shutil.copy2(os.path.join(HERE, "subguard", "fake_claude.py"), fake)
    exe = os.path.join(fake, "claude.exe")
    r = subprocess.run([CSC, "-nologo", "-out:" + exe, os.path.join(HERE, "subguard", "fake_claude.cs")], capture_output=True)
    if r.returncode:
        sys.exit("가짜 claude 못 만듦: " + r.stdout.decode("utf-8", "replace")[-400:])
    real = claude_bin.newest()
    open(os.path.join(fake, "real.path"), "w", encoding="utf-8").write(real)
    calls = os.path.join(fake, "calls.log")

    def mode(m):
        open(os.path.join(fake, "fake_claude.mode"), "w", encoding="utf-8").write(m)

    def ncalls(kind="-p"):
        try:
            return sum(1 for ln in open(calls, encoding="utf-8") if f'"{kind}"' in ln)
        except OSError:
            return 0

    # 시험 볼트 — 3_시스템 맨 위 대본·설정 전부(코드뿐) + 그림 하나 + LMS 마감 대기 글 하나
    tv = os.path.join(root, "vault")
    ts = os.path.join(tv, "3_시스템")
    os.makedirs(os.path.join(ts, "_index", "lms"))
    os.makedirs(os.path.join(ts, "_index", "collect"))
    for f in os.listdir(SYS):
        if f.endswith((".py", ".json")) and os.path.isfile(os.path.join(SYS, f)) and not f.endswith(".local.json"):
            shutil.copy2(os.path.join(SYS, f), ts)
    os.makedirs(os.path.join(tv, "1_수집", "시험"))
    os.makedirs(os.path.join(tv, "2_지식", "일정"))
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(im)
    d.ellipse((60, 40, 340, 260), outline="black", width=6)
    d.line((60, 150, 340, 150), fill="black", width=4)
    im.save(os.path.join(tv, "1_수집", "시험", "그림.png"))
    os.makedirs(os.path.join(tv, "0_작업", "시험"))
    open(os.path.join(tv, "0_작업", "시험", "공지.md"), "w", encoding="utf-8").write("---\ntitle: 과제 공지\n---\n# 과제 1 제출\n\n11월 20일까지 제출.\n")
    json.dump({"p1": {"path": "0_작업/시험/공지.md", "title": "과제 1 제출", "date": "2026-11-11"}}, open(os.path.join(ts, "_index", "lms", "마감-대기.json"), "w", encoding="utf-8"))
    state = os.path.join(ts, "_index", "subscription.json")
    slog = os.path.join(ts, "_index", "subscription.log")
    queue = os.path.join(ts, "_index", "수집-대기열.md")
    env = clean_env(BRAIN_CLAUDE_BIN=exe, INGEST_VISION_MODEL="haiku")

    def py(code, timeout=180):
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", "import sys; sys.path.insert(0, r'%s')\n" % ts + textwrap.dedent(code)],
                           cwd=tv, env=env, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")

    def ingest():
        return py("import runpy; sys.argv = ['ingest.py', '1_수집/시험/그림.png', '--vision', '--force']; runpy.run_path(r'%s', run_name='__main__')" % os.path.join(ts, "ingest.py"), 300)

    def alerts():
        try:
            return sum(1 for ln in open(slog, encoding="utf-8") if " 알림 " in ln)
        except OSError:
            return 0

    def st():
        try:
            return json.load(open(state, encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def qlines():
        try:
            return sum(1 for ln in open(queue, encoding="utf-8") if ln.startswith("- [ ]"))
        except OSError:
            return 0

    auto = """
        import importlib.util, json
        json.dump({'auto_judge': True}, open('3_시스템/collect.local.json', 'w'))
        s = importlib.util.spec_from_file_location('nf', '3_시스템/notice-filter.py'); nf = importlib.util.module_from_spec(s); s.loader.exec_module(nf)
        tot = nf.extract(10, sid='lms-post', settle=False, stop_on_warning=True)
        print('자동 결과', tot)
        w = importlib.util.spec_from_file_location('wc', '3_시스템/web-collect.py'); wc = importlib.util.module_from_spec(w); w.loader.exec_module(wc)
        wc.filt = lambda: nf
        wc.auto_extract({'id': 'lms-post', 'filter': {'auto_max': 10}}, {})
        print('web-collect 자동 끝')
    """
    manual = """
        import importlib.util
        s = importlib.util.spec_from_file_location('nf', '3_시스템/notice-filter.py'); nf = importlib.util.module_from_spec(s); s.loader.exec_module(nf)
        try:
            nf.extract(10, sid='lms-post', settle=False)
            print('수동 결과 끝남(멈추지 않음)')
        except SystemExit as e:
            print('수동 멈춤', e)
    """
    rc_code = """
        import os, json
        os.environ['BRAIN_RC_BIN'] = json.dumps([os.environ['BRAIN_CLAUDE_BIN']])
        import server
        try:
            server.rc_start({})
            print('RC 띄움')
        except server.Bad as e:
            print('RC 막음', e.code, e.msg)
    """

    expect = {"lapsed": claude_bin.LAPSED, "callfail": claude_bin.LAPSED, "nologin": claude_bin.LOGIN}
    for m, kind in expect.items():
        print(f"\n[{m}] 흉내 — 기대 갈래 {kind}", flush=True)
        mode(m)
        for p in (state, slog, queue):
            if os.path.exists(p):
                os.remove(p)
        n0 = ncalls()
        q0 = qlines()
        c1, o1 = ingest()
        c2, o2 = ingest()
        ok(f"[{m}] 그림 읽기 1회째 = 멈춤 줄(플러그인 알림)", f"그림 읽기 멈춤({kind})" in o1, o1[-400:])
        ok(f"[{m}] 그림 읽기 2회째 = 알림 없이 멈춤", "알림 끝남" in o2 and "그림 읽기 멈춤(" not in o2, o2[-400:])
        ok(f"[{m}] 끊김을 안 뒤엔 claude -p 를 다시 안 부름", ncalls() - n0 <= (1 if m == "callfail" else 0), f"-p {ncalls() - n0}번")
        c3, o3 = py(auto)
        c4, o4 = py(auto)
        ok(f"[{m}] 자동 판정 = 멈춤 · 대기열 줄 0(폰 «수집 막힘» 되풀이 없음)", "stopped" in o3 and "stopped" in o4 and qlines() == q0, f"대기열 +{qlines() - q0} · {o3[-200:]}")
        c5, o5 = py(manual)
        ok(f"[{m}] 수동 판정 단추 = 까닭을 보이고 멈춤", "수동 멈춤" in o5, o5[-300:])
        c6, o6 = py(rc_code)
        ok(f"[{m}] 폰 RC 켜기 = 409 로 막음", "RC 막음 409" in o6, o6[-300:])
        ok(f"[{m}] 알림 = 끊김 한 번에 한 번", alerts() == 1, f"알림 {alerts()}번 · " + (open(slog, encoding='utf-8').read()[-300:] if os.path.exists(slog) else ""))
        ok(f"[{m}] 상태 파일 = off · {kind}", st().get("state") == "off" and st().get("kind") == kind, st())

    # 사용량 한도(5시간 창 100%)는 해지가 아니다 — error rate_limit 있음 / 없음(글만)
    for m in ("ratelimit", "ratelimit-noerr"):
        print(f"\n[{m}] 흉내 — 기대 = 사용량 한도(해지 아님)", flush=True)
        mode(m)
        for p in (state, slog):
            if os.path.exists(p):
                os.remove(p)
        c1, o1 = ingest()
        ok(f"[{m}] 그림 읽기 = 사용량 한도로 멈춤(해지 아님)", "그림 읽기 멈춤(사용량 한도)" in o1 and claude_bin.LAPSED not in o1, o1[-300:])
        ok(f"[{m}] 상태 파일 off 아님 · 알림 0", st().get("state") != "off" and alerts() == 0, json.dumps(st(), ensure_ascii=False) + f" 알림 {alerts()}")

    # 그대로 도는 것(LLM 0) — 흉내가 걸린 채로
    print("\n[구독 없이 도는 것]", flush=True)
    mode("lapsed")
    n0 = ncalls("")
    c, o = py("import runpy; sys.argv=['alarms.py','--days','3']; runpy.run_path('3_시스템/alarms.py', run_name='__main__')")
    ok("알림 목록(alarms.py) 돎", c == 0, o[-200:])
    c, o = py("import runpy; sys.argv=['schedule.py','week','7']; runpy.run_path('3_시스템/schedule.py', run_name='__main__')")
    ok("일정(schedule.py week) 돎", c == 0, o[-200:])
    r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(SYS, "search.py"), "--q", "장학", "--k", "3"], cwd=VAULT, env=env, capture_output=True, timeout=180)
    ok("찾기(search.py · 진짜 볼트 읽기만) 돎", r.returncode == 0 and len(r.stdout) > 50, r.stdout.decode("utf-8", "replace")[-200:])
    c, o = py("import runpy; sys.argv=['ingest.py','1_수집/시험/그림.png','--force']; runpy.run_path('3_시스템/ingest.py', run_name='__main__')", 300)
    ok("원본 색인(OCR · --vision 없이) 돎", c == 0 and "그림 읽기" not in o, o[-200:])
    ok("위 넷이 claude 를 안 부름", ncalls("") == n0, f"{ncalls('') - n0}번")

    # 흉내 걷음 — 다시 구독하면 저절로 풀림
    print("\n[흉내 걷음]", flush=True)
    mode("lapsed")
    py("import claude_bin; claude_bin.check()")          # 걷기 전 = 끊김(앞 칸 순서와 상관없이)
    ok("걷기 전 상태 파일 = off", st().get("state") == "off", st())
    mode("real")
    c, o = py("import claude_bin, json; print(json.dumps(claude_bin.check(), ensure_ascii=False))")
    ok("auth status 가 구독이면 상태 파일이 저절로 ok", '"ok": true' in o and st().get("state") == "ok", o[-200:] + " " + json.dumps(st(), ensure_ascii=False))
    ok("풀림이 장부에", os.path.exists(slog) and "풀림" in open(slog, encoding="utf-8").read(), "")
    # 호출로 잡은 끊김(callfail) — 기다림이 지나면 한 번 다시 부르고, 되면 풀림
    mode("callfail")
    py("import claude_bin; claude_bin.note_call(False, 'oauth_org_not_allowed', 'x')")
    s = st()
    s["until"] = 0
    json.dump(s, open(state, "w", encoding="utf-8"))
    c, o = py("import claude_bin; print('check', claude_bin.check()['ok'])")
    ok("호출 끊김은 기다림이 지나면 다시 부를 수 있음", "check True" in o, o[-200:])

    if REAL:
        print("\n[진짜 claude — 오탐 0]", flush=True)
        renv = clean_env(INGEST_VISION_MODEL="haiku")
        for p in (state, slog):
            if os.path.exists(p):
                os.remove(p)
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", "import sys; sys.path.insert(0, r'%s'); import claude_bin, json; print(json.dumps(claude_bin.check(), ensure_ascii=False))" % ts],
                           cwd=tv, env=renv, capture_output=True, timeout=120)
        o = r.stdout.decode("utf-8", "replace")
        ok("진짜 구독 = check ok(auth status)", '"ok": true' in o, o + r.stderr.decode("utf-8", "replace")[-200:])
        code = ("import sys; sys.path.insert(0, r'%s'); import ingest_vision as iv\n"
                "t, u, e = iv._run([{'type': 'text', 'text': '1+1=? 숫자만'}], system='Answer with digits only.')\n"
                "print('답', repr(t), '오류', repr(e), '입력', u.get('in'), '출력', u.get('out'))") % ts
        r = subprocess.run([sys.executable, "-X", "utf8", "-c", code], cwd=tv, env=renv, capture_output=True, timeout=180)
        o = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
        ok("진짜 호출 1번 = 끊김으로 안 읽힘", "답 '2'" in o and st().get("state") != "off", o[-300:])
        ok("진짜 호출 뒤 알림 0", alerts() == 0, alerts())

    print("\n| 잰 것 | 결과 | 값 |\n|---|---|---|")
    for n, v, g in rows:
        print(f"| {n} | {v} | {g.replace('|', '/').replace(chr(10), ' ')[:120]} |")
    print(f"\n합계 {len(rows) - len(fails)}/{len(rows)} 통과" + (f" · 실패 {fails}" if fails else ""))
    shutil.rmtree(root, ignore_errors=True)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
