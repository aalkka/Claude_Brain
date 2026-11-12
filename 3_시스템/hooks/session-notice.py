# -*- coding: utf-8 -*-
"""기록 미완료 알림을 **사용자 화면**에 띄운다 (SessionStart 훅 · 결정론층).

왜 있나: `session-start.ps1` 이 주입하는 plain stdout 은 **사용자에게 보이지 않는다.**
공식 문서 — SessionStart stdout 은 "context that Claude can see and act on" 이고
terminal·transcript 표시 경로가 없다(anthropics/claude-code#47117).
실측(2026-09-12): 71 세션에서 주입됐고 Claude 가 사용자에게 전달한 것은 4 건(전부 기능 개발
당일). 최근 40 세션 연속 0 건. **채널이 없는데 순응에 기대고 있었다.**

그래서 같은 자료를 `systemMessage` 로 낸다 — 문서상 "Warning message shown to the user"
이고 SessionStart 절이 그 사용을 직접 권한다(hooks.md L1081). 층C 비용 경고가 이미 쓰는
경로라 이 볼트 안에 선례가 있다(ADR-010).

경계: 판정하지 않는다. Stop(`session-stub.py`)이 계산해 둔 캐시를 **읽어 한 줄로 줄일** 뿐이다.
생산자/소비자 분리는 ADR-010 그대로다.

계약: stdout = JSON 한 덩어리만. 미완료 0건이면 `{}`. 어떤 예외에도 `{}`(fail-open).
"""
import json, os, re, sys, time

PEND = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "_index", ".pending-sessions.txt")
HEALTH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_index", "health.json")
LIVE = {"git 잠금"}   # 운영 위험(drift.ops_rows)이 지금 재는 줄 — 지난 잼을 겹쳐 넣지 않는다
CAP = 10_000          # 문서상 훅 출력 문자열 상한


def build(me=""):
    path = os.path.normpath(PEND)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        raw = fh.read().strip()
    if not raw:
        return None
    lines = raw.splitlines()
    # 항목 줄에서 id·제목·날짜·경과일만 뽑는다. 지금 세션은 뺀다 — 자기 자신을 «기록이 남지 않은 세션»으로 묻게 된다.
    # 제목이 없으면 id 만으로는 기록할지 고를 수 없다(사용자 2026-10-03) — «제목» 은 session-stub.py 가 붙인다.
    items = []
    for ln in lines[1:]:
        mm = re.match(r"\s*-\s*(\w{8})\s*(?:«([^»]*)»\s*)?\(([^,]+),\s*요청\s*(\d+)회,\s*(\d+)일 전\)", ln)
        if mm and mm.group(1) != me:
            sid, title, when, req, age = mm.groups()
            items.append("   - {} «{}» ({} · 요청 {}회 · {}일 전)".format(
                sid, title or "제목 없음", when, req, age))
    if not items:
        return None
    return ("⚠ 기록이 남지 않은 세션 {}건\n{}\n"
            "   «기록» 이라고 하시면 처리합니다(세션노트 / recent 한 줄 / 넘어가기 중 택1)."
            ).format(len(items), "\n".join(items))[:CAP]


def ops():
    """조용히 일을 망치는 운영 위험(죽은 잠금 · 멈춘 자동 커밋 · 과금 환경 변수) — 있을 때만 한 덩이"""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
        import drift
        rows = drift.ops_rows()
    except Exception:
        return None
    if not rows:
        return None
    return "⚠ 운영 위험 — 사람과 대화하는 세션이면 첫 응답에 한 줄로 알린다\n" + "\n".join("   - {}: {}".format(w, t) for _, w, t in rows)


def health():
    """볼트 건강 — brain.py doctor 가 남긴 마지막 잼을 읽기만 한다(5초 · 여기서 재지 않음). 문제가 있을 때만.
    △ 는 줄 이름만(어느 영역인지 알면 요청과 닿는지 가른다 · 자세한 값과 고치는 길은 다시 잴 때 — 주입 값은 낡을 수 있다),
    ✗ 는 드물고 알려야 하므로 내용까지(11-12 사용자 «내용 다 vs 유무만» → 판단). 건강 창 «고치기»가 연 대화도 이 줄로 안다."""
    try:
        with open(os.path.normpath(HEALTH), encoding="utf-8") as fh:
            d = json.load(fh)
        rows = [r for r in d["rows"] if r.get("name") not in LIVE]
        bad = [r for r in rows if r.get("status") == "bad"][:6]
        warn = [str(r.get("name")) for r in rows if r.get("status") == "warn"][:12]
        when = time.strftime("%m-%d %H:%M", time.localtime(d["at"]))
    except Exception:
        return None
    out = ["[볼트 건강] ✗ {}: {} ({} 잼) — 사람과 대화하는 세션이면 첫 응답에 한 줄로 알린다".format(r["name"], r["line"], when) for r in bad]
    if warn:
        out.append("[볼트 건강] △{} {} — {} 잼 · 자세히·고치는 길 = py -3 3_시스템/brain.py doctor · 요청과 닿을 때만 말함".format(
            len(warn), " · ".join(warn), when))
    return "\n".join(out) or None


def hook_input():
    try:
        if sys.stdin.isatty():
            return {}
        return json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    except Exception:
        return {}


# 데스크탑 앱은 Agent SDK 로 Claude Code 를 띄우고, systemMessage 는 SDK 에서 별도 정보 메시지로
# 빠져 **화면에 그려지지 않는다**(사용자 판정 2026-09-24: CLI 에서만 뜬다 · 문서 hooks.md
# «In Agent SDK … can arrive as an SDKInformationalMessage»). 데스크탑에서 확실히 보이는 표면은
# Claude 의 본문 글뿐이다. 그런데 본문 맨 앞 한 줄은 다른 작업에 묻혀 대답할 타이밍이 안 나온다
# (사용자 2026-10-03) — 그래서 첫 응답에서 질문창(AskUserQuestion)을 띄워 그 자리에서 고르게 한다.
DESKTOP_DIRECTIVE = (
    "[기록 알림 · 데스크탑] 이 앱은 훅 systemMessage 를 화면에 띄우지 않고, 본문 한 줄은 대답할 "
    "타이밍이 안 나온다(사용자 2026-10-03). 이 세션 첫 응답에서 **다른 도구보다 먼저 "
    "AskUserQuestion 을 한 번** 부른다.\n"
    "- 세션마다 질문 하나(최대 4개 · 넘으면 오래된 4건). header = 세션 id 8자. "
    "question = «제목» (날짜 · 요청 N회) — 기록할까요? · multiSelect = false.\n"
    "- 선택지 넷: 세션노트 / recent 한 줄 / 넘어가기(영구 제외) / 이번엔 보류.\n"
    "- 답 처리: 넘어가기 = `3_시스템/_index/.pending-skip.txt` 에 id 한 줄 추가 · "
    "세션노트·recent 한 줄 = session-record 스킬 · 보류 = 아무것도 안 함(다음 세션에 다시 뜬다). "
    "기록 처리를 원래 요청보다 먼저 한다(뒤로 미루면 잊힌다).\n"
    "- 예외: 첫 요청이 무인 진행(무인 가동·루프·예약 작업)이거나 AskUserQuestion 이 없으면 이 알림을 "
    "무시하고 답에 적지 않는다(창이 무인 진행을 멈추고, 머리 없는 호출은 받는 사람이 없다 — 대본이 답을 파싱한다). "
    "창을 닫거나 답하지 않으면 다시 묻지 않는다.\n")


def main():
    # Windows locale 이 cp949 면 한글 JSON 이 깨져 훅이 통째로 무효가 된다(체크리스트 6).
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="")
    except Exception:
        pass
    out = {}
    try:
        inp = hook_input()
        # 압축·재개는 일의 한복판이다 — 여기서 «첫 응답에 창을 띄워라»가 나가면 일을 끊는다(11-02 실측: 압축 직후 발동).
        if inp.get("source") not in ("compact", "resume"):
            msg = build(str(inp.get("session_id", ""))[:8])
            risk = ops()
            hl = health()
            if os.environ.get("CLAUDE_CODE_ENTRYPOINT") == "claude-desktop":
                ctx = "\n".join(x for x in (risk, hl, DESKTOP_DIRECTIVE + msg if msg else None) if x)
            else:
                # CLI·대화창(`claude -p` = sdk-cli) — systemMessage 는 사람 화면용이라 Claude 가 못 본다(대화창은 그리지도 않음).
                # 운영 위험·볼트 건강은 Claude 가 알아야 하므로 진입점과 상관없이 맥락에도 넣는다(11-12).
                text = "\n".join(x for x in (risk, msg) if x)
                if text:
                    out["systemMessage"] = text
                ctx = "\n".join(x for x in (risk, hl) if x)
            if ctx:
                out["hookSpecificOutput"] = {"hookEventName": "SessionStart", "additionalContext": ctx[:CAP]}
    except Exception:
        out = {}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
