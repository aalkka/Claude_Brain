# 외부뇌 SessionEnd 훅 (결정론층 — 커밋만. 요약/recent 갱신은 session-close 스킬이 함)
# 동작: 볼트 커밋(Claude author) → 1_수집 별도 커밋(User author) → push
$ErrorActionPreference = 'SilentlyContinue'
$vault = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $vault

# [관측] 발화 증거 로그(_index는 gitignore, 상시 관측 — 스펙: 가이드 §15)
Add-Content -Path (Join-Path $vault '3_시스템\_index\hooks.log') -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') SessionEnd fired" -ErrorAction SilentlyContinue

$today = Get-Date -Format 'yyyy-MM-dd'

# 0. B1 의미링크 자동 갱신 (search.py 있을 때만): reindex(이번 세션 변경분) → link-write(관리블록).
#    직후 git add -A가 링크 변경분을 커밋에 흡수. 안전: strip_managed(피드백루프 차단)+newline LF(CRLF churn 차단).
$searchPy = Join-Path $vault '3_시스템\search.py'
if (Test-Path $searchPy) {
    py -3 $searchPy --reindex 2>$null | Out-Null
    py -3 $searchPy --link-write 2>$null | Out-Null
}

# 1. 볼트 커밋 (1_수집 제외 = Claude 소유 변경분 → Claude author로 인간과 분리)
git add -A -- ':!1_수집'
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { git commit -m "session: $today" --author="Claude <claude@local>" | Out-Null }

# 2. 1_수집(사용자 저작물) 별도 커밋 — author 분리
git add 1_수집
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) { git commit -m "user: $today" --author="User <user@local>" | Out-Null }

# 3. push (원격 있고 개인화 완료 시만, 실패 무시)
#    C5: 미치환 슬롯({{...}})이 남았으면 = 개인화 전 → push 스킵.
#    개인화 전 origin은 아직 공개 배포 repo일 수 있어(슬롯9 재지정 전) 자동 push 시 유출/오염.
#    개인화(setup-interview 슬롯9)가 origin을 개인 repo로 돌린 뒤부터 자동 push 활성.
$claudeMd = Join-Path $vault 'CLAUDE.md'
$slotsLeft = (Get-Content $claudeMd -Raw) -match '\{\{[^}]'
if (-not $slotsLeft -and (git remote)) { git push 2>$null | Out-Null }
