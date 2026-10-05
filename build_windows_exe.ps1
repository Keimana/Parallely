$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPath = "D:\ParallelyBuild\venv"
$buildRoot = "D:\ParallelyBuild"

if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment..."
    python -m venv $venvPath
}

& "$venvPath\Scripts\python.exe" -m pip install --upgrade pip
& "$venvPath\Scripts\python.exe" -m pip install -r "$projectRoot\requirements.txt"
& "$venvPath\Scripts\python.exe" -m pip install pyinstaller

$distPath = Join-Path $buildRoot "dist"
$workPath = Join-Path $buildRoot "build"
$specPath = Join-Path $buildRoot "spec"

New-Item -ItemType Directory -Force -Path $distPath | Out-Null
New-Item -ItemType Directory -Force -Path $workPath | Out-Null
New-Item -ItemType Directory -Force -Path $specPath | Out-Null

& "$venvPath\Scripts\pyinstaller.exe" `
    --noconfirm `
    --clean `
    --distpath $distPath `
    --workpath $workPath `
    --specpath $specPath `
    --windowed `
    --name "Parallely" `
    --add-data "$projectRoot\Assets;Assets" `
    "$projectRoot\main.py"

Write-Host "Executable created at: $distPath\Parallely.exe"
