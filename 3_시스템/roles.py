# -*- coding: utf-8 -*-
"""**roles** — 역할 이름으로 볼트 안 자리를 묻고, 주제(과목·프로젝트)를 가린다 (볼트 개혁 R6 · 2026-10-30).

왜: 코드·훅·스킬에 `2_지식/sessions` 같은 자리가 글자로 박혀 있으면(10-30 실측 77곳·35파일) 구조를 옮길 때마다
코드를 고쳐야 한다. 자리는 `3_시스템/roles.json` 한 곳에 두고 여기로 묻는다. 주제 등록부는 `2_지식/주제.md`(개인).

  py -3 3_시스템/roles.py path sessions [이어 붙일 조각…]   → 2_지식/기록/…
  py -3 3_시스템/roles.py list                               역할 전부
  py -3 3_시스템/roles.py group moc_notes                    묶음의 자리들(한 줄에 하나)
  py -3 3_시스템/roles.py topics [--json]                    주제 등록부
  py -3 3_시스템/roles.py canon 별칭                         별칭 → 정식 이름(모르면 종료 1)
  py -3 3_시스템/roles.py topic <볼트 상대 경로>               그 파일·폴더의 주제(자리 → md 의 `주제:` 속성)
  py -3 3_시스템/roles.py me [조사]                          사용자 호칭(프로필 «- **호칭**: …» · 없으면 «사용자»)

파이썬: `import roles` → `roles.path("sessions")` · `roles.abs("inbox")` · `roles.group("moc_notes")` ·
`roles.topics()` · `roles.canon("별칭")` · `roles.topic_of("1_수집/배움/과목A/x.pdf")` ·
`roles.me("이")` → «○○님이»(프로필 «- **호칭**: …» · 없으면 «사용자가»).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
_CFG = None
_TOPICS = None


def _vault(vault=None):
    return os.path.abspath(vault) if vault else VAULT


def config(vault=None):
    global _CFG
    if vault:
        with open(os.path.join(_vault(vault), "3_시스템", "roles.json"), encoding="utf-8") as f:
            return json.load(f)
    if _CFG is None:
        with open(os.path.join(HERE, "roles.json"), encoding="utf-8") as f:
            _CFG = json.load(f)
    return _CFG


def path(role, *more, vault=None):
    """역할의 볼트 상대 자리(슬래시). 없는 역할 = KeyError(조용히 엉뚱한 자리를 쓰지 않게)."""
    r = config(vault)["roles"][role]
    return "/".join([r] + [m.strip("/") for m in more if m])


def abs(role, *more, vault=None):  # noqa: A001 — 짧은 이름이 부르는 쪽을 읽기 쉽게 한다
    return os.path.join(_vault(vault), *path(role, *more, vault=vault).split("/"))


def props_table(rel, vault=None):
    """노트 자리 → 그 층의 속성 표(키 순서) · 표가 없는 층이면 None — roles.json `props` 하나를 옵시디언 새 노트 표·props-sync 가 함께 읽는다(ADR-027)."""
    rel = rel.replace("\\", "/")
    for role, keys in config(vault).get("props", {}).items():
        if not role.startswith("_") and rel.startswith(path(role, vault=vault) + "/"):
            return list(keys)
    return None


def group(name, vault=None):
    return [path(r, vault=vault) for r in config(vault)["groups"][name]]


def topics(vault=None):
    """`2_지식/주제.md` 의 첫 ```json 블록 → [{이름·영역·별칭·학기·상태…}]. 없으면 []."""
    global _TOPICS
    if _TOPICS is not None and not vault:
        return _TOPICS
    out = []
    try:
        text = open(abs("topics", vault=vault), encoding="utf-8").read()
        m = re.search(r"```json\s*\n(.*?)\n```", text, re.S)
        if m:
            out = json.loads(m.group(1)).get("topics", [])
    except (OSError, ValueError, KeyError):
        out = []
    if not vault:
        _TOPICS = out
    return out


RETENTION = {"작업산출물": 0, "작업멈춤": 7, "받은함": 7, "휴지통": 30, "웹대기칸": 90}  # 보존.md 가 없거나 칸이 빠졌을 때(설계안 §4 값)


def _retention_block(vault=None):
    try:
        text = open(abs("retention", vault=vault), encoding="utf-8").read()
        m = re.search(r"```json\s*\n(.*?)\n```", text, re.S)
        return json.loads(m.group(1)) if m else {}
    except (KeyError, OSError, ValueError, TypeError):  # KeyError = roles.json 에 retention 칸이 없음(옛 배포판·시험 볼트) → 기본값
        return {}


def _retention_row(key, vault=None):
    return (_retention_block(vault).get("칸") or {}).get(key)


def semester_ends(vault=None):
    """보존 일정표 «학기끝» → {학기 번호: «MM-DD»} · 표가 없으면 1학기 06-30 · 2학기 12-31."""
    return _retention_block(vault).get("학기끝") or {"1": "06-30", "2": "12-31"}


def semester_end(term, vault=None):
    """학기 «2026-2» → 그 학기 끝 날짜 «2026-12-31» · 모르는 꼴 = None."""
    m = re.fullmatch(r"(\d{4})-(\d+)", str(term or "").strip())
    end = semester_ends(vault).get(m.group(2)) if m else None
    return "%s-%s" % (m.group(1), end) if end else None


def retention(key, vault=None):
    """보존 일정표(`2_지식/보존.md` 첫 ```json 블록 · 사용자가 고침) 의 칸 하나의 «날». null = 무기한 → None."""
    row = _retention_row(key, vault)
    try:
        if row is not None and "날" in row:
            return None if row["날"] is None else int(row["날"])
    except (ValueError, TypeError):
        pass
    return RETENTION.get(key)


def retention_how(key, vault=None):
    """그 칸의 «처리»(자동 휴지통·후보·…) — 표에서 «후보»로 바꾸면 대본이 자동으로 안 지운다. 못 읽으면 빈 글(자동 안 함)."""
    row = _retention_row(key, vault)
    return str(row.get("처리") or "") if isinstance(row, dict) else ""


# ── 모듈 등록부(ADR-035) — 켜짐 판정은 여기 한 곳(옵시디언 쪽은 brain-base src/modules.ts 가 같은 규칙) ──
def _plugin_layers(vault=None):
    """enabledPlugins 를 Claude Code 와 같은 순서로(이 PC → 프로젝트 → 사용자). 못 읽는 층은 없는 셈."""
    base = _vault(vault)
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    out = []
    for p in (os.path.join(base, ".claude", "settings.local.json"), os.path.join(base, ".claude", "settings.json"), os.path.join(home, "settings.json")):
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f).get("enabledPlugins")
            out.append(d if isinstance(d, dict) else {})
        except (OSError, ValueError, AttributeError):
            out.append({})
    return out


def module_on(mid, vault=None, layers=None):
    """기본 = 켜짐 · enabledPlugins["<id>@skills-dir"] 가 false 면 꺼짐. 파일만 읽는다(claude 를 부르면 2초쯤 걸린다)."""
    for lay in _plugin_layers(vault) if layers is None else layers:
        if mid + "@skills-dir" in lay:
            return lay[mid + "@skills-dir"] is not False
    return True


def modules(on_only=False, vault=None):
    """볼트의 모듈 — [{id, dir, on, json}] · json = 못 읽으면 None(부르는 쪽이 알린다). 꺼진 모듈의 자료는 지우지 않는다."""
    base = os.path.join(_vault(vault), ".claude", "skills")
    layers = _plugin_layers(vault)
    out = []
    for mid in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        mp = os.path.join(base, mid, "module.json")
        if not os.path.isfile(mp):
            continue
        on = module_on(mid, layers=layers)
        if on_only and not on:
            continue
        try:
            with open(mp, encoding="utf-8") as f:
                mj = json.load(f)
        except (OSError, ValueError):
            mj = None
        out.append({"id": mid, "dir": os.path.join(base, mid), "on": on, "json": mj})
    return out


def canon(name, vault=None):
    """정식 이름·별칭(대소문자 무시) → 정식 이름 · 모르면 None."""
    n = (name or "").strip().lower()
    for t in topics(vault):
        if n == t["이름"].lower() or n in (a.lower() for a in t.get("별칭", [])):
            return t["이름"]
    return None


def find_notes(*names, vault=None):
    """basename(확장자 빼고)으로 2_지식 안 노트 자리를 찾는다 → {이름: 볼트 상대 경로} · 못 찾은 이름은 빠짐.
    노트 basename 은 볼트 전역 고유(conventions) — 특정 노트를 자리로 박지 않고 이름으로 묻는다(옮겨도 따라감)."""
    want = {n.lower().removesuffix(".md") + ".md": n for n in names}
    out = {}
    root = abs("knowledge", vault=vault)
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if not d.startswith(".")]
        for f in fns:
            n = want.get(f.lower())
            if n and n not in out:
                out[n] = os.path.relpath(os.path.join(dp, f), _vault(vault)).replace("\\", "/")
        if len(out) == len(want):
            break
    return out


def find_note(name, vault=None):
    return find_notes(name, vault=vault).get(name)


FM = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.S)


def _fm_topics(a):
    try:
        with open(a, encoding="utf-8") as f:
            head = f.read(4000)
    except (OSError, UnicodeDecodeError):
        return []
    m = FM.match(head)
    if not m:
        return []
    fm = m.group(1)
    one = re.search(r"^주제:\s*(.+)$", fm, re.M)
    if not one:
        return []
    v = one.group(1).strip()
    if v.startswith("["):
        return [x.strip().strip("\"'[]") for x in v.strip("[]").split(",") if x.strip().strip("\"'")]
    if v:
        return [v.strip("\"'")]
    items = re.match(r"((?:\s*-\s*.+\n?)+)", fm[one.end() + 1:])     # 주제:\n  - a\n  - b
    return [x.strip().lstrip("-").strip().strip("\"'") for x in items.group(1).splitlines() if x.strip()] if items else []


def topic_of(rel, read_md=True, vault=None):
    """파일·폴더의 주제 정식 이름(모르면 None). md 는 `주제:` 속성이 먼저(설계안 §2 예외) · 그다음 자리(topic_roots 바로 아래 폴더)."""
    rel = rel.replace("\\", "/").strip("/")
    if read_md and rel.lower().endswith(".md"):
        for t in _fm_topics(os.path.join(_vault(vault), *rel.split("/"))):
            c = canon(t, vault)
            if c:
                return c
    for root in sorted(config(vault).get("topic_roots", []), key=len, reverse=True):
        if rel.lower().startswith(root.lower() + "/"):
            seg = rel[len(root) + 1:].split("/")[0]
            if seg != rel[len(root) + 1:] or os.path.isdir(os.path.join(_vault(vault), *rel.split("/"))):
                return canon(seg, vault)
    return None


# ── 사용자 호칭 — 대본에 사람 이름을 박지 않는다(배포판 익명 · 2026-11-12) ──
# 프로필(역할 profile · `2_지식/profile.md`)의 «- **호칭**(설명): …» 줄(설명 괄호는 없어도 됨) · 없거나 슬롯({{…}}) 그대로면 «사용자».
# brain-base src/who.ts 와 같은 규칙. 조사는 앞말 끝 받침을 따른다 — 글자 치환이 «사용자이»를 만든 전례(2026-08-03).
ME_NONE = "사용자"
_ME_LINE = re.compile(r"^[ \t]*(?:[-*][ \t]*)?(?:\*\*)?호칭(?:\*\*)?(?:\([^)\n]*\))?[ \t]*[:：][ \t]*(.+?)[ \t]*$", re.M)
_PAIR = {"이": ("이", "가"), "가": ("이", "가"), "은": ("은", "는"), "는": ("은", "는"),
         "을": ("을", "를"), "를": ("을", "를"), "과": ("과", "와"), "와": ("과", "와")}
_ME = {}


def me_of(text):
    """프로필 글 → 호칭 · 못 찾으면 «사용자»."""
    m = _ME_LINE.search(text or "")
    v = re.sub(r"[.。]$", "", m.group(1)).strip() if m else ""
    return v if v and "{{" not in v else ME_NONE


def josa(word, j):
    """말 + 조사 — 짝 조사(이/가 · 은/는 · 을/를 · 과/와)만 받침으로 고르고 나머지(께 · 의 …)는 그대로 · 끝이 한글이 아니면 «이(가)»."""
    p = _PAIR.get(j)
    if not p:
        return word + j
    c = ord(word[-1]) if word else 0
    if not 0xAC00 <= c <= 0xD7A3:
        return "%s%s(%s)" % (word, p[0], p[1])
    return word + (p[0] if (c - 0xAC00) % 28 else p[1])


def me(j="", vault=None):
    """사용자 호칭(+ 조사) — me("이") = «○○님이» · 프로필에 호칭이 없으면 «사용자가». 한 번 읽으면 그 실행 동안 같은 값."""
    key = _vault(vault)
    if key not in _ME:
        try:
            with open(os.path.join(key, *path("profile", vault=vault).split("/")), encoding="utf-8") as f:
                _ME[key] = me_of(f.read())
        except (OSError, KeyError, ValueError):
            _ME[key] = ME_NONE
    return josa(_ME[key], j)


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    a = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in a
    a = [x for x in a if x != "--json"]
    cmd = a[0] if a else "list"
    try:
        if cmd == "path" and len(a) >= 2:
            print(path(a[1], *a[2:]))
        elif cmd == "group" and len(a) == 2:
            print("\n".join(group(a[1])))
        elif cmd == "list":
            roles = config()["roles"]
            if as_json:
                print(json.dumps(roles, ensure_ascii=False))
            else:
                for k, v in roles.items():
                    print("%-14s %s" % (k, v))
        elif cmd == "topics":
            ts = topics()
            if as_json:
                print(json.dumps(ts, ensure_ascii=False))
            else:
                for t in ts:
                    print("%s · %s%s%s" % (t["이름"], t.get("영역", "?"), " · " + "·".join(t["별칭"]) if t.get("별칭") else "",
                                           " · " + t["상태"] if t.get("상태") else ""))
                if not ts:
                    print("주제 등록부가 비었음(%s)" % path("topics"))
        elif cmd == "canon" and len(a) == 2:
            c = canon(a[1])
            if not c:
                print("모르는 주제: %s" % a[1])
                return 1
            print(c)
        elif cmd == "me" and len(a) <= 2:
            print(me(a[1] if len(a) == 2 else ""))
        elif cmd == "topic" and len(a) == 2:
            t = topic_of(a[1])
            print(t or "(주제 없음)")
            return 0 if t else 1
        else:
            print(__doc__.strip().split("\n\n")[1])
            return 2
    except KeyError as e:
        print("모르는 역할: %s — `roles.py list`" % e)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
