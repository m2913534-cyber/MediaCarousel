"""Run on Windows or Mac to produce a native standalone distribution."""
import platform,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parent
if sys.platform not in ('win32','darwin'):
    raise SystemExit('This build entry point requires Windows or macOS; cross-platform binaries cannot be created here.')
subprocess.run([sys.executable,'-m','unittest','discover','-s',str(root),'-p','test_model.py'],cwd=root,check=True)
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean',str(root/'MediaCarousel.spec')],cwd=root,check=True)
print('Build completed for',platform.system(),platform.machine())
print(root/'dist'/('MediaCarousel.app' if sys.platform=='darwin' else 'MediaCarousel/MediaCarousel.exe'))
