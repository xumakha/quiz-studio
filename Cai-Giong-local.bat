@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install requests certifi uv
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" setup_local_voice.py
if errorlevel 1 (
  echo Cai dat chua hoan tat. Chay lai de tiep tuc.
  pause
  exit /b 1
)
echo Da cai Adam local. Mo Mo-Giong-local.bat va chon Adam Local trong Giong doc.
pause
