@echo off
cd /d "%~dp0"
if not exist "release-clear\QuizStudio\QuizStudio.exe" goto missing
if not exist "release-clear\QuizStudio\_internal\python311.dll" goto missing
if not exist "release-clear\QuizStudio\_internal\_tcl_data\init.tcl" goto missing
if not exist "release-clear\QuizStudio\_internal\_tk_data\tk.tcl" goto missing
start "" "release-clear\QuizStudio\QuizStudio.exe"
exit /b
:missing
echo Khong tim thay ban app day du. Hay chay build.bat de dong goi lai.
pause
exit /b 1
