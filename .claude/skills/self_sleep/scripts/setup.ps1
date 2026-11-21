# 자체 절전 예약 작업 등록 — 사람 승인 뒤 실행한다(지속 설정). 관리자 불필요(이 사용자 로그온 트리거 · gpu_guard 11-13 실측).
#   powershell -ExecutionPolicy Bypass -File <볼트>\.claude\skills\self_sleep\scripts\setup.ps1                   # 등록 + 바로 띄움
#   powershell -ExecutionPolicy Bypass -File <볼트>\.claude\skills\self_sleep\scripts\setup.ps1 -RetireGpuGuard   # + 옛 «외부뇌 절전 지킴이»(gpu_guard) 작업을 끔(지우지 않음 · 되돌리기 = Enable-ScheduledTask)
#   powershell -ExecutionPolicy Bypass -File <볼트>\.claude\skills\self_sleep\scripts\setup.ps1 -Remove           # 지우기(돌던 것도 끔)
# 15분마다 «살아 있나»를 보고 없으면 띄운다 + 로그온 때 바로 · 이미 돌면 새로 안 뜬다(IgnoreNew + 대본 안 뮤텍스).
# 로고 조명 끄기는 관리자 설치가 따로 필요하다 → lights_setup.ps1(관리자로 한 번 · 레노버 기기만).
param([switch]$Remove, [switch]$RetireGpuGuard)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$name = '외부뇌 자체 절전'
$old = '외부뇌 절전 지킴이'
$py = Join-Path $PSScriptRoot 'self_sleep.py'

if ($Remove) {
    Stop-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'self_sleep\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Write-Output '지움'
    exit 0
}

$pyw = (Get-Command pyw -ErrorAction SilentlyContinue).Source
if (-not $pyw) { Write-Output '⚠ pyw(파이썬 런처)를 못 찾음 — 중단'; exit 1 }
if ($RetireGpuGuard -and (Get-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue)) {
    Stop-ScheduledTask -TaskName $old -ErrorAction SilentlyContinue
    Disable-ScheduledTask -TaskName $old | Out-Null
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Where-Object { $_.CommandLine -match 'gpu_guard\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Write-Output "옛 작업 끔: $old"
}
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)
$a = New-ScheduledTaskAction -Execute $pyw -Argument "-3 `"$py`" run" -WorkingDirectory $PSScriptRoot
$t = @((New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5) -RepetitionInterval (New-TimeSpan -Minutes 15)),
       (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"))
Register-ScheduledTask -TaskName $name -Action $a -Trigger $t -Settings $s -Force -Description '외부뇌: 덮개 닫힘·화면 꺼짐 때 자체 절전(윈도는 안 재움 · 칸마다 켬/끔 = 옵시디언 설정 «단계»)' | Out-Null
Start-ScheduledTask -TaskName $name
Start-Sleep -Seconds 4
py -3 $py status
