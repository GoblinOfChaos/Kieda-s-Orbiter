@echo off
title Kieda's Orbiter - Installer
color 0B

echo.
echo  ===================================================
echo   Kieda's Orbiter - Windows Installer
echo  ===================================================
echo.

:: Check Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python 3.11+ is not installed or not in PATH.
    echo.
    echo  Please install Python from:
    echo    https://python.org/downloads/
    echo.
    echo  IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    start https://python.org/downloads/
    exit /b 1
)

:: Check Python version is 3.11+
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python 3.11 or newer is required.
    python --version
    echo  Please update Python from https://python.org/downloads/
    pause
    exit /b 1
)

echo  Python found:
python --version
echo.

:: Run the Python installer
echo  Running installer...
echo.
python "%~dp0install.py"

if %errorlevel% neq 0 (
    echo.
    echo  Installation encountered errors. See messages above.
    pause
    exit /b 1
)

echo.
echo  You can now launch Kieda's Orbiter from the Start Menu,
echo  or by double-clicking "Start Kieda's Orbiter.bat"
echo.
pause
