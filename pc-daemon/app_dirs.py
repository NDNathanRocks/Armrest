"""Where the app keeps its files, and the one-time move out of the CouchJarvis folders (0.5.0).

The app was called CouchJarvis until 0.5.0. On the first run of a renamed build, its folders
under %APPDATA% and %LOCALAPPDATA% move to ``Armrest``. Each folder moves in one rename (atomic on
the same drive), so the app sees either all of the old folder or all of the new one, never half:
the room, the pairings and the TV browser's sign-ins all come along. A folder that cannot move
yet (Edge still has the TV profile open) stays where it is and is used from there; the move is
tried again on the next start. A moved folder leaves a note behind, which also tells this module
the move is done.

Inside an MSIX nothing moves: Windows virtualises these folders for the package.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

APP_DIR = "Armrest"
LEGACY_DIR = "CouchJarvis"
MOVED_NOTE = "MOVED_TO_ARMREST.txt"
_NOTE_TEXT = (
    "CouchJarvis is now called Armrest.\n"
    "Everything that was in this folder moved to the Armrest folder next to it.\n"
    "You can delete this folder.\n"
)


def roaming_base() -> Path:
    return Path(os.environ.get("APPDATA") or str(Path.home() / ".config"))


def local_base() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share"))


def _pick(base: Path) -> Path:
    """The old folder until it has moved, then the new one."""
    old = base / LEGACY_DIR
    if old.is_dir() and not (old / MOVED_NOTE).exists():
        return old
    return base / APP_DIR


def roaming_dir() -> Path:
    """%APPDATA%\\Armrest: settings, the room, pairings, favourites, the licence."""
    return _pick(roaming_base())


def local_dir() -> Path:
    """%LOCALAPPDATA%\\Armrest: logs, telemetry, the voice cache and the Edge TV profile."""
    return _pick(local_base())


def remap_legacy(path: Path) -> Path:
    """A path a config.env names inside a moved CouchJarvis folder, pointed at the new folder."""
    for base in (roaming_base(), local_base()):
        old = base / LEGACY_DIR
        if not (old / MOVED_NOTE).exists():
            continue
        try:
            rest = path.relative_to(old)
        except ValueError:
            continue
        return base / APP_DIR / rest
    return path


def move_legacy_folder(base: Path, clock: Callable[[], float] = time.time) -> str:
    """Move ``base\\CouchJarvis`` to ``base\\Armrest``. Returns what happened:
    ``moved``, ``nothing`` (no old folder, or moved before) or ``busy`` (try again next start)."""
    old, new = base / LEGACY_DIR, base / APP_DIR
    if not old.is_dir() or (old / MOVED_NOTE).exists():
        return "nothing"
    aside: Path | None = None
    if new.exists():
        # Something made the new folder before the move (a test run, a crash mid-way through a
        # first start). Keep it, out of the way: the old folder holds the user's real data.
        aside = base / f"{APP_DIR}.before-move-{int(clock())}"
        try:
            new.rename(aside)
        except OSError as exc:
            log.warning("cannot move %s yet: %s is in use (%s)", old, new, exc)
            return "busy"
    try:
        old.rename(new)
    except OSError as exc:
        if aside is not None:
            try:
                aside.rename(new)
            except OSError:
                log.exception("could not put %s back", new)
        log.warning("cannot move %s yet (in use?): %s; using it where it is", old, exc)
        return "busy"
    try:
        old.mkdir()
        (old / MOVED_NOTE).write_text(_NOTE_TEXT, encoding="utf-8")
    except OSError:
        log.exception("moved %s but could not leave the note", old)  # harmless: old is gone
    log.info("moved %s to %s", old, new)
    return "moved"


def move_legacy_folders(packaged: bool) -> dict[str, str]:
    """Run the move for both folders. Call it before anything opens a file in them."""
    if packaged:
        return {}
    return {
        "roaming": move_legacy_folder(roaming_base()),
        "local": move_legacy_folder(local_base()),
    }
