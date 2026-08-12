param(
    [string]$PythonExecutable = "D:\Python313\python.exe"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([System.IO.Path]::GetPathRoot($ProjectRoot) -ne "E:\") {
    throw "安全检查失败：项目必须位于 E 盘，当前目录为 $ProjectRoot"
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
    Write-Host "正在 E 盘创建虚拟环境..."
    & $PythonExecutable -m venv (Join-Path $ProjectRoot ".venv")
}

Write-Host "正在把依赖安装到 E 盘虚拟环境..."
& $VenvPython -m pip install -r (Join-Path $ProjectRoot "requirements.txt")

Write-Host ""
Write-Host "TripMate 环境准备完成。"
Write-Host "虚拟环境：$(Join-Path $ProjectRoot '.venv')"
Write-Host "pip 缓存：$env:PIP_CACHE_DIR"
Write-Host "下一步：.\scripts\run_e_drive.ps1 -SeedDemo"

