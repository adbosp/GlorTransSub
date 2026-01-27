"""
SmartTranslator (GOOGLE ONLY – REALTIME OCR SUBTITLE)

- Engine: Google Translate (deep-translator)
- Stateless
- Thread-safe
- LRU cache (~100MB)
- Optimized for realtime OCR subtitle
"""

import os
import re
import sys
from functools import lru_cache
from threading import Lock

# ===================== ENV =====================
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# ===================== GOOGLE =====================
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None

# ===================== CONFIG =====================
MAX_CACHE_SIZE = 30000  # ~80–100MB RAM

# ===================== INTERNAL =====================
_lock = Lock()
_translator_pool = {}

# force stdout flush (PyQt on Windows)
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass


# ===================== UTILS =====================
def normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


# ===================== ENGINE =====================
class GoogleEngine:
    name = "google"

    def __init__(self):
        if not GoogleTranslator:
            raise RuntimeError("GoogleTranslator not installed")

    def _get(self, src: str, tgt: str):
        key = f"{src}->{tgt}"
        if key not in _translator_pool:
            _translator_pool[key] = GoogleTranslator(
                source=src,
                target=tgt
            )
        return _translator_pool[key]

    def translate(self, text: str, src: str, tgt: str) -> str:
        try:
            return self._get(src, tgt).translate(text)
        except Exception:
            return ""


# ===================== CACHE =====================
@lru_cache(maxsize=MAX_CACHE_SIZE)
def _cached_translate(src: str, tgt: str, text: str) -> str:
    return SmartTranslator._engine.translate(text, src, tgt)


# ===================== PUBLIC API =====================
class SmartTranslator:
    """
    Used by OCRWorker
    translate(text, src, tgt) -> str
    """

    _engine = None

    def __init__(self):
        with _lock:
            if SmartTranslator._engine:
                return

            print("\n========== SmartTranslator INIT ==========")

            SmartTranslator._engine = GoogleEngine()
            print("[Google] ✅ Available")

            print("========== Translator READY ==========\n")

    def translate(self, text: str, src: str = "auto", tgt: str = "vi") -> str:
        if not text:
            return ""

        text = normalize_text(text)
        if len(text) < 2:
            return ""

        try:
            return _cached_translate(src, tgt, text) or ""
        except Exception as e:
            print("[Translator ERROR]", e)
            return ""


# ===================== OPTIONAL =====================
def clear_translation_cache():
    _cached_translate.cache_clear()
    print("[CACHE] Cleared")
