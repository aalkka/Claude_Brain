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

# 대상: notes/·decisions/ (재귀 — 하위폴더 포함). sessions/·_ref/·_접두 하위폴더는 MOC 대상 아님.
$dirs = @('2_지식\notes', '2_지식\decisions')
$noFm = @(); $noMoc = @()
foreach ($d in $dirs) {
    $p = Join-Path $vault $d
    if (-not (Test-Path $p)) { continue }
    foreach ($f in Get-ChildItem -Path $p -Filter *.md -File -Recurse) {
        # _접두 하위폴더(예 vocagrader/_ref)는 MOC 비대상 — top-level _ref와 동일(프로젝트 incident 등).
        # '2_지식'의 '_'는 앞이 '2'라 '\_' 패턴에 안 걸림(오작동 없음).
        if ($f.DirectoryName.Substring($vault.Length) -match '\\_') { continue }
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

# ③ 중복 basename 검출 (위키링크 [[name]] 모호성 방지). 스코프 = 2_지식/** + 3_시스템/_ref/**.
# (1_수집=사용자저작 불가침·_claude-memory·pdf-cache=기계 제외. Group-Object=공백파일명 안전.)
$allMd = Get-ChildItem -Path (Join-Path $vault '2_지식'), (Join-Path $vault '3_시스템\_ref') -Filter *.md -File -Recurse -ErrorAction SilentlyContinue
$dupNames = @($allMd | Group-Object BaseName | Where-Object { $_.Count -gt 1 } | ForEach-Object { $_.Name })

# 위반 없음 → 가드 리셋 후 커밋(로컬 durability) → 통과.
if ($noFm.Count -eq 0 -and $noMoc.Count -eq 0 -and $dupNames.Count -eq 0) {
    Remove-Item $guard -Force -ErrorAction SilentlyContinue
    # [커밋 이관] 실제 종료 = PC 셧다운 → SessionEnd는 OS가 kill(torch+커밋 완주 불가).
    # 그래서 커밋을 살아있는 턴 종료(Stop)로 옮긴다. torch 미로드 → 빠름(~수백ms).
    # 계약 준수: Stop stdout은 block JSON만 허용 → 모든 git 출력 억제. 변경 없으면 무커밋(diff 가드).
    # author 분리: 1_수집(사용자저작) ↔ 나머지(Claude). $LASTEXITCODE는 파이프 무관하게 git값 유지.
    git -C $vault add -A -- ':!1_수집' 2>&1 | Out-Null
    git -C $vault diff --cached --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { git -C $vault commit -m "session: $(Get-Date -Format 'yyyy-MM-dd')" --author="Claude <claude@local>" 2>&1 | Out-Null }
    git -C $vault add 1_수집 2>&1 | Out-Null
    git -C $vault diff --cached --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { git -C $vault commit -m "user: $(Get-Date -Format 'yyyy-MM-dd')" --author="User <user@local>" 2>&1 | Out-Null }
    # 커밋 후에도 스테이지 잔존 = pre-commit(3_시스템/hooks/pre-commit) 차단(secret/frontmatter) → 무성 좌초 가시화.
    git -C $vault diff --cached --quiet 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Add-Content -Path $log -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') Stop commit BLOCKED by pre-commit - staged remain" -ErrorAction SilentlyContinue }
    exit 0
}

# 순환 서킷브레이커: 동일 위반집합으로 이미 2회 차단됐으면 무한루프로 보고 해제(exit 0)한다.
# 조용히 넘기지 않도록 hooks.log에 기록(미해결 위반 가시화 — 인시던트 교훈).
if (-not (Test-Path $idx)) { New-Item -ItemType Directory $idx -Force | Out-Null }
$sig = ($noMoc -join ',') + '||' + ($noFm -join ',') + '||' + ($dupNames -join ',')
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
if ($dupNames.Count) { $parts += '중복 파일명(위키링크 [[name]] 모호): ' + ($dupNames -join ', ') }
$reason = "규약 위반 — 종료 전 조치 필요.`n" + ($parts -join "`n") +
    "`n조치: 각 노트를 2_지식/MOC.md의 알맞은 섹션(## 지식/## 결정)에 [[파일명]]으로 등재하고, " +
    "누락 노트엔 프론트매터(3_시스템/conventions.md 스키마)를 추가하고, " +
    "중복 파일명은 하나를 고유 basename으로 개명하세요. " +
    "(세션로그·_ref·_접두 하위폴더는 MOC 대상 아님 — 조용히 생략하지 말고 이 목록을 처리)"

$out = @{ decision = 'block'; reason = $reason } | ConvertTo-Json -Compress
Write-Output $out
exit 0
