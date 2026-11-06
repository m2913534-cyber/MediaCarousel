"""Validate the three native archives and create release metadata; no device claims."""
import ast
import hashlib
import os
from pathlib import Path
import plistlib
import re
import struct
import sys
import zipfile

root = Path(__file__).resolve().parents[2]
source = root / 'MediaCarousel-v2.1-GitHub-AutoBuild'
version = re.search(r"'CFBundleShortVersionString':'([^']+)'", (source / 'MediaCarousel.spec').read_text()).group(1)
tag = os.environ.get('GITHUB_REF', '')
if tag.startswith('refs/tags/') and tag != f'refs/tags/v{version}':
    raise SystemExit(f'Tag must match bundle version v{version}')
folder = Path(sys.argv[1])
packages = {
    'MediaCarousel-Windows-x64.zip': 'MediaCarousel/MediaCarousel.exe',
    'MediaCarousel-Mac-Apple-Silicon.zip': 'MediaCarousel.app/Contents/MacOS/MediaCarousel',
    'MediaCarousel-Mac-Intel.zip': 'MediaCarousel.app/Contents/MacOS/MediaCarousel',
}
assert {p.name for p in folder.glob('*.zip')} == set(packages), 'Unexpected or missing ZIP packages'
sums = []
for name, executable in packages.items():
    path = folder / name
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, f'ZIP CRC failed: {name}'
        assert len(archive.namelist()) == len(set(archive.namelist())), 'Duplicate ZIP entries'
        assert not any(n.startswith('/') or '..' in n.split('/') for n in archive.namelist()), 'Unsafe archive path'
        data = archive.read(executable)
        if 'Windows' in name:
            assert data[:2] == b'MZ', 'Missing PE header'
            offset = struct.unpack_from('<I', data, 0x3c)[0]
            assert data[offset:offset+4] == b'PE\0\0'
            assert struct.unpack_from('<H', data, offset+4)[0] == 0x8664, 'Expected Windows x64'
            assert any(n.startswith('MediaCarousel/_internal/') for n in archive.namelist()), 'Missing Windows runtime'
        else:
            assert data[:4] == b'\xcf\xfa\xed\xfe', 'Expected native 64-bit Mach-O'
            expected = 0x100000c if 'Apple' in name else 0x1000007
            assert struct.unpack_from('<I', data, 4)[0] == expected, 'Wrong macOS architecture'
            assert (archive.getinfo(executable).external_attr >> 16) & 0o111, 'Executable permission missing'
            info = plistlib.loads(archive.read('MediaCarousel.app/Contents/Info.plist'))
            assert info['CFBundleShortVersionString'] == version, 'Wrong bundle version'
            assert any(n.startswith('MediaCarousel.app/Contents/Frameworks/') for n in archive.namelist()), 'Missing macOS runtime'
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    sums.append(f'{digest}  {name}\n')
    print(f'PASS: CRC, executable architecture and runtime layout: {name}')
(folder / 'SHA256SUMS.txt').write_text(''.join(sums), encoding='utf-8')
notes = f'''# MediaCarousel {version}

三平台完整桌面 ZIP；使用者不需安裝 Python。Windows 解壓後開啟 MediaCarousel/MediaCarousel.exe，保留整個資料夾。Mac 解壓後將 MediaCarousel.app 拖到「應用程式」。M3 Max 請下載 Apple Silicon 版。

## 本次發佈驗證
- 同一次 GitHub Actions 的 Windows x64、macOS arm64、macOS x64 原生建置與模型測試通過，並執行 ci_verify.py 的成品啟動檢查。
- ZIP CRC、可執行檔架構及 runtime 目錄檢查通過；SHA256SUMS.txt 由本次三個 ZIP 計算。
- 以上為 CI 自動檢查，未完成實體 Windows、M3 Max、Intel Mac 安裝與操作測試。影片／音訊、12 路效能、擷取卡、外接螢幕及 PowerPoint 動畫音效仍待實機驗證。
- 未使用 Windows 商業簽章或 Apple Developer ID 簽章／公證。首次啟動可能遭系統攔截；確認來源後依系統提示允許開啟。
- 成品不包含 Office。PowerPoint 原生播放需另有已安裝、啟用的 PowerPoint 及必要系統權限。

來源 commit：{os.environ.get('GITHUB_SHA', 'local validation')}。
建置紀錄：https://github.com/{os.environ.get('GITHUB_REPOSITORY', 'm2913534-cyber/MediaCarousel')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}

## 2.11 更新紀錄（原始碼記載，非新增實機驗證）

'''
notes += (source / 'UPDATE-2.11.md').read_text(encoding='utf-8')
(folder / 'RELEASE-NOTES.md').write_text(notes, encoding='utf-8')
