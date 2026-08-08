#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""module-forge 정적 충돌검사 (P3② 완결판).

  py check.py <모듈명>                  → {ok, blocks, warns, infos} JSON. block 있으면 exit 1.
  py check.py --all                     → 전 모듈 일괄(하나라도 block이면 exit 1)
  py check.py <모듈명> --sync-surfaces  → surfaces 선언을 실제 스캔값으로 갱신 후 재검사
  py check.py <모듈명> --no-registry    → 레지스트리 재생성 생략(테스트용)

block: ①'_'접두(로더 스킵) ②모듈명↔코어스킬 동명 ③노트 basename 중복 ④1_수집 침범(I3)
       ⑤예약훅(I2) ⑥모듈간 touches 동일경로 ⑦deps 순환·미존재 ⑧코어 config 키 선언(I3)
       ⑨스크립트의 1_수집 접근·코어파일 참조(I1) ⑩산출물 폴더 규약(notes/ 금지·타모듈 침범)
warn : module.json 부재 · surfaces 드리프트 · touches 포함관계(인접)
       · 스크립트 하드코딩 경로가 touches 밖 · 무관 basename 중복 · schema 버전 상회
infos: 네임스페이스 열거(네이티브 `/<모듈>:<스킬>`가 이미 충돌차단 → 정보만)

forward-compat: module.json의 **모르는 키는 무시**한다(P4 확장 필드 선반영 안전).
       스키마가 바뀌면 `schema` 값을 올린다 → 구버전 check.py는 warn으로 자백.

한계(정직): 런타임 충돌(훅 실행순서·MCP 포트·bin PATH) 미검출 — P4 연기.
       SKILL.md 프로즈를 Claude가 읽고 쓰는 경로는 정적으로 귀속 불가 →
       touches 준수 검증은 **모듈 스크립트(결정론 코드)** 범위만.

부산물: 3_시스템/_index/modules.json 레지스트리 재생성(gitignore=파생·재생성).
진실원본 = 2_지식/notes/외부뇌-개발지원-모듈.md §A4-3 · P3②. Stop훅 basename 로직 재활용.
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
NOTES_ROOT = "2_지식/notes"      # mf:allow-path
# 오탐 억제(정직히 명시): 리터럴 스캔은 '언급'과 '접근'을 구분 못 한다 →
#   ⓐ 주석 줄 제외 ⓑ 글로브(*) 포함 = 선언/패턴이지 대상 아님 ⓒ 명시 escape.
ALLOW_LINE = "mf:allow-path"        # 해당 줄만 제외
ALLOW_FILE = "mf:allow-path-file"   # 파일 전체 제외(테스트 픽스처 등)


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
            blocks.append(f".claude/skills/{module}/ 없음 — 먼저 스캐폴드(/module-forge:new).")
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
            f"경계계약 없는 모듈은 충돌검사 대부분이 무력(무음 통과). templates/module.json.tmpl로 생성 권장."
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

    # ── ⑨ 스크립트 정적 스캔 (1_수집·코어파일=block · touches 밖=warn) ──
    lit_hits, core_hits = scan_scripts(info["dir"])
    for rel, p in lit_hits:
        if p.startswith("1_수집"):
            blocks.append(f"I3 위반 — 스크립트가 1_수집 경로 참조: {rel} → '{p}'.")
        elif touches and not under_any(p, touches):
            warns.append(f"스크립트 하드코딩 경로가 touches 밖: {rel} → '{p}' (touches: {', '.join(touches)}).")
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
        if t == NOTES_ROOT or t.startswith(NOTES_ROOT + "/"):
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
                f"파생·캐시는 '3_시스템/_index/{module}/'."
            )

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
