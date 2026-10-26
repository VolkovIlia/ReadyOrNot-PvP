# Builds HostBrain (rules core, its tests and the RonCompNative guard DLL) with MSVC and runs the tests.
#   powershell -File tools/build_hostbrain.ps1 [-Config Release|Debug]
param(
    [ValidateSet("Release", "Debug")][string]$Config = "Release"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$build = Join-Path $root "build\hostbrain"

$vswhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
$vs = & $vswhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vs) { throw "Visual Studio with the C++ toolset was not found." }
$vcvars = Join-Path $vs "VC\Auxiliary\Build\vcvars64.bat"

# Configure, build and test inside one cmd so the vcvars environment applies to all steps.
$steps = @(
    "call `"$vcvars`" >nul",
    "cmake -S `"$root\HostBrain`" -B `"$build`" -G Ninja -DCMAKE_BUILD_TYPE=$Config",
    "cmake --build `"$build`"",
    "ctest --test-dir `"$build`" --output-on-failure"
) -join " && "
& cmd /c $steps
if ($LASTEXITCODE -ne 0) { throw "HostBrain build or tests failed ($LASTEXITCODE)." }
Write-Host "Built $build\RonCompNative.dll"
