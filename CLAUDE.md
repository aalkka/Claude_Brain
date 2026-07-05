# 외부뇌 규약

## §0 사용자   [인터뷰 주입 — 하드코딩 아님]
- 호칭: {{호칭}}. {{언어·말투}}. {{답변 선호: 간결/상세 등}}.
- 상세 프로필 → `2_지식/profile.md` 참조(필요 시 읽기).
- 슬롯이 `{{}}` 그대로면(인터뷰 전): 기본값 = 중립 존댓말·간결. 사용자에게 setup-interview 실행 권유.
- (배포판은 빈 슬롯. setup-interview가 채움. "건희님·한국어·간결"은 첫 사용자 인터뷰 산출물이지 코어 상수 아님.)

## §1 세션 시작
- SessionStart 훅이 recent·open-loops를 주입한다. 추가로 읽을 것 없음.
- 볼트 작업 전 `git status` 1회 확인.

## §2 읽기·쓰기
- 읽기: MOC/검색으로 후보 좁힘 → 관련 노트만 Read. **폴더·파일 통독 금지.**
- PDF: 직접 Read 금지 → pdf-ingest 후 검색 경유(예외: 인제스트 전 초록 확인은 pages 파라미터).
- 쓰기: append 우선. 새 노트 = 프론트매터(`3_시스템/conventions.md`) + MOC 등록.
- **요약은 원문을 대체하지 않는다**(포인터+gist만).
- **1_수집/ 은 사용자 저작물 — 수정·삭제 금지.** 승격만(원문 보존).
- 삭제 금지 → `status: archived` 마킹.
- 버그·이상 발생 시: **_ref/ 검색 먼저**(과거 진단 재활용) → 해결 후 _ref/에 incident 기록.

## §3 진화
- 이 파일에 규칙 추가 시 **기존 규칙 하나 삭제**(one-in-one-out). 총 200줄 이하 유지.

## 스킬
setup-interview · search · session-close · inbox-sort · pdf-ingest · weekly-review · obsidian-markdown · defuddle
