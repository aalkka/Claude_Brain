#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check.py negative/positive 매트릭스 (P3② DoD).

  py test_check.py            → 전 케이스 실행. 실패 있으면 exit 1.

각 케이스 = 픽스처 모듈을 실제로 생성 → check() 판정이 기대와 일치하는지 대조 → 삭제.
"산출물 존재 ≠ 게이트 통과" — 가드레일이 '실제로 막는지'를 픽스처로
증명한다. 정리는 finally 보장(잔재 0).

이 파일의 볼트 경로 문자열은 전부 **픽스처 데이터**(실제 쓰기 아님) → 스캔 제외: mf:allow-path-file
"""
import sys, os, json, shutil, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check as C  # noqa: E402

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

SKILLS = C.SKILLS_DIR
REF = os.path.join(C.VAULT, "3_시스템", "_ref")
made_dirs = []


def w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def mk(name, module=None, deps=None, skills=("demo",), hooks=None, scripts=None):
    """픽스처 모듈 생성. module=None이면 module.json 없음(부재 케이스)."""
    d = os.path.join(SKILLS, name)
    made_dirs.append(d)
    pj = {"name": name, "description": "fixture", "version": "0.1.0", "author": {"name": "test"}}
    if deps:
        pj["dependencies"] = [{"name": x, "version": "~0.1"} for x in deps]
    w(os.path.join(d, ".claude-plugin", "plugin.json"), json.dumps(pj, ensure_ascii=False, indent=2))
    if module is not None:
        w(os.path.join(d, "module.json"), json.dumps(module, ensure_ascii=False, indent=2))
    for s in skills or []:
        w(os.path.join(d, "skills", s, "SKILL.md"), f"---\nname: {s}\ndescription: fixture\n---\n# {s}\n")
    if hooks:
        w(os.path.join(d, "hooks", "hooks.json"), json.dumps(hooks, ensure_ascii=False, indent=2))
    for fn, body in (scripts or {}).items():
        w(os.path.join(d, "scripts", fn), body)
    return d


def mod(touches, surfaces=None, writes_config=None, extra=None):
    m = {
        "schema": 1,
        "touches": touches,
        "forbids": ["1_수집/**"],
        "writes_config": writes_config or [],
        "invocation": "model",
        "surfaces": surfaces if surfaces is not None else {"skills": ["demo"], "hooks": [], "mcp": []},
    }
    m.update(extra or {})
    return m


def build():
    """전 픽스처 생성(순환·겹침은 쌍이 동시에 있어야 발화)."""
    mk("mf-t-ok", mod(["3_시스템/_index/mf-t-ok/"]))
    mk("_mf-t-under", mod(["3_시스템/_index/mf-t-under/"]))
    mk("mf-t-collect", mod(["1_수집/inbox/"]))
    mk("mf-t-hook", mod(["3_시스템/_index/mf-t-hook/"]),
       hooks={"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}})
    mk("mf-t-dupnote", mod(["3_시스템/_index/mf-t-dupnote/"]))
    mk("mf-t-ov-a", mod(["3_시스템/_index/mf-t-shared/"]))
    mk("mf-t-ov-b", mod(["3_시스템/_index/mf-t-shared/"]))
    mk("mf-t-nest-a", mod(["3_시스템/_index/mf-t-nest/"]))
    mk("mf-t-nest-b", mod(["3_시스템/_index/mf-t-nest/deep/"]))
    mk("mf-t-cyc-a", mod(["3_시스템/_index/mf-t-cyc-a/"]), deps=["mf-t-cyc-b"])
    mk("mf-t-cyc-b", mod(["3_시스템/_index/mf-t-cyc-b/"]), deps=["mf-t-cyc-a"])
    mk("mf-t-depmiss", mod(["3_시스템/_index/mf-t-depmiss/"]), deps=["mf-t-does-not-exist"])
    mk("mf-t-badscript", mod(["3_시스템/_index/mf-t-badscript/"]),
       scripts={"x.py": 'SRC = "1_수집/_inbox/note.md"\n'})
    mk("mf-t-outscript", mod(["3_시스템/_index/mf-t-outscript/"]),
       scripts={"x.py": 'DST = "2_지식/notes/aaa.md"\n'})
    mk("mf-t-drift", mod(["3_시스템/_index/mf-t-drift/"], surfaces={"skills": [], "hooks": [], "mcp": []}),
       skills=("demo", "extra"))
    mk("mf-t-nomodjson", None)
    mk("mf-t-config", mod(["3_시스템/_index/mf-t-config/"], writes_config=["embed_model"]))
    # 산출물 폴더 규약: notes/ 금지 · 타모듈 폴더 침범 금지 · 자기 폴더는 정상(infos)
    mk("mf-t-notes", mod(["2_지식/notes/mf-t-notes/"]))
    mk("mf-t-othermod", mod(["2_지식/modules/mf-t-nobody/"]))  # 남의 폴더(실모듈 무간섭)
    mk("mf-t-goodout", mod(["2_지식/modules/mf-t-goodout/", "3_시스템/_index/mf-t-goodout/"]))
    mk("mf-t-corefile", mod(["3_시스템/_index/mf-t-corefile/"]),
       scripts={"x.py": 'CFG = os.path.join(V, "3_시스템/config.json")\n'})
    # forward-compat: 모르는 키·미래 스키마는 검사기를 깨지 않는다(P4 확장 선반영 안전)
    mk("mf-t-future", mod(["3_시스템/_index/mf-t-future/"],
                          extra={"schema": 99, "runtime_ports": [8080], "router": {"expose": False}}))
    # 노트 basename 중복(Stop훅 스코프 = 3_시스템/_ref/** 사용 — MOC 요구 대상 아님)
    for sub in ("mf-t-dupA", "mf-t-dupB"):
        p = os.path.join(REF, sub)
        made_dirs.append(p)
        w(os.path.join(p, "외부뇌-mf-t-dupnote-모듈.md"),
          "---\ntype: reference\ntitle: fixture\nstatus: active\n---\nfixture\n")


# (모듈, ok기대, 기대키워드, 어느 버킷)
CASES = [
    ("mf-t-ok",        True,  None,                "-"),
    ("_mf-t-under",    False, "'_' 접두",           "blocks"),
    ("mf-t-collect",   False, "I3 위반",            "blocks"),
    ("mf-t-hook",      False, "I2 위반",            "blocks"),
    ("mf-t-dupnote",   False, "basename 중복",      "blocks"),
    ("mf-t-ov-a",      False, "touches 동일경로",    "blocks"),
    ("mf-t-cyc-a",     False, "deps 순환",          "blocks"),
    ("mf-t-depmiss",   False, "미존재",             "blocks"),
    ("mf-t-badscript", False, "스크립트가 1_수집",   "blocks"),
    ("mf-t-config",    False, "코어 config 키 선언", "blocks"),
    ("mf-t-corefile",  False, "I1 위반",            "blocks"),
    ("mf-t-notes",     False, "산출물 위치 위반",     "blocks"),
    ("mf-t-othermod",  False, "산출물 경계 위반",     "blocks"),
    ("mf-t-goodout",   True,  "산출물 폴더",         "infos"),
    ("mf-t-nest-b",    True,  "touches 포함관계",    "warns"),
    ("mf-t-outscript", True,  "touches 밖",         "warns"),
    ("mf-t-drift",     True,  "surfaces.skills 드리프트", "warns"),
    ("mf-t-nomodjson", True,  "module.json 없음",   "warns"),
    ("mf-t-future",    True,  "schema 99",          "warns"),
    ("mf-t-does-not-exist", False, "없음",          "blocks"),
]


def run():
    build()
    mods, core = C.scan_all()
    rows, fails = [], 0
    for name, want_ok, kw, bucket in CASES:
        r = C.check(name, mods, core)
        ok_match = (r["ok"] == want_ok)
        kw_match = True
        if kw:
            kw_match = any(kw in x for x in r.get(bucket, []))
        passed = ok_match and kw_match
        fails += 0 if passed else 1
        rows.append((name, "PASS" if passed else "FAIL", r["ok"], want_ok, kw or "-",
                     "" if passed else json.dumps(r, ensure_ascii=False)[:220]))

    # exit code 계약: 정상=0 · block=1
    env = dict(os.environ)
    for name, want_code in (("mf-t-ok", 0), ("mf-t-collect", 1)):
        p = subprocess.run([sys.executable, os.path.join(C.HERE, "check.py"), name, "--no-registry"],
                           capture_output=True, env=env)
        passed = (p.returncode == want_code)
        fails += 0 if passed else 1
        rows.append((f"exit:{name}", "PASS" if passed else "FAIL", p.returncode, want_code, "exit code", ""))

    # 실모듈 회귀(정상 통과 유지)
    for name in ("module-forge",):
        if name in mods:
            r = C.check(name, mods, core)
            passed = r["ok"]
            fails += 0 if passed else 1
            rows.append((f"real:{name}", "PASS" if passed else "FAIL", r["ok"], True, "회귀",
                         "" if passed else json.dumps(r["blocks"], ensure_ascii=False)[:220]))

    print(f"{'케이스':<22} {'결과':<6} {'ok':<6} {'기대':<6} 검증키워드")
    print("-" * 92)
    for name, res, got, want, kw, detail in rows:
        print(f"{name:<22} {res:<6} {str(got):<6} {str(want):<6} {kw}")
        if detail:
            print(f"    ↳ {detail}")
    print("-" * 92)
    print(f"{len(rows) - fails}/{len(rows)} PASS" + ("" if fails == 0 else f"  ({fails} FAIL)"))
    return 1 if fails else 0


def cleanup():
    for d in made_dirs:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    try:
        code = run()
    finally:
        cleanup()
    sys.exit(code)
