# 외부뇌 SessionEnd 훅 (결정론층 — 커밋만. 요약/recent 갱신은 session-close 스킬이 함)
# 동작: 볼트 커밋(Claude author) → 1_수집 별도 커밋(User author) → push
$ErrorActionPreference = 'SilentlyContinue'
$vault = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $vault

# [관측] 발화 증거 로그(_index는 gitignore, 상시 관측 — 스펙: 가이드 §15)
Add-Content -Path (Join-Path $vault '3_시스템\_index\hooks.log') -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') SessionEnd fired" -ErrorAction SilentlyContinue

$today = Get-Date -Format 'yyyy-MM-dd'

# [원인 시정] 구버전은 여기서 reindex+link-write(모델로드 16s+·link-write O(N²))를 **동기** 실행 후
#   커밋했다 → 콜드 세션에서 훅 타임아웃(60s) 초과 → 커밋 라인 도달 전 kill → 한 주간 커밋 정지
#   (incident 2026-07-19). 시정: ① 커밋은 Stop 훅(턴마다)이 이미 수행 → 여기선 best-effort 백업.
#   ② ML은 맨 끝에서 **디태치**(비대기) → 이 훅은 절대 블록 안 함. 셧다운이 kill해도 커밋은 이미 안전.

# 1. 볼트 커밋 (1_수집 제외 = Claude 소유 변경분 → Claude author로 인간과 분리)
git add -A -- ':!1_수집'
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "session: $today" --author="Claude <claude@local>" | Out-Null
    # pre-commit 차단(frontmatter/secret)으로 커밋 실패 시 스테이지 잔존 → 무성 좌초 가시화.
    git diff --cached --quiet
    if ($LASTEXITCODE -ne 0) {
        Add-Content -Path (Join-Path $vault '3_시스템\_index\hooks.log') -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') SessionEnd commit BLOCKED by pre-commit - staged changes remain" -ErrorAction SilentlyContinue
    }
}

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

# 4. B1 의미링크 갱신 — 맨 끝 **디태치**(비대기). reindex→link-write 1프로세스(main()이 순차 지원).
#    비핵심(인덱스=gitignore, 링크블록=멱등·1세션 지연 무해) → 셧다운이 죽여도 다음 시작 reindex가 커버.
#    이 훅이 여기서 절대 블록되지 않게 하는 게 목적(타임아웃 무의미화).
$searchPy = Join-Path $vault '3_시스템\search.py'
if (Test-Path $searchPy) {
    Start-Process -FilePath 'py' -ArgumentList '-3', $searchPy, '--reindex', '--link-write' -WindowStyle Hidden -ErrorAction SilentlyContinue
}
