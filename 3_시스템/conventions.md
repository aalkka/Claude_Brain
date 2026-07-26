---
type: procedural
title: 상세 규격
status: active
---
# 프론트매터 스키마
type: semantic|episodic|procedural|decision|moc|incident
title, created, updated: ISO날짜, tags: [], links: []
links 채울 때: 위키링크는 **따옴표 배열** — `links: ["[[노트명]]", "[[다른노트]]"]`. 무따옴표 `[[x]]`/`[[[x]]]`는 YAML 파싱오류(Obsidian 적색) → Stop훅·pre-commit이 차단.
status: active|archived (기본 active)
importance: 1-10 (선택, 정적. 기본 5)
confidence: verified|hypothesized (합성·인제스트물은 hypothesized)
source: user|pdf|session|claude
sensitive: true 시 push 제외

# 쓰기 위치
지식→2_지식/notes/ · 세션→sessions/ · 결정→decisions/ · 진단(외부뇌 시스템)→3_시스템/_ref/
프로젝트 문서·진단은 프로젝트 폴더로(예 2_지식/notes/<프로젝트>/ , incident은 2_지식/notes/<프로젝트>/_ref/). 3_시스템/_ref/ = 외부뇌 시스템 자체 전용(훅·검색·규약·인덱스). 프로젝트 버그 혼입 금지.

# incident 템플릿 (_ref/ 및 프로젝트 _ref/)
frontmatter(type:incident) + ## 증상 / ## 근본원인 / ## 해결 / ## 재발방지

# 파일명·폴더 규약 (Stop 훅이 강제)
- **파일명(basename) 볼트 전역 고유** — 위키링크 `[[name]]`가 basename 해석이라 동명 노트는 모호. 스코프 2_지식/**·3_시스템/_ref/**서 중복 시 턴 종료 차단.
- **notes/·decisions/ 는 재귀 MOC 강제** — 정리용 하위폴더(예 notes/<프로젝트>/) 안 노트도 MOC 등재+프론트매터 필수. 단 **`_`접두 하위폴더**(예 _ref)는 비대상(프로젝트 incident 등).
- 정리용 그룹 폴더는 notes/ 안에 두면 됨(밖으로 빼면 검색·강제서 이탈). 핵심파일(MOC·recent·open-loops·설계노트·사용자설명서) 이동 금지.

# _index 배치 규약 (파생물 전용, gitignore)
**신규 파생물만 대상** — 기존 경로(`embeddings.json`·`hooks.log`·`pdf-cache/`)는 이동하지 않는다(경로가 search.py에 각인됨).
- `_index/cache/` — 재생성 무료·결정적. 언제든 삭제 가능.
- `_index/work/` — 재생성 유료·비결정적(전사·OCR·LLM 산출). 중간산출이며 최종물은 2_지식으로 승격. 승격 후 삭제 가능.
- `_index/<모듈명>/` — 모듈 파생(module-forge가 강제, 기존 유지).
- 로그는 `_index/*.log`. 무한 append — weekly-review 용량 보고 대상.

원본 보관: 재생성에 외부파일이 필요해도 **원본 경로를 기록하지 않는다**(사용자가 파일을 옮기거나 지우면 stale 경로가 혼란을 키움). 필요하면 사용자에게 파일을 다시 요청한다.
