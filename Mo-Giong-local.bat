@echo off
cd /d "%~dp0"
if exist "release-adam-local\QuizStudio\QuizStudio.exe" (
  start "" "release-adam-local\QuizStudio\QuizStudio.exe"
  exit /b
)
".venv\Scripts\python.exe" app.py
