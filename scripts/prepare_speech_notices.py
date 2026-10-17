"""Retain the Piper source distribution and dependency notices with the ZIP."""
import hashlib
from importlib import metadata
from pathlib import Path
import shutil
import sys

import requests


def main(destination):
    destination = Path(destination)
    notices = destination / 'third-party-licenses'
    notices.mkdir(parents=True, exist_ok=True)
    for package in ('piper-tts', 'faster-whisper', 'PyAudioWPatch', 'av', 'onnxruntime',
                    'ctranslate2', 'tokenizers', 'huggingface-hub'):
        dist = metadata.distribution(package)
        for entry in dist.files or []:
            if 'license' in str(entry).lower() or 'copying' in str(entry).lower():
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    output = notices / package / str(entry).replace('..', '_')
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, output)
    response = requests.get('https://pypi.org/pypi/piper-tts/1.8.0/json', timeout=30)
    response.raise_for_status()
    source = next(x for x in response.json()['urls'] if x['packagetype'] == 'sdist')
    target = destination / 'sources' / source['filename']
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with requests.get(source['url'], stream=True, timeout=(10, 120)) as response:
        response.raise_for_status()
        with target.open('wb') as output:
            for chunk in response.iter_content(1024 * 1024):
                output.write(chunk)
                digest.update(chunk)
    if digest.hexdigest() != source['digests']['sha256']:
        target.unlink()
        raise RuntimeError('Piper source checksum mismatch.')


if __name__ == '__main__':
    main(sys.argv[1])
