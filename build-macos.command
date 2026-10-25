#!/bin/bash
cd "$(dirname "$0")" || exit 1
source ./macos-python.sh
.venv-macos/bin/python -m pip install pyinstaller
# Use standard macOS Tcl/Tk hooks; the Windows spec overrides them with DLLs.
.venv-macos/bin/python -m PyInstaller --noconfirm --clean --windowed --name QuizStudio \
  --distpath release-macos --workpath build/macos --specpath build/macos \
  --collect-all customtkinter --collect-all imageio_ffmpeg --collect-all edge_tts \
  --add-data 'assets:assets' --add-data 'examples:examples' --add-data 'docs:docs' app.py
echo "Đã tạo release-macos/QuizStudio.app"
