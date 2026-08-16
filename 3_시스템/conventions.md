---
type: procedural
title: 상세 규격
status: active
---
# 프론트매터 스키마
type: semantic|episodic|procedural|decision|moc|incident
  ← 6종 밖 값을 만들지 않는다. 맞는 값이 없어 보이면 semantic.
title, created, updated: ISO날짜, tags: [], links: []
  created 면제 = 상시 갱신 핵심파일(MOC·recent·open-loops·profile·설계노트·사용자설명서). 그 밖엔 필수.
  필드명은 created — `date` 아님(일반 Obsidian 스키마와 충돌).
links 채울 때: 위키링크는 **따옴표 배열** — `links: ["[[노트명]]", "[[다른노트]]"]`. 무따옴표 `[[x]]`/`[[[x]]]`는 YAML 파싱오류(Obsidian 적색) → Stop훅·pre-commit이 차단.
status: active|archived (기본 active)
importance: 1-10 (선택, 정적. 기본 5)
confidence: verified|hypothesized (합성·인제스트물은 hypothesized)
source: user|pdf|session|claude
sensitive: true 시 push 제외

# 쓰기 위치
지식→2_지식/notes/ · 세션→sessions/ · 결정→decisions/ · **모듈 산출물→2_지식/modules/<모듈명>/** · 진단(외부뇌 시스템)→3_시스템/_ref/
프로젝트 문서·진단은 프로젝트 폴더로(예 2_지식/notes/<프로젝트>/ , incident은 2_지식/notes/<프로젝트>/_ref/). 3_시스템/_ref/ = 외부뇌 시스템 자체 전용(훅·검색·규약·인덱스). 프로젝트 버그 혼입 금지.
**modules/ = 모듈(플러그인)이 생산한 지식노트 전용**(2026-07-27 신설). 모듈 *설계노트*는 여기가 아니라 notes/(`외부뇌-<모듈명>-모듈.md`). 파생·캐시는 3_시스템/_index/<모듈명>/.

# 링크 입도 — 노트냐 문단이냐 (2026-07-28 신설)
기본은 `[[노트명]]`(노트 전체). **긴 원문의 특정 대목을 가리킬 땐 문단 단위로 내린다**:
- 섹션 → `[[노트명#헤딩]]` · 문단·표·목록 → `[[노트명#^blockid]]`
- 블록 id는 대상 블록 **끝줄 뒤에 빈 줄 없이** `^blockid` 한 줄(영숫자·하이픈만).
**근거**: §2 "요약은 원문을 대체하지 않는다(포인터+gist)"의 실행 수단. 노트 전체만 가리키면 읽는 쪽이 다시 통독해야 해 §2 "통독 금지"와 충돌한다. 제작 볼트 2026-07-28 실측 = 블록참조 **0건**·헤딩링크 21건 → 입도가 노트에 묶여 있었다.
**주의**: 프론트매터 `links:`에는 따옴표 배열 그대로 — `links: ["[[노트#^id]]"]`.

# incident 템플릿 (_ref/ 및 프로젝트 _ref/)
frontmatter(type:incident) + ## 증상 / ## 근본원인 / ## 해결 / ## 재발방지

# 파일명·폴더 규약 (Stop 훅이 강제)
- **파일명(basename) 볼트 전역 고유** — 위키링크 `[[name]]`가 basename 해석이라 동명 노트는 모호. 스코프 2_지식/**·3_시스템/_ref/**서 중복 시 턴 종료 차단.
- **notes/·decisions/ 는 재귀 MOC 강제** — 정리용 하위폴더(예 notes/<프로젝트>/) 안 노트도 MOC 등재+프론트매터 필수. 단 **`_`접두 하위폴더**(예 _ref)는 비대상(프로젝트 incident 등).
- **modules/ 는 프론트매터만 강제, MOC 등재 면제** — 모듈은 MOC에 *설계노트 1줄*로 대표된다. 산출물마다 등재하면 MOC가 폭증(도그푸드 실측). 검색·중복basename·수식검사는 동일 적용.
- 정리용 그룹 폴더는 notes/ 안에 두면 됨(밖으로 빼면 검색·강제서 이탈). 핵심파일(MOC·recent·open-loops·설계노트·사용자설명서) 이동 금지.

# _index 배치 규약 (파생물 전용, gitignore)
**신규 파생물만 대상** — 기존 경로(`embeddings.json`·`hooks.log`·`pdf-cache/`)는 이동하지 않는다(경로가 search.py에 각인됨).
- `_index/cache/` — 재생성 무료·결정적. 언제든 삭제 가능.
- `_index/work/` — 재생성 유료·비결정적(전사·OCR·LLM 산출). 중간산출이며 최종물은 2_지식으로 승격. 승격 후 삭제 가능.
- `_index/<모듈명>/` — 모듈 파생(module-forge가 강제, 기존 유지).
- 로그는 `_index/*.log`. 무한 append — weekly-review 용량 보고 대상.

원본 보관: 재생성에 외부파일이 필요해도 **원본 경로를 기록하지 않는다**(사용자가 파일을 옮기거나 지우면 stale 경로가 혼란을 키움). 필요하면 사용자에게 파일을 다시 요청한다.
