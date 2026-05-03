@echo off
chcp 65001 >nul
REM RSI_MIEKCIK_BUY Protected Build Script (Cython + PyInstaller)

echo ================================================
echo   RSI_MIEKCIK_BUY Protected Build
echo   MieMie Kick! V3.0.3 (Cython Protected)
echo ================================================
echo.

REM Check Cython
echo [0/4] Checking dependencies...
python -c "import Cython" >nul 2>&1
if errorlevel 1 (
    echo       Cython not found! Installing...
    pip install cython
    if errorlevel 1 (
        echo       ERROR: Failed to install Cython!
        pause
        exit /b 1
    )
)
echo       Cython OK.

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
echo       PyInstaller OK.
echo.

REM Clean previous builds
echo [1/4] Cleaning previous builds...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "RSI_MIEKCIK_BUY.spec" del /q "RSI_MIEKCIK_BUY.spec"
del /q modules\*.pyd 2>nul
del /q modules\*.c 2>nul
echo       Done.
echo.

REM Cython compile
echo [2/4] Cython compiling core modules...
python setup_cython.py build_ext --inplace
if errorlevel 1 (
    echo.
    echo [ERROR] Cython compilation failed!
    echo         Make sure you have a C compiler installed.
    pause
    exit /b 1
)
echo       Cython compilation done.
echo.

REM Move source .py to .bak for compiled modules
echo       Moving source files...
for %%f in (api_client.py main.py sku_interceptor.py calibration.py browser.py config.py) do (
    if exist "modules\%%f" (
        move "modules\%%f" "modules\%%f.bak" >nul
    )
)
echo.

REM PyInstaller build
echo [3/4] Building with PyInstaller...
python -m PyInstaller --onefile --windowed --icon=icon.ico --name "RSI_MIEKCIK_BUY" RSI_MIEKCIK_BUY.py
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed!
)

REM Restore source .py files
echo       Restoring source files...
for %%f in (api_client.py main.py sku_interceptor.py calibration.py browser.py config.py) do (
    if exist "modules\%%f.bak" (
        move "modules\%%f.bak" "modules\%%f" >nul
    )
)
del /q modules\*.c 2>nul
echo.

if not exist "dist\RSI_MIEKCIK_BUY.exe" (
    echo [ERROR] EXE not found!
    pause
    exit /b 1
)

REM Copy resources
echo [4/4] Copying resources...
if not exist "dist\images" mkdir "dist\images"
copy /y "images\*.png" "dist\images\" >nul
copy /y "icon.ico" "dist\" >nul
copy /y "GUIDE.txt" "dist\" >nul
copy /y "sku_bookmarks.example.json" "dist\" >nul
echo       Done.
echo.

echo ================================================
echo   Protected Build Complete!
echo   Protection: Cython (.pyd) + Disclaimer
echo ================================================
echo.
pause