"""Resource limits, cancellation and optional real local speech models."""
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, MagicMock, patch

import numpy as np
from speech_translation import Utterances, put_latest, SpeechSession, SpeechOptions


class SpeechResources(unittest.TestCase):
    def test_silence_retains_only_small_preroll(self):
        cutter = Utterances()
        for _ in range(10000):
            self.assertIsNone(cutter.feed(np.zeros(800, dtype=np.float32)))
        self.assertEqual(len(cutter.parts), 0)
        self.assertLessEqual(sum(len(x) for x in cutter.preroll), 2400)

    def test_continuous_sound_is_split_without_unbounded_audio(self):
        cutter = Utterances()
        clips = []
        for _ in range(200):
            clip = cutter.feed(np.full(800, 0.1, dtype=np.float32))
            if clip is not None:
                clips.append(clip)
            self.assertLessEqual(cutter.samples, 48000)
        self.assertEqual(len(clips), 3)
        self.assertTrue(all(len(c) == 48000 for c in clips))

    def test_silence_ends_phrase_and_short_impulse_is_ignored(self):
        cutter = Utterances()
        cutter.feed(np.full(800, 0.2, dtype=np.float32))
        result = [cutter.feed(np.zeros(800, dtype=np.float32)) for _ in range(9)]
        self.assertTrue(all(x is None for x in result))
        for _ in range(10):
            cutter.feed(np.full(800, 0.1, dtype=np.float32))
        result = [cutter.feed(np.zeros(800, dtype=np.float32)) for _ in range(9)]
        self.assertEqual(sum(x is not None for x in result), 1)

    def test_waiting_audio_always_replaced_by_latest(self):
        waiting = queue.Queue(maxsize=1)
        for index in range(10000):
            put_latest(waiting, index)
        self.assertEqual(waiting.qsize(), 1)
        self.assertEqual(waiting.get_nowait(), 9999)

    def test_cancel_during_recognition_never_translates_or_speaks(self):
        import time
        entered, release = threading.Event(), threading.Event()
        segment = Mock(text='Hello', no_speech_prob=0.01, avg_logprob=-0.1)
        def transcribe(*args, **kwargs):
            entered.set()
            release.wait(3)
            return iter([segment]), None
        model = Mock()
        model.transcribe.side_effect = transcribe
        pa = MagicMock()
        status, translate, subtitle = Mock(), Mock(return_value='Xin chào'), Mock()
        with tempfile.TemporaryDirectory() as folder:
            for name in ('model.bin', 'config.json', 'tokenizer.json'):
                (Path(folder) / name).touch()
            session = SpeechSession(SpeechOptions(folder, 'voice'), translate, status, subtitle)
            def capture(device):
                put_latest(session.clips, (time.monotonic(), np.ones(16000, dtype=np.float32)))
                session.stopped.wait(3)
            session._capture = capture
            session._play = Mock()
            devices = ([dict(index=1, render_index=2, default=True)], [dict(index=2)], 2)
            with patch.dict(sys.modules, {'pyaudiowpatch': pa,
                 'faster_whisper': SimpleNamespace(WhisperModel=Mock(return_value=model))}), \
                 patch('speech_translation.audio_devices', return_value=devices), \
                 patch('speech_translation.load_voice', return_value=Mock()):
                session.start()
                self.assertTrue(entered.wait(3))
                session.stop()
                release.set()
                session.thread.join(3)
            self.assertFalse(session.alive)
            translate.assert_not_called()
            subtitle.assert_not_called()
            session._play.assert_not_called()

    def test_new_session_does_not_start_models_or_threads(self):
        session = SpeechSession(SpeechOptions('', ''), Mock())
        self.assertFalse(session.alive)
        self.assertIsNone(session.thread)
        self.assertEqual(session.clips.qsize(), 0)
        session.stop()
        self.assertTrue(session.stopped.is_set())

    def test_shared_output_does_not_enqueue_the_dubbed_voice(self):
        session = SpeechSession(SpeechOptions('', ''), Mock())
        session.speaking.set()
        pa = MagicMock()
        stream = pa.PyAudio.return_value.__enter__.return_value.open.return_value
        counter = 0
        def read(*args, **kwargs):
            nonlocal counter
            counter += 1
            if counter == 80:
                session.stopped.set()
            return np.full((2400, 2), 0.1, dtype=np.float32).tobytes()
        stream.read.side_effect = read
        with patch.dict(sys.modules, {'pyaudiowpatch': pa}):
            session._capture(dict(defaultSampleRate=48000, maxInputChannels=2, index=1))
        self.assertEqual(session.clips.qsize(), 0)
        stream.close.assert_called_once()

    def test_playback_uses_native_device_format_and_stops_between_blocks(self):
        session = SpeechSession(SpeechOptions('', ''), Mock())
        session.same_output = False
        audio = MagicMock()
        audio.get_device_info_by_index.return_value = dict(defaultSampleRate=48000, maxOutputChannels=2)
        stream = audio.open.return_value
        stream.write.side_effect = lambda *_: session.stopped.set()
        voice = Mock()
        voice.synthesize.return_value = iter([SimpleNamespace(sample_rate=22050,
            audio_float_array=np.ones(22050, dtype=np.float32) * 0.1)])
        with patch.dict(sys.modules, {'pyaudiowpatch': MagicMock(),
             'piper.config': SimpleNamespace(SynthesisConfig=Mock())}):
            session._play(audio, voice, 'Xin chào', 2)
        self.assertEqual(audio.open.call_args.kwargs['rate'], 48000)
        self.assertEqual(audio.open.call_args.kwargs['channels'], 2)
        self.assertEqual(stream.write.call_count, 1)
        self.assertLessEqual(len(stream.write.call_args.args[0]), 48000 // 20 * 4)
        stream.close.assert_called_once()
        self.assertFalse(session.speaking.is_set())


@unittest.skipUnless(os.environ.get('GLOSUB_SPEECH_MODEL_ROOT'), 'Real speech models not selected')
class RealSpeechModels(unittest.TestCase):
    def test_actual_int8_recognition_and_vietnamese_waveform(self):
        from speech_checks import check_speech_models
        result = check_speech_models(os.environ['GLOSUB_SPEECH_MODEL_ROOT'],
                                     os.environ.get('GLOSUB_SPEECH_FIXTURE'))
        self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['tts_provider'], ['CPUExecutionProvider'])
        self.assertIn(result['asr_compute_type'], ['int8', 'int8_float32'])
