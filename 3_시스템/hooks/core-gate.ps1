# 외부뇌 코어 게이트 2층 — PreToolUse (ADR-006)
# 1층(permissions.ask)이 못 잡는 Bash/PowerShell 경유 쓰기·신규 파일 생성을 잡고,
# 코어 접촉에 준수사항을 실어 보낸다. 상시 토큰 0 — 발동 시에만 출력.
#
# 검사 대상 = 도구별로 분리한다. raw 전체를 보면 노트 본문이 'CLAUDE.md'를
# 언급하기만 해도 걸린다(2026-07-30 실측: 모든 편집이 승인 요구 → 게이트 피로).
# 성능: PS 5.1의 ConvertFrom-Json이 ~150ms라 쓰지 않는다. 정규식으로 끝낸다.
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

# JSON 이스케이프된 따옴표를 먼저 되돌린다. 이 순서가 아니면 `\"`가 `/"`가 되어
# 인라인 코드 구간(-c "…")을 인식하지 못한다(2026-08-17 검증 N5·N6에서 드러남).
$p = $probe -replace '\\"', '"' -replace '\\\\', '/' -replace '\\', '/'

# ── 3. 코어 경로 매치. 절대경로면 이 볼트 안이어야 한다.
# dist 사본·git worktree·scratchpad 검증본은 코어가 아니다(2026-08-17 실측 27건).
$core = 'CLAUDE\.md|3_시스템/hooks/[^\s",;|&''<>)]*|3_시스템/search\.py|3_시스템/conventions\.md|\.claude/settings\.json|3_시스템/_index/\.core-token'
# 값싼 1차 검사를 먼저 한다. 대부분의 호출은 코어와 무관하고, 아래 절대경로 순회는
# 선택적 접두 + non-greedy 라 백트래킹이 붙는다 — 1차를 빼면 비코어 경로가
# 220ms→296ms 로 늘어난다(2026-08-17 실측). 상시 비용은 여기서 결정된다.
if ($p -notmatch ('(' + $core + ')')) { exit 0 }

# 무거운 판정(볼트 판정·절 분리·토큰)은 별도 파일로 뺀다. PowerShell 은 실행하지 않는
# 코드도 파싱·AST 생성 비용을 치르므로, 한 파일에 두면 코어와 무관한 모든 도구 호출이
# 그 값을 낸다(2026-08-17 실측: 실행 안 되는 코드만으로 +22ms). 주석은 비용이 없다.
# 파일이 없으면 통과시킨다 — 게이트 오작동이 볼트를 벽돌로 만들지 않게(ADR-006 fail-open).
# 다만 '조용히' 통과시키지는 않는다. 판정부만 사라지면 이 머리 파일은 멀쩡해 보여
# 게이트가 죽은 줄 아무도 모른다 — 로그를 남겨 weekly 7스텝이 잡게 한다.
$decide = Join-Path $PSScriptRoot 'core-gate-decide.ps1'
if (-not (Test-Path $decide)) {
    $v = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    Add-Content -Path (Join-Path $v '3_시스템/_index/core-gate.log') `
        -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [-] GATE-BROKEN(decide 없음) $tool -" -ErrorAction SilentlyContinue
    exit 0
}
. $decide
exit 0
