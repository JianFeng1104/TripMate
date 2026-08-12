param(
    [switch]$SeedDemo,
    [int]$Port = 5000
)

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
$env:PIP_CACHE_DIR = Join-Path $ProjectRoot ".cache\pip"
$env:PYTHONPYCACHEPREFIX = Join-Path $ProjectRoot ".cache\pycache"
if (-not $env:TRIPMATE_SECRET_KEY) {
    $env:TRIPMATE_SECRET_KEY = "tripmate-e-drive-local-development"
}

New-Item -ItemType Directory -Force -Path $env:TEMP, $env:PIP_CACHE_DIR, $env:PYTHONPYCACHEPREFIX | Out-Null
Push-Location $ProjectRoot
try {
    if ($SeedDemo) {
        & $VenvPython -m flask --app run:app seed-demo
    }
    Write-Host "TripMate 正在启动：http://127.0.0.1:$Port"
    & $VenvPython -m flask --app run:app run --host 127.0.0.1 --port $Port --debug
}
finally {
    Pop-Location
}

