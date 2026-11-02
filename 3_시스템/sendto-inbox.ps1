# 탐색기 우클릭 «보내기 → 외부뇌 받은함» 바로 가기 (2026-10-29 · 볼트 개혁 로드맵 R1 · 설계안 §13 B2①)
# 보낸 파일은 1_수집/_inbox 로 «복사»된다(윈도 보내기 = 복사, 원래 파일은 그대로). 같은 내용 거르기·분류는 받은함 정리(로드맵 R8)가 한다.
# 사람이 탐색기에서 한 일이라 장부(fileops)에는 들어올 때가 아니라 정리할 때 남는다.
#   powershell -NoProfile -ExecutionPolicy Bypass -File 3_시스템/sendto-inbox.ps1           만들기
#   powershell -NoProfile -ExecutionPolicy Bypass -File 3_시스템/sendto-inbox.ps1 -Remove   지우기
param([switch]$Remove)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$vault = Split-Path $PSScriptRoot -Parent
$inbox = Join-Path $vault '1_수집\_inbox'
$link  = Join-Path ([Environment]::GetFolderPath('SendTo')) '외부뇌 받은함.lnk'
if ($Remove) {
    if (Test-Path $link) { Remove-Item -LiteralPath $link; '지움: ' + $link } else { '없음: ' + $link }
    exit 0
}
if (-not (Test-Path $inbox)) { New-Item -ItemType Directory -Force $inbox | Out-Null }
$sh = New-Object -ComObject WScript.Shell
$s = $sh.CreateShortcut($link)
$s.TargetPath = $inbox
$s.Description = '외부뇌 받은함(1_수집/_inbox)으로 복사'
$s.Save()
'만듦: ' + $link + ' → ' + $inbox
