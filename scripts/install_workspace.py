"""Prepare a new offline workspace; never overwrite an existing directory."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from _common import SafetyError, checked_path, disjoint, extended, relative_name, sha256, utc

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = 'runtime/setup-receipt.json'
MAX_FILES = 512
MAX_FILE_BYTES = 200_000
MAX_TOTAL_BYTES = 20_000_000
LOCAL_IGNORE = b'\n# Installed workspace: never publish personal notes.\n/vault-template/\n/runtime/\n/control/\n'
FORBIDDEN = {'.git', '.obsidian', 'private', 'local', 'runtime', 'control', 'receipts', 'backups', 'snapshots'}


def allowed_name(value: str) -> str:
    name = relative_name(value)
    if any(part.casefold() in FORBIDDEN or part.casefold().startswith('.env') for part in name.split('/')):
        raise SafetyError('Private or runtime paths are not installable')
    return name


def write_new(file: Path, data: bytes) -> None:
    checked_path(file.parent)
    extended(file.parent).mkdir(parents=True, exist_ok=True)
    checked_path(file)
    with extended(file).open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def payload(source: Path) -> dict[str, bytes]:
    source = checked_path(source, directory=True)
    listing = checked_path(source / 'PUBLIC_FILES.txt')
    if listing.stat().st_size > MAX_FILE_BYTES:
        raise SafetyError('Oversized allowlist')
    names = [allowed_name(x) for x in listing.read_text(encoding='utf-8-sig').splitlines()
             if x and not x.startswith('#')]
    if not 1 <= len(names) <= MAX_FILES or len({x.casefold() for x in names}) != len(names):
        raise SafetyError('Duplicate, ambiguous or oversized allowlist')
    required = {'PUBLIC_FILES.txt', 'VERSION', '.gitignore', 'START_HERE.md', 'AI_START_HERE.md',
                'AGENTS.md', 'CLAUDE.md', 'GEMINI.md', '.github/copilot-instructions.md',
                '.cursor/rules/project-memory.mdc', 'vault-template/首页.md'}
    if not required <= set(names):
        raise SafetyError('Incomplete installation source')
    result, original, total = {}, {}, 0
    for name in names:
        file = checked_path(source / name)
        if not file.is_file() or file.stat().st_size > MAX_FILE_BYTES:
            raise SafetyError('Missing or oversized public file')
        data = extended(file).read_bytes()
        total += len(data)
        if total > MAX_TOTAL_BYTES or b'\x00' in data:
            raise SafetyError('Binary or oversized payload')
        data.decode('utf-8-sig')
        original[name] = hashlib.sha256(data).hexdigest().upper()
        result[name] = data + LOCAL_IGNORE if name == '.gitignore' else data
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[a-zA-Z0-9.-]+)?', result['VERSION'].decode().strip()):
        raise SafetyError('Invalid version')
    if any(sha256(checked_path(source / name)) != value for name, value in original.items()):
        raise SafetyError('Source changed during preflight')
    return result


def installation_report(target: Path) -> dict:
    target = checked_path(target, directory=True)
    receipt = checked_path(target / RECEIPT)
    if not receipt.is_file() or receipt.stat().st_size > MAX_FILE_BYTES:
        raise SafetyError('Existing folder is foreign or partial; choose a different new target')
    info = json.loads(receipt.read_text(encoding='utf-8-sig'))
    if not isinstance(info, dict):
        raise SafetyError('Installation receipt must be a JSON object')
    files = info.get('files')
    if (info.get('kind') != 'obsidian-memory-workspace' or info.get('status') != 'FILES_VERIFIED'
            or info.get('schema_version') != 1 or not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES):
        raise SafetyError('Invalid installation receipt')
    if len({name.casefold() for name in files}) != len(files):
        raise SafetyError('Ambiguous receipt inventory')
    changed = []
    for name, value in files.items():
        allowed_name(name)
        if not isinstance(value, str) or not re.fullmatch(r'[0-9A-Fa-f]{64}', value):
            raise SafetyError('Invalid installed hash')
        file = checked_path(target / name)
        if not file.is_file() or sha256(file) != value.upper():
            changed.append(name)
    return {'status': 'ALREADY_PRESENT_USER_DATA_PRESERVED', 'version': info.get('version'),
            'changed_files': changed, 'file_count': len(files), 'written': False,
            'ai_acceptance': 'NOT_TESTED', 'target': str(target)}


def install(source: Path, target: Path, *, preview: bool = False) -> dict:
    source = checked_path(source, directory=True)
    target = checked_path(target)
    disjoint(source, target)
    if target.exists():
        return installation_report(target)
    if not target.parent.is_dir():
        raise SafetyError('Target parent must already exist')
    if any((parent / '.git').exists() for parent in target.parents):
        raise SafetyError('Use a new target outside existing Git repositories')
    data = payload(source)
    if preview:
        return {'status': 'PREVIEW', 'file_count': len(data), 'target': str(target), 'written': False}
    # Exclusive creation reserves the destination. Partial work is kept, never certified or removed.
    extended(target).mkdir(exist_ok=False)
    hashes = {}
    for name, content in data.items():
        file = target / name
        write_new(file, content)
        value = hashlib.sha256(content).hexdigest().upper()
        if sha256(file) != value:
            raise SafetyError('Copy readback failed; partial installation is preserved')
        hashes[name] = value
    for name, value in hashes.items():
        if sha256(checked_path(target / name)) != value:
            raise SafetyError('Installed content changed; no success marker written')
    receipt = {'schema_version': 1, 'kind': 'obsidian-memory-workspace', 'status': 'FILES_VERIFIED',
               'version': data['VERSION'].decode().strip(), 'created_at_utc': utc(), 'files': hashes,
               'scope': 'local files only; no account, model, plugin, schedule or permission changes',
               'ai_acceptance': 'NOT_TESTED'}
    content = (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    write_new(target / RECEIPT, content)
    if extended(target / RECEIPT).read_bytes() != content:
        raise SafetyError('Receipt readback failed; do not certify installation')
    return {'status': 'INSTALLED_FILES_VERIFIED', 'file_count': len(hashes), 'written': True,
            'target': str(target), 'ai_acceptance': 'NOT_TESTED', 'start': str(target / 'START_HERE.md')}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, default=Path.home() / 'AI-Memory-Workspace')
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    try:
        result = install(ROOT, args.target, preview=args.preview)
    except (SafetyError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({'status': 'FAILED_NO_OVERWRITE', 'reason': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
