# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for My Typeless
使用方法: pyinstaller my_typeless.spec
"""

import sys
from pathlib import Path

block_cipher = None

# 项目根目录
ROOT = Path(SPECPATH)
SRC = ROOT / "src" / "my_typeless"
RESOURCES = SRC / "resources"

a = Analysis(
    [str(SRC / "main.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        # 打包资源文件
        (str(RESOURCES / "*.ico"), "my_typeless/resources"),
        (str(RESOURCES / "*.svg"), "my_typeless/resources"),
    ],
    hiddenimports=[
        "my_typeless",
        "my_typeless.config",
        "my_typeless.history",
        "my_typeless.hotkey",
        "my_typeless.llm_client",
        "my_typeless.recorder",
        "my_typeless.stt_client",
        "my_typeless.text_injector",
        "my_typeless.tray",
        "my_typeless.worker",
        "my_typeless.version",
        "my_typeless.updater",
        # PyQt6 相关
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.sip",
        # pyaudio 底层依赖
        "pyaudio",
        "_portaudio",
        # Win32 相关
        "win32clipboard",
        "win32con",
        "win32api",
        "pywintypes",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
        "pytest",
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MyTypeless",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI 应用，不显示控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(RESOURCES / "app_icon.ico"),
    # 版本信息
    version="file_version_info.txt",
)
