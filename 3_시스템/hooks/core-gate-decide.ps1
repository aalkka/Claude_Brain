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

# ── 3.5 플러그인 자리(.obsidian/plugins/)는 볼트 밖임이 «확실»할 때만 코어에서 뺀다(11-18 · 사용자 A안).
#   왜: 격리 시험이 볼트 밖 시험 볼트(스크래치패드)에 빌드를 복사할 때마다 승인을 물어, 사람이 없으면 일꾼이 몇 시간 멈췄다
#       (core-gate.log 11-18 01:23 · 06:27 · 07:23). 그 명령은 모두 경로를 변수에 담았다 — $S = "C:\…\scratchpad\space"; … "$S\…\.obsidian\plugins\…".
#       글자 그대로 쓴 볼트 밖 절대 경로는 이 절 전에도 코어가 아니었다(gate-cases Z7). 02:32 은 볼트 플러그인 읽기가 섞여 그대로 묻는다.
#   확실 = 글자 그대로의 절대 경로이거나, 같은 명령의 맨 윗단에서 조건 없이 한 번만 글자 그대로의 절대 경로를 담은 변수이고,
#          정규화(대소문자 · / \ · /c/ · . ..)해도 볼트 뿌리 밖 · 볼트와 같은 드라이브 글자 · 디스크에 있는 앞부분의 정션·링크를 풀어도 밖.
#   그 밖은 코어(닫힌 쪽): 맨 상대 경로 · 모르는 변수($env: · %X% · $CLAUDE_PROJECT_DIR) · ~ · 8.3(~1) · 깨진 따옴표 · 링크를 만드는 명령 · eval 류.
#   다른 폴더 아래 같은 이름(test/vault-ci/.obsidian/…)은 지금 규칙 그대로 두되 PS 뿌리(\…) · .. · $(…) · 끝 점은 코어(볼트 플러그인일 수 있었다).
#   판정은 JSON 을 푼 원문($gd)에서 한다 — $p 는 줄바꿈이 /n 이라 문장을 못 나눈다. 같은 차례(k 번째 플러그인 일치)로 잇는다.
#   한 명령에 볼트 안팎이 섞이면 안쪽 일치가 대상이 되어 4절이 지금처럼 판정한다. 잘 모르면(오류 포함) 빼지 않는다.
$gpDeny = '^(?i:\d.*|_|PWD|OLDPWD|HOME|PATH|CDPATH|IFS|REPLY|RANDOM|SRANDOM|SECONDS|LINENO|PPID|UID|EUID|SHELL|OPTARG|OPTIND|TMP|TEMP|TMPDIR|args|input|this|Matches|PSItem|MyInvocation|LASTEXITCODE|Error|ExecutionContext|Host|StackTrace|Event|EventArgs|EventSubscriber|Sender|ForEach|switch|true|false|null|ShellId|PID|PROFILE|(BASH|PS|HIST|EPOCH|COMP_|READLINE|FUNC|PIPE|DIRSTACK|GROUPS|CLAUDE).*)$'
$gpBadB = '(?m)(^|[;&|(){}`]|\b(?:then|do|else|elif)\b)\s*(?:eval|source|\.|builtin|command|declare|typeset|mapfile|readarray|getopts|let)(?=\s)|\bprintf\s+(?:-\w+\s+)*-v|<<|\$'''
$gpBadP = '(?i)invoke-expression|\biex\b|-variable\b|\b(?:sv|nv|clv|rv|gv)\b|variable:|\[ref\]|psvariable|executioncontext|\bparam\s*\(|\bfunction\s|\bfilter\s|\bworkflow\s|@"|@''|(^|[\s;{(|&])\.\s+\S|-(?:ov|pv|ev|wv|iv)\b|-(?:outv|pipelinev|errorv|warningv|informationv)|[‘’‚‛“”„‟]'
$gpRxB = '(?s)<<-?[ \t]*([''"]?)([A-Za-z_]\w*)\1[^\n]*\n(?:.*?\n)?[ \t]*\2[ \t]*(?=\n|$)|''[^'']*''|"(?:[^"\\]|\\.)*"|\\.|(?<![^\s;&|()])#[^\n]*|[0-9]*[<>]&[0-9-]*|&>>?|\|&|&&|\|\||;;|[;\n|&(){}]|[^''"\\#;&|\n(){}<>]+|.'
$gpRxP = '(?s)@"[ \t]*\r?\n.*?\r?\n"@|@''[ \t]*\r?\n.*?\r?\n''@|''(?:[^'']|'''')*''|"(?:[^"`]|`.|"")*"|`.|<#.*?#>|(?<![^\s;|(){}])#[^\n]*|&&|\|\||[;\n|(){}]|[^''"`#;|\n(){}&<]+|.'

function GpUnder([string]$a, [string]$v) {
    $a.Equals($v, [StringComparison]::OrdinalIgnoreCase) -or $a.StartsWith($v + '/', [StringComparison]::OrdinalIgnoreCase)
}
function GpLex([string]$f) {          # 드라이브 꼴 절대 경로를 글자로 정규화 · 모르면 $null
    $f = $f -replace '^/([A-Za-z])(/|$)', '$1:/'
    if ($f -notmatch '^[A-Za-z]:/') { return $null }
    $parts = [System.Collections.Generic.List[string]]::new()   # New-Object·Where-Object 같은 cmdlet 은 첫 호출에 수백 ms(11-18 잼) — .NET 으로
    foreach ($c in $f.Substring(3).Split('/')) {
        if ($c -eq '' -or $c -eq '.') { continue }
        if ($c -eq '..') { if ($parts.Count) { $parts.RemoveAt($parts.Count - 1) }; continue }
        if ($c -match '[.\s]$|:') { return $null }        # 끝 점·빈칸(윈도가 떼고 엶) · 대체 스트림(::$INDEX_ALLOCATION)
        $parts.Add($c)
    }
    $f.Substring(0, 1).ToUpper() + ':/' + ($parts -join '/')
}
function GpReal([string]$n) {         # 디스크에 있는 앞부분의 정션·링크를 푼다 · 없는 꼬리는 새로 만들 자리라 링크일 수 없다 · 모르면 $null
    for ($hop = 0; $hop -le 8; $hop++) {
        $parts = $n.Substring(3).Split([char[]]'/', [StringSplitOptions]::RemoveEmptyEntries)
        $cur = $n.Substring(0, 2); $jump = $null
        for ($i = 0; $i -lt $parts.Length; $i++) {
            $x = $cur + '/' + $parts[$i]
            if (-not ([IO.Directory]::Exists($x) -or [IO.File]::Exists($x))) { return $n }
            $at = [IO.File]::GetAttributes($x)
            if (($at -band [IO.FileAttributes]::ReparsePoint) -eq 0) { $cur = $x; continue }
            $t = "$(@((Get-Item -LiteralPath $x -Force).Target)[0])".Replace('\', '/') -replace '^//\?/|^/\?\?/', ''
            if (-not $t) { return $null }                 # 대상을 못 읽는 재분석 지점(클라우드 파일 등)
            if ($t -notmatch '^[A-Za-z]:/') { $t = $cur + '/' + $t }   # 상대 링크 = 링크가 든 폴더 기준
            $jump = GpLex ($t + '/' + $(if ($i + 1 -lt $parts.Length) { $parts[($i + 1)..($parts.Length - 1)] -join '/' } else { '' }))
            if (-not $jump) { return $null }
            break
        }
        if (-not $jump) { return $n }
        $n = $jump
    }
    $null
}
function GpOut([string]$base, [string]$tail) {   # base = …/.obsidian/plugins · tail = 그 밑
    if ($base -match '[$%`~*?\[\]{}"''<>|]') { return $false }    # 앞부분의 변수·8.3·글롭·묶음 = 모름
    $known = $base; $opaque = $false
    $tp = $tail.Split([char[]]'/', [StringSplitOptions]::RemoveEmptyEntries)
    foreach ($c in $tp) { if ($c -match '\.\.|^\.[^/]*[*?\[]|[(){}]') { return $false } }   # 꼬리로 거슬러 오름(.. · .* · 묶음)
    foreach ($c in $tp) {
        if ($c -match '[$%`~*?\[\]]') { $opaque = $true; break }        # 꼬리의 $f · * = 그 폴더 안 이름 하나
        $known += '/' + $c
    }
    $n = GpLex $known
    if (-not $n -or $n[0] -ne $gpV[0][0]) { return $false }      # 다른 드라이브 글자(subst · 연결 드라이브가 볼트일 수 있다)
    foreach ($v in $gpV) { if (GpUnder $n $v) { return $false } }
    $r = GpReal $n
    if (-not $r -or $r[0] -ne $gpV[0][0]) { return $false }
    foreach ($v in $gpV) { if (GpUnder $r $v) { return $false } }
    if ($opaque -and [IO.Directory]::Exists($r)) {                # 이름 모르는 자식 = 그 폴더에 링크가 하나도 없어야
        foreach ($e in [IO.Directory]::EnumerateFileSystemEntries($r)) {
            if ([IO.File]::GetAttributes($e) -band [IO.FileAttributes]::ReparsePoint) { return $false }
        }
    }
    $true
}
function GpScan([string]$d, [bool]$ps) {   # 맨 윗단 문장 나누기 · 짝 없는 따옴표 = Broken · 괄호·낱말 블록이 어긋나면 Unsure
    $o = [pscustomobject]@{ Broken = $false; Unsure = $false; Stmts = [System.Collections.Generic.List[object]]::new(); Sq = [System.Collections.Generic.List[object]]::new() }
    $seps = if ($ps) { @(';', "`n", '&&', '||', '|') } else { @(';', "`n", '&&', '||', '|', '|&', '&', ';;') }
    $depth = 0; $st = 0; $sep = '^'
    foreach ($t in [regex]::Matches($d, $(if ($ps) { $gpRxP } else { $gpRxB }))) {
        $v = $t.Value
        if ($v -eq '"' -or $v -eq "'") { $o.Broken = $true; return $o }
        if ($v.Length -gt 1 -and $v[0] -eq [char]39) { $o.Sq.Add(@($t.Index, ($t.Index + $v.Length))); continue }
        if ($v -eq '(' -or $v -eq '{') { $depth++; continue }
        if ($v -eq ')' -or $v -eq '}') { $depth--; if ($depth -lt 0) { $o.Unsure = $true; $depth = 0 }; continue }
        if ($depth -eq 0 -and $seps -contains $v) {
            $o.Stmts.Add([pscustomobject]@{ S = $st; E = $t.Index; Sep = $sep; After = $v; Top = $true; Chain = 0 })
            $sep = $v; $st = $t.Index + $v.Length
        }
    }
    $o.Stmts.Add([pscustomobject]@{ S = $st; E = $d.Length; Sep = $sep; After = '$'; Top = $true; Chain = 0 })
    if ($depth -ne 0) { $o.Unsure = $true }
    $kw = 0; $ch = 0
    foreach ($s in $o.Stmts) {
        if ($s.Sep -notin '&&', '|', '|&') { $ch++ }      # && · 파이프로 이은 문장 = 한 사슬
        $s.Chain = $ch
        if ($ps) { continue }
        $w = if ($d.Substring($s.S, $s.E - $s.S) -match '^\s*([a-z]+)\b') { $Matches[1] } else { '' }
        if ($w -in 'if', 'case', 'for', 'while', 'until', 'select') { $s.Top = $false; $kw++ }
        elseif ($w -in 'fi', 'esac', 'done') { $s.Top = $false; $kw--; if ($kw -lt 0) { $o.Unsure = $true; $kw = 0 } }
        else { $s.Top = ($kw -eq 0) }
    }
    if ($kw -ne 0) { $o.Unsure = $true }
    $o
}
function GpChain([int]$pos) { foreach ($s in $gsc.Stmts) { if ($pos -ge $s.S -and $pos -le $s.E) { return $s.Chain } }; -1 }
function GpVar([string]$name, [int]$use, [int]$dep) {   # 확실한 변수 값(쓰는 자리 $use 에서) · 모르면 $null
    if ($dep -gt 6 -or $name -match $gpDeny) { return $null }
    $ps = ($tool -eq 'PowerShell'); $e = [regex]::Escape($name)
    if ($ps) {   # 이 이름을 묶는 글: 대입 · foreach · 여럿 대입 · 범위 붙은 이름 · ++ · -XxxVariable 이름
        $nb = [regex]::Matches($gd, '(?i)\$\{?' + $e + '\}?\s*(?:[-+*/%]|\?\?)?=(?!=)|\(\s*\$' + $e + '\s+in\b|\$' + $e + '\s*,|\$\w+:' + $e + '\b|\$' + $e + '\s*(?:\+\+|--)|(?:\+\+|--)\s*\$' + $e + '\b|(?<!\S)-\w+(?:\s+|\s*:\s*)[''"]?\+?' + $e + '[''"]?(?=[\s;|)]|$)').Count
    } else {
        if ([regex]::IsMatch($gd, '\$\{' + $e + '[^}\w]')) { return $null }    # ${S:=…} · ${S/…} 꼴
        $nb = [regex]::Matches($gd, '(?<!\$|\$\{)\b' + $e + '\b').Count        # $ · ${ 없는 맨 이름 = 묶는 자리(read S · for S · S= …)
    }
    if ($nb -ne 1) { return $null }
    $rx = if ($ps) { '(?i)^\s*\$\{?' + $e + '\}?\s*=\s*(.+?)\s*$' } else { '^\s*' + $e + '=((?:''[^'']*''|"[^"]*"|[^\s''"])*)\s*$' }
    foreach ($s in $gsc.Stmts) {
        $mm = [regex]::Match($gd.Substring($s.S, $s.E - $s.S), $rx)
        if (-not $mm.Success) { continue }
        # 맨 윗단 · 쓰기 전에 끝남 · 뒤가 파이프·배경이 아님 · 앞이 처음·;·줄바꿈(&& 면 같은 사슬 안에서만)
        if (-not $s.Top -or $s.E -gt $use -or $s.After -notin '$', ';', "`n", '&&') { return $null }
        if ($s.Sep -eq '&&') { if ((GpChain $use) -ne $s.Chain) { return $null } }
        elseif ($s.Sep -notin '^', ';', "`n") { return $null }
        return (GpVal $mm.Groups[1].Value $ps $s.S $dep)
    }
    $null
}
function GpVal([string]$raw, [bool]$ps, [int]$pos, [int]$dep) {   # 대입 값 = 글자 그대로(+ 앞서 확실한 변수) · 모르면 $null
    if ($ps -and $raw -notmatch '^(?:"[^"]*"|''[^'']*'')$') { return $null }   # PS 맨 글자 값은 명령 실행이다
    if (-not $ps -and $raw.Contains('\')) { return $null }
    $out = ''
    foreach ($g in [regex]::Matches($raw, '''[^'']*''|"[^"]*"|[^''"]+')) {
        $x = $g.Value
        if ($x[0] -eq [char]39) { $out += $x.Substring(1, $x.Length - 2); continue }    # 홑따옴표 = 글자 그대로
        if ($x[0] -eq [char]34) { $x = $x.Substring(1, $x.Length - 2) } elseif ($x.Contains('~')) { return $null }   # bash 맨 ~ = 홈
        if ($x -match '`|\$\(|\$\{?\w+\}?[:\[]') { return $null }
        $i = 0
        foreach ($m in [regex]::Matches($x, '\$(?:\{(\w+)\}|(\w+))')) {
            $lit = $x.Substring($i, $m.Index - $i)
            if ($lit.Contains('$')) { return $null }
            $r = GpVar ($m.Groups[1].Value + $m.Groups[2].Value) $pos ($dep + 1)
            if (-not $r) { return $null }
            $out += $lit + $r; $i = $m.Index + $m.Length
        }
        if ($x.Substring($i).Contains('$')) { return $null }
        $out += $x.Substring($i)
    }
    $out.Replace('\', '/')
}
function GpOne([int]$at, [string]$val) {   # 플러그인 일치 하나가 볼트 밖임이 확실한가
    $tm = [regex]::Match($gdn.Substring(0, $at), '[^\s"''=(,;|&<>]*$', 'RightToLeft')
    $tok = $tm.Value; $st = $tm.Index; $k = $st - 1
    $dl = if ($k -ge 0) { [string]$gdn[$k] } else { ' ' }
    # 따옴표에 바로 붙은 낱말("$S"/… · abc"…") = 셸이 앞 글과 이어 붙인다 → 모름. C:/… 는 앞에 무엇이 붙으면 쓸 수 없는 경로라 뺀다(r'C:/…' 파이썬 글 등).
    if (($dl -eq '"' -or $dl -eq "'") -and $k -ge 1 -and [string]$gdn[$k - 1] -notmatch '[\s=(,;|&<>]' -and $tok -notmatch '^[A-Za-z]:/') { return $false }
    $j = $at + $val.Length                                                                # 뒤로 이어 붙임(…/plugins/"$f" · '…/plugins/'x)도 모름
    if ($j + 1 -lt $gdn.Length -and ($gdn[$j] -eq [char]34 -or $gdn[$j] -eq [char]39) -and [string]$gdn[$j + 1] -notmatch '[\s;|&<>),]') { return $false }
    if ($tok -match '^-\w+:(.+)$') { $tok = $Matches[1]; $st = $at - $tok.Length }      # PowerShell -이름:값
    $head = $val.Substring(0, 17); $tail = $val.Substring(17)                             # '.obsidian/plugins' · '/…'
    if ($tok -match '^\$(?:\{([A-Za-z_]\w*)\}|([A-Za-z_]\w*))(/.*)?$') {
        $name = "$($Matches[1])$($Matches[2])"; $rest = "$($Matches[3])"
        if ($dl -eq "'" -or -not $gsc -or $gsc.Unsure) { return $false }
        foreach ($q in $gsc.Sq) { if ($st -ge $q[0] -and $st -lt $q[1]) { return $false } }               # 홑따옴표 안 = 글자 그대로
        $v = GpVar $name $st 0
        if (-not $v) { return $false }
        return (GpOut ($v + $rest + $head) $tail)
    }
    if ($tok -match '^(?:[A-Za-z]:/|/[A-Za-z]/)') {
        if (-not (GpOut ($tok + $head) $tail)) { return $false }
        # PowerShell 의 /c/… 는 드라이브가 아니라 지금 드라이브 뿌리 밑 c 폴더다 — 그 뜻으로도 밖이어야
        if ($tool -eq 'PowerShell' -and $tok -match '^/[A-Za-z]/') { return (GpOut ($gpV[0].Substring(0, 2) + $tok + $head) $tail) }
        return $true
    }
    # 다른 폴더 아래 같은 이름(test/vault-ci/.obsidian/… · 지금 규칙) — ./ ../ · .. · 끝 점(.../) · // · 변수·$(…) · ~ · : · 묶음·글롭은 코어.
    # 뿌리(/…)는 PowerShell·파일 도구에선 지금 드라이브 뿌리(\Claude_Brain\… = 볼트)라 코어, Git Bash 에선 Git 폴더 밑이라 지금처럼 둔다.
    ($tok.Length -ge 2 -and $tok.EndsWith('/') -and $tok -notmatch '^\.{1,2}/|^//|[$%`~:(){}*?\[\]!]|(^|/)\.\.(/|$)|[.\s]/' -and $tail -notmatch '(^|/)\.\.(/|$)' -and
     ($tool -eq 'Bash' -or -not $tok.StartsWith('/')))
}
function GpVerdicts {   # 이 명령의 플러그인 일치마다 «볼트 밖임이 확실» 여부 · 못 이으면 빈 목록(= 하나도 빼지 않음)
    $ErrorActionPreference = 'Stop'
    $res = [System.Collections.Generic.List[bool]]::new()
    try {
        $gd = [regex]::Unescape($probe); $gdn = $gd.Replace('\', '/')
        $v0 = GpLex ($root -replace '\\', '/')
        if (-not $v0) { return ,$res }
        $gpV = @($v0); $vr = GpReal $v0
        if ($vr -and $vr -ne $v0) { $gpV += $vr }
        $ms = [regex]::Matches($gdn, '\.obsidian/plugins/[^\s",;|&''<>)]*')
        $pc = 0; foreach ($x in [regex]::Matches($p, $rxLoop)) { if ($x.Groups[1].Value.StartsWith('.obsidian/plugins/')) { $pc++ } }
        $gsc = $null; $ok = $true
        if ($tool -in 'Bash', 'PowerShell') {
            if ($gd -match '(?i)mklink|junction|symboliclink|hardlink|\bln\s|createsymboliclink|createhardlink|fsutil|\bsubst\b|new-psdrive|\bndr\b|\bnet\s+use\b|\bmount\b') { $ok = $false }
            else {
                $gsc = GpScan $gd ($tool -eq 'PowerShell')
                if ($gsc.Broken) { $ok = $false }
                elseif ($gd -match $(if ($tool -eq 'PowerShell') { $gpBadP } else { $gpBadB })) { $gsc.Unsure = $true }
            }
        }
        foreach ($m in $ms) {
            $one = $false
            try { $one = [bool]($ok -and (GpOne $m.Index $m.Value)) } catch { $one = $false }
            $res.Add($one)
        }
        # $p 의 일치는 원문 일치를 몇 개씩 묶은 것이다($p 는 줄바꿈 /n 에서 꼬리가 안 끊김). 개수가 다르면 차례로 못 잇는다 —
        # 원문의 일치가 모두 밖일 때만 다 빼고, 아니면 하나도 빼지 않는다.
        if ($res.Count -ne $pc) {
            $all = $res.Count -gt 0 -and -not $res.Contains($false)
            $res.Clear()
            if ($all) { for ($i = 0; $i -lt $pc; $i++) { $res.Add($true) } }
        }
    } catch { $res.Clear() }
    return ,$res
}

$target = $forced
if ($forced) {
    # 설치 대본 — 다른 볼트(시험 볼트)에 까는 것은 코어가 아니다
    if ($p -match 'install\.mjs\s+["'']?((?:[A-Za-z]:|/[A-Za-z])/[^\s"'']*)') {
        $dst = ($Matches[1] -replace '^/([A-Za-z])/', '$1:/').TrimEnd('/')
        if (-not $dst.Equals($vaultN, [StringComparison]::OrdinalIgnoreCase)) { exit 0 }
    }
} else {
    $rxLoop = '(?:(?:[A-Za-z]:|/[A-Za-z])/[^\s";,|&]*?)?(' + $core + ')'
    $gpR = $null; $gpK = 0
    foreach ($m in [regex]::Matches($p, $rxLoop)) {
        if ($m.Groups[1].Value.StartsWith('.obsidian/plugins/')) {
            # 플러그인 자리 = 3.5절 판정(볼트 밖임이 확실하면 뺀다). 같은 차례의 판정을 쓴다.
            if ($null -eq $gpR) { $gpR = GpVerdicts }
            $gpOut = $gpK -lt $gpR.Count -and $gpR[$gpK]; $gpK++
            if ($gpOut) { continue }
            $target = $m.Groups[1].Value
            break
        }
        $abs = $m.Value -replace '^/([A-Za-z])/', '$1:/'
        if ($abs -match '^[A-Za-z]:/') {
            if (-not $abs.StartsWith($vaultN + '/', [StringComparison]::OrdinalIgnoreCase)) { continue }
        } elseif ($p.Substring(0, $m.Index) -match '(^|[\s"''=(,;|&<>])(?!\.\.?/)[^\s"''=(,;|&<>$%]+/$') {
            continue   # 다른 폴더 아래 같은 이름(시험 볼트 test/vault-ci/.obsidian/… · ~/.claude/settings.json) · 변수로 시작하는 경로·./·../ 는 코어로 본다
        }
        $target = $m.Groups[1].Value
        break
    }
}
if (-not $target) { exit 0 }

# ── 4. 셸 도구는 '쓰기 동사'가 코어와 같은 절(clause)에 있을 때만 건다.
# 명령 전체에서 AND로 보면 `py … search.py --eval x >> 비코어; rm err.log`처럼
# 코어를 읽기만 하는 명령이 전부 걸린다(2026-08-17 실측: 셸 발동의 61%가 비쓰기).
# 인라인 코드(-c / -Command / heredoc)는 절로 쪼갤 수 없으므로 '쓰기 표지'로 가른다 —
# 코어 스크립트 '실행'·설정 '검사'와 코어 '쓰기'를 가르는 선이다.
if ($tool -in 'Bash','PowerShell' -and -not $forced) {
    $fire = $false
    $rxCode = "(?s)(?:-c|-Command)\s+(['""]).*?\1|<<\s*['""]?(\w+).*?\2"
    $code = -join ([regex]::Matches($p, $rxCode) | ForEach-Object { $_.Value })
    # 코드를 지운 자리에 표지를 남긴다. 공백으로 지우면 python3 -c "…" CLAUDE.md 에서
    # 코어가 스크립트 자리로 보여, 아래 인터프리터 예외가 이것까지 통과시킨다(케이스 04).
    $shell = [regex]::Replace($p, $rxCode, ' INL ')
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
    # 코드 전체에서 AND로 보면 코어를 '읽기만' 하는 코드가 **다른 파일**에 쓰기만 해도 걸린다
    # (2026-08-22 실측: 분기 a 21건 중 11건이 그것). 그래서 문(;·줄바꿈) 단위로 좁힌다.
    # 다만 경로를 담은 변수를 함께 추적해야 한다 — 이 볼트의 실제 코어 쓰기가
    # P="CLAUDE.md" 와 io.open(P,"w") 로 줄이 갈린다(케이스 N19). 줄 단위 단순 AND는
    # 그 형태를 놓친다. 별칭(Q=P)·경로 조립은 추적하지 않는다 = 수용한 거짓 음성(N22).
    $rxW = ',\s*[''"][wax]\+?b?[''"]|WriteAll\w+|AppendAll\w+|write_text|Set-Content|Add-Content|Out-File|os\.remove|\.unlink|os\.rename|shutil\.|json\.dump\(|\.truncate\('
    if ($code -match ('(' + $core + ')') -and $code -match $rxW) {
        # 줄바꿈은 이 시점에 '/n' 으로 접혀 있다(머리 파일의 백슬래시 정규화).
        $stmts = $code -split '(?:;|/n|\r?\n)'
        $vars = @()
        foreach ($st in $stmts) {
            foreach ($m in [regex]::Matches($st, '([A-Za-z_]\w*)\s*=\s*[''"]([^''"]*)[''"]')) {
                if ($m.Groups[2].Value -match ('(' + $core + ')')) { $vars += $m.Groups[1].Value }
            }
        }
        $rxV = if ($vars) { '\b(?:' + ((($vars | Sort-Object -Unique) |
                ForEach-Object { [regex]::Escape($_) }) -join '|') + ')\b' } else { $null }
        foreach ($st in $stmts) {
            if ($st -notmatch $rxW) { continue }
            if (($st -match ('(' + $core + ')')) -or ($rxV -and $st -match $rxV)) { $fire = $true; break }
        }
    }
    # (b) 코드 '밖'의 코어 = 쓰기 동사가 같은 절에 있을 때만. 껍데기에서 판정하므로
    #     `python3 -c "…" CLAUDE.md`(인자 전달)는 남고 `py -c "…CLAUDE.md…"`(코드 안)는 사라진다.
    if (-not $fire) {
        # 인터프리터는 '코어를 실행'과 '코어를 미지의 코드에 넘김'을 가른다. 코어가 첫
        # 비옵션 인자(스크립트 자리)면 실행 = 읽기다 — python 3_시스템/search.py --q …
        # 가 승인을 물었다(2026-08-22 실측 3건, 전부 볼트 검색). 그 자리가 아니면
        # (python3 -c "…" CLAUDE.md) 코드를 볼 수 없으므로 그대로 건다.
        $verbs ='>\s*&?[^\s;|&]*(' + $core + ')|sed\s+-i|tee\b|\bcp\b|\bmv\b|\brm\b|\btruncate\b|Set-Content|Add-Content|Out-File|New-Item|Remove-Item|Move-Item|Copy-Item|git\s+(checkout|restore|apply|reset)|WriteAll\w+|AppendAll\w+|\b(?:python\d?|node|perl)\b(?!\s+(?:-\S+\s+)*(?:' + $core + '))|\bpy\s+(-\d(\.\d+)?\s+)?-c\b|\bchmod\b|update-index'
        foreach ($c in ($shell -split '(?:;|&&|\|\||\||\r?\n)')) {
            if ($c -notmatch ('(' + $core + ')')) { continue }
            # cp 는 끝 인자가 대상이다 — 코어를 다른 데로 복사하는 것은 읽기(개정 7 · 격리 사본을 뜰 때마다 승인 창이 떴다)
            if ($c -match '(^|\s)cp\s' -and $c -notmatch ('(' + $core + ')["'']?\s*$') -and ($c -replace '(^|\s)cp\s', ' ') -notmatch $verbs) { continue }
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
    } elseif (-not $expOk) { $tag = 'TOKEN-EXPIRED' }   # 만료가 먼저다 — 다른 세션에 묶인 만료 토큰이 OTHERSESSION 으로 찍혀 집계가 틀어졌다(11-02)
}

Add-Content -Path $logf -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [$mode] $tag $tool $target" -ErrorAction SilentlyContinue

$reason = @'
⚠ 코어 수정 — ADR-006. 승인받은 수정도 아래를 확인한다.
- 필요한가: 새 강제층은 실측 2건 이상일 때만. 기존 기능·훅으로 되면 짓지 않는다.
- 절차: diff 제시 → 승인 → ADR. 고치라는 지시가 코어 수정 승인까지 뜻하진 않는다. 롤백 커밋을 먼저 확보한다.
- 검증: 격리 환경에서, 이 변경이 건드리는 축을 덮는 회귀 케이스로. powershell 5.1 로 돌린다.
- 범위: 의도한 것만 바꾼다. 검사 대상을 넓히지 않고 외부 의존성을 넣지 않는다. 실패 방향을 정한다(검증 실패 = 막음, 도구 없음 = 통과).
- 비용: CLAUDE.md·recent·open-loops·훅 출력을 늘리면 하나를 뺀다.
- 환경: .ps1 은 UTF-8 BOM · 줄바꿈 LF(파이썬은 newline='') · 한글 경로·로캘 주의.
- 파급: 무인 실행(승인 대기로 멈춤)과 배포판 오염을 확인한다.
전문 = 3_시스템/_ref/코어수정-준수사항-체크리스트.md
'@

# 토큰은 '승인'만 면제한다. 준수사항은 그대로 간다 —
# ADR-006 원 요구(사용자 인박스 2026-07-28)가 "승인받은 수정이더라도 매번 준수사항"이었다.
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
