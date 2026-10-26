# Decompiles selected functions of the game executable (or another module, -Binary) with headless
# Ghidra, without whole-program auto-analysis (which takes hours for the 150 MB shipping exe).
#   powershell -File tools/ghidra_decompile.ps1 -Out <dir> [-Depth 1] 0x1449a06e0 0x1449a0e40 dis:0x142a52df0:12
#   powershell -File tools/ghidra_decompile.ps1 -Out <dir> -Binary <...>\ue4ss\UE4SS.dll -Project UE4SS 0x1802c3b80
# Addresses are static VAs (game exe image base 0x140000000, UE4SS.dll 0x180000000). Entry points come
# from .pdata, UFunction exec pointers in the JMAP dump, or vtable slots (see docs/re-findings.md).
# Ghidra's batch launcher breaks on spaces and parentheses in paths, so the binary, project and script
# are kept under $WorkDir; every -Project keeps its own Ghidra project.
[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Mandatory = $true)][string]$Out,
    [int]$Depth = 0,
    [string]$GhidraDir = "C:\Users\iliav\Tools\ghidra_12.1.4_PUBLIC",
    [string]$JavaHome = "C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot",
    [string]$WorkDir = "C:\Users\iliav\Tools\ron_re",
    [string]$Binary = "C:\Program Files (x86)\Steam\steamapps\common\Ready Or Not\ReadyOrNot\Binaries\Win64\ReadyOrNotSteam-Win64-Shipping.exe",
    [string]$Project = "RoN",
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Targets
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
foreach ($dir in "bin", "scripts", "proj") { New-Item -ItemType Directory -Force (Join-Path $WorkDir $dir) | Out-Null }
New-Item -ItemType Directory -Force $Out | Out-Null
if ($Out -match "[ ()]") { throw "-Out must not contain spaces or parentheses (Ghidra's batch launcher)." }

$exeName = $Project + [IO.Path]::GetExtension($Binary)
$exe = Join-Path $WorkDir "bin\$exeName"
$binaryHash = (Get-FileHash $Binary).Hash
if (-not (Test-Path $exe) -or (Get-FileHash $exe).Hash -ne $binaryHash) {
    Copy-Item $Binary $exe -Force
    Remove-Item (Join-Path $WorkDir "proj\$Project.*") -Recurse -Force -ErrorAction SilentlyContinue
}
Copy-Item (Join-Path $root "re\ghidra_scripts\DecompileTargets.java") (Join-Path $WorkDir "scripts") -Force

$env:JAVA_HOME = $JavaHome
$env:PATH = "$JavaHome\bin;$env:PATH"
if (-not $env:GHIDRA_HEADLESS_MAXMEM) { $env:GHIDRA_HEADLESS_MAXMEM = "16G" }

$headless = Join-Path $GhidraDir "support\analyzeHeadless.bat"
$projectDir = Join-Path $WorkDir "proj"
$scriptArgs = @("out", $Out, "depth", "$Depth") + $Targets
# The launcher also fails when the current directory contains spaces.
Push-Location $WorkDir
try {
    if (Test-Path (Join-Path $projectDir "$Project.gpr")) {
        & cmd /c $headless $projectDir $Project -process $exeName -noanalysis -scriptPath (Join-Path $WorkDir "scripts") -postScript DecompileTargets.java @scriptArgs
    } else {
        & cmd /c $headless $projectDir $Project -import $exe -noanalysis -scriptPath (Join-Path $WorkDir "scripts") -postScript DecompileTargets.java @scriptArgs
    }
    if ($LASTEXITCODE -ne 0) { throw "Ghidra headless failed ($LASTEXITCODE)." }
}
finally {
    Pop-Location
}

& python -I (Join-Path $root "re\annotate_strings.py") $exe $Out
