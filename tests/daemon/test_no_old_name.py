"""The app is Armrest since 0.5.0: the old CouchJarvis name must not creep back into the code.

What still says CouchJarvis does so on purpose, to keep existing installs working (plan.md 14.3).
Each such file is listed with how many mentions it may have; anything else fails.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OLD_NAME = re.compile(r"couch.?jarvis", re.IGNORECASE)
CODE = ("pc-daemon", "web-remote/src", "web-remote/public", "installer", "scripts", "infra")
ROOT_FILES = ("pyproject.toml", ".env.example", "web-remote/package.json", "web-remote/index.html")

ALLOWED = {
    "pc-daemon/app_dirs.py": 6,  # the folder move
    "pc-daemon/app_entry.py": 4,  # the old single-instance name, the move
    "pc-daemon/brand.py": 3,  # the retired Vercel addresses, the history note
    "pc-daemon/config.py": 1,  # paths into a moved folder
    "pc-daemon/lan_auth.py": 3,  # the token issuer phones hold
    "infra/lambdas/common/auth.py": 3,  # the same, on the relay
    "infra/template.yaml": 1,  # "formerly CouchJarvis"
    "infra/samconfig.toml": 2,  # the relay stack keeps its name
    "installer/Armrest.iss": 6,  # the old exe, data folders, startup entry and shortcuts
    "installer/build_msix.ps1": 2,  # the local test certificate (replaced by Partner Center's)
    "scripts/test_installer_upgrade.ps1": 25,  # installs the old app and checks the move
    "web-remote/src/brand.ts": 1,  # why phone storage keeps its keys
    "web-remote/src/utils/storage.ts": 1,  # the IndexedDB name
    # until the GitHub repo is renamed (GitHub then redirects the old address)
    "pc-daemon/update_check.py": 1,
    "web-remote/src/App.tsx": 1,
}


def _tracked() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "--", *CODE, *ROOT_FILES],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [f for f in out.splitlines() if (ROOT / f).is_file()]


def test_the_old_name_only_appears_where_migration_needs_it() -> None:
    found: dict[str, int] = {}
    for rel in _tracked():
        try:
            text = (ROOT / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary (icons, fonts)
        count = len(OLD_NAME.findall(text))
        if count:
            found[rel] = count
    unexpected = {f: n for f, n in found.items() if n > ALLOWED.get(f, 0)}
    assert not unexpected, (
        f"CouchJarvis is back (rename it, or allow it here with a reason): {unexpected}"
    )
