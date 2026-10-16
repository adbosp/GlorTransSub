"""Portable regression checks; run: python -m unittest discover -s tests -v.

main.py starts Windows-specific imports at module scope. Load its actual worker
classes from the AST so these unit checks can run without a Windows desktop.
This does not validate screen capture, audio devices or native hotkeys.
"""
import ast
from collections import deque
from contextlib import closing
import gc
import hashlib
import os
from pathlib import Path
import queue
import re
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock
import weakref

# Match the Windows runtime DLL order: PyTorch must load before Qt.
import torch
from PyQt5 import QtCore
import smart_translator as translation
from tts_engines import TTSEngine


class OfflineGoogle:
    def __init__(self):
        self.calls = 0

    def translate(self, text, src, tgt):
        self.calls += 1
        return f'{tgt}: {text}'


def load_workers(translator):
    path = Path(__file__).resolve().parents[1] / 'main.py'
    wanted = {'VoiceSpeaker', 'OCRWorker', 'parse_context_dictionary',
              'parse_game_dialogue_rules', 'normalize_text', 'default_edge_voice'}
    tree = ast.parse(path.read_text(encoding='utf-8'))
    tree.body = [node for node in tree.body if getattr(node, 'name', '') in wanted]
    scope = dict(QtCore=QtCore, threading=threading, queue=queue, os=os,
                 tempfile=tempfile, time=time, sys=sys, hashlib=hashlib, closing=closing,
                 TTSEngine=TTSEngine, cfg={}, deque=deque, re=re,
                 translator=translator, VOICE_OPTIONS={})
    exec(compile(tree, str(path), 'exec'), scope)
    return scope


class TranslationResources(unittest.TestCase):
    def setUp(self):
        self.backend_patch = patch.object(translation, 'GoogleEngine', OfflineGoogle)
        self.backend_patch.start()
        self.addCleanup(self.backend_patch.stop)
        self.translator = translation.SmartTranslator()

    def test_long_session_bounds_cache_and_keeps_recent_hits(self):
        for index in range(20000):
            text = f'Subtitle {index}'
            self.assertEqual(self.translator.translate(text), f'vi: {text}')
        self.assertLessEqual(len(self.translator._cache), translation.MAX_CACHE_SIZE)
        self.assertLessEqual(self.translator._cache_bytes, translation.MAX_CACHE_BYTES)
        calls = self.translator._google.calls
        self.translator.translate('Subtitle 19999')
        self.assertEqual(self.translator._google.calls, calls)
        self.translator.translate('Subtitle 0')
        self.assertEqual(self.translator._google.calls, calls + 1)

    def test_unicode_large_entries_obey_byte_budget(self):
        for index in range(1000):
            self.translator.translate(f'{index} ' + '字幕🙂' * 2000)
        self.assertLess(len(self.translator._cache), translation.MAX_CACHE_SIZE)
        self.assertLessEqual(self.translator._cache_bytes, translation.MAX_CACHE_BYTES)
        measured = sum(self.translator._entry_size(k, v)
                       for k, v in self.translator._cache.items())
        self.assertEqual(measured, self.translator._cache_bytes)

    def test_oversize_result_is_returned_without_retaining_it(self):
        with patch.object(self.translator._google, 'translate',
                          return_value='a' * translation.MAX_CACHE_BYTES):
            self.assertEqual(len(self.translator.translate('Hello')),
                             translation.MAX_CACHE_BYTES)
        self.assertEqual(self.translator._cache_bytes, 0)
        self.assertFalse(self.translator._cache)

    def test_target_language_and_punctuation_are_distinct(self):
        self.assertEqual(self.translator.translate('Hello!', tgt='vi'), 'vi: Hello!')
        self.assertEqual(self.translator.translate('Hello!', tgt='ja'), 'ja: Hello!')
        self.assertEqual(self.translator.translate('Hello?', tgt='vi'), 'vi: Hello?')
        self.assertEqual(self.translator._google.calls, 3)

    def test_clear_and_reconfigure_release_entries(self):
        self.translator.translate('Hello')
        translation.clear_translation_cache(self.translator)
        self.assertFalse(self.translator._cache)
        self.assertEqual(self.translator._cache_bytes, 0)
        self.translator.translate('Hello')
        self.translator.configure('google')
        self.assertFalse(self.translator._cache)
        self.assertEqual(self.translator._cache_bytes, 0)

    def test_cache_does_not_keep_translator_alive(self):
        translator = translation.SmartTranslator()
        translator.translate('Hello')
        reference = weakref.ref(translator)
        del translator
        gc.collect()
        self.assertIsNone(reference())

    def test_setting_change_discards_inflight_response(self):
        started, release = threading.Event(), threading.Event()
        results = []

        def delayed(*args):
            started.set()
            if not release.wait(3):
                raise RuntimeError('test timed out')
            return 'old settings response'

        with patch.object(self.translator._google, 'translate', side_effect=delayed):
            thread = threading.Thread(target=lambda: results.append(
                self.translator.translate('Hello')))
            thread.start()
            try:
                self.assertTrue(started.wait(2))
                self.translator.configure('google')
            finally:
                release.set()
                thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results, [''])
        self.assertFalse(self.translator._cache)

    def test_fallback_and_pause_still_work(self):
        self.translator._engine = Mock()
        self.translator._engine.translate.side_effect = RuntimeError('offline')
        self.translator.engine_name = 'openai'
        self.assertEqual(self.translator.translate('Hello'), 'vi: Hello')
        self.assertEqual(self.translator.last_error, 'offline')
        self.assertFalse(self.translator._cache)
        calls = self.translator._google.calls
        self.translator.pause()
        self.assertEqual(self.translator.translate('Hello'), '')
        self.assertEqual(self.translator._google.calls, calls)

    def test_concurrent_duplicate_insertion_keeps_accounting_correct(self):
        barrier = threading.Barrier(4)
        def simultaneous(*args):
            barrier.wait(timeout=3)
            return 'same translation'
        with patch.object(self.translator._google, 'translate', side_effect=simultaneous):
            threads = [threading.Thread(target=self.translator.translate,
                                        args=('Hello',)) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(4)
                self.assertFalse(thread.is_alive())
        self.assertEqual(len(self.translator._cache), 1)
        self.assertEqual(self.translator._cache_bytes,
                         self.translator._entry_size(('auto', 'vi', 'Hello'),
                                                     'same translation'))

    def test_worker_uses_shared_cache_with_correct_language(self):
        scope = load_workers(self.translator)
        worker = scope['OCRWorker'](3)
        self.assertEqual(worker._translate_with_optional_context(
            'Hello!', 'hello', 'en', 'vi'), 'vi: Hello!')
        self.assertEqual(worker._translate_with_optional_context(
            'Hello!', 'hello', 'en', 'ja'), 'ja: Hello!')
        for index in range(3000):
            worker._translate_with_optional_context(str(index), str(index), 'en', 'vi')
        self.assertFalse(hasattr(worker, '_translate_cache'))
        self.assertLessEqual(len(self.translator._cache), translation.MAX_CACHE_SIZE)


class CaptureResources(unittest.TestCase):
    def test_pixels_released_before_translation_and_inference_has_no_grad(self):
        import numpy as np
        import torch
        from PIL import Image
        image = Image.new('RGB', (64, 64), 'white')
        refs = []
        scope = load_workers(None)
        worker = scope['OCRWorker'](3)

        def readtext(pixels, detail):
            self.assertTrue(torch.is_inference_mode_enabled())
            refs.append(weakref.ref(pixels))
            return ['Hello']

        def translate(*args):
            self.assertIsNone(refs[0]())
            # A closed Pillow image rejects further access to its pixels.
            with self.assertRaises(ValueError):
                image.getpixel((0, 0))
            worker.stop()
            return 'Xin chao'

        scope.update(reader=Mock(readtext=readtext), reader_language='en',
                     RED_REGION=(0, 0, 64, 64),
                     should_follow_mouse=lambda: False,
                     ImageGrab=Mock(grab=Mock(return_value=image)),
                     np=np, cv2=None, torch=torch, MOUSE_OCR_ENABLED=False,
                     frame_hash=lambda pixels: 'first frame')
        worker._translate_with_optional_context = translate
        worker.run()
        self.assertTrue(worker._stop)


class VoiceResources(unittest.TestCase):
    def setUp(self):
        self.scope = load_workers(None)
        self.speaker_class = self.scope['VoiceSpeaker']
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        directory_patch = patch.object(tempfile, 'gettempdir', return_value=self.temp_dir.name)
        directory_patch.start()
        self.addCleanup(directory_patch.stop)

    def test_disabled_voice_and_blank_subtitles_start_no_threads(self):
        with patch.object(threading, 'Thread') as create_thread:
            speaker = self.speaker_class(enabled=False)
            speaker.speak('Hello')
            speaker.configure(True, 'vi-VN', 'vi-VN-HoaiMyNeural')
            speaker.speak('')
            speaker.stop()
            create_thread.assert_not_called()

    def test_voice_starts_once_when_needed_and_never_restarts_after_stop(self):
        with patch.object(threading, 'Thread') as create_thread:
            speaker = self.speaker_class(enabled=True, mode='queue')
            self.assertEqual(create_thread.call_count, 0)
            speaker.speak('Hello')
            self.assertEqual(create_thread.call_count, 4)
            speaker.speak('Another subtitle')
            self.assertEqual(create_thread.call_count, 4)
            speaker.stop()
            speaker.speak('After stop')
            self.assertEqual(create_thread.call_count, 4)

    def test_real_voice_workers_stop_after_first_use(self):
        # Exercise thread lifecycle without a network call or audio device.
        with patch.object(self.speaker_class, '_playback_loop', return_value=None), \
             patch.object(TTSEngine, 'synthesize_to_file', side_effect=RuntimeError('offline')):
            speaker = self.speaker_class(enabled=True, mode='queue')
            speaker.speak('Hello')
            threads = [*speaker._synthesis_threads, speaker._queue_thread,
                       speaker._playback_thread]
            speaker.stop()
            for thread in threads:
                thread.join(2)
                self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main()
