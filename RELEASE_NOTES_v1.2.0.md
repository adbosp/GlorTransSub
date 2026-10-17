# GloSub v1.2.0 — Vietnamese game/video dubbing

Extract the whole Windows x64 ZIP, close the older app from the system tray,
then open GloSub.exe. Keep _internal and models alongside the executable.

Open Settings → Speech → Vietnamese. Choose the game/video output to listen to,
then Start dubbing. The included Tiny English ASR, OPUS-MT English → Vietnamese
and Piper Vietnamese voice run locally on CPU. Select the OPUS model folder in
General and save if you previously configured another model. No speech download
is needed with the included models. Other languages require Tiny/Base multilingual
and a matching OPUS model, or the explicitly selected online Google translator.

On the same listening/playback output, listening pauses during the Vietnamese
voice to prevent feedback. Dialogue during that time can be missed. For continuous
listening, route the game and Vietnamese voice to separate audio output devices.
F8 stops active dubbing; the panel also has a Stop button. OCR pauses and releases
its model during dubbing. Only the latest waiting audio clip is retained; stale
clips are discarded. Transcripts stay in a bounded on-screen history, not a file.

Designed around an i5 14th gen / RTX 3060 / 32 GB PC, with CPU inference to leave
the GPU for games. Actual latency depends on audio, game load and phrase length;
Tiny trades recognition accuracy for speed. This is a segmented ASR → translation
→ TTS pipeline, without original speaker voice preservation.

Both source and packaged executable checks exercise actual ASR, Vietnamese speech
synthesis, English OCR and OPUS translation. Audio-device behavior still requires
testing on the user's Windows PC. See THIRD_PARTY_SPEECH.md for licenses/source.
