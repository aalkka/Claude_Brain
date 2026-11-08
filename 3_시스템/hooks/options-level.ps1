# 기능 단계 읽기(PS 판) — 3_시스템/options.py 의 읽기 규칙과 같다. 훅이 파이썬을 새로 띄우지 않으려고 둔다.
# 코어 표(options.registry.json)의 기능만 본다(모듈 기능은 파이썬으로). 배터리 규칙은 보지 않는다 —
# 배터리 낮춤은 상옵 → 하옵이라 «사용 안 함» 판정을 바꾸지 않는다. 어떤 오류도 'high'(지금 동작).
#   . (Join-Path $PSScriptRoot 'options-level.ps1'); Get-OptionLevel $vault 'search.semantic'
function Test-OptionSchema($x) {
    return (($x -is [int] -or $x -is [long] -or $x -is [double] -or $x -is [decimal]) -and $x -eq 1)
}
function Get-OptionLevel([string]$Vault, [string]$Id) {
    try {
        $lp = Join-Path $Vault '3_시스템\options.local.json'
        if (-not (Test-Path -LiteralPath $lp)) { return 'high' }
        $rg = [IO.File]::ReadAllText((Join-Path $Vault '3_시스템\options.registry.json'), [Text.Encoding]::UTF8) | ConvertFrom-Json
        $lc = [IO.File]::ReadAllText($lp, [Text.Encoding]::UTF8) | ConvertFrom-Json
        if (-not (Test-OptionSchema $rg.schema) -or -not (Test-OptionSchema $lc.schema)) { return 'high' }
        $f = @($rg.features | Where-Object { $_.id -is [string] -and $_.id -ceq $Id -and @($_.levels) -ccontains 'high' })[0]
        if (-not $f -or ($f.ready -is [bool] -and -not $f.ready)) { return 'high' }
        $p = if ($lc.levels -is [pscustomobject]) { @($lc.levels.PSObject.Properties | Where-Object { $_.Name -ceq $Id })[0] } else { $null }
        $v = if ($p) { $p.Value } else { $null }
        if ($v -is [string] -and @($f.levels) -ccontains $v -and @('high', 'low', 'off') -ccontains $v) { return $v }
    } catch {}
    return 'high'
}
