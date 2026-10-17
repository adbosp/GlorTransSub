"""Retain complete Piper/eSpeak source and dependency notices with the ZIP."""
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
        if package == 'PyAudioWPatch' and sys.platform != 'win32':
            continue
        dist = metadata.distribution(package)
        for entry in dist.files or []:
            if 'license' in str(entry).lower() or 'copying' in str(entry).lower():
                source = Path(dist.locate_file(entry))
                if source.is_file():
                    output = notices / package / str(entry).replace('..', '_')
                    output.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, output)
    # Piper's PyPI sdist omits native espeakbridge.c/CMakeLists.txt. Use the
    # complete tagged repository and the exact eSpeak revision in its CMake.
    sources = [('OHF-Voice/piper1-gpl', '639388b6317fc4731e91d53da42aea68fd4166ff'),
               ('espeak-ng/espeak-ng', '724808c5a83f9ef95fdd0db886ba7ba537ff224a')]
    checksums = []
    for repo, revision in sources:
        target = destination / 'sources' / f'{repo.split("/")[1]}-{revision}.tar.gz'
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with requests.get(f'https://codeload.github.com/{repo}/tar.gz/{revision}',
                          stream=True, timeout=(10, 120)) as response:
            response.raise_for_status()
            with target.open('wb') as output:
                for chunk in response.iter_content(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
        checksums.append(f'{digest.hexdigest()}  {target.name}')
    (destination / 'sources' / 'SHA256SUMS.txt').write_text('\n'.join(checksums) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main(sys.argv[1])
