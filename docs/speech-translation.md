# Vietnamese game/video dubbing

Open **Settings → Speech → Vietnamese**. Choose the Windows output carrying your
game or video, and choose where to play Vietnamese. Press **Start dubbing**.
It records only after you start. **Stop** or F8 ends the session. OCR is suspended
and its model released during the session; it resumes after stopping.

For the requested i5 14th generation, RTX 3060 12 GB and 32 GB RAM, the default is
Faster-Whisper Tiny English, four CPU threads, INT8, beam size one, plus CPU INT8
OPUS-MT and a Piper Vietnamese ONNX voice using two threads. This leaves the GPU
for the game and requires no CUDA installation. This is a small ASR → translation
→ TTS pipeline, not a voice-cloning or single-model S2ST system.

The v1.2.0 ZIP includes English speech recognition and Vietnamese voice models.
Source installations need `pip install -r requirements-speech.txt` in addition to
the base requirements, then **Download speech models** (or
`python prepare_speech_models.py --output models/speech`). Downloading is explicit
and runs in the background. Inference uses local files only. The default speech
translation is OPUS-MT: select the matching model folder in General and save.
Google is a separate, explicit online option and sends recognized text to Google.
No online speech recognition or cloud TTS is used by this feature.

The pinned Tiny English weights occupy about 75.5 MB and the Vietnamese Piper
weights about 63.2 MB on disk. RAM usage is higher and also includes the app,
decoder state, OPUS model and native libraries. This is not a whole-app RAM limit.
Tiny is fast but less accurate, especially with music, accents and short fragments.
Choose **Base multilingual** for better recognition if Tiny makes too many errors.
For Japanese, Korean or other listed languages, select a multilingual model and
a matching OPUS source → Vietnamese model; the bundled OPUS model is English only.

Audio is read in 50 ms blocks, ended after about 400 ms of quiet or at three
seconds, then passed through speech VAD. Only one clip waits while the worker is
busy; a newer clip replaces it. Clips more than eight seconds old are dropped.
Under heavy load this deliberately skips speech instead of accumulating delay.
The transcript view retains at most 40 lines and is not written to disk.

**Avoiding feedback:** WASAPI loopback hears everything played to the selected
output, including GloSub itself. On the same output, the app therefore skips
capture while speaking and for a short tail afterward; dialogue during that time
can be lost. To listen continuously, configure the game to use output A and the
Vietnamese voice to use a distinct output B. Distinct software devices that are
mixed back into A can still feed back. Re-select devices after changing the
Windows default output or unplugging a headset. The app captures a whole output,
not one game process.

Local cloud-runner model checks recognized the Whisper JFK fixture and produced
a non-silent Vietnamese waveform on CPU. They do not establish latency on your PC:
end-to-end latency also includes waiting for a phrase boundary, CPU contention,
translation, synthesis and playback. Listen and adjust the model using your game.
Windows release checks repeat real ASR, Piper synthesis and UI/native imports in
the frozen executable; CI does not have your physical audio devices.

See [speech component sources and licenses](../THIRD_PARTY_SPEECH.md). The Piper
model's MODEL_CARD is retained beside the weights. No original speaker voice is
preserved, and generated speech should be recognizable as translated dubbing.
