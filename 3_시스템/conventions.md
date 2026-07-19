---
type: procedural
title: 상세 규격
status: active
---
# 프론트매터 스키마
type: semantic|episodic|procedural|decision|moc|incident
title, created, updated: ISO날짜, tags: [], links: []
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
