"""Local cache of each confirmed form's parameter keys (for 'similar form' ranking).

Ranking a new form against existing ones used to open *every* recipe's latest
form workbook in the shared OneDrive folder on every parse — a burst of shared
reads. The keys only change when the form file changes, so they are cached in
the local Cache folder keyed by path + (mtime, size); an unchanged form is only
stat()-ed, never re-opened.
"""
from __future__ import annotations

import json
import os

from . import atomicfile, formbuilder, locking, workdirs

CACHE_NAME = "form_params_cache.json"


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def similar_forms(save_dir: str, local_root: str, exclude: str | None = None) -> dict[str, set]:
    """{recipe: parameter-key set} for each recipe's latest confirmed form."""
    cache_dir = os.path.join(local_root, "Cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, CACHE_NAME)
    cache = _load(cache_path)
    out, dirty, seen = {}, False, set()
    for recipe in workdirs.list_recipes(save_dir):
        if recipe == exclude:
            continue
        form = workdirs.latest_form(save_dir, recipe)
        if not form:
            continue
        seen.add(form)
        stamp = list(locking.file_stamp(form) or ())
        hit = cache.get(form)
        if hit and hit.get("stamp") == stamp:
            out[recipe] = {tuple(k) for k in hit.get("keys", [])}
            continue
        try:
            keys = formbuilder.form_params(form)
        except Exception:  # noqa: BLE001 - a similarity hint must not block the form
            continue
        out[recipe] = keys
        cache[form] = dict(stamp=stamp, keys=sorted(list(k) for k in keys))
        dirty = True
    stale = [p for p in cache if p not in seen and p.startswith(os.path.abspath(save_dir))]
    for p in stale:
        cache.pop(p, None)
        dirty = True
    if dirty:
        atomicfile.write_json(cache_path, cache)     # local Cache only
    return out
