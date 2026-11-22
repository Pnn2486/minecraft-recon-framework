@echo off
rem Starts the recon web interface on Windows. Double-click this file.
rem It needs Python 3.10 or newer. If it is missing, the window tells you how to install it.
setlocal
cd /d "%~dp0"
set "PYCMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PYCMD=py -3"
)
if not defined PYCMD (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 set "PYCMD=python"
  )
)
if not defined PYCMD (
  echo Python 3.10 or newer was not found.
  echo Install it with: winget install Python.Python.3.12
  echo Or download the installer from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
%PYCMD% boot.py %*
if errorlevel 1 pause
