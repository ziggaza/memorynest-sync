@echo off
cd /d "%~dp0"

echo ================================================
echo  MemoryNest Sync - Build Standalone Installer
echo ================================================
echo.

:: Check PyInstaller
python -c "import PyInstaller" 2>nul
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

echo Building executable...
echo.

pyinstaller ^
    --onedir ^
    --windowed ^
    --name "MemoryNest Sync" ^
    --icon "assets\icon.ico" ^
    --add-data "config.json;." ^
    --add-data "core;core" ^
    --hidden-import "customtkinter" ^
    --hidden-import "PIL._tkinter_finder" ^
    --hidden-import "exifread" ^
    --hidden-import "pymediainfo" ^
    --hidden-import "xxhash" ^
    --hidden-import "pystray" ^
    --collect-all "customtkinter" ^
    --collect-all "darkdetect" ^
    --collect-all "pystray" ^
    main.py

if %errorlevel% equ 0 (
    echo.
    echo ================================================
    echo  Build SUCCESS!
    echo  Output folder: dist\MemoryNest Sync\
    echo ================================================
    echo.
    echo To distribute: ZIP the entire "dist\MemoryNest Sync\" folder
    echo or use Inno Setup with installer.iss to create a proper setup.exe
) else (
    echo.
    echo Build FAILED. Check errors above.
    pause
)
pause
