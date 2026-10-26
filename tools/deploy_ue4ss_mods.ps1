# Copies this project's UE4SS mods (HostBrain/ue4ss-mods/*) into the game's ue4ss/Mods folder.
#   powershell -File tools/deploy_ue4ss_mods.ps1 [-GameDir <path>] [-Only <ModName>]
param(
    [string]$GameDir = "C:\Program Files (x86)\Steam\steamapps\common\Ready Or Not",
    [string]$Only = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$modsTarget = Join-Path $GameDir "ReadyOrNot\Binaries\Win64\ue4ss\Mods"
if (-not (Test-Path $modsTarget)) { throw "UE4SS is not installed (no $modsTarget). Run tools/install_ue4ss.ps1 first." }

$mods = Get-ChildItem (Join-Path $root "HostBrain\ue4ss-mods") -Directory
if ($Only) { $mods = $mods | Where-Object Name -eq $Only }
foreach ($mod in $mods) {
    $destination = Join-Path $modsTarget $mod.Name
    if (Test-Path $destination) { Remove-Item $destination -Recurse -Force }
    Copy-Item $mod.FullName $destination -Recurse
    Write-Host "Deployed $($mod.Name)"
}

# HostBrain loads its native guards from Mods/HostBrain/native (built by tools/build_hostbrain.ps1).
$hostBrain = Join-Path $modsTarget "HostBrain"
if (Test-Path $hostBrain) {
    $dll = Join-Path $root "build\hostbrain\RonCompNative.dll"
    if (-not (Test-Path $dll)) { throw "RonCompNative.dll is not built. Run tools/build_hostbrain.ps1 first." }
    $native = Join-Path $hostBrain "native"
    New-Item -ItemType Directory -Force $native | Out-Null
    Copy-Item $dll $native -Force
    Write-Host "Deployed RonCompNative.dll"
}
