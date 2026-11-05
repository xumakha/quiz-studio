@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Khong tim thay Python cua Quiz Studio.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" voice_studio_runtime.py
if errorlevel 1 pause
