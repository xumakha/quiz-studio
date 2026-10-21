@echo off
cd /d "%~dp0"
if exist "release-current\QuizStudio\QuizStudio.exe" (
  if exist "release-current\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-current\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-samples\QuizStudio\QuizStudio.exe" (
  if exist "release-samples\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-samples\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-dialogue\QuizStudio\QuizStudio.exe" (
  if exist "release-dialogue\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-dialogue\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if not exist "release-clear\QuizStudio\QuizStudio.exe" goto missing
if not exist "release-clear\QuizStudio\_internal\python3*.dll" goto missing
if not exist "release-clear\QuizStudio\_internal\_tcl_data\init.tcl" goto missing
if not exist "release-clear\QuizStudio\_internal\_tk_data\tk.tcl" goto missing
start "" "release-clear\QuizStudio\QuizStudio.exe"
exit /b
:missing
echo Khong tim thay ban app day du. Hay chay build.bat de dong goi lai.
pause
exit /b 1
