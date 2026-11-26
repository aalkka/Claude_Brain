# First-level Explorer right-click menu: registers the unsigned identity package (no certificate, no Developer Mode).
# Windows requires admin once for this (one UAC prompt). Result goes to install-menu.log next to this script.
# install.py copies this script next to the DLL in the vault (3_system\door-app). Run that copy:
#   powershell -ExecutionPolicy Bypass -File <door-app>\install-menu.ps1            install
#   powershell -ExecutionPolicy Bypass -File <door-app>\install-menu.ps1 -Remove    remove
param([switch]$Remove)
$app = $PSScriptRoot
$log = Join-Path $app 'install-menu.log'
$me = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
if (-not $me.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'))
    if ($Remove) { $a += '-Remove' }
    Start-Process powershell.exe -Verb RunAs -ArgumentList $a -Wait
    Get-Content -LiteralPath $log
    exit
}
$out = @((Get-Date).ToString('s'))
try {
    if ($Remove) {
        Get-AppxPackage -Name 'BrainInbox.Menu' | Remove-AppxPackage -ErrorAction Stop
    } else {
        # Same version at a new external location cannot update in place: remove first
        Get-AppxPackage -Name 'BrainInbox.Menu' | Remove-AppxPackage -ErrorAction Stop
        Add-AppxPackage -Path (Join-Path $app 'brain-inbox-menu.msix') -ExternalLocation $app -AllowUnsigned -ForceUpdateFromAnyVersion -ErrorAction Stop
    }
    $out += 'OK'
} catch {
    $out += 'FAILED: ' + $_.Exception.Message
}
$p = Get-AppxPackage -Name 'BrainInbox.Menu'
$out += 'registered: ' + $(if ($p) { $p.PackageFullName + ' / ' + $p.SignatureKind } else { 'no' })
$out | Set-Content -LiteralPath $log -Encoding UTF8
