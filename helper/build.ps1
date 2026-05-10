.\venv\Scripts\Activate.ps1

Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue

pyinstaller --onefile --name ForgePlayHelper main.py