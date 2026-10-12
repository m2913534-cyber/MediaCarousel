#!/bin/bash
cd "$(dirname "$0")" || exit 1
media_python=''
for candidate in python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null && "$candidate" -c 'import sys; assert (3,11) <= sys.version_info[:2] <= (3,12)' 2>/dev/null; then
    media_python="$candidate"
    break
  fi
done
if [ -z "$media_python" ]; then
  echo 'Please install Python 3.11 or 3.12 from python.org.'
  read -r -p 'Press Return to close.'
  exit 1
fi
"$media_python" -m venv .venv || exit 1
if ! .venv/bin/python -c 'import PySide6' 2>/dev/null; then
  .venv/bin/python -m pip install -r requirements.txt || exit 1
fi
.venv/bin/python app.py
