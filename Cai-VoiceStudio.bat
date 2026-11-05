@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" setup_voice_studio.py
if errorlevel 1 (
  echo Cai dat chua hoan tat. Chay lai file nay de tiep tuc.
  pause
  exit /b 1
)
echo Cai dat xong. Mo Mo-QuizStudio.bat va bam VoiceStudio.
pause
