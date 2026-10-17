# Speech component attribution and source

GloSub's own source remains available under its MIT license. A distribution
including Piper also contains GPL-3.0-or-later components; their license and
source obligations apply to those distributions. Preserve their notices.
The Windows ZIP includes the complete Piper 1.8.0 and matching eSpeak NG source
archives in `sources/`, including the native bridge and build instructions.

- Faster-Whisper 1.2.1 (MIT): https://github.com/SYSTRAN/faster-whisper/tree/v1.2.1
- Whisper models and test recording (MIT): https://github.com/openai/whisper
- CTranslate2 (MIT): https://github.com/OpenNMT/CTranslate2
- Piper 1.8.0 (GPL-3.0-or-later), including eSpeak NG components:
  https://github.com/OHF-Voice/piper1-gpl/tree/v1.8.0
  License: https://github.com/OHF-Voice/piper1-gpl/blob/v1.8.0/COPYING
- eSpeak NG (GPL-3.0-or-later): https://github.com/espeak-ng/espeak-ng
- Vietnamese vais1000 voice: https://huggingface.co/rhasspy/piper-voices/tree/main/vi/vi_VN/vais1000/medium
  Its MODEL_CARD accompanies the downloaded model. The VAIS-1000 dataset is
  credited there under CC BY 4.0: https://creativecommons.org/licenses/by/4.0/
- ONNX Runtime (MIT): https://github.com/microsoft/onnxruntime
- PyAudioWPatch (MIT): https://github.com/s0d3s/PyAudioWPatch
- PyAV (BSD-3-Clause) and its FFmpeg dependencies: https://github.com/PyAV-Org/PyAV

Speech models are downloaded at pinned revisions in prepare_speech_models.py.
No voice cloning, speaker imitation or training data collection is performed.
