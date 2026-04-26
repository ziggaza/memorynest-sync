@echo off
cd /d "%~dp0"

echo ================================================
echo  MemoryNest Sync - Build Standalone Installer
echo ================================================
echo.

:: ── Read APP_VERSION from main.py ─────────────────────────────────────────────
for /f "delims=" %%v in ('python -c "import re; print(re.search(r'APP_VERSION\s*=\s*\"([^\"]+)\"', open('main.py', encoding='utf-8').read()).group(1))"') do set APP_VERSION=%%v
if "%APP_VERSION%"=="" (
    echo Could not detect APP_VERSION from main.py. Aborting.
    pause
    exit /b 1
)
echo Detected APP_VERSION = %APP_VERSION%
echo.

:: ── Check PyInstaller ─────────────────────────────────────────────────────────
python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

:: ── Clean previous build (avoid stale state) ─────────────────────────────────
if exist "build" rmdir /s /q "build"
if exist "dist"  rmdir /s /q "dist"

echo Building executable for v%APP_VERSION%...
echo.

pyinstaller ^
    --onedir ^
    --windowed ^
    --name "MemoryNest Sync" ^
    --icon "assets\icon.ico" ^
    --add-data "config.json;." ^
    --add-data "core;core" ^
    --add-data "assets;assets" ^
    --hidden-import "customtkinter" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "exifread" ^
    --hidden-import "pymediainfo" ^
    --hidden-import "xxhash" ^
    --hidden-import "pystray" ^
    --hidden-import "numpy" ^
    --collect-all "customtkinter" ^
    --collect-all "darkdetect" ^
    --collect-all "pystray" ^
    main.py

if %errorlevel% neq 0 (
    echo.
    echo Build FAILED. Check errors above.
    pause
    exit /b 1
)

:: ── Update installer.iss with the current version ────────────────────────────
:: Rewrites AppVersion + OutputBaseFilename so each release produces a uniquely-
:: named .exe in installer_output/, no manual edits required.
echo.
echo Updating installer.iss with version %APP_VERSION%...
python -c "import re; t=open('installer.iss',encoding='utf-8').read(); t=re.sub(r'^AppVersion=.*$', 'AppVersion=%APP_VERSION%', t, flags=re.M); t=re.sub(r'^OutputBaseFilename=.*$', 'OutputBaseFilename=MemoryNestSync_Setup_v%APP_VERSION%', t, flags=re.M); open('installer.iss','w',encoding='utf-8').write(t)"
if %errorlevel% neq 0 (
    echo Warning: Could not update installer.iss automatically.
    echo You can still compile manually with the existing version.
)

echo.
echo ================================================
echo  Build SUCCESS!  v%APP_VERSION%
echo ================================================
echo.
echo  PyInstaller output:   dist\MemoryNest Sync\
echo  Installer template:   installer.iss   (updated to v%APP_VERSION%)
echo.
echo  Next step: open installer.iss in Inno Setup Compiler and click Compile.
echo  Output:    installer_output\MemoryNestSync_Setup_v%APP_VERSION%.exe
echo.

pause
