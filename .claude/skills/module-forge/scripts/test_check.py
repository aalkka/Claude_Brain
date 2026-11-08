#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check.py negative/positive 매트릭스 (P3② DoD).

  py test_check.py            → 전 케이스 실행. 실패 있으면 exit 1.

각 케이스 = 픽스처 모듈을 실제로 생성 → check() 판정이 기대와 일치하는지 대조 → 삭제.
"산출물 존재 ≠ 게이트 통과"([[완료판단-산출물존재vs게이트통과-패턴]]) — 가드레일이
'실제로 막는지'를 픽스처로 증명한다. 정리는 finally 보장(잔재 0).

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
       scripts={"x.py": 'SRC = "1_수집/받은함/note.md"\n'})
    mk("mf-t-outscript", mod(["3_시스템/_index/mf-t-outscript/"]),
       scripts={"x.py": 'DST = "2_지식/notes/aaa.md"\n'})
    # reads(11-07) — 읽기만 하는 남의 자리. 같은 대본이 reads 없으면 경고(none) · 있으면 조용(reads · reads 가 touches 의 위 폴더여도)
    #   touches 안 reads = 중복 경고 · 1_수집·코어파일(그것을 품은 넓은 폴더 포함)은 reads 로도 못 풂 · 목록 아님 = 막힘
    src = 'IDX = "3_시스템/_index/{0}/"\nNOTE = "2_지식/mf-t-reads/설정.md"\n'
    mk("mf-t-reads-none", mod(["3_시스템/_index/mf-t-reads-none/draft/"]), scripts={"x.py": src.format("mf-t-reads-none")})
    mk("mf-t-reads", mod(["3_시스템/_index/mf-t-reads/draft/"],
                         extra={"reads": ["3_시스템/_index/mf-t-reads/", "2_지식/mf-t-reads/설정.md"]}),
       scripts={"x.py": src.format("mf-t-reads")})
    mk("mf-t-reads-dup", mod(["3_시스템/_index/mf-t-reads-dup/"], extra={"reads": ["3_시스템/_index/mf-t-reads-dup/a.json"]}))
    mk("mf-t-reads-collect", mod(["3_시스템/_index/mf-t-reads-collect/"], extra={"reads": ["1_수집/받은함/"]}))
    mk("mf-t-reads-core", mod(["3_시스템/_index/mf-t-reads-core/"], extra={"reads": ["3_시스템/config.json"]}))
    mk("mf-t-reads-wide", mod(["3_시스템/_index/mf-t-reads-wide/"], extra={"reads": ["3_시스템/"]}))
    mk("mf-t-reads-type", mod(["3_시스템/_index/mf-t-reads-type/"], extra={"reads": "3_시스템/_index/x/"}))
    mk("mf-t-drift", mod(["3_시스템/_index/mf-t-drift/"], surfaces={"skills": [], "hooks": [], "mcp": []}),
       skills=("demo", "extra"))
    mk("mf-t-nomodjson", None)
    mk("mf-t-config", mod(["3_시스템/_index/mf-t-config/"], writes_config=["embed_model"]))
    # 산출물 폴더 규약: notes/ 금지 · 타모듈 폴더 침범 금지 · 자기 폴더는 정상(infos)
    mk("mf-t-notes", mod([C.NOTE_AREAS[0] + "/mf-t-notes/"]))  # 옛 2_지식/notes 는 R9 로 사라졌다 — 역할에서 묻는다
    mk("mf-t-othermod", mod(["2_지식/modules/mf-t-nobody/"]))  # 남의 폴더(실모듈 무간섭)
    mk("mf-t-goodout", mod(["2_지식/modules/mf-t-goodout/", "3_시스템/_index/mf-t-goodout/"]))
    mk("mf-t-corefile", mod(["3_시스템/_index/mf-t-corefile/"]),
       scripts={"x.py": 'CFG = os.path.join(V, "3_시스템/config.json")\n'})
    # forward-compat: 모르는 키·미래 스키마는 검사기를 깨지 않는다(P4 확장 선반영 안전)
    mk("mf-t-future", mod(["3_시스템/_index/mf-t-future/"],
                          extra={"schema": 99, "runtime_ports": [8080], "router": {"expose": False}}))
    # ⑪ contributes 행위·건강(ADR-019 — 코어 brain.py 계약)
    def act(m, **k):
        a = {"id": f"{m}.go", "name": "시험", "risk": "read", "run": ["{py}", f".claude/skills/{m}/scripts/a.py"]}
        a.update(k)
        return a

    def con(m, c, scripts=True):
        mk(m, mod([f"3_시스템/_index/{m}/"], extra={"contributes": c}),
           scripts={"a.py": 'print("ok")\n'} if scripts else None)

    con("mf-t-act-ok", {"actions": [act("mf-t-act-ok", args=[{"name": "q"}],
                                        run=["{py}", ".claude/skills/mf-t-act-ok/scripts/a.py", "{q}", "{by}"])],
                        "doctor": ["{py}", ".claude/skills/mf-t-act-ok/scripts/a.py"]})
    con("mf-t-act-prefix", {"actions": [act("mf-t-act-prefix", id="go")]})
    con("mf-t-act-dup", {"actions": [act("mf-t-act-dup"), act("mf-t-act-dup")]})
    con("mf-t-act-risk", {"actions": [act("mf-t-act-risk", risk="delete")]})
    con("mf-t-act-builtin", {"actions": [act("mf-t-act-builtin", builtin="inbox")]})
    con("mf-t-act-noscript", {"actions": [act("mf-t-act-noscript")]}, scripts=False)
    con("mf-t-act-ph", {"actions": [act("mf-t-act-ph", run=["{py}", ".claude/skills/mf-t-act-ph/scripts/a.py", "{q}"])]})
    con("mf-t-act-out", {"actions": [act("mf-t-act-out", run=["{py}", "3_시스템/search.py"])]})
    con("mf-t-act-doc", {"doctor": "py a.py"})
    con("mf-t-act-later", {"menus": [{"where": "file"}], "settings": {}})
    mk("mf-t-act-type", mod(["3_시스템/_index/mf-t-act-type/"], extra={"contributes": ["search"]}))
    # ⑫ 튜토리얼·설명서(ADR-035)
    def doc(m, tutorial=None, manual=None, files=None):
        c = {k: v for k, v in (("tutorial", tutorial), ("manual", manual)) if v is not None}
        mk(m, mod([f"3_시스템/_index/{m}/"], extra={"contributes": c}))
        for rel, body in (files or {}).items():
            w(os.path.join(SKILLS, m, rel), body)

    chap = ("---\n형식: 2\n장: 1\n이름: 시험\n시간: 1분\n없애는 일: 시험\n해낼 일: 홈을 혼자 연다\n연습: 없음\n---\n"
            "## 홈 열기\n말: 이 단추로 홈을 여세요.\n가리키기: 리본 \"외부뇌 홈\"\n기다리기: 보임 홈\n풀이: 누르기\n\n"
            "## 확인\n말: 대화창을 여세요.\n가리키기: 리본 \"외부뇌 대화\"\n기다리기: 보임 대화창\n풀이: 누르기\n")
    v1 = "---\n장: 1\n이름: 시험\n---\n## 하나\n말: 보세요.\n기다리기: 다음\n"
    man = "---\ntitle: 시험\n---\n# 시험\n"
    ch = lambda m, name=None: [{"file": f".claude/skills/{m}/manual/{name or '설명서-' + m}.md", "name": "시험", "gist": "시험"}]
    doc("mf-t-doc-ok", ".claude/skills/mf-t-doc-ok/tutorial", ch("mf-t-doc-ok"),
        {"tutorial/1-시험.md": chap, "tutorial/연습 자료.md": "# 대본 아님\n", "manual/설명서-mf-t-doc-ok.md": man})
    doc("mf-t-doc-out", "3_시스템/tutorial")
    doc("mf-t-doc-empty", ".claude/skills/mf-t-doc-empty/tutorial", None, {"tutorial/연습 자료.md": "# 대본 아님\n"})
    doc("mf-t-doc-nosay", ".claude/skills/mf-t-doc-nosay/tutorial", None, {"tutorial/1.md": "---\n장: 1\n이름: 시험\n---\n## 하나\n기다리기: 다음\n"})
    doc("mf-t-doc-prac", ".claude/skills/mf-t-doc-prac/tutorial", None, {"tutorial/1.md": "---\n장: 1\n이름: 시험\n연습 파일: 없음.md\n---\n## 하나\n말: 보세요.\n"})
    # 형식 v2 — 3_시스템/tutorial_lint.py 와 같은 함수(합격선 미달 = block · v1 도 미달 «형식 v1» = block · 11-08)
    doc("mf-t-doc-v1", ".claude/skills/mf-t-doc-v1/tutorial", None, {"tutorial/1.md": v1})
    v2 = "---\n형식: 2\n장: 1\n이름: 시험\n시간: 1분\n없애는 일: 시험\n해낼 일: 홈을 혼자 연다\n연습: 없음\n---\n"
    hit = "가리키기: 리본 \"외부뇌 홈\"\n기다리기: 보임 홈\n풀이: 누르기\n"
    chat_hit = "가리키기: 리본 \"외부뇌 대화\"\n기다리기: 보임 대화창\n풀이: 누르기\n"
    doc("mf-t-doc-v2ok", ".claude/skills/mf-t-doc-v2ok/tutorial", None,
        {"tutorial/1.md": v2 + "## 홈 열기\n말: 이 단추로 홈을 여세요.\n" + hit + "\n## 확인\n말: 대화창을 여세요.\n" + chat_hit})
    # 확인이 앞 단계를 그대로 되풀이(같은 대상 · 사용자 11-09) = 막음
    doc("mf-t-doc-repeat", ".claude/skills/mf-t-doc-repeat/tutorial", None,
        {"tutorial/1.md": v2 + "## 홈 열기\n말: 이 단추로 홈을 여세요.\n" + hit + "\n## 확인\n말: 홈을 다시 여세요.\n보여 주기: 창닫기\n" + hit})
    doc("mf-t-doc-v2bad", ".claude/skills/mf-t-doc-v2bad/tutorial", None,
        {"tutorial/1.md": v2 + "## 하나\n말: 보세요.\n기다리기: 다음\n\n## 확인\n말: 혼자 해 보세요.\n" + hit})
    doc("mf-t-doc-file", None, ch("mf-t-doc-file"))
    doc("mf-t-doc-name", None, ch("mf-t-doc-name", "아무개"), {"manual/아무개.md": man})
    doc("mf-t-doc-nofm", None, ch("mf-t-doc-nofm"), {"manual/설명서-mf-t-doc-nofm.md": "# 머리 없음\n"})
    doc("mf-t-doc-dup", None, ch("mf-t-doc-dup"), {"manual/설명서-mf-t-doc-dup.md": man})
    doc("mf-t-doc-link", None, ch("mf-t-doc-link"), {"manual/설명서-mf-t-doc-link.md": man})
    p = os.path.join(REF, "mf-t-docdup")
    made_dirs.append(p)
    w(os.path.join(p, "설명서-mf-t-doc-dup.md"), "---\ntype: reference\ntitle: fixture\nstatus: active\n---\nfixture\n")
    # 코어 글이 모듈 장으로 링크 — 진짜 글을 고치지 않고 검사 함수만 바꿔 끼운다
    orig = C.core_doc_links
    C.core_doc_links = lambda: (lambda d: (d["links"].setdefault("설명서-mf-t-doc-link", []).append("시험 코어 글"), d)[1])(orig())
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
    ("mf-t-outscript", True,  "touches·reads 밖",   "warns"),
    ("mf-t-reads-none",    True,  "touches·reads 밖",   "warns"),
    ("mf-t-reads",         True,  "touches·reads 밖",   "!warns"),   # ! = 그 말이 없어야 통과
    ("mf-t-reads",         True,  "touches 안",         "!warns"),
    ("mf-t-reads-dup",     True,  "touches 안",         "warns"),
    ("mf-t-reads-collect", False, "reads 에 1_수집",     "blocks"),
    ("mf-t-reads-core",    False, "코어파일 '3_시스템/config.json'", "blocks"),
    ("mf-t-reads-wide",    False, "코어파일",            "blocks"),
    ("mf-t-reads-type",    False, "reads 는 경로 글자 목록", "blocks"),
    ("mf-t-drift",     True,  "surfaces.skills 드리프트", "warns"),
    ("mf-t-nomodjson", True,  "module.json 없음",   "warns"),
    ("mf-t-future",    True,  "schema 99",          "warns"),
    ("mf-t-does-not-exist", False, "없음",          "blocks"),
    ("mf-t-act-ok",       True,  "행위 1개",          "infos"),
    ("mf-t-act-prefix",   False, "로 시작해야",        "blocks"),
    ("mf-t-act-dup",      False, "행위 id 겹침",       "blocks"),
    ("mf-t-act-risk",     False, "risk 'delete'",     "blocks"),
    ("mf-t-act-builtin",  False, "코어 전용",          "blocks"),
    ("mf-t-act-noscript", False, "대본 없음",          "blocks"),
    ("mf-t-act-ph",       False, "자리표 '{q}'",       "blocks"),
    ("mf-t-act-out",      True,  "모듈 밖 대본",       "warns"),
    ("mf-t-act-doc",      False, "contributes.doctor", "blocks"),
    ("mf-t-act-later",    True,  "아직 읽는 곳 없음",   "infos"),
    ("mf-t-act-type",     False, "contributes 는 객체", "blocks"),
    ("mf-t-doc-ok",       True,  "튜토리얼 1장 · 설명서 1장", "infos"),
    ("mf-t-doc-out",      False, "모듈 안의 폴더가 아님", "blocks"),
    ("mf-t-doc-empty",    False, "대본 없음",          "blocks"),
    ("mf-t-doc-nosay",    False, "«말:» 없음",         "blocks"),
    ("mf-t-doc-prac",     False, "연습 파일 없음",      "blocks"),
    ("mf-t-doc-v1",       False, "형식 v1",            "blocks"),
    ("mf-t-doc-v2ok",     True,  "튜토리얼 1장",        "infos"),
    ("mf-t-doc-v2bad",    False, "해 보기 아님",        "blocks"),
    ("mf-t-doc-repeat",   False, "그대로 되풀이",       "blocks"),
    ("mf-t-doc-v1",       False, "튜토리얼 만들기",     "infos"),    # ⑫ 안내 줄 = SKILL «튜토리얼 만들기»
    ("mf-t-doc-ok",       True,  "고치는 순서",         "!infos"),
    ("mf-t-doc-v2bad",    False, "튜토리얼 만들기",     "infos"),
    ("mf-t-doc-v2ok",     True,  "고치는 순서",         "!infos"),   # 통과한 장에는 안내 줄 없음
    ("mf-t-doc-empty",    False, "쓰는 순서",           "blocks"),
    ("mf-t-doc-file",     False, "모듈 안의 파일이 아님", "blocks"),
    ("mf-t-doc-name",     False, "로 시작해야 한다",    "blocks"),
    ("mf-t-doc-nofm",     False, "프론트매터 없음",     "blocks"),
    ("mf-t-doc-dup",      False, "설명서 이름 겹침",    "blocks"),
    ("mf-t-doc-link",     False, "모듈을 끄면 깨진다",  "blocks"),
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
            hit = any(kw in x for x in r.get(bucket.lstrip("!"), []))
            kw_match = not hit if bucket.startswith("!") else hit
        passed = ok_match and kw_match
        fails += 0 if passed else 1
        rows.append((name, "PASS" if passed else "FAIL", r["ok"], want_ok,
                     (f"없음 «{kw}»" if bucket.startswith("!") else kw) if kw else "-",
                     "" if passed else json.dumps(r, ensure_ascii=False)[:220]))

    # exit code 계약: 정상=0 · block=1
    env = dict(os.environ)
    for name, want_code in (("mf-t-ok", 0), ("mf-t-collect", 1)):
        p = subprocess.run([sys.executable, os.path.join(C.HERE, "check.py"), name, "--no-registry"],
                           capture_output=True, env=env)
        passed = (p.returncode == want_code)
        fails += 0 if passed else 1
        rows.append((f"exit:{name}", "PASS" if passed else "FAIL", p.returncode, want_code, "exit code", ""))

    # 실모듈 회귀(정상 통과 유지) — collect_desk 는 수집 본체 통합 4단계(11-08)에 모듈이 아니게 됨(검사 = 3_시스템/_eval/collect_core_check.py)
    for name in ("module-forge", "study-helper", "dist-sync", "interactive_roadmap"):
        if name in mods:
            r = C.check(name, mods, core)
            passed = r["ok"]
            fails += 0 if passed else 1
            rows.append((f"real:{name}", "PASS" if passed else "FAIL", r["ok"], True, "회귀",
                         "" if passed else json.dumps(r["blocks"], ensure_ascii=False)[:220]))

    # ⑫ 안내 줄이 가리키는 절·본보기가 있다 — 절 이름을 바꾸거나 본보기를 옮기면 안내가 허공을 가리킨다
    rel, _, title = C.TUTORIAL_HOWTO.partition(" «")
    sk = os.path.join(C.VAULT, *rel.split("/"))
    skill = open(sk, encoding="utf-8").read() if os.path.isfile(sk) else ""
    docs = [(f"doc:절 {title.rstrip('»')}", f"## {title.rstrip('»')}" in skill)]
    for p in ("3_시스템/tutorial/8-수집.md", ".claude/skills/module-forge/tutorial/1-모듈-점검.md", ".claude/skills/dist-sync/tutorial/1-업데이트.md"):  # SKILL «본보기» 줄(배포판에 실리는 장만 · bigboss 는 안 실음 11-09)
        docs.append((f"doc:본보기 {p.split('/')[-1]}", f"`{p}`" in skill and os.path.isfile(os.path.join(C.VAULT, *p.split("/")))))
    for label, passed in docs:
        fails += 0 if passed else 1
        rows.append((label, "PASS" if passed else "FAIL", passed, True, "⑫ 안내 줄 대상", ""))

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
