@echo off
title Drox Screen Studio
cd /d "%~dp0"

echo ========================================================
echo         Launching Drox Screen Studio...
echo ========================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in your system PATH.
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

:: Run the application
python main.py

:: If the app exited with an error, pause so user can see it
if errorlevel 1 (
    echo.
    echo [ERROR] Application closed with an error.
    pause
)
