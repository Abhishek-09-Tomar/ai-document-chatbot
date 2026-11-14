"""Scan tracked files and reachable history; report locations, never secret values."""
import json
from pathlib import Path
import re
import shutil
# Git arguments are fixed below; object identifiers come from Git, never uploaded content.
import subprocess  # nosec B404
import sys

ROOT = Path(__file__).resolve().parents[1]
GIT = shutil.which('git')
PATTERNS = {
    'hugging_face': rb'hf_[A-Za-z0-9]{20,}',
    'openai': rb'sk-(?:proj-)?[A-Za-z0-9_-]{20,}',
    'github': rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})',
    'private_key': rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
    'aws_access': rb'AKIA[0-9A-Z]{16}',
}


def git(*args):
    if GIT is None:
        raise RuntimeError('Git is required for the secret scan.')
    return subprocess.check_output([GIT, *args], cwd=ROOT)  # nosec B603


def inspect(data, location, revision):
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        data = data.decode('utf-16').encode('utf-8')
    return [{'kind': kind, 'path': location, 'revision_or_blob': revision}
            for kind, pattern in PATTERNS.items() if re.search(pattern, data)]


def main():
    findings = []
    for name in git('ls-files', '-z').decode().split('\0'):
        if name and (ROOT / name).is_file():
            findings.extend(inspect((ROOT / name).read_bytes(), name, 'working-tree'))
    objects = git('rev-list', '--objects', '--all').decode().splitlines()
    for line in objects:
        oid, _, name = line.partition(' ')
        if git('cat-file', '-t', oid).strip() == b'blob':
            findings.extend(inspect(git('cat-file', 'blob', oid), name, oid))
    print(json.dumps({'findings': findings, 'reachable_objects_scanned': len(objects)}, indent=2))
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
