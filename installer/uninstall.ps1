# Ready or Not PvP uninstaller: removes the HostBrain mod, and the UE4SS that install.ps1 put there unless
# other mods now use it.
#   Uninstall.bat [-GameDir <game folder>]
param([string]$GameDir = "")

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "find-game.ps1")

Write-Host "Ready or Not PvP - удаление / uninstall" -ForegroundColor Cyan
$win64 = if ($GameDir) { Win64Of $GameDir } else { FindGame }
if (-not $win64) {
    $win64 = Win64Of (Read-Host "Путь к папке игры / game folder")
    if (-not $win64) { Fail "Игра не найдена." "Ready or Not was not found." }
}
Say "Игра: $win64" "Game: $win64"
if (GameRunning $win64) { Fail "Закройте игру и запустите удаление снова." "Close the game and run the uninstaller again." }

$ue4ss = Join-Path $win64 "ue4ss"
$mod = Join-Path $ue4ss "Mods\HostBrain"
if (Test-Path $mod) {
    Remove-Item $mod -Recurse -Force
    Say "Мод удалён." "The mod is removed."
} else {
    Say "Мод не найден." "The mod is not installed."
}

# UE4SS goes only if this installer put it there and no other mod was added since
$marker = Join-Path $ue4ss ".ronpvp-ue4ss.txt"
if (Test-Path $marker) {
    $bundled = @("BPML_GenericFunctions", "BPModLoaderMod", "CheatManagerEnablerMod", "ConsoleCommandsMod",
        "ConsoleEnablerMod", "Keybinds", "LineTraceMod", "SplitScreenMod", "shared")
    $others = Get-ChildItem (Join-Path $ue4ss "Mods") -Directory | Where-Object { $bundled -notcontains $_.Name }
    if ($others) {
        Say "UE4SS оставлен: им пользуются другие моды ($($others.Name -join ', '))." "UE4SS is kept: other mods use it."
    } else {
        Remove-Item (Join-Path $win64 "dwmapi.dll") -Force -ErrorAction SilentlyContinue
        Remove-Item $ue4ss -Recurse -Force
        Say "UE4SS удалён." "UE4SS is removed."
    }
}
Write-Host "Готово. / Done." -ForegroundColor Green
