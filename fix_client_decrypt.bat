@echo off
REM Fix "Failed to decrypt payload" - restart backend and clear client cache

echo Stopping backend on port 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /PID %%a /F 2>nul
    echo Killed PID %%a
)

echo.
echo Clearing client state...
if exist "dist\.runtime_data" (
    rmdir /s /q "dist\.runtime_data"
    echo Removed dist\.runtime_data
)
if exist ".runtime_data" (
    rmdir /s /q ".runtime_data"
    echo Removed .runtime_data
)

echo.
echo Starting backend...
start "Backend" cmd /k "cd /d %~dp0 && python -m uvicorn backend.src.main:app --host 127.0.0.1 --port 8000"

echo.
echo Done. Run dist\wishlist_bootstrap.exe and enter your license key again.
