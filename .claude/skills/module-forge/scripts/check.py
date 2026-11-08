#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""module-forge 정적 충돌검사 (P3② 완결판).

  py check.py <모듈명>                  → {ok, blocks, warns, infos} JSON. block 있으면 exit 1.
  py check.py --all                     → 전 모듈 일괄(하나라도 block이면 exit 1)
  py check.py <모듈명> --sync-surfaces  → surfaces 선언을 실제 스캔값으로 갱신 후 재검사
  py check.py <모듈명> --no-registry    → 레지스트리 재생성 생략(테스트용)

block: ①'_'접두(로더 스킵) ②모듈명↔코어스킬 동명 ③노트 basename 중복 ④1_수집 침범(I3)
       ⑤예약훅(I2) ⑥모듈간 touches 동일경로 ⑦deps 순환·미존재 ⑧코어 config 키 선언(I3)
       ⑨스크립트의 1_수집 접근·코어파일 참조(I1) · reads 선언의 1_수집·코어파일 ⑩산출물 폴더 규약(notes/ 금지·타모듈 침범)
       ⑪contributes 행위·건강 선언(id 접두 '<모듈>.'·겹침·risk·builtin·대본 없음·모르는 자리표 — ADR-019)
       ⑫contributes 튜토리얼·설명서 선언(모듈 밖·대본 꼴·설명서 이름 규칙·겹침·코어 글이 모듈 장으로 링크 — ADR-035)
         · 대본은 3_시스템/tutorial_lint.py 의 check_folder 로 잰다(코어와 같은 함수) — 합격선 미달이 block(형식 v1 도 미달 한 건 ·
           13장 모두 v2 로 옮김 11-08) · v1 장은 엔진이 못 읽는 꼴(legacy)도 함께 알린다
         · 미달·대본 없음이면 안내 줄(info·block)이 쓰는 순서 = SKILL «튜토리얼 만들기»(TUTORIAL_HOWTO)를 가리킨다
warn : module.json 부재 · surfaces 드리프트 · touches 포함관계(인접)
       · 스크립트 하드코딩 경로가 touches·reads 밖 · reads 가 touches 안(중복) · 무관 basename 중복 · schema 버전 상회
       · 행위·doctor 가 모듈 밖 대본을 부름 · 행위 name 없음
infos: 네임스페이스 열거(네이티브 `/<모듈>:<스킬>`가 이미 충돌차단 → 정보만)

forward-compat: module.json의 **모르는 키는 무시**한다(P4 확장 필드 선반영 안전).
       스키마가 바뀌면 `schema` 값을 올린다 → 구버전 check.py는 warn으로 자백.
       `reads`(11-07)는 더한 키라 schema 1 그대로 — 구버전은 무시해 «touches 밖» 경고를 낼 뿐(더 엄격 · 거짓 통과 없음).

한계(정직): 런타임 충돌(훅 실행순서·MCP 포트·bin PATH) 미검출 — P4 연기.
       SKILL.md 프로즈를 Claude가 읽고 쓰는 경로는 정적으로 귀속 불가 →
       touches 준수 검증은 **모듈 스크립트(결정론 코드)** 범위만.

부산물: 3_시스템/_index/modules.json 레지스트리 재생성(gitignore=파생·재생성).
진실원본 = [[외부뇌-개발지원-모듈]] §A4-3 · P3②. Stop훅 basename 로직 재활용.
"""
import sys, os, json, glob, re

# stdout/stderr UTF-8 강제: Windows 콘솔 기본 cp949 → 한글 reason 출력 시 크래시 방지
# (search.py와 동일 패턴 — incident-2026-07-04-search-stdout-cp949 계열).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# check.py = .claude/skills/module-forge/scripts/check.py → 4단계 위가 볼트 루트
HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
SKILLS_DIR = os.path.join(VAULT, ".claude", "skills")
REGISTRY = os.path.join(VAULT, "3_시스템", "_index", "modules.json")
RESERVED_HOOKS = {"Stop", "SessionStart", "SessionEnd"}
# 스크립트 안의 볼트 경로 리터럴 추출용(따옴표로 감싼 볼트 루트 시작 경로).
PATH_LITERAL = re.compile(r'["\']((?:1_수집|2_지식|3_시스템)[/\\][^"\']*)["\']')
SCRIPT_EXTS = ("*.py", "*.ps1", "*.sh", "*.js", "*.ts")
COMMENT_START = ("#", "//", "<#", "*", '"""', "'''")
# I1 코어 무수정 — 모듈 스크립트가 이 경로를 참조하면 코어 수정 유발.
CORE_PATHS = (                                                    # mf:allow-path
    "3_시스템/config.json", "3_시스템/hooks", "3_시스템/search.py",  # mf:allow-path
    ".claude/settings.json", "CLAUDE.md", ".gitignore",            # mf:allow-path
)
MODULE_SCHEMA = 1  # module.json 스키마 버전(미래 필드 추가 시 증가 — forward-compat 앵커)
# 산출물 폴더 규약(2026-07-27): 모듈 지식산출물은 modules/<모듈명>/, notes/는 코어 지식 전용.
MODULES_ROOT = "2_지식/modules"  # mf:allow-path
sys.path.insert(0, os.path.join(VAULT, "3_시스템"))
import roles  # noqa: E402 — 자리는 역할로(볼트 개혁 R6)
import tutorial_lint  # noqa: E402 — 튜토리얼 대본 규칙은 한 곳(코어 정적 검사와 같은 함수)
NOTE_AREAS = roles.group("note_areas")  # 코어 지식 노트 자리 전부(R9 뒤 노트·학교·프로젝트·생활)
# 오탐 억제(정직히 명시): 리터럴 스캔은 '언급'과 '접근'을 구분 못 한다 →
#   ⓐ 주석 줄 제외 ⓑ 글로브(*) 포함 = 선언/패턴이지 대상 아님 ⓒ 명시 escape.
ALLOW_LINE = "mf:allow-path"        # 해당 줄만 제외
ALLOW_FILE = "mf:allow-path-file"   # 파일 전체 제외(테스트 픽스처 등)
# ⑫ 안내 줄이 가리키는 절 — 튜토리얼을 쓰는 순서·본보기(test_check 가 이 절과 본보기 파일이 있는지 잰다)
TUTORIAL_HOWTO = ".claude/skills/module-forge/skills/check/SKILL.md «튜토리얼 만들기»"
# contributes(행위·건강) — 코어 brain.py 와 같은 계약(ADR-019). 코어 행위 목록은 겹침 검사에만 읽는다.
CORE_ACTIONS = os.path.join(VAULT, "3_시스템", "actions.json")
ACTION_RISKS = ("read", "write", "send", "usage")
RUN_BUILTINS = {"py", "by", "vault"}            # brain.py 가 채우는 자리표
RUN_SCRIPT_EXTS = (".py", ".ps1")               # brain.py 가 볼트 루트 기준으로 푸는 대본
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def load_json(path):
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def norm(p):
    """경로 정규화: 역슬래시→슬래시, 선행 './' 제거, 후행 '/' 제거."""
    s = str(p).replace("\\", "/").strip()
    while s.startswith("./"):
        s = s[2:]
    return s.rstrip("/")


def vault_basenames():
    """Stop훅과 동일 스코프: 2_지식/** + 3_시스템/_ref/**. basename → [경로]."""
    roots = [os.path.join(VAULT, "2_지식"), os.path.join(VAULT, "3_시스템", "_ref")]
    m = {}
    for r in roots:
        for p in glob.glob(os.path.join(r, "**", "*.md"), recursive=True):
            b = os.path.splitext(os.path.basename(p))[0]
            m.setdefault(b, []).append(p)
    return m


def other_manuals(module, mods):
    """다른 모듈이 선언한 설명서 장 이름 → 모듈"""
    out = {}
    for name, info in mods.items():
        con = (info.get("module") or {}).get("contributes")
        chs = con.get("manual") if isinstance(con, dict) else None
        if name == module or not isinstance(chs, list):
            continue
        for ch in chs:
            if isinstance(ch, dict) and ch.get("file"):
                out[os.path.splitext(os.path.basename(norm(ch["file"])))[0]] = name
    return out


def core_doc_links():
    """코어 설명서 글 — {names: 코어 장 이름, links: 링크 대상 → [글]}. 모듈을 끄면 그 장이 없어지니 여기서 모듈 장으로 링크하면 깨진다."""
    sysd = os.path.join(VAULT, "3_시스템")
    paths = glob.glob(os.path.join(sysd, "설명서", "*.md")) + glob.glob(os.path.join(sysd, "tutorial", "*.md"))
    names = {os.path.splitext(os.path.basename(p))[0] for p in paths}
    hub = roles.find_note("사용자설명서")
    if hub:
        paths.append(os.path.join(VAULT, *hub.split("/")))
    links = {}
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            continue
        for t in set(re.findall(r"\[\[([^\]|#]+)", text)):
            links.setdefault(t.strip(), []).append(os.path.relpath(p, VAULT).replace(os.sep, "/"))
    return {"names": names, "links": links}


def scan_surfaces(d):
    """디렉토리 스캔으로 실제 표면 추출(선언 아닌 실물 — 드리프트 대조용)."""
    skills = sorted(
        os.path.basename(os.path.dirname(p))
        for p in glob.glob(os.path.join(d, "skills", "*", "SKILL.md"))
    )
    hj = load_json(os.path.join(d, "hooks", "hooks.json"))
    hooks = []
    if isinstance(hj, dict):
        ev = hj.get("hooks", hj)
        if isinstance(ev, dict):
            hooks = sorted(ev.keys())
    mj = load_json(os.path.join(d, ".mcp.json"))
    mcp = []
    if isinstance(mj, dict):
        srv = mj.get("mcpServers", mj)
        if isinstance(srv, dict):
            mcp = sorted(srv.keys())
    return {"skills": skills, "hooks": hooks, "mcp": mcp}


def scan_scripts(d):
    """모듈 스크립트 정적 스캔 → (볼트경로 리터럴, 코어파일 참조).

    주석·글로브·escape 표식은 제외(위 오탐 억제 규칙). SKILL.md 프로즈는 스코프 밖.
    """
    hits, core_hits = [], []
    for ext in SCRIPT_EXTS:
        for p in glob.glob(os.path.join(d, "**", ext), recursive=True):
            try:
                with open(p, encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except Exception:
                continue
            if any(ALLOW_FILE in ln for ln in lines[:40]):
                continue
            rel = os.path.relpath(p, VAULT).replace("\\", "/")
            for ln in lines:
                s = ln.strip()
                if not s or s.startswith(COMMENT_START) or ALLOW_LINE in s:
                    continue
                flat = ln.replace("\\", "/")
                for c in CORE_PATHS:
                    if c in flat:
                        core_hits.append((rel, c))
                for m in PATH_LITERAL.finditer(ln):
                    lit = norm(m.group(1))
                    if "*" in lit:
                        continue
                    hits.append((rel, lit))
    return hits, core_hits


def scan_all():
    """.claude/skills/ 를 모듈(매니페스트 보유)과 코어 plain 스킬로 분류."""
    mods, core = {}, []
    for d in sorted(glob.glob(os.path.join(SKILLS_DIR, "*"))):
        if not os.path.isdir(d):
            continue
        name = os.path.basename(d)
        pj = load_json(os.path.join(d, ".claude-plugin", "plugin.json"))
        if pj is None:
            if os.path.isfile(os.path.join(d, "SKILL.md")):
                core.append(name)
            continue
        # module.json 위치 = 루트 우선(실사용 규약), .claude-plugin/ 폴백
        mpath = os.path.join(d, "module.json")
        if not os.path.isfile(mpath):
            alt = os.path.join(d, ".claude-plugin", "module.json")
            mpath = alt if os.path.isfile(alt) else None
        mods[name] = {
            "dir": d,
            "plugin": pj,
            "module": load_json(mpath),
            "module_path": mpath,
            "actual": scan_surfaces(d),
            "root_skill": os.path.isfile(os.path.join(d, "SKILL.md")),
        }
    return mods, sorted(core)


def core_action_ids():
    d = load_json(CORE_ACTIONS) or {}
    return {str(a.get("id")) for a in d.get("actions") or [] if isinstance(a, dict) and a.get("id")}


def deps_of(info):
    """plugin.json dependencies → 이름 리스트(객체·문자열 양식 모두 허용)."""
    out = []
    for dep in (info["plugin"].get("dependencies") or []):
        n = dep.get("name") if isinstance(dep, dict) else dep
        if n:
            out.append(str(n))
    return out


def touches_of(info):
    m = info.get("module") or {}
    return [norm(t) for t in (m.get("touches") or [])]


def find_cycle(start, mods):
    """start에서 출발하는 의존 순환 경로 반환(없으면 None). DFS."""
    stack = [(start, [start])]
    while stack:
        node, path = stack.pop()
        if node not in mods:
            continue
        for d in deps_of(mods[node]):
            if d in path:
                return path + [d]
            stack.append((d, path + [d]))
    return None


def under_any(path, roots):
    """path가 roots 중 하나에 포함되는가(자기자신 포함)."""
    return any(path == r or path.startswith(r + "/") for r in roots)


def write_registry(mods, core):
    """모듈 레지스트리 재생성(설계 R0 — 충돌검사의 '기존 것' 소스). gitignore=파생."""
    reg = {"core_skills": core, "modules": {}}
    for name, info in sorted(mods.items()):
        reg["modules"][name] = {
            "version": info["plugin"].get("version"),
            "dependencies": deps_of(info),
            "touches": touches_of(info),
            "invocation": (info.get("module") or {}).get("invocation"),
            "surfaces_declared": (info.get("module") or {}).get("surfaces") or {},
            "surfaces_actual": info["actual"],
        }
    try:
        os.makedirs(os.path.dirname(REGISTRY), exist_ok=True)
        with open(REGISTRY, "w", encoding="utf-8", newline="\n") as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)
            f.write("\n")
    except Exception as e:  # 레지스트리 실패가 검사를 막지 않도록(정직히 무음 아님 → 호출부 warn)
        return str(e)
    return None


def sync_surfaces(info):
    """surfaces 선언을 실제 스캔값으로 덮어쓴다(--sync-surfaces)."""
    if not info.get("module_path") or not isinstance(info.get("module"), dict):
        return False
    info["module"]["surfaces"] = info["actual"]
    with open(info["module_path"], "w", encoding="utf-8", newline="\n") as f:
        json.dump(info["module"], f, ensure_ascii=False, indent=2)
        f.write("\n")
    return True


def check(module, mods, core):
    blocks, warns, infos = [], [], []

    # ── ① '_' 접두 (P0 실측: 로더가 스킵 — CLI는 발견하나 세션 미활성) ──
    if module.startswith("_"):
        blocks.append(f"모듈명 '{module}' = '_' 접두 금지(로더 스킵). kebab-case로 개명.")

    if module not in mods:
        d = os.path.join(SKILLS_DIR, module)
        if os.path.isdir(d):
            blocks.append(f".claude/skills/{module}/에 .claude-plugin/plugin.json 없음 — 모듈이 아님(코어 plain 스킬).")
        else:
            blocks.append(f".claude/skills/{module}/ 없음 — 모듈 이름을 확인한다.")
        return {"ok": False, "blocks": blocks, "warns": warns, "infos": infos}

    info = mods[module]
    mj = info.get("module")
    touches = touches_of(info)

    # ── ② 모듈명 ↔ 코어 plain 스킬 동명 ──
    # 모듈 루트 SKILL.md는 plain 스킬 '<모듈>'로 등록된다(실측: module-forge 3항목 공존).
    if module in core:
        blocks.append(f"모듈명 '{module}'이 코어 plain 스킬과 동명 — 전역 스킬명 오염. 개명 필요.")

    # ── ③ 노트 basename 중복 (이 모듈 관련=block, 그 외 기존 dup=warn) ──
    expected = {f"외부뇌-{module}-모듈"}
    for b, paths in vault_basenames().items():
        if len(paths) > 1:
            rels = ", ".join(os.path.relpath(p, VAULT) for p in paths)
            is_mine = (b in expected) or (b.startswith("ADR-") and module in b)
            if is_mine:
                blocks.append(f"노트 basename 중복 '{b}' (위키링크 [[{b}]] 모호): {rels}")
            else:
                warns.append(f"기존 basename 중복 '{b}' (이 모듈 무관 · 볼트 청소 권고)")

    # ── module.json 부재 = 경계 미선언 (warn — 순수 스킬묶음도 가능하나 계약 없음) ──
    if mj is None:
        warns.append(
            f"module.json 없음 — 볼트 쓰기경계 미선언(touches/forbids/invocation/surfaces). "
            f"경계계약 없는 모듈은 충돌검사 대부분이 무력(무음 통과). module.json 을 두는 것을 권장."
        )
        mj = {}

    # ── ④ 1_수집 침범 (I3 HARD block) ──
    for t in touches:
        if t.startswith("1_수집"):
            blocks.append(f"I3 위반 — touches가 1_수집 침범: '{t}'. 사용자 저작물 불가침(승격만).")

    # ── ⑤ 예약훅 (I2 HARD block) ──
    bad = set(info["actual"]["hooks"]) & RESERVED_HOOKS
    if bad:
        blocks.append(f"I2 위반 — 예약훅 등록 금지: {', '.join(sorted(bad))}. 안전 이벤트(PostToolUse 등)만.")

    # ── ⑥ 모듈간 touches 겹침 (동일=block · 포함관계=warn) ──
    for other, oinfo in sorted(mods.items()):
        if other == module:
            continue
        for a in touches:
            for b in touches_of(oinfo):
                if a == b:
                    blocks.append(f"touches 동일경로 충돌 — '{a}'를 '{module}'과 '{other}'가 함께 씀(소유권 모호).")
                elif a.startswith(b + "/") or b.startswith(a + "/"):
                    warns.append(f"touches 포함관계 — '{module}':'{a}' ↔ '{other}':'{b}'. 상위 경로 모듈이 하위를 덮음(경계 좁힐 것).")

    # ── ⑦ deps 순환·미존재 (단방향 의존 강제) ──
    for d in deps_of(info):
        if d not in mods:
            blocks.append(f"dependencies '{d}' 미존재 — .claude/skills/{d}/ 에 모듈 없음.")
    cyc = find_cycle(module, mods)
    if cyc:
        blocks.append(f"deps 순환 — {' → '.join(cyc)}. 단방향 의존 위반(순환 금지).")

    # ── ⑧ 코어 config 격리 (I3 — A6 결정: 공유 config.json에 키 추가 금지) ──
    wc = mj.get("writes_config") or []
    if wc:
        blocks.append(
            f"I3 위반 — 코어 config 키 선언: {', '.join(str(x) for x in wc)}. "
            f"코어 config는 불가침(A6 = config 모듈별 격리) → 모듈 자체 config를 "
            f"`.claude/skills/{module}/config.json` 또는 `3_시스템/_index/{module}/config.json`에 둘 것."
        )

    # ── ⑨ 스크립트 정적 스캔 (1_수집·코어파일=block · touches ∪ reads 밖=warn) ──
    # reads = 읽기만 하는 남의 볼트 경로(코어 엔진 상태 폴더·설정 노트 등 — 주인은 코어나 다른 모듈).
    #   touches(쓰는·소유하는 자리)에 넣으면 주인을 잘못 선언한다. 1_수집·코어파일은 reads 로도 풀지 않는다.
    reads = mj.get("reads")
    if reads is None:
        reads = []
    elif not (isinstance(reads, list) and all(isinstance(r, str) and norm(r) for r in reads)):
        blocks.append("reads 는 경로 글자 목록이어야 한다 — 읽기만 하는 볼트 경로(코어 상태 폴더·남의 설정 노트 등).")
        reads = []
    reads = [norm(r) for r in reads]
    for r in reads:
        core = [c for c in CORE_PATHS if under_any(r, [c]) or under_any(c, [r])]
        if r.startswith("1_수집"):
            blocks.append(f"I3 위반 — reads 에 1_수집: '{r}'. 1_수집은 읽기로도 풀지 않는다(대본 참조도 block).")
        elif core:
            blocks.append(f"I1 위반 — reads '{r}' 가 코어파일 '{core[0]}' 에 닿음. 코어파일은 reads 로 풀지 않는다.")
        elif under_any(r, touches):
            warns.append(f"reads '{r}' 가 touches 안 — 쓰는 자리는 touches 하나로 둔다(읽기도 덮는다).")
    lit_hits, core_hits = scan_scripts(info["dir"])
    bounds = touches + reads
    for rel, p in lit_hits:
        if p.startswith("1_수집"):
            blocks.append(f"I3 위반 — 스크립트가 1_수집 경로 참조: {rel} → '{p}'.")
        elif bounds and not under_any(p, bounds):
            where = f"touches: {', '.join(touches) or '없음'}" + (f" · reads: {', '.join(reads)}" if reads else "")
            warns.append(f"스크립트 하드코딩 경로가 touches·reads 밖: {rel} → '{p}' ({where}). 쓰면 touches, 읽기만 하면 reads 에.")
    for rel, c in sorted(set(core_hits)):
        blocks.append(f"I1 위반 — 스크립트가 코어파일 참조: {rel} → '{c}'. 모듈은 코어를 건드리지 않는다.")

    # ── module.json 스키마 버전 (forward-compat 앵커 — 미지원 필드는 무시된다) ──
    sc = mj.get("schema")
    if isinstance(sc, int) and sc > MODULE_SCHEMA:
        warns.append(f"module.json schema {sc} > 이 check.py 지원 {MODULE_SCHEMA} — 검사기 갱신 필요(미지원 필드 무시 중).")

    # ── surfaces 드리프트 (선언 ↔ 실제 스캔) ──
    decl = (mj.get("surfaces") or {}) if isinstance(mj, dict) else {}
    for kind in ("skills", "hooks", "mcp"):
        want, have = sorted(info["actual"][kind]), sorted(decl.get(kind) or [])
        if want != have:
            miss = [x for x in want if x not in have]
            extra = [x for x in have if x not in want]
            det = []
            if miss:
                det.append(f"실물에만 있음: {', '.join(miss)}")
            if extra:
                det.append(f"선언에만 있음(유령): {', '.join(extra)}")
            warns.append(
                f"surfaces.{kind} 드리프트 — 선언[{', '.join(have) or '없음'}] vs 실제[{', '.join(want) or '없음'}] "
                f"({' / '.join(det)}). `--sync-surfaces`로 갱신."
            )

    # ── ⑩ 산출물 폴더 규약 (모든 모듈이 같은 형식을 갖도록 강제) ──
    own = MODULES_ROOT + "/" + module
    for t in touches:
        if any(t == r or t.startswith(r + "/") for r in NOTE_AREAS):
            blocks.append(
                f"산출물 위치 위반 — touches '{t}'. 모듈 지식산출물은 '{own}/'에 둔다"
                f"(notes/는 코어 지식 전용). 모듈 설계노트는 touches에 넣지 않는다(귀속 규칙 — ADR-004)."
            )
        elif t == MODULES_ROOT or (t.startswith(MODULES_ROOT + "/") and t.split("/")[2] != module):
            blocks.append(
                f"산출물 경계 위반 — touches '{t}'. 모듈은 자기 폴더 '{own}/'만 선언한다(타모듈 침범·루트 독점 금지)."
            )
        elif t.startswith(MODULES_ROOT + "/"):
            infos.append(
                f"산출물 폴더 '{t}' — 프론트매터 **필수**(Stop훅 검사), MOC 등재 **면제**"
                f"(모듈은 MOC에 설계노트 1줄로 대표 — 산출물마다 등재하면 MOC 폭증). "
                f"파생·캐시는 '3_시스템/_index/{module}/'."  # mf:allow-path — 안내문 속 경로(접근 아님)
            )

    # ── ⑪ 행위·건강 선언 contributes (볼트 개혁 R4 · ADR-019 — 코어 brain.py 가 읽어 list·run·doctor) ──
    con = mj.get("contributes")
    if con is not None and not isinstance(con, dict):
        blocks.append("contributes 는 객체여야 한다 — {\"actions\": [...], \"doctor\": [...]}.")
        con = None
    con = con or {}
    mod_rel = norm(os.path.relpath(info["dir"], VAULT))

    def argv_problems(what, argv, names):
        if not (isinstance(argv, list) and argv and all(isinstance(t, str) for t in argv)):
            blocks.append(f"{what} — 명령줄이 문자열 목록이 아님.")
            return
        for t in argv:
            for ph in PLACEHOLDER.findall(t):
                if ph not in names | RUN_BUILTINS:
                    blocks.append(f"{what} — 자리표 '{{{ph}}}' 가 args 에 없음(brain.py 가 글자 그대로 넘긴다).")
            if t.startswith("{") or not t.endswith(RUN_SCRIPT_EXTS):
                continue
            p = norm(t)
            if not os.path.isfile(os.path.join(VAULT, p)):
                blocks.append(f"{what} — 대본 없음 '{p}'(볼트 루트 기준 경로).")
            elif not under_any(p, [mod_rel]):
                warns.append(f"{what} — 모듈 밖 대본 '{p}'. 모듈을 빼거나 옮기면 깨진다(모듈 안 scripts/ 로).")

    acts = con.get("actions") or []
    if not isinstance(acts, list):
        blocks.append("contributes.actions 는 목록이어야 한다.")
        acts = []
    core_ids, other_ids, mine = core_action_ids(), {}, []
    for o, oinfo in mods.items():
        oc = (oinfo.get("module") or {}).get("contributes")
        if o != module and isinstance(oc, dict) and isinstance(oc.get("actions"), list):
            for a in oc["actions"]:
                if isinstance(a, dict) and a.get("id"):
                    other_ids[str(a["id"])] = o
    for a in acts:
        if not isinstance(a, dict) or not a.get("id"):
            blocks.append("contributes.actions 에 id 없는 행위.")
            continue
        aid = str(a["id"])
        if not aid.startswith(module + "."):
            blocks.append(f"행위 id '{aid}' — '{module}.' 로 시작해야 한다(코어·다른 모듈 행위와 안 겹치게).")
        if aid in core_ids or aid in other_ids or aid in mine:
            who = "코어" if aid in core_ids else other_ids.get(aid, "같은 모듈")
            blocks.append(f"행위 id 겹침 '{aid}' — {who}와. brain.py 는 먼저 읽은 것만 쓴다.")
        mine.append(aid)
        if a.get("risk") not in ACTION_RISKS:
            blocks.append(f"행위 '{aid}' risk '{a.get('risk')}' — {'·'.join(ACTION_RISKS)} 중 하나.")
        if a.get("builtin"):
            blocks.append(f"행위 '{aid}' builtin — 코어 전용. 모듈은 run(명령줄)으로.")
        names = set()
        for g in (a.get("args") or []) + ([a["rest"]] if isinstance(a.get("rest"), dict) else []):
            n = g.get("name") if isinstance(g, dict) else None
            if not (isinstance(n, str) and re.match(r"^[A-Za-z_]\w*$", n)):
                blocks.append(f"행위 '{aid}' 인자 이름이 영문 식별자가 아님: {str(g)[:60]}")
            else:
                names.add(n)
        argv_problems(f"행위 '{aid}' run", a.get("run"), names)
        if not a.get("name"):
            warns.append(f"행위 '{aid}' name 없음 — 목록·옵시디언에 id 가 그대로 보인다.")
    if "doctor" in con:
        argv_problems("contributes.doctor", con["doctor"], set())
    if "record" in con:
        argv_problems("contributes.record", con["record"], set())
    if "view" in con:
        v = con["view"] if isinstance(con["view"], dict) else {}
        argv_problems("contributes.view.data", v.get("data"), {"reason"})
        html = str(v.get("html") or "")
        if not (under_any(norm(html), [mod_rel]) and os.path.isfile(os.path.join(VAULT, norm(html)))):
            blocks.append(f"contributes.view.html — 모듈 안의 화면 파일이 아님 '{html}'.")
    # ── ⑫ 튜토리얼·설명서 선언 (ADR-035 — 켜진 모듈 것만 볼트 목록에 합쳐지고 끄면 빠진다) ──
    n_chap, n_man = 0, 0
    if "tutorial" in con:
        t = norm(str(con["tutorial"] or ""))
        d = os.path.join(VAULT, t)
        if not (under_any(t, [mod_rel]) and os.path.isdir(d)):
            blocks.append(f"contributes.tutorial — 모듈 안의 폴더가 아님 '{t}'.")
        else:
            tl = tutorial_lint.check_folder(d, module, mj, VAULT)
            for r in tl["chapters"]:
                n_chap += 1
                name = os.path.basename(r["file"])
                # 형식과 상관없이 합격선 미달은 막는다(13장 모두 v2 · 11-08 · v1 = 미달 «형식 v1») · v1 장은 엔진이 못 읽는 꼴(legacy)을 앞에 붙인다
                legacy = list(r.get("legacy") or []) if r["version"] == 1 else []
                bad = legacy + [x for x in tutorial_lint.lines(r["blocks"]) if x not in legacy]
                blocks.extend(f"튜토리얼 대본 {name} — {x}" for x in bad)
                warns.extend(f"튜토리얼 대본 {name} — {x}" for x in tutorial_lint.lines(r["warns"]))
                if bad:  # 안내 줄은 막음 수에 넣지 않는다(건강 줄 «검사 막힘 N» 은 고칠 것만 셈)
                    infos.append(f"튜토리얼 대본 {name} — 합격선 미달 {len(bad)}건(까닭 = py -3 3_시스템/tutorial_lint.py --why {r['file']}) · 고치는 순서 = {TUTORIAL_HOWTO}.")
            blocks.extend(f"튜토리얼 대본 — {x}" for x in tl["problems"])
            if not n_chap:
                blocks.append(f"contributes.tutorial — 대본 없음 '{t}'(머리에 «장:» 이 있는 md · 쓰는 순서 = {TUTORIAL_HOWTO}).")
    if "manual" in con:
        chs = con["manual"] if isinstance(con["manual"], list) else None
        if chs is None:
            blocks.append("contributes.manual 은 목록이어야 한다 — [{\"file\": …, \"name\": …, \"gist\": …}].")
        names = vault_basenames()
        others = other_manuals(module, mods)
        core_docs = core_doc_links()
        for ch in chs or []:
            rel = norm(ch.get("file") or "") if isinstance(ch, dict) else ""
            base = os.path.splitext(os.path.basename(rel))[0]
            if not (under_any(rel, [mod_rel]) and os.path.isfile(os.path.join(VAULT, rel))):
                blocks.append(f"contributes.manual — 모듈 안의 파일이 아님 '{rel}'.")
                continue
            n_man += 1
            if not ch.get("name"):
                blocks.append(f"contributes.manual '{base}' — name 없음(목차에 보일 이름).")
            if not base.startswith(f"설명서-{module}"):
                blocks.append(f"설명서 이름 '{base}' — '설명서-{module}' 로 시작해야 한다(다른 모듈·코어 장과 안 겹치게).")
            if base in names:
                blocks.append(f"설명서 이름 겹침 '{base}' (위키링크 모호): {os.path.relpath(names[base][0], VAULT)}.")
            if base in others:
                blocks.append(f"설명서 이름 겹침 '{base}' — 모듈 {others[base]}와.")
            if base in core_docs["names"]:
                blocks.append(f"설명서 이름 겹침 '{base}' — 코어 장과.")
            for doc in core_docs["links"].get(base, []):
                blocks.append(f"코어 글 {doc} 이 모듈 설명서 [[{base}]] 로 링크 — 모듈을 끄면 깨진다(목차는 brain-manual 이 그린다).")
            with open(os.path.join(VAULT, rel), encoding="utf-8") as f:
                text = f.read()
            if not text.startswith("---"):
                blocks.append(f"설명서 {base} — 프론트매터 없음.")
            for other in sorted({x for x in others if re.search(r"\[\[" + re.escape(x) + r"[\]|#]", text)}):
                warns.append(f"설명서 {base} 가 다른 모듈의 장 [[{other}]] 로 링크 — 그 모듈을 끄면 깨진다.")
    later = sorted(set(con) - {"actions", "doctor", "record", "view", "tutorial", "manual"})
    if later:
        infos.append(f"contributes.{', '.join(later)} — 아직 읽는 곳 없음(바탕 플러그인 R5 부터) · 무시됨.")
    if mine:
        infos.append(f"행위 {len(mine)}개: {', '.join(mine)} (brain.py list · run).")
    if n_chap or n_man:
        infos.append(f"튜토리얼 {n_chap}장 · 설명서 {n_man}장 — 켜진 동안만 볼트 목록에 합쳐진다.")

    # ── 네임스페이스 (info — 네이티브 `/<모듈>:<스킬>`가 이미 충돌차단) ──
    if info["actual"]["skills"]:
        ns = ", ".join(f"/{module}:{s}" for s in info["actual"]["skills"])
        infos.append(f"네임스페이스: {ns} (네이티브 프리픽스 — 타모듈·코어와 충돌 불가).")
    if info["root_skill"]:
        infos.append(f"루트 SKILL.md → plain 스킬 '{module}' 등록(오케스트레이터). 코어 스킬: {', '.join(core)}.")
    if mj.get("invocation") == "hook" or info["actual"]["hooks"]:
        infos.append("훅 보유 모듈 — 훅 실행순서·중복발동은 런타임 충돌(정적검사 밖, P4 연기).")

    return {"ok": len(blocks) == 0, "blocks": blocks, "warns": warns, "infos": infos}


def main(argv):
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = {a for a in argv[1:] if a.startswith("--")}
    mods, core = scan_all()

    if "--sync-surfaces" in flags and args:
        if args[0] in mods and sync_surfaces(mods[args[0]]):
            mods, core = scan_all()  # 갱신 후 재스캔

    if "--no-registry" not in flags:
        write_registry(mods, core)

    if "--all" in flags:
        out, ok = {}, True
        for name in sorted(mods):
            r = check(name, mods, core)
            out[name] = r
            ok = ok and r["ok"]
        print(json.dumps({"ok": ok, "modules": out}, ensure_ascii=False, indent=2))
        return 0 if ok else 1

    if not args:
        print(json.dumps({"ok": False, "blocks": ["사용법: check.py <모듈명> | --all"], "warns": [], "infos": []},
                         ensure_ascii=False))
        return 2

    res = check(args[0], mods, core)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
