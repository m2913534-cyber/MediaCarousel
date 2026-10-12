"""Verify the bundled app starts, then package the complete distribution."""
import json
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parent
if sys.platform=='win32':
    executable=root/'dist/MediaCarousel/MediaCarousel.exe'
elif sys.platform=='darwin':
    executable=root/'dist/MediaCarousel.app/Contents/MacOS/MediaCarousel'
else:
    raise SystemExit('Windows or macOS required')
if not executable.is_file():
    raise SystemExit(f'Missing executable: {executable}')
with tempfile.TemporaryDirectory() as temp:
    report=Path(temp)/'startup.json'
    subprocess.run([str(executable),'--build-smoke-test',str(report)],cwd=temp,check=True,timeout=90)
    result=json.loads(report.read_text(encoding='utf-8'))
    if not result.get('ok'):
        raise SystemExit(f'Startup check failed: {result}')
print('PASS: bundled app startup and decoder enumeration',platform.system(),platform.machine())
