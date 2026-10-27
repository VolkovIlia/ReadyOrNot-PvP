# Builds the release archive dist/RoN-PvP-<version>.zip: the one-click installer, RE-UE4SS and the HostBrain mod
# (no RonCompProbe). Needs build/hostbrain/RonCompNative.dll (tools/build_hostbrain.ps1) and a UE4SS build in
# tools/bin/ue4ss/<version>/extracted.
#   powershell -File tools/package_release.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$mod = Join-Path $root "HostBrain\ue4ss-mods\HostBrain"

$version = [regex]::Match((Get-Content (Join-Path $mod "Scripts\main.lua") -Raw), 'local Version = "([^"]+)"').Groups[1].Value
if (-not $version) { throw "No Version in main.lua" }
$dll = Join-Path $root "build\hostbrain\RonCompNative.dll"
if (-not (Test-Path $dll)) { throw "RonCompNative.dll is not built. Run tools/build_hostbrain.ps1 first." }
$ue4ssBuild = Get-ChildItem (Join-Path $root "tools\bin\ue4ss") -Directory | Sort-Object Name | Select-Object -Last 1
$ue4ss = Join-Path $ue4ssBuild.FullName "extracted"
if (-not (Test-Path (Join-Path $ue4ss "dwmapi.dll"))) { throw "No extracted UE4SS build in $ue4ss" }

$name = "RoN-PvP-$version"
$dist = Join-Path $root "dist"
$stage = Join-Path $dist $name
if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Force $stage | Out-Null

# Text files go out with Windows line endings; the PowerShell scripts with a UTF-8 BOM, which Windows
# PowerShell 5.1 needs to read their Cyrillic text.
function WriteText($from, $to, [switch]$Bom) {
    $text = (Get-Content $from -Raw -Encoding UTF8) -replace "`r?`n", "`r`n"
    New-Item -ItemType Directory -Force (Split-Path -Parent $to) | Out-Null
    [System.IO.File]::WriteAllText($to, $text, (New-Object System.Text.UTF8Encoding($Bom.IsPresent)))
}
$installer = Join-Path $root "installer"
WriteText (Join-Path $installer "Install.bat") (Join-Path $stage "Install.bat")
WriteText (Join-Path $installer "Uninstall.bat") (Join-Path $stage "Uninstall.bat")
WriteText (Join-Path $installer "README.txt") (Join-Path $stage "README.txt") -Bom
WriteText (Join-Path $root "LICENSE") (Join-Path $stage "LICENSE.txt")
foreach ($script in "install.ps1", "uninstall.ps1", "find-game.ps1") {
    WriteText (Join-Path $installer $script) (Join-Path $stage "installer\$script") -Bom
}

$game = Join-Path $stage "game"
Copy-Item $ue4ss $game -Recurse
$target = Join-Path $game "ue4ss\Mods\HostBrain"
Copy-Item (Join-Path $mod "Scripts") (Join-Path $target "Scripts") -Recurse
Copy-Item (Join-Path $mod "enabled.txt") $target
New-Item -ItemType Directory -Force (Join-Path $target "native") | Out-Null
Copy-Item $dll (Join-Path $target "native")

$zip = Join-Path $dist "$name.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path $stage -DestinationPath $zip
Write-Host "Packed $zip (UE4SS $($ue4ssBuild.Name), $([math]::Round((Get-Item $zip).Length / 1MB, 1)) MB)"
