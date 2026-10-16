# GloSub v1.1.2 — Windows x64

Download GloSub-v1.1.2-Windows-x64.zip, extract the entire folder to a writable
location, close any previous GloSub instance, then run GloSub.exe.
Keep _internal and models next to GloSub.exe. No Python/pip setup is needed.
Existing user settings remain under %LOCALAPPDATA%\GloSub.

Changes:
- Bound translation caching and remove the unbounded duplicate OCR cache.
- Start Voice workers and audio playback only when speech is actually requested.
- Release captured images before waiting for translation requests.
- Add optional OPUS-MT + CTranslate2 offline CPU INT8 translation.
- Include a prepared English-to-Vietnamese model and English OCR weights.
- Refresh OpenAI, Gemini and DeepSeek defaults; existing saved selections remain.

For offline translation, select English as Input Language, Vietnamese as Translate
To, and OPUS-MT in Settings. The bundled model folder is filled automatically when
no custom folder has been saved. Use Test Offline Translation, then Apply/Save.
The local engine does not fall back to Google when it fails. LLM context/glossary
rules are bypassed for OPUS-MT. Voice is a separate setting; cloud speech providers
still need Internet and any required credentials. Other OCR languages may need a
first-use model download.

The release workflow checks Windows imports, compiled CPU operators, a Qt widget,
English OCR and actual OPUS-MT inference in both source and the packaged executable.
These smoke checks do not replace extended testing on your own Windows desktop.
The application is unsigned; verify the ZIP against SHA256SUMS.txt before running.
