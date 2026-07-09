@echo off
REM ============================================================
REM  Telegram APK Bot - Windows double-click launcher
REM  File: run_bot.bat
REM
REM  Just double-click this file in File Explorer to:
REM    1) Make sure Python is installed
REM    2) Install the bot's dependencies
REM    3) Run the bot
REM ============================================================

chcp 65001 > nul 2>&1
title Telegram APK Bot (Uptodown)
cd /d "%~dp0"

echo.
echo ============================================================
echo   Telegram APK Bot - Windows Launcher
echo ============================================================
echo.

REM ---- Step 1: Check that Python is installed ----
echo [1/3] Checking Python...
python --version > nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.10+ from:
    echo   https://www.python.org/downloads/windows/
    echo.
    echo IMPORTANT: During installation, check the box
    echo   "Add Python to PATH" before clicking Install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version') do set PYVER=%%v
echo   Python %PYVER% found.

REM ---- Step 2: Install dependencies ----
echo.
echo [2/3] Installing dependencies (first run only, may take 1-2 minutes)...
python -m pip install --quiet --upgrade pip > nul 2>&1
python -m pip install --quiet -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies.
    echo Try running manually:
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo   Dependencies OK.

REM ---- Step 3: Check .env exists ----
echo.
echo [3/3] Checking .env file...
if not exist ".env" (
    echo.
    echo WARNING: .env file not found!
    echo   Creating from .env.example...
    echo   Please edit .env and fill in BOT_TOKEN before running.
    echo.
    copy .env.example .env > nul
    echo   .env created. Edit it now (BOT_TOKEN is required).
    echo.
    pause
    exit /b 1
)
echo   .env file found.

REM ---- Run the bot ----
echo.
echo ============================================================
echo   Starting bot... Press Ctrl+C to stop.
echo ============================================================
echo.
python bot.py

pause
