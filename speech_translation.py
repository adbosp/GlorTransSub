"""Bounded, local speech translation. Native audio/model imports are lazy."""
from dataclasses import dataclass
from collections import deque
import json
import math
import os
from pathlib import Path
import queue
import threading
import time

import numpy as np

SAMPLE_RATE = 16000
PIPER_VOICE = 'vi_VN-vais1000-medium.onnx'


@dataclass(frozen=True)
class SpeechOptions:
    asr_dir: str
    voice_path: str
    source: str = 'en'
    capture_index: int | None = None
    output_index: int | None = None
    max_age: float = 8.0
    threads: int = 4


class Utterances:
    """Energy endpointing before Whisper's speech VAD; bounded even over music."""
    def __init__(self, max_seconds=3.0, silence_seconds=0.4, threshold=0.008):
        self.maximum = int(max_seconds * SAMPLE_RATE)
        self.silence_limit = int(silence_seconds * SAMPLE_RATE)
        self.threshold = threshold
        self.reset()

    def reset(self):
        self.parts = []
        self.samples = self.silent = self.voiced = 0
        self.preroll = deque(maxlen=3)

    def feed(self, block):
        block = np.asarray(block, dtype=np.float32)
        loud = bool(np.sqrt(np.mean(block * block)) >= self.threshold)
        if not self.parts:
            if not loud:
                self.preroll.append(block.copy())
                return None
            self.parts.extend(self.preroll)
            self.samples = sum(len(x) for x in self.parts)
            self.preroll.clear()
        self.parts.append(block.copy())
        self.samples += len(block)
        self.voiced += len(block) if loud else 0
        self.silent = 0 if loud else self.silent + len(block)
        if self.samples < self.maximum and self.silent < self.silence_limit:
            return None
        result = np.concatenate(self.parts) if self.voiced >= SAMPLE_RATE // 5 else None
        self.reset()
        return result


def put_latest(target, value):
    try:
        target.put_nowait(value)
    except queue.Full:
        try:
            target.get_nowait()
        except queue.Empty:
            pass
        try:
            target.put_nowait(value)
        except queue.Full:
            pass


def audio_devices():
    import pyaudiowpatch as pa
    with pa.PyAudio() as audio:
        host = audio.get_host_api_info_by_type(pa.paWASAPI)
        default = audio.get_device_info_by_index(host['defaultOutputDevice'])
        loopbacks = list(audio.get_loopback_device_info_generator())
        outputs = [audio.get_device_info_by_index(i) for i in range(audio.get_device_count())]
        outputs = [d for d in outputs if d['hostApi'] == host['index']
                   and d['maxOutputChannels'] > 0 and not d.get('isLoopbackDevice')]
        # WASAPI loopback and render devices have different indices. Store the
        # actual render counterpart for reliable same-device echo protection.
        captures = []
        for d in loopbacks:
            matches = [o for o in outputs if o['name'] in d['name']]
            render = max(matches, key=lambda o: len(o['name'])) if matches else None
            captures.append(dict(d, render_index=render['index'] if render else None,
                                 default=bool(render and render['index'] == default['index'])))
        return captures, outputs, int(default['index'])


def load_voice(path, threads=2):
    import onnxruntime as ort
    from piper import PiperVoice
    from piper.config import PiperConfig
    root = Path(path)
    config = json.loads(Path(str(root) + '.json').read_text(encoding='utf-8'))
    if config.get('language', {}).get('code') != 'vi_VN':
        raise ValueError('Choose a Vietnamese Piper voice (vi_VN).')
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    return PiperVoice(session=ort.InferenceSession(str(root), sess_options=options,
                      providers=['CPUExecutionProvider']), config=PiperConfig.from_dict(config))


class SpeechSession:
    """One capture thread + one inference/playback thread, one waiting clip."""
    def __init__(self, options, translate, status=lambda text: None,
                 subtitle=lambda source, target: None):
        self.options, self.translate = options, translate
        self.status, self.subtitle = status, subtitle
        self.stopped = threading.Event()
        self.speaking = threading.Event()
        self.clips = queue.Queue(maxsize=1)
        self.thread = None
        self.capture_thread = None
        self.same_output = True

    def start(self):
        if self.thread is not None:
            raise RuntimeError('This session has already been started.')
        self.thread = threading.Thread(target=self._run, name='SpeechTranslation', daemon=True)
        self.thread.start()

    def stop(self):
        self.stopped.set()
        put_latest(self.clips, None)

    @property
    def alive(self):
        return ((self.thread is not None and self.thread.is_alive())
                or (self.capture_thread is not None and self.capture_thread.is_alive()))

    def _capture(self, capture):
        import pyaudiowpatch as pa
        from scipy.signal import resample_poly
        rate = int(capture['defaultSampleRate'])
        channels = min(2, int(capture['maxInputChannels']))
        size = rate // 20
        gcd = math.gcd(rate, SAMPLE_RATE)
        cutter = Utterances()
        try:
            with pa.PyAudio() as audio:
                stream = audio.open(format=pa.paFloat32, channels=channels, rate=rate,
                                    input=True, input_device_index=int(capture['index']),
                                    frames_per_buffer=size)
                try:
                    while not self.stopped.is_set():
                        raw = stream.read(size, exception_on_overflow=False)
                        if self.same_output and self.speaking.is_set():
                            cutter.reset()
                            continue
                        mono = np.frombuffer(raw, dtype=np.float32).reshape(-1, channels).mean(axis=1)
                        block = resample_poly(mono, SAMPLE_RATE // gcd, rate // gcd).astype(np.float32)
                        clip = cutter.feed(block)
                        if clip is not None:
                            put_latest(self.clips, (time.monotonic(), clip))
                finally:
                    stream.stop_stream()
                    stream.close()
        except Exception as exc:
            if not self.stopped.is_set():
                self.status(f'Audio capture failed: {exc}')
            self.stop()

    def _play(self, audio, voice, text, output_index):
        import pyaudiowpatch as pa
        from piper.config import SynthesisConfig
        from scipy.signal import resample_poly
        device = audio.get_device_info_by_index(output_index)
        rate = int(device['defaultSampleRate'])
        channels = min(2, int(device['maxOutputChannels']))
        stream = None
        self.speaking.set()
        try:
            # Generate a sentence at a time; do not retain an entire WAV or
            # create a permanent disk cache of private conversations.
            for chunk in voice.synthesize(text, SynthesisConfig(length_scale=0.9)):
                if self.stopped.is_set():
                    break
                if stream is None:
                    stream = audio.open(format=pa.paInt16, channels=channels, rate=rate,
                                        output=True, output_device_index=output_index)
                gcd = math.gcd(rate, chunk.sample_rate)
                samples = resample_poly(chunk.audio_float_array, rate // gcd, chunk.sample_rate // gcd)
                samples = np.clip(samples * 32767, -32767, 32767).astype(np.int16)
                data = np.repeat(samples[:, None], channels, axis=1).tobytes()
                step = rate // 20 * 2 * channels
                for offset in range(0, len(data), step):
                    if self.stopped.is_set():
                        break
                    stream.write(data[offset:offset + step])
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            if self.same_output:
                self.stopped.wait(0.35)  # drain playback/loopback tail before listening
            self.speaking.clear()

    def _run(self):
        try:
            import pyaudiowpatch as pa
            from faster_whisper import WhisperModel
            captures, outputs, default = audio_devices()
            capture = next((d for d in captures if d['index'] == self.options.capture_index), None)
            if self.options.capture_index is None:
                capture = next((d for d in captures if d['default']), None)
            if capture is None:
                raise ValueError('Selected game/video output is unavailable. Refresh audio devices.')
            output_index = self.options.output_index if self.options.output_index is not None else default
            if not any(d['index'] == output_index for d in outputs):
                raise ValueError('Selected playback device is unavailable. Refresh audio devices.')
            self.same_output = capture['render_index'] is None or capture['render_index'] == output_index
            root = Path(self.options.asr_dir)
            for name in ('model.bin', 'config.json', 'tokenizer.json'):
                if not (root / name).is_file():
                    raise ValueError('Download or choose a local Faster-Whisper model first.')
            self.status('Loading local speech models…')
            asr = WhisperModel(str(root), device='cpu', compute_type='int8',
                               cpu_threads=self.options.threads, num_workers=1,
                               local_files_only=True)
            voice = load_voice(self.options.voice_path)
            if self.stopped.is_set():
                return
            self.capture_thread = threading.Thread(target=self._capture, args=(capture,),
                                                   name='GameAudioCapture', daemon=True)
            self.capture_thread.start()
            mode = 'same output: listening pauses during speech' if self.same_output else 'separate outputs'
            self.status(f'Listening · CPU INT8 · {mode}')
            with pa.PyAudio() as audio:
                while not self.stopped.is_set():
                    try:
                        item = self.clips.get(timeout=0.2)
                    except queue.Empty:
                        continue
                    if item is None:
                        break
                    captured, clip = item
                    if time.monotonic() - captured > self.options.max_age:
                        continue
                    started = time.monotonic()
                    segments, _ = asr.transcribe(clip, language=self.options.source,
                        beam_size=1, best_of=1, temperature=0, condition_on_previous_text=False,
                        vad_filter=True, vad_parameters={'min_silence_duration_ms': 250},
                        without_timestamps=True, max_new_tokens=96)
                    text = ' '.join(s.text.strip() for s in segments
                                    if s.no_speech_prob < 0.6 and s.avg_logprob > -1.0).strip()
                    del clip
                    if not text or self.stopped.is_set():
                        continue
                    if time.monotonic() - captured > self.options.max_age:
                        continue
                    target = self.translate(text, self.options.source, 'vi').strip()
                    if self.stopped.is_set() or not target:
                        continue
                    if time.monotonic() - captured > self.options.max_age:
                        continue
                    self.subtitle(text, target)
                    self.status(f'ASR + translation {time.monotonic() - started:.2f}s · {mode}')
                    self._play(audio, voice, target, output_index)
                    if self.same_output:
                        # Clips recorded just before playback are stale after
                        # half-duplex speech; never speak the previous backlog.
                        while not self.clips.empty():
                            try:
                                self.clips.get_nowait()
                            except queue.Empty:
                                break
        except Exception as exc:
            self.status(f'Speech translation failed: {exc}')
        finally:
            self.stop()
            if self.capture_thread is not None:
                self.capture_thread.join(timeout=2)
