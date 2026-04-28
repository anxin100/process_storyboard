# -*- mode: python ; coding: utf-8 -*-
"""
CLI build (default):
- macOS: dist/process_storyboard  (one-file executable)
- Windows: dist/process_storyboard.exe (one-file executable)

This spec intentionally bundles ONLY the current platform's dreamina CLI payload:
  vendor/dreamina_cli/<platform_key>/**
"""

import os
import platform
import sys

from PyInstaller.building.api import EXE, PYZ
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
    if system == "linux":
        return f"linux_{machine}"
    if system == "windows":
        return "windows_amd64"
    return f"{system}_{machine}"


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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="process_storyboard",
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

