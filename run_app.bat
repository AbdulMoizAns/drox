@echo off
title Drox Screen Studio
echo Launching Drox Screen Studio...
python main.py
if errorlevel 1 (
    echo.
    echo An error occurred. Please make sure Python and PyQt6 are installed.
    pause
)
