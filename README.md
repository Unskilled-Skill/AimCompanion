# Aim Companion

Aim Companion is a local Windows desktop companion for Kovaak's and Voltaic S5.
It imports result CSVs, calculates benchmark progress, recommends adaptive aim
training, tracks live scenario blocks, and exports Kovaak's playlists.

## Install on Windows

Download `AimCompanion-Setup.exe` from the
[latest GitHub release](https://github.com/Unskilled-Skill/AimCompanion/releases/latest),
then run the installer. The app installs for the current Windows user and does
not require administrator access by default.

Version 1.0.0 is not Authenticode-signed, so Windows may display an Unknown
Publisher warning. Every release includes `AimCompanion-Setup.exe.sha256` for
independent integrity verification.

## Automatic updates

The installed app checks the public GitHub Releases API shortly after startup.
When a newer semantic version is available, Aim Companion asks before downloading
or installing anything. The installer is accepted only when its SHA-256 hash
matches the digest published with the release. Automatic checks can be disabled
under **Settings -> Updates**.

Updates replace only program files. User scores, settings, backups, and training
history stay in `%LOCALAPPDATA%\AimCompanion`.

## Run from source

Requires Python 3.11 or newer.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

On first launch, confirm the Kovaak's installation folder and preferences.
Writable data is stored in `%LOCALAPPDATA%\AimCompanion`; bundled JSON under
`data/` remains read-only. Existing `data/kovaaks.db` and `data/config.json`
files are copied forward automatically the first time the new storage location
is used.

## Development

```powershell
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m compileall -q core models ui tests
```

## Build a Windows release

```powershell
winget install JRSoftware.InnoSetup
pip install -r requirements-dev.txt
.\scripts\build_release.ps1
```

The portable executable, installer, and checksum are written to `dist/`. Tagged
commits matching `v*` are built and published by the Windows release workflow.
Test first-run setup, score-folder detection, Steam launching, notifications,
automatic updates, and backup restoration on a clean Windows account before
publishing.

## Data safety

Use **Backup data -> Full Backup** before moving machines or installing a major
update. A full backup contains scores, sessions, saved routines, settings, and
training preferences. Restore replaces the current local data after confirmation.
