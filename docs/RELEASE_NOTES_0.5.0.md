# Armrest 0.5.0

The rename is finished. Since 0.4.0 the app looked like Armrest, but on your PC it still ran as `CouchJarvis.exe`
from CouchJarvis folders. Now the program, its folders, the installer and the startup entry are all Armrest. There
are no new features.

**Free preview:** 0.x versions stay free with no trial and no licence key.

## Update from 0.4.0 or 0.2.0

Run `Armrest-Setup.exe`. It finds your install (under its old name too) and updates it in place: it closes the app,
installs over it and starts it again. Nothing needs re-pairing this time.

On its first start, Armrest moves your data from the `CouchJarvis` folders in `%APPDATA%` and `%LOCALAPPDATA%` to
`Armrest` folders. That covers your settings, room keys, paired phones, favourites, and the TV browser profile, so
you stay signed in to your streaming sites. Each folder moves in one step: you have either all of the old folder or
all of the new one, never half. A note is left in each old folder; you can delete those folders afterwards.

If the TV browser is still open when Armrest starts, its folder is kept where it is and used from there. It moves on
a later start, once the browser has been closed.

## Good to know
- **Your settings file:** it is now `%APPDATA%\Armrest\config.env`. New settings start with `ARMREST_`. Lines that
  start with `CJ_` keep working, and the app never rewrites them. Where a file has both, `ARMREST_` wins.
- **In Task Manager** the app is now `Armrest.exe`. The startup entry is renamed too.
- **Your install folder stays where it was** (for example `Programs\CouchJarvis`). Only new installs go to
  `Programs\Armrest`.
- **Going back to 0.4.0 isn't supported:** it would look for the old folders and start fresh. Stay on 0.5.0.
- The installer isn't code-signed, so Windows SmartScreen may warn on first run ("More info" → "Run anyway").

## Files
| File | SHA-256 |
|---|---|
| `Armrest-Setup.exe` (recommended) | `a8698f1f06e24429a58e9dd0f88df4030c442886202ea3e4353e9414e5b4a064` |
| `Armrest-portable-0.5.0.zip` | `42bc79fba57bb7855f9e395f3428ebcdf9ad175a4d5859eb59bfa8b0a0c8912e` |

## Checked before release
Automated: 1,039 Python tests, 209 phone-app tests, linting, type checks, and the licence and secret scans. A new
test fails if the old name appears outside the migration code.

Upgrade test, from the published 0.4.0 and from 0.2.0: 33 of 33 checks passed each time, on a sandboxed copy of an
old install. They cover:
- the update stays in the same folder, and `Armrest.exe` replaces `CouchJarvis.exe`
- the running app is closed, and started again afterwards
- the startup entry is renamed
- both single-instance names are held, and a second launch exits
- `room.json`, `config.env` and the browser sign-ins moved byte for byte, with only the note left behind
- one Start-menu shortcut that points at `Armrest.exe`
- uninstalling keeps your data

Not yet checked: the move on your real install with a real TV and phone.
