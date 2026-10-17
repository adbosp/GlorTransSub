"""Actual local ASR and Vietnamese synthesis checks, with no audio device needed."""
from pathlib import Path
import time


def check_speech_models(root, fixture=None):
    import numpy as np
    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio
    from speech_translation import load_voice, PIPER_VOICE
    root = Path(root)
    fixture = Path(fixture) if fixture else root / 'test-audio' / 'jfk.flac'
    model = WhisperModel(str(root / 'tiny.en'), device='cpu', compute_type='int8',
                         cpu_threads=4, num_workers=1, local_files_only=True)
    audio = decode_audio(str(fixture), sampling_rate=16000)
    started = time.perf_counter()
    segments, _ = model.transcribe(audio, language='en', beam_size=1, best_of=1,
        condition_on_previous_text=False, vad_filter=True, without_timestamps=True, max_new_tokens=96)
    text = ' '.join(s.text.strip() for s in segments)
    seconds = time.perf_counter() - started
    assert 'country' in text.casefold(), text
    voice = load_voice(root / 'piper-vi' / PIPER_VOICE)
    started = time.perf_counter()
    samples = 0
    peak = 0.0
    for chunk in voice.synthesize('Xin chào. Chúc bạn một ngày tốt lành.'):
        assert np.isfinite(chunk.audio_float_array).all()
        samples += len(chunk.audio_float_array)
        peak = max(peak, float(np.abs(chunk.audio_float_array).max()))
    assert samples > voice.config.sample_rate // 2 and peak > 0.01, (samples, peak)
    return dict(status='passed', recognized=text, asr_seconds=round(seconds, 3),
                tts_seconds=round(time.perf_counter() - started, 3),
                audio_seconds=round(samples / voice.config.sample_rate, 3),
                asr_device='cpu', asr_compute_type=model.model.compute_type,
                tts_provider=voice.session.get_providers())
