@echo off
chcp 65001 >nul
cd /d "%~dp0"

where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo ffmpeg nerastas - diegiama...
    winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
    echo Po ffmpeg idiegimo uzdarykite si langa ir paleiskite start.bat is naujo.
    pause
    exit /b
)

if not exist ".venv\Scripts\python.exe" (
    echo Kuriama virtuali aplinka...
    py -3.12 -m venv .venv 2>nul || python -m venv .venv
    if errorlevel 1 (
        echo Nepavyko sukurti aplinkos. Idiekite Python 3.12.
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r src\requirements.txt
equirements.txt
    if errorlevel 1 (
        echo Nepavyko idiegti paketu.
        rmdir /s /q .venv
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" src\app.py
pause
