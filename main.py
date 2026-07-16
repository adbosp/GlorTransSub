import sys
import os
import json
import time
import hashlib
import math
import asyncio
import queue
import tempfile
from collections import deque
from pynput import mouse
import re
import numpy as np
# PyTorch must load its Windows DLLs before PyQt5. With current releases,
# importing Qt first can make c10.dll fail with WinError 1114.
import torch
from PyQt5 import QtWidgets, QtGui, QtCore
from PIL import ImageGrab
from smart_translator import SmartTranslator
import smart_translator
from win_hotkey import WinHotkey
import threading
import winreg
try:
    import cv2
except Exception:
    cv2 = None

# ====================== SYSTEM LANGUAGE ======================
import locale

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
# ====================== APP STYLESHEET ======================    
APP_STYLESHEET = """
QWidget {
    background-color: #1e1e1e;
    color: #eaeaea;
    font-family: Segoe UI, Arial;
    font-size: 13px;
}

QLabel {
    color: #cfcfcf;
}

QSpinBox, QComboBox {
    background-color: #2b2b2b;
    border: 1px solid #3c3c3c;
    border-radius: 8px;
    padding-left: 10px;
    padding-right: 30px;
    min-height: 36px;
    line-height: 36px;
}

QComboBox QAbstractItemView {
    background-color: #2b2b2b;
    selection-background-color: #007acc;
    padding: 6px;
}

QComboBox QAbstractItemView::item {
    height: 32px;
}

QSlider {
    min-height: 26px;
}

QSlider::groove:horizontal {
    height: 8px;
    background: #333;
    border-radius: 4px;
}

QSlider::handle:horizontal {
    background: #00c8ff;
    width: 18px;
    height: 18px;
    margin: -6px 0;
    border-radius: 9px;
}

QPushButton {
    background-color: #2d2d2d;
    border: 1px solid #3c3c3c;
    border-radius: 10px;
    padding: 10px 18px;
}

QPushButton:hover {
    background-color: #3a3a3a;
}

QPushButton:checked {
    background-color: #005f87;
}
QScrollBar:vertical {
    background: #1e1e1e;
    width: 10px;
    margin: 4px 2px;
}

QScrollBar::handle:vertical {
    background: #555;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #777;
}

QScrollBar::add-line,
QScrollBar::sub-line {
    height: 0px;
}

"""
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

    QtCore.QTimer.singleShot(0, overlay.reset_to_base_region)
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
CONFIG_FILE = "subtitle_config.json"
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
    if enable:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
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
    global worker, overlay

    if worker is None or overlay is None:
        return

    worker.toggle()

    if worker.running:
        overlay.show()
        overlay.update_text("Hello World!")
        # 🔥 ÉP REFRESH UI
        overlay.raise_()
        overlay.update()
        

    else:
        overlay.reset_to_base_region()
        overlay.update_text("")
        overlay.hide()
        mouse_ocr_preview.hide()

        
def should_follow_mouse() -> bool:
    """
    🔥 SINGLE DECISION POINT
    """
    if MOUSE_MODE == "hold":
        if not is_ctrl_pressed():
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
def is_ctrl_pressed():
    return windll.user32.GetAsyncKeyState(0x11) & 0x8000
# ====================== CTRL HOLD STATE TRACK ======================
def update_mouse_hold_state():
    global MOUSE_FOLLOW_ACTIVE, mouse_pos, mouse_last_move_time, mouse_idle_triggered

    if MOUSE_MODE != "hold":
        return

    if is_ctrl_pressed():
        if not MOUSE_FOLLOW_ACTIVE:
            MOUSE_FOLLOW_ACTIVE = True
            print("[MOUSE] Ctrl DOWN → FOLLOW ON")

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
            print("[MOUSE] Ctrl UP → FOLLOW OFF")

            QtCore.QTimer.singleShot(0, overlay.reset_to_base_region)
            QtCore.QTimer.singleShot(0, mouse_ocr_preview.hide)


def frame_hash(img: np.ndarray) -> str:
    return hashlib.md5(img.tobytes()).hexdigest()


def normalize_text(text: str) -> str:
    # lowercase and remove punctuation for caching/normalization
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


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
    global reader, reader_language

    if reader is not None and reader_language == lang:
        return

    import easyocr

    use_gpu = torch.cuda.is_available()
    print(f"[OCR] Using {'GPU' if use_gpu else 'CPU'}")

    new_reader = easyocr.Reader([lang], gpu=use_gpu, verbose=False)
    reader = new_reader
    reader_language = lang

# ====================== I18N LOAD ======================
I18N = {}

def load_i18n():
    global I18N
    try:
        path = os.path.join(os.path.dirname(__file__), "i18n.json")
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
            "outline_color": [0, 0, 0],
            "voice_enabled": False,
            "voice_language": "vi-VN",
            "voice": "vi-VN-HoaiMyNeural",
            "context_enabled": False,
            "context_mode": "video",
            "context_memory_size": 10,
            "context_dictionary": "",
            "context_game_rules": ""
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
if "translate_target" not in cfg:
    cfg["translate_target"] = get_default_translate_target()
if "translate_engine" not in cfg:
    cfg["translate_engine"] = "google"
if "hotkey_pause" not in cfg:
    cfg["hotkey_pause"] = "F8"
if "hotkey_settings" not in cfg:
    cfg["hotkey_settings"] = "F10"

# Input language is the single source of truth for both OCR and translation.
cfg["translate_source"] = OCR_TO_TRANSLATE_LANGUAGE.get(cfg["ocr_lang"], "en")

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


class VoiceSpeaker:
    """Generate and play Edge TTS speech without blocking the Qt/OCR threads."""

    def __init__(self, enabled=False, language="vi-VN", voice="vi-VN-HoaiMyNeural"):
        self.enabled = bool(enabled)
        self.language = language
        self.voice = voice
        self._queue = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, name="VoiceSpeaker", daemon=True)
        self._thread.start()

    def configure(self, enabled, language, voice):
        self.enabled = bool(enabled)
        self.language = language
        self.voice = voice
        if not self.enabled:
            self._clear_pending()
            try:
                import pygame
                pygame.mixer.music.stop()
            except Exception:
                pass

    def speak(self, text):
        text = (text or "").strip()
        if not self.enabled or not text:
            return

        # Realtime subtitles should speak the newest result, not build a long
        # backlog when OCR changes faster than audio playback.
        self._clear_pending()
        try:
            self._queue.put_nowait((text, self.voice))
        except queue.Full:
            pass

    def _clear_pending(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    def _run(self):
        try:
            import edge_tts
            import pygame

            pygame.mixer.init()
        except Exception as exc:
            print("[VOICE] Initialization failed:", exc)
            return

        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:
                break

            text, voice = item
            audio_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as audio_file:
                    audio_path = audio_file.name

                asyncio.run(edge_tts.Communicate(text, voice).save(audio_path))
                if not self.enabled or self._stop_event.is_set():
                    continue

                pygame.mixer.music.load(audio_path)
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy() and not self._stop_event.wait(0.05):
                    pass
                pygame.mixer.music.unload()
            except Exception as exc:
                print("[VOICE ERROR]", exc)
            finally:
                if audio_path:
                    try:
                        os.remove(audio_path)
                    except OSError:
                        pass

        try:
            pygame.mixer.music.stop()
            pygame.mixer.quit()
        except Exception:
            pass

    def stop(self):
        self.enabled = False
        self._stop_event.set()
        self._clear_pending()
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        self._thread.join(timeout=2.0)


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

        screen = QtWidgets.QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())

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
        self.hide()

    def show_at(self, x: int, y: int, width: int, height: int):
        self._width = width
        self._height = height
        geometry = QtCore.QRect(
            x - width // 2,
            y - height // 2,
            width,
            height,
        )
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
        painter.drawText(label_rect, QtCore.Qt.AlignCenter, "OCR + TRANSLATE AREA")

        size_rect = QtCore.QRectF(10, self.height() - 34, 112, 24)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 170))
        painter.drawRoundedRect(size_rect, 6, 6)
        painter.setPen(QtGui.QColor(220, 245, 255))
        painter.drawText(
            size_rect,
            QtCore.Qt.AlignCenter,
            f"{self._width} x {self._height} px",
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
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        x = screen.center().x() - self.width() // 2
        y = 24
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
        # expand overlay horizontally to full screen width so styles can
        # stretch to screen edges while keeping vertical placement
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        screen_w = screen.width()
        self.setGeometry(0, y1, screen_w, y2 - y1)
        self.follow_mouse = False
        # store base/top geometry so we can auto-expand height anchored to bottom
        self.base_top = int(y1)
        self.base_height = int(y2 - y1)
        self.screen_w = screen_w

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
    def reset_to_base_region(self):
        self.follow_mouse = False
        self.setFixedWidth(self.screen_w)
        self.setGeometry(
            0,
            self.base_top,
            self.screen_w,
            self.base_height
        )
        self.update()

    def move_near_mouse(self, x, y):
        if not self.follow_mouse:
            self.follow_mouse = True
            self.setFixedWidth(600)   # thử 400–600
            self.adjustSize()

        screen = QtWidgets.QApplication.primaryScreen().geometry()

        new_x = x + MOUSE_SUBTITLE_OFFSET_X
        new_y = y + MOUSE_SUBTITLE_OFFSET_Y

        if new_x + self.width() > screen.width():
            new_x = x - self.width() - 10
        if new_y + self.height() > screen.height():
            new_y = y - self.height() - 10

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
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        screen_w = screen.width()
        # keep full-width overlay starting at x=0, update only y and keep height
        self.setGeometry(0, int(new_top_left.y()), screen_w, self.height())
        event.accept()

    def mouseReleaseEvent(self, event):
        if not self.edit_mode:
            return
        self._drag_pos = None
        # update stored yellow region to current geometry
        g = self.geometry()
        global cfg
        screen = QtWidgets.QApplication.primaryScreen().geometry()
        screen_w = screen.width()
        # ensure stored region is balanced horizontally (0..screen_w)
        cfg["yellow_region"] = (0, g.top(), screen_w, g.top() + g.height())
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
        if new_top < 0:
            new_top = 0

        if (self.geometry().top() != new_top) or (self.height() != final_h):
            self.setGeometry(0, new_top, self.width(), final_h)

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

        screen = QtWidgets.QApplication.primaryScreen().geometry()
        sw, sh = screen.width(), screen.height()

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
        nl = max(0, min(nl, sw - min_w))
        nt = max(0, min(nt, sh - min_h))
        nr = max(nl + min_w, min(nr, sw))
        nb = max(nt + min_h, min(nb, sh))

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
        # simple cache for translations keyed by normalized text
        self._translate_cache = {}
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
            self._translate_cache.clear()

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

        if not enabled:
            if normalized in self._translate_cache:
                return self._translate_cache[normalized]
            translated = translator.translate(text, src, tgt)
            if translated:
                self._translate_cache[normalized] = translated
            return translated

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
        global RED_REGION, reader

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
            try:
                # ===== Choose OCR region (SINGLE DECISION POINT) =====
                if should_follow_mouse():
                    idle_time = time.time() - mouse_last_move_time
                    mx, my = mouse_pos

                    global mouse_idle_triggered
                    if not mouse_idle_triggered:
                        mouse_idle_triggered = True
                        print(f"[MOUSE] FOLLOW ON (idle {idle_time:.1f}s)")
                    half_width = MOUSE_OCR_WIDTH // 2
                    half_height = MOUSE_OCR_HEIGHT // 2

                    x1 = max(0, mx - half_width)
                    y1 = max(0, my - half_height)
                    x2 = mx + half_width
                    y2 = my + half_height
                else:
                    mouse_idle_triggered = False
                    x1, y1, x2, y2 = RED_REGION
                    
                if not self.running or self._stop:
                    continue
                # ===== Capture screen region =====
                pil_img = ImageGrab.grab(bbox=(int(x1), int(y1), int(x2), int(y2)))
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

                    result = reader.readtext(img_for_ocr, detail=0)
                    text = " ".join(result)

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

                        # ===== EMIT SUBTITLE =====
                        if translated:
                            # 1️⃣ set text trước → Qt resize
                            self.subtitle_ready.emit(translated)

                            # 2️⃣ move sau khi đã có text
                            if should_follow_mouse():
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
class SettingsPanel(QtWidgets.QWidget):
    # ===== Window Dragging =====
    _drag_active = False
    _drag_candidate = False
    _drag_pos = None
    _drag_press_pos = None
    # ===== Signals =====    
    settings_changed = QtCore.pyqtSignal(dict)
    engine_switch_result = QtCore.pyqtSignal(bool, str)
    
    def _on_engine_change(self, index):
        engine = self.engine_cb.itemData(index)
        # 🔒 Currently only Google is supported
        # Hook for future engines
        pass

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
        self.overlay.base_top = YELLOW_REGION[1]
        self.overlay.base_height = YELLOW_REGION[3] - YELLOW_REGION[1]
        self.overlay.setGeometry(
            0,
            self.overlay.base_top,
            self.overlay.screen_w,
            self.overlay.base_height
        )

        # 🔁 Restore OCR editor
        self.editor.region = list(RED_REGION)
        self.editor.update_geometry()

        # 🔁 Restore visual settings
        self.overlay.update_settings(cfg["settings"])
        context_settings = cfg.get("settings", {})
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

        title_label = QtWidgets.QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: 600;
                color: #ffffff;
            }
        """)
        box.addWidget(title_label)

        frame = QtWidgets.QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border-radius: 14px;
            }
        """)

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
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.settings["outline_color"] = [
                color.red(),
                color.green(),
                color.blue()
            ]
        oc = self.settings.get("outline_color", [0,0,0])
        self.outline_color_btn.setStyleSheet(
            f"background-color: rgb({oc[0]}, {oc[1]}, {oc[2]}); border-radius:8px;"
        )


    def section_label(self, text):
        lbl = QtWidgets.QLabel(text)
        lbl.setContentsMargins(2, 6, 2, 4)
        lbl.setStyleSheet("color:#cfcfcf;")
        return lbl

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
        # ===== CUSTOM TITLE BAR =====
        title_bar = QtWidgets.QHBoxLayout()
        title_bar.setContentsMargins(4, 4, 4, 4)

        title_label = QtWidgets.QLabel(f"⚙ {tr('SETTINGS_TITLE')}")
        title_label.setStyleSheet("font-weight:600; font-size:14px;")
        # enable mouse tracking for dragging
        title_label.setCursor(QtCore.Qt.SizeAllCursor)
        title_label.installEventFilter(self)

        btn_close = QtWidgets.QPushButton("✕")
        btn_close.setFixedSize(28, 28)
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #ff5c5c;
                font-size: 16px;
                border: none;
            }
            QPushButton:hover {
                background: #2d2d2d;
                border-radius: 6px;
            }
        """)
        btn_close.clicked.connect(self.on_close_clicked)

        title_bar.addWidget(title_label)
        title_bar.addStretch()
        title_bar.addWidget(btn_close)
        # ===== Window Icon =====
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QtGui.QIcon(icon_path))
        # make settings panel wider to avoid cramped controls (4 columns)
        # reduce vertical size by 300 as requested
        self.resize(840, 760)
        self.setMinimumWidth(760)
        self.setMinimumHeight(660)
        # ===== RUN ON STARTUP CHECKBOX =====
        startup_enabled = is_run_on_startup()
        self.run_startup_cb = QtWidgets.QCheckBox("Run with Windows")
        self.run_startup_cb.setChecked(startup_enabled)
        self.run_startup_cb.toggled.connect(self.on_run_startup_toggled)
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

        self.voice_language_value = QtWidgets.QLabel()
        self.voice_language_value.setStyleSheet("color:#9cdcfe; padding:6px 2px;")

        self.voice_cb = QtWidgets.QComboBox()
        self.voice_cb.setMinimumHeight(34)

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
        self.context_dictionary_input.setStyleSheet(
            "QPlainTextEdit { background:#2b2b2b; border:1px solid #3c3c3c; "
            "border-radius:8px; padding:8px; }"
        )

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
        self.context_game_rules_input.setStyleSheet(
            "QPlainTextEdit { background:#2b2b2b; border:1px solid #3c3c3c; "
            "border-radius:8px; padding:8px; }"
        )
        self.context_game_rules_help = QtWidgets.QLabel(
            "Priority: mentioned name > previous speaker > general speaker rule"
        )
        self.context_game_rules_help.setStyleSheet(
            "color:#8f8f8f; font-size:11px;"
        )
        self.context_game_example_btn = QtWidgets.QPushButton(
            "Insert Example Rules"
        )
        self.context_game_example_btn.setToolTip(GAME_RULES_EXAMPLE)
        self.context_game_example_btn.clicked.connect(
            self._insert_game_rules_example
        )

        self.mouse_hold_key_input = QtWidgets.QLineEdit()
        self.mouse_hold_key_input.setReadOnly(True)
        self.mouse_hold_key_input.setPlaceholderText("Press & hold a key (default: Ctrl)")
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
        self.font_color_btn.setStyleSheet(f"background-color: rgb({fc[0]}, {fc[1]}, {fc[2]}); color: black; border-radius:8px;")

        # shadow color chooser
        sc = self.settings.get("shadow_color", [0, 0, 0])
        if isinstance(sc, QtGui.QColor):
            sc = [sc.red(), sc.green(), sc.blue()]
        self.shadow_color_btn = QtWidgets.QPushButton("Choose Shadow Color")
        self.shadow_color_btn.setMinimumHeight(36)
        self.shadow_color_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.shadow_color_btn.clicked.connect(self.choose_shadow_color)
        self.shadow_color_btn.setStyleSheet(f"background-color: rgb({sc[0]}, {sc[1]}, {sc[2]}); color: black; border-radius:8px;")

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
        # ===== Translator Engine (ONLY GOOGLE FOR NOW) =====
        self.engine_cb = QtWidgets.QComboBox()
        self.engine_cb.addItem("Google Translate", "google")

        current_engine = cfg.get("translate_engine", "google")
        for i in range(self.engine_cb.count()):
            if self.engine_cb.itemData(i) == current_engine:
                self.engine_cb.setCurrentIndex(i)
                break

        for code, name in TRANSLATE_LANGUAGES.items():
            self.trans_tgt_cb.addItem(name, code)

        current_tgt = cfg.get("translate_target", "vi")
        for i in range(self.trans_tgt_cb.count()):
            if self.trans_tgt_cb.itemData(i) == current_tgt:
                self.trans_tgt_cb.setCurrentIndex(i)
                break

        self.trans_tgt_cb.setMinimumHeight(34)
        self.trans_tgt_cb.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.trans_tgt_cb.currentIndexChanged.connect(self._sync_voice_to_translate_target)
        self._sync_voice_to_translate_target(
            saved_voice=voice_settings.get("voice", "vi-VN-HoaiMyNeural")
        )

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
        root_layout.addLayout(title_bar)
        root_layout.setSpacing(10)
        root_layout.setContentsMargins(8, 8, 8, 8)

        # ===== SCROLL AREA =====
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)

        # Widget chứa toàn bộ nội dung settings
        content_widget = QtWidgets.QWidget()
        content_layout = QtWidgets.QVBoxLayout(content_widget)
        content_layout.setSpacing(18)
        content_layout.setContentsMargins(8, 8, 8, 8)

        scroll_area.setWidget(content_widget)

        root_layout.addWidget(scroll_area)


        # ===== APPEARANCE =====
        appearance_box, appearance = self.section("🎨 Appearance")
        # arrange appearance controls into four groups stacked vertically on the left

        col1 = QtWidgets.QVBoxLayout()
        col1.setSpacing(8)
        col2 = QtWidgets.QVBoxLayout()
        col2.setSpacing(8)
        col3 = QtWidgets.QVBoxLayout()
        col3.setSpacing(8)
        col4 = QtWidgets.QVBoxLayout()
        col4.setSpacing(8)

        # column 1: size, style
        col1.addWidget(self.section_label("Font Size"))
        col1.addWidget(self.font_size_input)
        col1.addWidget(self.section_label("Mouse Subtitle Font Size"))
        col1.addWidget(self.mouse_font_size_input)

        col1.addWidget(self.font_size_input)
        col1.addWidget(self.section_label("Style"))
        col1.addWidget(self.style_cb)
        col1.addStretch()

        # column 2: bg opacity, bg color
        col2.addWidget(self.section_label("Background Opacity"))
        col2.addWidget(self.bg_alpha_input)
        col2.addWidget(self.color_btn)
        col2.addStretch()

        # column 3: font color (shadow color moved to middle column)
        col3.addWidget(self.section_label("Font Color"))
        col3.addWidget(self.font_color_btn)
        col3.addStretch()

        # column 4: outline width (shadow opacity/offset moved to middle column)
        col4.addWidget(self.section_label("Outline Width"))
        col4.addWidget(self.stroke_width_input)
        col4.addWidget(self.section_label("Outline Color"))
        col4.addWidget(self.outline_color_btn)
        col4.addStretch()


        # create widget wrappers for each group so they can be stacked vertically
        col_widget1 = QtWidgets.QWidget()
        col_widget1.setLayout(col1)
        col_widget2 = QtWidgets.QWidget()
        col_widget2.setLayout(col2)
        col_widget3 = QtWidgets.QWidget()
        col_widget3.setLayout(col3)
        col_widget4 = QtWidgets.QWidget()
        col_widget4.setLayout(col4)

        left_cols_widget = QtWidgets.QWidget()
        left_cols_layout = QtWidgets.QVBoxLayout(left_cols_widget)
        left_cols_layout.setSpacing(12)
        left_cols_layout.setContentsMargins(0, 0, 0, 0)
        left_cols_layout.addWidget(col_widget1)
        left_cols_layout.addWidget(col_widget2)
        left_cols_layout.addWidget(col_widget3)
        left_cols_layout.addWidget(col_widget4)

        # container holds left stacked groups, middle shadow column, and the language column on the right
        container_widget = QtWidgets.QWidget()
        container_layout = QtWidgets.QHBoxLayout(container_widget)
        container_layout.setSpacing(12)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(left_cols_widget, 1)

        # middle column: all shadow-related controls
        middle_col = QtWidgets.QVBoxLayout()
        middle_col.setSpacing(8)
        middle_col.addWidget(self.section_label("Shadow Color"))
        middle_col.addWidget(self.shadow_color_btn)
        middle_col.addWidget(self.section_label("Shadow Opacity"))
        middle_col.addWidget(self.shadow_alpha_input)
        middle_col.addWidget(self.section_label("Shadow Offset (px)"))
        middle_col.addWidget(self.shadow_offset_input)
        middle_col.addStretch()

        middle_widget = QtWidgets.QWidget()
        middle_widget.setLayout(middle_col)
        container_layout.addWidget(middle_widget)

        # add container into appearance frame; language layout will be inserted into container_layout below
        appearance.addWidget(container_widget)
        content_layout.addLayout(appearance_box)

        # ===== LANGUAGE =====
        lang_box, lang = self.section("🌐 Language")
        lang_box_widget = lang.parentWidget()  # chính là frame
        lang_box_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Maximum
        )
        lang.addWidget(self.section_label("Input Language (OCR + Translate From)"))
        lang.addWidget(self.input_lang_cb)

        lang.addWidget(self.section_label("Translate To"))
        lang.addWidget(self.trans_tgt_cb)
        lang.addWidget(self.section_label("Translator Engine"))
        lang.addWidget(self.engine_cb)

        # initialize visibility based on current engine
        self._on_engine_change(self.engine_cb.currentIndex())
        # insert language column into the appearance container on the right
        try:
            container_layout.addLayout(lang_box, 0)
            container_layout.setAlignment(lang_box, QtCore.Qt.AlignTop)

        except NameError:
            # fallback: if container not present, add to main layout
            content_layout.addLayout(lang_box)

        # ===== TOOLS =====
        tools_box, tools = self.section("🛠 Tools")
        tools.addWidget(self.run_startup_cb)
        tools.addWidget(self.mouse_ocr_cb)
        tools.addWidget(self.section_label("Mouse OCR Area Width"))
        tools.addWidget(self.mouse_ocr_width_input)
        tools.addWidget(self.section_label("Mouse OCR Area Height"))
        tools.addWidget(self.mouse_ocr_height_input)
        tools.addWidget(self.voice_enabled_cb)
        tools.addWidget(self.section_label("Voice Language (follows Translate To)"))
        tools.addWidget(self.voice_language_value)
        tools.addWidget(self.section_label("Voice"))
        tools.addWidget(self.voice_cb)
        tools.addWidget(self.section_label("Mouse OCR Hold Key"))
        tools.addWidget(self.mouse_hold_key_input)
        tools.addWidget(self.edit_btn)
        content_layout.addLayout(tools_box)
        tools.addWidget(self.section_label("Toggle OCR + Subtitle Hotkey"))
        tools.addWidget(self.hotkey_input)
        tools.addWidget(self.section_label("Toggle Settings Panel Hotkey"))
        tools.addWidget(self.settings_hotkey_input)

        # ===== VIDEO / GAME CONTEXT =====
        context_box, context_layout = self.section("🧠 Video / Game Context")
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
        dictionary_help.setStyleSheet("color:#8f8f8f; font-size:11px;")
        context_layout.addWidget(dictionary_help)
        context_layout.addWidget(self.context_game_rules_label)
        context_layout.addWidget(self.context_game_rules_input)
        context_layout.addWidget(self.context_game_rules_help)
        context_layout.addWidget(self.context_game_example_btn)
        content_layout.addLayout(context_box)
        self._update_context_controls(self.context_enabled_cb.isChecked())

        # ===== SPACER =====

        # ===== ABOUT =====
        about_box, about = self.section("About")
        about_text = QtWidgets.QLabel()
        about_text.setText(
            "Create by GlorSub Community.<br/><b>App Version:</b> 1.0.0"
        )
        about.addWidget(about_text)
        content_layout.addLayout(about_box)

        # ===== ACTION BUTTONS =====
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()

        apply_btn = QtWidgets.QPushButton("Apply")
        apply_btn.setMinimumHeight(38)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border-radius: 12px;
                padding: 8px 18px;
            }
            QPushButton:hover { background-color: #1493e3; }
        """)
        apply_btn.clicked.connect(
            lambda: self.apply_settings(show_message=False, silent=True)
        )
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.setMinimumHeight(38)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ea043;
                color: white;
                border-radius: 12px;
                padding: 8px 18px;
            }
            QPushButton:hover { background-color: #3fb950; }
        """)
        save_btn.clicked.connect(self.save_and_close)

        btn_row.addWidget(apply_btn)
        btn_row.addWidget(save_btn)
        root_layout.addLayout(btn_row)
        self._install_drag_surfaces()

    # ---------- LOGIC ----------
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

    def _install_drag_surfaces(self):
        """Allow dragging from non-interactive areas across the settings UI."""
        interactive_types = (
            QtWidgets.QAbstractButton,
            QtWidgets.QLineEdit,
            QtWidgets.QComboBox,
            QtWidgets.QAbstractSpinBox,
            QtWidgets.QAbstractSlider,
            QtWidgets.QAbstractItemView,
            QtWidgets.QPlainTextEdit,
            QtWidgets.QTextEdit,
        )

        surfaces = [self, *self.findChildren(QtWidgets.QWidget)]
        for widget in surfaces:
            current = widget
            belongs_to_interactive_control = False
            while current is not None and current is not self:
                if isinstance(current, interactive_types):
                    belongs_to_interactive_control = True
                    break
                current = current.parentWidget()
            if belongs_to_interactive_control:
                continue
            if isinstance(widget, QtWidgets.QLabel) and widget.openExternalLinks():
                continue
            widget.setProperty("settingsDragSurface", True)
            widget.installEventFilter(self)

    def _sync_voice_to_translate_target(self, _index=None, saved_voice=None):
        translate_target = self.trans_tgt_cb.currentData()
        language = VOICE_LANGUAGE_BY_TRANSLATE_TARGET.get(translate_target)
        language_info = VOICE_OPTIONS.get(language)
        current_voice = saved_voice or self.voice_cb.currentData()

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
        for label, voice_id in language_info["voices"]:
            self.voice_cb.addItem(label, voice_id)
        voice_index = self.voice_cb.findData(current_voice)
        self.voice_cb.setCurrentIndex(max(0, voice_index))
        self.voice_cb.blockSignals(False)

    def choose_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.settings["bg_color"] = [color.red(), color.green(), color.blue()]

    def choose_font_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.settings["font_color"] = [color.red(), color.green(), color.blue()]
            # update preview on button
            self.font_color_btn.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); color: black; border-radius:8px;")

    def choose_shadow_color(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.settings["shadow_color"] = [color.red(), color.green(), color.blue()]
            self.shadow_color_btn.setStyleSheet(f"background-color: rgb({color.red()}, {color.green()}, {color.blue()}); color: black; border-radius:8px;")

    def apply_settings(self, show_message=True, silent=False):
        global cfg, translator, voice_speaker, worker
        global MOUSE_OCR_ENABLED, MOUSE_HOLD_KEY
        global MOUSE_OCR_WIDTH, MOUSE_OCR_HEIGHT

        MOUSE_OCR_ENABLED = self.mouse_ocr_cb.isChecked()
        cfg.setdefault("settings", {})
        cfg["settings"]["mouse_ocr_enabled"] = MOUSE_OCR_ENABLED
        MOUSE_OCR_WIDTH = self.mouse_ocr_width_input.value()
        MOUSE_OCR_HEIGHT = self.mouse_ocr_height_input.value()
        cfg["settings"]["mouse_ocr_width"] = MOUSE_OCR_WIDTH
        cfg["settings"]["mouse_ocr_height"] = MOUSE_OCR_HEIGHT

        key_text = self.mouse_hold_key_input.text().strip()
        if key_text:
            MOUSE_HOLD_KEY = key_text.lower()
        cfg.setdefault("settings", {})
        cfg["settings"]["mouse_hold_key"] = MOUSE_HOLD_KEY

        voice_language = VOICE_LANGUAGE_BY_TRANSLATE_TARGET.get(
            self.trans_tgt_cb.currentData(), ""
        )
        voice = self.voice_cb.currentData() or ""
        voice_enabled = self.voice_enabled_cb.isChecked() and bool(voice_language and voice)
        cfg["settings"].update({
            "voice_enabled": voice_enabled,
            "voice_language": voice_language,
            "voice": voice,
        })
        if voice_speaker is not None:
            voice_speaker.configure(voice_enabled, voice_language, voice)

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
            cfg["ocr_lang"] = new_ocr
            init_ocr_reader(new_ocr)        
        
        # ===== TRANSLATOR ENGINE (ONLY GOOGLE FOR NOW) =====
        new_engine = self.engine_cb.itemData(self.engine_cb.currentIndex())
        cfg["translate_engine"] = new_engine
        # 🔒 Google engine is always active

        # --- HOTKEY: Pause OCR ---
        new_hotkey = self.hotkey_input.text().strip()
        if new_hotkey:
            cfg["hotkey_pause"] = new_hotkey
        # --- HOTKEY: Settings Panel ---
        new_settings_hotkey = self.settings_hotkey_input.text().strip()
        if new_settings_hotkey:
            cfg["hotkey_settings"] = new_settings_hotkey

        # After applying settings, test the translator briefly and inform user.
        def _test_translation():
            try:
                test = translator.translate("Hello", "en", "vi")
                if not test:
                    raise RuntimeError("Empty translation result")
                if not silent:
                    QtWidgets.QMessageBox.information(
                        self,
                        "Translator OK",
                        f"Translator engine '{cfg['translate_engine']}' is working.\n\nTest result:\n{test}"
                    )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Translator Error",
                    f"Translator failed:\n{e}\n\nFalling back to Google."
                )
                try:
                    translator.set_engine("google", None, None)
                except Exception:
                    pass

        QtCore.QTimer.singleShot(400, _test_translation)
        if show_message:
            QtWidgets.QMessageBox.information(
                self,
                "Settings Applied",
                "Settings have been applied successfully."
            )
    def save_and_close(self):
        global SETTINGS_SNAPSHOT
        self.apply_settings(show_message=False, silent=True)
        save_config(cfg)
        SETTINGS_SNAPSHOT = None
        self.hide()

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
        if obj in (
            self.hotkey_input,
            self.settings_hotkey_input,
            self.mouse_hold_key_input,
        ):
            if event.type() == QtCore.QEvent.KeyPress:
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

        # ===== WINDOW DRAGGING (all non-interactive menu surfaces) =====
        if bool(obj.property("settingsDragSurface")):
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
        icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
        icon = QtGui.QIcon(icon_path) if os.path.exists(icon_path) else QtGui.QIcon()

        super().__init__(icon, parent)
        self.setToolTip("GloSub")

        self.overlay = overlay
        self.settings_panel = settings_panel

        menu = QtWidgets.QMenu()

        toggle_action = menu.addAction("Show / Hide Subtitle")
        toggle_action.triggered.connect(self.toggle_overlay)

        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self.show_settings)

        exit_action = menu.addAction("Exit")
        exit_action.triggered.connect(QtWidgets.qApp.quit)

        self.setContextMenu(menu)
        self.show()   # ✅ SHOW SAU KHI INIT

    
    def toggle_overlay(self):
        if self.overlay.isVisible():
            self.overlay.hide()
        else:
            self.overlay.show()

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
    except Exception as e:
        print("[Translator] Initialization failed:", e)

        class _FallbackTranslator:
            def translate(self, text, src, tgt):
                return text
            def set_engine(self, *a, **k):
                pass

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
    icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QtGui.QIcon(icon_path))
    app.setStyleSheet(APP_STYLESHEET)

    

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
    # ====================== CTRL HOLD POLLING TIMER ======================
    ctrl_timer = QtCore.QTimer()
    ctrl_timer.timeout.connect(update_mouse_hold_state)
    ctrl_timer.start(30)  # 30ms

    overlay.show()
    overlay.update_text(tr("HELLO"))

    # ===== Edit Mode Backdrop (dark background) =====
    global edit_backdrop
    edit_backdrop = EditModeBackdrop()
    edit_backdrop.hide()

    editor = OCRRegionEditor(RED_REGION)

    # expose worker as module-global so SettingsPanel can pause/resume it safely
    global worker
    worker = OCRWorker(CAPTURE_FPS)
    worker.subtitle_ready.connect(overlay.update_text)
    worker.subtitle_move.connect(overlay.move_near_mouse)
    global voice_speaker
    voice_settings = cfg.get("settings", {})
    voice_speaker = VoiceSpeaker(
        enabled=voice_settings.get("voice_enabled", False),
        language=voice_settings.get("voice_language", "vi-VN"),
        voice=voice_settings.get("voice", "vi-VN-HoaiMyNeural"),
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

        overlay.base_top = YELLOW_REGION[1]
        overlay.base_height = YELLOW_REGION[3] - YELLOW_REGION[1]
        overlay.setGeometry(
            0,
            overlay.base_top,
            overlay.screen_w,
            overlay.base_height
        )

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

    app.aboutToQuit.connect(on_exit)
    print("[APP] Starting Qt event loop...")
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
