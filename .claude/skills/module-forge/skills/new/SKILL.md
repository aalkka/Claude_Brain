---
name: new
description: 새 외부뇌 모듈을 설계조력과 함께 만든다. 사용자가 "모듈 만들자", "이 기능을 외부뇌 확장/플러그인으로", "새 스킬 묶음" 같은 맥락을 보이면 발동. 능동 co-design 인터뷰(분해·경계 제안) → 볼트 설계노트+MOC+ADR → 스캐폴드 → basename 충돌검사 → "재시작해야 활성" 안내로 끝난다.
---
# /module-forge:new <kebab-모듈명> — 설계조력 + 스캐폴드

**단순 스캐폴더가 아니다. 설계 조수다.** 템플릿을 채우기 전에 함께 설계한다. 규율 = `${CLAUDE_PLUGIN_ROOT}/rules-lib.md`(먼저 읽어라).

## 절차 (순서 = DoD 관통 순서)

### 0. 모듈명 게이트 (하드블록)
- kebab-case인가? 아니면 개명 요구. **`_` 접두면 거부**(로더 스킵 — P0 실측).
- `.claude/skills/<모듈명>/` 이미 있으면 중단(덮어쓰기 금지, `check`로 안내).

### 1. 설계조력 co-design 인터뷰 (본체 — 능동 제안)
`rules-lib.md` §C 최소 질문 세트를 **대화로** 던진다. 템플릿 빈칸 받아쓰기가 아니라, 후보를 제시하고 사용자가 고르게 한다:
- **무엇/fit** 한 줄 + 외부뇌 어디 붙나.
- **진짜 차별점**(§8) — 기존 스킬·직접작업 대비 왜 별도 모듈? **재발명이면 여기서 중단** 권고.
- **분해·경계 제안**(A1 휴리스틱: 응집·인터페이스우선·단방향의존) — "스킬 N개로, 계약은 이것" 후보 제시 → 판단 받기. **토글 응집을 반드시 물어라(D5): "이 스킬들은 항상 같이 켜지고 같이 꺼지나?"** yes면 개수·크기와 무관하게 한 모듈. **크기를 이유로 쪼개지 마라.** 분리 근거는 사용주기 불일치뿐.
- **스코프 P0~** + **효율 로드맵 골격**(A2 riskiest-first: 스파이크→스켈레톤→수직슬라이스, 각 DoD).
- **touches**(볼트 쓰기경계) — **지식산출물은 `2_지식/modules/<모듈명>/`**(모든 모듈 동일 형식·MOC 등재 면제·프론트매터 필수), **파생·캐시는 `3_시스템/_index/<모듈명>/`**. `2_지식/notes/` 선언 = **block**(코어 지식 전용), 타모듈 폴더 선언 = **block**. `1_수집` 침범 = 즉시 거부.

### 2. 예방접종 (A3 — preflight 시드)
모듈 성격 키워드로 `search`(또는 Grep) → `3_시스템/_ref/`·프로젝트 `_ref/`·`2_지식/decisions/`에서 관련 함정 1~2개 소환 → **preflight 체크리스트**로 노출. 예: 한글경로/CP949·정합퇴화·백로그갭. cold start면 웹 common-pitfall로 보완(정직히 "인시던트 적음" 명시).

### 3. 볼트 설계노트 + MOC 등재
**먼저 기존 설계노트 존재 확인**(도그푸드 마찰점#1 실측): `search`/Grep로 이 모듈 주제의 기존 노트를 찾아라. **있으면 신규생성·append 금지** → convention(`외부뇌-<모듈명>-모듈`)으로 **rename + module-note 구조로 정리**(중복노트 = §2 위반·백링크 분열). 백링크 전파는 UTF-8 명시 처리(CP949 회피). 없을 때만 아래 신규생성:
`${CLAUDE_PLUGIN_ROOT}/templates/module-note.md.tmpl` 치환 → `2_지식/notes/외부뇌-<모듈명>-모듈.md` 생성(무엇/fit/차별점/스코프P0~/구현형태/**리스크(본체)**/잔여결정 + preflight). → `2_지식/MOC.md`의 `## 지식 (notes/)`에 `[[외부뇌-<모듈명>-모듈]]` 한 줄 등재(**Stop훅이 강제 — 생략 시 종료 차단**).

### 4. ADR 1건 (A4)
핵심 결정(왜 이 경계·인터페이스·스코프)을 `templates/`의 ADR 형식으로 `2_지식/decisions/ADR-NNN-<모듈명>-<주제>.md` 기록 + MOC `## 결정 (decisions/)`에 등재. 프론트매터 필수(Stop훅 검사).

### 5. 스캐폴드 (template {{slot}} 치환 — `plugin init` 미사용)
`claude plugin init`은 `~/.claude/skills/`(personal)에 만든다 → **우리는 프로젝트스코프 필요** → 템플릿 직접 치환. `${CLAUDE_PLUGIN_ROOT}/templates/`에서:
```
.claude/skills/<모듈명>/
├── .claude-plugin/plugin.json   ← plugin.json.tmpl
├── module.json                  ← module.json.tmpl (schema·touches·forbids·invocation·surfaces)
├── skills/<스킬>/SKILL.md        ← SKILL.md.tmpl (description = model-invoke 트리거의 전부 — §F 준수)
├── scripts/<이름>.py             ← script-preflight.py.tmpl (스크립트 필요할 때만)
└── README.md                    ← README.md.tmpl (볼트 설계노트 포인터)
```
슬롯: `{{module}}`·`{{description}}`·`{{skill}}`·`{{touches}}`·`{{invocation}}`·`{{script_purpose}}`·`{{author}}`(볼트 소유자 이름 — CLAUDE.md §0 호칭에서 가져온다). **version = 템플릿 기본 `0.1.0`**(clean `validate` 0경고 — P3 측정: version 생략 시 validate 경고). commit-SHA 버전 원하면 삭제.

⚠ **`module.json`은 생략 금지**. 없으면 볼트 쓰기경계 미선언 = 충돌검사 대부분이 무음 통과(check가 warn). `touches`는 **좁게** — 모듈이 직접 소유하는 경로만. 남이 쓸 산출물(설계노트·ADR)은 그 대상의 경계에 귀속된다. `writes_config`는 **항상 빈 배열** — 코어 config 불가침(모듈 자체 config를 쓴다), 채우면 block.

⚠ **description 게이트 (`rules-lib.md` §F — 슬롯 채우기 전에 읽어라).** description은 설명문이 아니라 라우팅 신호다. **짧게 쓰는 게 목적이 아니라 발동에 기여 안 하는 바이트를 0으로 만드는 게 목적** — 줄이다 트리거를 지우면 절감이 아니라 고장이다.
- 넣을 것 4개: ①행위 1구 ②발동 조건(본체) ③**사용자 어휘 트리거 3~5개**(따옴표, 내부용어 금지) ④형제·이웃과의 **음성 경계 1구**.
- 뺄 것: 절차 나열·산출물 포맷·아키텍처·하위스킬 위임설명·모듈명 반복 → 전부 본문 몫.
- 쓴 뒤 §F3 3문 자기점검(오발동·미발동·형제충돌)을 **소리 내어 통과시켜라.**
- 예산 = 스킬당 ≤350B(한글 바이트÷5.8≈토큰). **하드블록 아님** — 넘으면 자르지 말고 위 "뺄 것"이 섞였는지 보라. 모듈 합계 상한은 없다(D5).

⚠ **스크립트를 쓸 거면 `script-preflight.py.tmpl`에서 시작**. UTF-8 강제·LF 고정·`${CLAUDE_PLUGIN_ROOT}` 상대경로·인자로 경로받기·실측게이트가 이미 박혀 있다(실측 인시던트 대응 — 매 모듈 재작성 금지). 경로를 하드코딩하면 check가 "touches 밖"으로 경고하고, 코어파일을 참조하면 **I1 block**이다.

**예약 스키마(P4 대비 — 지금은 쓰지 마라)**: `module.json`의 모르는 키는 check가 **무시**한다(선반영 안전). 미래 확장 예약어 = `runtime`(MCP 포트·`bin/` PATH 선언) · `router`(진입점 라우터 노출제어) · `marketplace`(배포 메타). 스키마가 바뀌면 `schema` 값이 오르고 구버전 검사기는 warn으로 자백한다.

### 6. 충돌검사 (가드레일)
```bash
py -3 "${CLAUDE_PLUGIN_ROOT}/scripts/check.py" <모듈명>
```
`{ok, blocks, warns, infos}` 출력. **block 있으면(exit≠0) 중단** — `_`접두·코어스킬 동명·basename 중복·`1_수집` 침범(I3)·예약훅(I2)·모듈간 touches 동일경로·deps 순환/미존재. 스킬을 나중에 추가했으면 `--sync-surfaces`로 `surfaces` 갱신(드리프트 warn 해소). 이어서 네이티브 검증:
```bash
claude plugin validate ".claude/skills/<모듈명>"
```

### 7. 재시작 안내 (하드규칙 — 여기서 멈춤)
> ⚠ 신규 모듈은 이 환경에서 **세션 재시작해야 활성**된다(`/reload-plugins` 미지원 — P0 실측). 생성 당일 세션엔 `/<모듈명>:<스킬>` 못 쓴다. **"재시작 후 로드 확인" 안내하고 멈춰라.** 다음 세션에서 `claude plugin list`에 `<모듈명>@skills-dir` 확인 → 스킬 발동 테스트.

## DoD (이 스킬이 관통시켜야 할 것)
trivial 모듈이 [인터뷰(분해제안·로드맵·preflight·ADR) → 볼트노트+MOC+ADR → 스캐폴드 → basename검사 통과 → (재시작 후)로드]까지. 설계조력 산출물(로드맵·preflight·ADR)이 **실재**해야 통과(산출물 ≠ 게이트, 실제 내용 있어야).
