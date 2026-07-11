# 외부뇌 Stop 훅 — notes/·decisions/ 프론트매터 + MOC 등재 결정론 검증
# 뿌리②(규약 발동이 모델 의존 → 죽은 규약) 시정: MOC 등록·프론트매터를
# 규약(모델 준수)이 아니라 훅으로 강제한다. 위반 시 종료를 차단하고 모델에 되먹인다.
# 계약(공식): stdout에 {"decision":"block","reason":...} + exit 0 (설계노트 §7·§12.6).
# 인시던트: 3_시스템/_ref/2026-07-11-규약단계-침묵생략.
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# 구버전 Claude Code 루프 플래그(있으면 즉시 해제). 신버전엔 미보장 →
# 아래 파일 서킷브레이커가 무한루프를 버전 무관하게 보증한다.
$raw = [Console]::In.ReadToEnd()
try { $inp = $raw | ConvertFrom-Json } catch { $inp = $null }
if ($inp -and $inp.stop_hook_active) { exit 0 }

$vault = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$moc   = Join-Path $vault '2_지식\MOC.md'
$idx   = Join-Path $vault '3_시스템\_index'
$guard = Join-Path $idx '.stopcheck-guard'
$log   = Join-Path $idx 'hooks.log'
if (-not (Test-Path $moc)) { exit 0 }   # MOC 없으면(초기 상태) 검사 스킵
$mocText = Get-Content $moc -Raw -Encoding UTF8

# 대상: notes/·decisions/만. sessions/·_ref/는 MOC 대상 아님(설계·session-close 5단계).
$dirs = @('2_지식\notes', '2_지식\decisions')
$noFm = @(); $noMoc = @()
foreach ($d in $dirs) {
    $p = Join-Path $vault $d
    if (-not (Test-Path $p)) { continue }
    foreach ($f in Get-ChildItem -Path $p -Filter *.md -File) {
        $name = [System.IO.Path]::GetFileNameWithoutExtension($f.Name)
        # ① 프론트매터: 파일 선두가 '---' (BOM 있으면 제거 후 판정)
        $txt = Get-Content $f.FullName -Raw -Encoding UTF8
        if ($null -ne $txt) { $txt = $txt.TrimStart([char]0xFEFF) }
        if (-not ($txt -and $txt.StartsWith('---'))) { $noFm += $f.Name }
        # ② MOC 등재: [[name]] / [[name|별칭]] / [[name#섹션]]
        $esc = [regex]::Escape($name)
        if ($mocText -notmatch "\[\[$esc[\]|#]") { $noMoc += $f.Name }
    }
}

# 위반 없음 → 가드 리셋 후 통과.
if ($noFm.Count -eq 0 -and $noMoc.Count -eq 0) {
    Remove-Item $guard -Force -ErrorAction SilentlyContinue
    exit 0
}

# 순환 서킷브레이커: 동일 위반집합으로 이미 2회 차단됐으면 무한루프로 보고 해제(exit 0)한다.
# 조용히 넘기지 않도록 hooks.log에 기록(미해결 위반 가시화 — 인시던트 교훈).
if (-not (Test-Path $idx)) { New-Item -ItemType Directory $idx -Force | Out-Null }
$sig = ($noMoc -join ',') + '||' + ($noFm -join ',')
$sha = [System.Security.Cryptography.SHA1]::Create()
$sigHash = [BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($sig))) -replace '-'
$count = 0
if (Test-Path $guard) {
    $prev = (Get-Content $guard -Raw -ErrorAction SilentlyContinue) -split '\|'
    if ($prev.Count -ge 2 -and $prev[0] -eq $sigHash) { $count = [int]$prev[1] }
}
if ($count -ge 2) {
    Add-Content -Path $log -Encoding UTF8 -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') stop-check 순환차단 해제 — 미해결 위반 잔존: MOC[$($noMoc -join ',')] FM[$($noFm -join ',')]" -ErrorAction SilentlyContinue
    Remove-Item $guard -Force -ErrorAction SilentlyContinue
    exit 0
}
Set-Content -Path $guard -Value "$sigHash|$($count + 1)" -Encoding ASCII -ErrorAction SilentlyContinue

$parts = @()
if ($noMoc.Count) { $parts += 'MOC.md 미등재: ' + ($noMoc -join ', ') }
if ($noFm.Count)  { $parts += "프론트매터 누락(선두 '---' 없음): " + ($noFm -join ', ') }
$reason = "규약 위반 — 종료 전 조치 필요.`n" + ($parts -join "`n") +
    "`n조치: 각 노트를 2_지식/MOC.md의 알맞은 섹션(## 지식/## 결정)에 [[파일명]]으로 등재하고, " +
    "누락 노트엔 프론트매터(3_시스템/conventions.md 스키마)를 추가하세요. " +
    "(세션로그·_ref는 대상 아님 — 조용히 생략하지 말고 이 목록을 처리)"

$out = @{ decision = 'block'; reason = $reason } | ConvertTo-Json -Compress
Write-Output $out
exit 0
