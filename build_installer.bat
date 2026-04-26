@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo ====================================================
echo   MemoryNest Sync - Build Standalone Installer
echo ====================================================
echo.

REM -- Sanity check: Python on PATH --
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] python is not on PATH.
    echo         Install Python and ensure it is added to PATH, then retry.
    pause
    exit /b 1
)

REM -- Sanity check: required source files --
if not exist "main.py" (
    echo [ERROR] main.py not found in %CD%.
    echo         Run this batch from the project root.
    pause
    exit /b 1
)
if not exist "_build_helper.py" (
    echo [ERROR] _build_helper.py not found.
    echo         It should sit alongside build_installer.bat.
    pause
    exit /b 1
)

REM -- Read APP_VERSION via the helper script --
echo Detecting APP_VERSION from main.py ...
for /f "usebackq tokens=*" %%v in (`python _build_helper.py version`) do set "APP_VERSION=%%v"
if "%APP_VERSION%"=="" (
    echo [ERROR] Could not read APP_VERSION. Helper output was empty.
    pause
    exit /b 1
)
echo Detected APP_VERSION = %APP_VERSION%
echo.

REM -- Ensure PyInstaller is available --
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo PyInstaller not found. Installing ...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] PyInstaller install failed.
        pause
        exit /b 1
    )
)

REM -- Clean previous build outputs to avoid stale state --
if exist "build" (
    echo Cleaning previous build/ ...
    rmdir /s /q "build"
)
if exist "dist" (
    echo Cleaning previous dist/ ...
    rmdir /s /q "dist"
)

echo.
echo Building executable for v%APP_VERSION% ...
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

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed. Check messages above.
    pause
    exit /b 1
)

REM -- Sync installer.iss with the detected version --
echo.
echo Updating installer.iss to v%APP_VERSION% ...
python _build_helper.py update-iss %APP_VERSION%
if errorlevel 1 (
    echo [WARN] Could not auto-update installer.iss. Edit AppVersion manually.
)

REM -- Try to auto-compile the installer with Inno Setup if it is available --
REM ISCC.exe is the command-line compiler installed alongside Inno Setup 6.
REM We probe a few common install paths AND PATH; if found we run it
REM automatically so the user gets a setup.exe in one click.
echo.
echo Looking for Inno Setup Compiler (ISCC.exe) ...
set "ISCC="
for %%P in (
    "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles%\Inno Setup 6\ISCC.exe"
    "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"
    "%ProgramFiles%\Inno Setup 5\ISCC.exe"
) do (
    if exist %%P set "ISCC=%%~P"
)
if "%ISCC%"=="" (
    where ISCC.exe >nul 2>nul && for /f "delims=" %%p in ('where ISCC.exe') do set "ISCC=%%p"
)

if "%ISCC%"=="" (
    echo.
    echo ====================================================
    echo  Build SUCCESS  -  v%APP_VERSION%   ^(stage 1 of 2^)
    echo ====================================================
    echo.
    echo  PyInstaller output : dist\MemoryNest Sync\
    echo  Installer template : installer.iss   ^(synced to v%APP_VERSION%^)
    echo.
    echo  Inno Setup Compiler not found.
    echo  Install it from  https://jrsoftware.org/isdl.php  to enable
    echo  auto-compilation, OR open installer.iss manually and press F9.
    echo.
    echo  Final output will be:
    echo    installer_output\MemoryNestSync_Setup_v%APP_VERSION%.exe
    echo.
    pause
    endlocal
    exit /b 0
)

echo Found: %ISCC%
echo.
echo Compiling installer with Inno Setup ...
echo.
"%ISCC%" /Qp installer.iss
if errorlevel 1 (
    echo.
    echo [ERROR] Inno Setup compile failed. See messages above.
    pause
    exit /b 1
)

echo.
echo ====================================================
echo  Build SUCCESS  -  v%APP_VERSION%   ^(complete^)
echo ====================================================
echo.
echo  Final installer:
echo    %CD%\installer_output\MemoryNestSync_Setup_v%APP_VERSION%.exe
echo.
echo  Distribute this single .exe — it will install MemoryNest Sync
echo  on any Windows machine without requiring admin rights by default.
echo.

REM Open the output folder so the user sees the file immediately.
if exist "installer_output" start "" "%CD%\installer_output"

pause
endlocal
