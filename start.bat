@echo off
title AMRO — Start All Services
color 0A

echo.
echo  ======================================
echo    AMRO AI Trading Intelligence
echo  ======================================
echo.

REM Check PocketBase
if not exist "pocketbase.exe" (
    echo  [!] ไม่พบ pocketbase.exe
    echo  [!] รัน: python scripts/setup.py ก่อน
    pause
    exit /b 1
)

REM Check .env
if not exist ".env" (
    echo  [!] ไม่พบ .env
    echo  [!] รัน: python scripts/setup.py ก่อน
    pause
    exit /b 1
)

echo  [1] Starting PocketBase on port 8090...
start "PocketBase" cmd /k "cd /d "%~dp0" && pocketbase.exe serve --http=127.0.0.1:8090"

echo  [2] Waiting 3 seconds...
timeout /t 3 /nobreak > nul

echo  [3] Starting AMRO FastAPI on port 8000...
start "AMRO API" cmd /k "cd /d "%~dp0" && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo  [4] Waiting 4 seconds...
timeout /t 4 /nobreak > nul

echo  [5] Opening browser...
start "" "http://localhost:8000"

echo.
echo  ======================================
echo    Services running:
echo    API:        http://localhost:8000
echo    API Docs:   http://localhost:8000/docs
echo    PocketBase: http://localhost:8090/_/
echo  ======================================
echo.
echo  กด Ctrl+C ใน window ใดก็ได้เพื่อหยุด service นั้น
pause
