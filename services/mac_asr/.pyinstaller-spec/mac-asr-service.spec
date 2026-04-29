# -*- mode: python ; coding: utf-8 -*-
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_submodules

HERE = os.path.dirname(os.path.abspath(SPEC))
SERVICE_ROOT = os.path.normpath(os.path.join(HERE, '..'))
COMMON_SRC = os.path.normpath(os.path.join(HERE, '..', '..', 'common', 'src'))

for path in (SERVICE_ROOT, COMMON_SRC):
    if path not in sys.path:
        sys.path.insert(0, path)

datas = []
binaries = []
hiddenimports = []

for pkg in ('uvicorn', 'anyio', 'starlette', 'fastapi', 'common',
            'faster_whisper', 'ctranslate2', 'tokenizers'):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hiddenimports += h

# PyObjC frameworks used by mac_asr (Speech recognition)
for pkg in ('objc', 'Foundation', 'AppKit', 'Speech', 'CoreFoundation'):
    try:
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h
    except Exception:
        hiddenimports += collect_submodules(pkg)

hiddenimports += [
    'objc._objc', 'Foundation', 'AppKit', 'Speech', 'CoreFoundation',
]

hiddenimports += collect_submodules('app')
hiddenimports += collect_submodules('src')


a = Analysis(
    [os.path.join(HERE, 'entry.py')],
    pathex=[SERVICE_ROOT, COMMON_SRC],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='mac-asr-service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
