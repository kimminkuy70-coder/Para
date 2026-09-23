"""Writes into the shared save folder (OneDrive) — one file event per save.

Rule (2026-08 security alert 'Unusual High-Volume Directory Access'): the save
folder only ever receives the result file itself. No temporary files, no
rename dance, no repeated writes. The tkinter app saves workbooks straight
onto the target (`wb.save(path)`); here the workbook is serialised in the
local Temp folder first and then copied over the target in one write, so the
shared file is open for the shortest time and nothing else appears next to it.
"""
from __future__ import annotations

import json
import os
import shutil

from . import localdirs


def save_workbook(wb, path: str, local_root: str) -> None:
    run = localdirs.new_temp_run(localdirs.ensure(local_root), "shared-save")
    try:
        staged = os.path.join(run, "workbook.xlsx")
        wb.save(staged)
        shutil.copyfile(staged, path)          # single write to the shared file
    finally:
        localdirs.drop(run)


def write_json(path: str, data) -> None:
    """Small shared JSON (e.g. 값확인_셀색상.json): serialise first, then one write.
    Never atomicfile here — that leaves a temp file in the shared folder."""
    text = json.dumps(data, ensure_ascii=False)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
