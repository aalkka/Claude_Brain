---
type: semantic
title: module-forge 토글 누수 측정
created: 2026-07-30
updated: 2026-07-30
status: active
tags: [측정, module-forge, 토큰, 컨텍스트, 플러그인, 토글]
links: []
source: session
confidence: verified
---
# module-forge 토글 누수 측정

2단계 실험의 기준선(1/2단계). module-forge를 ON/OFF로 토글하며 `/context` 상주 토큰을 대조해 "꺼도 안 빠지는" 누수가 있는지 확인한다. 근거 노트: 제작자 볼트의 토큰 절감 모듈 노트(배포판 미포함). 선행 실측(사용자 지정): 이 대화의 description 바이트 표.

이 파일은 측정값만 기록한다. 단계 간 델타·해석은 2단계(OFF) 완료 후 별도 섹션에 추가.

## 2026-07-30 · 1/2단계 · module-forge = ON

### 컨텍스트 사용 (`/context` 직접 실행, 사용자 붙여넣기)

모델: `claude-sonnet-5` · 총합: **80.3k / 967k (8%)**

| Category | Tokens | % |
|---|---|---|
| System prompt | 9.8k | 1.0% |
| System tools | 18.5k | 1.9% |
| MCP tools | 7.1k | 0.7% |
| MCP tools (deferred) | 25.7k | 2.7% |
| System tools (deferred) | 17.5k | 1.8% |
| Custom agents | 550 | 0.1% |
| Memory files | 1.3k | 0.1% |
| Skills | 5.3k | 0.5% |
| Messages | 38.1k | 3.9% |
| Free space | 853.4k | 88.3% |
| Autocompact buffer | 33k | 3.4% |

필수 4행(요청 지정):

| 행 | 값 |
|---|---|
| System prompt | 9.8k (1.0%) |
| Skills | 5.3k (0.5%) |
| Custom agents | 550 (0.1%) |
| 총 상주 토큰 | 80.3k / 967k (8%) |

### Skills 세부 — module-forge 관련 행만 발췌

| Skill | Source | Tokens |
|---|---|---|
| module-forge | Project | ~60 |
| module-forge:check | Plugin (module-forge) | ~60 |
| module-forge:new | Plugin (module-forge) | ~70 |

주: 루트 `module-forge`는 Source=Project, 하위 `check`/`new`는 Source=Plugin (module-forge)로 분리 표기됨 — skills-dir 플러그인화 방식 차이. 원본 전체 Skills 표(46행)는 이 세션 트랜스크립트에 있음, 여기 미전재.

### 통제 변수

| 변수 | 값 | 출처 |
|---|---|---|
| 볼트 스킬 수 | 15 (`SKILL.md` 파일 수, `.claude/skills/**` 재귀) | `Glob` 실측 |
| 활성 플러그인 (`claude plugin list`) | caveman@caveman (scope: user, status: enabled) · module-forge@skills-dir (scope: project, status: loaded) · study-helper@skills-dir (scope: project, status: loaded) | Bash 실행 |
| enabledPlugins | `{"caveman@caveman": true}` | `~/.claude/settings.json` |
| 모델 | Sonnet 5 (`claude-sonnet-5`) | 이 세션 `/context` |

파일 신설 여부: `3_시스템/_ref/measure-module-toggle.md` 이번에 신규 생성. `_ref/`는 `_` 접두 폴더로 MOC 등재 규약 면제 대상(`3_시스템/conventions.md` §파일명·폴더 규약) — MOC 미등재.

## 2026-07-30 · 2/2단계 · module-forge = OFF

토글 방법 확인(실측): `~/.claude/settings.json`의 `enabledPlugins`에 `"module-forge@skills-dir": false` 추가. `skillOverrides`가 아님 — 별도 메커니즘. 세션 재시작 후 반영(SessionStart:resume 훅 발화 확인).

### 컨텍스트 사용 (`/context` 직접 실행, 사용자 붙여넣기)

모델: `claude-sonnet-5` · 총합: **97.4k / 967k (10%)**

| Category | Tokens | % |
|---|---|---|
| System prompt | 9.8k | 1.0% |
| System tools | 18.7k | 1.9% |
| MCP tools | 7.1k | 0.7% |
| MCP tools (deferred) | 25.7k | 2.7% |
| System tools (deferred) | 17.5k | 1.8% |
| Custom agents | 550 | 0.1% |
| Memory files | 1.3k | 0.1% |
| Skills | 5.1k | 0.5% |
| Messages | 56.8k | 5.9% |
| Free space | 834.7k | 86.3% |
| Autocompact buffer | 33k | 3.4% |

필수 4행(요청 지정):

| 행 | 값 |
|---|---|
| System prompt | 9.8k (1.0%) |
| Skills | 5.1k (0.5%) |
| Custom agents | 550 (0.1%) |
| 총 상주 토큰 | 97.4k / 967k (10%) |

### Skills 세부 — module-forge 관련 행

0행. `module-forge`(Project) · `module-forge:check`(Plugin) · `module-forge:new`(Plugin) 3행 전부 Skills 표에서 소멸 확인(1단계 대비).

### 통제 변수

| 변수 | 값 | 출처 |
|---|---|---|
| 볼트 스킬 수 | 15 (`SKILL.md` 파일 수, `.claude/skills/**` 재귀) — 1단계와 동일, 디스크 파일 그대로(디세이블=로드차단이지 파일삭제 아님) | `Glob` 실측 |
| 활성 플러그인 (`claude plugin list`) | caveman@caveman (scope: user, status: enabled) · study-helper@skills-dir (scope: project, status: loaded) · module-forge@skills-dir (scope: project, **status: disabled**) | Bash 실행 |
| enabledPlugins | `{"caveman@caveman": true, "module-forge@skills-dir": false}` — 1단계 대비 `module-forge@skills-dir: false` 신규 추가 | `~/.claude/settings.json` |
| 모델 | Sonnet 5 (`claude-sonnet-5`) — 1단계와 동일 | 이 세션 `/context` |

### 1↔2단계 원값 대조 (산술 델타만, 해석 없음)

| Category | 1단계(ON) | 2단계(OFF) | Δ |
|---|---|---|---|
| System prompt | 9.8k | 9.8k | 0 |
| System tools | 18.5k | 18.7k | +0.2k |
| MCP tools | 7.1k | 7.1k | 0 |
| MCP tools (deferred) | 25.7k | 25.7k | 0 |
| System tools (deferred) | 17.5k | 17.5k | 0 |
| Custom agents | 550 | 550 | 0 |
| Memory files | 1.3k | 1.3k | 0 |
| Skills | 5.3k | 5.1k | −0.2k |
| Messages | 38.1k | 56.8k | +18.7k |
| Free space | 853.4k | 834.7k | −18.7k |
| Autocompact buffer | 33k | 33k | 0 |
| **총 상주** | 80.3k | 97.4k | +17.1k |

Messages/Free space 델타는 대화 진행에 따른 자연 증가분(세션 내 턴 누적) — 토글과 무관, 참고용 병기만 함. 나머지 행 해석·결론은 미작성(사용자 지정 보류).

