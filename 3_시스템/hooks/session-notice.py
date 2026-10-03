# -*- coding: utf-8 -*-
"""기록 미완료 알림을 **사용자 화면**에 띄운다 (SessionStart 훅 · 결정론층).

왜 있나: `session-start.ps1` 이 주입하는 plain stdout 은 **사용자에게 보이지 않는다.**
공식 문서 — SessionStart stdout 은 "context that Claude can see and act on" 이고
terminal·transcript 표시 경로가 없다(anthropics/claude-code#47117).
실측(2026-09-12): 71 세션에서 주입됐고 Claude 가 사용자에게 전달한 것은 4 건(전부 기능 개발
당일). 최근 40 세션 연속 0 건. **채널이 없는데 순응에 기대고 있었다.**

그래서 같은 자료를 `systemMessage` 로 낸다 — 문서상 "Warning message shown to the user"
이고 SessionStart 절이 그 사용을 직접 권한다(hooks.md L1081). 층C 비용 경고가 이미 쓰는
경로라 제작자 볼트에 선례가 있다(층C 비용 경고).

경계: 판정하지 않는다. Stop(`session-stub.py`)이 계산해 둔 캐시를 **읽어 한 줄로 줄일** 뿐이다.
생산자(Stop)/소비자(SessionStart) 분리는 기존 설계 그대로다.

계약: stdout = JSON 한 덩어리만. 미완료 0건이면 `{}`. 어떤 예외에도 `{}`(fail-open).
"""
import json, os, re, sys

PEND = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "_index", ".pending-sessions.txt")
CAP = 10_000          # 문서상 훅 출력 문자열 상한


def build():
    path = os.path.normpath(PEND)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        raw = fh.read().strip()
    if not raw:
        return None
    lines = raw.splitlines()
    # 첫 줄에서 건수, 항목 줄에서 id·제목·날짜·경과일만 뽑는다. 원문은 훅이 컨텍스트로 이미 준다.
    # 제목이 없으면 id 만으로는 기록할지 고를 수 없다(사용자 지적 2026-10-03) — «제목» 은 session-stub.py 가 붙인다.
    m = re.search(r"(\d+)\s*건", lines[0])
    n = m.group(1) if m else "?"
    items = []
    for ln in lines[1:]:
        mm = re.match(r"\s*-\s*(\w{8})\s*(?:«([^»]*)»\s*)?\(([^,]+),\s*요청\s*(\d+)회,\s*(\d+)일 전\)", ln)
        if mm:
            sid, title, when, req, age = mm.groups()
            items.append("   - {} «{}» ({} · 요청 {}회 · {}일 전)".format(
                sid, title or "제목 없음", when, req, age))
    body = "\n".join(items) if items else "   상세는 세션 시작 컨텍스트에"
    return ("⚠ 기록이 남지 않은 세션 {}건\n{}\n"
            "   «기록» 이라고 하시면 처리합니다(세션노트 / recent 한 줄 / 넘어가기 중 택1)."
            ).format(n, body)[:CAP]


# 데스크탑 앱은 Agent SDK 로 Claude Code 를 띄우고, systemMessage 는 SDK 에서 별도 정보 메시지로
# 빠져 **화면에 그려지지 않는다**(제작자 볼트 판정 2026-09-24: CLI 에서만 뜬다 · 문서 hooks.md
# «In Agent SDK … can arrive as an SDKInformationalMessage»). 데스크탑에서 확실히 보이는 표면은
# Claude 의 본문 글뿐이다. 그런데 본문 맨 앞 한 줄은 다른 작업에 묻혀 대답할 타이밍이 안 나온다
# (사용자 지적 2026-10-03) — 그래서 첫 응답에서 질문창(AskUserQuestion)을 띄워 그 자리에서 고르게 한다.
DESKTOP_DIRECTIVE = (
    "[기록 알림 · 데스크탑] 이 앱은 훅 systemMessage 를 화면에 띄우지 않고, 본문 한 줄은 대답할 "
    "타이밍이 안 나온다. 이 세션 첫 응답에서 **다른 도구보다 먼저 "
    "AskUserQuestion 을 한 번** 부른다.\n"
    "- 세션마다 질문 하나(최대 4개 · 넘으면 오래된 4건). header = 세션 id 8자. "
    "question = «제목» (날짜 · 요청 N회) — 기록할까요? · multiSelect = false.\n"
    "- 선택지 넷: 세션노트 / recent 한 줄 / 넘어가기(영구 제외) / 이번엔 보류.\n"
    "- 답 처리: 넘어가기 = `3_시스템/_index/.pending-skip.txt` 에 id 한 줄 추가 · "
    "세션노트·recent 한 줄 = session-record 스킬 · 보류 = 아무것도 안 함(다음 세션에 다시 뜬다). "
    "기록 처리를 원래 요청보다 먼저 한다(뒤로 미루면 잊힌다).\n"
    "- 예외: 첫 요청이 무인 진행(무인 가동·루프·예약 작업)이거나 AskUserQuestion 이 없으면 창을 "
    "띄우지 말고(창이 무인 진행을 멈춘다) 첫 응답 맨 앞에 아래 목록을 그대로 적는다. "
    "창을 닫거나 답하지 않으면 다시 묻지 않는다.\n")


def main():
    # Windows locale 이 cp949 면 한글 JSON 이 깨져 훅이 통째로 무효가 된다(체크리스트 6).
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="")
    except Exception:
        pass
    out = {}
    try:
        msg = build()
        if msg and os.environ.get("CLAUDE_CODE_ENTRYPOINT") == "claude-desktop":
            out = {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                          "additionalContext": DESKTOP_DIRECTIVE + msg}}
        elif msg:
            out = {"systemMessage": msg}
    except Exception:
        out = {}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
