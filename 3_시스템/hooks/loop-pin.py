# -*- coding: utf-8 -*-
"""«루프» 지시에 규약을 고정 재주입한다 (UserPromptSubmit 훅 · 결정론층).

왜 있나 — 제작자 볼트 실측(2026-09-12 · 트랜스크립트 102 세션 전수):
  루프 요청 123 건 중 `deep-loop` 스킬 발동 **27 건(21%)**.
  발동 시 루프 중앙값 8 · 자료 16 건 / 미발동 시 루프 2 · 자료 2 건.
  미발동 요청의 **39%는 루프가 0 개** — 사용자가 "루프 돌려" 라 했는데 일반 응답이 나왔다.
규약은 스킬 파일(T2)에 있어 **부르지 않으면 읽히지 않는다.** 제작자 볼트는 같은 병을 이미 진단해 두었다 — "죽은 규약 문제. 문서로 존재하는데
발동하지 않는다. 이유는 계층이다."

처방은 Constraint Pinning — 약 47 토큰 고정 재주입으로 규약 위반 0% 복원
(Governance Decay, arXiv 2606.22528).

⛔ 한계를 명시한다: 이 주입도 **system-reminder 채널**이다("injected as a system reminder",
공식 hooks 문서 UserPromptSubmit 절). 기록 알림이 0% 로 실패한 바로 그 채널이다.
다른 점은 **내용이 그 프롬프트 자체를 향한다**는 것뿐이다. 순응 의존이 남아 있고,
효과는 적용 후 발동률 재측정으로만 확정된다(예측: 21% → 40% 이상).

비용: 매 프롬프트 py 기동 125ms(실측). UserPromptSubmit 은 완료까지 세션을 멈춘다.
계약: stdout = JSON 한 덩어리. 비대상이면 `{}`. 어떤 예외에도 `{}`(fail-open).
"""
import json, re, sys

HIT = re.compile(r"루프")
# 루프 지시가 아닌 용례만 뺀다. 오탐(60 토큰 낭비)보다 미탐(규율 0)의 비용이 크므로 넓게 잡는다.
NEG = re.compile(r"폐루프|루프백|무한루프|이벤트\s*루프|for\s*루프|while\s*루프|루프문")

PIN = """[loop-pin] 이 지시는 deep-loop 대상이다.
⑴ 먼저 Skill(deep-loop) 를 호출한다.
⑵ **루프가 끝날 때마다** 그 루프의 질문·측정·⭐답·예측을 본문 글로 바로 보고하고 다음 루프로 간다(첫 도구 호출 전엔 앵커·루프 종류·관점). 마지막 메시지 = 종합 + 루프당 한 줄 색인.
⑶ 루프마다 **통제 밖 값** 하나(측정·실행 출력·볼트 실측·사람 판정. 검색 자료 제외). 없으면 "이번 루프는 사유다".
⑷ 결론이 굳으면 예측+반증조건을 등록하고 다음 루프에서 대조한다.
⑸ 실행 루프는 잴 것이 남으면 멈추지 않는다. N 지정 시 N 을 채운다."""


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="")
    except Exception:
        pass
    out = {}
    try:
        raw = sys.stdin.read()
        prompt = (json.loads(raw) or {}).get("prompt") or ""
        if HIT.search(prompt) and not NEG.search(prompt):
            out = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                          "additionalContext": PIN}}
    except Exception:
        out = {}
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
