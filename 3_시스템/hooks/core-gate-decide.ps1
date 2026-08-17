# 코어 게이트 판정부 — core-gate.ps1 이 코어 언급을 확인한 뒤에만 dot-source 한다.
# 호출자 스코프에서 실행되므로 $raw · $p · $core · $tool 을 그대로 쓴다.
# 여기서부터가 '코어를 언급한' 소수 경로다. 볼트 루트 계산(Split-Path 2회)은
# 값이 비싸므로 1차 검사를 통과한 뒤에 한다.
# 판정용 루트만 분리한다 — 검증 하네스는 훅을 임시 샌드박스로 복사해 돌리므로
# $PSScriptRoot 기반 볼트가 temp를 가리켜 절대경로 케이스가 전부 '볼트 밖'이 된다.
# 로그는 $vault(샌드박스)에 남기고 판정 루트만 override 해 실볼트 로그를 지킨다.
$vault  = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$root   = if ($env:CORE_GATE_ROOT) { $env:CORE_GATE_ROOT } else { $vault }
$vaultN = ($root -replace '\\', '/')
$target = $null
foreach ($m in [regex]::Matches($p, '(?:[A-Za-z]:/[^\s";,|&]*?)?(' + $core + ')')) {
    if ($m.Value -match '^[A-Za-z]:/') {
        if (-not $m.Value.StartsWith($vaultN + '/', [StringComparison]::OrdinalIgnoreCase)) { continue }
    }
    $target = $m.Groups[1].Value
    break
}
if (-not $target) { exit 0 }

# ── 4. 셸 도구는 '쓰기 동사'가 코어와 같은 절(clause)에 있을 때만 건다.
# 명령 전체에서 AND로 보면 `py … search.py --eval x >> 비코어; rm err.log`처럼
# 코어를 읽기만 하는 명령이 전부 걸린다(2026-08-17 실측: 셸 발동의 61%가 비쓰기).
# 인라인 코드(-c / -Command / heredoc)는 절로 쪼갤 수 없으므로 '쓰기 표지'로 가른다 —
# 코어 스크립트 '실행'·설정 '검사'와 코어 '쓰기'를 가르는 선이다.
if ($tool -in 'Bash','PowerShell') {
    $fire = $false
    $rxCode = "(?s)(?:-c|-Command)\s+(['""]).*?\1|<<\s*['""]?(\w+).*?\2"
    $code = -join ([regex]::Matches($p, $rxCode) | ForEach-Object { $_.Value })
    $shell = [regex]::Replace($p, $rxCode, ' ')
    # 인용문은 절 구분자를 담아도 절을 나누지 않는다 — `sed -i 's/;/x/' CLAUDE.md` 가
    # 세미콜론에서 쪼개져 통과했다(2026-08-17 검증 X1·X2). 다만 인용문 안에 코어 경로가
    # 있으면(`> "CLAUDE.md"`) 지우지 않는다 — 지우면 그 코어를 놓친다.
    $coreRx = [regex]('(' + $core + ')')
    $q = [char]39
    $rxQuote = "$q[^$q]*$q" + '|"[^"]*"'
    $shell = [regex]::Replace($shell, $rxQuote,
        [System.Text.RegularExpressions.MatchEvaluator]{
            param($m) if ($coreRx.IsMatch($m.Value)) { $m.Value } else { ' Q ' } })
    # (a) 인라인 코드 '안'의 코어 = 쓰기 표지로 가른다. json.load·open().read()·py_compile은 읽기다.
    if ($code -match ('(' + $core + ')') -and
        $code -match ',\s*[''"][wax]\+?b?[''"]|WriteAll\w+|AppendAll\w+|write_text|Set-Content|Add-Content|Out-File|os\.remove|\.unlink|os\.rename|shutil\.|json\.dump\(|\.truncate\(') { $fire = $true }
    # (b) 코드 '밖'의 코어 = 쓰기 동사가 같은 절에 있을 때만. 껍데기에서 판정하므로
    #     `python3 -c "…" CLAUDE.md`(인자 전달)는 남고 `py -c "…CLAUDE.md…"`(코드 안)는 사라진다.
    if (-not $fire) {
        $verbs ='>\s*&?[^\s;|&]*(' + $core + ')|sed\s+-i|tee\b|\bcp\b|\bmv\b|\brm\b|\btruncate\b|Set-Content|Add-Content|Out-File|New-Item|Remove-Item|Move-Item|Copy-Item|git\s+(checkout|restore|apply|reset)|WriteAll\w+|AppendAll\w+|\bpython\d?\b|\bnode\b|\bperl\b|\bpy\s+(-\d(\.\d+)?\s+)?-c\b|\bchmod\b|update-index'
        foreach ($c in ($shell -split '(?:;|&&|\|\||\||\r?\n)')) {
            if ($c -notmatch ('(' + $core + ')')) { continue }
            if ($c -match $verbs) { $fire = $true; break }
        }
    }
    if (-not $fire) { exit 0 }
}

# ── 5. 통과 토큰. 무인 실행에서 ask는 조용한 사망이다(incident 2026-07-27).
# 훅은 무인 세션을 판별할 수 없다(2026-08-17 실측: promptSource=sdk가 87/88).
# 사용자가 남긴 토큰이 '이 실행은 무인이다'를 훅에 알리는 유일한 신뢰 경로다.
$mode = if ($raw -match '"permission_mode"\s*:\s*"([^"]+)"') { $Matches[1] } else { '-' }
$logf = Join-Path $vault '3_시스템/_index/core-gate.log'
$tokf = Join-Path $vault '3_시스템/_index/.core-token'
$sid = if ($raw -match '"session_id"\s*:\s*"([^"]+)"') { $Matches[1] } else { '' }
$decision = 'ask'; $tag = 'ASK'
if (Test-Path $tokf) {
    $tk = ([System.IO.File]::ReadAllText($tokf, [System.Text.Encoding]::UTF8)) -replace "`r", ''
    $exp = if ($tk -match '(?m)^expires\s*=\s*(\S+)') { $Matches[1] } else { '' }
    $scp = if ($tk -match '(?m)^scope\s*=\s*(.+?)\s*$')  { $Matches[1] } else { '' }
    # 세션 축. 토큰은 파일이라 그대로 두면 볼트의 '모든' 세션이 공유한다 —
    # 다중 세션에서 발행하지 않은 세션이 코어를 고칠 수 있다.
    # bind=first(기본): 처음 쓴 세션에 묶고 그 세션만 통과. 무인 세션 id는 발행 시점에
    #   알 수 없으므로 이것이 무인화와 양립하는 유일한 좁힘이다.
    # bind=any: 세션 제한 없음(명시해야만 넓어진다). bind=<id>: 그 세션만.
    $bind  = if ($tk -match '(?m)^bind\s*=\s*(\S+)')  { $Matches[1] } else { 'first' }
    $bound = if ($tk -match '(?m)^bound\s*=\s*(\S+)') { $Matches[1] } else { '' }
    $sessOk = $false; $bindNow = $false
    if     ($bind -eq 'any')   { $sessOk = $true }
    elseif ($bind -eq 'first') {
        # 세션을 특정할 수 없으면 묶을 수도 없다 → 토큰 무효(fail-closed).
        if     (-not $sid)       { $sessOk = $false; $tag = 'TOKEN-NOSESSION' }
        elseif (-not $bound)     { $sessOk = $true; $bindNow = $true }
        elseif ($bound -eq $sid) { $sessOk = $true }
        else                     { $tag = 'TOKEN-OTHERSESSION' }
    }
    elseif ($bind -eq $sid) { $sessOk = $true }
    else { $tag = 'TOKEN-OTHERSESSION' }
    # 만료는 실제 시각으로 비교한다. 문자열 비교는 `expires=언젠가`·`2026-8-18` 같은
    # 형식 불량을 '먼 미래'로 읽어 무제한 토큰을 만든다(2026-08-17 검증 X4·X6).
    $expDt = [datetime]::MinValue
    $expOk = $exp -and [datetime]::TryParseExact($exp, 'yyyy-MM-ddTHH:mm:ssZ',
        [Globalization.CultureInfo]::InvariantCulture,
        [Globalization.DateTimeStyles]::AdjustToUniversal -bor [Globalization.DateTimeStyles]::AssumeUniversal,
        [ref]$expDt) -and $expDt -gt [DateTime]::UtcNow
    if ($expOk -and $sessOk) {
        # 토큰이 살아 있다 = 무인 실행. 범위 안이면 통과, 밖이면 즉시 실패(대기 금지).
        # 게이트 자신을 이루는 셋은 어떤 범위로도 통과시키지 않는다 —
        # 토큰(무한 연장·범위 확대) · 훅(판정 로직 교체) · settings.json(훅 등록 해제).
        # 토큰은 게이트가 '지키는 것'을 위임할 뿐, 게이트 '자신'은 위임하지 못한다.
        $inScope = $false
        if ($target -notlike '*.core-token' -and $target -notlike '*core-gate*.ps1' -and $target -notlike '*settings.json') {
            foreach ($g in ($scp -split '\s*,\s*')) {
                if (-not $g) { continue }
                if ($g -eq '*') { $inScope = $true; break }
                if ($target -like $g) { $inScope = $true; break }
            }
        }
        if ($inScope) {
            $decision = 'allow'; $tag = 'TOKEN-ALLOW'
            # 첫 사용 세션에 묶는다. 이 줄이 붙은 뒤로 다른 세션은 통과하지 못한다.
            # 기록에 실패하면(읽기전용·디스크 오류) 세션 구속이 사라져 토큰이 전역 공유로
            # 퇴화한다 — 조용히 넘기지 않고 차단한다(fail-closed).
            if ($bindNow -and $sid) {
                Add-Content -Path $tokf -Value "bound=$sid" -Encoding UTF8 -ErrorAction SilentlyContinue
                $after = [System.IO.File]::ReadAllText($tokf, [System.Text.Encoding]::UTF8)
                if ($after -notmatch [regex]::Escape("bound=$sid")) { $decision = 'deny'; $tag = 'TOKEN-BINDFAIL' }
            }
        }
        else { $decision = 'deny';  $tag = 'TOKEN-DENY' }
    } elseif ($tag -eq 'ASK' -and -not $expOk) { $tag = 'TOKEN-EXPIRED' }
}

Add-Content -Path $logf -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [$mode] $tag $tool $target" -ErrorAction SilentlyContinue

$reason = @'
⚠ 코어파일 수정 — ADR-006 게이트

■ 0. 필요한가 (먼저 답할 것)
  · 강제층 추가는 실측 2건 이상에서만(§9). 1건이면 보류하고 계측기부터.
  · 이미 있는 것으로 되는가 — 네이티브 기능·기존 훅·git 이력. 새로 짓기 전에 확인.
  · 모듈발이면 전 볼트 일반규칙일 때만 승격(ADR-004 8항). 모듈 특수면 모듈 훅으로.

■ 1. 절차
  · 발견 즉시 고치지 않는다. diff 제시 → 승인 → ADR.
  · "고쳐라"로 읽히는 지시도 코어 수정 권한까지 자동 확장되지 않는다.

■ 2. 검증 (코어에 넣기 전)
  · 격리 환경에서 실행. 07-27: 이 단계를 건너뛴 코드가 실제 문법오류였다.
  · 기존 케이스 회귀 0 + 회귀 케이스가 '이번 변경이 건드리는 축'을 덮는가.
    07-30: 성능만 고치려던 변경이 판정 로직을 바꿨는데 케이스에 그 축이 없어 통과했다.
  · 검증은 powershell(5.1)로. pwsh 7은 UTF-8 기본이라 인코딩 버그를 못 잡는다.

■ 3. 격리성 — 의도한 것만 바뀌는가
  · 리팩터링·정리·개선을 끼워넣지 않는다. 수정 사유에 없는 변경 = 별건.
  · 외부 의존성 금지. 미선언 의존성은 fail-closed로 전 커밋을 막는다(07-27 실증).
  · 실패 방향을 명시적으로 정한다 — 검증 실패는 막고, 도구 부재는 통과(fail-open).

■ 4. 최소 표면
  · 같은 목적이면 한 파일·최소 줄. pre-commit이 권위 게이트, stop-check는 손대지 않는다.
  · 검사 대상 경로를 조용히 넓히지 않는다(07-27 부수 위반: _ref 무단 확대).

■ 5. 비용
  · 상시 토큰: T0(CLAUDE.md)·T1(recent·open-loops)·훅 출력 증가 금지. 늘리면 one-in-one-out.
  · 지연: 훅은 발동마다 PowerShell 스폰(176ms 하한). SessionStart 23초·Stop +0.28s 전례.

■ 6. 환경 (이 볼트의 상습 실패모드 — incident 4건)
  · .ps1은 UTF-8 BOM 저장. PS 5.1이 cp949로 오독한다.
  · 한글 경로(3_시스템)·한글 유저명이 글롭·로캘·stdout에서 깨진다.
  · 줄바꿈은 .gitattributes가 강제. 파이썬 writer에 newline 지정 금지.

■ 7. 파급
  · 무인 실행(weekly-review 스케줄)이 이 변경으로 죽지 않는가 — 승인 대기 = 조용한 사망.
  · dist(배포 템플릿) 오염 여부. 흘러가면 신규 사용자 볼트가 같은 결함을 받는다.
  · 롤백 지점(커밋 해시)을 먼저 확보.

전문·근거 incident → 3_시스템/_ref/코어수정-준수사항-체크리스트.md
'@

# 토큰은 '승인'만 면제한다. 준수사항은 그대로 간다 —
# ADR-006 원 요구(건희님 인박스 2026-07-28)가 "승인받은 수정이더라도 매번 준수사항"이었다.
# 게이트의 두 기능(차단 / 준수사항 주입) 중 토큰이 끄는 것은 차단뿐이다.
if ($decision -eq 'allow') {
    @{ hookSpecificOutput = @{
        hookEventName      = 'PreToolUse'
        permissionDecision = 'allow'
        permissionDecisionReason = "코어 통과 토큰(범위 $scp, 만료 $exp) — 무인 실행."
        additionalContext  = "⚠ 토큰으로 승인은 면제됐다. 준수사항은 면제되지 않는다.`n" + $reason
    } } | ConvertTo-Json -Depth 5 -Compress
    exit 0
}

if ($decision -eq 'deny') {
    $reason = "⚠ 코어 쓰기 차단 — 무인 실행 토큰의 허용 범위 밖이다(대상 $target, 범위 $scp).`n승인할 사람이 없으므로 대기하지 않고 즉시 실패시킨다. 이 수정은 대화형 세션에서 다시 시도하고, 지금은 open-loops.md에 제안으로만 남긴다."
}

@{ hookSpecificOutput = @{
    hookEventName            = 'PreToolUse'
    permissionDecision       = $decision
    permissionDecisionReason = $reason
    additionalContext        = $reason
} } | ConvertTo-Json -Depth 5 -Compress
exit 0
