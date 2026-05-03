@echo off
chcp 65001 >nul
REM RSI_MIEKCIK_BUY Protected Build - DEBUG (console visible)

echo ================================================
echo   RSI_MIEKCIK_BUY Protected Build (DEBUG)
echo   MieMie Kick! V3.0.3 - Console Mode
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
if exist "dist_debug" rmdir /s /q "dist_debug"
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
    pause
    exit /b 1
)
echo       Cython compilation done.
echo.

REM Move source .py to .bak
echo       Moving source files...
for %%f in (api_client.py main.py sku_interceptor.py calibration.py browser.py config.py) do (
    if exist "modules\%%f" (
        move "modules\%%f" "modules\%%f.bak" >nul
    )
)
echo.

REM PyInstaller build (NO --windowed, console stays open for debug)
echo [3/4] Building with PyInstaller (console mode)...
python -m PyInstaller --onefile --icon=icon.ico --name "RSI_MIEKCIK_BUY" --distpath dist_debug RSI_MIEKCIK_BUY.py
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

if not exist "dist_debug\RSI_MIEKCIK_BUY.exe" (
    echo [ERROR] EXE not found!
    pause
    exit /b 1
)

REM Copy resources
echo [4/4] Copying resources...
if not exist "dist_debug\images" mkdir "dist_debug\images"
copy /y "images\*.png" "dist_debug\images\" >nul
copy /y "icon.ico" "dist_debug\" >nul
copy /y "GUIDE.txt" "dist_debug\" >nul
copy /y "sku_bookmarks.example.json" "dist_debug\" >nul
echo       Done.
echo.

echo ================================================
echo   Protected Build Complete! (DEBUG - Console)
echo   Console stays open on crash for error info
echo   Output: dist_debug\RSI_MIEKCIK_BUY.exe
echo ================================================
echo.
pause