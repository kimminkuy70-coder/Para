"""Build-side CLI for the package integrity manifest (logic: param_manager.desktop_package)."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from param_manager.desktop_package import MANIFEST, REQUIRED, create, inventory, verify, version  # noqa: E402,F401

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('create', 'verify'))
    parser.add_argument('folder', type=Path)
    parser.add_argument('--version')
    args = parser.parse_args()
    result = create(args.folder, args.version or '') if args.action == 'create' else verify(args.folder)
    print(result['product'], result['version'], 'integrity verified; not deployment approval')
