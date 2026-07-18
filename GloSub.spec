# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files


datas = [
    ("i18n.json", "."),
    ("subtitle_config.json", "."),
    ("Icon.ico", "."),
    ("requirements-gpu.txt", "."),
    ("assets", "assets"),
]
datas += collect_data_files("easyocr")

hiddenimports = [
    "easyocr",
    "edge_tts",
    "pygame",
    "deep_translator",
    "boto3",
    "botocore",
    "google.auth",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["runtime_hook_torch.py"],
    excludes=[
        "tkinter",
        "matplotlib",
        "IPython",
        "jupyter",
        "torch.utils.tensorboard",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GloSub",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=["Icon.ico"],
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GloSub-v1.0.0-Windows-x64",
)
