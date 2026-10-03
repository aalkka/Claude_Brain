# PermissionRequest 프로브 (2026-08-22, 코어 게이트 개정 6).
# 계약에 있으나 이 환경에서 발화하는지 미확인이라 '판정만' 한다 — 아무것도 막지 않고
# 아무것도 출력하지 않는다(출력하면 모델 컨텍스트에 상시 비용이 붙는다).
# 목적: 코어 게이트 미결 1 '승인 프롬프트 관측 불가'를 푸는지 본다. 오탐률을 사용자 보고
# 없이 계측할 수 있게 되면 이 프로브를 계측기로 승격하고, 발화가 없으면 제거한다.
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$raw = [Console]::In.ReadToEnd()
$v = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$t = if ($raw -match '"tool_name"\s*:\s*"([^"]+)"') { $Matches[1] } else { '-' }
$m = if ($raw -match '"permission_mode"\s*:\s*"([^"]+)"') { $Matches[1] } else { '-' }
# 원문은 남기지 않는다(경로·명령이 그대로 쌓인다). 발화 사실·도구·크기만.
Add-Content -Path (Join-Path $v '3_시스템/_index/permission-probe.log') `
    -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [$m] $t $($raw.Length)B" -Encoding UTF8
exit 0
