param(
    [string]$PythonExecutable = "D:\Python313\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([System.IO.Path]::GetPathRoot($ProjectRoot) -ne "E:\") {
    throw "Safety check failed: the project must be stored on drive E. Current path: $ProjectRoot"
}

if (-not (Test-Path -LiteralPath $PythonExecutable -PathType Leaf)) {
    $PythonCommand = Get-Command python -ErrorAction Stop
    $PythonExecutable = $PythonCommand.Source
}

$env:TEMP = Join-Path $ProjectRoot ".tmp"
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $ProjectRoot ".cache\pip"
$env:PYTHONPYCACHEPREFIX = Join-Path $ProjectRoot ".cache\pycache"

New-Item -ItemType Directory -Force -Path $env:TEMP, $env:PIP_CACHE_DIR, $env:PYTHONPYCACHEPREFIX | Out-Null

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    Write-Host "Creating the virtual environment on drive E..."
    & $PythonExecutable -m venv (Join-Path $ProjectRoot ".venv")
}

Write-Host "Installing dependencies into the E-drive virtual environment..."
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")

Write-Host ""
Write-Host "TripMate setup is complete."
Write-Host "Virtual environment: $(Join-Path $ProjectRoot '.venv')"
Write-Host "pip cache: $env:PIP_CACHE_DIR"
Write-Host "Next: .\scripts\run_e_drive.ps1 -SeedDemo"
