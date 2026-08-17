<#
  코어 게이트 회귀 검증 하네스 v2 — 판정(allow/deny/ask)과 토큰 축을 검사한다.
  기존 gate-verify.ps1 은 FIRE/NOFIRE 만 봤다. 토큰이 들어오면 '발동했으나 통과'가
  생기므로 그 축이 필요하다.

  케이스 5필드: 기대판정 <TAB> 라벨 <TAB> 로그기대(-=생략) <TAB> 토큰(-=없음, 파일내용을 \n 으로) <TAB> 페이로드
  기대판정 = NOFIRE | ASK | ALLOW | DENY

  페이로드의 볼트 절대경로는 플레이스홀더로 쓴다 — 볼트 경로를 박으면 다른 위치에
  설치한 사용자에게는 전 케이스가 '볼트 밖'으로 판정돼 하네스가 조용히 무력화된다.
    <VB> = 볼트 루트, JSON 이스케이프 백슬래시 (예 "<VB>\\CLAUDE.md")
    <VS> = 볼트 루트, 슬래시                  (예 '<VS>/CLAUDE.md')
  `<VB>_dist` 처럼 접미를 붙이면 볼트 밖 경로가 되어 접두 경계 검사에 쓸 수 있다.
#>
param([string]$Hook, [string]$Baseline, [string]$Cases)
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = New-Object System.Text.UTF8Encoding($false)

$here = Split-Path $MyInvocation.MyCommand.Path -Parent
# 볼트 = _eval 의 부모. 케이스 페이로드의 절대경로가 이 볼트를 가리켜야 판정이 산다.
$vaultRoot = Split-Path $here -Parent | Split-Path -Parent
if (-not $Hook)  { $Hook  = Join-Path $vaultRoot '3_시스템\hooks\core-gate.ps1' }
if (-not $Cases) { $Cases = Join-Path $here 'gate-cases.tsv' }
if (-not (Test-Path $Hook)) { "hook not found: $Hook"; exit 99 }

$bytes = [System.IO.File]::ReadAllBytes($Hook)
$bom   = ($bytes[0..2]) -join ','
$txt   = [System.IO.File]::ReadAllText($Hook)
$crlf  = ([regex]::Matches($txt, "`r`n")).Count
$perr  = $null
[void][System.Management.Automation.Language.Parser]::ParseFile($Hook, [ref]$null, [ref]$perr)
"hook   = $Hook"
"PS     = $($PSVersionTable.PSVersion)" + $(if ($PSVersionTable.PSVersion.Major -eq 5) { '  OK' } else { '  *** must be 5.1 ***' })
"BOM    = $bom" + $(if ($bom -eq '239,187,191') { '  OK' } else { '  *** missing ***' })
"syntax = " + @($perr).Count + " error(s)"
foreach ($e in @($perr)) { '  ' + $e.Message }
"CRLF   = $crlf" + $(if ($crlf -eq 0) { '  OK' } else { '  *** churn ***' })

# 샌드박스: 훅의 $vault 가 <sand> 를 가리키도록 <sand>\v\hooks 에 둔다.
# 경로 판정 루트는 CORE_GATE_ROOT 로 실볼트를 가리키게 해 절대경로 케이스를 살린다.
$sand      = Join-Path ([System.IO.Path]::GetTempPath()) ('gv2-' + [guid]::NewGuid().ToString('N').Substring(0,8))
$sandHooks = Join-Path $sand 'v\hooks'
$sandIdx   = Join-Path $sand '3_시스템\_index'
New-Item -ItemType Directory -Force $sandHooks | Out-Null
New-Item -ItemType Directory -Force $sandIdx   | Out-Null
$sandLog = Join-Path $sandIdx 'core-gate.log'
$sandTok = Join-Path $sandIdx '.core-token'
$sandHook = Join-Path $sandHooks 'core-gate.ps1'
Copy-Item $Hook $sandHook -Force
# 판정부를 분리한 구성이면 함께 옮긴다(머리 파일이 $PSScriptRoot 기준으로 찾는다).
$decideSrc = Join-Path (Split-Path $Hook -Parent) 'core-gate-decide.ps1'
if (Test-Path $decideSrc) { Copy-Item $decideSrc (Join-Path $sandHooks 'core-gate-decide.ps1') -Force }
$sandBase = $null
if ($Baseline) { $sandBase = Join-Path $sandHooks 'baseline.ps1'; Copy-Item $Baseline $sandBase -Force }
# 훅은 자기 위치에서 볼트를 유추하는데 여기서는 샌드박스에 있으므로, 판정 루트만
# 실볼트로 알려준다(로그는 계속 샌드박스에 남는다 — 실볼트 계측 오염 방지).
if (-not $env:CORE_GATE_ROOT) { $env:CORE_GATE_ROOT = $vaultRoot }

function Invoke-Case($gate, $payload, $token) {
  Remove-Item $sandLog -Force -ErrorAction SilentlyContinue
  Remove-Item $sandTok -Force -ErrorAction SilentlyContinue
  if ($token -and $token -ne '-') {
    # 케이스 파일은 한 줄이므로 \n·\r 을 실제 제어문자로 되돌려 쓴다(CRLF 축 검사용).
    [System.IO.File]::WriteAllText($sandTok, (($token -replace '\\r', "`r") -replace '\\n', "`n"), (New-Object System.Text.UTF8Encoding($false)))
  }
  $out = $payload | & powershell -NoProfile -File $gate
  $verdict = 'NOFIRE'
  if (-not [string]::IsNullOrWhiteSpace($out)) {
    if     ($out -match '"permissionDecision"\s*:\s*"allow"') { $verdict = 'ALLOW' }
    elseif ($out -match '"permissionDecision"\s*:\s*"deny"')  { $verdict = 'DENY'  }
    else                                                       { $verdict = 'ASK'   }
  }
  $line = (Get-Content $sandLog -Encoding UTF8 -ErrorAction SilentlyContinue | Select-Object -Last 1)
  New-Object psobject -Property @{ V = $verdict; Log = $line }
}

$rows = @(Get-Content $Cases -Encoding UTF8 | Where-Object { $_.Trim() -and -not $_.StartsWith('#') })
$fail = 0; $changed = @()
''
if ($sandBase) { "case                                      base    hook    want    log   verdict" }
else           { "case                                      hook    want    log   verdict" }
foreach ($row in $rows) {
  $f = $row -split "`t", 5
  $want = $f[0].Trim(); $label = $f[1].Trim(); $logWant = $f[2].Trim(); $token = $f[3].Trim(); $payload = $f[4]
  $payload = $payload.Replace('<VB>', $vaultRoot.Replace('\', '\\')).Replace('<VS>', $vaultRoot.Replace('\', '/'))
  $r = Invoke-Case $sandHook $payload $token
  $bad = @()
  if ($r.V -ne $want) { $bad += 'decision' }
  $logOk = '-'
  if ($logWant -ne '-') {
    if ($r.Log -and $r.Log.EndsWith($logWant)) { $logOk = 'OK' } else { $logOk = 'BAD'; $bad += 'log' }
  }
  if ($bad.Count) { $fail++ }
  $vd = if ($bad.Count) { '*** MISMATCH: ' + ($bad -join '+') + ' ***' } else { 'OK' }
  if ($sandBase) {
    $b = (Invoke-Case $sandBase $payload $token).V
    if ($b -ne $r.V) { $changed += $label }
    "{0,-41} {1,-7} {2,-7} {3,-7} {4,-5} {5}" -f $label, $b, $r.V, $want, $logOk, $vd
  } else {
    "{0,-41} {1,-7} {2,-7} {3,-5} {4}" -f $label, $r.V, $want, $logOk, $vd
  }
}
''
"cases = $($rows.Count)   mismatches = $fail"
if ($sandBase) { "differs from baseline on: " + $(if ($changed) { $changed -join ' | ' } else { 'none' }) }
Remove-Item $sand -Recurse -Force -ErrorAction SilentlyContinue
exit $fail
