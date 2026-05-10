# ForgePlay Helper Production Hardening

## Runtime Contract

- Helper listens on `http://127.0.0.1:8000`.
- Health endpoint is `GET /` and returns `{"status":"ok"}`.
- Logs always write to `%LOCALAPPDATA%\ForgePlay\forgeplay.log`.
- Cache files live under `%LOCALAPPDATA%\ForgePlay\cache`.
- A Windows mutex prevents duplicate helper instances.
- A Windows named shutdown event lets `ForgePlayHelper.exe --shutdown` stop the running tray process cleanly.

## Local Build

Run from `D:\forgeplay-main\helper`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build.ps1
```

The production PyInstaller target is:

```powershell
pyinstaller --noconfirm --clean --noupx --onefile --windowed --name ForgePlayHelper --collect-all yt_dlp --hidden-import pystray._win32 --hidden-import uvicorn.logging --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto --hidden-import uvicorn.protocols.http.h11_impl --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on main.py
```

## Installer Build

After the helper exe exists at `helper\dist\ForgePlayHelper.exe`, compile:

```powershell
& "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" "/DMyAppVersion=1.0.0" "installer\installer.iss"
```

The installer output is `installer\ForgePlaySetup.exe`.

## Release Flow

The GitHub Actions release workflow:

- Resolves the version from tags like `v1.2.3`.
- Builds the windowed onefile helper.
- Installs Inno Setup.
- Builds `ForgePlaySetup.exe`.
- Uploads both the raw helper exe and installer.
- Publishes both files to tagged GitHub Releases.

## Remaining Production Risks

- Long downloads still keep the extension service worker waiting for `/download`; a job-based API would be more resilient.
- The installer and exe are not code-signed, so SmartScreen trust will be weak for first-time users.
- There is no auto-update channel for the helper yet.
- Extension/helper pairing has no per-install token. The current URL whitelist and loopback-only bind reduce exposure, but a local token would be stronger.
- The Chrome Web Store URL is hardcoded in the installer and should be treated as release metadata.

## Recommended Next Pass

1. Replace synchronous `/download` with `POST /downloads`, `GET /downloads/{id}`, and a player page that waits for readiness.
2. Add Authenticode signing for both `ForgePlayHelper.exe` and `ForgePlaySetup.exe`.
3. Add a generated `version.json` and expose `GET /version`.
4. Add a small diagnostics command that opens the log folder and copies health status.
5. Add a clean extension onboarding page that checks helper health and shows one recovery action if localhost is unavailable.
