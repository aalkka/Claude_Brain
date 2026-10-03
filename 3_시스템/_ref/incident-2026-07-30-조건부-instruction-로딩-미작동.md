---
type: incident
title: 조건부 instruction 로딩 미작동 — rules paths·중첩 CLAUDE.md 양쪽 무응답
created: 2026-07-30
updated: 2026-07-30
tags: [훅, 규약, 조건부로딩, rules, 토큰, 진단]
links: ["[[incident-2026-07-30-유저전역설정-classifier차단]]"]
status: active
---

# 조건부 instruction 로딩 미작동

## 증상

코어파일 게이트를 상시 토큰 0으로 만들기 위해 조건부 규약 로딩을 검증했다. **두 메커니즘 모두 발동하지 않았다.**

| 프로브 | 메커니즘 | `paths`/대상 | 결과 |
|---|---|---|---|
| `.claude/rules/probe-conditional-load.md` | rules `paths:` | `3_시스템/conventions.md` (한글) | 미발동 |
| `.claude/rules/probe-ascii-control.md` | rules `paths:` | `README.md` (ASCII) | 미발동 |
| `3_시스템/hooks/CLAUDE.md` | 중첩 CLAUDE.md | 해당 디렉터리 파일 Read | 미발동 |
| `.claude/rules/probe-always.md` | rules, `paths` 없음(상시) | — | **미판정** (다음 세션) |

각 프로브는 고유 마커 문자열을 담았고, 대상 파일을 `Read`한 뒤 컨텍스트에 마커가 나타나는지로 판정했다. **재시작 전후 모두 미출현.**

환경: Claude Code 2.1.220 · Windows 11 · 데스크톱 앱.

## 근본원인

⚠ **미확정.** 아래는 배제된 것과 남은 것.

**배제됨**
- *한글 경로* — ASCII 대조군(`README.md`)도 실패했다. 제작자 볼트의 상습 실패모드(CP949 로캘·writer CRLF·caveman 경로버그)였으나 이번엔 아니다.
- *세션 중 생성* — 재시작 후에도 동일.
- *파일 형식* — 프론트매터·경로 모두 문서 스펙과 일치함을 확인.
- *rules 고유 버그* — 중첩 CLAUDE.md는 별개 메커니즘인데 함께 실패했다.

- *디렉터리 미스캔* — `paths:` **없는** 프로브(`probe-always.md`)는 서브세션에서 마커 `ALWY`가 **정상 출현**했다. `.claude/rules/`는 읽힌다.

**확정된 범위**

**고장난 것은 `paths:` 조건부 스코프 기능 하나뿐이다.** rules 디렉터리 스캔·상시 로드는 정상. 공개 이슈 [#16853](https://github.com/anthropics/claude-code/issues/16853)(path-scoped rules 자동 로드 안 됨)과 증상 일치. 관련 [#22170](https://github.com/anthropics/claude-code/issues/22170)·[#23569](https://github.com/anthropics/claude-code/issues/23569). 중첩 CLAUDE.md도 함께 실패한 이유는 미상.

## 해결

**조건부 로딩에 의존하지 않는 설계로 전환.** 게이트를 `permissions` + 훅으로 세운다 — 둘 다 이 환경에서 작동이 검증된 경로다.

```json
{
  "permissions": {
    "ask": ["Edit(/CLAUDE.md)", "Edit(/3_시스템/hooks/**)", "Edit(/3_시스템/search.py)",
            "Edit(/3_시스템/conventions.md)", "Edit(/.claude/settings.json)"]
  }
}
```

- **차단 = `permissions.ask`.** 공식 문서: *"Hook decisions don't bypass permission rules… a matching ask rule still prompts even when the hook returned allow."* 훅보다 강하고 훅이 죽어도 남는다.
- **주입 = `PreToolUse` 훅의 `permissionDecisionReason`.** 준수사항을 승인 프롬프트에 실어 보낸다. 발동 시에만 나가므로 **상시 토큰 0**.
- 두 층은 서로 독립이라 한쪽이 죽어도 다른 쪽이 산다.

문법 함정 (공식 문서, v2.1.210+):
- **`Write(path)`·`NotebookEdit(path)` 경로 규칙은 무시된다** — 규칙을 받고 시작 시 경고만 낸다. `Edit(...)`만 파일 권한 검사에 쓰이며 모든 편집 도구를 커버.
- `/path`는 절대경로가 아니라 **설정 소스 기준**. 절대경로는 `//path`.
- deny·ask 규칙은 Bash의 `cat`·`head`·`tail`·`sed`에도 적용된다. 단 임의 서브프로세스(python/node가 직접 파일 여는 것)는 미적용.

## 재발방지

- **하네스 기능은 문서에 있어도 작동을 가정하지 않는다.** 제작자 볼트에서 07-30 하루에만 같은 유형이 3건 — caveman `skillOverrides` 무효 · 커스텀 output style 리마인더 미수신 · 조건부 로딩 미작동. **문서→프로브→판정**을 기본 절차로 한다.
- **프로브는 대조군과 함께 만든다.** ASCII 대조군이 없었으면 한글 경로를 범인으로 오인하고 며칠을 썼다. 판정표를 프로브 파일 안에 미리 적어두면 결과 해석이 즉시 끝난다.
- **조건부 로딩에 안전 장치를 얹지 않는다.** 미발동이 조용하기 때문이다. 안전은 `permissions`(하네스 강제)나 훅(exit 2)처럼 실패가 시끄러운 층에 둔다.

## 부수 — 하네스 설정은 세션 중 반영되지 않는다 (실측)

`permissions.ask`를 `settings.local.json`에 세션 중 추가하고 대상 파일을 `Edit` → **승인 프롬프트 없이 통과.** 한글 경로(`Edit(/3_시스템/_index/permtest.md)`)와 ASCII 대조군(`Edit(/permtest2.md)`) **양쪽 모두** 미발동 → 한글 경로 원인 아님.

→ **rules도 permissions도 세션 중 변경이 즉시 반영되지 않는다.** 프로브 설계 시 "재시작 1회 = 판정 1회"로 잡고, **검증 항목을 모아 한 번에 판정**해야 한다. 이번 세션은 이 사실을 몰라 재시작을 2회 소모했다.

## 부수 — 서브세션 계측기 개통 (관측자 효과 없는 판정 도구)

`claude -p`가 처음엔 `Failed to authenticate: OAuth session expired`로 막혔다. 진단: CLI는 `C:\Users\<사용자>\.local\bin\claude.exe`(네이티브 설치, npm 전역 없음)이고 `.credentials.json`이 07-27에 멈춰 있었다. **데스크톱 앱 로그인과 CLI 자격증명은 별개다** — 터미널에서 `claude` → `/login`으로 해결.

개통 후 **재시작 없이** 세 판정을 끝냈다. 새 세션이 뜨므로 설정이 새로 로드되고, 무엇보다 **내가 나를 관측하지 않는다.** 코어 게이트 설계 노트 §9.5의 라우터 실패 감지, 골든셋 hit@8 재측정, 스킬 발동률 측정에 그대로 쓸 수 있다.

사용법 함정:
- 프롬프트를 **먼저**, 플래그를 뒤에. `claude -p --allowedTools "Edit" "프롬프트"`는 `Error: Input must be provided either through stdin or as a prompt argument`로 죽는다.
- `-p`는 비대화형이라 **파일 편집이 기본 차단**된다. 권한을 재려면 `--allowedTools "Edit"`으로 기저선을 열어야 한다.
- 매 호출이 SessionStart/End 훅을 발동시킨다(`Hook cancelled` 로그는 정상 종료 시 나타남).

## 실험 설계 교훈 — 음성 대조군 없는 긍정 결과는 거짓일 수 있다

`permissions.ask` 검증에서 한글·ASCII 대상 둘 다 `BLOCKED`가 나왔다. **여기서 멈췄으면 "ask 작동 확인"이라는 거짓 확정을 했다.** 대조군(ask에 없는 파일)을 돌리니 그것도 `BLOCKED` — 원인은 ask가 아니라 `-p` 모드의 기본 편집 차단이었다.

`--allowedTools "Edit"`으로 기저선을 연 뒤 재측정한 결과가 진짜다:

| 실험 | 결과 |
|---|---|
| 대조군(`ask` 미등록) | **SUCCESS** |
| ASCII 경로 `ask` 등록 | **BLOCKED** |
| **한글 경로 `ask` 등록** | **BLOCKED** |

→ **`permissions.ask`는 한글 경로에서 작동하고, `--allowedTools`로 allow를 열어둬도 막는다**(ask > allow 우선순위 실측 확인). 코어 게이트 설계 노트 §10.3 차단층이 검증됐다.

**규칙: 차단을 관측했으면 통과 케이스도 관측한다.** 안 그러면 "막혔다"가 게이트의 증거인지 환경의 기본값인지 갈리지 않는다. «완료 판단 = 산출물 존재 vs 게이트 통과» 패턴의 변종 — 저기서는 산출물이 있어도 통과가 아니었고, 여기서는 차단이 있어도 게이트가 아니었다.

### 두 번째 설계 오류 — 반대 방향

게이트를 실제 배치한 뒤, 파일을 망가뜨리지 않으려고 **존재하지 않는 문자열**(`ZZZ_NONEXISTENT_STRING_QQQ`)로 Edit을 시도했다. 결과 `NOTFOUND` → "ask 규칙이 발동하지 않는다"로 읽고 **작동하는 게이트를 미작동으로 판정**했다. 원인을 `settings.json` vs `settings.local.json` 차이로 오인해 서브세션 2회를 더 낭비했다.

실제 원인: **권한 검사는 도구 인자 검증 이후에 온다.** `old_string`이 파일에 없으면 권한 층에 닿기 전에 에러가 난다.

실존 문자열로 다시 재니 결과가 뒤집혔다:

| 실험 | 결과 |
|---|---|
| 보호 대상(`3_시스템/hooks/gatetest.tmp`, 글롭 `Edit(/3_시스템/hooks/**)`) | **BLOCKED** |
| 비보호(`3_시스템/_index/gatetest.md`) | **SUCCESS** |
| 보호 대상 파일 내용 | 무변경 |

**규칙: 권한을 테스트할 때는 "도구가 실제로 성공할 수 있는 입력"을 준다.** 안전하려고 실패하게 만든 입력은 권한 층에 닿지도 못한다. 대상 파괴가 걱정되면 입력을 무해하게 만들 게 아니라 **대상을 무해하게** 만든다(보호 글롭 안에 임시 파일을 놓고 그것을 친다).

## 배치 사고 — 유저 전역에 넣으면 볼트가 보호되지 않는다

사용자가 게이트 규칙을 `~/.claude/settings.json`(유저 전역)에 배치했다. 두 가지 문제:

1. **JSON 문법 오류** — `"theme": "auto"` 뒤 쉼표 누락. 이 상태면 유저 전역 설정 전체가 파싱 실패한다(`enabledPlugins`·`theme`·`tui` 무효화).
2. **경로 앵커가 다르다** — 유저 설정에서 `/path`는 `~/.claude/path`로 앵커된다. 공식 문서: *"A deny rule such as `Read(/secrets/**)` in user settings blocks `~/.claude/secrets/**`, not a `secrets` directory in your project."* → `Edit(/3_시스템/hooks/**)`가 `~/.claude/3_시스템/hooks/**`(부재 경로)를 가리켜 **볼트는 전혀 보호되지 않는다.**

**게이트는 프로젝트 `.claude/settings.json`에 둔다** — 앵커가 프로젝트 루트이고, git에 추적되어 배포판에도 딸려간다. 유저 전역 쓰기는 classifier가 차단하므로(→ [[incident-2026-07-30-유저전역설정-classifier차단]]) 원복은 사용자 직접 수행.

