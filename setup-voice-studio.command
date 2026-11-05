#!/bin/bash
set -e
cd "$(dirname "$0")"
./macos-python.sh .venv-macos/bin/python setup_voice_studio.py
