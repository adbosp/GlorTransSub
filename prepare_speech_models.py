"""Explicit, versioned speech model setup; inference never downloads files."""
import argparse
from pathlib import Path
import shutil
import tempfile

from speech_translation import PIPER_VOICE

ASR_MODELS = {
    'tiny.en': ('Systran/faster-whisper-tiny.en', '0d3d19a32d3338f10357c0889762bd8d64bbdeba'),
    'tiny': ('Systran/faster-whisper-tiny', 'd90ca5fe260221311c53c58e660288d3deb8d356'),
    'base': ('Systran/faster-whisper-base', 'ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66'),
}
VOICE_REPO = 'rhasspy/piper-voices'
VOICE_REVISION = 'c10ece1aade47bb51c153c893d14e5bf8e5b7117'
VOICE_FOLDER = 'vi/vi_VN/vais1000/medium'


def prepare(root, model='tiny.en', status=print):
    from huggingface_hub import snapshot_download, hf_hub_download
    root = Path(root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    repo, revision = ASR_MODELS[model]
    destination = root / model
    if not destination.is_dir():
        status(f'Downloading Faster-Whisper {model}…')
        temporary = Path(tempfile.mkdtemp(prefix='.asr-', dir=root))
        try:
            snapshot_download(repo, revision=revision, local_dir=str(temporary),
                              allow_patterns=['model.bin', 'config.json', 'tokenizer.json',
                                              'preprocessor_config.json', 'vocabulary.*',
                                              'README.md', 'LICENSE*'])
            for name in ('model.bin', 'config.json', 'tokenizer.json'):
                if not (temporary / name).is_file():
                    raise ValueError(f'Download is missing {name}.')
            temporary.rename(destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    voice_root = root / 'piper-vi'
    if not voice_root.is_dir():
        status('Downloading Vietnamese Piper voice (~64 MB)…')
        temporary = Path(tempfile.mkdtemp(prefix='.piper-', dir=root))
        try:
            for name in (PIPER_VOICE, PIPER_VOICE + '.json', 'MODEL_CARD'):
                downloaded = hf_hub_download(VOICE_REPO, f'{VOICE_FOLDER}/{name}', revision=VOICE_REVISION)
                shutil.copyfile(downloaded, temporary / name)
            temporary.rename(voice_root)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    status('Speech models are ready. No network is needed for local inference.')
    return destination, voice_root / PIPER_VOICE


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--model', choices=list(ASR_MODELS), default='tiny.en')
    args = parser.parse_args()
    prepare(args.output, args.model)
