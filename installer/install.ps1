# Ready or Not PvP installer: puts RE-UE4SS (unless the game already has one) and the HostBrain mod into the
# game's Binaries\Win64. Only the host needs it.
#   Install.bat [-GameDir <game folder>] [-DetectOnly]
# The game folder is found through Steam; without Steam it is asked for.
param(
    [string]$GameDir = "",
    [switch]$DetectOnly
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "find-game.ps1")
$Payload = Join-Path (Split-Path -Parent $PSScriptRoot) "game"
$OurMarkers = @(".ronpvp-ue4ss.txt", ".roncomp-install.txt") # the second one is left by the developer's tools

Write-Host "Ready or Not PvP (alpha) - установка / install" -ForegroundColor Cyan
Write-Host ""

$win64 = if ($GameDir) { Win64Of $GameDir } else { FindGame }
if (-not $win64) {
    if ($GameDir) { Fail "Игра не найдена в $GameDir" "Ready or Not was not found in $GameDir" }
    Say "Не удалось найти Ready or Not в Steam." "Could not find Ready or Not through Steam."
    $answer = Read-Host "Вставьте путь к папке игры (Steam > Ready or Not > Управление > Просмотреть локальные файлы) / game folder"
    $win64 = Win64Of $answer
    if (-not $win64) { Fail "В этой папке нет $Exe." "$Exe is not in that folder." }
}
Say "Игра: $win64" "Game: $win64"
if ($DetectOnly) { exit 0 }
if (GameRunning $win64) { Fail "Закройте игру и запустите установку снова." "Close the game and run the installer again." }

$ue4ss = Join-Path $win64 "ue4ss"
$hasUe4ss = (Test-Path (Join-Path $win64 "dwmapi.dll")) -or (Test-Path (Join-Path $ue4ss "UE4SS.dll"))
$ours = $false
foreach ($marker in $OurMarkers) { if (Test-Path (Join-Path $ue4ss $marker)) { $ours = $true } }

$copied = New-Object System.Collections.Generic.List[string]
# Copies a folder's files over another; files listed in $keep (relative paths) are not replaced.
function CopyTree($from, $to, [string[]]$keep) {
    foreach ($file in Get-ChildItem $from -Recurse -File) {
        $relative = $file.FullName.Substring($from.Length + 1)
        $target = Join-Path $to $relative
        if ($keep -contains $relative -and (Test-Path $target)) { continue }
        New-Item -ItemType Directory -Force (Split-Path -Parent $target) | Out-Null
        Copy-Item $file.FullName $target -Force
        $copied.Add($target)
    }
}

if (-not $hasUe4ss -or $ours) {
    # a fresh UE4SS, or the one this installer put there before (its settings and mod list stay)
    Copy-Item (Join-Path $Payload "dwmapi.dll") $win64 -Force
    $copied.Add((Join-Path $win64 "dwmapi.dll"))
    CopyTree (Join-Path $Payload "ue4ss") $ue4ss @("UE4SS-settings.ini", "Mods\mods.txt", "Mods\mods.json")
    if (-not $hasUe4ss) {
        @("Installed by Ready or Not PvP $(Get-Date -Format s)", "Uninstall.bat removes this UE4SS unless other mods use it.") |
            Set-Content (Join-Path $ue4ss ".ronpvp-ue4ss.txt")
    }
    Say "UE4SS установлен." "UE4SS installed."
} else {
    # another UE4SS (other mods may need it): only the mod is added
    Say "UE4SS уже стоит - оставляю его (нужна сборка 3.0.1 experimental или новее)." "UE4SS is already installed; keeping it (3.0.1 experimental or newer is needed)."
    CopyTree (Join-Path $Payload "ue4ss\Mods\HostBrain") (Join-Path $ue4ss "Mods\HostBrain") @("settings.txt")
}

$mod = Join-Path $ue4ss "Mods\HostBrain" # (with a fresh UE4SS the mod came along in its Mods tree)
# scripts gone from the package must not keep loading after an update
foreach ($stale in Get-ChildItem (Join-Path $mod "Scripts") -Filter *.lua -File) {
    if (-not (Test-Path (Join-Path $Payload "ue4ss\Mods\HostBrain\Scripts\$($stale.Name)"))) { Remove-Item $stale.FullName -Force }
}

# files from a downloaded archive carry the "from the internet" mark
foreach ($path in $copied) { Unblock-File $path -ErrorAction SilentlyContinue }

Write-Host ""
Write-Host "Готово! Запустите игру и начните любую ко-оп миссию: на экране подготовки откроется меню команд." -ForegroundColor Green
Write-Host "  Done! Start the game and any co-op mission: the team menu opens on the pre-mission screen." -ForegroundColor DarkGray
Write-Host "Друзьям устанавливать ничего не нужно. Ошибки: https://github.com/VolkovIlia/ReadyOrNot-PvP/issues"
Write-Host "  Friends need nothing. Bugs: https://github.com/VolkovIlia/ReadyOrNot-PvP/issues" -ForegroundColor DarkGray
