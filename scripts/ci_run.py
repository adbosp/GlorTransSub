"""Stream CI output and surface command failures in GitHub's run annotations."""
import argparse
from collections import deque
import os
from pathlib import Path
import re
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == '--':
        command = command[1:]
    if not command:
        parser.error('A command is required.')
    if command[0] == 'python':
        command[0] = sys.executable
    log_dir = Path('build')
    log_dir.mkdir(exist_ok=True)
    tail = deque(maxlen=12)
    errors = deque(maxlen=10)
    label = re.sub(r'[^A-Za-z0-9_-]', '-', args.label)
    with (log_dir / f'{label}.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace',
                                   env={**os.environ, 'PYTHONUNBUFFERED': '1'})
        for line in process.stdout:
            print(line, end='', flush=True)
            log.write(line)
            tail.append(line.rstrip()[:1200])
            if re.search(r'(Traceback|[A-Za-z]+Error:|\bERROR\b|recursion)', line, re.IGNORECASE):
                errors.append(line.rstrip()[:1200])
        result = process.wait()
    if result:
        detail = ('\n'.join(errors) + '\nRecent output:\n' + '\n'.join(tail))[:6000]
        escaped = detail.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print(f'::error title={label}::{escaped}', flush=True)
    else:
        print(f'::notice title={label}::Completed successfully.', flush=True)
    return result


if __name__ == '__main__':
    sys.exit(main())
