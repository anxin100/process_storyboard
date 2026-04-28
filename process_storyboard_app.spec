# -*- mode: python ; coding: utf-8 -*-
"""
macOS .app build (optional):
- dist/process_storyboard.app

This spec intentionally bundles ONLY the current platform's dreamina CLI payload:
  vendor/dreamina_cli/<platform_key>/**
"""

import os
import platform
import sys

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_all


def _normalize_machine(m: str) -> str:
    m = (m or "").lower()
    if m in {"amd64", "x86_64"}:
        return "amd64"
    if m in {"aarch64", "arm64"}:
        return "arm64"
    return m


def _default_platform_key() -> str:
    system = platform.system().lower()
    machine = _normalize_machine(platform.machine())
    if system == "darwin":
        return f"darwin_{machine}"
    return f"{system}_{machine}"


if sys.platform != "darwin":
    raise SystemExit("process_storyboard_app.spec 仅用于 macOS 构建")

# macOS-only import
from PyInstaller.building.osx import BUNDLE  # type: ignore


block_cipher = None

platform_key = os.environ.get("DREAMINA_PLATFORM_KEY") or _default_platform_key()
dreamina_datas = [(f"vendor/dreamina_cli/{platform_key}", f"vendor/dreamina_cli/{platform_key}")]

binaries = []
hiddenimports = []
datas = dreamina_datas[:]

for pkg in ("pandas", "numpy", "requests", "certifi", "openpyxl"):
    try:
        d, b, h = collect_all(pkg)
    except Exception:
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["process_storyboard.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="process_storyboard",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="process_storyboard",
)

app = BUNDLE(
    coll,
    name="process_storyboard.app",
    icon=None,
    bundle_identifier="com.anxin.process_storyboard",
    info_plist={
        "CFBundleShortVersionString": "0.0.0",
        "CFBundleVersion": "0.0.0",
        "NSHighResolutionCapable": True,
    },
)

