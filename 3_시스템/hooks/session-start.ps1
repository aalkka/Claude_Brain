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

# 1.5 기록 미완료는 여기서 내지 않는다 — session-notice.py 가 사용자에게 알린다. 모든 세션 입력에 넣으면
#     질문과 무관한 첫 답이 «기록이 남지 않은 세션»으로 시작한다(11-02 실측 3회).

# 1.6 일정 7일 — 2_지식/일정/*.md 의 열린 줄(- [ ])을 오늘~7일 뒤만, 최대 8줄. 파이썬 없이(1.5와 같은 이유).
#     문법은 3_시스템/schedule.py 의 LINE 과 같다(바꾸면 둘 다). 대조 = `schedule.py week`. 형식 → 외부뇌-일정-형식 · ADR-017
$schedDir = Join-Path $vault '2_지식\일정'
if (Test-Path $schedDir) {
    $rx = '^\s*- \[ \] (\d{4}-\d{2}-\d{2})(?: \(\S{1,3}\))?(?: (\d{1,2}:\d{2})(?:~(\d{1,2}:\d{2}))?)? (.+?)(?: \^[A-Za-z0-9-]+)?\s*$'
    $wd = '일월화수목금토'
    $today = (Get-Date).Date
    $rows = foreach ($f in Get-ChildItem $schedDir -Filter *.md -File) {
        foreach ($ln in [IO.File]::ReadAllLines($f.FullName, [Text.Encoding]::UTF8)) {
            if ($ln -notmatch $rx) { continue }
            try { $d = [datetime]::ParseExact($Matches[1], 'yyyy-MM-dd', $null) } catch { continue }
            if ($d -lt $today) { continue }
            $t = if ($Matches[2]) { $Matches[2].PadLeft(5, '0') + $(if ($Matches[3]) { '~' + $Matches[3] } else { '' }) } else { '' }
            $txt = $Matches[4] -replace '\[\[[^\]]*\|원본\]\]|\[원본\]\([^)]*\)', '' -replace '\[\[[^\]|]*\|([^\]]*)\]\]', '$1' -replace '\[\[([^\]]*)\]\]', '$1'
            $txt = ($txt -split '\s+' | Where-Object { $_ }) -join ' '
            [pscustomobject]@{ D = $d; T = $t; Txt = $txt; Course = ($txt -split ' · ', 2)[0] }
        }
    }
    $rows = @($rows | Sort-Object D, T, Txt)
    $week = @($rows | Where-Object { $_.D -le $today.AddDays(7) })
    $fmt = { param($r) '- {0:MM-dd} ({1}){2} ' -f $r.D, $wd[[int]$r.D.DayOfWeek], $(if ($r.T) { ' ' + $r.T } else { '' }) }
    Write-Output "`n=== 일정 7일 (2_지식/일정) ==="
    if ($week.Count) {
        $out = foreach ($g in ($week | Group-Object { '{0:yyyyMMdd}|{1}|{2}' -f $_.D, $_.T, $_.Course })) {
            $r = $g.Group[0]
            if ($g.Count -ge 3) { (& $fmt $r) + $r.Txt + " 외 $($g.Count - 1)건" } else { $g.Group | ForEach-Object { (& $fmt $_) + $_.Txt } }
        }
        $out | Select-Object -First 8
    } elseif ($rows.Count) {
        Write-Output ('7일 안 없음 · 다음: ' + ((& $fmt $rows[0]) + $rows[0].Txt).Substring(2))
    } else { Write-Output '(열린 일정 없음)' }
}

# 2. 헬스 1줄 (지식노트만 — profile/recent/open-loops/MOC 제외)
# 자리는 역할로(볼트 개혁 R6 · 3_시스템/roles.json groups.knowledge_notes) — 못 읽으면 0
$kn = @()
try { $rj = [System.IO.File]::ReadAllText((Join-Path $vault '3_시스템\roles.json'), [System.Text.Encoding]::UTF8) | ConvertFrom-Json; $kn = @($rj.groups.knowledge_notes | ForEach-Object { $rj.roles.$_ }) } catch {}
$noteCount = ($kn | ForEach-Object { Get-ChildItem (Join-Path $vault $_) -Recurse -Filter *.md -ErrorAction SilentlyContinue } | Measure-Object).Count
$lastCommit = (git -C $vault log -1 --format='%cr' 2>$null)
if (-not $lastCommit) { $lastCommit = '없음' }
$idx = Join-Path $vault '3_시스템\_index\embeddings.json'
if (Test-Path $idx) {
    $days = [int]((Get-Date) - (Get-Item $idx).LastWriteTime).TotalDays
    $idxAge = "${days}d"
} else {
    $idxAge = 'N/A'
}
# 받은함(설계안 §13.3 B4 · 볼트 개혁 R9) — 머문 것이 있을 때만 붙인다(0건이면 글자 0 · 상시 토큰 늘리지 않음). 못 읽으면 빼고 간다.
$ib = ''
try {
    $it = @(Get-ChildItem (Join-Path $vault ($rj.roles.inbox -replace '/', '\')) -ErrorAction Stop | Where-Object { $_.Name -notmatch '^[._]' })
    if ($it.Count) { $ib = " | 받은함 $($it.Count)(가장 오래된 $([int]((Get-Date) - ($it | Sort-Object LastWriteTime | Select-Object -First 1).LastWriteTime).TotalDays)일 · inbox.py)" }
} catch {}
Write-Output "[뇌] 노트 ${noteCount}개 | 인덱스 age $idxAge | 마지막커밋 $lastCommit$ib"

# 2.5 따라가기(설계안 §19.3) — 옵시디언 밖에서 옮기거나 지운 파일 뒤처리 · 알릴 것이 있을 때만 한 줄(0건이면 글자 0) · 사진이 있으면 0.7초(11-03 실측) · 찾기 색인(3)보다 먼저
$followPy = Join-Path $vault '3_시스템\follow.py'
if (Test-Path $followPy) { & py -3 $followPy --hook 2>$null }

# 3. search.py 있으면 증분 인덱스 — **디태치**(비대기, session-end와 동일 패턴).
#    구 구조는 동기 실행이었다: 세션 시작 시점엔 직전 세션이 남긴 노트 변경분이 거의 항상 있어
#    지연로드 스킵(search.py:236 "to_embed 있을 때만")이 안 걸린다 → 모델로드 15.6s(HF Hub 확인
#    5.1s 포함)+인코딩 ≈18s를 사용자가 그대로 대기(실측 중앙값 23s·p90 84s·최대 118s, 81회).
#    비핵심(인덱스=gitignore·검색 품질에만 영향)이고 save_index가 tmp→os.replace 원자교체라
#    중도 kill·SessionEnd 디태치와 동시 실행에도 손상 없음(다음 reindex가 hash 불일치로 자기치유).
#    ※ push(4)는 동기 유지 — 1.5s로 짧고, git 동시 실행은 index.lock 경합 위험(2026-07-19 사례).
$searchPy = Join-Path $vault '3_시스템\search.py'
if (Test-Path $searchPy) {
    Start-Process -FilePath 'py' -ArgumentList '-3', $searchPy, '--reindex' -WindowStyle Hidden -ErrorAction SilentlyContinue
}

# 4. 원격 push — 밀린 커밋 동기(셧다운이 SessionEnd를 kill해도 다음 세션 시작 때 확실히 push).
#    개인화 완료(미치환 슬롯 없음)+원격 존재 시만. stdout 무출력(주입 컨텍스트 오염 없음). 실패 무시.
if ((Get-Content $claudeMd -Raw) -notmatch '\{\{[^}]' -and (git -C $vault remote)) { git -C $vault push 2>$null | Out-Null }
