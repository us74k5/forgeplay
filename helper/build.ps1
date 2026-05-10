$ErrorActionPreference = "Stop"

$HelperDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $HelperDir

$Python = Join-Path $HelperDir "venv\Scripts\python.exe"
$PyInstallerVersion = "6.20.0"

if (-not (Test-Path -LiteralPath $Python)) {
    python -m venv (Join-Path $HelperDir "venv")
}

& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt "pyinstaller==$PyInstallerVersion"

Remove-Item -LiteralPath (Join-Path $HelperDir "build") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $HelperDir "dist") -Recurse -Force -ErrorAction SilentlyContinue

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --noupx `
    --onefile `
    --windowed `
    --name ForgePlayHelper `
    --collect-all yt_dlp `
    --hidden-import pystray._win32 `
    --hidden-import uvicorn.logging `
    --hidden-import uvicorn.loops.auto `
    --hidden-import uvicorn.protocols.http.auto `
    --hidden-import uvicorn.protocols.http.h11_impl `
    --hidden-import uvicorn.protocols.websockets.auto `
    --hidden-import uvicorn.lifespan.on `
    main.py
