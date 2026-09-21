"""Offline whole-folder integrity manifest. No updater, downloader or deployment.

Hashes detect corruption, not publisher identity. Windows signing and trust gates
must be verified separately before this development package can be distributed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

MANIFEST = 'package-manifest.json'
REQUIRED = {'Camtek_AOI_manager.exe', 'sidecar/Camtek_AOI_engine.exe'}


def version(value):
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', value):
        raise ValueError('Desktop version must be MAJOR.MINOR.PATCH, for example 8.1.0')
    if any(int(n) > 65535 for n in value.split('.')):
        raise ValueError('Version components must be at most 65535')
    return value


def inventory(root):
    root = Path(root)
    if root.is_symlink():
        raise ValueError('Package root cannot be a link')
    result = {}
    for file in sorted(root.rglob('*')):
        if file.is_symlink() or (hasattr(file, 'is_junction') and file.is_junction()):
            raise ValueError('Package cannot contain links')
        if file.is_file() and file != root / MANIFEST:
            with file.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            result[file.relative_to(root).as_posix()] = {'sha256': digest, 'size': file.stat().st_size}
    if not REQUIRED <= result.keys():
        raise ValueError('UI and Python engine must both be present')
    return result


def create(root, app_version):
    root = Path(root)
    data = dict(schema_version=1, product='Camtek_AOI_manager', version=version(app_version),
                protocol_version=1, deployment_approved=False, files=inventory(root))
    # Never rewrite an existing manifest in place; an output must be a fresh build.
    with (root / MANIFEST).open('x', encoding='utf-8') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    return data


def verify(root):
    path = Path(root) / MANIFEST
    if path.is_symlink() or path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Invalid package manifest')
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or data.get('protocol_version') != 1 or data.get('product') != 'Camtek_AOI_manager':
        raise ValueError('Unsupported package manifest')
    version(data['version'])
    if data.get('files') != inventory(root):
        raise ValueError('Package files changed, are missing, or extra files were added')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('create', 'verify'))
    parser.add_argument('folder', type=Path)
    parser.add_argument('--version')
    args = parser.parse_args()
    result = create(args.folder, args.version or '') if args.action == 'create' else verify(args.folder)
    print(result['product'], result['version'], 'integrity verified; not deployment approval')
