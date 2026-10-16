"""Download/convert one bilingual Marian OPUS-MT model for offline use.

Example: python prepare_opus_model.py --source en --target vi --output models/opus-en-vi
Conversion needs requirements.txt and requirements-opus-build.txt installed.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile

from opus_mt import MANIFEST, language_code


def prepare_model(source, target, output, model=None, revision=None):
    source, target = language_code(source), language_code(target)
    if not all(re.fullmatch(r'[a-z]{2,3}', code) for code in (source, target)):
        raise ValueError('Use explicit two/three-letter language codes, for example en and vi.')
    model = model or f'Helsinki-NLP/opus-mt-{source}-{target}'
    if not model.startswith('Helsinki-NLP/opus-mt-') or not model.endswith(f'-{source}-{target}'):
        raise ValueError('The model ID must be a bilingual Helsinki-NLP OPUS-MT model matching the declared pair.')
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise ValueError(f'Output already exists: {output}. Choose a new folder.')
    from huggingface_hub import snapshot_download
    from transformers import MarianTokenizer, AutoConfig
    from ctranslate2.converters import TransformersConverter

    # Resolve a single snapshot before conversion so tokenizer and weights
    # always come from the same revision. Never execute model repository code.
    snapshot = snapshot_download(
        model, revision=revision,
        allow_patterns=['*.json', '*.spm', '*.safetensors', 'pytorch_model.bin',
                        'README.md', 'LICENSE*'],
    )
    config = AutoConfig.from_pretrained(snapshot, local_files_only=True, trust_remote_code=False)
    if config.model_type != 'marian':
        raise ValueError('Only Marian OPUS-MT models are supported.')
    tokenizer = MarianTokenizer.from_pretrained(snapshot, local_files_only=True)
    if tokenizer.supported_language_codes:
        raise ValueError('Choose a bilingual OPUS-MT model; multilingual target prefixes are not supported.')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='glosub-opus-', dir=output.parent) as staging:
        converted = Path(staging) / 'converted'
        TransformersConverter(snapshot).convert(str(converted), quantization='int8')
        tokenizer.save_pretrained(str(converted))
        metadata = {
            'format_version': 1, 'model_id': model,
            'revision': Path(snapshot).name, 'source_lang': source, 'target_lang': target,
            'normalizer_lang': tokenizer.source_lang,
            'eos_token': tokenizer.eos_token,
            'special_tokens': tokenizer.all_special_tokens,
        }
        (converted / MANIFEST).write_text(json.dumps(metadata, indent=2), encoding='utf-8')
        for name in ('README.md', 'LICENSE', 'LICENSE.md', 'LICENSE.txt'):
            if (Path(snapshot) / name).is_file():
                shutil.copy2(Path(snapshot) / name, converted / name)
        converted.rename(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--model', help='Optional Helsinki-NLP model ID for the declared language pair')
    parser.add_argument('--revision', help='Optional model commit SHA/tag')
    args = parser.parse_args()
    try:
        output = prepare_model(args.source, args.target, args.output, args.model, args.revision)
    except Exception as exc:
        parser.exit(1, f'OPUS-MT preparation failed: {exc}\n')
    print(f'Prepared CPU INT8 model: {output}')
    print('Select OPUS-MT in Settings and choose this folder. Runtime needs no Internet.')


if __name__ == '__main__':
    main()
