import sys
import os
import ctypes
import json
import shutil
import time
import hashlib
import math
import asyncio
import queue
import tempfile
from collections import deque
from contextlib import closing

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass
# ====================== SINGLE INSTANCE ======================
_single_instance_handle = None


def acquire_single_instance():
    """Return False when another GloSub process already owns the mutex."""
    global _single_instance_handle
    if os.name != "nt":
        return True

    mutex_name = "Local\\GloSub.SingleInstance.1.0"
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, mutex_name)
    if not handle:
        return True

    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        try:
            message_box_timeout = ctypes.windll.user32.MessageBoxTimeoutW
            message_box_timeout(
                None,
                "GloSub is already running in the system tray.",
                "GloSub",
                0x40,
                0,
                2500,
            )
        except Exception:
            pass
        return False

    _single_instance_handle = handle
    return True


def release_single_instance():
    global _single_instance_handle
    if os.name == "nt" and _single_instance_handle:
        try:
            ctypes.windll.kernel32.CloseHandle(_single_instance_handle)
        except Exception:
            pass
        _single_instance_handle = None


if __name__ == "__main__" and "--self-test" not in sys.argv and not acquire_single_instance():
    sys.exit(0)

# PyTorch must load its Windows DLLs before PyQt5. With current releases,
# importing Qt first can make c10.dll fail with WinError 1114.
from gpu_bootstrap import ensure_gpu_runtime
if __name__ == "__main__" and "--self-test" not in sys.argv:
    ensure_gpu_runtime()
import torch
from pynput import mouse
import re
import numpy as np
from PyQt5 import QtWidgets, QtGui, QtCore
from PIL import ImageGrab
from smart_translator import AI_PROVIDERS, SmartTranslator, test_provider
import smart_translator
from secret_store import protect_secret, unprotect_secret
from tts_engines import TTS_PROVIDERS, TTSEngine, test_tts_provider
from win_hotkey import WinHotkey
import threading
import winreg
try:
    import cv2
except Exception:
    cv2 = None

# ====================== SYSTEM LANGUAGE ======================
import locale


def resource_path(relative_path):
    """Return a bundled resource path in source and PyInstaller builds."""
    base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, relative_path)


def config_path():
    """Keep release configuration in a writable per-user location."""
    if getattr(sys, "frozen", False):
        config_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "GloSub"
        )
        os.makedirs(config_dir, exist_ok=True)
        target = os.path.join(config_dir, "subtitle_config.json")
        bundled_default = resource_path("subtitle_config.json")
        if not os.path.exists(target) and os.path.isfile(bundled_default):
            try:
                shutil.copyfile(bundled_default, target)
            except OSError:
                pass
        return target
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "subtitle_config.json")

def get_system_language():
    try:
        lang, _ = locale.getdefaultlocale()
        if not lang:
            return "en"
        return lang.split("_")[0].lower()
    except Exception:
        return "en"
def get_default_translate_target():
    region = get_system_language()
    return REGION_TO_TRANSLATE_TARGET.get(region, "en")
# ====================== APP THEME ======================
def build_app_stylesheet(theme="dark"):
    light = theme == "light"
    asset_dir = resource_path("assets").replace("\\", "/")
    arrow_down = f"{asset_dir}/chevron-down.svg"
    arrow_up = f"{asset_dir}/chevron-up.svg"
    colors = {
        "window": "#f4f7fb" if light else "#16181d",
        "surface": "#ffffff" if light else "#202329",
        "surface_hover": "#eef3fa" if light else "#2b3038",
        "input": "#ffffff" if light else "#292d34",
        "text": "#172033" if light else "#f2f4f8",
        "muted": "#667085" if light else "#a8b0bd",
        "border": "#d8e0eb" if light else "#363c46",
        "accent": "#2563eb" if light else "#4f8cff",
        "accent_hover": "#1d4ed8" if light else "#70a2ff",
        "track": "#dbe3ee" if light else "#343a44",
        "scroll": "#aab7c8" if light else "#596273",
    }
    return f"""
    QWidget {{
        background-color: {colors['window']};
        color: {colors['text']};
        font-family: "Segoe UI", Arial;
        font-size: 13px;
    }}
    QLabel, QCheckBox, QRadioButton {{ background-color: transparent; }}
    QWidget#settingsTitleBar {{
        background-color: {colors['surface']};
        border: 1px solid {colors['border']};
        border-radius: 14px;
    }}
    QLabel {{ color: {colors['text']}; }}
    QLabel#sectionTitle {{
        color: {colors['text']};
        font-size: 15px;
        font-weight: 600;
    }}
    QLabel#fieldLabel, QLabel#helpText {{ color: {colors['muted']}; }}
    QLabel#accentLabel {{ color: {colors['accent']}; }}
    QFrame#settingsCard {{
        background-color: {colors['surface']};
        border: 1px solid {colors['border']};
        border-radius: 14px;
    }}
    QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QComboBox {{
        background-color: {colors['input']};
        color: {colors['text']};
        border: 1px solid {colors['border']};
        border-radius: 10px;
        padding: 7px 10px;
        selection-background-color: {colors['accent']};
    }}
    QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus,
    QSpinBox:focus, QComboBox:focus {{ border: 1px solid {colors['accent']}; }}
    QComboBox QAbstractItemView {{
        background-color: {colors['input']};
        color: {colors['text']};
        border: 1px solid {colors['border']};
        selection-background-color: {colors['accent']};
        padding: 5px;
    }}
    QComboBox QAbstractItemView::item {{ min-height: 30px; }}
    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 30px;
        background: transparent;
        border: none;
        border-top-right-radius: 10px;
        border-bottom-right-radius: 10px;
    }}
    QComboBox::down-arrow {{
        image: url("{arrow_down}");
        width: 12px;
        height: 12px;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        subcontrol-origin: border;
        width: 26px;
        background: transparent;
        border: none;
    }}
    QSpinBox::up-button {{
        subcontrol-position: top right;
        border-top-right-radius: 10px;
    }}
    QSpinBox::down-button {{
        subcontrol-position: bottom right;
        border-bottom-right-radius: 10px;
    }}
    QSpinBox::up-arrow {{
        image: url("{arrow_up}");
        width: 10px;
        height: 10px;
    }}
    QSpinBox::down-arrow {{
        image: url("{arrow_down}");
        width: 10px;
        height: 10px;
    }}
    QPushButton {{
        background-color: {colors['surface']};
        color: {colors['text']};
        border: 1px solid {colors['border']};
        border-radius: 10px;
        padding: 9px 16px;
    }}
    QPushButton:hover {{ background-color: {colors['surface_hover']}; }}
    QPushButton:checked {{
        color: white;
        background-color: {colors['accent']};
        border-color: {colors['accent']};
    }}
    QPushButton#closeButton {{
        background: transparent;
        color: #ef4444;
        border: none;
        padding: 0;
        font-size: 16px;
    }}
    QPushButton#closeButton:hover {{ background-color: {colors['surface_hover']}; }}
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; }}
    QTabWidget::pane {{ border: none; background: transparent; top: -1px; }}
    QTabBar {{ background: transparent; }}
    QTabBar::tab {{
        background: transparent;
        color: {colors['muted']};
        border: none;
        border-bottom: 2px solid transparent;
        min-width: 78px;
        padding: 11px 16px 12px 16px;
        margin: 0 3px;
        font-family: "Segoe UI Semibold", "Segoe UI", Arial;
        font-size: 14px;
        font-weight: normal;
    }}
    QTabBar::tab:selected {{
        color: {colors['accent']};
        border-bottom-color: {colors['accent']};
    }}
    QTabBar::tab:hover {{ color: {colors['text']}; }}
    QSlider {{ min-height: 26px; }}
    QSlider::groove:horizontal {{
        height: 7px;
        background: {colors['track']};
        border-radius: 3px;
    }}
    QSlider::handle:horizontal {{
        background: {colors['accent']};
        width: 18px;
        height: 18px;
        margin: -6px 0;
        border-radius: 9px;
    }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 2px; }}
    QScrollBar::handle:vertical {{ background: {colors['scroll']}; border-radius: 5px; min-height: 28px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QToolTip {{
        background-color: {colors['surface']};
        color: {colors['text']};
        border: 1px solid {colors['border']};
        padding: 5px;
    }}
    """


def apply_ui_theme(theme):
    normalized = "light" if theme == "light" else "dark"
    app = QtWidgets.QApplication.instance()
    if app is not None:
        app.setStyleSheet(build_app_stylesheet(normalized))


def virtual_desktop_geometry():
    """Return the union of every monitor in global desktop coordinates."""
    screens = QtWidgets.QApplication.screens()
    if not screens:
        return QtCore.QRect(0, 0, 1920, 1080)
    geometry = QtCore.QRect(screens[0].geometry())
    for screen in screens[1:]:
        geometry = geometry.united(screen.geometry())
    return geometry


def screen_geometry_at(x, y):
    point = QtCore.QPoint(int(x), int(y))
    screen = QtWidgets.QApplication.screenAt(point)
    if screen is None:
        screen = QtWidgets.QApplication.primaryScreen()
    return QtCore.QRect(screen.geometry()) if screen else virtual_desktop_geometry()


def screen_geometry_for_region(region):
    left, top, right, bottom = region
    return screen_geometry_at((left + right) // 2, (top + bottom) // 2)


def mouse_capture_geometry(x, y, width, height):
    """Keep the Mouse OCR rectangle fully inside the monitor under the cursor."""
    screen = screen_geometry_at(x, y)
    width = min(int(width), screen.width())
    height = min(int(height), screen.height())
    left = int(x) - width // 2
    top = int(y) - height // 2
    left = max(screen.left(), min(left, screen.right() - width + 1))
    top = max(screen.top(), min(top, screen.bottom() - height + 1))
    return QtCore.QRect(left, top, width, height)
TRANSLATE_LANGUAGES = {
    "auto": "Auto Detect",

    # Popular
    "en": "English",
    "vi": "Vietnamese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",

    # European
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "ru": "Russian",
    "pl": "Polish",
    "tr": "Turkish",
    "uk": "Ukrainian",

    # Middle East / South Asia
    "ar": "Arabic",
    "fa": "Persian",
    "hi": "Hindi",
    "ur": "Urdu",

    # Others
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "cs": "Czech",
    "el": "Greek",
    "he": "Hebrew",
    "ro": "Romanian",
    "hu": "Hungarian",
}

# EasyOCR and translation providers use different language codes for a few
# languages. The UI exposes one input language and this map configures both
# stages consistently.
OCR_TO_TRANSLATE_LANGUAGE = {
    "en": "en", "vi": "vi", "ja": "ja", "ko": "ko",
    "ch_sim": "zh-cn", "ch_tra": "zh-tw", "th": "th",
    "id": "id", "ms": "ms", "fr": "fr", "de": "de",
    "es": "es", "pt": "pt", "it": "it", "nl": "nl",
    "ru": "ru", "pl": "pl", "tr": "tr", "uk": "uk",
    "ar": "ar", "fa": "fa", "hi": "hi", "ur": "ur",
    "sv": "sv", "no": "no", "da": "da", "fi": "fi",
    "cs": "cs", "el": "el", "he": "he", "ro": "ro",
    "hu": "hu",
}

INPUT_LANGUAGE_LABELS = {
    ocr_code: TRANSLATE_LANGUAGES[translate_code]
    for ocr_code, translate_code in OCR_TO_TRANSLATE_LANGUAGE.items()
}

VOICE_OPTIONS = {
    "vi-VN": {
        "label": "Vietnamese",
        "voices": [("HoaiMy (Female)", "vi-VN-HoaiMyNeural"), ("NamMinh (Male)", "vi-VN-NamMinhNeural")],
    },
    "en-US": {
        "label": "English (US)",
        "voices": [("Aria (Female)", "en-US-AriaNeural"), ("Guy (Male)", "en-US-GuyNeural")],
    },
    "ja-JP": {
        "label": "Japanese",
        "voices": [("Nanami (Female)", "ja-JP-NanamiNeural"), ("Keita (Male)", "ja-JP-KeitaNeural")],
    },
    "ko-KR": {
        "label": "Korean",
        "voices": [("SunHi (Female)", "ko-KR-SunHiNeural"), ("InJoon (Male)", "ko-KR-InJoonNeural")],
    },
    "zh-CN": {
        "label": "Chinese (Simplified)",
        "voices": [("Xiaoxiao (Female)", "zh-CN-XiaoxiaoNeural"), ("Yunxi (Male)", "zh-CN-YunxiNeural")],
    },
    "zh-TW": {
        "label": "Chinese (Traditional)",
        "voices": [("HsiaoChen (Female)", "zh-TW-HsiaoChenNeural"), ("YunJhe (Male)", "zh-TW-YunJheNeural")],
    },
    "th-TH": {
        "label": "Thai",
        "voices": [("Premwadee (Female)", "th-TH-PremwadeeNeural"), ("Niwat (Male)", "th-TH-NiwatNeural")],
    },
    "id-ID": {
        "label": "Indonesian",
        "voices": [("Gadis (Female)", "id-ID-GadisNeural"), ("Ardi (Male)", "id-ID-ArdiNeural")],
    },
    "fr-FR": {
        "label": "French",
        "voices": [("Denise (Female)", "fr-FR-DeniseNeural"), ("Henri (Male)", "fr-FR-HenriNeural")],
    },
    "de-DE": {
        "label": "German",
        "voices": [("Katja (Female)", "de-DE-KatjaNeural"), ("Conrad (Male)", "de-DE-ConradNeural")],
    },
    "es-ES": {
        "label": "Spanish",
        "voices": [("Elvira (Female)", "es-ES-ElviraNeural"), ("Alvaro (Male)", "es-ES-AlvaroNeural")],
    },
    "pt-BR": {
        "label": "Portuguese (Brazil)",
        "voices": [("Francisca (Female)", "pt-BR-FranciscaNeural"), ("Antonio (Male)", "pt-BR-AntonioNeural")],
    },
    "ru-RU": {
        "label": "Russian",
        "voices": [("Svetlana (Female)", "ru-RU-SvetlanaNeural"), ("Dmitry (Male)", "ru-RU-DmitryNeural")],
    },
}

VOICE_LANGUAGE_BY_TRANSLATE_TARGET = {
    "vi": "vi-VN",
    "en": "en-US",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
    "th": "th-TH",
    "id": "id-ID",
    "fr": "fr-FR",
    "de": "de-DE",
    "es": "es-ES",
    "pt": "pt-BR",
    "ru": "ru-RU",
}

GAME_RULES_EXAMPLE = """[Speaker: Ethan -> Lisa]
I = Con
You = Mẹ

[Speaker: Ethan -> John]
I = tôi
You = anh

[Speaker: Lisa -> John]
I = tôi
You = ông

[Speaker: Ethan]
I = tôi
You = bạn"""
# ===== DEFAULT TARGET BY REGION =====
REGION_TO_TRANSLATE_TARGET = {
    "vi": "vi",
    "ja": "ja",
    "ko": "ko",
    "zh": "zh-cn",
    "th": "th",
    "id": "id",
    "ms": "ms",

    # fallback phổ biến
    "en": "en",
    "fr": "fr",
    "de": "de",
    "es": "es",
}
# ====================== INTERNATIONALIZATION (I18N) ======================

from ctypes import windll
def on_mouse_move(x, y):
    global mouse_pos, mouse_last_move_time, mouse_idle_triggered

    if not MOUSE_FOLLOW_ACTIVE:
        return

    mouse_pos = (x, y)
    mouse_last_move_time = time.time()

    if mouse_idle_triggered:
        mouse_idle_triggered = False
        print("[MOUSE] moved again → idle reset")


def on_hold_key_down():
    global MOUSE_FOLLOW_ACTIVE
    if MOUSE_MODE != "hold":
        return
    MOUSE_FOLLOW_ACTIVE = True
    print("[MOUSE] HOLD → FOLLOW ON")

def on_hold_key_up():
    global MOUSE_FOLLOW_ACTIVE
    if MOUSE_MODE != "hold":
        return

    MOUSE_FOLLOW_ACTIVE = False
    print("[MOUSE] HOLD → FOLLOW OFF")

    QtCore.QTimer.singleShot(0, restore_main_subtitle_overlay)
    QtCore.QTimer.singleShot(0, mouse_ocr_preview.hide)
    
def tr(key: str) -> str:
    lang = cfg.get("ui_lang") or get_system_language()

    if lang not in I18N:
        lang = "en"

    if "en" not in I18N:
        return key  # fail-safe

    return I18N.get(lang, {}).get(
        key,
        I18N["en"].get(key, key)
    )





    
# ====== CONFIG & PATH ======
CAPTURE_FPS = 3
CONFIG_FILE = config_path()
APP_NAME = "GloSub"
# default regions (left, top, right, bottom)
DEFAULT_RED_REGION = (0, 900, 1920, 1080)
DEFAULT_YELLOW_REGION = (0, 800, 1920, 900)
SETTINGS_SNAPSHOT = None

# ====== OCR ENGINE ======
def set_run_on_startup(enable: bool):
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Run",
        0,
        winreg.KEY_SET_VALUE
    )
    exe_path = sys.executable
    if getattr(sys, "frozen", False):
        startup_command = f'"{exe_path}"'
    else:
        python_dir = os.path.dirname(exe_path)
        pythonw_path = os.path.join(python_dir, "pythonw.exe")
        launcher = os.path.abspath(__file__)
        startup_command = (
            f'"{pythonw_path if os.path.isfile(pythonw_path) else exe_path}" '
            f'"{launcher}"'
        )
    if enable:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, startup_command)
    else:
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
    key.Close()
    
def is_run_on_startup() -> bool:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_READ
        )
        winreg.QueryValueEx(key, APP_NAME)
        key.Close()
        return True
    except FileNotFoundError:
        return False
    
def toggle_ocr_and_subtitle():
    global worker, overlay, voice_speaker

    if worker is None or overlay is None:
        return

    worker.toggle()

    if worker.running:
        try:
            translator.resume()
        except Exception:
            pass
        if voice_speaker is not None:
            voice_speaker.resume_pending()
        if cfg.get("settings", {}).get("main_subtitle_enabled", True):
            overlay.reset_to_base_region()
            overlay.show()
            overlay.raise_()
            overlay.update()
        else:
            overlay.update_text("")
            overlay.hide()
    else:
        try:
            translator.pause()
        except Exception:
            pass
        if voice_speaker is not None:
            voice_speaker.cancel_pending()
        overlay.reset_to_base_region()
        overlay.update_text("")
        overlay.hide()
        mouse_ocr_preview.hide()


def restore_main_subtitle_overlay():
    if overlay is None:
        return
    overlay.reset_to_base_region()
    enabled = cfg.get("settings", {}).get("main_subtitle_enabled", True)
    if enabled and worker is not None and worker.running:
        overlay.show()
        overlay.raise_()
    else:
        overlay.update_text("")
        overlay.hide()

        
def should_follow_mouse() -> bool:
    """
    🔥 SINGLE DECISION POINT
    """
    if MOUSE_MODE == "hold":
        if not is_mouse_hold_key_pressed():
            return False
        
    if not MOUSE_OCR_ENABLED:
        return False

    if not MOUSE_FOLLOW_ACTIVE:
        return False

    if mouse_pos is None:
        return False

    idle_time = time.time() - mouse_last_move_time
    return idle_time >= MOUSE_OCR_DELAY
from ctypes import windll

SPECIAL_KEY_VKS = {
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "win": 0x5B,
    "space": 0x20,
    "tab": 0x09,
    "enter": 0x0D,
    "esc": 0x1B,
    "backspace": 0x08,
    "capslock": 0x14,
    "insert": 0x2D,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
}


def key_token_to_vk(token):
    token = (token or "").strip().lower()
    if token in SPECIAL_KEY_VKS:
        return SPECIAL_KEY_VKS[token]
    function_match = re.fullmatch(r"f([1-9]|1[0-2])", token)
    if function_match:
        return 0x70 + int(function_match.group(1)) - 1
    if len(token) == 1 and token.isascii() and token.isalnum():
        return ord(token.upper())
    return None


def is_mouse_hold_key_pressed():
    key_tokens = [part for part in MOUSE_HOLD_KEY.lower().split("+") if part]
    virtual_keys = [key_token_to_vk(token) for token in key_tokens]
    if not virtual_keys or any(vk is None for vk in virtual_keys):
        return False
    return all(windll.user32.GetAsyncKeyState(vk) & 0x8000 for vk in virtual_keys)


# ====================== MOUSE HOLD KEY STATE TRACK ======================
def update_mouse_hold_state():
    global MOUSE_FOLLOW_ACTIVE, mouse_pos, mouse_last_move_time, mouse_idle_triggered

    if MOUSE_MODE != "hold":
        return

    if is_mouse_hold_key_pressed():
        if not MOUSE_FOLLOW_ACTIVE:
            MOUSE_FOLLOW_ACTIVE = True
            print(f"[MOUSE] {MOUSE_HOLD_KEY.upper()} DOWN → FOLLOW ON")

        cursor_pos = QtGui.QCursor.pos()
        current_pos = (cursor_pos.x(), cursor_pos.y())
        if current_pos != mouse_pos:
            mouse_pos = current_pos
            mouse_last_move_time = time.time()
            mouse_idle_triggered = False

        if MOUSE_OCR_ENABLED:
            mouse_ocr_preview.show_at(
                current_pos[0], current_pos[1], MOUSE_OCR_WIDTH, MOUSE_OCR_HEIGHT
            )
    else:
        if MOUSE_FOLLOW_ACTIVE:
            MOUSE_FOLLOW_ACTIVE = False
            print(f"[MOUSE] {MOUSE_HOLD_KEY.upper()} UP → FOLLOW OFF")

            QtCore.QTimer.singleShot(0, restore_main_subtitle_overlay)
            QtCore.QTimer.singleShot(0, mouse_ocr_preview.hide)


def frame_hash(img: np.ndarray) -> str:
    return hashlib.md5(img.tobytes()).hexdigest()


def normalize_text(text: str) -> str:
    # lowercase and remove punctuation for caching/normalization
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def strip_mouse_preview_artifacts(text, width, height):
    """Remove only the guide overlay's own labels from Mouse OCR output."""
    cleaned = text or ""
    cleaned = re.sub(
        r"\bOCR\s*\+?\s*TRANSL(?:ATE|ATION)\s+AREA\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        rf"\b{int(width)}\s*[x×]\s*{int(height)}\s*(?:px)?\b",
        " ",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" \t\r\n+|-")


def parse_context_dictionary(raw_text: str) -> dict:
    """Parse one `source = preferred translation` glossary entry per line."""
    entries = {}
    for raw_line in (raw_text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        source, target = (part.strip() for part in line.split("=", 1))
        if source and target:
            entries[source] = target
    return entries


def parse_game_dialogue_rules(raw_text: str) -> dict:
    """Parse speaker-aware rules grouped by `[Speaker: Name -> Listener]`."""
    rules = {}
    current_key = None
    header_pattern = re.compile(
        r"^\[\s*Speaker\s*:\s*([^\]-]+?)\s*(?:->\s*([^\]]+?))?\s*\]$",
        re.IGNORECASE,
    )
    for raw_line in (raw_text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        header = header_pattern.match(line)
        if header:
            speaker = header.group(1).strip().casefold()
            listener = (header.group(2) or "*").strip().casefold()
            current_key = (speaker, listener)
            rules.setdefault(current_key, {})
            continue
        if current_key and "=" in line:
            source, target = (part.strip() for part in line.split("=", 1))
            if source and target:
                rules[current_key][source] = target
    return rules

def init_ocr_reader(lang="en"):
    global reader, reader_language, OCR_DEVICE_STATUS

    if reader is not None and reader_language == lang:
        return

    import easyocr

    # EasyOCR uses a shared temp.zip while downloading recognition models. A
    # previous interrupted Chinese download otherwise leaves the language
    # permanently unusable on the next attempt.
    if lang in ("ch_sim", "ch_tra"):
        stale_download = os.path.join(
            os.path.expanduser("~"), ".EasyOCR", "model", "temp.zip"
        )
        try:
            os.remove(stale_download)
        except OSError:
            pass

    reader_options = {}
    if getattr(sys, "frozen", False) and lang == "en":
        bundled_ocr = os.path.join(os.path.dirname(sys.executable), "models", "easyocr")
        if os.path.isdir(bundled_ocr):
            reader_options["model_storage_directory"] = bundled_ocr

    use_gpu = bool(torch.cuda.is_available())
    if use_gpu:
        gpu_name = torch.cuda.get_device_name(0)
        OCR_DEVICE_STATUS = f"GPU · {gpu_name}"
        print(f"[OCR] Auto device: {OCR_DEVICE_STATUS}")
        try:
            # Catch driver/runtime problems before loading the larger OCR model.
            torch.empty(1, device="cuda")
            new_reader = easyocr.Reader([lang], gpu=True, verbose=False, **reader_options)
        except Exception as exc:
            print(f"[OCR] GPU failed, falling back to CPU: {exc}")
            OCR_DEVICE_STATUS = "CPU · GPU fallback"
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass
            new_reader = easyocr.Reader([lang], gpu=False, verbose=False, **reader_options)
    else:
        reason = "CUDA runtime unavailable"
        if torch.version.cuda is None:
            reason = "CPU PyTorch / no CUDA"
        OCR_DEVICE_STATUS = f"CPU · {reason}"
        print(f"[OCR] Auto device: {OCR_DEVICE_STATUS}")
        new_reader = easyocr.Reader([lang], gpu=False, verbose=False, **reader_options)

    reader = new_reader
    reader_language = lang

# ====================== I18N LOAD ======================
I18N = {}

def load_i18n():
    global I18N
    try:
        path = resource_path("i18n.json")
        with open(path, "r", encoding="utf-8") as f:
            I18N = json.load(f)
        print("[I18N] Loaded languages:", list(I18N.keys()))
    except Exception as e:
        print("[I18N ERROR] Failed to load i18n.json:", e)
        I18N = {}
        
# ====================== Helpers: config load/save ======================
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
                return cfg
        except Exception as e:
            print("[OCR ERROR]", e) 
    # default config
    return {
        "ui_lang": get_system_language(),
        "translate_source": "auto",
        "translate_target": get_default_translate_target(),
        "translate_engine": "google",
        "ai_api_keys": {},
        "ai_models": {
            provider: details["model"] for provider, details in AI_PROVIDERS.items()
        },
        "tts_profiles": {
            provider: {"model": details.get("model", ""), "voice": details.get("voice", "")}
            for provider, details in TTS_PROVIDERS.items()
        },
        "tts_secrets": {},
        "red_region": DEFAULT_RED_REGION,
        "yellow_region": DEFAULT_YELLOW_REGION,
        "settings": {
            "font_size": 28,
            "mouse_font_size": 22,   # font size cho mouse subtitle
            "bg_alpha": 150,
            "bg_color": [0, 0, 0],
            "font_color": [255, 255, 255],
            "style": "centered",
            "shadow_color": [0, 0, 0],
            "shadow_alpha": 200,
            "shadow_offset": 4,
            "stroke_width": 4,
            "hotkey_pause": "F8",
            "hotkey_settings": "F10",
            "font_weight": 75,
            "mouse_hold_key": "ctrl",
            "mouse_ocr_enabled": True,
            "mouse_ocr_width": 300,
            "mouse_ocr_height": 300,
            "main_subtitle_enabled": True,
            "outline_color": [0, 0, 0],
            "voice_enabled": False,
            "tts_provider": "edge",
            "voice_language": "vi-VN",
            "voice": "vi-VN-HoaiMyNeural",
            "voice_mode": "smart",
            "context_enabled": False,
            "context_mode": "video",
            "context_memory_size": 10,
            "context_dictionary": "",
            "context_game_rules": "",
            "ui_theme": "dark"
        }
    }


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


cfg = load_config()
MOUSE_OCR_ENABLED = cfg.get("settings", {}).get("mouse_ocr_enabled", False)
# ===== Load mouse hold key from config =====
MOUSE_HOLD_KEY = cfg.get("settings", {}).get("mouse_hold_key", "ctrl")
# ===== Load regions from config =====
RED_REGION = tuple(cfg.get("red_region", DEFAULT_RED_REGION))
YELLOW_REGION = tuple(cfg.get("yellow_region", DEFAULT_YELLOW_REGION))
_last_toggle_time = 0

# ensure language settings exist in config
if "ocr_lang" not in cfg:
    cfg["ocr_lang"] = "en"
if "translate_source" not in cfg:
    cfg["translate_source"] = "auto"
if cfg.get("translate_target") in (None, "auto"):
    cfg["translate_target"] = get_default_translate_target()
if "translate_engine" not in cfg:
    cfg["translate_engine"] = "google"
if getattr(sys, "frozen", False):
    bundled_models = os.path.join(os.path.dirname(sys.executable), "models")
    bundled_opus = os.path.join(bundled_models, "opus-en-vi")
    if not cfg.get("opus_mt_model_dir") and os.path.isfile(os.path.join(bundled_opus, "glosub-opus.json")):
        cfg["opus_mt_model_dir"] = bundled_opus
if not isinstance(cfg.get("ai_api_keys"), dict):
    cfg["ai_api_keys"] = {}
if not isinstance(cfg.get("ai_models"), dict):
    cfg["ai_models"] = {}
for provider, details in AI_PROVIDERS.items():
    cfg["ai_models"].setdefault(provider, details["model"])
if not isinstance(cfg.get("tts_profiles"), dict):
    cfg["tts_profiles"] = {}
if not isinstance(cfg.get("tts_secrets"), dict):
    cfg["tts_secrets"] = {}
for provider, details in TTS_PROVIDERS.items():
    profile = cfg["tts_profiles"].setdefault(provider, {})
    profile.setdefault("model", details.get("model", ""))
    profile.setdefault("voice", details.get("voice", ""))
if "hotkey_pause" not in cfg:
    cfg["hotkey_pause"] = "F8"
if "hotkey_settings" not in cfg:
    cfg["hotkey_settings"] = "F10"

# Input language is the single source of truth for both OCR and translation.
cfg["translate_source"] = OCR_TO_TRANSLATE_LANGUAGE.get(cfg["ocr_lang"], "en")


def get_ai_api_key(provider, config=None):
    """Read a DPAPI-protected key, falling back to the provider env variable."""
    config = config or cfg
    protected = config.get("ai_api_keys", {}).get(provider, "")
    try:
        key = unprotect_secret(protected)
    except Exception as exc:
        print(f"[AI Key] Could not decrypt {provider}: {exc}")
        key = ""
    return key or os.getenv(AI_PROVIDERS.get(provider, {}).get("env", ""), "")


def configure_translator(config=None):
    config = config or cfg
    engine = config.get("translate_engine", "google")
    if engine == "opus_mt":
        translator.configure("opus_mt", model=config.get("opus_mt_model_dir", ""))
        return
    if engine not in AI_PROVIDERS:
        translator.configure("google")
        return
    model = config.get("ai_models", {}).get(engine, AI_PROVIDERS[engine]["model"])
    translator.configure(engine, get_ai_api_key(engine, config), model)


def get_tts_secret_fields(provider, config=None):
    config = config or cfg
    result = {}
    saved = config.get("tts_secrets", {}).get(provider, {})
    for key, _label, is_secret in TTS_PROVIDERS.get(provider, {}).get("fields", []):
        if not is_secret:
            continue
        try:
            result[key] = unprotect_secret(saved.get(key, ""))
        except Exception as exc:
            print(f"[TTS Secret] Could not decrypt {provider}.{key}: {exc}")
            result[key] = ""
    return result


def get_tts_runtime_config(config=None):
    config = config or cfg
    provider = config.get("settings", {}).get("tts_provider", "edge")
    if provider not in TTS_PROVIDERS:
        provider = "edge"
    profile = dict(config.get("tts_profiles", {}).get(provider, {}))
    fields = get_tts_secret_fields(provider, config)
    for key, _label, is_secret in TTS_PROVIDERS[provider].get("fields", []):
        if not is_secret:
            fields[key] = profile.get(key, "")
    return provider, profile, fields

# ====================== GLOBALS ======================
# initialize EasyOCR reader according to saved config
# ===== Edit Mode Snapshot =====
EDIT_SNAPSHOT_RED = None
EDIT_SNAPSHOT_YELLOW = None
# ===== Mouse Subtitle Position =====
MOUSE_SUBTITLE_OFFSET_X = 20   # lệch phải chuột (px)
MOUSE_SUBTITLE_OFFSET_Y = 30   # lệch xuống chuột (px)
# ===== Mouse Subtitle Font Tuning =====
MOUSE_SUBTITLE_FONT_DELTA = 6   # px (<=10 để không quá khác subtitle center)

mouse_subtitle_pos = None     # (x, y) vị trí hiển thị subtitle

# Loaded from config above; do not overwrite it during global initialization.
EDIT_MODE_ACTIVE = False


MOUSE_OCR_WIDTH = int(cfg.get("settings", {}).get("mouse_ocr_width", 300))
MOUSE_OCR_HEIGHT = int(cfg.get("settings", {}).get("mouse_ocr_height", 300))
MOUSE_OCR_DELAY = 0.1              # giây chuột đứng yên
# ===== Mouse Subtitle Mode =====
MOUSE_MODE = "hold"   # "hold" | "toggle"
MOUSE_FOLLOW_ACTIVE = False

mouse_pos = None
mouse_last_move_time = 0
mouse_hold_active = False
mouse_idle_triggered = False  # 🔥 BẮT BUỘC – cờ idle chuột


# ====================== Translator (initialized in main) ======================
translator = None
reader = None
reader_language = None
OCR_DEVICE_STATUS = "Detecting..."
voice_speaker = None
worker = None
current_hotkey = None
current_hotkey_subtitle = None
current_hotkey_settings = None
# ===== Mouse hook state (PREVENT DUPLICATE HOOK) =====
_mouse_hook_registered = False
# translator will be created in main() with safe fallback
# global OCR reader (initialized lazily in OCRWorker)
# track current hotkey to avoid duplicate registrations


def default_edge_voice(language):
    voices = VOICE_OPTIONS.get(language, {}).get("voices", [])
    return voices[0][1] if voices else "en-US-AriaNeural"


class VoiceSpeaker:
    """Generate speech with Smart subtitle stabilization by default."""

    CACHE_LIMIT = 64
    CACHE_SIZE_LIMIT = 50 * 1024 * 1024
    SYNTHESIS_WORKERS = 2
    QUEUE_LIMIT = 12
    SMART_STABILITY_DELAY = 0.4
    SMART_MAX_UNINTERRUPTED_SECONDS = 2.5

    def __init__(
        self,
        enabled=False,
        language="vi-VN",
        voice="vi-VN-HoaiMyNeural",
        mode="smart",
        provider="edge",
        model="",
        provider_fields=None,
    ):
        self.enabled = bool(enabled)
        self.language = language
        self.voice = voice
        self.provider = provider
        self.model = model
        self.provider_fields = dict(provider_fields or {})
        try:
            self._tts_engine = TTSEngine(
                provider, model, voice, language, self.provider_fields
            )
        except Exception as exc:
            print(f"[VOICE] {provider} configuration unavailable: {exc}; using Edge TTS")
            self.provider = "edge"
            self.model = ""
            self.voice = default_edge_voice(language)
            self._tts_engine = TTSEngine("edge", voice=self.voice, language=language)
        self.mode = mode if mode in ("smart", "latest", "queue") else "smart"
        self._generation = 0
        self._generation_lock = threading.Lock()
        self._smart_timer = None
        self._smart_timer_lock = threading.Lock()
        self._playback_state_lock = threading.Lock()
        self._playback_active = False
        self._playback_started_at = 0.0
        self._synthesis_queue = queue.Queue(maxsize=1)
        self._playback_queue = queue.Queue(maxsize=1)
        self._voice_queue = queue.Queue(maxsize=self.QUEUE_LIMIT)
        self._last_queued_text = ""
        self._stop_event = threading.Event()
        self._paused = threading.Event()
        self._cache_dir = os.path.join(tempfile.gettempdir(), "glosub-tts-cache")
        os.makedirs(self._cache_dir, exist_ok=True)

        self._start_lock = threading.Lock()
        self._synthesis_threads = []
        self._queue_thread = None
        self._playback_thread = None

    def _ensure_started(self):
        # Translation-only sessions should not create audio threads or open
        # the mixer. Start once, on the first actual spoken subtitle.
        with self._start_lock:
            if self._synthesis_threads or self._stop_event.is_set():
                return
            self._synthesis_threads = [
                threading.Thread(
                    target=self._synthesis_loop,
                    name=f"VoiceSynthesis-{index + 1}",
                    daemon=True,
                )
                for index in range(self.SYNTHESIS_WORKERS)
            ]
            for synthesis_thread in self._synthesis_threads:
                synthesis_thread.start()

            self._queue_thread = threading.Thread(
                target=self._queue_mode_loop,
                name="VoiceQueueSynthesis",
                daemon=True,
            )
            self._queue_thread.start()

            self._playback_thread = threading.Thread(
                target=self._playback_loop,
                name="VoicePlayback",
                daemon=True,
            )
            self._playback_thread.start()

    def configure(
        self, enabled, language, voice, mode="smart", provider="edge",
        model="", provider_fields=None
    ):
        engine = TTSEngine(provider, model, voice, language, provider_fields or {})
        self.enabled = bool(enabled)
        self.language = language
        self.voice = voice
        self.provider = provider
        self.model = model
        self.provider_fields = dict(provider_fields or {})
        self._tts_engine = engine
        self.mode = mode if mode in ("smart", "latest", "queue") else "smart"
        self._cancel_smart_timer()
        self._invalidate_current()
        self._clear_queue(self._synthesis_queue)
        self._clear_queue(self._playback_queue)
        self._clear_queue(self._voice_queue)
        self._last_queued_text = ""
        self._stop_playback()

    def speak(self, text):
        text = (text or "").strip()
        if not self.enabled or self._paused.is_set() or self._stop_event.is_set():
            return
        if text:
            self._ensure_started()

        if self.mode == "queue":
            if not text:
                self._last_queued_text = ""
                return
            if text == self._last_queued_text:
                return
            self._last_queued_text = text
            try:
                self._voice_queue.put_nowait((text, self._tts_engine))
            except queue.Full:
                # Bound latency: discard the oldest waiting subtitle rather
                # than allowing Queue mode to drift indefinitely.
                try:
                    self._voice_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._voice_queue.put_nowait((text, self._tts_engine))
                except queue.Full:
                    pass
            return

        # Invalidate synthesis for any subtitle that has already disappeared.
        generation = self._invalidate_current()
        self._clear_queue(self._synthesis_queue)
        self._clear_queue(self._playback_queue)
        self._cancel_smart_timer()
        if not text:
            return

        if self.mode == "smart":
            # Ignore text that only flashes briefly. Current audio may finish,
            # but long speech is interrupted so Voice cannot lag far behind.
            with self._playback_state_lock:
                playback_age = (
                    time.perf_counter() - self._playback_started_at
                    if self._playback_active else 0.0
                )
            if playback_age >= self.SMART_MAX_UNINTERRUPTED_SECONDS:
                self._stop_playback()
            timer = threading.Timer(
                self.SMART_STABILITY_DELAY,
                self._queue_synthesis,
                args=(generation, text, self._tts_engine),
            )
            timer.daemon = True
            with self._smart_timer_lock:
                self._smart_timer = timer
            timer.start()
            return

        # Latest mode interrupts immediately and always follows newest text.
        self._stop_playback()
        self._queue_synthesis(generation, text, self._tts_engine)

    def _queue_synthesis(self, generation, text, engine):
        if not self._is_current(generation):
            return
        try:
            self._synthesis_queue.put_nowait((generation, text, engine))
        except queue.Full:
            pass

    def _cancel_smart_timer(self):
        with self._smart_timer_lock:
            timer = self._smart_timer
            self._smart_timer = None
        if timer is not None:
            timer.cancel()

    def _invalidate_current(self):
        with self._generation_lock:
            self._generation += 1
            return self._generation

    def _is_current(self, generation):
        with self._generation_lock:
            return (
                generation == self._generation
                and self.enabled
                and not self._paused.is_set()
                and not self._stop_event.is_set()
            )

    @staticmethod
    def _clear_queue(target_queue):
        while True:
            try:
                target_queue.get_nowait()
            except queue.Empty:
                return

    @staticmethod
    def _stop_playback():
        try:
            pygame = sys.modules.get("pygame")
            if pygame is not None and pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass

    def _cache_path(self, text, engine):
        cache_key = hashlib.sha256(
            f"{engine.cache_key}\0{text}".encode("utf-8")
        ).hexdigest()
        return os.path.join(self._cache_dir, f"{cache_key}.mp3")

    def _synthesis_loop(self):
        while not self._stop_event.is_set():
            try:
                item = self._synthesis_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:
                break

            generation, text, engine = item
            if not self._is_current(generation):
                continue

            started_at = time.perf_counter()
            audio_path = self._cache_path(text, engine)
            partial_path = f"{audio_path}.{generation}.part"
            try:
                if os.path.isfile(audio_path) and os.path.getsize(audio_path) > 0:
                    os.utime(audio_path, None)
                    print(f"[VOICE] Cache hit in {time.perf_counter() - started_at:.3f}s")
                else:
                    engine.synthesize_to_file(text, partial_path)
                    if not self._is_current(generation):
                        continue
                    os.replace(partial_path, audio_path)
                    self._prune_cache()
                    print(f"[VOICE] Synthesized in {time.perf_counter() - started_at:.3f}s")

                if not self._is_current(generation):
                    continue

                self._clear_queue(self._playback_queue)
                try:
                    self._playback_queue.put_nowait(
                        (generation, audio_path, self.mode)
                    )
                except queue.Full:
                    pass
            except Exception as exc:
                print("[VOICE ERROR]", exc)
            finally:
                try:
                    os.remove(partial_path)
                except OSError:
                    pass

    def _queue_mode_loop(self):
        while not self._stop_event.is_set():
            try:
                item = self._voice_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is None:
                break

            text, engine = item
            if not self.enabled or self.mode != "queue" or self._paused.is_set():
                continue

            started_at = time.perf_counter()
            audio_path = self._cache_path(text, engine)
            partial_path = f"{audio_path}.queue.{time.time_ns()}.part"
            try:
                if os.path.isfile(audio_path) and os.path.getsize(audio_path) > 0:
                    os.utime(audio_path, None)
                    print(f"[VOICE QUEUE] Cache hit in {time.perf_counter() - started_at:.3f}s")
                else:
                    engine.synthesize_to_file(text, partial_path)
                    if not self.enabled or self.mode != "queue" or self._paused.is_set():
                        continue
                    os.replace(partial_path, audio_path)
                    self._prune_cache()
                    print(f"[VOICE QUEUE] Synthesized in {time.perf_counter() - started_at:.3f}s")

                while (
                    self.enabled
                    and self.mode == "queue"
                    and not self._paused.is_set()
                    and not self._stop_event.is_set()
                ):
                    try:
                        self._playback_queue.put(
                            (None, audio_path, "queue"), timeout=0.2
                        )
                        break
                    except queue.Full:
                        continue
            except Exception as exc:
                print("[VOICE QUEUE ERROR]", exc)
            finally:
                try:
                    os.remove(partial_path)
                except OSError:
                    pass

    def _prune_cache(self):
        try:
            cache_files = [
                os.path.join(self._cache_dir, name)
                for name in os.listdir(self._cache_dir)
                if name.endswith(".mp3")
            ]
            cache_files.sort(key=os.path.getmtime, reverse=True)
            total_size = 0
            for index, cache_file in enumerate(cache_files):
                file_size = os.path.getsize(cache_file)
                total_size += file_size
                if index >= self.CACHE_LIMIT or total_size > self.CACHE_SIZE_LIMIT:
                    try:
                        os.remove(cache_file)
                    except OSError:
                        pass
        except OSError:
            pass

    def _playback_loop(self):
        try:
            import pygame
            pygame.mixer.init()
        except Exception as exc:
            print("[VOICE] Playback initialization failed:", exc)
            return

        while not self._stop_event.is_set():
            try:
                item = self._playback_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:
                break

            generation, audio_path, item_mode = item
            if item_mode != "queue" and not self._is_current(generation):
                continue
            if item_mode == "queue" and (
                not self.enabled or self.mode != "queue" or self._paused.is_set()
            ):
                continue

            try:
                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
                with self._playback_state_lock:
                    self._playback_active = True
                    self._playback_started_at = time.perf_counter()
                while pygame.mixer.music.get_busy() and not self._stop_event.wait(0.03):
                    if item_mode == "latest" and not self._is_current(generation):
                        pygame.mixer.music.stop()
                        break
                pygame.mixer.music.unload()
            except Exception as exc:
                print("[VOICE ERROR]", exc)
            finally:
                with self._playback_state_lock:
                    self._playback_active = False
                    self._playback_started_at = 0.0

        try:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except Exception:
            pass

    def cancel_pending(self):
        """Stop current speech and discard queued subtitles without disabling Voice."""
        self._paused.set()
        self._cancel_smart_timer()
        self._invalidate_current()
        self._clear_queue(self._synthesis_queue)
        self._clear_queue(self._playback_queue)
        self._clear_queue(self._voice_queue)
        self._last_queued_text = ""
        self._stop_playback()

    def resume_pending(self):
        self._paused.clear()

    def stop(self):
        self.enabled = False
        self._cancel_smart_timer()
        self._invalidate_current()
        self._stop_event.set()
        self._clear_queue(self._synthesis_queue)
        self._clear_queue(self._playback_queue)
        self._clear_queue(self._voice_queue)
        self._stop_playback()
        for _ in self._synthesis_threads:
            try:
                self._synthesis_queue.put_nowait(None)
            except queue.Full:
                break
        try:
            self._voice_queue.put_nowait(None)
        except queue.Full:
            pass
        try:
            self._playback_queue.put_nowait(None)
        except queue.Full:
            pass
        for thread in (self._queue_thread, self._playback_thread):
            if thread is not None:
                thread.join(timeout=2.0)


# ====================== CLICK-THROUGH UTIL ======================
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x80000
WS_EX_TRANSPARENT = 0x20

def make_click_through(win: QtWidgets.QWidget):
    hwnd = int(win.winId())
    ex = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED | WS_EX_TRANSPARENT)


def remove_click_through(win: QtWidgets.QWidget):
    hwnd = int(win.winId())
    ex = windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    # remove WS_EX_TRANSPARENT bit
    windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex & (~WS_EX_TRANSPARENT))
# ====================== EDIT MODE BACKDROP ======================
class EditModeBackdrop(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            QtCore.Qt.Tool |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.WindowDoesNotAcceptFocus  # 🔥 QUAN TRỌNG
        )

        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        # 🔥 CHỐT HẠ: TUYỆT ĐỐI KHÔNG NHẬN FOCUS
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        self.setGeometry(virtual_desktop_geometry())

    # 🔥 CHỐT CUỐI: NUỐT MỌI EVENT (PHÒNG QT GRAB NGẦM)
    def mousePressEvent(self, event):
        event.ignore()

    def mouseReleaseEvent(self, event):
        event.ignore()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(
            self.rect(),
            QtGui.QColor(0, 0, 0, 120)  # nền mờ
        )
        painter.end()

        
# ====================== MOUSE OCR PREVIEW OVERLAY ======================
class MouseOCRPreview(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            QtCore.Qt.Tool |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)

        self._width = MOUSE_OCR_WIDTH
        self._height = MOUSE_OCR_HEIGHT
        # Keep the guide visible to the user but exclude it from Windows
        # screen capture. A text sanitizer remains as a fallback for Windows
        # versions that do not support WDA_EXCLUDEFROMCAPTURE.
        self._capture_excluded = False
        if os.name == "nt":
            try:
                WDA_EXCLUDEFROMCAPTURE = 0x00000011
                self._capture_excluded = bool(
                    windll.user32.SetWindowDisplayAffinity(
                        int(self.winId()), WDA_EXCLUDEFROMCAPTURE
                    )
                )
            except Exception as exc:
                print(f"[MOUSE PREVIEW] Capture exclusion unavailable: {exc}")
        print(
            "[MOUSE PREVIEW] Windows capture exclusion: "
            + ("enabled" if self._capture_excluded else "sanitizer fallback")
        )
        self.hide()

    def show_at(self, x: int, y: int, width: int, height: int):
        self._width = width
        self._height = height
        geometry = mouse_capture_geometry(x, y, width, height)
        if self.geometry() != geometry:
            self.setGeometry(geometry)
        if not self.isVisible():
            self.show()
            self.raise_()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self.rect().adjusted(2, 2, -2, -2)

        # 🌫 nền rất nhẹ
        painter.setBrush(QtGui.QColor(0, 160, 255, 42))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(rect, 10, 10)

        # 🔲 viền nét đứt
        pen = QtGui.QPen(QtGui.QColor(0, 210, 255), 3)
        pen.setStyle(QtCore.Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(rect, 10, 10)

        center = self.rect().center()
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 220), 2))
        painter.drawLine(center.x() - 12, center.y(), center.x() + 12, center.y())
        painter.drawLine(center.x(), center.y() - 12, center.x(), center.y() + 12)

        label_rect = QtCore.QRectF(10, 10, 178, 28)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 80, 110, 225))
        painter.drawRoundedRect(label_rect, 7, 7)
        label_font = QtGui.QFont("Segoe UI", 9)
        label_font.setBold(True)
        painter.setFont(label_font)
        painter.setPen(QtGui.QColor(255, 255, 255))
        painter.drawText(label_rect, QtCore.Qt.AlignCenter, "OCR + TRANSLATION AREA")

        size_rect = QtCore.QRectF(10, self.height() - 34, 112, 24)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 170))
        painter.drawRoundedRect(size_rect, 6, 6)
        painter.setPen(QtGui.QColor(220, 245, 255))
        painter.drawText(
            size_rect,
            QtCore.Qt.AlignCenter,
            f"{self._width}x{self._height} px",
        )

        painter.end()

# ====================== EDIT MODE CONTROL OVERLAY ======================
class EditModeControlOverlay(QtWidgets.QWidget):
    def __init__(self, on_exit, on_confirm):
        super().__init__()

        self.on_exit = on_exit
        self.on_confirm = on_confirm

        self.setWindowFlags(
            QtCore.Qt.Tool |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.setFixedSize(160, 64)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # ❌ Exit
        btn_exit = QtWidgets.QPushButton("✕")
        btn_exit.setFixedSize(64, 64)
        btn_exit.clicked.connect(self._exit)

        btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #e53935;
                color: white;
                font-size: 28px;
                font-weight: bold;
                border-radius: 32px;
            }
            QPushButton:hover {
                background-color: #ff5252;
            }
        """)

        # ✅ Confirm
        btn_ok = QtWidgets.QPushButton("✓")
        btn_ok.setFixedSize(64, 64)
        btn_ok.clicked.connect(self._confirm)

        btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #2ea043;
                color: white;
                font-size: 26px;
                font-weight: bold;
                border-radius: 32px;
            }
            QPushButton:hover {
                background-color: #3fb950;
            }
        """)

        layout.addWidget(btn_exit)
        layout.addWidget(btn_ok)

        self._move_to_top_center()

    def _move_to_top_center(self):
        screen = screen_geometry_at(
            QtGui.QCursor.pos().x(), QtGui.QCursor.pos().y()
        )
        x = screen.center().x() - self.width() // 2
        y = screen.top() + 24
        self.move(x, y)

    def _exit(self):
        self.hide()
        if callable(self.on_exit):
            self.on_exit()

    def _confirm(self):
        self.hide()
        if callable(self.on_confirm):
            self.on_confirm()

# ====================== Subtitle Overlay ======================
class SubtitleOverlay(QtWidgets.QWidget):
    def __init__(self, yellow_region, settings):
        super().__init__()

        self.setWindowFlags(
            QtCore.Qt.Tool |
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self._edit_placeholder = "🔧 SUBTITLE AREA (EDIT MODE)"
        x1, y1, x2, y2 = yellow_region
        # Expand on the monitor containing the saved subtitle region. Global
        # coordinates may be negative when a monitor sits left of primary.
        screen = screen_geometry_for_region(yellow_region)
        screen_x = screen.left()
        screen_w = screen.width()
        region_height = max(1, y2 - y1)
        y1 = max(screen.top(), min(y1, screen.bottom() - region_height + 1))
        self.setGeometry(screen_x, y1, screen_w, region_height)
        self.follow_mouse = False
        # store base/top geometry so we can auto-expand height anchored to bottom
        self.base_top = int(y1)
        self.base_height = int(region_height)
        self.screen_x = screen_x
        self.screen_w = screen_w
        self.screen_geometry = QtCore.QRect(screen)

        # style settings
        self.settings = settings.copy()
        self.follow_mouse = False

        # text content
        self.text = ""
        # Transparent top-level windows can receive many identical repaint
        # requests. Cache the finished subtitle instead of rebuilding its text
        # layout and outline every time.
        self._render_cache_key = None
        self._render_cache_pixmap = None

        # drag state (only active in edit mode)
        self.edit_mode = False
        self._drag_pos = None

        # initially click-through
        make_click_through(self)

    # ========== edit mode control ==========
    def set_edit_mode(self, enabled: bool):
        self.edit_mode = enabled

        if enabled:
            # 🔒 backup subtitle thật
            self._saved_text_before_edit = self.text

            # ❌ ẩn subtitle thật
            self.text = ""

            # 🔓 cho phép mouse
            self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
            remove_click_through(self)

            # ✅ TOOLTIP HƯỚNG DẪN
            self.setToolTip("Left-click to drag\nRight-click disabled\nPress ESC to exit")

            self.show()
            self.raise_()
            self.update()

        else:
            # 🔁 restore subtitle thật
            self.text = getattr(self, "_saved_text_before_edit", "")
            self._saved_text_before_edit = ""

            # 🔒 click-through
            self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
            make_click_through(self)

            # ❌ clear tooltip
            self.setToolTip("")

            self.update()

    
    # ========== settings update ==========


    def update_settings(self, new_settings):
        # new_settings: dict with font_size, bg_alpha, bg_color as [r,g,b]
        self.settings = new_settings.copy()
        # convert bg_color list to QColor if necessary
        if isinstance(self.settings.get("bg_color"), list):
            r, g, b = self.settings["bg_color"]
            self.settings["bg_color"] = QtGui.QColor(r, g, b)
        # convert font_color list to QColor if necessary
        if isinstance(self.settings.get("font_color"), list):
            fr, fg, fb = self.settings["font_color"]
            self.settings["font_color"] = QtGui.QColor(fr, fg, fb)
        # convert shadow color
        if isinstance(self.settings.get("shadow_color"), list):
            sr, sg, sb = self.settings["shadow_color"]
            self.settings["shadow_color"] = QtGui.QColor(sr, sg, sb)
        # ensure numeric shadow params exist
        if "shadow_alpha" not in self.settings:
            self.settings["shadow_alpha"] = 200
        if "shadow_offset" not in self.settings:
            self.settings["shadow_offset"] = 4
        if "stroke_width" not in self.settings:
            self.settings["stroke_width"] = 4
        # ensure style exists
        if "style" not in self.settings:
            self.settings["style"] = "centered"
        self._invalidate_render_cache()
        self.update()

    def update_text(self, text):
        if text is None:
            return
    # 🔒 Chỉ cho OCR ghi đè khi đã có text OCR thật
        if self.text == "HELLO WORLD!" and not text.strip():
            return
        self.text = text
        self._invalidate_render_cache()

        # KHÔNG adjustSize trong paintEvent
        pass

        self.update()

    def _invalidate_render_cache(self):
        self._render_cache_key = None
        self._render_cache_pixmap = None

    def _current_render_key(self):
        def stable_value(value):
            if isinstance(value, QtGui.QColor):
                return value.rgba()
            if isinstance(value, (list, tuple)):
                return tuple(stable_value(item) for item in value)
            return value

        settings_key = tuple(
            sorted((key, stable_value(value)) for key, value in self.settings.items())
        )
        return (self.width(), self.height(), self.text, self.follow_mouse, settings_key)

    def set_base_region(self, region):
        screen = screen_geometry_for_region(region)
        _left, top, _right, bottom = region
        self.screen_x = screen.left()
        self.screen_w = screen.width()
        self.screen_geometry = QtCore.QRect(screen)
        self.base_height = max(1, int(bottom - top))
        self.base_top = max(
            screen.top(),
            min(int(top), screen.bottom() - self.base_height + 1),
        )
        self.follow_mouse = False
        self.setFixedWidth(self.screen_w)
        self.setGeometry(
            self.screen_x, self.base_top, self.screen_w, self.base_height
        )

    def reset_to_base_region(self):
        self.follow_mouse = False
        self.setFixedWidth(self.screen_w)
        self.setGeometry(
            self.screen_x,
            self.base_top,
            self.screen_w,
            self.base_height
        )
        self.update()

    def move_near_mouse(self, x, y):
        if not self.isVisible():
            self.show()
            self.raise_()
        if not self.follow_mouse:
            self.follow_mouse = True
            self.setFixedWidth(600)   # thử 400–600
            self.adjustSize()

        screen = screen_geometry_at(x, y)

        new_x = x + MOUSE_SUBTITLE_OFFSET_X
        new_y = y + MOUSE_SUBTITLE_OFFSET_Y

        if new_x + self.width() > screen.right() + 1:
            new_x = x - self.width() - 10
        if new_y + self.height() > screen.bottom() + 1:
            new_y = y - self.height() - 10
        new_x = max(screen.left(), min(new_x, screen.right() - self.width() + 1))
        new_y = max(screen.top(), min(new_y, screen.bottom() - self.height() + 1))

        self.move(int(new_x), int(new_y))



    # ========== mouse dragging ==========
    def mousePressEvent(self, event):
        if not self.edit_mode:
            return
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self.edit_mode or self._drag_pos is None:
            return
        # compute new position but keep overlay horizontally balanced
        new_top_left = event.globalPos() - self._drag_pos
        screen = screen_geometry_at(event.globalPos().x(), event.globalPos().y())
        screen_w = screen.width()
        new_y = max(
            screen.top(),
            min(int(new_top_left.y()), screen.bottom() - self.height() + 1),
        )
        self.screen_x = screen.left()
        self.screen_w = screen_w
        self.screen_geometry = QtCore.QRect(screen)
        self.setGeometry(self.screen_x, new_y, screen_w, self.height())
        event.accept()

    def mouseReleaseEvent(self, event):
        if not self.edit_mode:
            return
        self._drag_pos = None
        # update stored yellow region to current geometry
        g = self.geometry()
        global cfg, YELLOW_REGION
        screen = screen_geometry_at(g.center().x(), g.center().y())
        self.screen_x = screen.left()
        self.screen_w = screen.width()
        self.screen_geometry = QtCore.QRect(screen)
        YELLOW_REGION = (
            screen.left(), g.top(), screen.right() + 1, g.top() + g.height()
        )
        cfg["yellow_region"] = YELLOW_REGION
        # update base_top/base_height so runtime anchoring uses new edit position
        try:
            self.base_top = int(g.top())
            self.base_height = int(g.height())
        except Exception:
            pass
    def _update_layout_geometry(self, needed_h: int):
        if self.follow_mouse:
            return

        min_h = getattr(self, 'base_height', self.height())
        final_h = max(min_h, needed_h)

        base_top = getattr(self, 'base_top', self.geometry().top())
        new_top = int(base_top + min_h - final_h)
        screen_top = getattr(self, "screen_geometry", virtual_desktop_geometry()).top()
        if new_top < screen_top:
            new_top = screen_top

        if (self.geometry().top() != new_top) or (self.height() != final_h):
            self.setGeometry(self.screen_x, new_top, self.width(), final_h)

    # ========== painting with wrapped text ==========
    def paintEvent(self, event):
        if self.edit_mode:
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)

            rect = self.rect().adjusted(8, 8, -8, -8)

            # 🟦 1. BACKGROUND TRẮNG MỜ (dễ click & drag)
            bg_color = QtGui.QColor(255, 255, 255, 50)  # alpha 30–70 là đẹp
            painter.setBrush(bg_color)
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(rect, 18, 18)

            # 🟡 2. BORDER VÀNG NÉT ĐỨT
            pen = QtGui.QPen(QtGui.QColor(255, 215, 0), 3)
            pen.setStyle(QtCore.Qt.DashLine)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRoundedRect(rect, 18, 18)

            return  # ❌ không vẽ subtitle thật

        if not self.text and not self.edit_mode:
            return
        cache_key = self._current_render_key()
        if self._render_cache_key == cache_key and self._render_cache_pixmap is not None:
            painter = QtGui.QPainter(self)
            painter.drawPixmap(0, 0, self._render_cache_pixmap)
            return

        rendered = QtGui.QPixmap(self.size())
        rendered.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(rendered)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()

        # prepare font and layout
        font = QtGui.QFont("Arial")

        base_size = int(self.settings["font_size"])

        # 🔥 Mouse subtitle → font nhỏ hơn subtitle center
        if self.follow_mouse:
            font_size = int(self.settings.get("mouse_font_size", base_size))
        else:
            font_size = base_size

        font.setPointSize(font_size)
        font.setWeight(int(self.settings.get("font_weight", 75)))
        painter.setFont(font)


        option = QtGui.QTextOption()
        option.setAlignment(QtCore.Qt.AlignCenter)
        option.setWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)

        padding_x = 24
        padding_y = 12
        style = self.settings.get("style", "centered")
        # 🔥 Mouse subtitle: force floating style
        if self.follow_mouse:
            style = "youtube"

        # two-pass layout: first assume max width, then shrink bg if needed
        tentative_wrap = rect.width() - padding_x * 2

        def do_layout(wrap_width):
            layout = QtGui.QTextLayout(self.text, font)
            layout.setTextOption(option)
            layout.beginLayout()
            lines = []
            h = 0
            while True:
                line = layout.createLine()
                if not line.isValid():
                    break
                line.setLineWidth(wrap_width)
                line.setPosition(QtCore.QPointF(0, h))
                h += line.height()
                lines.append(line)
            layout.endLayout()
            # compute max natural width of lines
            max_nw = 0
            for ln in lines:
                try:
                    nw = ln.naturalTextWidth()
                except Exception:
                    nw = ln.width()
                if nw > max_nw:
                    max_nw = nw
            return layout, lines, h, max_nw

        layout, lines, height, max_text_w = do_layout(tentative_wrap)

        # decide background width for each style
        if style == "centered":
            bg_w = min(rect.width() - 40, max_text_w + padding_x * 2)
            wrap_width = int(max(40, bg_w - padding_x * 2))
            corner_radius = 16
        elif style == "netflix":
            # Netflix-like: longer bar centered, slightly larger padding
            extra = 160
            bg_w = min(rect.width() - 40, max_text_w + padding_x * 2 + extra)
            wrap_width = int(max(60, bg_w - padding_x * 2))
            corner_radius = 8
        else:  # youtube
            # YouTube: tight capsule around text with small padding
            small_pad = 12
            bg_w = min(rect.width() - 80, max_text_w + small_pad * 2)
            wrap_width = int(max(20, bg_w - small_pad * 2))
            corner_radius = 20

        # if wrap width changed, relayout to wrap lines properly
        if wrap_width != tentative_wrap:
            layout, lines, height, max_text_w = do_layout(wrap_width)

        # compute final background rect and text_x/y offsets
        needed_h = int(height + padding_y * 2)
        bg_rect = QtCore.QRectF((rect.width() - bg_w) / 2, rect.height() / 2 - (height / 2) - padding_y, bg_w, needed_h)
        text_x = bg_rect.left() + (bg_rect.width() - max_text_w) / 2

        # ensure overlay widget height can contain bg_rect: auto-expand anchored to bottom
        # keep minimum as base_height
        # chỉ tính toán, KHÔNG setGeometry
        needed_h = int(height + padding_y * 2)
        rect = self.rect()

        y_offset = rect.height() / 2 - height / 2

        # background color
        bg = self.settings.get("bg_color")
        if isinstance(bg, QtGui.QColor):
            bgc = QtGui.QColor(bg)
        else:
            bgc = QtGui.QColor(*bg) if isinstance(bg, (list, tuple)) else QtGui.QColor(0, 0, 0)
        bgc.setAlpha(self.settings.get("bg_alpha", 150))

        # style-specific background drawing
        painter.setPen(QtCore.Qt.NoPen)
        if style == "youtube":
            # soft shadow offset
            shadow = QtGui.QColor(0, 0, 0, max(80, int(bgc.alpha() * 0.8)))
            painter.setBrush(shadow)
            painter.drawRoundedRect(bg_rect.translated(2, 2), corner_radius, corner_radius)
            painter.setBrush(bgc)
            painter.drawRoundedRect(bg_rect, corner_radius, corner_radius)
        else:
            if style == "netflix":
                # slightly stronger background for netflix style
                bgc.setAlpha(min(255, int(bgc.alpha() * 1.2)))
            painter.setBrush(bgc)
            painter.drawRoundedRect(bg_rect, corner_radius, corner_radius)

        # stroke (outline) for text for readability
        # draw text shadow (offset) using configured shadow color/alpha/offset
        shadow_col = self.settings.get("shadow_color", QtGui.QColor(0, 0, 0))
        shadow_alpha = int(self.settings.get("shadow_alpha", 200))
        shadow_offset = int(self.settings.get("shadow_offset", 4))
        if isinstance(shadow_col, list):
            shadow_col = QtGui.QColor(*shadow_col)
        shadow_col.setAlpha(shadow_alpha)
        if shadow_offset > 0:
            shadow_width = max(1, int(self.settings.get("shadow_blur", 3)))
            painter.setPen(QtGui.QPen(shadow_col, shadow_width))
            for line in lines:
                line.draw(painter, QtCore.QPointF(text_x + shadow_offset, y_offset + shadow_offset))

        # stroke (outline) for text readability using configured stroke_width
        stroke_w = int(self.settings.get("stroke_width", 4))
        outline_color = self.settings.get("outline_color", [0, 0, 0])

        if isinstance(outline_color, list):
            outline_color = QtGui.QColor(*outline_color)

        painter.setPen(QtGui.QPen(outline_color, 1))

        # 🔥 Vẽ outline bằng nhiều offset xung quanh
        if stroke_w > 0:
            # Sampling the perimeter preserves the visible outline without
            # repainting every point inside the stroke circle.
            sample_count = max(8, stroke_w * 4)
            outline_offsets = {
                (
                    round(math.cos(2 * math.pi * index / sample_count) * stroke_w),
                    round(math.sin(2 * math.pi * index / sample_count) * stroke_w),
                )
                for index in range(sample_count)
            }
            for dx, dy in outline_offsets:
                for line in lines:
                    line.draw(
                        painter,
                        QtCore.QPointF(text_x + dx, y_offset + dy)
                    )

        # draw main text
        text_color = self.settings.get("font_color", QtGui.QColor(255, 255, 255))
        if isinstance(text_color, list):
            text_color = QtGui.QColor(*text_color)
        painter.setPen(QtGui.QPen(text_color, 1))
        for line in lines:
            line.draw(painter, QtCore.QPointF(text_x, y_offset))
        painter.end()
        self._render_cache_key = cache_key
        self._render_cache_pixmap = rendered

        widget_painter = QtGui.QPainter(self)
        widget_painter.drawPixmap(0, 0, rendered)
        widget_painter.end()
        # finally, adjust overlay height if needed
        QtCore.QTimer.singleShot(
            0,
            lambda h=needed_h: self._update_layout_geometry(h)
        )


# ====================== OCR Region Editor (red box) ======================
class OCRRegionEditor(QtWidgets.QWidget):
    HANDLE_SIZE = 10

    def __init__(self, initial_region):
        super().__init__()
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint |
            QtCore.Qt.WindowStaysOnTopHint |
            QtCore.Qt.WindowDoesNotAcceptFocus
        )

        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        # start hidden; shown only in edit mode
        self.setVisible(False)

        self.region = list(initial_region)  # [l,t,r,b]
        self.dragging = False
        self.resizing = False
        self.resize_dir = None
        self._start_pos = None
        self._start_region = None

        self.update_geometry()

    def update_geometry(self):
        l, t, r, b = self.region
        self.setGeometry(int(l), int(t), int(r - l), int(b - t))
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()

        # translucent fill (very light)
        painter.fillRect(rect, QtGui.QColor(255, 0, 0, 40))
        # red border
        pen = QtGui.QPen(QtGui.QColor(255, 0, 0), 2)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRect(rect.adjusted(1, 1, -1, -1))

        # draw handles
        s = self.HANDLE_SIZE
        w, h = rect.width(), rect.height()
        handles = [
            (0, 0, s, s),  # top-left
            (w - s, 0, s, s),  # top-right
            (0, h - s, s, s),  # bottom-left
            (w - s, h - s, s, s)  # bottom-right
        ]
        painter.setBrush(QtGui.QColor(255, 0, 0))
        for x, y, ww, hh in handles:
            painter.drawRect(x, y, ww, hh)

    def mousePressEvent(self, event):
        # ❌ CHẶN CHUỘT PHẢI (FIX KẸT UI)
        if event.button() == QtCore.Qt.RightButton:
            event.accept()
            return

        if event.button() != QtCore.Qt.LeftButton:
            return

        pos = event.pos()
        rect = self.rect()
        s = self.HANDLE_SIZE

        # check resize handles
        if QtCore.QRect(0, 0, s, s).contains(pos):
            self.resizing = True
            self.resize_dir = "tl"
        elif QtCore.QRect(rect.width() - s, 0, s, s).contains(pos):
            self.resizing = True
            self.resize_dir = "tr"
        elif QtCore.QRect(0, rect.height() - s, s, s).contains(pos):
            self.resizing = True
            self.resize_dir = "bl"
        elif QtCore.QRect(rect.width() - s, rect.height() - s, s, s).contains(pos):
            self.resizing = True
            self.resize_dir = "br"
        else:
            self.dragging = True

        self._start_pos = event.globalPos()
        self._start_region = tuple(self.region)


    def mouseMoveEvent(self, event):
        if not (self.dragging or self.resizing):
            return

        delta = event.globalPos() - self._start_pos
        dx, dy = delta.x(), delta.y()
        l, t, r, b = self._start_region

        desktop = virtual_desktop_geometry()

        min_w, min_h = 50, 30

        if self.dragging:
            nl = l + dx
            nt = t + dy
            nr = nl + (r - l)
            nb = nt + (b - t)

        else:  # resizing
            nl, nt, nr, nb = l, t, r, b

            if self.resize_dir == "tl":
                nl += dx
                nt += dy
            elif self.resize_dir == "tr":
                nr += dx
                nt += dy
            elif self.resize_dir == "bl":
                nl += dx
                nb += dy
            elif self.resize_dir == "br":
                nr += dx
                nb += dy

            # enforce minimum size
            if nr - nl < min_w:
                if self.resize_dir in ("tl", "bl"):
                    nl = nr - min_w
                else:
                    nr = nl + min_w

            if nb - nt < min_h:
                if self.resize_dir in ("tl", "tr"):
                    nt = nb - min_h
                else:
                    nb = nt + min_h

        # 🔒 CLAMP TO SCREEN BOUNDS
        nl = max(desktop.left(), min(nl, desktop.right() - min_w + 1))
        nt = max(desktop.top(), min(nt, desktop.bottom() - min_h + 1))
        nr = max(nl + min_w, min(nr, desktop.right() + 1))
        nb = max(nt + min_h, min(nb, desktop.bottom() + 1))

        self.region = [nl, nt, nr, nb]
        self.update_geometry()


    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.resizing = False
        self.resize_dir = None
        self._start_pos = None
        self._start_region = None
        # persist region to global config
        global cfg, RED_REGION
        g = self.geometry()
        RED_REGION = (g.left(), g.top(), g.left() + g.width(), g.top() + g.height())
        cfg["red_region"] = RED_REGION
        save_config(cfg)


# ====================== OCR THREAD ======================
class OCRWorker(QtCore.QThread):
    subtitle_move = QtCore.pyqtSignal(int, int)
    subtitle_ready = QtCore.pyqtSignal(str)

    def __init__(self, fps):
        super().__init__()
        self.running = True
        self._stop = False
        self.fps = fps
        # track last recognized text and inactivity to auto-hide subtitles
        self._last_text = ""
        self._last_change_time = time.time()
        self._blank_emitted = False
        self._inactivity_timeout = 10.0  # seconds
        # track last processed frame hash to avoid duplicate OCR
        self._last_frame_hash = None
        # minimum delay between translation calls (seconds)
        self._translate_cooldown = 0.5
        self._last_mouse_text = ""
        self._context_lock = threading.RLock()
        self._context_memory = deque()
        self._context_signature = None
        context_settings = cfg.get("settings", {})
        self.configure_context(
            context_settings.get("context_enabled", False),
            context_settings.get("context_mode", "video"),
            context_settings.get("context_memory_size", 10),
            context_settings.get("context_dictionary", ""),
            context_settings.get("context_game_rules", ""),
        )

    def configure_context(
        self, enabled, mode, memory_size, dictionary_text, game_rules_text=""
    ):
        memory_size = max(8, min(12, int(memory_size)))
        mode = mode if mode in ("video", "game") else "video"
        glossary = parse_context_dictionary(dictionary_text)
        game_rules = parse_game_dialogue_rules(game_rules_text)

        with self._context_lock:
            previous = list(getattr(self, "_context_memory", []))[-memory_size:]
            settings_changed = (
                getattr(self, "_context_enabled", None) != bool(enabled)
                or getattr(self, "_context_mode", None) != mode
                or getattr(self, "_context_glossary", None) != glossary
                or getattr(self, "_context_game_rules", None) != game_rules
            )
            self._context_enabled = bool(enabled)
            self._context_mode = mode
            self._context_memory_size = memory_size
            self._context_glossary = glossary
            self._context_game_rules = game_rules
            self._context_memory = deque(
                [] if settings_changed else previous,
                maxlen=memory_size,
            )
            if settings_changed:
                self._context_signature = None

    @staticmethod
    def _protect_glossary(text, glossary):
        protected = text
        replacements = {}
        for index, (source, target) in enumerate(
            sorted(glossary.items(), key=lambda item: len(item[0]), reverse=True)
        ):
            token = f"ZXQTERM{index:03d}QXZ"
            escaped = re.escape(source)
            if source[0].isalnum() and source[-1].isalnum():
                pattern = rf"(?<!\w){escaped}(?!\w)"
            else:
                pattern = escaped
            protected, count = re.subn(
                pattern, token, protected, flags=re.IGNORECASE
            )
            if count:
                replacements[token] = target
        return protected, replacements

    @staticmethod
    def _restore_glossary(text, replacements):
        restored = text
        for token, target in replacements.items():
            restored = re.sub(re.escape(token), target, restored, flags=re.IGNORECASE)
        return restored

    @staticmethod
    def _split_game_dialogue(text):
        match = re.match(r"^([^:\n]{1,40}):\s+(.+)$", text.strip())
        if not match:
            return None, text
        speaker = match.group(1).strip()
        if not re.search(r"[^\W\d_]", speaker, flags=re.UNICODE):
            return None, text
        return speaker, match.group(2).strip()

    def _translate_with_optional_context(self, text, normalized, src, tgt):
        with self._context_lock:
            enabled = self._context_enabled
            mode = self._context_mode
            history = list(self._context_memory)
            glossary = dict(self._context_glossary)
            game_rules = dict(self._context_game_rules)
            signature = (src, tgt, mode)
            if self._context_signature != signature:
                self._context_memory.clear()
                history = []
                self._context_signature = signature

        if not enabled or translator.engine_name == "opus_mt":
            # OPUS-MT is sentence translation, not an instruction-following
            # LLM: do not send context markers/glossary placeholders to it.
            # SmartTranslator owns the bounded, language-aware cache.
            return translator.translate(text, src, tgt)

        speaker = None
        dialogue_text = text
        if mode == "game":
            speaker, dialogue_text = self._split_game_dialogue(text)
            if speaker:
                listener = None
                speaker_key = speaker.casefold()

                # Highest priority: a configured character name explicitly
                # mentioned in the current dialogue (for example "Lisa, ...").
                configured_listeners = {
                    rule_listener
                    for rule_speaker, rule_listener in game_rules
                    if rule_speaker == speaker_key and rule_listener != "*"
                }
                for candidate in sorted(configured_listeners, key=len, reverse=True):
                    candidate_pattern = rf"(?<!\w){re.escape(candidate)}(?!\w)"
                    if re.search(candidate_pattern, dialogue_text, flags=re.IGNORECASE):
                        listener = candidate
                        break

                # Otherwise infer the listener from the most recent different
                # speaker in the conversation history.
                if listener is None:
                    for previous_line in reversed(history):
                        previous_speaker, _ = self._split_game_dialogue(previous_line)
                        if (
                            previous_speaker
                            and previous_speaker.casefold() != speaker_key
                        ):
                            listener = previous_speaker.casefold()
                            break

                speaker_rules = game_rules.get((speaker_key, listener or ""))
                if speaker_rules is None:
                    speaker_rules = game_rules.get((speaker_key, "*"), {})
                glossary.update(speaker_rules)

        marker = "ZXQCURRENTSEGMENTQXZ"
        history = [line[-350:] for line in history]
        payload = "\n".join([*history, marker, dialogue_text])
        if len(payload) > 4500:
            payload = payload[-4500:]

        protected_payload, replacements = self._protect_glossary(payload, glossary)
        translated_block = translator.translate(protected_payload, src, tgt)
        if not translated_block:
            return ""

        marker_match = re.search(marker, translated_block, flags=re.IGNORECASE)
        if marker_match:
            translated = translated_block[marker_match.end():].strip()
        else:
            translated_lines = [line.strip() for line in translated_block.splitlines() if line.strip()]
            if len(translated_lines) > 1:
                translated = translated_lines[-1]
            else:
                # If the provider removes the segment marker and all line
                # breaks, fall back safely instead of showing the whole context.
                protected_text, current_replacements = self._protect_glossary(
                    dialogue_text, glossary
                )
                translated = translator.translate(protected_text, src, tgt)
                replacements = current_replacements

        translated = self._restore_glossary(translated or "", replacements)
        if translated and speaker:
            translated = f"{speaker}: {translated}"
        if translated:
            with self._context_lock:
                if not self._context_enabled or self._context_signature != signature:
                    return translated
                if mode == "game":
                    normalized_history = {normalize_text(line) for line in self._context_memory}
                    if normalized not in normalized_history:
                        self._context_memory.append(text)
                else:
                    self._context_memory.append(text)
        return translated
        
    def run(self):
        global RED_REGION, reader, reader_language

        # lazy-init OCR reader inside worker thread
        if reader is None:
            try:
                init_ocr_reader(cfg.get("ocr_lang", "en"))
            except Exception as e:
                print("[OCR] Failed to initialize reader:", e)

        while not self._stop:
            if not self.running:
                self.msleep(200)
                continue
            desired_language = cfg.get("ocr_lang", "en")
            if reader is None or reader_language != desired_language:
                try:
                    init_ocr_reader(desired_language)
                except Exception as exc:
                    print(f"[OCR] Failed to load {desired_language}: {exc}")
                    self.msleep(2000)
                    continue
            try:
                # ===== Choose OCR region (SINGLE DECISION POINT) =====
                mouse_capture = should_follow_mouse()
                main_subtitle_enabled = cfg.get("settings", {}).get(
                    "main_subtitle_enabled", True
                )
                if not mouse_capture and not main_subtitle_enabled:
                    # Mouse-only mode: do not capture, OCR, translate, or call
                    # a paid API while the hold key is not active.
                    self._last_frame_hash = None
                    self._last_text = ""
                    self.msleep(100)
                    continue
                if mouse_capture:
                    idle_time = time.time() - mouse_last_move_time
                    mx, my = mouse_pos

                    global mouse_idle_triggered
                    if not mouse_idle_triggered:
                        mouse_idle_triggered = True
                        print(f"[MOUSE] FOLLOW ON (idle {idle_time:.1f}s)")
                    capture_rect = mouse_capture_geometry(
                        mx, my, MOUSE_OCR_WIDTH, MOUSE_OCR_HEIGHT
                    )
                    x1 = capture_rect.left()
                    y1 = capture_rect.top()
                    x2 = capture_rect.right() + 1
                    y2 = capture_rect.bottom() + 1
                else:
                    mouse_idle_triggered = False
                    x1, y1, x2, y2 = RED_REGION
                    
                if not self.running or self._stop:
                    continue
                # ===== Capture screen region =====
                grab_options = {
                    "bbox": (int(x1), int(y1), int(x2), int(y2))
                }
                if os.name == "nt":
                    # Required for monitors positioned left/above primary,
                    # whose global desktop coordinates are negative.
                    grab_options["all_screens"] = True
                with closing(ImageGrab.grab(**grab_options)) as pil_img:
                    np_img = np.array(pil_img)

                text = ""
                if reader is not None:
                    img_for_ocr = np_img

                    # skip OCR if frame unchanged
                    try:
                        h = frame_hash(img_for_ocr)
                    except Exception:
                        h = None

                    if h is not None and h == self._last_frame_hash:
                        self.msleep(int(1000 / self.fps))
                        continue

                    self._last_frame_hash = h

                    if cv2 is not None:
                        try:
                            hh, ww = img_for_ocr.shape[:2]
                            scale = 0.75
                            img_for_ocr = cv2.resize(
                                img_for_ocr,
                                (int(ww * scale), int(hh * scale)),
                                interpolation=cv2.INTER_LINEAR,
                            )
                        except Exception:
                            pass

                    with torch.inference_mode():
                        result = reader.readtext(img_for_ocr, detail=0)
                    text = " ".join(result)
                    del img_for_ocr, result
                    if mouse_capture:
                        text = strip_mouse_preview_artifacts(
                            text, MOUSE_OCR_WIDTH, MOUSE_OCR_HEIGHT
                        )

                # Release captured pixels before waiting on a translation API.
                del np_img
                now = time.time()
                cleaned = text.strip()
                # ❌ Nếu OCR OFF thì bỏ qua toàn bộ
                if not self.running:
                    self.msleep(100)
                    continue

                # tránh spam khi dùng mouse OCR
                if MOUSE_OCR_ENABLED:
                    if cleaned == self._last_mouse_text:
                        self.msleep(80)
                        continue
                    self._last_mouse_text = cleaned

                if cleaned:
                    if (cleaned != self._last_text) or (self._last_text == ""):
                        normalized = normalize_text(cleaned)

                        # ===== TRANSLATE (SAFE) =====
                        src = cfg.get("translate_source", "auto")
                        tgt = cfg.get("translate_target", "vi")
                        translated = self._translate_with_optional_context(
                            cleaned, normalized, src, tgt
                        )

                        # F8 may have paused the worker while an in-flight API
                        # request was finishing. Never display or speak it, and
                        # do not continue processing after Pause.
                        if not self.running or self._stop:
                            continue
                        if (
                            not mouse_capture
                            and not cfg.get("settings", {}).get(
                                "main_subtitle_enabled", True
                            )
                        ):
                            continue

                        # ===== EMIT SUBTITLE =====
                        if translated:
                            # 1️⃣ set text trước → Qt resize
                            self.subtitle_ready.emit(translated)

                            # 2️⃣ move sau khi đã có text
                            if mouse_capture:
                                mx, my = mouse_pos
                                self.subtitle_move.emit(mx, my)

                            self._last_text = cleaned
                            self._last_change_time = now
                            self._blank_emitted = False

                else:
                    self._last_frame_hash = None
                    if self._last_text and not self._blank_emitted and (now - self._last_change_time > self._inactivity_timeout):
                        self.subtitle_ready.emit("")
                        self._blank_emitted = True

            except Exception as e:
                print("[OCRWorker ERROR]", e)
                self.msleep(500)

            # OCR ON → sleep theo FPS
            self.msleep(int(1000 / self.fps))


    def toggle(self):
        self.running = not self.running
        print("OCR:", "ON" if self.running else "OFF")

        if not self.running:
            self._last_frame_hash = None
            self._last_text = ""
            self._last_mouse_text = ""
            self._blank_emitted = True
            with self._context_lock:
                self._context_memory.clear()

            QtCore.QTimer.singleShot(0, mouse_ocr_preview.hide)

        else:
            # 🔥 RESET TOÀN BỘ STATE KHI BẬT LẠI
            self._last_frame_hash = None
            self._last_text = ""
            self._last_mouse_text = ""
            self._blank_emitted = False
            self._last_change_time = time.time()


    def stop(self):
        self._stop = True

ALLOWED_FUNCTION_KEYS = {
    QtCore.Qt.Key_F1: "f1",
    QtCore.Qt.Key_F2: "f2",
    QtCore.Qt.Key_F3: "f3",
    QtCore.Qt.Key_F4: "f4",
    QtCore.Qt.Key_F5: "f5",
    QtCore.Qt.Key_F6: "f6",
    QtCore.Qt.Key_F7: "f7",
    QtCore.Qt.Key_F8: "f8",
    QtCore.Qt.Key_F9: "f9",
    QtCore.Qt.Key_F10: "f10",
    QtCore.Qt.Key_F11: "f11",
    QtCore.Qt.Key_F12: "f12",
}

MOUSE_HOLD_SPECIAL_KEYS = {
    QtCore.Qt.Key_Space: "space",
    QtCore.Qt.Key_Tab: "tab",
    QtCore.Qt.Key_Return: "enter",
    QtCore.Qt.Key_Enter: "enter",
    QtCore.Qt.Key_Escape: "esc",
    QtCore.Qt.Key_Backspace: "backspace",
    QtCore.Qt.Key_CapsLock: "capslock",
    QtCore.Qt.Key_Insert: "insert",
    QtCore.Qt.Key_Delete: "delete",
    QtCore.Qt.Key_Home: "home",
    QtCore.Qt.Key_End: "end",
    QtCore.Qt.Key_PageUp: "pageup",
    QtCore.Qt.Key_PageDown: "pagedown",
    QtCore.Qt.Key_Left: "left",
    QtCore.Qt.Key_Up: "up",
    QtCore.Qt.Key_Right: "right",
    QtCore.Qt.Key_Down: "down",
}


def qt_keyevent_to_mouse_hold_key(event: QtGui.QKeyEvent) -> str:
    """Capture a keyboard key or combination supported by GetAsyncKeyState."""
    key = event.key()
    mods = event.modifiers()
    parts = []

    if mods & QtCore.Qt.ControlModifier:
        parts.append("ctrl")
    if mods & QtCore.Qt.AltModifier:
        parts.append("alt")
    if mods & QtCore.Qt.ShiftModifier:
        parts.append("shift")
    if mods & QtCore.Qt.MetaModifier:
        parts.append("win")

    modifier_keys = {
        QtCore.Qt.Key_Control: "ctrl",
        QtCore.Qt.Key_Alt: "alt",
        QtCore.Qt.Key_Shift: "shift",
        QtCore.Qt.Key_Meta: "win",
    }
    if key in modifier_keys:
        modifier = modifier_keys[key]
        if modifier not in parts:
            parts.append(modifier)
        return "+".join(parts)

    base_key = ALLOWED_FUNCTION_KEYS.get(key) or MOUSE_HOLD_SPECIAL_KEYS.get(key)
    if base_key is None and QtCore.Qt.Key_A <= key <= QtCore.Qt.Key_Z:
        base_key = chr(key).lower()
    elif base_key is None and QtCore.Qt.Key_0 <= key <= QtCore.Qt.Key_9:
        base_key = chr(key)

    if base_key:
        parts.append(base_key)
        return "+".join(parts)
    return ""


def qt_keyevent_to_hotkey(event: QtGui.QKeyEvent) -> str:
    key = event.key()
    mods = event.modifiers()

    parts = []

    if mods & QtCore.Qt.ControlModifier:
        parts.append("ctrl")
    if mods & QtCore.Qt.AltModifier:
        parts.append("alt")
    if mods & QtCore.Qt.ShiftModifier:
        parts.append("shift")

    # ✅ Modifier đơn lẻ (Ctrl / Alt / Shift)
    if key in (QtCore.Qt.Key_Control, QtCore.Qt.Key_Alt, QtCore.Qt.Key_Shift):
        return "+".join(parts)

    # ✅ F1 → F12
    if key in ALLOWED_FUNCTION_KEYS:
        parts.append(ALLOWED_FUNCTION_KEYS[key])
        return "+".join(parts)

    # ❌ Reject toàn bộ phím khác
    return ""


# ====================== SETTINGS PANEL ======================
class OutlinedToastLabel(QtWidgets.QLabel):
    """Toast label with a thin dark glyph outline for reliable contrast."""

    def paintEvent(self, event):
        super().paintEvent(event)

        text = self.text()
        if not text:
            return

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing, True)
        painter.setFont(self.font())
        text_flags = QtCore.Qt.AlignCenter | QtCore.Qt.TextSingleLine
        outline_color = QtGui.QColor(0, 0, 0, 230)

        painter.setPen(outline_color)
        for dx, dy in (
            (-1, -1), (0, -1), (1, -1),
            (-1, 0),            (1, 0),
            (-1, 1),  (0, 1),  (1, 1),
        ):
            painter.drawText(self.rect().translated(dx, dy), text_flags, text)

        painter.setPen(QtGui.QColor("white"))
        painter.drawText(self.rect(), text_flags, text)


class SettingsPanel(QtWidgets.QWidget):
    # ===== Window Dragging =====
    _drag_active = False
    _drag_candidate = False
    _drag_pos = None
    _drag_press_pos = None
    # ===== Signals =====    
    settings_changed = QtCore.pyqtSignal(dict)
    engine_switch_result = QtCore.pyqtSignal(bool, str)
    tts_test_result = QtCore.pyqtSignal(bool, str)
    opus_test_result = QtCore.pyqtSignal(bool, str)
    
    def _save_ai_draft(self, provider=None):
        provider = provider or getattr(self, "_active_ai_provider", None)
        if provider in AI_PROVIDERS and hasattr(self, "ai_api_key_input"):
            self._ai_key_drafts[provider] = self.ai_api_key_input.text().strip()
            self._ai_model_drafts[provider] = self.ai_model_cb.currentText().strip()

    def _on_engine_change(self, index):
        self._save_ai_draft()
        engine = self.engine_cb.itemData(index)
        self._active_ai_provider = engine if engine in AI_PROVIDERS else None
        if not hasattr(self, "ai_api_key_input"):
            return
        enabled = engine in AI_PROVIDERS
        for widget in self._ai_widgets:
            widget.setVisible(enabled)
        for widget in self._opus_widgets:
            widget.setVisible(engine == "opus_mt")
        if enabled:
            details = AI_PROVIDERS[engine]
            self.ai_api_key_label.setText(f"{details['label']} API Key")
            self.ai_api_key_input.setText(self._ai_key_drafts.get(engine, ""))
            self.ai_api_key_input.setPlaceholderText(details["env"])
            self.ai_model_cb.blockSignals(True)
            self.ai_model_cb.clear()
            self.ai_model_cb.addItems(details.get("models", [details["model"]]))
            self.ai_model_cb.setCurrentText(
                self._ai_model_drafts.get(engine, details["model"])
            )
            self.ai_model_cb.blockSignals(False)
            self.ai_status_label.clear()

    def _browse_opus_model(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choose a prepared OPUS-MT model", self.opus_model_input.text()
        )
        if folder:
            self.opus_model_input.setText(folder)

    def _test_opus_model(self):
        model_dir = self.opus_model_input.text().strip()
        src = OCR_TO_TRANSLATE_LANGUAGE.get(self.input_lang_cb.currentData(), "en")
        tgt = self.trans_tgt_cb.currentData()
        self.opus_test_btn.setEnabled(False)
        self.opus_status_label.setText("Loading and testing local model...")

        def run_test():
            try:
                from opus_mt import OpusMTEngine
                engine = OpusMTEngine(model_dir)
                # An actual local inference, with a probe suitable for the
                # configured source language rather than always English.
                probes = {"en": "Hello world!", "vi": "Xin chào!", "ja": "こんにちは", "ko": "안녕하세요",
                          "zh-cn": "你好", "zh-tw": "你好", "fr": "Bonjour", "de": "Hallo Welt!"}
                result = engine.translate(probes.get(src, "Hello"), src, tgt)
                if not result:
                    raise RuntimeError("The model returned an empty translation.")
                self.opus_test_result.emit(True, f"Local translation: {result}")
            except Exception as exc:
                self.opus_test_result.emit(False, str(exc))

        threading.Thread(target=run_test, name="OpusModelTest", daemon=True).start()

    @QtCore.pyqtSlot(bool, str)
    def _on_opus_test_result(self, ok, message):
        self.opus_test_btn.setEnabled(True)
        self.opus_status_label.setStyleSheet(f"color: {'#22c55e' if ok else '#ef4444'};")
        self.opus_status_label.setText(message)

    def _toggle_api_key_visibility(self, checked):
        mode = QtWidgets.QLineEdit.Normal if checked else QtWidgets.QLineEdit.Password
        self.ai_api_key_input.setEchoMode(mode)

    def _test_ai_connection(self):
        provider = self.engine_cb.currentData()
        if provider not in AI_PROVIDERS:
            return
        self._save_ai_draft(provider)
        key = self._ai_key_drafts.get(provider, "")
        model = self._ai_model_drafts.get(provider, "")
        if not key:
            self._on_ai_test_result(False, "Enter an API key first.")
            return
        self.ai_test_btn.setEnabled(False)
        self.ai_status_label.setText("Testing connection...")

        def run_test():
            ok, message = test_provider(provider, key, model)
            self.engine_switch_result.emit(ok, message)

        threading.Thread(target=run_test, daemon=True).start()

    @QtCore.pyqtSlot(bool, str)
    def _on_ai_test_result(self, ok, message):
        self.ai_test_btn.setEnabled(True)
        color = "#22c55e" if ok else "#ef4444"
        self.ai_status_label.setStyleSheet(f"color: {color};")
        self.ai_status_label.setText(message)

    def _save_tts_draft(self, provider=None):
        provider = provider or getattr(self, "_active_tts_provider", None)
        if provider not in TTS_PROVIDERS or not hasattr(self, "tts_model_cb"):
            return
        profile = self._tts_profile_drafts.setdefault(provider, {})
        profile["model"] = self.tts_model_cb.currentText().strip()
        voice_data = self.voice_cb.currentData()
        profile["voice"] = (
            str(voice_data).strip() if voice_data is not None
            else self.voice_cb.currentText().strip()
        )
        for key, widget, is_secret in getattr(self, "_tts_field_widgets", []):
            value = widget.text().strip()
            if is_secret:
                self._tts_secret_drafts.setdefault(provider, {})[key] = value
            else:
                profile[key] = value

    def _on_tts_provider_change(self, index):
        self._save_tts_draft()
        provider = self.tts_provider_cb.itemData(index)
        self._active_tts_provider = provider
        if not hasattr(self, "tts_model_cb"):
            return
        details = TTS_PROVIDERS[provider]
        profile = self._tts_profile_drafts.setdefault(provider, {})
        self.tts_model_cb.blockSignals(True)
        self.tts_model_cb.clear()
        self.tts_model_cb.addItems(details.get("models", []))
        self.tts_model_cb.setCurrentText(profile.get("model", details.get("model", "")))
        self.tts_model_cb.blockSignals(False)
        has_model = bool(details.get("models"))
        self.tts_model_label.setVisible(has_model)
        self.tts_model_cb.setVisible(has_model)
        self._rebuild_tts_fields(provider)
        self._sync_voice_to_translate_target(saved_voice=profile.get("voice"))
        self.tts_status_label.clear()

    def _rebuild_tts_fields(self, provider):
        while self.tts_fields_layout.count():
            item = self.tts_fields_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._tts_field_widgets = []
        profile = self._tts_profile_drafts.setdefault(provider, {})
        secrets = self._tts_secret_drafts.setdefault(provider, {})
        for key, label, is_secret in TTS_PROVIDERS[provider].get("fields", []):
            field_label = self.section_label(label)
            field = QtWidgets.QLineEdit()
            field.setMinimumHeight(34)
            field.setText(secrets.get(key, "") if is_secret else profile.get(key, ""))
            if is_secret:
                field.setEchoMode(
                    QtWidgets.QLineEdit.Normal
                    if self.tts_show_secrets_cb.isChecked()
                    else QtWidgets.QLineEdit.Password
                )
            self.tts_fields_layout.addWidget(field_label)
            self.tts_fields_layout.addWidget(field)
            self._tts_field_widgets.append((key, field, is_secret))
        has_secrets = any(item[2] for item in self._tts_field_widgets)
        self.tts_show_secrets_cb.setVisible(has_secrets)

    def _toggle_tts_secret_visibility(self, checked):
        mode = QtWidgets.QLineEdit.Normal if checked else QtWidgets.QLineEdit.Password
        for _key, widget, is_secret in getattr(self, "_tts_field_widgets", []):
            if is_secret:
                widget.setEchoMode(mode)

    def _test_tts_connection(self):
        provider = self.tts_provider_cb.currentData() or "edge"
        self._save_tts_draft(provider)
        profile = self._tts_profile_drafts.get(provider, {})
        fields = dict(self._tts_secret_drafts.get(provider, {}))
        for key, _label, is_secret in TTS_PROVIDERS[provider].get("fields", []):
            if not is_secret:
                fields[key] = profile.get(key, "")
        language = VOICE_LANGUAGE_BY_TRANSLATE_TARGET.get(
            self.trans_tgt_cb.currentData(), "en-US"
        )
        self.tts_test_btn.setEnabled(False)
        self.tts_status_label.setText("Generating test voice...")

        def run_test():
            ok, message = test_tts_provider(
                provider,
                profile.get("model", ""),
                profile.get("voice", ""),
                language,
                fields,
            )
            self.tts_test_result.emit(ok, message)

        threading.Thread(target=run_test, daemon=True).start()

    @QtCore.pyqtSlot(bool, str)
    def _on_tts_test_result(self, ok, message):
        self.tts_test_btn.setEnabled(True)
        self.tts_status_label.setStyleSheet(
            f"color: {'#22c55e' if ok else '#ef4444'};"
        )
        self.tts_status_label.setText(message)

    # ===== Rollback Snapshot =====
    def rollback_settings(self):
        global cfg, SETTINGS_SNAPSHOT, worker

        if not SETTINGS_SNAPSHOT:
            return

        # 🔁 Restore cfg
        cfg.clear()
        cfg.update(json.loads(json.dumps(SETTINGS_SNAPSHOT)))

        # 🔁 Restore regions
        global RED_REGION, YELLOW_REGION
        RED_REGION = tuple(cfg.get("red_region", RED_REGION))
        YELLOW_REGION = tuple(cfg.get("yellow_region", YELLOW_REGION))

        # 🔁 Restore overlay position
        self.overlay.set_base_region(YELLOW_REGION)

        # 🔁 Restore OCR editor
        self.editor.region = list(RED_REGION)
        self.editor.update_geometry()

        # 🔁 Restore visual settings
        self.overlay.update_settings(cfg["settings"])
        context_settings = cfg.get("settings", {})
        if hasattr(self, "main_subtitle_cb"):
            self.main_subtitle_cb.setChecked(
                context_settings.get("main_subtitle_enabled", True)
            )
            restore_main_subtitle_overlay()
        if hasattr(self, "tts_provider_cb"):
            self._active_tts_provider = None
            self._tts_profile_drafts = {
                provider: dict(cfg.get("tts_profiles", {}).get(provider, {}))
                for provider in TTS_PROVIDERS
            }
            self._tts_secret_drafts = {
                provider: get_tts_secret_fields(provider, cfg)
                for provider in TTS_PROVIDERS
            }
            restored_provider = context_settings.get("tts_provider", "edge")
            self.tts_provider_cb.blockSignals(True)
            self.tts_provider_cb.setCurrentIndex(
                max(0, self.tts_provider_cb.findData(restored_provider))
            )
            self.tts_provider_cb.blockSignals(False)
            self._on_tts_provider_change(self.tts_provider_cb.currentIndex())
            self.voice_enabled_cb.setChecked(
                context_settings.get("voice_enabled", False)
            )
            self.voice_mode_cb.setCurrentIndex(
                max(0, self.voice_mode_cb.findData(
                    context_settings.get("voice_mode", "smart")
                ))
            )
        restored_theme = context_settings.get("ui_theme", "dark")
        if hasattr(self, "theme_cb"):
            self.theme_cb.blockSignals(True)
            self.theme_cb.setCurrentIndex(
                max(0, self.theme_cb.findData(restored_theme))
            )
            self.theme_cb.blockSignals(False)
        apply_ui_theme(restored_theme)
        try:
            configure_translator(cfg)
        except Exception as exc:
            print(f"[Translator rollback] {exc}")
        if voice_speaker is not None:
            try:
                provider, profile, fields = get_tts_runtime_config(cfg)
                voice_speaker.configure(
                    context_settings.get("voice_enabled", False),
                    context_settings.get("voice_language", "vi-VN"),
                    profile.get("voice", context_settings.get("voice", "")),
                    context_settings.get("voice_mode", "smart"),
                    provider,
                    profile.get("model", ""),
                    fields,
                )
            except Exception as exc:
                print(f"[TTS rollback] {exc}")
        if worker is not None:
            worker.configure_context(
                context_settings.get("context_enabled", False),
                context_settings.get("context_mode", "video"),
                context_settings.get("context_memory_size", 10),
                context_settings.get("context_dictionary", ""),
                context_settings.get("context_game_rules", ""),
            )

    # ---------- Helper ----------
    def section(self, title):
        box = QtWidgets.QVBoxLayout()
        box.setSpacing(10)
        # Keep short cards pinned to the top when a neighbouring card is
        # taller. Without this, QBoxLayout distributes the spare height
        # between the title and frame, creating a large visual gap.
        box.setAlignment(QtCore.Qt.AlignTop)

        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("sectionTitle")
        box.addWidget(title_label)

        frame = QtWidgets.QFrame()
        frame.setObjectName("settingsCard")

        # ⭐ QUAN TRỌNG
        frame.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Preferred
        )

        frame_layout = QtWidgets.QVBoxLayout(frame)
        frame_layout.setContentsMargins(16, 16, 16, 16)
        frame_layout.setSpacing(12)

        box.addWidget(frame)
        return box, frame_layout
    
    def choose_outline_color(self):
        color = self._open_color_dialog(
            "Choose Outline Color", self.settings.get("outline_color", [0, 0, 0])
        )
        if color.isValid():
            self.settings["outline_color"] = [
                color.red(),
                color.green(),
                color.blue()
            ]
        oc = self.settings.get("outline_color", [0,0,0])
        self.outline_color_btn.setStyleSheet(self._color_button_style(oc))

    @staticmethod
    def _color_button_style(rgb):
        red, green, blue = rgb[:3]
        luminance = (0.299 * red) + (0.587 * green) + (0.114 * blue)
        text_color = "#111827" if luminance > 155 else "#ffffff"
        return (
            f"background-color: rgb({red}, {green}, {blue}); "
            f"color: {text_color}; border-radius: 10px;"
        )


    def section_label(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setContentsMargins(2, 6, 2, 4)
        lbl.setObjectName("fieldLabel")
        return lbl

    def _open_color_dialog(self, title, initial_rgb):
        initial = QtGui.QColor(*(initial_rgb or [0, 0, 0])[:3])
        dialog = QtWidgets.QColorDialog(initial, self)
        dialog.setWindowTitle(title)
        # Settings itself is always-on-top. Make the owned color dialog modal
        # and topmost as well so Windows cannot place it behind its parent.
        dialog.setOption(QtWidgets.QColorDialog.DontUseNativeDialog, True)
        dialog.setWindowModality(QtCore.Qt.WindowModal)
        dialog.setWindowFlags(
            QtCore.Qt.Dialog
            | QtCore.Qt.WindowTitleHint
            | QtCore.Qt.WindowSystemMenuHint
            | QtCore.Qt.WindowCloseButtonHint
            | QtCore.Qt.WindowStaysOnTopHint
        )
        dialog.setSizeGripEnabled(True)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            return dialog.selectedColor()
        return QtGui.QColor()

    def on_close_clicked(self):
        # ❌ Cancel all Apply/Confirm changes
        self.rollback_settings()
        self.hide()
        
    @QtCore.pyqtSlot()
    def toggle_from_hotkey(self):
        global SETTINGS_SNAPSHOT, cfg, overlay

        print("[UI] SettingsPanel.toggle_from_hotkey()")

        if self.isVisible():
            print("[UI] Hiding Settings Panel (Cancel)")
            self.on_close_clicked()
            overlay.raise_()
            return

        print("[UI] Showing Settings Panel")

        # snapshot để rollback
        SETTINGS_SNAPSHOT = json.loads(json.dumps(cfg))

        overlay.lower()

        self.show()
        self.setWindowState(
            self.windowState() & ~QtCore.Qt.WindowMinimized
        )
        self.raise_()
        self.activateWindow()
        self.setFocus()

        print("[UI] Settings Panel shown + activated")


    # ---------- INIT ----------
    def __init__(self, overlay, editor, parent=None):
        super().__init__(parent)
        self._active_ai_provider = None
        self._ai_key_drafts = {
            provider: get_ai_api_key(provider) for provider in AI_PROVIDERS
        }
        self._ai_model_drafts = {
            provider: cfg.get("ai_models", {}).get(provider, details["model"])
            for provider, details in AI_PROVIDERS.items()
        }
        self._active_tts_provider = None
        self._tts_profile_drafts = {
            provider: dict(cfg.get("tts_profiles", {}).get(provider, {}))
            for provider in TTS_PROVIDERS
        }
        self._tts_secret_drafts = {
            provider: get_tts_secret_fields(provider) for provider in TTS_PROVIDERS
        }
        self._drag_active = False
        self._drag_candidate = False
        self._drag_pos = None
        self._drag_press_pos = None
        self.setWindowFlags(
            QtCore.Qt.Tool |
            QtCore.Qt.FramelessWindowHint |     
            QtCore.Qt.WindowStaysOnTopHint
        )

        self.setWindowTitle("GloSub Settings")
        self.setObjectName("settingsWindow")
        # ===== CUSTOM TITLE BAR =====
        title_bar_widget = QtWidgets.QWidget()
        title_bar_widget.setObjectName("settingsTitleBar")
        title_bar_widget.setMinimumHeight(48)
        title_bar_widget.setCursor(QtCore.Qt.SizeAllCursor)
        title_bar_widget.setProperty("settingsTitleDrag", True)
        title_bar_widget.installEventFilter(self)
        title_bar = QtWidgets.QHBoxLayout(title_bar_widget)
        title_bar.setContentsMargins(4, 4, 4, 4)

        self.theme_cb = QtWidgets.QComboBox()
        self.theme_cb.setFixedWidth(112)
        self.theme_cb.setToolTip("Settings theme")
        self.theme_cb.addItem("Dark", "dark")
        self.theme_cb.addItem("Light", "light")
        saved_theme = cfg.get("settings", {}).get("ui_theme", "dark")
        self.theme_cb.setCurrentIndex(max(0, self.theme_cb.findData(saved_theme)))
        self.theme_cb.currentIndexChanged.connect(self._on_theme_changed)

        title_label = QtWidgets.QLabel(f"⚙ {tr('SETTINGS_TITLE')}")
        title_label.setStyleSheet("font-weight:600; font-size:14px;")
        title_label.setCursor(QtCore.Qt.SizeAllCursor)
        title_label.setProperty("settingsTitleDrag", True)
        title_label.installEventFilter(self)

        btn_close = QtWidgets.QPushButton("✕")
        btn_close.setObjectName("closeButton")
        btn_close.setFixedSize(28, 28)
        btn_close.clicked.connect(self.on_close_clicked)

        title_bar.addWidget(title_label)
        title_bar.addStretch()
        title_bar.addWidget(self.theme_cb)
        title_bar.addWidget(btn_close)
        # ===== Window Icon =====
        icon_path = resource_path("Icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))
        # make settings panel wider to avoid cramped controls (4 columns)
        # reduce vertical size by 300 as requested
        self.resize(920, 720)
        self.setMinimumWidth(800)
        self.setMinimumHeight(620)
        # ===== RUN ON STARTUP CHECKBOX =====
        startup_enabled = is_run_on_startup()
        self.run_startup_cb = QtWidgets.QCheckBox("Run with Windows")
        self.run_startup_cb.setChecked(startup_enabled)
        self.run_startup_cb.toggled.connect(self.on_run_startup_toggled)
        self.main_subtitle_cb = QtWidgets.QCheckBox(
            "Enable Main Subtitle (fixed OCR area)"
        )
        self.main_subtitle_cb.setChecked(
            cfg.get("settings", {}).get("main_subtitle_enabled", True)
        )
        self.main_subtitle_cb.setToolTip(
            "Turn this off for Mouse Subtitle only. F8 still pauses all OCR and translation."
        )
        self.ocr_device_value = QtWidgets.QLabel(OCR_DEVICE_STATUS)
        self.ocr_device_value.setObjectName("accentLabel")
        self.ocr_device_value.setWordWrap(True)
        self.ocr_device_value.setToolTip(
            "Auto uses an NVIDIA CUDA GPU when available; otherwise CPU is used."
        )
        self.ocr_device_timer = QtCore.QTimer(self)
        self.ocr_device_timer.timeout.connect(self._refresh_ocr_device_status)
        self.ocr_device_timer.start(750)
        # ===== MOUSE OCR CHECKBOX =====
        self.mouse_ocr_cb = QtWidgets.QCheckBox("Enable Mouse OCR (Hold key)")
        self.mouse_ocr_cb.setChecked(
            cfg.get("settings", {}).get("mouse_ocr_enabled", False)
        )
        self.mouse_ocr_width_input = QtWidgets.QSpinBox()
        self.mouse_ocr_width_input.setRange(100, 1600)
        self.mouse_ocr_width_input.setSingleStep(50)
        self.mouse_ocr_width_input.setSuffix(" px")
        self.mouse_ocr_width_input.setValue(
            int(cfg.get("settings", {}).get("mouse_ocr_width", 300))
        )
        self.mouse_ocr_width_input.setMinimumHeight(34)

        self.mouse_ocr_height_input = QtWidgets.QSpinBox()
        self.mouse_ocr_height_input.setRange(100, 1200)
        self.mouse_ocr_height_input.setSingleStep(50)
        self.mouse_ocr_height_input.setSuffix(" px")
        self.mouse_ocr_height_input.setValue(
            int(cfg.get("settings", {}).get("mouse_ocr_height", 300))
        )
        self.mouse_ocr_height_input.setMinimumHeight(34)
        # ===== VOICE =====
        voice_settings = cfg.get("settings", {})
        self.voice_enabled_cb = QtWidgets.QCheckBox("Enable Voice")
        self.voice_enabled_cb.setChecked(voice_settings.get("voice_enabled", False))

        self.tts_provider_cb = QtWidgets.QComboBox()
        for provider, details in TTS_PROVIDERS.items():
            self.tts_provider_cb.addItem(details["label"], provider)
        saved_tts_provider = voice_settings.get("tts_provider", "edge")
        if saved_tts_provider == "edge" and voice_settings.get("voice"):
            self._tts_profile_drafts.setdefault("edge", {})["voice"] = voice_settings["voice"]
        self.tts_provider_cb.setCurrentIndex(
            max(0, self.tts_provider_cb.findData(saved_tts_provider))
        )

        self.tts_model_label = self.section_label("TTS Model / Engine")
        self.tts_model_cb = QtWidgets.QComboBox()
        self.tts_model_cb.setEditable(True)
        self.tts_model_cb.setMinimumHeight(34)

        self.tts_fields_widget = QtWidgets.QWidget()
        self.tts_fields_layout = QtWidgets.QVBoxLayout(self.tts_fields_widget)
        self.tts_fields_layout.setContentsMargins(0, 0, 0, 0)
        self.tts_fields_layout.setSpacing(8)
        self._tts_field_widgets = []
        self.tts_show_secrets_cb = QtWidgets.QCheckBox("Show TTS credentials")
        self.tts_show_secrets_cb.toggled.connect(self._toggle_tts_secret_visibility)

        self.voice_language_value = QtWidgets.QLabel()
        self.voice_language_value.setObjectName("accentLabel")
        self.voice_language_value.setContentsMargins(2, 6, 2, 6)

        self.voice_cb = QtWidgets.QComboBox()
        self.voice_cb.setEditable(True)
        self.voice_cb.setMinimumHeight(34)

        self.tts_test_btn = QtWidgets.QPushButton("Test TTS Connection")
        self.tts_test_btn.setMinimumHeight(36)
        self.tts_test_btn.clicked.connect(self._test_tts_connection)
        self.tts_status_label = QtWidgets.QLabel()
        self.tts_status_label.setWordWrap(True)
        self.tts_test_result.connect(self._on_tts_test_result)
        self.tts_provider_cb.currentIndexChanged.connect(self._on_tts_provider_change)

        self.voice_mode_cb = QtWidgets.QComboBox()
        self.voice_mode_cb.addItem("Smart (Recommended)", "smart")
        self.voice_mode_cb.addItem("Queue (Read every subtitle)", "queue")
        self.voice_mode_cb.addItem("Latest (Interrupt immediately)", "latest")
        saved_voice_mode = voice_settings.get("voice_mode", "smart")
        self.voice_mode_cb.setCurrentIndex(
            max(0, self.voice_mode_cb.findData(saved_voice_mode))
        )
        self.voice_mode_cb.setToolTip(
            "Smart balances timing. Queue reads in order. Latest interrupts immediately."
        )

        # ===== VIDEO / GAME CONTEXT =====
        context_settings = cfg.get("settings", {})
        self.context_enabled_cb = QtWidgets.QCheckBox("Enable Video/Game Context")
        self.context_enabled_cb.setChecked(
            context_settings.get("context_enabled", False)
        )
        self.context_enabled_cb.toggled.connect(self._update_context_controls)

        self.context_mode_cb = QtWidgets.QComboBox()
        self.context_mode_cb.addItem("Video (chronological dialogue)", "video")
        self.context_mode_cb.addItem("Game (unique recent lines)", "game")
        mode_index = self.context_mode_cb.findData(
            context_settings.get("context_mode", "video")
        )
        self.context_mode_cb.setCurrentIndex(max(0, mode_index))
        self.context_mode_cb.setMinimumHeight(34)
        self.context_mode_cb.currentIndexChanged.connect(
            self._update_context_mode_controls
        )

        self.context_memory_input = QtWidgets.QSpinBox()
        self.context_memory_input.setRange(8, 12)
        self.context_memory_input.setSuffix(" sentences")
        self.context_memory_input.setValue(
            int(context_settings.get("context_memory_size", 10))
        )
        self.context_memory_input.setMinimumHeight(34)

        self.context_dictionary_input = QtWidgets.QPlainTextEdit()
        self.context_dictionary_input.setPlaceholderText(
            "One entry per line: source = preferred translation\n"
            "Example: Cloud = Cloud\nPotion = Bình máu"
        )
        self.context_dictionary_input.setPlainText(
            context_settings.get("context_dictionary", "")
        )
        self.context_dictionary_input.setMinimumHeight(110)
        self.context_dictionary_input.setMaximumHeight(150)

        self.context_game_rules_label = self.section_label(
            "Game Speaker & Relationship Rules"
        )
        self.context_game_rules_input = QtWidgets.QPlainTextEdit()
        self.context_game_rules_input.setPlaceholderText(GAME_RULES_EXAMPLE)
        self.context_game_rules_input.setPlainText(
            context_settings.get("context_game_rules", "")
        )
        self.context_game_rules_input.setMinimumHeight(140)
        self.context_game_rules_input.setMaximumHeight(190)
        self.context_game_rules_help = QtWidgets.QLabel(
            "Priority: mentioned name > previous speaker > general speaker rule"
        )
        self.context_game_rules_help.setObjectName("helpText")
        self.context_game_example_btn = QtWidgets.QPushButton(
            "Insert Example Rules"
        )
        self.context_game_example_btn.setToolTip(GAME_RULES_EXAMPLE)
        self.context_game_example_btn.clicked.connect(
            self._insert_game_rules_example
        )

        self.mouse_hold_key_input = QtWidgets.QLineEdit()
        self.mouse_hold_key_input.setReadOnly(True)
        self.mouse_hold_key_input.setPlaceholderText(
            "Press a key or combination (e.g. Q, F6, Alt+Q)"
        )
        self.mouse_hold_key_input.setText(MOUSE_HOLD_KEY.upper())
        self.mouse_hold_key_input.setMinimumHeight(32)
        self.mouse_hold_key_input.installEventFilter(self)
        #===== HOTKEY INPUT =====
        self.hotkey_input = QtWidgets.QLineEdit()
        self.hotkey_input.setPlaceholderText("Press key (e.g. F8, F9, Ctrl+Alt+P)")
        self.hotkey_input.setText(cfg.get("hotkey_pause", "F8"))
        self.hotkey_input.setMinimumHeight(34)
        self.hotkey_input.installEventFilter(self)
        self.settings_hotkey_input = QtWidgets.QLineEdit()
        self.settings_hotkey_input.setPlaceholderText("Press key (e.g. F10, Ctrl+Alt+S)")
        self.settings_hotkey_input.setText(cfg.get("hotkey_settings", "F10"))
        self.settings_hotkey_input.setMinimumHeight(34)
        self.settings_hotkey_input.installEventFilter(self)
        


        #===== REFERENCES =====
        self.overlay = overlay
        self.editor = editor

        # ===== LOAD SETTINGS =====
        bg = overlay.settings["bg_color"]
        if isinstance(bg, list):
            bg = QtGui.QColor(*bg)

        # font color default
        fcol = overlay.settings.get("font_color", [255, 255, 255])
        if isinstance(fcol, QtGui.QColor):
            fcol = [fcol.red(), fcol.green(), fcol.blue()]

        self.settings = {
            "font_size": overlay.settings["font_size"],
            "font_weight": overlay.settings.get("font_weight", 75),
            "mouse_font_size": overlay.settings.get("mouse_font_size", 22),
            "bg_alpha": overlay.settings["bg_alpha"],
            "bg_color": [bg.red(), bg.green(), bg.blue()],
            "font_color": fcol,
            "outline_color": overlay.settings.get("outline_color", [0,0,0]),
            "style": overlay.settings.get("style", "centered")
        }

        # ===== WIDGETS =====
        self.font_size_input = QtWidgets.QSpinBox()
        self.font_size_input.setRange(10, 80)
        self.font_size_input.setValue(self.settings["font_size"])
        self.font_size_input.setMinimumHeight(32)
        self.font_size_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        # font weight input
        self.font_weight_input = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.font_weight_input.setRange(10, 99)
        self.font_weight_input.setValue(self.settings["font_weight"])
        self.font_weight_input.setMinimumHeight(22)
        # Mouse subtitle font size
        self.mouse_font_size_input = QtWidgets.QSpinBox()
        self.mouse_font_size_input.setRange(10, 60)
        self.mouse_font_size_input.setValue(self.settings["mouse_font_size"])
        self.mouse_font_size_input.setMinimumHeight(32)

        # background opacity slider
        self.outline_color_btn = QtWidgets.QPushButton("Choose Outline Color")
        self.outline_color_btn.setMinimumHeight(36)
        self.outline_color_btn.clicked.connect(self.choose_outline_color)
        self.outline_color_btn.setStyleSheet(
            self._color_button_style(self.settings.get("outline_color", [0, 0, 0]))
        )
        # apply initial preview color
        self.bg_alpha_input = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.bg_alpha_input.setRange(0, 255)
        self.bg_alpha_input.setValue(self.settings["bg_alpha"])
        self.bg_alpha_input.setMinimumHeight(22)
        # reduced minimum width to better fit into four narrow columns
        self.bg_alpha_input.setMinimumWidth(140)
        self.bg_alpha_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.color_btn = QtWidgets.QPushButton("Choose Background Color")
        self.color_btn.setMinimumHeight(36)
        self.color_btn.clicked.connect(self.choose_color)
        self.color_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        # font color chooser
        self.font_color_btn = QtWidgets.QPushButton("Choose Font Color")
        self.font_color_btn.setMinimumHeight(36)
        self.font_color_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.font_color_btn.clicked.connect(self.choose_font_color)
        # apply initial preview color
        fc = self.settings.get("font_color", [255, 255, 255])
        self.font_color_btn.setStyleSheet(self._color_button_style(fc))

        # shadow color chooser
        sc = self.settings.get("shadow_color", [0, 0, 0])
        if isinstance(sc, QtGui.QColor):
            sc = [sc.red(), sc.green(), sc.blue()]
        self.shadow_color_btn = QtWidgets.QPushButton("Choose Shadow Color")
        self.shadow_color_btn.setMinimumHeight(36)
        self.shadow_color_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.shadow_color_btn.clicked.connect(self.choose_shadow_color)
        self.shadow_color_btn.setStyleSheet(self._color_button_style(sc))

        # shadow opacity slider
        self.shadow_alpha_input = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.shadow_alpha_input.setRange(0, 255)
        self.shadow_alpha_input.setValue(self.settings.get("shadow_alpha", 200))
        self.shadow_alpha_input.setMinimumHeight(22)
        self.shadow_alpha_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        # shadow offset (pixels)
        self.shadow_offset_input = QtWidgets.QSpinBox()
        self.shadow_offset_input.setRange(0, 50)
        self.shadow_offset_input.setValue(self.settings.get("shadow_offset", 4))
        self.shadow_offset_input.setMinimumHeight(32)
        self.shadow_offset_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        # stroke width for outline
        self.stroke_width_input = QtWidgets.QSpinBox()
        self.stroke_width_input.setRange(0, 20)
        self.stroke_width_input.setValue(self.settings.get("stroke_width", 4))
        self.stroke_width_input.setMinimumHeight(32)
        self.stroke_width_input.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        # theme chooser removed

        self.input_lang_cb = QtWidgets.QComboBox()
        for ocr_code, label in INPUT_LANGUAGE_LABELS.items():
            self.input_lang_cb.addItem(label, ocr_code)

        current_input_language = cfg.get("ocr_lang", "en")
        input_index = self.input_lang_cb.findData(current_input_language)
        self.input_lang_cb.setCurrentIndex(max(0, input_index))
        self.input_lang_cb.setMinimumHeight(34)
        self.input_lang_cb.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.trans_tgt_cb = QtWidgets.QComboBox()
        # ===== Translator Engine =====
        self.engine_cb = QtWidgets.QComboBox()
        self.engine_cb.addItem("Google Translate", "google")
        self.engine_cb.addItem("OPUS-MT (Offline · CPU INT8)", "opus_mt")
        for provider, details in AI_PROVIDERS.items():
            self.engine_cb.addItem(details["label"], provider)

        current_engine = cfg.get("translate_engine", "google")
        for i in range(self.engine_cb.count()):
            if self.engine_cb.itemData(i) == current_engine:
                self.engine_cb.setCurrentIndex(i)
                break

        self.ai_api_key_label = self.section_label("API Key")
        self.ai_api_key_input = QtWidgets.QLineEdit()
        self.ai_api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.ai_api_key_input.setMinimumHeight(34)
        self.ai_show_key_cb = QtWidgets.QCheckBox("Show API key")
        self.ai_show_key_cb.toggled.connect(self._toggle_api_key_visibility)
        self.ai_model_label = self.section_label("AI Model")
        self.ai_model_cb = QtWidgets.QComboBox()
        self.ai_model_cb.setEditable(True)
        self.ai_model_cb.setMinimumHeight(34)
        self.ai_test_btn = QtWidgets.QPushButton("Test AI Connection")
        self.ai_test_btn.setMinimumHeight(36)
        self.ai_test_btn.clicked.connect(self._test_ai_connection)
        self.ai_status_label = QtWidgets.QLabel()
        self.ai_status_label.setWordWrap(True)
        self._ai_widgets = [
            self.ai_api_key_label,
            self.ai_api_key_input,
            self.ai_show_key_cb,
            self.ai_model_label,
            self.ai_model_cb,
            self.ai_test_btn,
            self.ai_status_label,
        ]
        self.opus_model_label = self.section_label("OPUS-MT model folder")
        self.opus_model_input = QtWidgets.QLineEdit(cfg.get("opus_mt_model_dir", ""))
        self.opus_model_input.setPlaceholderText("Choose a prepared model folder")
        self.opus_model_input.setMinimumHeight(34)
        self.opus_browse_btn = QtWidgets.QPushButton("Choose Model Folder")
        self.opus_browse_btn.clicked.connect(self._browse_opus_model)
        self.opus_test_btn = QtWidgets.QPushButton("Test Offline Translation")
        self.opus_test_btn.clicked.connect(self._test_opus_model)
        self.opus_status_label = QtWidgets.QLabel()
        self.opus_status_label.setWordWrap(True)
        self.opus_hint = QtWidgets.QLabel(
            "No API key or Internet needed after model preparation. The model must match "
            "Input Language and Translate To. Context and glossary rules apply to online engines only."
        )
        self.opus_hint.setWordWrap(True)
        self._opus_widgets = [self.opus_model_label, self.opus_model_input,
                              self.opus_browse_btn, self.opus_test_btn,
                              self.opus_status_label, self.opus_hint]
        self.opus_test_result.connect(self._on_opus_test_result)
        self.engine_switch_result.connect(self._on_ai_test_result)
        self.engine_cb.currentIndexChanged.connect(self._on_engine_change)

        for code, name in TRANSLATE_LANGUAGES.items():
            if code != "auto":
                self.trans_tgt_cb.addItem(name, code)

        current_tgt = cfg.get("translate_target", "vi")
        for i in range(self.trans_tgt_cb.count()):
            if self.trans_tgt_cb.itemData(i) == current_tgt:
                self.trans_tgt_cb.setCurrentIndex(i)
                break

        self.trans_tgt_cb.setMinimumHeight(34)
        self.trans_tgt_cb.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.trans_tgt_cb.currentIndexChanged.connect(self._sync_voice_to_translate_target)
        self._on_tts_provider_change(self.tts_provider_cb.currentIndex())

        # style chooser
        self.style_cb = QtWidgets.QComboBox()
        self.style_cb.addItem("Centered Box", "centered")
        self.style_cb.addItem("Netflix Style", "netflix")
        self.style_cb.addItem("YouTube Style", "youtube")
        # select current
        cur_style = self.settings.get("style", "centered")
        for i in range(self.style_cb.count()):
            if self.style_cb.itemData(i) == cur_style:
                self.style_cb.setCurrentIndex(i)
                break
        self.style_cb.setMinimumHeight(34)
        self.style_cb.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.edit_btn = QtWidgets.QPushButton("Edit Subtitle & OCR Region")
        self.edit_btn.setCheckable(True)
        self.edit_btn.setMinimumHeight(38)
        self.edit_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.edit_btn.toggled.connect(self.on_edit_toggled)

        # ===== ROOT LAYOUT =====
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.addWidget(title_bar_widget)
        root_layout.setSpacing(8)
        root_layout.setContentsMargins(10, 10, 10, 10)

        tabs = QtWidgets.QTabWidget()
        tabs.setDocumentMode(True)
        tabs.tabBar().setDrawBase(False)
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setElideMode(QtCore.Qt.ElideNone)
        tabs.tabBar().setUsesScrollButtons(False)
        root_layout.addWidget(tabs, 1)

        def create_scroll_tab(title):
            tab = QtWidgets.QWidget()
            tab_layout = QtWidgets.QVBoxLayout(tab)
            tab_layout.setContentsMargins(0, 6, 0, 0)
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
            content = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(content)
            layout.setSpacing(16)
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setAlignment(QtCore.Qt.AlignTop)
            scroll.setWidget(content)
            tab_layout.addWidget(scroll)
            tabs.addTab(tab, title)
            return layout

        general_layout = create_scroll_tab("General")
        subtitle_layout = create_scroll_tab("Subtitle")
        context_tab_layout = create_scroll_tab("Context")
        about_layout = create_scroll_tab("About")

        general_top = QtWidgets.QHBoxLayout()
        general_top.setSpacing(16)
        general_top.setAlignment(QtCore.Qt.AlignTop)
        lang_box, lang = self.section("Language & Translation")
        lang.addWidget(self.section_label("Input Language (OCR + Translate From)"))
        lang.addWidget(self.input_lang_cb)
        lang.addWidget(self.section_label("Translate To"))
        lang.addWidget(self.trans_tgt_cb)
        lang.addWidget(self.section_label("Translator Engine"))
        lang.addWidget(self.engine_cb)
        for widget in [*self._ai_widgets, *self._opus_widgets]:
            lang.addWidget(widget)
        self._on_engine_change(self.engine_cb.currentIndex())
        general_top.addLayout(lang_box, 1)
        general_top.setAlignment(lang_box, QtCore.Qt.AlignTop)

        voice_box, voice_layout = self.section("Voice")
        voice_layout.addWidget(self.voice_enabled_cb)
        voice_layout.addWidget(self.section_label("TTS Engine"))
        voice_layout.addWidget(self.tts_provider_cb)
        voice_layout.addWidget(self.tts_model_label)
        voice_layout.addWidget(self.tts_model_cb)
        voice_layout.addWidget(self.tts_fields_widget)
        voice_layout.addWidget(self.tts_show_secrets_cb)
        voice_layout.addWidget(self.section_label("Language (follows Translate To)"))
        voice_layout.addWidget(self.voice_language_value)
        voice_layout.addWidget(self.section_label("Voice"))
        voice_layout.addWidget(self.voice_cb)
        voice_layout.addWidget(self.section_label("Voice Mode"))
        voice_layout.addWidget(self.voice_mode_cb)
        voice_layout.addWidget(self.tts_test_btn)
        voice_layout.addWidget(self.tts_status_label)
        voice_layout.addStretch()
        general_top.addLayout(voice_box, 1)
        general_top.setAlignment(voice_box, QtCore.Qt.AlignTop)
        general_layout.addLayout(general_top)

        general_bottom = QtWidgets.QHBoxLayout()
        general_bottom.setSpacing(16)
        mouse_box, mouse_layout = self.section("Mouse Subtitle & OCR Area")
        mouse_layout.addWidget(self.mouse_ocr_cb)
        mouse_area_row = QtWidgets.QHBoxLayout()
        mouse_width_col = QtWidgets.QVBoxLayout()
        mouse_width_col.addWidget(self.section_label("Area Width"))
        mouse_width_col.addWidget(self.mouse_ocr_width_input)
        mouse_height_col = QtWidgets.QVBoxLayout()
        mouse_height_col.addWidget(self.section_label("Area Height"))
        mouse_height_col.addWidget(self.mouse_ocr_height_input)
        mouse_area_row.addLayout(mouse_width_col)
        mouse_area_row.addLayout(mouse_height_col)
        mouse_layout.addLayout(mouse_area_row)
        mouse_layout.addWidget(self.section_label("Hold Key"))
        mouse_layout.addWidget(self.mouse_hold_key_input)
        mouse_layout.addWidget(self.edit_btn)
        general_bottom.addLayout(mouse_box, 1)

        app_box, app_layout = self.section("Application & Shortcuts")
        app_layout.addWidget(self.run_startup_cb)
        app_layout.addWidget(self.main_subtitle_cb)
        app_layout.addWidget(self.section_label("OCR Processing Device (Auto)"))
        app_layout.addWidget(self.ocr_device_value)
        app_layout.addWidget(self.section_label("Pause All OCR + Translation"))
        app_layout.addWidget(self.hotkey_input)
        app_layout.addWidget(self.section_label("Open Settings"))
        app_layout.addWidget(self.settings_hotkey_input)
        app_layout.addStretch()
        general_bottom.addLayout(app_box, 1)
        general_layout.addLayout(general_bottom)

        appearance_box, appearance = self.section("Subtitle Appearance")
        appearance_grid = QtWidgets.QGridLayout()
        appearance_grid.setHorizontalSpacing(18)
        appearance_grid.setVerticalSpacing(8)
        appearance_fields = [
            ("Font Size", self.font_size_input),
            ("Mouse Subtitle Font Size", self.mouse_font_size_input),
            ("Style", self.style_cb),
            ("Background Opacity", self.bg_alpha_input),
            ("Background Color", self.color_btn),
            ("Font Color", self.font_color_btn),
            ("Outline Width", self.stroke_width_input),
            ("Outline Color", self.outline_color_btn),
            ("Shadow Color", self.shadow_color_btn),
            ("Shadow Opacity", self.shadow_alpha_input),
            ("Shadow Offset", self.shadow_offset_input),
        ]
        for index, (label, control) in enumerate(appearance_fields):
            column = index % 3
            row = (index // 3) * 2
            appearance_grid.addWidget(self.section_label(label), row, column)
            appearance_grid.addWidget(control, row + 1, column)
        for column in range(3):
            appearance_grid.setColumnStretch(column, 1)
        appearance.addLayout(appearance_grid)
        subtitle_layout.addLayout(appearance_box)

        context_box, context_layout = self.section("Video / Game Context")
        context_layout.addWidget(self.context_enabled_cb)
        context_layout.addWidget(self.section_label("Context Mode"))
        context_layout.addWidget(self.context_mode_cb)
        context_layout.addWidget(self.section_label("Memory Length"))
        context_layout.addWidget(self.context_memory_input)
        context_layout.addWidget(
            self.section_label("Character & Terminology Dictionary")
        )
        context_layout.addWidget(self.context_dictionary_input)
        dictionary_help = QtWidgets.QLabel(
            "Format: source = preferred translation (one entry per line)"
        )
        dictionary_help.setObjectName("helpText")
        context_layout.addWidget(dictionary_help)
        context_layout.addWidget(self.context_game_rules_label)
        context_layout.addWidget(self.context_game_rules_input)
        context_layout.addWidget(self.context_game_rules_help)
        context_layout.addWidget(self.context_game_example_btn)
        context_tab_layout.addLayout(context_box)
        self._update_context_controls(self.context_enabled_cb.isChecked())

        # ===== SPACER =====

        # ===== ABOUT =====
        about_box, about = self.section("About")
        about_text = QtWidgets.QLabel()
        about_text.setText(
            "Create by GlorSub Community.<br/><b>App Version:</b> 1.0.0"
        )
        about.addWidget(about_text)
        about_layout.addLayout(about_box)

        # ===== ACTION BUTTONS =====
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()

        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.setMinimumHeight(38)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border-radius: 10px;
                padding: 8px 18px;
            }
            QPushButton:hover { background-color: #1493e3; }
        """)
        apply_btn.clicked.connect(
            self.apply_with_feedback
        )
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setMinimumHeight(38)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ea043;
                color: white;
                border-radius: 10px;
                padding: 8px 18px;
            }
            QPushButton:hover { background-color: #3fb950; }
        """)
        save_btn.clicked.connect(self.save_and_close)

        btn_row.addWidget(apply_btn)
        btn_row.addWidget(save_btn)
        root_layout.addLayout(btn_row)

    # ---------- LOGIC ----------
    def _show_settings_feedback(self, message, success=True):
        if not hasattr(self, "_feedback_toast"):
            self._feedback_toast = OutlinedToastLabel()
            self._feedback_toast.setWindowFlags(
                QtCore.Qt.Tool
                | QtCore.Qt.FramelessWindowHint
                | QtCore.Qt.WindowStaysOnTopHint
            )
            self._feedback_toast.setAttribute(QtCore.Qt.WA_ShowWithoutActivating)
            self._feedback_toast.setAttribute(QtCore.Qt.WA_TranslucentBackground)
            self._feedback_toast.setAlignment(QtCore.Qt.AlignCenter)
            self._feedback_toast.setFont(
                QtGui.QFont("Segoe UI", 10, QtGui.QFont.DemiBold)
            )
            self._feedback_shadow = QtWidgets.QGraphicsDropShadowEffect(
                self._feedback_toast
            )
            self._feedback_shadow.setBlurRadius(32)
            self._feedback_shadow.setOffset(0, 8)
            self._feedback_shadow.setColor(QtGui.QColor(0, 0, 0, 105))
            self._feedback_toast.setGraphicsEffect(self._feedback_shadow)
            self._feedback_timer = QtCore.QTimer(self)
            self._feedback_timer.setSingleShot(True)
            self._feedback_timer.timeout.connect(self._feedback_toast.hide)

        background = "#16a34a" if success else "#dc2626"
        border = "#4ade80" if success else "#f87171"
        icon = "\u2713" if success else "!"
        self._feedback_toast.setText(f"  {icon}   {message}  ")
        self._feedback_toast.setStyleSheet(
            "QLabel {"
            f"background-color: {background}; color: white;"
            f"border: 1px solid {border}; border-radius: 18px;"
            "padding: 14px 24px;"
            "}"
        )
        self._feedback_toast.adjustSize()
        anchor = self.frameGeometry()
        screen = screen_geometry_at(anchor.center().x(), anchor.center().y())
        x = screen.left() + (screen.width() - self._feedback_toast.width()) // 2
        y = screen.top() + (screen.height() - self._feedback_toast.height()) // 2
        self._feedback_toast.move(x, y)
        self._feedback_toast.show()
        self._feedback_toast.raise_()
        self._feedback_timer.start(2200 if success else 3500)

    def apply_with_feedback(self):
        try:
            self.apply_settings(show_message=False, silent=True)
            self._suppress_next_save_feedback = True
            self._show_settings_feedback("Settings applied successfully")
        except Exception as exc:
            self._suppress_next_save_feedback = False
            print(f"[SETTINGS APPLY ERROR] {exc}")
            self._show_settings_feedback(f"Apply failed: {exc}", success=False)

    def _update_context_controls(self, enabled):
        self.context_mode_cb.setEnabled(enabled)
        self.context_memory_input.setEnabled(enabled)
        self.context_dictionary_input.setEnabled(enabled)
        self._update_context_mode_controls()

    def _update_context_mode_controls(self, _index=None):
        game_mode = (
            self.context_enabled_cb.isChecked()
            and self.context_mode_cb.currentData() == "game"
        )
        self.context_game_rules_label.setVisible(game_mode)
        self.context_game_rules_input.setVisible(game_mode)
        self.context_game_rules_input.setEnabled(game_mode)
        self.context_game_rules_help.setVisible(game_mode)
        self.context_game_example_btn.setVisible(game_mode)
        self.context_game_example_btn.setEnabled(game_mode)

    def _insert_game_rules_example(self):
        current = self.context_game_rules_input.toPlainText().strip()
        if not current:
            self.context_game_rules_input.setPlainText(GAME_RULES_EXAMPLE)
            return
        if GAME_RULES_EXAMPLE not in current:
            self.context_game_rules_input.appendPlainText(
                "\n\n# Example rules\n" + GAME_RULES_EXAMPLE
            )

    def _on_theme_changed(self, _index=None):
        theme = self.theme_cb.currentData() or "dark"
        apply_ui_theme(theme)

    def _refresh_ocr_device_status(self):
        if self.ocr_device_value.text() != OCR_DEVICE_STATUS:
            self.ocr_device_value.setText(OCR_DEVICE_STATUS)

    def _sync_voice_to_translate_target(self, _index=None, saved_voice=None):
        translate_target = self.trans_tgt_cb.currentData()
        language = VOICE_LANGUAGE_BY_TRANSLATE_TARGET.get(translate_target)
        language_info = VOICE_OPTIONS.get(language)
        provider = self.tts_provider_cb.currentData() or "edge"
        details = TTS_PROVIDERS[provider]
        profile = self._tts_profile_drafts.setdefault(provider, {})
        current_voice = (
            saved_voice if saved_voice is not None
            else profile.get("voice", details.get("voice", ""))
        )

        self.voice_cb.blockSignals(True)
        self.voice_cb.clear()
        if not language_info:
            target_name = self.trans_tgt_cb.currentText() or "selected language"
            self.voice_language_value.setText(f"Voice unavailable for {target_name}")
            self.voice_cb.setEnabled(False)
            self.voice_enabled_cb.setChecked(False)
            self.voice_enabled_cb.setEnabled(False)
            self.voice_cb.blockSignals(False)
            return

        self.voice_language_value.setText(f"{language_info['label']} (automatic)")
        self.voice_cb.setEnabled(True)
        self.voice_enabled_cb.setEnabled(True)
        if provider == "edge":
            self.voice_cb.setEditable(False)
            for label, voice_id in language_info["voices"]:
                self.voice_cb.addItem(label, voice_id)
            voice_index = self.voice_cb.findData(current_voice)
            self.voice_cb.setCurrentIndex(max(0, voice_index))
        else:
            self.voice_cb.setEditable(True)
            if provider == "google":
                self.voice_cb.addItem("Automatic (language default)", "")
            for voice_id in details.get("voices", []):
                self.voice_cb.addItem(voice_id, voice_id)
            voice_index = self.voice_cb.findData(current_voice)
            if voice_index >= 0:
                self.voice_cb.setCurrentIndex(voice_index)
            else:
                self.voice_cb.setCurrentText(current_voice or "")
        profile["voice"] = current_voice or ""
        self.voice_cb.blockSignals(False)

    def choose_color(self):
        color = self._open_color_dialog(
            "Choose Background Color", self.settings.get("bg_color", [0, 0, 0])
        )
        if color.isValid():
            self.settings["bg_color"] = [color.red(), color.green(), color.blue()]
            self.color_btn.setStyleSheet(
                self._color_button_style(self.settings["bg_color"])
            )

    def choose_font_color(self):
        color = self._open_color_dialog(
            "Choose Font Color", self.settings.get("font_color", [255, 255, 255])
        )
        if color.isValid():
            self.settings["font_color"] = [color.red(), color.green(), color.blue()]
            # update preview on button
            self.font_color_btn.setStyleSheet(
                self._color_button_style(self.settings["font_color"])
            )

    def choose_shadow_color(self):
        color = self._open_color_dialog(
            "Choose Shadow Color", self.settings.get("shadow_color", [0, 0, 0])
        )
        if color.isValid():
            self.settings["shadow_color"] = [color.red(), color.green(), color.blue()]
            self.shadow_color_btn.setStyleSheet(
                self._color_button_style(self.settings["shadow_color"])
            )

    def apply_settings(self, show_message=True, silent=False):
        global cfg, translator, voice_speaker, worker
        global MOUSE_OCR_ENABLED, MOUSE_HOLD_KEY
        global MOUSE_OCR_WIDTH, MOUSE_OCR_HEIGHT

        MOUSE_OCR_ENABLED = self.mouse_ocr_cb.isChecked()
        cfg.setdefault("settings", {})
        ui_theme = self.theme_cb.currentData() or "dark"
        cfg["settings"]["ui_theme"] = ui_theme
        apply_ui_theme(ui_theme)
        cfg["settings"]["mouse_ocr_enabled"] = MOUSE_OCR_ENABLED
        MOUSE_OCR_WIDTH = self.mouse_ocr_width_input.value()
        MOUSE_OCR_HEIGHT = self.mouse_ocr_height_input.value()
        cfg["settings"]["mouse_ocr_width"] = MOUSE_OCR_WIDTH
        cfg["settings"]["mouse_ocr_height"] = MOUSE_OCR_HEIGHT
        cfg["settings"]["main_subtitle_enabled"] = (
            self.main_subtitle_cb.isChecked()
        )
        restore_main_subtitle_overlay()

        key_text = self.mouse_hold_key_input.text().strip()
        if key_text:
            MOUSE_HOLD_KEY = key_text.lower()
        cfg.setdefault("settings", {})
        cfg["settings"]["mouse_hold_key"] = MOUSE_HOLD_KEY

        voice_language = VOICE_LANGUAGE_BY_TRANSLATE_TARGET.get(
            self.trans_tgt_cb.currentData(), ""
        )
        tts_provider = self.tts_provider_cb.currentData() or "edge"
        self._save_tts_draft(tts_provider)
        tts_profile = self._tts_profile_drafts.get(tts_provider, {})
        voice = tts_profile.get("voice", "")
        voice_mode = self.voice_mode_cb.currentData() or "smart"
        voice_required = tts_provider != "google"
        voice_enabled = self.voice_enabled_cb.isChecked() and bool(
            voice_language and (voice or not voice_required)
        )
        cfg["tts_profiles"] = json.loads(json.dumps(self._tts_profile_drafts))
        protected_tts_secrets = {}
        for provider, fields in self._tts_secret_drafts.items():
            saved_fields = {
                key: protect_secret(value)
                for key, value in fields.items()
                if value
            }
            if saved_fields:
                protected_tts_secrets[provider] = saved_fields
        cfg["tts_secrets"] = protected_tts_secrets
        cfg["settings"].update({
            "voice_enabled": voice_enabled,
            "voice_language": voice_language,
            "voice": voice,
            "voice_mode": voice_mode,
            "tts_provider": tts_provider,
        })
        if voice_speaker is not None:
            provider_fields = dict(self._tts_secret_drafts.get(tts_provider, {}))
            for key, _label, is_secret in TTS_PROVIDERS[tts_provider].get("fields", []):
                if not is_secret:
                    provider_fields[key] = tts_profile.get(key, "")
            try:
                voice_speaker.configure(
                    voice_enabled,
                    voice_language,
                    voice,
                    voice_mode,
                    tts_provider,
                    tts_profile.get("model", ""),
                    provider_fields,
                )
            except Exception as exc:
                cfg["settings"]["voice_enabled"] = False
                self.voice_enabled_cb.setChecked(False)
                self._on_tts_test_result(False, str(exc))
                if not silent:
                    QtWidgets.QMessageBox.warning(
                        self, "TTS Configuration", f"Voice was disabled:\n{exc}"
                    )

        context_enabled = self.context_enabled_cb.isChecked()
        context_mode = self.context_mode_cb.currentData() or "video"
        context_memory_size = self.context_memory_input.value()
        context_dictionary = self.context_dictionary_input.toPlainText().strip()
        context_game_rules = self.context_game_rules_input.toPlainText().strip()
        cfg["settings"].update({
            "context_enabled": context_enabled,
            "context_mode": context_mode,
            "context_memory_size": context_memory_size,
            "context_dictionary": context_dictionary,
            "context_game_rules": context_game_rules,
        })
        if worker is not None:
            worker.configure_context(
                context_enabled,
                context_mode,
                context_memory_size,
                context_dictionary,
                context_game_rules,
            )

            
        self.settings["font_size"] = self.font_size_input.value()
        self.settings["bg_alpha"] = self.bg_alpha_input.value()
        self.settings["font_weight"] = self.font_weight_input.value()
        self.settings["mouse_font_size"] = self.mouse_font_size_input.value()
        # ensure font_color present
        if "font_color" not in self.settings:
            self.settings["font_color"] = [255, 255, 255]
        # read style selection
        sel_style = self.style_cb.itemData(self.style_cb.currentIndex()) if hasattr(self, 'style_cb') else self.settings.get('style','centered')
        self.settings['style'] = sel_style
        # read shadow/outline settings
        self.settings['shadow_alpha'] = int(self.shadow_alpha_input.value())
        self.settings['shadow_offset'] = int(self.shadow_offset_input.value())
        self.settings['stroke_width'] = int(self.stroke_width_input.value())
        if 'shadow_color' not in self.settings:
            # keep existing or default black
            self.settings['shadow_color'] = self.settings.get('shadow_color', [0,0,0])

        overlay_settings = {
            "font_size": self.settings["font_size"],
            "mouse_font_size": self.settings["mouse_font_size"],
            "font_weight": self.settings["font_weight"],
            "bg_alpha": self.settings["bg_alpha"],
            "bg_color": QtGui.QColor(*self.settings["bg_color"]),
            "font_color": QtGui.QColor(*self.settings["font_color"]),

            # 🔥 OUTLINE
            "outline_color": self.settings["outline_color"],
            "stroke_width": self.settings.get("stroke_width", 4),

            # 🔥 SHADOW (THIẾU TRƯỚC ĐÓ)
            "shadow_color": self.settings.get("shadow_color", [0, 0, 0]),
            "shadow_alpha": self.settings.get("shadow_alpha", 200),
            "shadow_offset": self.settings.get("shadow_offset", 4),

            "style": self.settings["style"],
        }

        self.overlay.update_settings(overlay_settings)

        cfg["settings"].update({
            "font_size": self.settings["font_size"],
            "bg_alpha": self.settings["bg_alpha"],
            "bg_color": self.settings["bg_color"],
            "font_color": self.settings["font_color"],
            "mouse_font_size": self.settings["mouse_font_size"],
            "style": self.settings.get("style", "centered"),
            "shadow_color": self.settings.get("shadow_color", [0,0,0]),
            "shadow_alpha": self.settings.get("shadow_alpha", 200),
            "shadow_offset": self.settings.get("shadow_offset", 4),
            "stroke_width": self.settings.get("stroke_width", 4),
            "font_weight": self.settings["font_weight"],
            "outline_color": self.settings["outline_color"],
        })

        new_ocr = self.input_lang_cb.currentData() or "en"
        new_src = OCR_TO_TRANSLATE_LANGUAGE.get(new_ocr, "en")
        new_tgt = self.trans_tgt_cb.currentData()

        cfg["translate_source"] = new_src
        cfg["translate_target"] = new_tgt
    
        if cfg.get("ocr_lang") != new_ocr:
            # OCRWorker observes this change and loads the model in its own
            # thread, keeping Settings responsive during first-time downloads.
            cfg["ocr_lang"] = new_ocr
        
        # ===== TRANSLATOR ENGINE =====
        new_engine = self.engine_cb.itemData(self.engine_cb.currentIndex())
        cfg["translate_engine"] = new_engine
        cfg["opus_mt_model_dir"] = self.opus_model_input.text().strip()
        self._save_ai_draft(new_engine)
        cfg["ai_models"] = dict(self._ai_model_drafts)
        protected_keys = {}
        try:
            for provider, key in self._ai_key_drafts.items():
                if key:
                    protected_keys[provider] = protect_secret(key)
            cfg["ai_api_keys"] = protected_keys
            if new_engine == "opus_mt":
                translator.configure("opus_mt", model=cfg["opus_mt_model_dir"])
            elif new_engine == "google":
                translator.configure("google")
            else:
                translator.configure(
                    new_engine,
                    self._ai_key_drafts.get(new_engine, ""),
                    self._ai_model_drafts.get(new_engine, ""),
                )
        except Exception as exc:
            if new_engine == "opus_mt":
                self._on_opus_test_result(False, str(exc))
            else:
                self._on_ai_test_result(False, str(exc))
            if not silent:
                QtWidgets.QMessageBox.warning(
                    self,
                    "AI Translator",
                    f"Could not activate the selected AI engine:\n{exc}\n\n"
                    "Please correct the model or provider settings.",
                )
            if new_engine == "opus_mt":
                raise
            translator.configure("google")

        # --- HOTKEY: Pause OCR ---
        new_hotkey = self.hotkey_input.text().strip()
        if new_hotkey:
            cfg["hotkey_pause"] = new_hotkey
        # --- HOTKEY: Settings Panel ---
        new_settings_hotkey = self.settings_hotkey_input.text().strip()
        if new_settings_hotkey:
            cfg["hotkey_settings"] = new_settings_hotkey

        if show_message:
            QtWidgets.QMessageBox.information(
                self,
                "Settings Applied",
                "Settings have been applied successfully."
            )
    def save_and_close(self):
        global SETTINGS_SNAPSHOT
        suppress_feedback = getattr(self, "_suppress_next_save_feedback", False)
        try:
            self.apply_settings(show_message=False, silent=True)
            save_config(cfg)
        except Exception as exc:
            self._suppress_next_save_feedback = False
            print(f"[SETTINGS SAVE ERROR] {exc}")
            self._show_settings_feedback(f"Save failed: {exc}", success=False)
            return

        self._suppress_next_save_feedback = False
        SETTINGS_SNAPSHOT = None
        self.hide()
        if not suppress_feedback:
            self._show_settings_feedback("Settings saved successfully")

    def on_edit_toggled(self, checked):
        global edit_exit_overlay
        global EDIT_MODE_ACTIVE
        global EDIT_SNAPSHOT_RED, EDIT_SNAPSHOT_YELLOW

        if checked:
            # ================== ENTER EDIT MODE ==================
            EDIT_MODE_ACTIVE = True

            # 🔒 Snapshot trạng thái hiện tại
            EDIT_SNAPSHOT_RED = tuple(cfg.get("red_region", RED_REGION))
            EDIT_SNAPSHOT_YELLOW = tuple(cfg.get("yellow_region", YELLOW_REGION))

            self.edit_btn.setText("Editing...")
            self.hide()

            # 🌫 BACKDROP (LUÔN Ở DƯỚI)
            edit_backdrop.show()
            edit_backdrop.raise_()

            # 🔴 OCR REGION EDITOR
            self.editor.region = list(RED_REGION)
            self.editor.update_geometry()
            self.editor.show()
            self.editor.raise_()

            # 🟡 SUBTITLE OVERLAY
            self.overlay.set_edit_mode(True)
            self.overlay.raise_()

            # ❌ / ✅ CONTROL BUTTONS
            if edit_exit_overlay:
                edit_exit_overlay.show()
                edit_exit_overlay.raise_()

        else:
            # ================== EXIT EDIT MODE ==================
            EDIT_MODE_ACTIVE = False

            self.edit_btn.setText("Edit Subtitle & OCR Region")

            # 🔴 Hide editor
            self.editor.hide()

            # 🟡 Restore overlay
            self.overlay.set_edit_mode(False)

            # ❌ / ✅ Buttons
            if edit_exit_overlay:
                edit_exit_overlay.hide()

            # 🌫 BACKDROP – BẮT BUỘC HIDE (KHÔNG ĐƯỢC PHỤ THUỘC IF)
            edit_backdrop.hide()

         #-- save edited region ---   
    def on_run_startup_toggled(self, checked: bool):
        cfg["run_on_startup"] = checked
        set_run_on_startup(checked)
        save_config(cfg)
        # inform user

    def eventFilter(self, obj, event):

        # ===== HOTKEY INPUT ONLY =====
        hotkey_inputs = tuple(
            control
            for control in (
                getattr(self, "hotkey_input", None),
                getattr(self, "settings_hotkey_input", None),
                getattr(self, "mouse_hold_key_input", None),
            )
            if control is not None
        )
        if obj in hotkey_inputs:
            if event.type() == QtCore.QEvent.KeyPress:
                if obj is getattr(self, "mouse_hold_key_input", None):
                    hotkey = qt_keyevent_to_mouse_hold_key(event)
                else:
                    hotkey = qt_keyevent_to_hotkey(event)

                if hotkey:
                    obj.setText(hotkey.upper())

                return True  # chặn Ctrl+C, Ctrl+V...

            if event.type() in (
                QtCore.QEvent.KeyRelease,
                QtCore.QEvent.Shortcut,
                QtCore.QEvent.ShortcutOverride
            ):
                return True

        # ===== WINDOW DRAGGING (custom title bar only) =====
        if bool(obj.property("settingsTitleDrag")):
            if event.type() == QtCore.QEvent.MouseButtonPress:
                if event.button() == QtCore.Qt.LeftButton:
                    self._drag_candidate = True
                    self._drag_active = False
                    self._drag_press_pos = event.globalPos()
                    self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                    return False

            elif event.type() == QtCore.QEvent.MouseMove:
                if self._drag_candidate and self._drag_pos:
                    if not (event.buttons() & QtCore.Qt.LeftButton):
                        self._drag_candidate = False
                        self._drag_active = False
                        return False
                    if not self._drag_active:
                        distance = (event.globalPos() - self._drag_press_pos).manhattanLength()
                        if distance < QtWidgets.QApplication.startDragDistance():
                            return False
                        self._drag_active = True
                    self.move(event.globalPos() - self._drag_pos)
                    return True

            elif event.type() == QtCore.QEvent.MouseButtonRelease:
                was_dragging = self._drag_active
                self._drag_candidate = False
                self._drag_active = False
                self._drag_pos = None
                self._drag_press_pos = None
                return was_dragging

        return super().eventFilter(obj, event)
# ====================== SETTINGS TOGGLE (HOTKEY) ======================



def toggle_settings_panel():
    print("[HOTKEY] F10 pressed → toggle_settings_panel() called")

    try:
        QtCore.QMetaObject.invokeMethod(
            settings_panel,
            "toggle_from_hotkey",
            QtCore.Qt.QueuedConnection
        )
    except Exception as e:
        print("[HOTKEY ERROR] invokeMethod failed:", e)




# ====================== SYSTEM TRAY ======================
class SystemTray(QtWidgets.QSystemTrayIcon):
    def __init__(self, parent, overlay, settings_panel):
        icon_path = resource_path("Icon.ico")
        icon = QtGui.QIcon(icon_path) if os.path.exists(icon_path) else QtGui.QIcon()

        super().__init__(icon, parent)
        self.setToolTip("GloSub")

        self.overlay = overlay
        self.settings_panel = settings_panel

        menu = QtWidgets.QMenu()

        toggle_action = menu.addAction("Pause / Resume OCR + Translation")
        toggle_action.triggered.connect(self.toggle_overlay)

        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self.show_settings)

        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(QtWidgets.qApp.quit)

        self.setContextMenu(menu)
        self.show()   # ✅ SHOW SAU KHI INIT

    
    def toggle_overlay(self):
        toggle_ocr_and_subtitle()

    def show_settings(self):
        global SETTINGS_SNAPSHOT
        SETTINGS_SNAPSHOT = json.loads(json.dumps(cfg))
        self.settings_panel.show()
        self.settings_panel.raise_()
        self.settings_panel.activateWindow()
        overlay.lower()

# ====================== GLOBAL ESC HANDLER (EDIT MODE) ======================
class GlobalEscFilter(QtCore.QObject):
    def eventFilter(self, obj, event):
        if not EDIT_MODE_ACTIVE:
            return False

        if event.type() == QtCore.QEvent.KeyPress:
            if event.key() == QtCore.Qt.Key_Escape:
                print("[EDIT MODE] ESC → exit edit mode")

                try:
                    edit_exit_overlay.on_exit()
                except Exception as e:
                    print("[ESC ERROR]", e)

                return True  # NUỐT ESC

        return False

# ====================== MAIN ======================
def main():
    
    global RED_REGION, YELLOW_REGION, cfg
    load_i18n()
    # initialize translator here with safe fallback
    global translator
    try:
        translator = SmartTranslator()
        try:
            configure_translator(cfg)
        except Exception as exc:
            print(f"[Translator] Configuration unavailable: {exc}")
            if cfg.get("translate_engine") != "opus_mt":
                translator.configure("google")
    except Exception as e:
        print("[Translator] Initialization failed:", e)

        class _FallbackTranslator:
            engine_name = "unavailable"
            def translate(self, text, src, tgt):
                return text
            def set_engine(self, *a, **k):
                pass
            configure = set_engine
            pause = set_engine
            resume = set_engine

        translator = _FallbackTranslator()

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("GloSub")
    esc_filter = GlobalEscFilter()
    app.installEventFilter(esc_filter)

    # ====================== GLOBAL RIGHT-CLICK BLOCKER ======================

    # ===== HIDDEN HOST WINDOW (ẨN TASKBAR ICON) =====
    host = QtWidgets.QWidget()
    host.setWindowFlags(
        QtCore.Qt.Tool |                # ❌ không hiện taskbar
        QtCore.Qt.FramelessWindowHint
    )
    host.setAttribute(QtCore.Qt.WA_DontShowOnScreen, True)
    host.hide()

    # ===== Mouse OCR hooks =====

    def _mouse_listener():
        def _on_move(x, y):
            on_mouse_move(x, y)

        listener = mouse.Listener(on_move=_on_move)
        listener.daemon = True
        listener.start()

    _mouse_listener()

    # ===== Application Icon (Taskbar / Alt+Tab) =====
    icon_path = resource_path("Icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))
    apply_ui_theme(cfg.get("settings", {}).get("ui_theme", "dark"))

    

    # keep application running even if all windows are closed (tray-based app)
    app.setQuitOnLastWindowClosed(False)

    # read updated config values
    RED_REGION = tuple(cfg.get("red_region", DEFAULT_RED_REGION))
    YELLOW_REGION = tuple(cfg.get("yellow_region", DEFAULT_YELLOW_REGION))

    global overlay
    overlay = SubtitleOverlay(YELLOW_REGION, {
        "font_size": cfg["settings"].get("font_size", 28),
        "mouse_font_size": cfg["settings"].get("mouse_font_size", 22),
        "bg_alpha": cfg["settings"].get("bg_alpha", 150),
        "bg_color": cfg["settings"].get("bg_color", [0, 0, 0]),
        "font_color": cfg["settings"].get("font_color", [255, 255, 255]),
        "style": cfg["settings"].get("style", "centered"),
        "shadow_color": cfg["settings"].get("shadow_color", [0, 0, 0]),
        "shadow_alpha": cfg["settings"].get("shadow_alpha", 200),
        "shadow_offset": cfg["settings"].get("shadow_offset", 4),
        "stroke_width": cfg["settings"].get("stroke_width", 4),
    })
    global mouse_ocr_preview
    mouse_ocr_preview = MouseOCRPreview()
    # ====================== CONFIGURABLE HOLD-KEY POLLING TIMER ======================
    mouse_hold_timer = QtCore.QTimer()
    mouse_hold_timer.timeout.connect(update_mouse_hold_state)
    mouse_hold_timer.start(30)  # 30ms

    if cfg.get("settings", {}).get("main_subtitle_enabled", True):
        overlay.show()
        overlay.update_text(tr("HELLO"))
    else:
        overlay.update_text("")
        overlay.hide()

    # ===== Edit Mode Backdrop (dark background) =====
    global edit_backdrop
    edit_backdrop = EditModeBackdrop()
    edit_backdrop.hide()

    editor = OCRRegionEditor(RED_REGION)

    def refresh_monitor_layout():
        edit_backdrop.setGeometry(virtual_desktop_geometry())
        overlay.set_base_region(tuple(cfg.get("yellow_region", YELLOW_REGION)))
        editor.region = list(cfg.get("red_region", RED_REGION))
        editor.update_geometry()
        print(
            f"[DISPLAY] {len(QtWidgets.QApplication.screens())} monitor(s), "
            f"virtual desktop={virtual_desktop_geometry().getRect()}"
        )

    def register_screen(screen):
        try:
            screen.geometryChanged.connect(
                lambda _geometry: QtCore.QTimer.singleShot(0, refresh_monitor_layout)
            )
        except Exception:
            pass
        QtCore.QTimer.singleShot(0, refresh_monitor_layout)

    for connected_screen in QtWidgets.QApplication.screens():
        register_screen(connected_screen)
    app.screenAdded.connect(register_screen)
    app.screenRemoved.connect(
        lambda _screen: QtCore.QTimer.singleShot(0, refresh_monitor_layout)
    )

    # expose worker as module-global so SettingsPanel can pause/resume it safely
    global worker
    worker = OCRWorker(CAPTURE_FPS)
    worker.subtitle_ready.connect(overlay.update_text)
    worker.subtitle_move.connect(overlay.move_near_mouse)
    global voice_speaker
    voice_settings = cfg.get("settings", {})
    tts_provider, tts_profile, tts_fields = get_tts_runtime_config(cfg)
    voice_speaker = VoiceSpeaker(
        enabled=voice_settings.get("voice_enabled", False),
        language=voice_settings.get("voice_language", "vi-VN"),
        voice=tts_profile.get(
            "voice", voice_settings.get("voice", "vi-VN-HoaiMyNeural")
        ),
        mode=voice_settings.get("voice_mode", "smart"),
        provider=tts_provider,
        model=tts_profile.get("model", ""),
        provider_fields=tts_fields,
    )
    worker.subtitle_ready.connect(voice_speaker.speak)
    worker.start()   # ✅ START DUY NHẤT 1 LẦN
    
    # ===== SETTINGS PANEL =====

    global settings_panel
    settings_panel = SettingsPanel(overlay, editor)
    # ===== Edit Mode Exit Button (Floating X) =====
    global edit_exit_overlay

    def _exit_edit_mode():
        global RED_REGION, YELLOW_REGION
        global EDIT_SNAPSHOT_RED, EDIT_SNAPSHOT_YELLOW
        global EDIT_MODE_ACTIVE 

        EDIT_MODE_ACTIVE = False
        # 🔁 Restore saved snapshot
        if EDIT_SNAPSHOT_RED:
            RED_REGION = EDIT_SNAPSHOT_RED
            cfg["red_region"] = EDIT_SNAPSHOT_RED

        if EDIT_SNAPSHOT_YELLOW:
            YELLOW_REGION = EDIT_SNAPSHOT_YELLOW
            cfg["yellow_region"] = EDIT_SNAPSHOT_YELLOW

        # Update editor & overlay immediately
        editor.region = list(RED_REGION)
        editor.update_geometry()

        overlay.set_base_region(YELLOW_REGION)

        settings_panel.edit_btn.setChecked(False)
        settings_panel.show()
        settings_panel.raise_()
        edit_backdrop.hide()



    def _confirm_edit_mode():
        global EDIT_MODE_ACTIVE  
        EDIT_MODE_ACTIVE = False  
        # Có thể thêm validate / save nếu cần
        settings_panel.edit_btn.setChecked(False)
        settings_panel.show()
        settings_panel.raise_()
        edit_backdrop.hide()

    edit_exit_overlay = EditModeControlOverlay(
        on_exit=_exit_edit_mode,
        on_confirm=_confirm_edit_mode
    )

    settings_panel.settings_changed.connect(lambda s: overlay.update_settings(s))
    
    if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
        QtWidgets.QMessageBox.critical(
            None,
            "System Tray",
            "System tray is not available on this system."
        )
        sys.exit(1)

    global tray
    tray = SystemTray(host, overlay, settings_panel)
# ====================== REGISTER GLOBAL HOTKEYS (WINAPI) ======================
    global hotkey_pause, hotkey_settings

    try:
        hotkey_pause = WinHotkey(
            1,
            cfg.get("hotkey_pause", "f8")
        )
        hotkey_pause.activated.connect(
            lambda: QtCore.QTimer.singleShot(0, toggle_ocr_and_subtitle)
        )

        hotkey_settings = WinHotkey(
            2,
            cfg.get("hotkey_settings", "f10")
        )
        hotkey_settings.activated.connect(
            lambda: QtCore.QTimer.singleShot(0, toggle_settings_panel)
        )

        print("[HOTKEY] WinAPI hotkeys registered")

    except Exception as e:
        print("[HOTKEY ERROR]", e)

    # ====================== CLEANUP ON EXIT ======================
    def on_exit():
        try:
            worker.stop()
            worker.wait(1500)
        except Exception:
            pass
        try:
            voice_speaker.stop()
        except Exception:
            pass
        release_single_instance()

    app.aboutToQuit.connect(on_exit)
    print("[APP] Starting Qt event loop...")
    sys.exit(app.exec_())

if __name__ == "__main__":
    if "--self-test" in sys.argv:
        from release_checks import main as release_self_test
        sys.exit(release_self_test([arg for arg in sys.argv[1:] if arg != "--self-test"]))
    main()
