@echo off
chcp 65001 >nul
REM RSI-AB Build Script

echo ================================================
echo   RSI-AB Build Script
echo   MieMie Kick! V3.0.0
echo ================================================
echo.

REM Check PyInstaller
echo [0/3] Checking PyInstaller...
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo       PyInstaller not found! Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo       ERROR: Failed to install PyInstaller!
        pause
        exit /b 1
    )
)
echo       OK.
echo.

REM Clean previous builds
echo [1/3] Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "RSI_MIEKCIK_BUY.spec" del /q "RSI_MIEKCIK_BUY.spec"
echo       Done.
echo.

echo [2/3] Building with PyInstaller...
echo.

python -m PyInstaller --onefile --windowed --icon=icon.ico --name "RSI_MIEKCIK_BUY" RSI_MIEKCIK_BUY.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check errors above.
    pause
    exit /b 1
)

REM Copy images and guide to dist
echo.
echo [3/3] Copying resources...
if not exist "dist\images" mkdir "dist\images"
copy /y "images\*.png" "dist\images\" >nul
copy /y "icon.ico" "dist\" >nul
copy /y "RSI_MIEBUY_Guide.txt" "dist\" >nul
echo       Done.
echo.

if exist "dist\RSI_MIEKCIK_BUY.exe" (
    echo ================================================
    echo   Build Complete!
    echo   Output: dist\RSI_MIEKCIK_BUY.exe
    echo   Images: dist\images\
    echo ================================================
) else (
    echo [ERROR] EXE not found!
    pause
    exit /b 1
)

echo.
pause
