---
name: session-close
description: 세션 마무리. 사용자가 "세션 종료"라 하거나 작업 마무리 시 실행.
---
1. 세션 요약 작성 → `2_지식/sessions/YYYY-MM-DD-<주제>.md` (type:episodic, 결정·산출물·미결 포함).
2. `2_지식/recent.md` 맨 위에 1줄 추가(35단어 이하) — 10줄 초과분 삭제.
3. `2_지식/open-loops.md` 갱신: 끝난 항목 제거, 새 미결 추가, "다음 세션" 기입.
4. 이번 세션에 버그 해결 있었으면 _ref/에 incident 노트.
5. 새 **지식노트(notes/·decisions/)** MOC 등록 — *확인이 아니라 대조·강제*: `2_지식/notes/`·`decisions/` 파일명을 `MOC.md`와 대조해 **미등재분을 나열하고 전부 등재**. 프론트매터 없는 노트는 생성 시점에 즉시 보강(지연 금지). (세션로그·인시던트는 MOC 대상 아님 — _ref는 weekly-review가 반영.) ※ Stop 훅(`stop-check.ps1`)이 동일 항목을 결정론 검증해 미처리 시 종료를 차단하지만, 스킬에서 선제 처리한다.
(커밋은 SessionEnd 훅이 함 — 여기선 안 함.)
