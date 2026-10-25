#!/bin/bash
cd "$(dirname "$0")" || exit 1
# Keep Finder's Terminal window open when setup or the app fails.
quiz_finish() {
  status=$?
  if [[ $status -ne 0 && -t 0 ]]; then
    read -r -p "Không mở được app. Xem lỗi phía trên; nhấn Enter để đóng..." || true
  fi
  exit "$status"
}
trap quiz_finish EXIT
source ./macos-python.sh
.venv-macos/bin/python app.py
