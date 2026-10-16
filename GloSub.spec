# -*- mode: python ; coding: utf-8 -*-

from importlib.util import find_spec
from PyInstaller.utils.hooks import collect_data_files, collect_all, collect_dynamic_libs, collect_submodules


datas = [
    ("i18n.json", "."),
    ("subtitle_config.json", "."),
    ("icon.ico", "."),
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

# Optional offline runtime is bundled only when installed in the build venv.
# Converted model weights remain external, selected by the user in Settings.
binaries = []
if find_spec("ctranslate2") is not None:
    datas += collect_data_files("ctranslate2")
    binaries += collect_dynamic_libs("ctranslate2")
    hiddenimports += collect_submodules(
        "ctranslate2",
        filter=lambda name: not name.startswith(("ctranslate2.converters", "ctranslate2.specs")),
    )
    for package in ("sentencepiece", "sacremoses"):
        package_datas, package_binaries, package_imports = collect_all(package)
        datas += package_datas
        binaries += package_binaries
        hiddenimports += package_imports

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
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
        # Offline runtime uses CTranslate2/SentencePiece; these packages are
        # conversion-only and otherwise drag hundreds of unused models in.
        "transformers",
        "tokenizers",
        "safetensors",
        "huggingface_hub",
        "ctranslate2.converters",
        "ctranslate2.specs",
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
    icon=["icon.ico"],
    version="version_info.txt",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GloSub-v1.1.1-Windows-x64",
)
