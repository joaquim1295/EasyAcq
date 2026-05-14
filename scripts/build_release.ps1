# Build EasyAcq (PyInstaller onedir). Optional: Inno Setup installer.
# Usage (from repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build_release.ps1 -Installer
#
# Requer Python 3.11 ou 3.12 na venv: empacota NumPy 1.26 (compativel com Windows 10 e CPUs sem x86-64-v2).
param(
    [switch]$Installer
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$pyExe = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $pyExe)) {
    $pyExe = "python"
}

$pyVer = & $pyExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$parts = $pyVer.Split(".")
$pyMajor = [int]$parts[0]
$pyMinor = [int]$parts[1]
if ($pyMajor -ne 3 -or $pyMinor -lt 11 -or $pyMinor -gt 12) {
    Write-Error @"
Python $pyVer nao e suportado para gerar EasyAcq com compatibilidade Windows 10 / hardware antigo.
Use uma venv com Python 3.11 ou 3.12 (instale de https://www.python.org/downloads/ ),
depois: py -3.12 -m venv .venv  e  .venv\Scripts\pip install -r requirements.txt -r requirements-build.txt
(Nao use requirements-py313.txt para gerar o executavel.)
"@
}

Write-Host "Installing dependencies..." -ForegroundColor Cyan
& $pyExe -m pip install -r requirements.txt -r requirements-build.txt
Write-Host "Forcing NumPy 1.26 + matplotlib 3.8 (evita NumPy 2.x no pacote)..." -ForegroundColor Cyan
& $pyExe -m pip install --force-reinstall --no-cache-dir "numpy==1.26.4" "matplotlib==3.8.4"
& $pyExe -c "import numpy as np; v=np.__version__; assert v.startswith('1.26'), ('NumPy deve ser 1.26.x, obtido: ' + v); print('NumPy OK:', v)"

Write-Host "Cleaning previous dist/build..." -ForegroundColor Cyan
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist\EasyAcq) { Remove-Item -Recurse -Force dist\EasyAcq }

$iconPath = Join-Path $root "assets\easyacq.ico"
if (-not (Test-Path $iconPath)) {
    Write-Error "assets\easyacq.ico not found (coloque o icone nessa pasta)."
}

Write-Host "Running PyInstaller (EasyAcq.spec)..." -ForegroundColor Cyan
& $pyExe -m PyInstaller --noconfirm EasyAcq.spec

$exe = Join-Path $root "dist\EasyAcq\EasyAcq.exe"
if (-not (Test-Path $exe)) {
    Write-Error "Expected output missing: $exe"
}
Write-Host "OK: $exe" -ForegroundColor Green

$lnkPath = Join-Path $root "EasyAcq.lnk"
$workDir = Join-Path $root "dist\EasyAcq"
try {
    $wsh = New-Object -ComObject WScript.Shell
    $sc = $wsh.CreateShortcut($lnkPath)
    $sc.TargetPath = $exe
    $sc.WorkingDirectory = $workDir
    if (Test-Path $iconPath) {
        $sc.IconLocation = "$iconPath,0"
    }
    $sc.Description = "EasyAcq (build local PyInstaller)"
    $sc.Save()
    Write-Host "Atalho criado: $lnkPath" -ForegroundColor Green
} catch {
    Write-Host "Nao foi possivel criar EasyAcq.lnk: $_" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "AVISO: Nao execute o programa a partir de build\ (pasta intermedia)." -ForegroundColor Yellow
Write-Host "       Arranque sempre: dist\EasyAcq\EasyAcq.exe (com a pasta dist\EasyAcq completa)." -ForegroundColor Yellow
Write-Host "       Ou use o atalho EasyAcq.lnk na raiz do projeto." -ForegroundColor Yellow
Write-Host ""

if ($Installer) {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )
    $iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) {
        Write-Error "Inno Setup 6 not found (ISCC.exe). Install from https://jrsoftware.org/isdl.php"
    }
    New-Item -ItemType Directory -Force (Join-Path $root "release") | Out-Null
    Write-Host "Compiling installer with: $iscc" -ForegroundColor Cyan
    & $iscc (Join-Path $root "packaging\EasyAcq.iss")
    Write-Host "Installer output under release\" -ForegroundColor Green
}
