#!/bin/bash
set -e
cd "$(dirname "$0")"
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
"$media_python" -m venv .build-venv
.build-venv/bin/python -m pip install -r requirements-build.txt
.build-venv/bin/python build.py
echo 'Finished: dist/MediaCarousel.app. Copy it to Applications on a Mac of the same architecture.'
open dist
read -r -p 'Press Return to close.'
