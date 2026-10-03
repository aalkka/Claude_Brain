---
type: incident
title: weekly-review 자동실행이 권한 대기로 사망 (성공한 것처럼 보임)
created: 2026-07-27
updated: 2026-07-27
tags: [훅, 스케줄, 권한, 무인실행]
links: []
status: active
---

# weekly-review 자동실행 — 권한 대기로 사망

## 증상

스케줄 태스크 `weekly-review`(매주 일요일 21:00)가 루틴 목록상 `lastRunAt`이 갱신되어 **실행된 것으로 보이는데 산출물이 하나도 없다.** 통찰노트·`_eval/results-weekly.md`·커밋·push 전부 없음. 사용자에게 어떤 보고도 도달하지 않음.

## 근본원인

**무인 실행 세션에서 승인이 필요한 도구를 호출하면, 응답할 사람이 없어 무한 대기하다 세션이 죽는다.**

스케줄 세션 전사 추적:

| 시각(KST) | 사건 |
|---|---|
| 07-26 21:11:05 | 발화·세션 생성 (로컬 정상) |
| 21:11:10 | `git status` ✓ |
| 21:11:14 | weekly-review 스킬 로드 ✓ |
| ~21:12:29 | sessions·open-loops·recent·MOC·conventions 읽기, inbox-sort 진입 ✓ |
| 21:12:49 | **첫 `Write`** → 권한 프롬프트 |
| … | **3시간 54분 대기** |
| 07-27 01:06:37 | `Tool permission request failed: AbortError: Tool permission stream closed before response received` / `toolDenialKind: "permission-rule"` → 세션 사망 |

읽기 도구는 기본 허용이라 통과했고, **첫 쓰기에서 걸렸다.** `.claude/settings.local.json`의 `permissions.allow`에는 Bash 개별 명령 40여 개만 있고 `Write`·`Edit`가 없다.

**가시성 실패가 문제를 키웠다**: `lastRunAt`은 **발화 시각만** 기록한다. 성공 여부를 반영하지 않으므로 UI에는 정상 실행으로 보인다. `notifyOnCompletion`도 꺼져 있어 실패 알림도 없었다.

부수 사실: 스케줄은 **앱이 켜져 있을 때만** 발화한다. 태스크 생성(7-5) 후 일요일 4회 중 `lastRunAt`이 기록된 건 7-26 한 번뿐 — 나머지는 그 시각에 앱이 꺼져 있었다.

## 해결

`create/update_scheduled_task` 스키마에 permission mode 파라미터가 **없다.** 스케줄 세션은 일반 권한을 그대로 쓴다.

`update_scheduled_task` 응답에서 확인된 메커니즘이 답이었다:

> Tool approvals granted during a run are stored on the task and auto-applied to future runs.

→ **태스크를 "Run now"로 1회 수동 실행**해 그 자리에서 승인하면, 승인이 **그 태스크에만** 저장되어 다음 자동 실행부터 통과한다.

`settings.local.json`에 `Write`/`Edit`를 추가하는 안은 **기각**했다. 권한은 세션 종류를 구분하지 못해 대화형 세션에도 함께 적용되고, 승인 게이트가 그 경로에서 영구 소멸한다. 태스크 스코프 승인이 더 좁다.

적용한 완화:
- `notifyOnCompletion=true` — 실행 종료 시 알림
- 태스크 프롬프트에 **무인 실행 제약** 신설: 쓰기를 산출 경로 4곳으로 한정 · `1_수집` 삭제 금지 · 그 밖의 경로는 고치지 말고 `open-loops.md`에 제안으로 기록 · **승인 프롬프트가 뜰 것 같은 작업은 시도 자체를 하지 말 것**
- 이 실패 사실(3시간 54분 대기 후 abort)을 프롬프트에 근거로 명시

※ 이 시점에서 근본 복구는 미완이다 — 사용자의 "Run now" 1회가 남아 있다.

## 재발방지

- **무인 실행 프롬프트에는 "승인이 필요한 작업을 시도하지 말라"를 명시한다.** 무인 세션은 승인 대기를 견디지 못하고, 실패가 조용하다.
- **스케줄 태스크를 만들면 "Run now"로 1회 돌려 승인을 등록한다.** 만든 직후가 아니라 첫 자동 실행 전에.
- **`lastRunAt`을 성공 신호로 읽지 않는다.** 발화 시각일 뿐이다. 성공 판정은 산출물(커밋·파일) 존재로 한다 — «완료 판단 = 산출물 존재 vs 게이트 통과» 패턴의 역방향 사례: 저기서는 산출물이 있어도 완료가 아니었고, 여기서는 실행 기록이 있어도 실행이 아니었다.
- 새 스킬·규약이 무인 경로에서 도는 경우, **쓰기가 발생하는 첫 지점**을 미리 확인한다.

> [!info]- 관련 노트 %%sl%%
> [[코어수정-준수사항-체크리스트]]
