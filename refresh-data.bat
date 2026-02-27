@echo off
REM Refresh all cached data: PDFs, cost analysis, financial analysis
REM This script triggers the Python refresh workflow

setlocal enabledelayedexpansion

REM Get the project root directory
for %%A in ("%~dp0..") do set "PROJECT_ROOT=%%~fA"

REM Check if API is running
echo Checking if API is running...
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:8000/health' -TimeoutSec 5 -ErrorAction Stop; Write-Host 'API is healthy' } catch { Write-Host 'API is not running'; exit 1 }" >nul 2>&1

if errorlevel 1 (
    echo.
    echo ❌ API server is not running!
    echo Please start the API server first by running:
    echo    python scripts\run_api.py
    echo.
    pause
    exit /b 1
)

echo ✅ API is running
echo.
echo 🚀 Starting data refresh workflow...
echo.

REM Run the Python refresh script
cd /d "%PROJECT_ROOT%"
python scripts\refresh_data.py

if errorlevel 1 (
    echo.
    echo ❌ Refresh failed with errors
    pause
    exit /b 1
) else (
    echo.
    echo ✅ Refresh completed successfully
    pause
    exit /b 0
)
