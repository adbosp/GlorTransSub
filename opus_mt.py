"""Local, bilingual OPUS-MT inference. No downloads or network fallback at runtime."""
import json
import os
from pathlib import Path
from threading import Lock

MANIFEST = 'glosub-opus.json'
LANGUAGE_ALIASES = {'zh-cn': 'zh', 'zh-tw': 'zh', 'he': 'he'}


def language_code(code):
    return LANGUAGE_ALIASES.get(code.lower(), code.lower())


class OpusMTEngine:
    name = 'opus_mt'

    def __init__(self, model_dir):
        if not model_dir:
            raise ValueError('Choose a converted OPUS-MT model folder first.')
        self.model = str(Path(model_dir).expanduser().resolve())
        root = Path(self.model)
        try:
            self.metadata = json.loads((root / MANIFEST).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise ValueError('Invalid OPUS-MT folder. Prepare it with prepare_opus_model.py.') from exc
        if self.metadata.get('format_version') != 1:
            raise ValueError('Unsupported OPUS-MT manifest version.')
        for field in ('source_lang', 'target_lang', 'eos_token', 'special_tokens'):
            if not self.metadata.get(field):
                raise ValueError(f'OPUS-MT manifest is missing {field}.')
        for name in ('model.bin', 'config.json', 'source.spm', 'target.spm'):
            if not (root / name).is_file():
                raise ValueError(f'OPUS-MT folder is missing {name}.')
        self.source_lang = language_code(self.metadata['source_lang'])
        self.target_lang = language_code(self.metadata['target_lang'])
        self._lock = Lock()
        self._translator = None
        self._source = None
        self._target = None
        self._normalizer = None

    def _load(self):
        if self._translator is not None:
            return
        try:
            import ctranslate2
            import sentencepiece
            from sacremoses import MosesPunctNormalizer
        except ImportError as exc:
            raise RuntimeError('Install optional offline dependencies: pip install -r requirements-opus.txt') from exc
        root = Path(self.model)
        source = sentencepiece.SentencePieceProcessor(model_file=str(root / 'source.spm'))
        target = sentencepiece.SentencePieceProcessor(model_file=str(root / 'target.spm'))
        translator = ctranslate2.Translator(
            self.model, device='cpu', compute_type='int8', inter_threads=1,
            intra_threads=min(4, os.cpu_count() or 1), max_queued_batches=1,
        )
        self._normalizer = MosesPunctNormalizer(self.metadata.get('normalizer_lang')).normalize
        self._source, self._target, self._translator = source, target, translator

    def translate(self, text, src, tgt):
        if language_code(src) != self.source_lang or language_code(tgt) != self.target_lang:
            raise ValueError(f'This OPUS-MT model supports {self.source_lang} → {self.target_lang} only. '
                             'Select matching input and output languages; auto detection is not supported.')
        with self._lock:
            self._load()
            translated_lines = []
            special = set(self.metadata['special_tokens'])
            for line in text.splitlines():
                if not line.strip():
                    translated_lines.append('')
                    continue
                tokens = self._source.encode(self._normalizer(line), out_type=str)
                # Chunk instead of silently truncating long input. Process one
                # chunk at a time to bound decoder memory and CPU parallelism.
                chunks = []
                for offset in range(0, len(tokens), 256):
                    source = tokens[offset:offset + 256] + [self.metadata['eos_token']]
                    results = self._translator.translate_batch(
                        [source], beam_size=2, max_input_length=0,
                        max_decoding_length=512,
                    )
                    if not results or not results[0].hypotheses:
                        raise RuntimeError('OPUS-MT returned no translation.')
                    pieces = [token for token in results[0].hypotheses[0] if token not in special]
                    chunks.append(self._target.decode(pieces))
                translated_lines.append(' '.join(chunks))
            return '\n'.join(translated_lines).strip()
