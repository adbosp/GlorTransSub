"""Automatically install the CUDA PyTorch runtime on supported NVIDIA PCs."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time


RETRY_AFTER_SECONDS = 6 * 60 * 60


def _app_data_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.dirname(__file__)
    path = os.path.join(base, "GloSub")
    os.makedirs(path, exist_ok=True)
    return path


def _nvidia_gpu_available():
    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        system_smi = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"),
            "System32",
            "nvidia-smi.exe",
        )
        nvidia_smi = system_smi if os.path.isfile(system_smi) else None
    if not nvidia_smi:
        return False
    try:
        result = subprocess.run(
            [nvidia_smi, "-L"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0 and "GPU" in result.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def _torch_has_cuda_build():
    spec = importlib.util.find_spec("torch")
    if spec is None or not spec.submodule_search_locations:
        return False
    version_file = os.path.join(spec.submodule_search_locations[0], "version.py")
    try:
        with open(version_file, "r", encoding="utf-8") as handle:
            version_source = handle.read()
        return "+cu" in version_source and "cuda: Optional[str] = None" not in version_source
    except OSError:
        return False


def _recent_failure():
    state_path = os.path.join(_app_data_dir(), "gpu-setup-state.json")
    try:
        with open(state_path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
        return time.time() - float(state.get("failed_at", 0)) < RETRY_AFTER_SECONDS
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def _record_failure(message):
    state_path = os.path.join(_app_data_dir(), "gpu-setup-state.json")
    try:
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump({"failed_at": time.time(), "message": message[-1000:]}, handle)
    except OSError:
        pass


def _clear_failure():
    try:
        os.remove(os.path.join(_app_data_dir(), "gpu-setup-state.json"))
    except OSError:
        pass


def _pip_install_gpu_runtime():
    requirements = os.path.join(os.path.dirname(__file__), "requirements-gpu.txt")
    log_path = os.path.join(_app_data_dir(), "gpu-setup.log")
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-input",
        "--upgrade",
        "-r",
        requirements,
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = result.stdout or ""
    try:
        with open(log_path, "w", encoding="utf-8") as handle:
            handle.write(output)
    except OSError:
        pass
    return result.returncode == 0 and _torch_has_cuda_build(), output


def _install_with_progress():
    result = {"done": False, "success": False, "output": ""}

    def install():
        result["success"], result["output"] = _pip_install_gpu_runtime()
        result["done"] = True

    worker = threading.Thread(target=install, name="GpuRuntimeSetup", daemon=True)
    worker.start()

    try:
        import tkinter as tk
        from tkinter import ttk

        window = tk.Tk()
        window.title("GloSub Setup")
        window.geometry("460x150")
        window.resizable(False, False)
        window.attributes("-topmost", True)
        frame = ttk.Frame(window, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Installing NVIDIA GPU acceleration…", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(frame, text="This runs once. GloSub will open automatically when finished.").pack(anchor="w", pady=(8, 14))
        progress = ttk.Progressbar(frame, mode="indeterminate")
        progress.pack(fill="x")
        progress.start(12)

        def poll():
            if result["done"]:
                window.destroy()
            else:
                window.after(250, poll)

        window.protocol("WM_DELETE_WINDOW", lambda: None)
        window.after(250, poll)
        window.mainloop()
    except Exception:
        worker.join()

    worker.join()
    return result["success"], result["output"]


def ensure_gpu_runtime():
    """Install CUDA wheels once when NVIDIA hardware is present."""
    # A frozen PyInstaller executable already contains its Python runtime and
    # packages. Running ``GloSub.exe -m pip`` cannot modify that bundle, so the
    # portable release uses its bundled CPU PyTorch runtime on every PC.
    if getattr(sys, "frozen", False):
        return False
    if os.name != "nt" or not _nvidia_gpu_available() or _torch_has_cuda_build():
        return False
    if _recent_failure():
        return False

    success, output = _install_with_progress()
    if success:
        _clear_failure()
        return True

    _record_failure(output or "Unknown pip installation failure")
    return False
