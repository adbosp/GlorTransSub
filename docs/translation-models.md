# Translation models, OCR and offline OPUS-MT

Reviewed on 2026-10-16. Public documentation confirms model names and lifecycle;
no paid translation API was called, so account-specific access is not verified.

| Component | Previous setting | Finding / change |
| --- | --- | --- |
| OpenAI | `gpt-5-mini` | GPT-5 mini has an announced 2026-12-11 shutdown. New default: `gpt-5.4-mini`, a smaller supported model rather than a large reasoning model. |
| Gemini | `gemini-3.5-flash` | Google documents this as an alias routed to a newer Flash model. New default: `gemini-3.8-flash`. |
| DeepSeek | `deepseek-v4-flash` | Legacy accepted name, now served by V4.1 Flash. New default uses the recommended API name `deepseek-flash`. |
| Claude | `claude-sonnet-5` | A newer Sonnet 5.5 exists. Retain the existing default; add Sonnet 5.5 and Haiku 5.5 choices without automatically changing the user's model/cost. |
| xAI | `grok-4.3` | Still listed. Add `grok-4.7` as a choice; retain the default. |
| EasyOCR | `1.7.2` | Still the latest PyPI release at review time. Standard English recognition uses `english_g2`; other scripts can use generation 1 or 2. A current package does not mean its underlying weights are newly trained. |

Existing per-user model selections are preserved. Defaults in the bundled template
are updated; select a new model explicitly in Settings for an existing installation.
The model field remains editable. Use **Test AI Connection** to check access with
your actual account.

Sources:

- [OpenAI deprecations](https://developers.openai.com/api/docs/deprecations)
- [OpenAI SDK model names](https://github.com/openai/openai-python/blob/main/src/openai/types/shared/chat_model.py)
- [Gemini lifecycle](https://ai.google.dev/gemini-api/docs/deprecations)
- [DeepSeek models](https://api-docs.deepseek.com/quick_start/pricing)
- [Claude models](https://platform.claude.com/docs/en/about-claude/models/overview)
- [xAI models](https://docs.x.ai/developers/models)
- [EasyOCR releases](https://pypi.org/project/easyocr/) and [model definitions](https://github.com/JaidedAI/EasyOCR/blob/master/easyocr/config.py)

## Offline translation with OPUS-MT + CTranslate2

OPUS-MT is a bilingual translation model, not a replacement for OCR or a new LLM.
It is useful for local subtitle translation without per-request charges. Quality
on idioms, games and conversational context should be compared on your own text.
It also adds model RAM on top of EasyOCR: CPU INT8 makes it lighter, not free.

### Prepare a model once

In a Python development environment (Windows PowerShell shown):

```powershell
python -m pip install -r requirements.txt
python -m pip install -r requirements-opus-build.txt
python prepare_opus_model.py --source en --target vi --output "$env:LOCALAPPDATA\GloSub\models\opus-en-vi"
```

The helper downloads `Helsinki-NLP/opus-mt-en-vi`, converts it to CPU INT8, exports
its SentencePiece tokenizers and a `glosub-opus.json` manifest, and retains the
model card/license when supplied. It resolves one snapshot for both weights and
tokenizers. `--revision COMMIT_SHA` pins the model revision. An existing output
folder is never overwritten. Not every language pair has a bilingual OPUS model;
an unavailable pair must be handled by choosing a different engine/model.

Preparation needs Internet access to Hugging Face and its download CDN. If the
cloud reports a proxy 403, allow the reported hostname in environment settings;
a saved draft alone does not prove that the running network policy has changed.
Set `HF_HOME` to a writable cache directory if the default home is read-only.

### Select it in GloSub

1. Open **Settings → General → Language & Translation**.
2. Set **Input Language** to English and **Translate To** to Vietnamese.
3. Select **OPUS-MT (Offline · CPU INT8)**, then **Choose Model Folder**.
4. Choose the prepared folder and click **Test Offline Translation**, then Apply/Save.

For an already prepared model, only `requirements-opus.txt` is needed in addition
to the normal runtime requirements. Transformers is a conversion dependency;
local inference uses CTranslate2, SentencePiece and punctuation normalization.
For a Windows executable, install the optional runtime before building with
`GloSub.spec`. Converted weights stay in an external folder. Older executables
must be rebuilt to gain the new engine.

The local engine loads lazily, uses up to four CPU threads and serial inference,
and retains one selected model. Applying the same folder reuses that model.
Translation caching retains the existing 1,024-entry / 4 MiB string budget.
Long inputs are chunked at 256 SentencePiece tokens; line breaks are preserved.
Chunking can reduce quality across sentence boundaries. Language auto-detection,
multilingual target-prefix models and automatic pivot translation are not
implemented. Use a folder matching the selected source/target pair.

Context-history prompts and glossary placeholders are bypassed for OPUS-MT:
these markers require an instruction-following engine. Offline failures stay
offline and report an error; they never silently fall back to Google translation.
Voice is a separate setting: cloud TTS can still send the translated text online
if Voice is enabled. Disable Voice or choose an appropriate separate speech setup
when you want the entire workflow offline.

### Validation

```powershell
python -m unittest discover -s tests -v
$env:GLOSUB_TEST_CT2_CONVERSION="1"
python -m unittest discover -s tests -p test_opus_mt.py -v
$env:GLOSUB_OPUS_TEST_MODEL="$env:LOCALAPPDATA\GloSub\models\opus-en-vi"
python -m unittest discover -s tests -p test_opus_mt.py -v
```

The conversion check creates a tiny synthetic Marian model and exercises the
real converter, SentencePiece and CPU INT8 runtime. It tests machinery, not
translation quality. The pretrained test requires the actual converted English
→ Vietnamese model and is explicitly skipped when its folder is not supplied.
Native Windows GUI/hotkeys and executable packaging require Windows validation.

[CTranslate2's Marian integration](https://opennmt.net/CTranslate2/guides/transformers.html#marianmt)
