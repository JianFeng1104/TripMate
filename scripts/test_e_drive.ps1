$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([System.IO.Path]::GetPathRoot($ProjectRoot) -ne "E:\") {
    throw "Safety check failed: the project must be stored on drive E. Current path: $ProjectRoot"
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    throw "The E-drive virtual environment was not found. Run .\scripts\setup_e_drive.ps1 first."
}

$env:TEMP = Join-Path $ProjectRoot ".tmp"
$env:TMP = $env:TEMP
$env:PYTHONPYCACHEPREFIX = Join-Path $ProjectRoot ".cache\pycache"
New-Item -ItemType Directory -Force -Path $env:TEMP, $env:PYTHONPYCACHEPREFIX | Out-Null

Push-Location $ProjectRoot
try {
    & $VenvPython -m pytest -q
}
finally {
    Pop-Location
}
