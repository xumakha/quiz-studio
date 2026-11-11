@echo off
cd /d "%~dp0"
if exist "release-history-left\QuizStudio\QuizStudio.exe" (
  if exist "release-history-left\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-history-left\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-dmv-centered\QuizStudio\QuizStudio.exe" (
  if exist "release-dmv-centered\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-dmv-centered\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-dmv\QuizStudio\QuizStudio.exe" (
  if exist "release-dmv\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-dmv\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-history\QuizStudio\QuizStudio.exe" (
  if exist "release-history\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-history\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-title-centered\QuizStudio\QuizStudio.exe" (
  if exist "release-title-centered\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-title-centered\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-watermark-centered\QuizStudio\QuizStudio.exe" (
  if exist "release-watermark-centered\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-watermark-centered\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-watermark\QuizStudio\QuizStudio.exe" (
  if exist "release-watermark\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-watermark\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-prep-english\QuizStudio\QuizStudio.exe" (
  if exist "release-prep-english\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-prep-english\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-prep\QuizStudio\QuizStudio.exe" (
  if exist "release-prep\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-prep\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-corners\QuizStudio\QuizStudio.exe" (
  if exist "release-corners\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-corners\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-outro\QuizStudio\QuizStudio.exe" (
  if exist "release-outro\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-outro\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-tabs\QuizStudio\QuizStudio.exe" (
  if exist "release-tabs\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-tabs\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-background-library\QuizStudio\QuizStudio.exe" (
  if exist "release-background-library\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-background-library\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
if exist "release-latest\QuizStudio\QuizStudio.exe" (
  if exist "release-latest\QuizStudio\_internal\_tcl_data\init.tcl" (
    start "" "release-latest\QuizStudio\QuizStudio.exe"
    exit /b
  )
)
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
