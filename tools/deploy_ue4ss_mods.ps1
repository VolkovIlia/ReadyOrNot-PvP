# Copies this project's UE4SS mods (HostBrain/ue4ss-mods/*) into the game's ue4ss/Mods folder.
#   powershell -File tools/deploy_ue4ss_mods.ps1 [-GameDir <path>] [-Only <ModName>]
# Works while the game runs: files are copied one by one (scripts take effect after RestartMod), and the
# loaded RonCompNative.dll, which the game keeps locked, is only replaced when it changed.
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
    foreach ($file in Get-ChildItem $mod.FullName -Recurse -File) {
        $target = Join-Path $destination $file.FullName.Substring($mod.FullName.Length + 1)
        New-Item -ItemType Directory -Force (Split-Path -Parent $target) | Out-Null
        Copy-Item $file.FullName $target -Force
    }
    # scripts removed from the project must not keep loading in the game
    $scripts = Join-Path $destination "Scripts"
    if (Test-Path $scripts) {
        foreach ($stale in Get-ChildItem $scripts -Filter *.lua -File) {
            if (-not (Test-Path (Join-Path $mod.FullName "Scripts\$($stale.Name)"))) { Remove-Item $stale.FullName -Force }
        }
    }
    Write-Host "Deployed $($mod.Name)"
}

# HostBrain loads its native guards from Mods/HostBrain/native (built by tools/build_hostbrain.ps1).
$hostBrain = Join-Path $modsTarget "HostBrain"
if (Test-Path $hostBrain) {
    $dll = Join-Path $root "build\hostbrain\RonCompNative.dll"
    if (-not (Test-Path $dll)) { throw "RonCompNative.dll is not built. Run tools/build_hostbrain.ps1 first." }
    $native = Join-Path $hostBrain "native"
    New-Item -ItemType Directory -Force $native | Out-Null
    $deployed = Join-Path $native "RonCompNative.dll"
    if ((Test-Path $deployed) -and (Get-FileHash $deployed).Hash -eq (Get-FileHash $dll).Hash) {
        Write-Host "RonCompNative.dll is up to date"
    } else {
        try {
            Copy-Item $dll $native -Force
            Write-Host "Deployed RonCompNative.dll"
        } catch {
            Write-Warning "RonCompNative.dll is in use by the running game; restart the game to load the new one"
        }
    }
}
