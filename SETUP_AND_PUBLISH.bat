@echo off
setlocal
cd /d "%~dp0"
echo VA AILOCK AI Studio - GitHub Pages setup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0publish_github.ps1"
if errorlevel 1 (
    echo.
    echo Setup did not finish. Read the error above. You can rerun this file safely.
)
echo.
pause
