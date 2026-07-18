"""Load PyTorch's Windows DLL chain before other frozen runtime hooks."""

import ctypes
import os
import sys


if sys.platform == "win32" and getattr(sys, "frozen", False):
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    torch_lib = os.path.join(sys._MEIPASS, "torch", "lib")
    if os.path.isdir(torch_lib):
        os.add_dll_directory(torch_lib)
        os.environ["PATH"] = torch_lib + os.pathsep + os.environ.get("PATH", "")
        for dll_name in ("libiomp5md.dll", "uv.dll", "c10.dll"):
            ctypes.WinDLL(os.path.join(torch_lib, dll_name), winmode=0)
