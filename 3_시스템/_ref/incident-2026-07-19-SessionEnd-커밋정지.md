---
type: incident
title: SessionEnd 커밋 한 주간 정지 — ML 동기실행 타임아웃 + 셧다운 종료
created: 2026-07-19
status: active
tags: [incident, 훅, 커밋, git, 셧다운]
---
# SessionEnd 커밋 한 주간 정지

## 증상
자동 세션 커밋이 07-13 이후 07-19까지 멈춤(git log: f431f6f→74f811e 6일 공백). 세션노트 07-16/17/18이 07-19에야 최초 add. 사용자 체감: "SessionEnd가 발화 안 함".

## 근본원인
**발화는 정상**(hooks.log에 07-15~19 SessionEnd fired 다수). 진짜 원인 = **커밋 라인 도달 전 훅 종료**.
1. **ML 동기실행 병목**: session-end.ps1이 커밋(21행) 앞에서 `search.py --reindex`(모델로드 16.5s+·인코딩) + `--link-write`(순수 파이썬 코사인 O(N²)) **동기** 실행. warm 31s, cold(부팅후 첫 세션·torch DLL 디스크로드·HF Hub HEAD 네트워크확인) 60s 초과.
2. **훅 타임아웃 60s**(Claude Code 기본, settings.json 오버라이드 없음) → cold 세션에서 ML 중 kill → git commit 미실행. "fired" 로그는 스크립트 선두(8행)라 진입만 증명.
3. **하루 1세션 = 매번 cold = 매번 초과** → 누적 정지. 07-19 다중 연속세션서 warm 1회 통과 → 백로그 일괄 flush.
4. **종료 = PC 셧다운**(사용자 확인): OS가 프로세스 트리째 kill, 종료 유예 수 초 → SessionEnd가 torch+커밋 완주 불가. **타임아웃 상향으로 해결 불가**(OS가 안 기다림).

부차: 07-19 01:55:49 단발 "commit BLOCKED by pre-commit - staged remain" 로그 = SessionEnd 동시 2회 발화(01:54:57 ×2) git index.lock 경합 또는 pre-commit 실차단(`3_시스템/hooks/pre-commit` 존재·`core.hooksPath` 활성 — secret/frontmatter 스캔 작동 중). **주간 정지 주원인과는 별개**: 07-14~18엔 BLOCKED 로그 0 = 훅이 pre-commit 도달 전 ML 단계서 kill(도달했다면 매번 로그). ※ 조사 중 "pre-commit 부재" 오판이 있었으나 실재 확인·정정함(파일이 확장자 없어 glob서 누락됐던 것).

## 해결
**커밋을 살아있는 세션 중 트리거로 이관**(셧다운 무관):
- **Stop 훅**(stop-check.ps1): clean 경로(위반 0)에서 **커밋 수행**(Claude/User author 분리). torch 미로드 → ~수백ms. stdout 억제(block JSON 계약 보존). 변경 없으면 diff 가드로 무커밋. → **매 턴 커밋 → 셧다운 시점엔 이미 안전.** 실동작 검증(커밋 1a454ec 착지·STDOUT 공백).
- **SessionEnd**(session-end.ps1): ML을 맨 끝 **Start-Process 디태치**(비대기)로 이동 → 훅 절대 블록 안 함. 커밋+push는 best-effort 백업으로 유지.
- **SessionStart**(session-start.ps1): 기존 reindex 뒤 **push 추가** → 셧다운이 SessionEnd를 kill해도 다음 시작 때 밀린 커밋 원격 동기.

타임아웃 상향(검토안 B)은 **채택 안 함**: 정상종료 프리즈·셧다운 무용·race 확대·link-write O(N²)라 미봉.

## 재발방지
- 원칙: **latency-bound 훅(타임아웃 有)에 무거운 ML 넣지 말 것**(설계노트 §7 "훅=결정론적 추출·저장·커밋·검증만" 위반이 뿌리였음).
- 무성 실패 가시화: session-end.ps1은 pre-commit 차단 시 hooks.log 기록(기존). Stop 커밋은 diff 가드로 안전.
- 향후 종료방식 바뀌면(예: /quit 습관화) 재평가. reindex의 SessionStart 무변경분 모델로드 낭비(16s)는 별건 최적화 여지(잔여).

> [!info]- 관련 노트 %%sl%%
> [[incident-2026-08-02-git-index-lock-62시간-자동커밋사망]]
