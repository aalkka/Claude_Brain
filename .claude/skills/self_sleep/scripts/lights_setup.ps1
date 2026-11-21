# 관리자로 한 번 실행(사람 승인 뒤): C:\Program Files\BrainLight\logo.ps1 설치 + 예약 작업 셋(끔·되돌림·읽기) 등록 — 자체 절전의 «로고 조명 끔» 칸이 이 작업이 있을 때만 보인다.
#   Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','<이 파일>','-Src','<scripts\lights_lenovo.ps1>','-User',"$env:USERDOMAIN\$env:USERNAME",'-Out','<결과.txt>'
# 레노버(LENOVO_LIGHTING WMI) 기기에서만 뜻이 있다. 대본을 볼트(사용자 쓰기 가능)에 두고 관리자로 돌리면 권한 상승 구멍이 되므로 Program Files 에 복사한다.
# 지우기: Unregister-ScheduledTask '외부뇌 로고 조명 *' + C:\Program Files\BrainLight 삭제(관리자).
param([string]$Src, [string]$User, [string]$Out)
$r = New-Object System.Collections.Generic.List[string]
try {
    $dst = 'C:\Program Files\BrainLight'
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    Copy-Item -LiteralPath $Src -Destination (Join-Path $dst 'logo.ps1') -Force
    $r.Add('acl ' + ((Get-Acl $dst).Access | Where-Object { $_.IdentityReference -match 'Users|사용자' } | ForEach-Object { "$($_.IdentityReference)=$($_.FileSystemRights)" }) -join '; ')
    $p = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Highest
    $s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 2) -MultipleInstances Queue -StartWhenAvailable
    foreach ($m in @(@('끔', 'off'), @('되돌림', 'restore'), @('읽기', 'get'))) {
        $a = New-ScheduledTaskAction -Execute 'conhost.exe' -Argument ('--headless powershell.exe -NoProfile -ExecutionPolicy Bypass -File "' + (Join-Path $dst 'logo.ps1') + '" -Mode ' + $m[1])
        Register-ScheduledTask -TaskName ('외부뇌 로고 조명 ' + $m[0]) -Action $a -Principal $p -Settings $s -Description '외부뇌 자체 절전 — 덮개 닫힌 동안 로고 조명을 끄고 열면 되돌림' -Force | Out-Null
        $r.Add('task ok ' + $m[0])
    }
} catch { $r.Add('ERR ' + $_.Exception.Message) }
[IO.File]::WriteAllLines($Out, $r, (New-Object Text.UTF8Encoding $false))
