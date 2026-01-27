import ctypes
from ctypes import wintypes
from PyQt5 import QtCore

user32 = ctypes.windll.user32

MOD_ALT     = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT   = 0x0004
MOD_WIN     = 0x0008

VK_MAP = {
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}

class WinHotkey(QtCore.QObject):
    activated = QtCore.pyqtSignal()

    def __init__(self, hotkey_id: int, hotkey: str, parent=None):
        super().__init__(parent)

        self.hotkey_id = hotkey_id
        self.hotkey = hotkey.lower()

        mod = 0
        vk = None

        parts = self.hotkey.split("+")
        for p in parts:
            if p == "ctrl":
                mod |= MOD_CONTROL
            elif p == "alt":
                mod |= MOD_ALT
            elif p == "shift":
                mod |= MOD_SHIFT
            elif p in VK_MAP:
                vk = VK_MAP[p]

        if vk is None:
            raise ValueError(f"Unsupported hotkey: {hotkey}")

        if not user32.RegisterHotKey(None, hotkey_id, mod, vk):
            raise RuntimeError(f"RegisterHotKey failed: {hotkey}")

        self._filter = _HotkeyEventFilter(hotkey_id, self)
        QtCore.QCoreApplication.instance().installNativeEventFilter(self._filter)

    def unregister(self):
        try:
            user32.UnregisterHotKey(None, self.hotkey_id)
        except Exception:
            pass


class _HotkeyEventFilter(QtCore.QAbstractNativeEventFilter):
    def __init__(self, hotkey_id, owner):
        super().__init__()
        self.hotkey_id = hotkey_id
        self.owner = owner

    def nativeEventFilter(self, eventType, message):
        if eventType != "windows_generic_MSG":
            return False, 0

        msg = wintypes.MSG.from_address(message.__int__())
        if msg.message == 0x0312 and msg.wParam == self.hotkey_id:
            self.owner.activated.emit()
            return True, 0

        return False, 0
