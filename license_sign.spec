# -*- mode: python ; coding: utf-8 -*-
"""
独立打包离线授权签名工具（不含 process_storyboard / dreamina）：
- macOS/Linux: dist/license_sign
- Windows: dist/license_sign.exe
"""

import os

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_all

# 必须把 scripts 放进搜索路径，否则 sibling 模块 license_common 在 Analysis 阶段找不到，
# onefile 运行时会出现 ModuleNotFoundError: license_common（Windows/macOS 均可能发生）。
_SPEC_DIR = os.path.dirname(os.path.abspath(SPEC))
_SCRIPTS_DIR = os.path.join(_SPEC_DIR, "scripts")

block_cipher = None

binaries = []
hiddenimports = []
datas = []

for pkg in ("cryptography",):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["scripts/license_sign.py"],
    pathex=[_SCRIPTS_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["license_common"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="license_sign",
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
