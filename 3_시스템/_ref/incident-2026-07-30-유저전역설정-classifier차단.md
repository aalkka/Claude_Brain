---
type: incident
title: 유저 전역 settings.json 쓰기가 classifier에 차단됨 (승인 프롬프트 없이)
created: 2026-07-30
updated: 2026-07-30
tags: [권한, 설정, 플러그인, classifier, 절차]
links: ["[[incident-2026-07-27-weekly자동실행-권한대기-사망]]", "[[measure-module-toggle]]"]
status: active
---

# 유저 전역 settings.json 쓰기 차단 — 승인 프롬프트 없이 즉시 거부

## 증상

caveman 플러그인을 끄기 위해 `~/.claude/settings.json`을 수정해야 했다. `Write` 시도 → 거부. `Edit`(부분 치환) 시도 → 거부. **둘 다 사용자에게 승인 프롬프트가 뜨지 않았다.**

```
Permission for this action was denied by the Claude Code auto mode classifier. Reason: Blocked by classifier.
```

같은 세션에서 볼트 내부 `C:\Claude_Brain\.claude\settings.local.json` 편집은 **통과했다.** 파일 종류(설정 JSON)가 아니라 **경로 — 유저 전역이냐 프로젝트냐**가 갈랐다.

## 근본원인

auto mode classifier가 유저 전역 설정 파일 쓰기를 고위험으로 분류하고 **승인 경로로 넘기지 않고 즉시 거부**한다. 사용자가 허용할 기회 자체가 없다.

⚠ **확정 아님.** 분류기 규칙을 직접 보지 못했다. `permissions.allow`로 우회 가능한지도 미검증 — 검증하려면 규칙을 추가해 봐야 하는데, 그건 승인 게이트를 영구적으로 넓히는 변경이라 시도하지 않았다.

## 해결

사용자 직접 편집. Claude는 **목표 상태 JSON 전문**과 검증 명령만 제공한다.

## 절차 (재발 시)

유저 전역 `~/.claude/settings.json`을 바꿔야 하면:

1. **도구로 시도하지 않는다.** 차단이 확정적이라 시도는 턴만 소모한다.
2. **부분 지시가 아니라 목표 상태 전문**을 준다. 이번에 "3건 삭제"로 지시했더니 1건만 반영된 중간 상태(`caveman` 제거 ✓ / `statusLine`·`skillOverrides` 잔존)가 나왔다.
3. 적용 후 **디스크를 다시 읽는다.** 사용자 화면과 디스크가 다를 수 있다 — 미저장, 다른 버퍼, 토글 UI의 메모리 상태. 이번에 이 불일치에 **2턴**을 썼다. 사용자가 "바꿨다"고 해도 디스크가 권위다.
4. `LastWriteTime`을 함께 본다. 저장 여부를 가른다.
5. 검증은 문자열이 아니라 파싱으로:

```powershell
$s = Get-Content "$env:USERPROFILE\.claude\settings.json" -Raw -Encoding UTF8 | ConvertFrom-Json
"keys: " + ($s.PSObject.Properties.Name -join ', ')
"caveman: " + [bool]($s.enabledPlugins.PSObject.Properties.Name -contains 'caveman@caveman')
```

## 부수 사실

- **`enabledPlugins`의 `false`는 키 삭제와 다르다.** `false`는 명시적 비활성 기록으로 남는다. 이번에 발견한 `"module-forge@skills-dir": false`를 오토글로 **오인했는데**, 실제 출처는 [[measure-module-toggle]] 2/2단계 측정이었다. → **설정에서 예상 밖의 값을 보면 오조작으로 단정하기 전에 `_ref/` 측정 기록부터 찾는다.**
- 플러그인을 꺼도 `~/.claude/.caveman-active` 같은 상태 파일과 캐시 디렉터리는 남는다. `statusLine`이 그 파일을 읽으면 **배지가 거짓말한다** → 플러그인 off와 `statusLine` 키 처리를 같은 편집에서 해야 한다.

## 권한 실패는 두 종류다

| | [[incident-2026-07-27-weekly자동실행-권한대기-사망]] | 이 건 |
|---|---|---|
| 기제 | 승인 프롬프트가 뜨고 응답할 사람이 없음 | 프롬프트 없이 classifier가 즉시 거부 |
| 증상 | 무한 대기 후 abort, 조용한 실패 | 즉시 에러, 시끄러운 실패 |
| 대응 | 태스크 스코프 승인 사전 등록 | 사용자 직접 수행 |

**"권한이 없다"를 한 덩어리로 다루면 대응을 틀린다.**

> [!info]- 관련 노트 %%sl%%
> [[incident-2026-07-30-조건부-instruction-로딩-미작동]]
