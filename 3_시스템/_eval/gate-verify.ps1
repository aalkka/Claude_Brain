<#
  코어 게이트 회귀 검증 하네스 (ADR-006 개정 1, 2026-08-02 승격)

  용법 (반드시 powershell 5.1 — 체크리스트 §2):
    powershell -NoProfile -File 3_시스템/_eval/gate-verify.ps1
    powershell -NoProfile -File 3_시스템/_eval/gate-verify.ps1 -Baseline <패치 전 사본>

  훅을 임시 샌드박스로 복사해 실행한다. 제자리에서 돌리면 실볼트 core-gate.log가
  오염되고 weekly 7스텝의 발동 수가 틀어진다(ADR-006 개정 2 교훈 ⓑ).

  종료코드 = 불일치 건수. 0이 아니면 코어에 넣지 않는다.
#>
param(
  [string]$Hook,
  [string]$Baseline
)
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
# PS 5.1의 $OutputEncoding 기본값은 ASCII다. 이대로 파이프하면 페이로드의 `3_시스템`이
# `?`로 깨져 §3 코어 경로 매치가 무조건 실패하고, 한글 경로 케이스가 전부 거짓 통과한다.
$OutputEncoding = New-Object System.Text.UTF8Encoding($false)

if (-not $Hook) { $Hook = Join-Path (Split-Path $PSScriptRoot -Parent) 'hooks\core-gate.ps1' }
if (-not (Test-Path $Hook)) { "hook not found: $Hook"; exit 99 }

# ── 정적 검사 (§6 환경 · §2 검증)
$bytes = [System.IO.File]::ReadAllBytes($Hook)
$bom   = ($bytes[0..2]) -join ','
$txt   = [System.IO.File]::ReadAllText($Hook)
$crlf  = ([regex]::Matches($txt, "`r`n")).Count
$perr  = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($Hook, [ref]$null, [ref]$perr)

"hook      = $Hook"
"PS        = $($PSVersionTable.PSVersion)" + $(if ($PSVersionTable.PSVersion.Major -eq 5) { '  OK' } else { '  *** must be 5.1 (checklist S2) ***' })
"BOM       = $bom" + $(if ($bom -eq '239,187,191') { '  OK' } else { '  *** missing (checklist S6) ***' })
"syntax    = " + @($perr).Count + " error(s)"
foreach ($e in @($perr)) { '  ' + $e.Message }
"CRLF      = $crlf" + $(if ($crlf -eq 0) { '  OK (eol=lf)' } else { '  *** churn ***' })

# ── 샌드박스. 훅의 $vault 계산이 <sand> 를 가리키도록 <sand>\v\hooks 에 둔다.
$sand      = Join-Path ([System.IO.Path]::GetTempPath()) ('gate-verify-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
$sandHooks = Join-Path $sand 'v\hooks'
$sandLogD  = Join-Path $sand '3_시스템\_index'
New-Item -ItemType Directory -Force $sandHooks | Out-Null
New-Item -ItemType Directory -Force $sandLogD  | Out-Null
$sandLog  = Join-Path $sandLogD 'core-gate.log'
$sandHook = Join-Path $sandHooks 'core-gate.ps1'
Copy-Item $Hook $sandHook -Force
$sandBase = $null
if ($Baseline) {
  if (-not (Test-Path $Baseline)) { "baseline not found: $Baseline"; exit 99 }
  $sandBase = Join-Path $sandHooks 'baseline.ps1'
  Copy-Item $Baseline $sandBase -Force
}

function Invoke-Case($gate, $payload) {
  Remove-Item $sandLog -Force -ErrorAction SilentlyContinue
  $out  = $payload | & powershell -NoProfile -File $gate
  $fire = if ([string]::IsNullOrWhiteSpace($out)) { 'NOFIRE' } else { 'FIRE' }
  $line = (Get-Content $sandLog -Encoding UTF8 -ErrorAction SilentlyContinue | Select-Object -Last 1)
  New-Object psobject -Property @{ Fire = $fire; Log = $line }
}

$rows = @(Get-Content (Join-Path $PSScriptRoot 'gate-cases.tsv') -Encoding UTF8 |
          Where-Object { $_.Trim() -and -not $_.StartsWith('#') })
$fail = 0
$changed = @()
''
if ($sandBase) { "case                                 base    hook    want    log     verdict" }
else           { "case                                 hook    want    log     verdict" }

foreach ($row in $rows) {
  $f = $row -split "`t", 4
  $want = $f[0].Trim(); $label = $f[1].Trim(); $logWant = $f[2].Trim(); $payload = $f[3]

  $r = Invoke-Case $sandHook $payload
  $bad = @()
  if ($r.Fire -ne $want) { $bad += 'fire' }

  $logOk = '-'
  if ($logWant -ne '-') {
    if ($r.Log -and $r.Log.EndsWith($logWant)) { $logOk = 'OK' } else { $logOk = 'BAD'; $bad += 'log' }
  }
  if ($bad.Count) { $fail++ }
  $verdict = if ($bad.Count) { '*** MISMATCH: ' + ($bad -join '+') + ' ***' } else { 'OK' }

  if ($sandBase) {
    $b = (Invoke-Case $sandBase $payload).Fire
    if ($b -ne $r.Fire) { $changed += $label }
    "{0,-36} {1,-7} {2,-7} {3,-7} {4,-7} {5}" -f $label, $b, $r.Fire, $want, $logOk, $verdict
  } else {
    "{0,-36} {1,-7} {2,-7} {3,-7} {4}" -f $label, $r.Fire, $want, $logOk, $verdict
  }
}

''
"cases = $($rows.Count)   mismatches = $fail"
if ($sandBase) {
  "differs from baseline on: " + $(if ($changed) { $changed -join ' | ' } else { 'none' })
}
Remove-Item $sand -Recurse -Force -ErrorAction SilentlyContinue
exit $fail
