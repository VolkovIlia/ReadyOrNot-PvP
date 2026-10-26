# Removes a UE4SS installation made by tools/install_ue4ss.ps1 (and only that one).
#   powershell -File tools/uninstall_ue4ss.ps1 [-GameDir <path>]
param(
    [string]$GameDir = "C:\Program Files (x86)\Steam\steamapps\common\Ready Or Not"
)

$ErrorActionPreference = "Stop"
$win64 = Join-Path $GameDir "ReadyOrNot\Binaries\Win64"
$marker = Join-Path $win64 "ue4ss\.roncomp-install.txt"
if (-not (Test-Path $marker)) { throw "No UE4SS installed by this project in $win64." }
if (Get-Process -Name "ReadyOrNotSteam-Win64-Shipping" -ErrorAction SilentlyContinue) { throw "Close the game first." }

Remove-Item (Join-Path $win64 "dwmapi.dll") -Force
Remove-Item (Join-Path $win64 "ue4ss") -Recurse -Force
Write-Host "UE4SS removed from $win64."
