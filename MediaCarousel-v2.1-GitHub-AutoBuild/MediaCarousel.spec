# Build on the target operating system. Qt multimedia hooks include decoder libs.
import sys
from pathlib import Path
root=Path(SPECPATH)
platform_imports=['pythoncom','pywintypes','win32com.client'] if sys.platform=='win32' else []
a=Analysis([str(root/'app.py')],pathex=[str(root)],binaries=[],datas=[(str(root/'assets'),'assets')],hiddenimports=['playback_cache','smoke_media','compositor','model','interface','audio_meter','audio_mixer','single_editor','video_editor','pdf_source','presentations','powerpoint','PySide6.QtPdf']+platform_imports,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtWebEngineQuick'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='MediaCarousel',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,disable_windowed_traceback=False,target_arch=None,codesign_identity=None,entitlements_file=None)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='MediaCarousel')
if sys.platform=='darwin':
    app=BUNDLE(coll,name='MediaCarousel.app',icon=None,bundle_identifier='local.mediacarousel.studio',info_plist={'CFBundleShortVersionString':'2.9.0','CFBundleVersion':'290','NSHighResolutionCapable':True,'NSCameraUsageDescription':'加入攝影機或 HDMI 擷取卡的即時畫面。','NSScreenCaptureUsageDescription':'將選定螢幕或視窗加入多畫面輸出。'})

