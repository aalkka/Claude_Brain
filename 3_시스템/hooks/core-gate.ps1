# 외부뇌 코어 게이트 2층 — PreToolUse (ADR-006)
# 1층(permissions.ask)이 못 잡는 Bash/PowerShell 경유 쓰기·신규 파일 생성을 잡고,
# 코어 접촉에 준수사항을 실어 보낸다. 상시 토큰 0 — 발동 시에만 출력.
#
# 검사 대상 = 도구별로 분리한다. raw 전체를 보면 노트 본문이 'CLAUDE.md'를
# 언급하기만 해도 걸린다(2026-07-30 실측: 모든 편집이 승인 요구 → 게이트 피로).
# 성능: PS 5.1의 ConvertFrom-Json이 ~150ms라 쓰지 않는다. 정규식 2회로 끝낸다(217ms, 스폰 하한 176ms).
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$raw = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($raw)) { exit 0 }

# ── 1. 도구 판별. 읽기 도구는 게이트 대상이 아니다.
if ($raw -notmatch '"tool_name"\s*:\s*"([^"]+)"') { exit 0 }
$tool = $Matches[1]
if ($tool -in 'Read','Grep','Glob','NotebookRead') { exit 0 }

# ── 2. 검사 문자열 추출 — 파일 도구는 경로만, 셸 도구는 명령만. 본문은 보지 않는다.
$probe = ''
if ($tool -in 'Edit','Write','NotebookEdit','MultiEdit') {
    if ($raw -match '"file_path"\s*:\s*"((?:[^"\\]|\\.)*)"') { $probe = $Matches[1] }
} elseif ($tool -in 'Bash','PowerShell') {
    if ($raw -match '"command"\s*:\s*"((?:[^"\\]|\\.)*)"') { $probe = $Matches[1] }
} else { exit 0 }
if ([string]::IsNullOrWhiteSpace($probe)) { exit 0 }

$p = $probe -replace '\\\\', '/' -replace '\\', '/'

# ── 3. 코어 경로 매치
if ($p -notmatch '(CLAUDE\.md|3_시스템/hooks/[^\s",]*|3_시스템/search\.py|3_시스템/conventions\.md|\.claude/settings\.json)') { exit 0 }
$target = $Matches[1]

# ── 4. 셸 도구는 '쓰기 동사'가 함께 있을 때만 건다.
# 경로만 보면 `grep CLAUDE.md`·`cat conventions.md`·`git log -- CLAUDE.md`가
# 전부 걸려 게이트 피로를 만든다(오탐이 게이트를 죽이는 주 경로).
# `py`는 -c(인라인 코드)에만 건다. 넓히면 `py -3 3_시스템/search.py`(weekly 4스텝·search 스킬)가
# 걸려 무인 실행이 승인 대기로 죽는다. 코어 스크립트 '실행'과 코어 '쓰기'를 가르는 선이다.
if ($tool -in 'Bash','PowerShell') {
    if ($p -notmatch '>|sed\s+-i|tee\b|\bcp\b|\bmv\b|\brm\b|\btruncate\b|Set-Content|Add-Content|Out-File|New-Item|Remove-Item|Move-Item|Copy-Item|\bpython\d?\b|\bnode\b|\bperl\b|git\s+(checkout|restore|apply|reset)|\bpy\s+(-\d(\.\d+)?\s+)?-c\b|WriteAll\w+|AppendAll\w+') { exit 0 }
}

# ── 5. 발동 — 관측 로그(_index는 gitignore) 후 ask + 준수사항
$mode = if ($raw -match '"permission_mode"\s*:\s*"([^"]+)"') { $Matches[1] } else { '-' }
$vault = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Add-Content -Path (Join-Path $vault '3_시스템/_index/core-gate.log') `
    -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [$mode] $tool $target" -ErrorAction SilentlyContinue

$reason = @'
⚠ 코어파일 수정 — ADR-006 게이트

■ 0. 필요한가 (먼저 답할 것)
  · 강제층 추가는 실측 2건 이상에서만(§9). 1건이면 보류하고 계측기부터.
  · 이미 있는 것으로 되는가 — 네이티브 기능·기존 훅·git 이력. 새로 짓기 전에 확인.
  · 모듈발이면 전 볼트 일반규칙일 때만 승격(ADR-004 8항). 모듈 특수면 모듈 훅으로.

■ 1. 절차
  · 발견 즉시 고치지 않는다. diff 제시 → 승인 → ADR.
  · "고쳐라"로 읽히는 지시도 코어 수정 권한까지 자동 확장되지 않는다.

■ 2. 검증 (코어에 넣기 전)
  · 격리 환경에서 실행. 07-27: 이 단계를 건너뛴 코드가 실제 문법오류였다.
  · 기존 케이스 회귀 0 + 회귀 케이스가 '이번 변경이 건드리는 축'을 덮는가.
    07-30: 성능만 고치려던 변경이 판정 로직을 바꿨는데 케이스에 그 축이 없어 통과했다.
  · 검증은 powershell(5.1)로. pwsh 7은 UTF-8 기본이라 인코딩 버그를 못 잡는다.

■ 3. 격리성 — 의도한 것만 바뀌는가
  · 리팩터링·정리·개선을 끼워넣지 않는다. 수정 사유에 없는 변경 = 별건.
  · 외부 의존성 금지. 미선언 의존성은 fail-closed로 전 커밋을 막는다(07-27 실증).
  · 실패 방향을 명시적으로 정한다 — 검증 실패는 막고, 도구 부재는 통과(fail-open).

■ 4. 최소 표면
  · 같은 목적이면 한 파일·최소 줄. pre-commit이 권위 게이트, stop-check는 손대지 않는다.
  · 검사 대상 경로를 조용히 넓히지 않는다(07-27 부수 위반: _ref 무단 확대).

■ 5. 비용
  · 상시 토큰: T0(CLAUDE.md)·T1(recent·open-loops)·훅 출력 증가 금지. 늘리면 one-in-one-out.
  · 지연: 훅은 발동마다 PowerShell 스폰(176ms 하한). SessionStart 23초·Stop +0.28s 전례.

■ 6. 환경 (이 볼트의 상습 실패모드 — incident 4건)
  · .ps1은 UTF-8 BOM 저장. PS 5.1이 cp949로 오독한다.
  · 한글 경로(3_시스템)·한글 유저명이 글롭·로캘·stdout에서 깨진다.
  · 줄바꿈은 .gitattributes가 강제. 파이썬 writer에 newline 지정 금지.

■ 7. 파급
  · 무인 실행(weekly-review 스케줄)이 이 변경으로 죽지 않는가 — 승인 대기 = 조용한 사망.
  · dist(배포 템플릿) 오염 여부. 흘러가면 신규 사용자 볼트가 같은 결함을 받는다.
  · 롤백 지점(커밋 해시)을 먼저 확보.

전문·근거 incident → 3_시스템/_ref/코어수정-준수사항-체크리스트.md
'@

@{ hookSpecificOutput = @{
    hookEventName            = 'PreToolUse'
    permissionDecision       = 'ask'
    permissionDecisionReason = $reason
    additionalContext        = $reason
} } | ConvertTo-Json -Depth 5 -Compress
exit 0
