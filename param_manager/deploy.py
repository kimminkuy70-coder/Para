"""What a v13 install contains — one list, used by the release zip (CI), the updater
(which copies these out of a downloaded source zip) and the safety test.

Only what the program needs to run: no tests, tools, docs or CI files. The script-text
rule (#31 · #58 `Trojan:Script`) is checked over exactly these files
(`tests/test_deploy_files.py`).
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT_FILES = ("Camtek_AOI_manager.pyw", "LICENSE.txt")
TREES = ("param_manager", "frontend/dist", "vendor")
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}
# Never shipped, whatever the tree holds: executables and script files.
FORBIDDEN_SUFFIXES = {".exe", ".dll", ".pyd", ".bat", ".cmd", ".ps1", ".vbs", ".vbe", ".wsf",
                      ".hta", ".scr", ".msi", ".lnk", ".com", ".jse"}


def files(root) -> list[str]:
    """Relative paths ('/'-separated) of everything an install needs, sorted."""
    root = Path(root)
    out = [name for name in ROOT_FILES if (root / name).is_file()]
    for tree in TREES:
        base = root / tree
        if not base.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for name in sorted(filenames):
                if Path(name).suffix.lower() in SKIP_SUFFIXES:
                    continue
                out.append((Path(dirpath) / name).relative_to(root).as_posix())
    return sorted(out)


def forbidden(paths) -> list[str]:
    return [p for p in paths if Path(p).suffix.lower() in FORBIDDEN_SUFFIXES]
