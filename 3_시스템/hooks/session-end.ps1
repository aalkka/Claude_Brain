# 외부뇌 SessionEnd 훅 (결정론층 — 커밋만. 요약/recent 갱신은 session-record 스킬이 함)
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

# 1~2. 볼트 커밋(Claude) → 1_수집 커밋(User) — Stop 훅·서버와 같은 함수(stop-check.py --commit-only · 자동 커밋 잠금을 잡음)로.
#   왜(11-15): 이 훅만 잠금 없이 git add -A 를 해서, 같은 순간 도는 다른 커밋의 pre-commit 이 민감 노트를 내린 뒤 틈에
#   다시 올렸다(01:32:55 SessionEnd → 01:32:56 민감 노트 2건 커밋 · 격리 재현 134회 중 24). 잠금을 30초 못 잡으면 건너뛴다
#   (다음 커밋이 담음). 파이썬이 없거나 결과를 못 내면 아래 예전 길(잠금 없음)로 한다 — 커밋을 아예 거르지는 않는다.
$sc = Join-Path $PSScriptRoot 'stop-check.py'
$res = $null
if (Test-Path $sc) { $res = (& py -3 $sc --commit-only --vault $vault --tag SessionEnd 2>$null) -join '' }
if ($res -notmatch '"result"') {
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
}

# 3. push (원격 있고 개인화 완료 시만, 실패 무시)
#    C5: 미치환 슬롯({{...}})이 남았으면 = 개인화 전 → push 스킵.
#    개인화 전 origin은 아직 공개 배포 repo일 수 있어(슬롯9 재지정 전) 자동 push 시 유출/오염.
#    개인화(setup-interview 슬롯9)가 origin을 개인 repo로 돌린 뒤부터 자동 push 활성.
$claudeMd = Join-Path $vault 'CLAUDE.md'
$slotsLeft = (Get-Content $claudeMd -Raw) -match '\{\{[^}]'
#    origin 이 아직 공개 배포 저장소면(개인 저장소 단계를 건너뜀) push 하지 않는다 — 권한이 없어 늘 실패하고,
#    권한이 있는 사람(배포판 주인)에게는 개인 커밋이 공개 저장소로 간다(11-26). 배포 저장소 = dist 원격 · 받는 문 해시 표의 주소.
$origin = git remote get-url origin 2>$null
$pubUrls = @(git remote get-url dist 2>$null)
$relJson = Join-Path $vault '3_시스템\door-app\release.json'
if (Test-Path $relJson) {
    $m = [regex]::Match((Get-Content $relJson -Raw), 'https://github\.com/[^/"\s]+/[^/"\s]+')
    if ($m.Success) { $pubUrls += $m.Value }
}
$canon = { param($u) ("$u".Trim() -replace '\.git$', '' -replace '/+$', '').ToLower() }
$originIsPub = $origin -and @($pubUrls | Where-Object { $_ -and ((& $canon $_) -eq (& $canon $origin)) }).Count -gt 0
if (-not $slotsLeft -and $origin -and -not $originIsPub) { git push 2>$null | Out-Null }

# 3.5 주인 장부(11-19) — 이 세션의 장부 항목·시험 프로세스(에뮬레이터·격리 옵시디언·머리 없는 크롬)를 끝낸다.
#   왜: 세션이 끝나도 띄운 것이 남아 메모리를 쥐었다(에뮬레이터 이틀 · 11-15). 동기 0.5초 · 실패해도 계속 · 그 밖의 배경 작업은 예약 작업 tick 이 맡음.
$ownPy = Join-Path $vault '3_시스템\own.py'
if (Test-Path $ownPy) { & py -3 $ownPy end 2>$null | Out-Null }

# 4. B1 의미링크 갱신 — 맨 끝 **디태치**(비대기). reindex→link-write 1프로세스(main()이 순차 지원).
#    비핵심(인덱스=gitignore, 링크블록=멱등·1세션 지연 무해) → 셧다운이 죽여도 다음 시작 reindex가 커버.
#    이 훅이 여기서 절대 블록되지 않게 하는 게 목적(타임아웃 무의미화).
#    기능 «재색인 빈도»(search.reindex): «안 함»이면 띄우지 않는다 · «6시간마다»면 search.py 가 재색인을 6시간에 한 번으로 미루고 그때만 링크를 쓴다 · «의미 링크 쓰기» 끔이면 search.py 가 링크를 건너뜀(session-start 와 같은 꼴).
$searchPy = Join-Path $vault '3_시스템\search.py'
$semantic = 'high'
$optPs = Join-Path $PSScriptRoot 'options-level.ps1'
if (Test-Path $optPs) { . $optPs; $semantic = Get-OptionLevel $vault 'search.reindex' }
if ((Test-Path $searchPy) -and $semantic -ne 'off') {
    $env:BRAIN_AUTO = '1'
    Start-Process -FilePath 'py' -ArgumentList '-3', $searchPy, '--reindex', '--link-write' -WindowStyle Hidden -ErrorAction SilentlyContinue
}
