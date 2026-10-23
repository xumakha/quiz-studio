@echo off
cd /d "%~dp0"
if exist "release-background-library\QuizStudio\QuizStudio.exe" (
  call Mo-QuizStudio.bat
  exit /b
)
if exist "release-latest\QuizStudio\QuizStudio.exe" (
  call Mo-QuizStudio.bat
  exit /b
)
if exist "release-current\QuizStudio\QuizStudio.exe" (
  call Mo-QuizStudio.bat
  exit /b
)
if exist "release-samples\QuizStudio\QuizStudio.exe" (
  call Mo-QuizStudio.bat
  exit /b
)
if exist "release-dialogue\QuizStudio\QuizStudio.exe" (
  call Mo-QuizStudio.bat
  exit /b
)
if exist "release-clear\QuizStudio\QuizStudio.exe" (
  call Mo-QuizStudio.bat
  exit /b
)
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto fail
".venv\Scripts\python.exe" app.py
exit /b
:fail
echo Khong khoi dong duoc. Kiem tra Python va ket noi Internet.
pause
