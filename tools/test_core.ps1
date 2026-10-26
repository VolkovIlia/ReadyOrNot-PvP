# Builds and runs the HostBrain rules-core unit tests.
# Uses MSVC (cl) when available, otherwise g++. The core is plain C++17 with no game dependencies.
#   powershell -File tools/test_core.ps1 [-Filter <substring>]
param(
    [string]$Filter = ""
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$outDir = Join-Path $root "build\core-tests"
New-Item -ItemType Directory -Force $outDir | Out-Null

$sources = @(
    Get-ChildItem (Join-Path $root "HostBrain\src\core\*.cpp")
    Get-ChildItem (Join-Path $root "HostBrain\tests\*.cpp")
) | ForEach-Object { $_.FullName }

$exe = Join-Path $outDir "core_tests.exe"

if (Get-Command cl -ErrorAction SilentlyContinue) {
    & cl /nologo /std:c++17 /EHsc /W4 /WX /permissive- /Fe:$exe /Fo:"$outDir\\" @sources
} elseif (Get-Command g++ -ErrorAction SilentlyContinue) {
    & g++ -std=c++17 -O1 -Wall -Wextra -Werror -pedantic -o $exe @sources
} else {
    throw "No C++ compiler found (need MSVC cl or g++)."
}
if ($LASTEXITCODE -ne 0) { throw "Build failed." }

$dataDir = Join-Path $root "data"
if ($Filter) { & $exe $dataDir $Filter } else { & $exe $dataDir }
exit $LASTEXITCODE
