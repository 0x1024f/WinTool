@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
    echo uv is required. Install uv and reopen this launcher.
    pause
    exit /b 1
)
uv sync --locked
if errorlevel 1 (
    echo Failed to synchronize dependencies. See the error above.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m wintools
