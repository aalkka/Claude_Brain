# 절전 지킴이 — 덮개가 닫힌 동안 재생되는 미디어(유튜브 탭 등)를 멈춘다.
# gpu_guard.py 가 들어갈 때 띄우고 나올 때 끈다. Windows PowerShell 5.1 전용(WinRT 투영 · pwsh 7 은 안 됨).
# 한 줄 출력 = 멈춘 세션 하나(JSON). 부모(-Parent)가 죽으면 스스로 끝난다.
# 까닭(11-13 실측): 윈도 업데이트 재시작 → 자동 로그온 → 크롬이 --restore-last-session 으로 탭을 되살림 → 유튜브가 덮개 닫힌 채 재생.
param([int]$Parent = 0, [int]$Every = 3)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
} | Select-Object -First 1
function Await($op, [type]$t) {
    $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op))
    [void]$task.Wait(10000)
    $task.Result
}
function Say($o) { [Console]::Out.WriteLine(($o | ConvertTo-Json -Compress)); [Console]::Out.Flush() }

$M = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media.Control, ContentType = WindowsRuntime]
$mgr = Await ($M::RequestAsync()) $M
Say @{ ready = $true }
while ($true) {
    if ($Parent -and -not (Get-Process -Id $Parent -ErrorAction SilentlyContinue)) { break }
    foreach ($s in $mgr.GetSessions()) {
        try {
            if ($s.GetPlaybackInfo().PlaybackStatus -eq 'Playing') {
                $ok = Await ($s.TryPauseAsync()) ([bool])
                Say @{ app = $s.SourceAppUserModelId; ok = [bool]$ok }
            }
        } catch { Say @{ err = $_.Exception.Message } }
    }
    Start-Sleep -Seconds $Every
}
