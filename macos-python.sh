#!/bin/bash
# Shared setup for the macOS launch and build commands.
set -e
cd "$(dirname "${BASH_SOURCE[0]}")"
if [[ "$(uname -s)" != Darwin ]]; then
  echo "Lệnh này dành cho macOS." >&2
  exit 1
fi
quiz_python_works() {
  "$1" -c 'import sys; assert sys.version_info >= (3, 11); import tkinter' >/dev/null 2>&1
}

PYTHON=""
if [[ -n "${QUIZ_PYTHON:-}" ]]; then
  if quiz_python_works "$QUIZ_PYTHON"; then
    PYTHON="$QUIZ_PYTHON"
  else
    echo "Python được chọn không dùng được: $QUIZ_PYTHON" >&2
    "$QUIZ_PYTHON" -c 'import sys; print(sys.version); assert sys.version_info >= (3, 11), "Cần Python 3.11+"; import tkinter' >&2
    exit 1
  fi
else
  # Finder and Terminal can resolve python3 to Apple's older system Python.
  # Also look for versioned Homebrew and python.org installations.
  for candidate in .venv-macos/bin/python python3 \
    /opt/homebrew/bin/python3 /opt/homebrew/bin/python3.[0-9]* \
    /usr/local/bin/python3 /usr/local/bin/python3.[0-9]* \
    /Library/Frameworks/Python.framework/Versions/3.*/bin/python3; do
    if quiz_python_works "$candidate"; then
      PYTHON="$candidate"
      break
    fi
  done
fi
if [[ -z "$PYTHON" ]]; then
  echo "Không tìm thấy Python 3.11+ có Tkinter." >&2
  echo "Cài Python từ python.org hoặc gói Homebrew python-tk khớp phiên bản Python." >&2
  echo "Có thể chọn Python bằng: QUIZ_PYTHON=/duong/dan/python3 ./run.command" >&2
  exit 1
fi
echo "Dùng Python: $PYTHON"
# Some Homebrew Python bottles require Expat symbols newer than macOS ships.
# Scope the library override to this launcher, leaving the system untouched.
if ! "$PYTHON" -c 'import pyexpat' >/dev/null 2>&1; then
  for quiz_expat in /opt/homebrew/opt/expat/lib /usr/local/opt/expat/lib; do
    if [[ -f "$quiz_expat/libexpat.1.dylib" ]] && \
      DYLD_LIBRARY_PATH="$quiz_expat${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}" \
      "$PYTHON" -c 'import pyexpat' >/dev/null 2>&1; then
      export DYLD_LIBRARY_PATH="$quiz_expat${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}"
      break
    fi
  done
  if ! "$PYTHON" -c 'import pyexpat' >/dev/null 2>&1; then
    echo "Python gặp lỗi thư viện XML. Với Homebrew, chạy: brew install expat" >&2
    "$PYTHON" -c 'import pyexpat' >&2
    exit 1
  fi
fi
if [[ ! -x .venv-macos/bin/python ]]; then
  "$PYTHON" -m venv .venv-macos
fi
.venv-macos/bin/python -c 'import tkinter'
if ! .venv-macos/bin/python -m pip --version >/dev/null 2>&1; then
  .venv-macos/bin/python -m ensurepip --upgrade --default-pip
fi
.venv-macos/bin/python -m pip install -r requirements.txt
