# Installs a downloaded RE-UE4SS build into the Ready or Not game folder.
#   powershell -File tools/install_ue4ss.ps1 [-Dev] [-GameDir <path>] [-Build <tools/bin/ue4ss/...>]
# -Dev turns on the UE4SS console windows and Lua hot reload (development machines only).
# Only the host needs UE4SS; clients play with the shared pak alone.
param(
    [switch]$Dev,
    [string]$GameDir = "C:\Program Files (x86)\Steam\steamapps\common\Ready Or Not",
    [string]$Build = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not $Build) {
    $Build = Get-ChildItem (Join-Path $root "tools\bin\ue4ss") -Directory | Sort-Object Name | Select-Object -Last 1 -ExpandProperty FullName
}
$source = Join-Path $Build "extracted"
if (-not (Test-Path (Join-Path $source "dwmapi.dll"))) { throw "No extracted UE4SS build at $source" }

$win64 = Join-Path $GameDir "ReadyOrNot\Binaries\Win64"
if (-not (Test-Path (Join-Path $win64 "ReadyOrNotSteam-Win64-Shipping.exe"))) { throw "Game executable not found in $win64" }
if (Get-Process -Name "ReadyOrNotSteam-Win64-Shipping" -ErrorAction SilentlyContinue) { throw "Close the game before installing UE4SS." }

$proxy = Join-Path $win64 "dwmapi.dll"
$marker = Join-Path $win64 "ue4ss\.roncomp-install.txt"
if ((Test-Path $proxy) -and -not (Test-Path $marker)) {
    throw "A dwmapi.dll that this script did not install already exists in $win64. Remove it manually if it is another UE4SS."
}

Copy-Item (Join-Path $source "dwmapi.dll") $win64 -Force
Copy-Item (Join-Path $source "ue4ss") $win64 -Recurse -Force

$ini = Join-Path $win64 "ue4ss\UE4SS-settings.ini"
$values = @{}
if ($Dev) {
    $values = @{
        "ConsoleEnabled" = "1"
        "GuiConsoleEnabled" = "1"
        "GuiConsoleVisible" = "1"
        "GraphicsAPI" = "dx11"
        "EnableHotReloadSystem" = "1"
    }
}
$text = Get-Content $ini -Raw
foreach ($key in $values.Keys) {
    $text = [regex]::Replace($text, "(?m)^(\s*$key\s*=).*$", "`${1} $($values[$key])")
}
Set-Content -Path $ini -Value $text -NoNewline

@(
    "Installed by tools/install_ue4ss.ps1 on $(Get-Date -Format s)"
    "Build: $(Split-Path -Leaf $Build)"
    "Dev: $Dev"
) | Set-Content $marker

Write-Host "UE4SS installed into $win64 (build $(Split-Path -Leaf $Build), dev=$Dev)."
