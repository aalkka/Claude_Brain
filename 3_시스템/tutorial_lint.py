#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""튜토리얼 대본 정적 검사 — 형식 v2 합격선 가운데 대본만 읽어 재는 것(T1·T2·T3·T4·T5·T6·T7 의 정적 몫).

대본·module.json·모듈 화면 HTML·actions.json 을 읽기만 한다. 옵시디언·엔진·대본을 돌리지 않는다.

  py -3 3_시스템/tutorial_lint.py                      코어 장 + 모든 모듈 장 · 장마다 한 줄
  py -3 3_시스템/tutorial_lint.py <파일|폴더> …        그것만(모듈 폴더 안이면 그 모듈로 잰다)
  py -3 3_시스템/tutorial_lint.py --module <id> <파일>  모듈 밖에 둔 사본을 그 모듈 장으로 잰다(작업 폴더 본보기)
  py -3 3_시스템/tutorial_lint.py --why                장마다 막음·경고 줄까지
  py -3 3_시스템/tutorial_lint.py --md                 마크다운 표(결과 글에 붙일 때)
  py -3 3_시스템/tutorial_lint.py --json               기계가 읽는 꼴
  py -3 3_시스템/tutorial_lint.py --vocab              어휘 표(brain-base tutorial.ts 와 맞춰 볼 때)

종료 코드: 0 = 모두 통과 · 1 = 미달 장 있음 · 2 = 대본 없음.
규칙은 여기 한 곳이다 — module-forge check.py ⑫ 가 check_folder 를 그대로 부른다(같은 함수 · 따로 고치지 않는다).
형식 = 튜토리얼 작업 글 «형식 v2» · 합격선 = 같은 작업 글 §4. 재생으로만 재는 것(들어갈 때 거짓 → 풀이 → 참 · 상태마다 대상 찾음 · 끊어도 잔여 0)은 재생기 몫이다.
어휘 = brain-base src/ttscript.ts(0.43.0 · PLACE·PLACE_SCREEN·WAIT_VERBS·SCREEN_EVENTS·ACT_VERBS·SCREEN_CMDS — 시험 test/tutorial_vocab_check.mjs 가 이 표와 맞춘다). 값이 «E#» 인 것은 v2 에서 정했고 엔진에 아직 없다(작업 글 §5.1).
"""
import glob
import json
import os
import re
import sys
from collections import Counter

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def find_vault(start):
    """roles.py 가 든 3_시스템 의 부모 — 3_시스템 에 두든 작업 폴더에 두든 같은 볼트를 찾는다"""
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "3_시스템", "roles.py")):
            return d
        up = os.path.dirname(d)
        if up == d:
            return None
        d = up


VAULT = find_vault(os.path.dirname(os.path.abspath(__file__)))

# ── 어휘 · 값 "" = 엔진에 있음 · "E#" = 형식 v2 에서 정했고 엔진에 아직 없음(brain-base 0.45.1 = E1~E7 모두 있음 · 11-08) ──
PLACES = {  # 가리키기 자리 — ttscript.ts PLACE + 보기(지금 보는 화면)
    "리본": "", "탐색기": "", "주제탭": "", "주제패널": "", "모듈화면": "", "홈": "", "캘린더": "", "대화창": "",
    "입력": "", "고른글칩": "", "파일칩": "", "일모드켜짐": "", "계기": "", "맥락": "", "결과": "", "도구": "",
    "바뀐파일": "", "승인": "", "상자모드": "", "글자칩": "", "그림칩": "", "창": "", "메뉴": "", "보기": "",
    "화면": "",  # 모듈 화면 안(E3 화면 문 · 0.43) — 이름 = 그 화면 HTML 의 data-tt
    "고르기창": "",  # 행위 고르기 같은 고르기 창(.prompt) — 줄 이름으로 가리킴 · 홈 단추와 «또는» 으로 이음(brain-base 0.46.2)
}
WAITS = {  # 기다리기 동사 — ttscript.ts WAIT_VERBS
    "다음": "", "받은함": "", "보임": "", "사라짐": "", "늘어남": "", "연파일": "", "열림": "", "있음": "", "없음": "",
    "화면": "",  # 화면 누름|바뀜|보임 "이름"(E3 · 0.43) — 누름·바뀜 = 화면이 보내는 tt-event · 보임 = 엔진이 화면에 물어 잰 상태
}
SCREEN_EVENTS = ("누름", "바뀜", "보임")  # ttscript.ts SCREEN_EVENTS
SCREEN_CMDS = ("list", "open", "focus", "scroll", "move", "close", "back", "forward", "side")  # screen.ts — act() 의 나머지
ACTS = {  # 보여 주기·세우기·풀이 동사 — ttscript.ts ACT_VERBS + SCREEN_CMDS(screen.ts) · 풀이 동사 8개 = E7(brain-base 0.41.0)
    "대화창": "", "새대화": "", "홈": "", "파일탭": "", "주제탭": "", "드러내기": "", "밖에두기": "", "명령": "",
    "화면닫기": "", "치우기": "", "창닫기": "", "받은함치우기": "",
    **{c: "" for c in SCREEN_CMDS},
    "누르기": "", "치기": "", "고르기": "", "상자": "", "보내기": "", "행위": "", "되살리기": "", "받은함넣기": "",
    "채우기": "",  # 보여 주기 — 칸에 칠 말을 미리 채움(Enter 없음 · brain-base 0.46.1 · 사용자 11-08)
    "꼴": "",
    "휴지통에두기": "", "이름바꾸기": "",  # 흉내(brain-base 0.46.3) — 연습 휴지통에 줄 하나 · 연습 파일 이름 바꾸기(흉내 장부 · fileops 장부 0)
}
NO_ARG = ("대화창", "새대화", "홈", "파일탭", "주제탭", "창닫기", "화면닫기")
LAYOUTS = ("넓음", "좁음")  # 꼴 — 넓음 = 수집 창이 출처 나무를 그림 · 좁음 = 묶음 줄+칩(곁창이 옆에 열리거나 폭 ≤760px · 0.38.3)
PRE_STATE = ("보임", "사라짐", "있음", "없음", "열림", "연파일")  # 전제에 쓰는 상태 — 기다리기와 같은 뜻
REHEARSE = ("답", "화면", "고치기", "행위")  # 연습 답 — 답·화면·고치기 = 대화창(chat.ts rehearse) · 행위 = 행위 고르기에서 고른 행위의 결과 창(brain-base 0.46.3 · 진짜 행위 0)
CHAT_REHEARSE = ("답", "화면", "고치기")  # 보낸 말(«넣기:»)의 연습 답
BUILTIN_FILES = ("연습 노트.md", "연습 자료.pdf")  # 엔진이 만드는 연습 파일(samples)
PERSON = {"받은함", "보임", "사라짐", "늘어남", "연파일", "열림", "있음", "없음", "화면"}  # 사람의 동작을 기다림
SHOW_GIVES = {"홈": "보임 홈", "대화창": "보임 대화창", "새대화": "보임 대화창", "파일탭": "보임 탐색기", "주제탭": "보임 주제탭"}
CHAT_OUT = ("결과", "도구")  # 보낸 뒤에 늘어나는 것
PLACE_WORDS = re.compile(r"왼쪽|오른쪽|위쪽|아래쪽|맨\s?위|맨\s?아래|맨\s?끝|가운데|윗줄|아랫줄")
TYPE_WORDS = re.compile(r"(?<![고펼겹합부닫미바])쳐|치세요|치고|입력하|적어|적고|적으세요|복사|붙여")  # 보낼 말 단계의 말이 사람에게 치게·적게·붙이게 시킴 — 보낼 말은 입력칸에 미리 채우고 사람은 전송만(사용자 11-08)
SAY_SENTENCES = 3  # 넘으면 경고 — 작업 글 §4 T5 «두 문장 안팎»
SAY_CHARS = 110  # 넘으면 경고 — 11-07 13장 68단계의 말 길이로 정함(형식 v2 §4)
MAX_STEPS = 7  # 넘으면 경고 — §4 T7
HEAD_KEYS = ("형식", "장", "이름", "시간", "없애는 일", "해낼 일", "연습", "정리", "연습 파일", "화면", "옛 id")  # 화면·옛 id = 코어로 옮긴 모듈 장(수집 본체 통합 11-07)
STEP_KEYS = ("말", "가리키기", "기다리기", "풀이", "전제", "세우기", "아니면", "시킬 말", "연습", "보여 주기", "넣기", "조건")
MULTI = ("보여 주기", "풀이", "전제", "세우기")  # 여러 줄 — 나머지는 한 줄(엔진은 뒤의 것을 씀)
EXT = r"(?:md|pdf|png|jpe?g|gif|txt|docx|xlsx|pptx|hwp|canvas|json|csv|sheet)"
REF = re.compile(r"@([^@|]+?\." + EXT + r")(?=\s|\||$)")
TARGET = re.compile(r'^(\S+)(?:\s+"(.+)")?$')  # tutorial.ts all()
LINE = re.compile(r"^([^:：]+):\s*(.*)$")  # tutorial.ts parseChapter 줄 규칙
FRONT = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$")
CHECK_STEP = re.compile(r"^확인(\s|$)")

LABEL = {  # 표의 까닭 이름
    "V1": "형식 v1", "HEAD": "머리 칸", "T4": "해낼 일·확인", "PRAC": "연습 선언", "T1": "해 보기 비율", "SOLVE": "풀이 없음",
    "POINT": "가리킬 대상", "VOCAB": "어휘", "FAKE": "가짜 해 보기", "T5": "자리 낱말", "WAIT": "빈 기다리기",
    "CHAT": "보낼 말", "OLD": "v1 칸", "SAY": "말 없음", "TYPE": "치게 하는 말",
    "REAL": "진짜에 닿음", "SIM": "행위 흉내 없음", "REPEAT": "되풀이 확인",
}


# ── 읽기 ──
class Step:
    def __init__(self, name):
        self.name = name
        self.pairs = []  # (키, 값) 순서대로

    def all(self, k):
        return [v for kk, v in self.pairs if kk == k]

    def get(self, k):
        vs = self.all(k)
        return vs[-1] if vs else ""  # 엔진 = 뒤의 것

    def has(self, k):
        return any(kk == k for kk, _ in self.pairs)


class Parsed:
    def __init__(self, head, steps, preamble):
        self.head, self.steps, self.preamble = head, steps, preamble

    def head1(self, k):
        return next((v for kk, v in self.head if kk == k), "")  # 엔진 = 앞의 것

    def head_all(self, k):
        return [v for kk, v in self.head if kk == k]


def _pairs(s):
    out = []
    for ln in re.split(r"\r?\n", s):
        m = LINE.match(ln)
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def parse(text):
    """tutorial.ts parseChapter 와 같은 규칙 — 머리(--- 키: 값 ---) + `## 단계` 마다 키: 값 줄. 장 번호가 없으면 대본이 아니다(None)"""
    m = FRONT.match(text)
    if not m:
        return None
    parts = re.split(r"^## ", m.group(2), flags=re.M)
    steps = []
    for part in parts[1:]:
        nl = part.find("\n")
        st = Step((part if nl < 0 else part[:nl]).strip())
        st.pairs = _pairs("" if nl < 0 else part[nl + 1:])
        steps.append(st)
    return Parsed(_pairs(m.group(1)), steps, parts[0].strip())


# ── 맥락(대본 밖에서 읽는 것) ──
_CACHE = {}


def _json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def all_actions(vault):
    """{id: (이름, 위험)} — 코어 actions.json + 모든 모듈 contributes.actions(꺼진 모듈 포함)"""
    key = ("acts", vault)
    if key not in _CACHE:
        acts = {}
        core = _json(os.path.join(vault, "3_시스템", "actions.json")) or {}
        for a in core.get("actions") or []:
            if isinstance(a, dict) and a.get("id"):
                acts[a["id"]] = (a.get("name") or a["id"], a.get("risk") or "")
        for mp in sorted(glob.glob(os.path.join(vault, ".claude", "skills", "*", "module.json"))):
            con = (_json(mp) or {}).get("contributes")
            for a in (con.get("actions") if isinstance(con, dict) else None) or []:
                if isinstance(a, dict) and a.get("id"):
                    acts.setdefault(a["id"], (a.get("name") or a["id"], a.get("risk") or ""))
        _CACHE[key] = acts
    return _CACHE[key]


TT = [re.compile(r"""data-tt\s*=\s*["']([^"'{}$<>]+)["']"""), re.compile(r"""dataset\.tt\s*=\s*["']([^"']+)["']"""),
      re.compile(r"""setAttribute\(\s*["']data-tt["']\s*,\s*["']([^"']+)["']""")]


def view_names(vault, mj):
    """모듈 화면이 내놓은 가리킬 이름(data-tt) — 화면 HTML 과 같은 폴더의 .js"""
    con = (mj or {}).get("contributes") if isinstance(mj, dict) else None
    v = con.get("view") if isinstance(con, dict) else None
    html = str(v.get("html") or "") if isinstance(v, dict) else ""
    if not html:
        return None  # 화면 없음
    p = os.path.join(vault, *html.replace("\\", "/").split("/"))
    names = set()
    for f in [p] + sorted(glob.glob(os.path.join(os.path.dirname(p), "*.js"))):
        try:
            with open(f, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            continue
        for rx in TT:
            names.update(x.strip() for x in rx.findall(text))
    return names


def core_view_names(vault, owner):
    """코어 화면(3_시스템/views.json)의 가리킬 이름 — 머리 «화면:» 이 그 owner 를 가리킨 코어 장 · 화면이 없으면 None(수집 본체 통합 4단계)"""
    d = _json(os.path.join(vault, "3_시스템", "views.json"))
    for v in (d.get("views") if isinstance(d, dict) and isinstance(d.get("views"), list) else []):
        if isinstance(v, dict) and v.get("owner") == owner:
            return view_names(vault, {"contributes": {"view": v}})
    return None


def view_practice(vault, mj=None, owner=None):
    """화면 선언에 연습 자료 명령(«practice» · E2)이 있나 — 코어 = views.json 의 그 owner · 모듈 = contributes.view(엔진 modview.ts 와 같은 첫 칸 «{py}»)"""
    if owner:
        d = _json(os.path.join(vault, "3_시스템", "views.json"))
        vs = [v for v in (d.get("views") if isinstance(d, dict) and isinstance(d.get("views"), list) else []) if isinstance(v, dict) and v.get("owner") == owner]
    else:
        con = (mj or {}).get("contributes") if isinstance(mj, dict) else None
        vs = [con["view"]] if isinstance(con, dict) and isinstance(con.get("view"), dict) else []
    return any(isinstance(v.get("practice"), list) and len(v["practice"]) > 1 and v["practice"][0] == "{py}" for v in vs)


def context(module, mj, vault):
    con = (mj or {}).get("contributes") if isinstance(mj, dict) else None
    acts = (con.get("actions") if isinstance(con, dict) else None) or []
    return {
        "module": module,
        "tt": view_names(vault, mj) if module else None,
        "practice": view_practice(vault, mj) if module else False,  # 화면 선언의 연습 자료 명령(E2)
        "actions": all_actions(vault),
        "mod_actions": {a["id"]: a.get("name") or a["id"] for a in acts if isinstance(a, dict) and a.get("id") and a.get("risk") not in ("usage", "send")},
    }


# ── 판정 ──
class Out:
    def __init__(self):
        self.blocks, self.warns, self.plan = [], [], Counter()

    def block(self, code, step, msg):
        self.blocks.append({"code": code, "step": step, "msg": msg})

    def warn(self, code, step, msg):
        self.warns.append({"code": code, "step": step, "msg": msg})


def lines(items):
    """막음·경고 → 사람이 읽는 줄"""
    return [(f"«{x['step']}» " if x.get("step") else "") + x["msg"] for x in items]


def _refs(s):
    return [m.group(1) for m in REF.finditer(s or "")]


def _bad_ref(s):
    return (s or "").count("@") > len(_refs(s))


class Chapter:
    """장 하나를 잴 때의 상태 — 쓴 연습·쓴 행위·화면 안 쓰임"""

    def __init__(self, ctx, out):
        self.ctx, self.out = ctx, out
        self.files, self.outside, self.view_inside, self.used_acts = set(), set(), False, set()

    def ref(self, s, step, where):
        if _bad_ref(s):
            self.out.block("VOCAB", step, f"{where} — «@» 뒤 연습 파일 이름은 확장자까지 '{s}'")
        self.files.update(_refs(s))

    def target(self, spec, step, where, need_text=False):
        """가리킬 것 한 줄 — 자리 이름·글·모듈 화면 이름을 잰다"""
        o, ctx = self.out, self.ctx
        m = TARGET.match((spec or "").strip())
        if not m:
            o.block("VOCAB", step, f"{where} 꼴 틀림 '{spec}' — <자리> 또는 <자리> \"글\"")
            return None
        place, text = m.group(1), m.group(2)
        if place not in PLACES:
            o.block("VOCAB", step, f"{where} 모르는 자리 '{place}'")
            return place
        if PLACES[place]:
            o.plan[f"자리 {place}({PLACES[place]})"] += 1
        if need_text and not text:
            o.block("VOCAB", step, f"{where} — 글이 있어야 함(<자리> \"글\")")
        if place in ("화면", "모듈화면"):
            if not (ctx["module"] or ctx.get("view")):
                o.block("VOCAB", step, f"{where} — 코어 장이 모듈 화면을 가리킴(모듈을 끄면 깨짐 · 코어 화면이면 머리 «화면:»)")
            elif ctx["tt"] is None:
                o.block("VOCAB", step, f"{where} — 이 모듈은 화면이 없음(contributes.view)")
            elif place == "화면":
                self.view_inside = True
                if not text:
                    o.block("VOCAB", step, f"{where} — 화면 안은 이름으로 가리킴(화면 \"이름\")")
                elif text not in ctx["tt"]:
                    o.block("VOCAB", step, f"{where} — 모듈 화면에 data-tt=\"{text}\" 없음")
        return place

    def act(self, line, st, where):
        """보여 주기·세우기·풀이 한 줄"""
        o, ctx, step = self.out, self.ctx, st.name
        sp = (line or "").strip().split(None, 1)
        verb = sp[0] if sp else ""
        arg = sp[1].strip() if len(sp) > 1 else ""
        if verb not in ACTS:
            o.block("VOCAB", step, f"{where} 모르는 동사 '{verb}'")
            return verb, arg
        if ACTS[verb]:
            o.plan[f"{where} {verb}({ACTS[verb]})"] += 1
        self.ref(arg, step, where)
        if verb in NO_ARG and arg:
            o.warn("VOCAB", step, f"{where} «{verb}» 뒤의 '{arg}' 는 쓰이지 않음")
        if verb == "화면닫기" and not ((ctx["module"] or ctx.get("view")) and ctx["tt"] is not None):
            o.block("VOCAB", step, f"{where} 화면닫기 — 화면이 있는 모듈 장·머리 «화면:» 코어 장에서만")
        elif verb in ("드러내기", "치우기", "되살리기", "명령", "휴지통에두기") and not arg:
            o.block("VOCAB", step, f"{where} «{verb}» 뒤에 대상이 없음")
        elif verb in ("치우기", "되살리기") and not _refs(arg):
            o.block("REAL", step, f"{where} «{verb} {arg}» — 연습 파일(@…)만(튜토리얼은 진짜 파일·휴지통·장부를 안 건드림 · 사용자 11-09)")
        elif verb == "이름바꾸기" and not (len(_refs(arg.split("|")[0])) == 1 and "|" in arg and arg.split("|", 1)[1].strip()):
            o.block("VOCAB", step, f"{where} 이름바꾸기 꼴 — 이름바꾸기 @<연습 파일> | <새 이름>")
        elif verb == "받은함치우기":
            o.block("OLD", step, f"{where} «받은함치우기» — 연습 받은함은 엔진이 장 끝에 치움(진짜 받은함은 안 씀 · brain-base 0.46.3)")
        elif verb in ("밖에두기", "받은함넣기"):  # 연습 받은함 = 볼트 밖 임시 폴더(brain-base 0.46.3 · 진짜 받은함 0)
            if not arg:
                o.block("VOCAB", step, f"{where} «{verb}» 뒤에 파일 이름이 없음")
            self.outside.add(arg)
        elif verb == "행위":
            aid = arg.split()[0] if arg else ""
            if aid not in ctx["actions"]:
                o.block("VOCAB", step, f"{where} 모르는 행위 '{aid}'(actions.json·module.json 에 없음)")
            o.block("REAL", step, f"{where} «행위 {aid}» — 진짜 행위를 바로 돌림 · 사람 길(누르기 홈 \"행위 고르기\" · 누르기 고르기창 \"<이름>\") + «연습: 행위 | <id> | <결과 글>»(볼트 영향 0 · 사용자 11-09)")
            self.used_acts.add(aid)
        elif verb == "누르기":
            if arg:
                self.target(arg, step, where)
            elif not st.get("가리키기").strip():
                o.block("VOCAB", step, f"{where} 누르기 — 누를 대상이 없음(뒤에 적거나 가리키기)")
        elif verb in ("치기", "채우기"):  # 채우기 = 칸에 미리 채움(Enter 없음 · 보여 주기) · 치기 = 쳐 넣고 Enter(풀이)
            m = re.match(r'^(\S+\s+"[^"]+")\s+(.+)$', arg)
            if not m:
                o.block("VOCAB", step, f"{where} {verb} 꼴 틀림 — {verb} <자리> \"글\" <칠 말>")
            else:
                self.target(m.group(1), step, where, need_text=True)
        elif verb in ("고르기", "상자"):
            if self.target(arg, step, where, need_text=True) == "화면":
                o.block("VOCAB", step, f"{where} «{verb}» — 화면 안은 누르기·치기만(E3 화면 문)")
        elif verb == "보내기":  # 인자 없음 = 입력칸에 미리 채운 말(넣기) 그대로 전송 단추를 누름(엔진 chat.ts press)
            put = st.get("넣기").strip()
            if not st.has("넣기"):
                o.block("CHAT", step, f"{where} 보내기 — 이 단계에 «넣기:»(입력칸에 미리 채울 보낼 말)가 없음")
            elif not put:
                o.block("CHAT", step, f"{where} 보내기 — «넣기:» 가 비었음")
            elif arg and arg != put:
                o.block("SOLVE", step, f"{where} 보내기 '{arg}' 가 «넣기:» 와 다름 — 인자 없이 «보내기»(채운 말 그대로 전송)")
        elif verb == "꼴" and arg not in LAYOUTS:
            o.block("VOCAB", step, f"{where} 꼴 '{arg}' — {' · '.join(LAYOUTS)} 만")
        return verb, arg

    def state(self, s, step, where):
        """기다리기·전제의 상태 한 줄(보임 X · 있음 @f …) — 동사·인자를 잰다"""
        o = self.out
        sp = (s or "").strip().split(None, 1)
        verb = sp[0] if sp else ""
        arg = sp[1].strip() if len(sp) > 1 else ""
        if verb in ("보임", "사라짐", "늘어남"):
            if not arg:
                o.block("VOCAB", step, f"{where} «{verb}» 뒤에 대상이 없음")
            elif self.target(arg, step, where) == "화면":
                o.block("VOCAB", step, f"{where} «{verb} 화면» — 화면 안은 «화면 {'|'.join(SCREEN_EVENTS)} \"이름\"»(엔진이 화면에 물음 · E3)")
        elif verb in ("연파일", "있음", "없음", "열림"):
            if not arg:
                o.block("VOCAB", step, f"{where} «{verb}» 뒤에 파일이 없음")
            self.ref(arg, step, where)
        elif verb == "화면":
            if WAITS["화면"]:
                o.plan[f"{where} 화면({WAITS['화면']})"] += 1
            m = re.match(r'^(\S+)\s+"(.+)"$', arg)
            if not m or m.group(1) not in SCREEN_EVENTS:
                o.block("VOCAB", step, f"{where} 화면 꼴 틀림 — 화면 {'|'.join(SCREEN_EVENTS)} \"이름\"")
            else:
                self.target(f'화면 "{m.group(2)}"', step, where)
        elif verb in ("다음", "받은함"):
            if arg:
                o.block("VOCAB", step, f"{where} «{verb}» 뒤에 글 '{arg}' — 엔진이 못 알아봐 단계가 멈춤")
        return verb, arg


def legacy_problems(p, folder):
    """지금 엔진(v1)이 대본을 읽는 데 필요한 꼴 — module-forge ⑫ 가 11-04 부터 막던 것과 같은 말"""
    probs = []
    no = p.head1("장")
    if not no.strip().isdigit():
        probs.append(f"«장:» 이 숫자가 아님 '{no}'.")
    if not p.head1("이름"):
        probs.append("«이름:» 없음.")
    if not p.steps:
        probs.append("단계(## ) 없음.")
    for st in p.steps:
        if not st.get("말").strip():
            probs.append(f"단계 «{st.name}» 에 «말:» 없음.")
    for f in p.head_all("연습 파일"):
        if not os.path.isfile(os.path.join(folder, f.strip())):
            probs.append(f"연습 파일 없음 '{f.strip()}'(대본 폴더 안).")
    return probs


def check_chapter(path, module=None, mj=None, vault=None, ctx=None):
    """대본 한 파일 → 판정. chapter=False 면 대본이 아니다(머리에 «장:» 없음 = 연습 파일 등)"""
    vault = vault or VAULT
    rel = os.path.relpath(path, vault).replace(os.sep, "/") if vault else path
    with open(path, encoding="utf-8") as f:
        text = f.read()
    bom = text.startswith("﻿")
    p = parse(text[1:] if bom else text)
    if p is None or not p.head1("장"):
        return {"file": rel, "chapter": False}
    ctx = ctx or context(module, mj, vault)
    own = "" if ctx["module"] else p.head1("화면").strip()
    if own:  # 코어로 옮긴 장 — 머리 «화면:» = 그 owner 의 코어 화면(엔진 tutorial.ts «화면닫기»와 같은 뜻)
        ctx = dict(ctx, view=own, tt=core_view_names(vault, own), practice=view_practice(vault, owner=own))
    folder = os.path.dirname(path)
    o = Out()
    c = Chapter(ctx, o)
    if own and ctx["tt"] is None:
        o.block("HEAD", None, f"머리 «화면: {own}» — 3_시스템/views.json 에 그 owner 의 화면이 없음")
    if bom:
        o.warn("KEY", None, "파일 앞 BOM — 엔진이 머리를 못 읽을 수 있음")

    # 머리
    raw = p.head1("형식").strip()
    version = 2 if raw == "2" else 1 if raw == "" else 0
    if version == 1:
        o.block("V1", None, "형식 v1 — 머리에 «형식: 2» 없음")
    elif version == 0:
        o.block("HEAD", None, f"모르는 형식 '{raw}' — «형식: 2» 만 안다")
    if not p.head1("장").strip().isdigit():
        o.block("HEAD", None, f"«장:» 이 숫자가 아님 '{p.head1('장')}'")
    for k, code in (("이름", "HEAD"), ("시간", "HEAD"), ("없애는 일", "HEAD"), ("해낼 일", "T4"), ("연습", "PRAC")):
        if not p.head1(k).strip():
            o.block(code, None, f"머리 «{k}:» 없음")
    if p.head_all("연습 파일"):
        o.block("OLD", None, "머리 «연습 파일:» — «연습:» 으로 합침")
    if p.head_all("정리"):
        o.warn("CLEAN", None, f"머리 «정리:» {len(p.head_all('정리'))}줄 — 엔진이 연습 장부로 치움(E1) · 손으로 안 씀")
    for k, n in Counter(k for k, _ in p.head).items():
        if k not in HEAD_KEYS:
            o.warn("KEY", None, f"모르는 머리 칸 «{k}»")
        elif n > 1 and k not in ("정리", "연습 파일"):
            o.warn("DUP", None, f"머리 «{k}:» {n}번 — 엔진은 앞의 것만 씀")
    if p.preamble:
        o.warn("KEY", None, "첫 «## » 앞의 글은 엔진이 버림")
    decl = practice(p.head1("연습"), folder, ctx, o) if p.head1("연습").strip() else None

    # 단계
    n = len(p.steps)
    if not n:
        o.block("HEAD", None, "단계(## ) 없음")
    kinds, targets, checks, stats = [], [], [], Counter()
    for i, st in enumerate(p.steps):
        s = st.name
        say = st.get("말").strip()
        wait = st.get("기다리기").strip()
        verb = wait.split(None, 1)[0] if wait else ""
        put, reh = st.has("넣기"), st.get("연습").strip()
        is_check = bool(CHECK_STEP.match(s))
        doing = verb in PERSON  # «넣기:» 단계도 해 보기 — 사람이 채운 말을 보고(고치고) 전송을 누른다(사용자 11-08)
        kinds.append(doing)
        for k, cnt in Counter(k for k, _ in st.pairs).items():
            if k not in STEP_KEYS:
                o.warn("KEY", s, f"모르는 칸 «{k}»")
            elif cnt > 1 and k not in MULTI:
                o.warn("DUP", s, f"«{k}:» {cnt}번 — 엔진은 뒤의 것만 씀")
        # 말
        if not say:
            o.block("SAY", s, "«말:» 없음")
        else:
            words = sorted(set(PLACE_WORDS.findall(say)))
            if words:
                o.block("T5", s, f"말에 자리 낱말 {' · '.join(words)} — 자리는 테두리가 가리킨다")
                stats["place_word_steps"] += 1
            sentences = len(re.findall(r"[.!?。](?=\s|$)", say))
            if sentences > SAY_SENTENCES or len(say) > SAY_CHARS:
                o.warn("LONG", s, f"긴 말 {sentences}문장 {len(say)}자 — 두 문장 안팎 · 자세한 것은 설명서로")
        # 기다리기
        if not wait:
            o.block("WAIT", s, "빈 «기다리기:» — v2 는 오류(글 카드는 «기다리기: 다음»)")
        elif verb not in WAITS:
            o.block("VOCAB", s, f"모르는 기다리기 '{verb}' — 엔진이 못 알아봐 «건너뛰기»로만 넘어감")
        else:
            c.state(wait, s, "기다리기")
        if verb == "늘어남" and wait.split(None, 1)[-1].split()[0] in CHAT_OUT and not put:
            o.block("CHAT", s, "보낸 뒤를 기다리는데 «넣기:»(입력칸에 미리 채울 보낼 말)가 없음")
        if verb == "다음" and put:
            o.block("CHAT", s, "«넣기:» 단계가 «다음»으로 넘어감 — 보낸 뒤를 기다려야 함")
        # 보낼 말 · 연습 답 — 보낼 말은 사람이 치지 않는다: 들어갈 때 입력칸에 채우고 사람은 전송만(고쳐도 됨 · 사용자 11-08)
        if st.has("시킬 말"):
            o.block("OLD", s, "«시킬 말:» — «넣기:» 로(보낼 말은 입력칸에 미리 채우고 사람은 전송만 · 사용자 11-08)")
        if put:
            stats["put_steps"] += 1
            words = sorted(set(TYPE_WORDS.findall(say)))
            if words:
                o.block("TYPE", s, f"보낼 말 단계의 말이 치게·적게·붙이게 시킴({' · '.join(words)}) — 채운 말을 보내게만")
            if not any((ln.strip().split() or [""])[0] == "보내기" for ln in st.all("풀이")):
                o.block("SOLVE", s, "«넣기:» 단계의 «풀이:» 에 «보내기» 가 없음 — 재생·건너뛰기가 채운 말을 못 보냄")
        parts = [x.strip() for x in reh.split("|")] if reh else []
        sim_act = parts[1] if len(parts) >= 3 and parts[0] == "행위" else None  # 연습: 행위 | <id> | <결과 글>
        if put and not reh:
            o.block("CHAT", s, "보낼 말에 «연습:» 답이 없음 — 튜토리얼은 토큰 0")
        if reh:
            if len(parts) < 2 or parts[0] not in REHEARSE:
                o.block("VOCAB", s, f"«연습:» 답 꼴 — {' | '.join(REHEARSE)} 로 시작하는 «종류 | …»")
            elif parts[0] == "화면" and (len(parts) < 3 or parts[1].split()[0] not in SCREEN_CMDS):
                o.block("VOCAB", s, "«연습: 화면 | <화면 명령> | 글» 꼴 틀림")
            elif parts[0] == "행위" and (sim_act is None or sim_act not in ctx["actions"] or not parts[2]):
                o.block("VOCAB", s, f"«연습: 행위 | <행위 id> | <결과 글>» 꼴 틀림 — 아는 행위 id 와 결과 글")
            c.ref(reh, s, "연습 답")
            if parts and parts[0] == "행위":
                if put:
                    o.block("CHAT", s, f"보낼 말(«넣기:») 단계의 «연습:» 은 {' · '.join(CHAT_REHEARSE)}")
            elif not put:
                o.block("CHAT", s, "보낼 말(«넣기:») 없는 «연습:» 답")
        # 행위 고르기 — 고른 행위는 흉내(결과 창 = 대본 글 · 진짜 행위·장부·실행 기록 0 · 사용자 11-09)
        names = {nm: aid for aid, (nm, _r) in ctx["actions"].items()}
        picks = set()
        for spec in re.split(r"\s+또는\s+", st.get("가리키기").strip()) + [ln.strip()[4:].strip() for ln in st.all("풀이") if ln.strip().startswith("누르기 ")]:
            tm = TARGET.match(spec.strip())
            if tm and tm.group(1) == "고르기창" and tm.group(2):
                picks.add(tm.group(2))
        for nm in sorted(picks):
            aid = names.get(nm)
            c.used_acts.add(aid or nm)
            if not aid:
                o.block("VOCAB", s, f"고르기창 «{nm}» — 그 이름의 행위가 없음(actions.json·module.json)")
            elif sim_act != aid:
                o.block("SIM", s, f"행위 고르기에서 «{nm}» 을 고르는데 «연습: 행위 | {aid} | <결과 글>» 이 없음 — 튜토리얼은 진짜 행위를 안 돌림(결과 창 = 그 글)")
        if sim_act and not picks:
            o.warn("SIM", s, f"«연습: 행위 | {sim_act}» 인데 이 단계에서 고르기창 줄을 고르지 않음")
        # 가리키기
        point = st.get("가리키기").strip()
        if point:
            for part in re.split(r"\s+또는\s+", point):  # «A 또는 B» = 앞에서부터 보이고 안 가려진 첫 것(엔진 find)
                c.target(part, s, "가리키기")
        elif doing and verb != "받은함" and not is_check:
            o.block("POINT", s, "해 보기에 «가리키기:» 없음")
            stats["no_point"] += 1
        if is_check and not point:
            o.warn("HINT", s, "확인에 «가리키기:» 없음 — 늦을 때 힌트·보여 주기를 못 냄(E5)")
        # 보여 주기 · 세우기 · 풀이
        gives = set()
        for ln in st.all("보여 주기"):
            v, a = c.act(ln, st, "보여 주기")
            gives.add(SHOW_GIVES.get(v, ""))
            if v == "open":
                gives.update(f"연파일 @{f}" for f in _refs(a))
        setups = st.all("세우기")
        for ln in setups:
            v, a = c.act(ln, st, "세우기")
            gives.add(SHOW_GIVES.get(v, ""))
        if setups:
            if not st.has("전제") and not point:
                o.block("VOCAB", s, "«세우기:» 만 있고 «전제:»·«가리키기:» 가 없음 — 돌 때가 없음")
        if doing and wait in gives:
            o.block("FAKE", s, f"들어갈 때 이미 참 — 보여 주기·세우기가 '{wait}' 를 만듦(가짜 해 보기)")
        sols = st.all("풀이")
        if sols:
            for ln in sols:
                c.act(ln, st, "풀이")
            if not doing:
                o.warn("SOLVE", s, "해 보기가 아닌 단계의 «풀이:» 는 쓰이지 않음")
        elif doing:
            o.block("SOLVE", s, "해 보기에 «풀이:» 없음 — 건너뛰기·이어서·재생이 못 넘음(E7)")
            stats["no_solve"] += 1
        # 칠 말 — 사람이 칸에 적지 않는다: 보여 주기 «채우기» 로 미리 채우고 사람은 Enter 만(사용자 11-08 · 대화 입력칸의 «넣기:» 와 같은 원칙)
        fills = {a for v, a in (((ln.strip().split(None, 1) + [""])[:2]) for ln in st.all("보여 주기")) if v == "채우기"}
        for ln in sols:
            v, a = (ln.strip().split(None, 1) + [""])[:2]
            if v == "치기" and a.strip() not in {f.strip() for f in fills}:
                o.block("TYPE", s, f"풀이 «치기 {a}» 인데 보여 주기 «채우기 {a}» 가 없음 — 칠 말은 칸에 미리 채우고 사람은 Enter 만")
        if fills:
            words = sorted(set(TYPE_WORDS.findall(say)))
            if words:
                o.block("TYPE", s, f"채우기 단계의 말이 치게·적게·붙이게 시킴({' · '.join(words)}) — 채운 말을 Enter 로 넣게만")
        # 전제 · 아니면 · 조건
        for ln in st.all("전제"):
            sp = ln.strip().split(None, 1)
            pv = sp[0] if sp else ""
            pa = sp[1].strip() if len(sp) > 1 else ""
            if pv == "플러그인":
                if not pa:
                    o.block("VOCAB", s, "«전제: 플러그인» 뒤에 id 가 없음")
            elif pv == "꼴":
                if pa not in LAYOUTS:
                    o.block("VOCAB", s, f"«전제: 꼴 {pa}» — {' · '.join(LAYOUTS)} 만")
            elif pv in PRE_STATE:
                c.state(ln, s, "전제")
            else:
                o.block("VOCAB", s, f"모르는 전제 '{pv}' — 플러그인 · 꼴 · {' · '.join(PRE_STATE)}")
        alt = st.get("아니면").strip()
        if st.has("아니면"):
            if not (alt == "건너뜀" or re.match(r"^말\s+\S", alt)):
                o.block("VOCAB", s, f"«아니면:» '{alt}' — «건너뜀» 또는 «말 <글>»")
        if st.has("조건"):
            o.block("OLD", s, "«조건:» — «전제: 플러그인 …» 으로 합침(안 맞으면 건너뜀)")
        # 사람이 하는 곳 — 가리킨 곳 · 풀이가 누르는 곳 · 보낼 말(입력) · 받은함(끌어 넣기)
        tg = {x.strip() for x in re.split(r"\s+또는\s+", point) if x.strip()} if point else set()
        tg.update(ln.strip()[4:].strip() for ln in sols if ln.strip().startswith("누르기 ") and ln.strip()[4:].strip())
        if put:
            tg.add("입력")
        if verb == "받은함":
            tg.add("받은함")
        # 확인
        if is_check:
            checks.append(i)
            if not doing:
                o.block("T4", s, "확인이 해 보기가 아님 — 사람이 혼자 하는 동작을 기다려야 함")
            before = set().union(*targets) if targets else set()
            if tg and tg <= before:
                o.block("REPEAT", s, f"확인이 앞 단계를 그대로 되풀이({' · '.join(sorted(tg))}) — 앞에서 안 한 일로(사용자 11-09)")
        targets.append(tg)

    # 장 전체 — T1 · T4 · T6 · T7
    d = sum(kinds)
    runs, cur, start, worst = [], 0, 0, (0, 0)
    for i, k in enumerate(kinds):
        if k:
            cur = 0
        else:
            cur += 1
            if cur > worst[0]:
                worst = (cur, i)
    if n:
        if 2 * d < n:
            o.block("T1", None, f"해 보기 {d}/{n} — 절반 미만")
        if worst[0] >= 2:
            a, b = worst[1] - worst[0] + 1, worst[1]
            o.block("T1", None, f"해 보기 아닌 단계 연달아 {worst[0]}(«{p.steps[a].name}»~«{p.steps[b].name}»)")
        if not kinds[0]:
            o.block("T1", None, f"첫 단계 «{p.steps[0].name}» 가 해 보기 아님")
        if not checks:
            o.block("T4", None, "끝 확인(«## 확인» — 가리킴 없이 혼자) 없음")
        elif checks[-1] != n - 1 or len(checks) > 1:
            o.block("T4", None, "«## 확인» 은 끝 단계 하나여야 함")
        if n > MAX_STEPS:
            o.warn("LEN", None, f"{n}단계 — {MAX_STEPS}단계를 넘음(나눔)")
    # T6(11-09 뒤집음 · 사용자 «직접 해 보기도 흉내») — 진짜 행위는 «행위» 동사 막음(REAL) · 고른 행위는 «연습: 행위» 흉내(SIM)
    used = sorted(c.files) + [f"밖 {x}" for x in sorted(c.outside)] + (["모듈"] if c.view_inside or (version != 2 and decl is not None and decl[2]) else [])  # v1 머리 «연습: 모듈» = 엔진이 연습 화면을 켬(E2 · ttscript.ts 와 같음)
    if decl is not None:
        dfiles, douts, dmod = decl
        for f in sorted(c.files - dfiles):
            o.block("PRAC", None, f"선언 안 한 연습 파일 @{f} — «연습:» 에 적음")
        for x in sorted(c.outside - douts):
            o.block("PRAC", None, f"선언 안 한 밖 파일 '{x}' — «연습: 밖 {x}»")
        if c.view_inside and not dmod:
            o.block("PRAC", None, "모듈 화면 안을 쓰는데 «연습: 모듈» 없음 — 장이 화면 상태를 소유해야 함(E2)")
        for f in sorted(dfiles - c.files):
            o.warn("PRAC", None, f"쓰지 않는 연습 파일 '{f}'")
        for x in sorted(douts - c.outside):
            o.warn("PRAC", None, f"쓰지 않는 밖 파일 '{x}'")
        if dmod and not c.view_inside:
            o.warn("PRAC", None, "«연습: 모듈» 인데 화면 안을 쓰는 단계가 없음")
    stats.update({"steps": n, "doing": d, "max_run": worst[0], "first_doing": bool(n and kinds[0]), "check": bool(checks),
                  "text_steps": sum(1 for st in p.steps if st.get("기다리기").strip() in ("", "다음"))})
    return {
        "file": rel, "chapter": True, "module": ctx["module"], "no": int(p.head1("장")) if p.head1("장").strip().isdigit() else None,
        "name": p.head1("이름"), "version": version, "ok": version == 2 and not o.blocks,
        "blocks": o.blocks, "warns": o.warns, "legacy": legacy_problems(p, folder),
        "planned": dict(o.plan), "stats": dict(stats), "uses": used,
    }


def practice(value, folder, ctx, o):
    """머리 «연습:» → (파일, 밖 파일, 모듈) · 꼴과 있는지를 잰다"""
    items = [x.strip() for x in re.split(r"[·,]", value) if x.strip()]
    files, outs, mod = set(), set(), False
    if "없음" in items and len(items) > 1:
        o.block("PRAC", None, "«연습: 없음» 에 다른 것을 함께 적음")
    for x in items:
        if x == "없음":
            continue
        if x == "모듈":
            mod = True
            if not (ctx["module"] or ctx.get("view")):
                o.block("PRAC", None, "«연습: 모듈» — 코어 장에는 없음(머리 «화면:» 이 없으면)")
            elif ctx["tt"] is None:
                o.block("PRAC", None, "«연습: 모듈» — 이 모듈은 화면이 없음(contributes.view)")
            elif not ctx.get("practice"):
                o.block("PRAC", None, "«연습: 모듈» — 그 화면 선언에 연습 자료 명령(practice)이 없음(E2 · 연습 동안 쓰기가 진짜 대본을 안 부르게)")
        elif x.startswith("밖 "):
            outs.add(x[2:].strip())
        elif re.search(r"\." + EXT + r"$", x):
            files.add(x)
            if x not in BUILTIN_FILES and not os.path.isfile(os.path.join(folder, x)):
                o.block("PRAC", None, f"연습 파일 '{x}' 가 대본 폴더에 없음(엔진이 만드는 것 = {' · '.join(BUILTIN_FILES)})")
        else:
            o.block("PRAC", None, f"«연습:» 모르는 항목 '{x}' — 없음 · 모듈 · 밖 <파일> · <파일.확장자>")
    return files, outs, mod


def check_folder(folder, module=None, mj=None, vault=None):
    """대본 폴더 하나 — 장마다 판정 + 폴더 문제(장 번호 겹침). module-forge ⑫ 가 이것을 부른다"""
    vault = vault or VAULT
    ctx = context(module, mj, vault)
    res = []
    for p in sorted(glob.glob(os.path.join(folder, "*.md"))):
        r = check_chapter(p, module, mj, vault, ctx)
        if r["chapter"]:
            res.append(r)
    problems = []
    for no, k in Counter(r["no"] for r in res if r["no"] is not None).items():
        if k > 1:
            problems.append(f"장 번호 {no} 겹침 — {', '.join(os.path.basename(r['file']) for r in res if r['no'] == no)}")
    return {"folder": os.path.relpath(folder, vault).replace(os.sep, "/"), "module": module, "chapters": res, "problems": problems}


# ── 볼트 전체 ──
def module_of(path, vault):
    """경로가 .claude/skills/<id>/ 안이면 (id, module.json)"""
    rel = os.path.relpath(os.path.abspath(path), vault).replace(os.sep, "/")
    m = re.match(r"^\.claude/skills/([^/]+)/", rel + ("/" if os.path.isdir(path) else ""))
    if not m:
        return None, None
    return m.group(1), _json(os.path.join(vault, ".claude", "skills", m.group(1), "module.json"))


def folders(vault):
    """[(폴더, 모듈 id, module.json)] — 코어 장 + contributes.tutorial 을 낸 모듈(꺼진 모듈 포함 · 엔진은 켜진 것만 읽음)"""
    out = [(os.path.join(vault, "3_시스템", "tutorial"), None, None)]
    for mp in sorted(glob.glob(os.path.join(vault, ".claude", "skills", "*", "module.json"))):
        mid = os.path.basename(os.path.dirname(mp))
        mj = _json(mp) or {}
        t = (mj.get("contributes") or {}).get("tutorial") if isinstance(mj.get("contributes"), dict) else None
        if isinstance(t, str) and t.replace("\\", "/").startswith(f".claude/skills/{mid}/"):
            out.append((os.path.join(vault, *t.strip("/").split("/")), mid, mj))
    return out


def reasons(r):
    c = Counter(b["code"] for b in r["blocks"])
    return " · ".join(LABEL.get(k, k) + (f" {v}" if v > 1 else "") for k, v in c.items())


def row(r):
    s = r["stats"]
    return {
        "장": r["file"], "결과": "통과" if r["ok"] else "미달", "단계": s.get("steps", 0),
        "해 보기": f"{s.get('doing', 0)}/{s.get('steps', 0)}", "연달아": s.get("max_run", 0),
        "첫 해 보기": "예" if s.get("first_doing") else "아니오", "확인": "있음" if s.get("check") else "없음",
        "풀이 없음": s.get("no_solve", 0), "자리 낱말": s.get("place_word_steps", 0), "넣기": s.get("put_steps", 0),
        "막음": len(r["blocks"]), "경고": len(r["warns"]), "까닭": reasons(r),
    }


def main(argv):
    args, flags, module = [], set(), None
    it = iter(argv[1:])
    for a in it:
        if a == "--module":
            module = next(it, None)
        elif a.startswith("--"):
            flags.add(a)
        else:
            args.append(a)
    vault = VAULT
    if not vault:
        print("볼트를 못 찾음(3_시스템/roles.py)", file=sys.stderr)
        return 2
    if "--vocab" in flags:
        print(json.dumps({"places": PLACES, "waits": WAITS, "screen_events": SCREEN_EVENTS, "acts": ACTS, "layouts": LAYOUTS,
                          "rehearse": REHEARSE, "builtin_files": BUILTIN_FILES, "head": HEAD_KEYS, "step": STEP_KEYS}, ensure_ascii=False, indent=1))
        return 0
    groups = []
    if not args:
        for d, mid, mj in folders(vault):
            groups.append(check_folder(d, mid, mj, vault))
    else:
        for a in args:
            p = os.path.abspath(a if os.path.isabs(a) else os.path.join(os.getcwd(), a))
            if not os.path.exists(p):
                p = os.path.join(vault, a)
            mid, mj = (module, _json(os.path.join(vault, ".claude", "skills", module, "module.json"))) if module else module_of(p, vault)
            if os.path.isdir(p):
                groups.append(check_folder(p, mid, mj, vault))
            else:
                r = check_chapter(p, mid, mj, vault)
                groups.append({"folder": os.path.dirname(r["file"]), "module": mid, "chapters": [r] if r["chapter"] else [], "problems": []})
    chs = [r for g in groups for r in g["chapters"]]
    probs = [x for g in groups for x in g["problems"]]
    if "--json" in flags:
        print(json.dumps({"ok": bool(chs) and all(r["ok"] for r in chs) and not probs, "groups": groups}, ensure_ascii=False, indent=1))
    elif "--md" in flags:
        rows = [row(r) for r in chs]
        if rows:
            ks = list(rows[0])
            print("| " + " | ".join(ks) + " |")
            print("|" + "---|" * len(ks))
            for x in rows:
                print("| " + " | ".join(str(x[k]).replace("|", "\\|") for k in ks) + " |")
    else:
        for r in chs:
            x = row(r)
            print(f"{x['결과']} {x['장']} — 해 보기 {x['해 보기']} · 연달아 {x['연달아']} · 확인 {x['확인']} · 막음 {x['막음']} · 경고 {x['경고']}" + (f" · {x['까닭']}" if x["까닭"] else ""))
            if "--why" in flags:
                for ln in lines(r["blocks"]):
                    print("    ✗ " + ln)
                for ln in lines(r["warns"]):
                    print("    △ " + ln)
                if r["planned"]:
                    print("    · 엔진에 아직 없음: " + " · ".join(f"{k} ×{v}" if v > 1 else k for k, v in r["planned"].items()))
                if r["version"] == 1:
                    print("    · 쓰는 연습: " + (" · ".join(r["uses"]) or "없음"))
    for x in probs:
        print("✗ " + x)
    if not chs:
        return 2
    return 0 if all(r["ok"] for r in chs) and not probs else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
