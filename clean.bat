@echo off
chcp 65001 >nul
REM RSI_MIEKCIK_BUY - Clean caches for development

echo ================================================
echo   Clean build caches (.pyd + __pycache__)
echo ================================================
echo.

echo Cleaning .pyd files...
del /q modules\*.pyd 2>nul
echo       Done.

echo Cleaning .c files (Cython intermediate)...
del /q modules\*.c 2>nul
echo       Done.

echo Cleaning __pycache__...
if exist "modules\__pycache__" rmdir /s /q "modules\__pycache__"
echo       Done.

echo.
echo ================================================
echo   All caches cleaned. Safe to run source code.
echo ================================================
echo.
pause
