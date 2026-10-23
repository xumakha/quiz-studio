@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 exit /b 1
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --distpath release-background-library QuizStudio.spec
if errorlevel 1 exit /b 1
echo.
echo Dong goi thanh cong. Mo Mo-QuizStudio.bat hoac release-background-library\QuizStudio\QuizStudio.exe.
echo Thu muc build chi chua file trung gian, khong chay exe trong do.
echo Khi sao chep app, giu nguyen ca thu muc release-background-library\QuizStudio va _internal.
pause
