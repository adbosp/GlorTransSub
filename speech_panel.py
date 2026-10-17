"""On-demand game/video dubbing controls. No recording on application startup."""
from pathlib import Path
import sys
import threading

from PyQt5 import QtCore, QtWidgets

from prepare_speech_models import prepare
from speech_translation import SpeechOptions, SpeechSession, PIPER_VOICE, audio_devices


class SpeechPanel(QtWidgets.QWidget):
    status_ready = QtCore.pyqtSignal(str)
    subtitle_ready = QtCore.pyqtSignal(str, str)
    active_changed = QtCore.pyqtSignal(bool)
    setup_finished = QtCore.pyqtSignal()
    devices_ready = QtCore.pyqtSignal(object)

    def __init__(self, config, translator_factory, save, parent=None):
        super().__init__(parent)
        self.config, self.translator_factory, self.save = config, translator_factory, save
        self.session = None
        self.downloader = None
        self.device_loader = None
        self._active = False
        saved = config.get('speech', {})
        layout = QtWidgets.QVBoxLayout(self)
        note = QtWidgets.QLabel(
            'Game/video audio → speech recognition → translation → Vietnamese voice.\n'
            'CPU INT8 keeps the GPU available for games. OCR pauses while dubbing.\n'
            'On the same audio output, listening pauses during speech and can miss dialogue. '
            'Use a separate output for the Vietnamese voice to listen continuously.')
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QtWidgets.QFormLayout()
        bundled = Path(sys.executable).parent / 'models' / 'speech'
        default_root = bundled if getattr(sys, 'frozen', False) and bundled.is_dir() else (
            Path(QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.AppLocalDataLocation)) / 'speech-models')
        self.root = QtWidgets.QLineEdit(saved.get('model_root', str(default_root)))
        root_row = QtWidgets.QHBoxLayout()
        root_row.addWidget(self.root)
        browse = QtWidgets.QPushButton('Browse…')
        browse.clicked.connect(self._browse)
        root_row.addWidget(browse)
        form.addRow('Speech model folder', root_row)
        self.model = QtWidgets.QComboBox()
        for label, value in [('Tiny English (~75 MB, fastest)', 'tiny.en'),
                             ('Tiny multilingual (~75 MB)', 'tiny'),
                             ('Base multilingual (~145 MB, more accurate)', 'base')]:
            self.model.addItem(label, value)
        self.model.setCurrentIndex(max(0, self.model.findData(saved.get('model', 'tiny.en'))))
        form.addRow('Recognition model', self.model)
        self.language = QtWidgets.QComboBox()
        for label, value in [('English', 'en'), ('Japanese', 'ja'), ('Korean', 'ko'),
                             ('Chinese', 'zh'), ('French', 'fr'), ('German', 'de')]:
            self.language.addItem(label, value)
        self.language.setCurrentIndex(max(0, self.language.findData(saved.get('source', 'en'))))
        form.addRow('Spoken language', self.language)
        self.engine = QtWidgets.QComboBox()
        self.engine.addItem('OPUS-MT offline (selected model folder in General)', 'opus_mt')
        self.engine.addItem('Google Translate (online)', 'google')
        self.engine.setCurrentIndex(max(0, self.engine.findData(saved.get('engine', 'opus_mt'))))
        form.addRow('Translation', self.engine)
        self.capture = QtWidgets.QComboBox()
        self.output = QtWidgets.QComboBox()
        self.capture.addItem('Default Windows output (game/video)', None)
        self.output.addItem('Default Windows output', None)
        form.addRow('Listen to', self.capture)
        form.addRow('Vietnamese playback', self.output)
        layout.addLayout(form)
        buttons = QtWidgets.QHBoxLayout()
        self.refresh = QtWidgets.QPushButton('Refresh audio devices')
        self.refresh.clicked.connect(self.refresh_devices)
        self.download = QtWidgets.QPushButton('Download speech models')
        self.download.clicked.connect(self.download_models)
        self.start_button = QtWidgets.QPushButton('Start dubbing')
        self.start_button.clicked.connect(self.start)
        self.stop_button = QtWidgets.QPushButton('Stop')
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop)
        for button in (self.refresh, self.download, self.start_button, self.stop_button):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self.status = QtWidgets.QLabel('Stopped. Download speech models once, then start.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.transcript = QtWidgets.QPlainTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setMaximumBlockCount(40)
        self.transcript.setPlaceholderText('Recognized speech and Vietnamese translation appear here.')
        layout.addWidget(self.transcript)
        self.status_ready.connect(self.status.setText)
        self.subtitle_ready.connect(self._subtitle)
        self.setup_finished.connect(self._setup_done)
        self.devices_ready.connect(self._devices_loaded)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(150)

    def _browse(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Speech models', self.root.text())
        if folder:
            self.root.setText(folder)

    def _save(self):
        self.config['speech'] = dict(model_root=self.root.text().strip(), model=self.model.currentData(),
                                    source=self.language.currentData(), engine=self.engine.currentData())
        self.save()

    def refresh_devices(self):
        if self.device_loader is not None and self.device_loader.is_alive():
            return
        self.refresh.setEnabled(False)
        def load():
            try:
                self.devices_ready.emit(audio_devices())
            except Exception as exc:
                self.status_ready.emit(f'Cannot list WASAPI devices: {exc}')
                self.devices_ready.emit(None)
        self.device_loader = threading.Thread(target=load, daemon=True)
        self.device_loader.start()

    def _devices_loaded(self, devices):
        self.refresh.setEnabled(not self._active)
        if devices is None:
            return
        captures, outputs, _ = devices
        self.capture.clear()
        self.output.clear()
        self.capture.addItem('Default Windows output (game/video)', None)
        self.output.addItem('Default Windows output', None)
        for device in captures:
            self.capture.addItem(device['name'], int(device['index']))
        for device in outputs:
            self.output.addItem(device['name'], int(device['index']))

    def _controls(self, enabled):
        for widget in (self.root, self.model, self.language, self.engine, self.capture,
                       self.output, self.refresh, self.download, self.start_button):
            widget.setEnabled(enabled)
        self.stop_button.setEnabled(not enabled and self._active)

    def download_models(self):
        if self._active or (self.downloader is not None and self.downloader.is_alive()):
            return
        try:
            self._save()
        except Exception as exc:
            self.status.setText(f'Cannot save speech settings: {exc}')
            return
        folder, model = self.root.text(), self.model.currentData()
        self._controls(False)
        def download():
            try:
                prepare(folder, model, self.status_ready.emit)
            except Exception as exc:
                self.status_ready.emit(f'Model download failed: {exc}. You can retry.')
            finally:
                self.setup_finished.emit()
        self.downloader = threading.Thread(target=download, name='SpeechModelSetup', daemon=True)
        self.downloader.start()

    def _setup_done(self):
        self._controls(True)

    def start(self):
        if self._active:
            return
        try:
            source = self.language.currentData()
            model = self.model.currentData()
            if model == 'tiny.en' and source != 'en':
                raise ValueError('Select Tiny/Base multilingual for a language other than English.')
            self._save()
            translate = self.translator_factory(source, self.engine.currentData())
            root = Path(self.root.text().strip())
            self.session = SpeechSession(SpeechOptions(str(root / model), str(root / 'piper-vi' / PIPER_VOICE),
                source=source, capture_index=self.capture.currentData(), output_index=self.output.currentData()),
                translate, self.status_ready.emit, self.subtitle_ready.emit)
            self._active = True
            self.active_changed.emit(True)
            self._controls(False)
            self.session.start()
        except Exception as exc:
            self.status.setText(f'Cannot start dubbing: {exc}')
            if self._active:
                self._finish()

    def stop(self):
        if self.session is not None:
            self.status.setText('Stopping dubbing…')
            self.session.stop()
            self.stop_button.setEnabled(False)

    def _finish(self):
        if self.status.text() == 'Stopping dubbing…':
            self.status.setText('Stopped.')
        self.session = None  # release ASR/TTS/translation model owners after worker exit
        self._active = False
        self._controls(True)
        self.active_changed.emit(False)

    def _poll(self):
        if self._active and self.session is not None and not self.session.alive:
            self._finish()

    def _subtitle(self, source, target):
        if self._active:
            self.transcript.appendPlainText(f'{source}\n→ {target}\n')
