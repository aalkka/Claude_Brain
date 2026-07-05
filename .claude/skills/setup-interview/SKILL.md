---
name: setup-interview
description: 신규 설치 개인최적화. 첫 실행 시 또는 "/재보정" 시. 인터뷰로 개인 레이어를 채운다.
---
목적: 일반 코어(배포)는 그대로, 개인 레이어(§0·profile·open-loops·도메인시드)만 대화로 채운다.

슬롯(순서대로 대화, 적응형으로 파고들기):
0. **네이티브 메모리 리다이렉트(옵션R) — 설치 직후 우선 실행(다른 슬롯보다 먼저).** Claude Code 자동 메모리를 볼트 안으로 돌려 인간가독·git·검색에 포함(설계노트 §6). 배포엔 이 설정이 없으므로(settings.local.json=gitignore) 반드시 여기서 세팅.
   - 볼트 절대경로 확인(예: `C:\Claude_Brain`). `.claude/settings.local.json`에 (기존 permissions 보존하며) 병합: `"autoMemoryDirectory": "<볼트절대경로>\\3_시스템\\_claude-memory"` (Windows 경로는 `\\` 이스케이프).
   - Claude Code **재시작** → 워크스페이스 트러스트 다이얼로그 수락 → `/memory`로 경로가 볼트 `_claude-memory`인지 확인. "테스트 기억: R검증OK" 후 그 폴더에 파일 생기는지 확인.
   - **실패 시 폴백**: `"autoMemoryEnabled": false`(볼트 스킬이 메모리 전담). 기존 기본위치(`~/.claude/…`)에 이미 네이티브 메모리가 쌓였으면 그 내용을 볼트 `_claude-memory` 또는 `2_지식/notes/`로 수동 이관.
1. 정체성: 호칭·언어·존댓말 여부 → CLAUDE.md §0 {{}} 치환.
2. 커뮤니케이션: 간결/상세·톤·피할 것(맞장구·근거없는단정 등) → §0.
   **예시 캘리브레이션(필수):** 같은 질문에 대한 답변 샘플 A(간결 3줄)/B(상세 단락)를 실제로 보여주고 고르게 함 — 선언 선호("상세히 좋아요")는 부정확, 보고 고른 것이 진짜 선호.
3. 역할·도메인: 분야·현재 초점·전문성 → profile 역할·도메인.
4. 작업방식·환경: 도구·위임 성향 → profile 선호.
5. 목표·프로젝트: 활성 목표 → open-loops "활성".
6. 경계·금지: 절대 금지·프라이버시(sensitive 태그 대상) → profile 경계·금지.
7. 기존 지식: 이전할 노트/PDF 있나 → 있으면 inbox/pdf-ingest 경로 안내(일괄 마이그레이션 아님, 개별).
8. 하드웨어: **자동감지 먼저** — `nvidia-smi --query-gpu=name,memory.total --format=csv` 실행(실패 시 `wmic path win32_VideoController get name` + RAM은 `systeminfo`). 감지 실패 시에만 질문. → 임베딩 모델 config 결정(VRAM≥8GB=bge-m3 / 4~8GB=e5-base / 그 외·CPU=e5-small). 일반 사용자는 GPU 사양 모름 — 물어보는 것보다 감지가 정확.
   **우선순위: 측정 > 티어표.** `_eval/results-*`에 측정 채택 구성이 이미 있으면(=첫 사용자·측정 수행자) 그것이 config 우선 — 티어표는 측정 안 하는 신규 배포 사용자의 기본값. config는 `3_시스템/config.json` `"embed_model"`.
   **이웃밀도(graph.neigh_k):** 벡터 채택 시 의미그래프 노트당 자동링크 이웃 수. `config.json` `"graph":{"neigh_k":3}`. **기본 3 그대로 두는 게 정답**(측정 채택값 — avg차수 4.5, 고립0, 소규모 코퍼스 최적). 물어보지 말고 기본 유지 → 사용자가 그래프 조밀/희소를 명시 요구할 때만 조정(밀=5, 희=2). 코퍼스 커지면(수백 노트) union 밀도 선형↑라 재검토. floor·dup은 안전레일이라 건드리지 않음.

9. 개인 백업 저장소: 사용자에게 **개인 비공개 repo URL** 요청. 받으면 —
   **먼저 `git remote get-url origin` 확인.** origin이 배포 템플릿 repo면 → `git remote rename origin dist`(배포 보존) → `git remote add origin <개인URL>`. **이미 개인 repo면**(사용자가 직접 교체해 둠) → rename 스킵, 그대로 사용. → 마지막에 `git push -u origin main`.
   이후 SessionEnd 자동 push = **개인 repo(origin)로 감**(개인화 완료 후부터 활성 — session-end 가드가 미치환 슬롯 있으면 push 스킵). 배포 repo(dist)는 템플릿 발행(tag) 시에만.
   (2-repo 모델: **배포 repo** = 모두 clone하는 템플릿 / **개인 repo** = 이 사용자의 실제 진화 볼트. 섞이면 안 됨.) URL 없으면 스킵 → 로컬 git만(자동 push 계속 비활성).

10. 주간 점검 자동화(선택): `weekly-review`를 클라우드 루틴 cron으로 자동 실행할지.
   **전제**: 슬롯9서 개인 repo 연결됐어야 함(클라우드 에이전트가 볼트를 clone·push로 접근). 미연결이면 → "지금은 수동(`weekly-review` 주 1회 호출), 개인 repo 연결 후 /재보정서 자동화 가능" 안내하고 스킵.
   **물음**: 자동 주간점검 원하나? 요일·시간(기본 **일요일 밤**). 사용자 타임존 확인.
   **등록**: 클라우드 루틴 cron 등록(`schedule` 스킬 또는 scheduled-tasks 도구) —
     - cron = 선택 시각의 주간 반복(예 일요일 21:00 → `0 21 * * 0`, 사용자 TZ).
     - 대상 repo = 개인 repo(origin). 프롬프트 = "볼트에서 `weekly-review` 스킬을 실행하고 산출(통찰노트·open-loops·회귀 결과)을 커밋·push하라."
   **주의(정직히 안내)**: 클라우드 에이전트는 개인 repo를 clone해 돌리므로 **커밋된 내용만** 봄(로컬 전용 `_index`·미커밋 세션은 없음). 골든셋 재측정은 클라우드서 `sentence-transformers` 설치 필요(느림) → 무거우면 그 스텝은 스킵하고 통찰합성·open-loops 정리만 시켜도 됨. 산출은 push로 다음 세션에 반영됨.
   **해제/변경**: `/재보정` 또는 `schedule` 스킬로 cron 갱신·삭제.

산출: settings.local.json 옵션R(autoMemoryDirectory) + CLAUDE.md §0 슬롯 치환 + `2_지식/profile.md` 채움 + `2_지식/open-loops.md` 초기화 + search.py 모델 config 기입 + 개인 repo origin 설정 + (선택)weekly-review 클라우드 cron 등록.
원칙: 코어 규약(§1~§3)은 안 건드림. 개인 레이어만. 재실행(/재보정) 시 diff 제시 → 확인 후 적용(사용자 저작물 불가침).
(예시 캘리브레이션은 승격 — 슬롯2 필수. 나머지 강화 5수단[역질문 검증·주기 재보정 자동화 등]은 DEFERRED — 인터뷰 산출물은 사용 중 자연 교정됨[세션서 톤 지적→profile 갱신], 선불 정교화 ROI 낮음.)
