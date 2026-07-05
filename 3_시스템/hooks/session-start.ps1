# 외부뇌 SessionStart 훅 (결정론층 — LLM 호출 없음)
# 동작: 개인화 미완료 감지 → recent/open-loops 주입 → 헬스 1줄 → (있으면) 인덱스 증분
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$vault = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent

# [관측] 발화 증거 로그(_index는 gitignore, 상시 관측 — 스펙: 가이드 §15)
Add-Content -Path (Join-Path $vault '3_시스템\_index\hooks.log') -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') SessionStart fired" -ErrorAction SilentlyContinue

# 0. 첫 실행(개인화 미완료) 감지 — CLAUDE.md에 미치환 슬롯 {{ }} 남아 있으면 안내
$claudeMd = Join-Path $vault 'CLAUDE.md'
if ((Get-Content $claudeMd -Raw) -match '\{\{[^}]') {
    # H4: '{{[^}]' = 미치환 실슬롯({{호칭}} 등)만 매치. 문서행의 리터럴 '{{}}'는 제외 → 인터뷰 후 경고 사라짐.
    Write-Output '⚠ 개인화 미완료 — setup-interview 실행 필요 (개인 레이어 슬롯이 비어 있음)'
}

# 1. recent + open-loops 컨텍스트 주입
$recent = Join-Path $vault '2_지식\recent.md'
$loops  = Join-Path $vault '2_지식\open-loops.md'
if (Test-Path $recent) { Write-Output "`n=== recent.md ==="; Get-Content $recent -Raw -Encoding UTF8 }
if (Test-Path $loops)  { Write-Output "`n=== open-loops.md ==="; Get-Content $loops -Raw -Encoding UTF8 }

# 2. 헬스 1줄 (지식노트만: notes/sessions/decisions — profile/recent/open-loops/MOC 제외)
$noteCount = (@('2_지식\notes','2_지식\sessions','2_지식\decisions') | ForEach-Object { Get-ChildItem (Join-Path $vault $_) -Recurse -Filter *.md -ErrorAction SilentlyContinue } | Measure-Object).Count
$lastCommit = (git -C $vault log -1 --format='%cr' 2>$null)
if (-not $lastCommit) { $lastCommit = '없음' }
$idx = Join-Path $vault '3_시스템\_index\embeddings.json'
if (Test-Path $idx) {
    $days = [int]((Get-Date) - (Get-Item $idx).LastWriteTime).TotalDays
    $idxAge = "${days}d"
} else {
    $idxAge = 'N/A'
}
Write-Output "[뇌] 노트 ${noteCount}개 | 인덱스 age $idxAge | 마지막커밋 $lastCommit"

# 3. search.py 있으면 증분 인덱스 (Phase 3 이후에만 존재)
$searchPy = Join-Path $vault '3_시스템\search.py'
if (Test-Path $searchPy) { py -3 $searchPy --reindex 2>$null | Out-Null }
