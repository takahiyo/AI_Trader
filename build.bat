@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo AI_Trader Build Script
echo ==========================================

REM Check PyInstaller
where pyinstaller >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller not found.
    exit /b 1
)

echo [INFO] Starting build...
set START_TIME=%TIME%

REM Run PyInstaller
REM --onefile: Bundle into one executable
REM --noconfirm: Skip overwrite confirmation
REM --clean: Clean cache
REM --name: Output name
pyinstaller --noconfirm --onefile --console --name "AI_Trader" main.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build failed.
    exit /b 1
)

set END_TIME=%TIME%
echo [INFO] Build completed.
echo Start: %START_TIME%
echo End: %END_TIME%
echo Output: dist\AI_Trader.exe

endlocal
