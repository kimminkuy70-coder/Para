"""Program editions (v14.4, owner 2026-11-23): one install, one update, two starters.

  full = AOI Manager       — every feature (the program until v14.3; 'Camtek AOI Manager' before)
  mini = AOI Manager Mini  — the same program with fewer features, for people outside the AOI process

Both editions are the same files in the same install folder: `AOI_Manager.bat` starts the full one,
`AOI_Manager_Mini.bat` the same start file with ``--mini``. The owner hands out the zip without the
full .bat. An update replaces `app/` for both at once (there is only one program), so a change to a
feature that Mini shows reaches Mini by itself.

What Mini shows is decided in one place on each side — the screen (`frontend/src/edition.ts`,
`MINI_TABS`) and here (`MINI` features the engine needs to know). The limit is a simpler screen,
not a security lock: the code of every feature is on the PC.
"""
from __future__ import annotations

import os

FULL, MINI = "full", "mini"
ENV = "PARA_EDITION"
FLAG = "--mini"

NAMES = {FULL: "AOI Manager", MINI: "AOI Manager Mini"}
SHORTCUTS = {FULL: "AOI Manager.lnk", MINI: "AOI Manager Mini.lnk"}
# Shortcut names of earlier releases: replaced by the new one (we made them, nothing else).
OLD_SHORTCUTS = {FULL: ("Camtek AOI Manager.lnk",), MINI: ()}
STARTERS = {FULL: "AOI_Manager.bat", MINI: "AOI_Manager_Mini.bat"}


def from_argv(argv) -> str:
    return MINI if FLAG in [str(a).strip().lower() for a in (argv or [])] else FULL


def current() -> str:
    return MINI if os.environ.get(ENV, "").strip().lower() == MINI else FULL


def set_current(edition: str) -> None:
    os.environ[ENV] = MINI if edition == MINI else FULL


def is_mini(edition: str | None = None) -> bool:
    return (edition or current()) == MINI


def name(edition: str | None = None) -> str:
    return NAMES[MINI if is_mini(edition) else FULL]


def args(edition: str | None = None) -> list[str]:
    """Extra start-file arguments of this edition (desktop shortcut)."""
    return [FLAG] if is_mini(edition) else []


def watches_on(edition: str | None = None) -> bool:
    """Automatic analyses (parameter · Commonality · Batch Report) are full-edition features:
    Mini never runs them, even on a PC whose settings switched them on."""
    return not is_mini(edition)
