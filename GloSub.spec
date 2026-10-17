# -*- mode: python ; coding: utf-8 -*-

from importlib.util import find_spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_all, collect_dynamic_libs, collect_submodules, get_package_paths


datas = [
    ("i18n.json", "."),
    ("subtitle_config.json", "."),
    ("icon.ico", "."),
    ("requirements-gpu.txt", "."),
    ("THIRD_PARTY_SPEECH.md", "."),
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
if find_spec("faster_whisper") is not None:
    datas += collect_data_files("faster_whisper")  # bundled Silero VAD graph
    # Piper imports ONNX Runtime at its package entry point. Keep Piper raw as
    # well so the shared scanner cannot import ONNX indirectly through it.
    datas += collect_data_files("piper", include_py_files=True,
                               includes=["*.py", "**/*.py", "espeak-ng-data/**/*"])
    binaries += collect_dynamic_libs("piper")
    _, piper_dir = get_package_paths("piper")
    for pattern in ("*.pyd", "*.so"):
        binaries += [(str(path), "piper") for path in Path(piper_dir).glob(pattern)]
    # As with SentencePiece below, ONNX Runtime works in the application but
    # crashes PyInstaller's reused DLL-probing process after Torch/Qt imports.
    # Ship its Python/native package explicitly without importing it in that
    # shared scanner. The frozen EXE still exercises real ASR/VAD and synthesis.
    _, onnx_dir = get_package_paths("onnxruntime")
    datas += collect_data_files("onnxruntime", include_py_files=True)
    binaries += collect_dynamic_libs("onnxruntime")
    for native in Path(onnx_dir).rglob("*"):
        if native.is_file() and (native.suffix in (".pyd", ".so") or ".so." in native.name):
            target = str(Path("onnxruntime") / native.parent.relative_to(onnx_dir))
            binaries.append((str(native), target))
    hiddenimports += ["faster_whisper", "pyaudiowpatch",
                      "tokenizers", "huggingface_hub", "flatbuffers", "packaging", "wave"]
if find_spec("ctranslate2") is not None:
    datas += collect_data_files("ctranslate2")
    binaries += collect_dynamic_libs("ctranslate2")
    hiddenimports += collect_submodules(
        "ctranslate2",
        filter=lambda name: not name.startswith(("ctranslate2.converters", "ctranslate2.specs")),
    )
    # PyInstaller's shared Windows DLL-probing subprocess crashes when it
    # imports SentencePiece after the large Torch/Qt package graph. Keep its
    # Python package as source data and collect native files explicitly, so
    # dependency scanning can inspect the PE files without importing it.
    _, sentencepiece_dir = get_package_paths("sentencepiece")
    datas += collect_data_files("sentencepiece", include_py_files=True)
    binaries += collect_dynamic_libs("sentencepiece")
    for pattern in ("*.pyd", "*.so"):
        binaries += [(str(path), "sentencepiece") for path in Path(sentencepiece_dir).glob(pattern)]
    for package in ("sacremoses",):
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
        "safetensors",
        "ctranslate2.converters",
        "ctranslate2.specs",
        "sentencepiece",  # shipped above as a raw package, not omitted
        "onnxruntime",  # shipped above as a raw package, not omitted
        "piper",  # avoids indirect ONNX imports in the DLL scanner
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
    name="GloSub-v1.2.0-Windows-x64",
)
