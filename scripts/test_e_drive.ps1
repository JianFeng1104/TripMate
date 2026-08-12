$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ([System.IO.Path]::GetPathRoot($ProjectRoot) -ne "E:\") {
    throw "安全检查失败：项目必须位于 E 盘，当前目录为 $ProjectRoot"
}

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    throw "未找到 E 盘虚拟环境。请先运行 .\scripts\setup_e_drive.ps1"
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

