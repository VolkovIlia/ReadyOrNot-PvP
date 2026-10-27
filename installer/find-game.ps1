# Shared by install.ps1 and uninstall.ps1: messages and finding the game's Binaries\Win64 through Steam
# (registry + libraryfolders.vdf + the app manifest).

$AppId = "1144200"
$Exe = "ReadyOrNotSteam-Win64-Shipping.exe"

function Say($ru, $en) { Write-Host $ru; if ($en) { Write-Host "  $en" -ForegroundColor DarkGray } }
function Fail($ru, $en) { Write-Host ""; Write-Host $ru -ForegroundColor Red; if ($en) { Write-Host "  $en" -ForegroundColor DarkGray }; exit 1 }

# The game's Binaries\Win64 from the game folder, ReadyOrNot or Win64 itself; $null when the exe is not there.
function Win64Of($dir) {
    if (-not $dir) { return $null }
    $dir = $dir.Trim().Trim('"')
    foreach ($candidate in @($dir, (Join-Path $dir "ReadyOrNot\Binaries\Win64"), (Join-Path $dir "Binaries\Win64"))) {
        if (Test-Path (Join-Path $candidate $Exe)) { return (Resolve-Path $candidate).Path }
    }
    return $null
}

function SteamLibraries {
    $roots = @()
    foreach ($key in "HKCU:\Software\Valve\Steam", "HKLM:\SOFTWARE\WOW6432Node\Valve\Steam", "HKLM:\SOFTWARE\Valve\Steam") {
        try {
            $item = Get-ItemProperty $key -ErrorAction Stop
            foreach ($name in "SteamPath", "InstallPath") { if ($item.$name) { $roots += ($item.$name -replace "/", "\") } }
        } catch {}
    }
    $libraries = @()
    foreach ($root in ($roots | Select-Object -Unique)) {
        $libraries += $root
        $vdf = Join-Path $root "steamapps\libraryfolders.vdf"
        if (Test-Path $vdf) {
            foreach ($match in [regex]::Matches((Get-Content $vdf -Raw), '"path"\s+"([^"]+)"')) {
                $libraries += ($match.Groups[1].Value -replace "\\\\", "\")
            }
        }
    }
    return $libraries | Select-Object -Unique
}

function FindGame {
    foreach ($library in SteamLibraries) {
        $installDir = "Ready Or Not"
        $manifest = Join-Path $library "steamapps\appmanifest_$AppId.acf"
        if (Test-Path $manifest) {
            $m = [regex]::Match((Get-Content $manifest -Raw), '"installdir"\s+"([^"]+)"')
            if ($m.Success) { $installDir = $m.Groups[1].Value }
        }
        $win64 = Win64Of (Join-Path $library "steamapps\common\$installDir")
        if ($win64) { return $win64 }
    }
    return $null
}

# True while this copy of the game runs (another copy elsewhere does not matter).
function GameRunning($win64) {
    $running = Get-Process -Name "ReadyOrNotSteam-Win64-Shipping" -ErrorAction SilentlyContinue |
        Where-Object { $_.Path -and $_.Path.StartsWith($win64, [StringComparison]::OrdinalIgnoreCase) }
    return [bool]$running
}
