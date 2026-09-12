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
    # 첫 줄에서 건수, 항목 줄에서 id 와 경과일만 뽑는다. 원문은 훅이 컨텍스트로 이미 준다.
    m = re.search(r"(\d+)\s*건", lines[0])
    n = m.group(1) if m else "?"
    items = []
    for ln in lines[1:]:
        mm = re.match(r"\s*-\s*(\w{8})\s*\(([^,]+),[^,]*,\s*(\d+)일 전\)", ln)
        if mm:
            items.append("{}({}일)".format(mm.group(1), mm.group(3)))
    body = " · ".join(items) if items else "상세는 세션 시작 컨텍스트에"
    return ("⚠ 기록이 남지 않은 세션 {}건 — {}\n"
            "   «기록» 이라고 하시면 처리합니다(세션노트 / recent 한 줄 / 넘어가기 중 택1)."
            ).format(n, body)[:CAP]


def main():
    # Windows locale 이 cp949 면 한글 JSON 이 깨져 훅이 통째로 무효가 된다(체크리스트 6).
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="")
    except Exception:
        pass
    out = {}
    try:
        msg = build()
        if msg:
            out = {"systemMessage": msg}
    except Exception:
        out = {}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
