# 자체 절전(self_sleep) — 레노버 조명 어댑터: 덮개 로고 조명 끔·되돌림(레노버 WMI LENOVO_LIGHTING · Lighting_ID 3·4 = 로고).
# 관리자 권한 예약 작업 «외부뇌 로고 조명 끔» · «외부뇌 로고 조명 되돌림» 이 부른다(self_sleep.py 가 들어갈 때·나올 때).
# 이 파일은 관리자만 고칠 수 있는 자리(C:\Program Files\BrainLight)에 lights_setup.ps1 이 복사한다 — 일반 권한 프로그램이 작업을 불러도 조명만 바뀐다.
# 처음 판 = gpu_guard 0.2 logo.ps1(11-13) · 설치된 판과 같은 동작.
param([ValidateSet('off', 'restore', 'get')][string]$Mode = 'get')
$ErrorActionPreference = 'Stop'
$ids = 3, 4
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$prevFile = Join-Path $dir 'prev.json'
$logFile = Join-Path $dir 'log.txt'
function Log($s) { Add-Content -LiteralPath $logFile -Value ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " $Mode $s") -Encoding UTF8 }

$l = @(Get-WmiObject -Namespace root\WMI -Class LENOVO_LIGHTING_METHOD)[0]
$sup = @{}
Get-WmiObject -Namespace root\WMI -Class LENOVO_LIGHTING_DATA | ForEach-Object { $sup[[int]$_.Lighting_Id] = [int]$_.State_Type_Num }
function Get-L($id) {
    $in = $l.GetMethodParameters('Get_Lighting_Current_Status')
    $in['Lighting_ID'] = [byte]$id
    $o = $l.InvokeMethod('Get_Lighting_Current_Status', $in, $null)
    [ordered]@{ s = [int]$o['Current_State_Type']; b = [int]$o['Current_Brightness_Level'] }
}
function Set-L($id, $s, $b) {
    $in = $l.GetMethodParameters('Set_Lighting_Current_Status')
    $in['Lighting_ID'] = [byte]$id
    $in['Current_State_Type'] = [byte]$s
    $in['Current_Brightness_Level'] = [byte]$b
    [void]$l.InvokeMethod('Set_Lighting_Current_Status', $in, $null)
}

try {
    $use = $ids | Where-Object { $sup[$_] -gt 0 }
    if ($Mode -eq 'get') {
        $diag = 'l=' + ($null -ne $l) + ' sup=' + (($sup.GetEnumerator() | Sort-Object Name | ForEach-Object { "$($_.Name):$($_.Value)" }) -join ',')
        try {
            $in = $l.GetMethodParameters('Get_Lighting_Current_Status'); $in['Lighting_ID'] = [byte]3
            $o = $l.InvokeMethod('Get_Lighting_Current_Status', $in, $null)
            $diag += ' raw3=' + (($o.Properties | ForEach-Object { "$($_.Name):$($_.Value)" }) -join ',')
        } catch { $diag += ' raw3 오류 ' + $_.Exception.Message.Split("`n")[0] }
        Log ($diag + ' | ' + (($use | ForEach-Object { "$_=" + ((Get-L $_) | ConvertTo-Json -Compress) }) -join ' '))
    } elseif ($Mode -eq 'off') {
        $prev = [ordered]@{}
        foreach ($id in $use) { $prev["$id"] = Get-L $id }
        if (-not (Test-Path -LiteralPath $prevFile)) {          # 되돌리기 전에 또 끄면 «꺼진 값»으로 덮지 않는다
            [IO.File]::WriteAllText($prevFile, ($prev | ConvertTo-Json -Compress))
        }
        foreach ($id in $use) { Set-L $id 0 $prev["$id"].b }
        Log ('전 ' + ($prev | ConvertTo-Json -Compress) + ' 뒤 ' + (($use | ForEach-Object { "$_=" + ((Get-L $_) | ConvertTo-Json -Compress) }) -join ' '))
    } else {
        if (-not (Test-Path -LiteralPath $prevFile)) { Log '되돌릴 값 없음'; exit 0 }
        $prev = Get-Content -LiteralPath $prevFile -Raw | ConvertFrom-Json
        foreach ($p in $prev.PSObject.Properties) { Set-L ([int]$p.Name) $p.Value.s $p.Value.b }
        Remove-Item -LiteralPath $prevFile
        Log ('뒤 ' + (($use | ForEach-Object { "$_=" + ((Get-L $_) | ConvertTo-Json -Compress) }) -join ' '))
    }
} catch { Log ('오류 ' + $_.Exception.Message.Split("`n")[0]) ; exit 1 }
