# Aim Companion

Aim Companion is a local Windows desktop companion for Kovaak's and Voltaic S5.
It imports result CSVs, calculates benchmark progress, recommends adaptive aim
training, tracks live scenario blocks, and exports Kovaak's playlists.

## Install on Windows

Download `AimCompanion-Setup.exe` from the
[latest GitHub release](https://github.com/Unskilled-Skill/AimCompanion/releases/latest),
then run the installer. The app installs for the current Windows user and does
not require administrator access by default.

Current releases are not Authenticode-signed, so Windows may display an Unknown
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

## Benchmark calculation and score importing

Aim Companion's official Voltaic S5 rank view uses the active, bundled
`kovaaks_s5` definition set. For the Best view, the calculator keeps the best
eligible imported score for each benchmark, then selects the highest scenario
energy in each required subcategory. Overall energy is the harmonic mean of all
nine required subcategories:

```text
subcategory energy = max(eligible scenario energies in that subcategory)
overall energy = 9 / sum(1 / subcategory energy for all nine subcategories)
```

No official overall energy or rank is shown until all nine subcategories have a
valid score. The definition snapshot records the public benchmark source,
version, retrieval time, and checksum; its bundled copy keeps this calculation
available offline. The checksum verifies the local snapshot payload. It does
not authenticate or prove the freshness of the remote Voltaic publication.
The header and Skill Matrix use Best scores for the official rank; Dashboard and
status text label Latest, 7-day, 30-day, and Recent 5 average selections as
local current-form analytics rather than official ranks.
See [benchmark data provenance](docs/benchmark-data-provenance.md) for the
exact version, checksum, cap behavior, and known daily update lag.

After startup, the app watches the configured Kovaak's stats directory and
imports changes in a debounced background batch, so score discovery does not
block the UI. Drag-and-drop, file selection, and **Import from Kovaak's** are
manual fallback paths through the same importer. Malformed or unreadable files
are recorded for retry while valid files in the same batch continue importing;
the affected file names and retry action remain visible. Imported paths retain a
content checksum, so unchanged files skip parsing while a changed or completed
file is re-imported transactionally without deleting unrelated history. The
recorded failure is cleared after a successful retry.

## Guided training modes

Aim Companion has three session modes:

- **Warm-up** remembers the last game or routine context and prepares the
  relevant movements without changing routine progress or benchmark freshness.
- **Step-by-Step Training** presents one evidence-backed 3–5 minute block at a
  time. Due benchmark checks come first; otherwise the three highest-priority
  weaknesses follow a deterministic 50/30/20 rotation without avoidable
  scenario or subcategory repeats. You can stop after any completed block.
- **Full Routine** preserves the selected source's scenario order, guide text,
  and complete prescribed run counts. If you stop early, the next session
  starts with unfinished material and makes exactly one circular pass.

Every detected or manually confirmed run is persisted. A partially completed
scenario restarts at its full run requirement in the next Full Routine session.
See [training modes](docs/training-modes.md) for the exact circular-resume example,
evidence fields, manual fallback, and fatigue opt-in behavior.

## Coaching-first interface

Home now leads with your official rank state, current weakness, evidence, and
three choices: Warm-up, Step-by-Step Training, or Full Routine. Session shows
the complete selected routine alongside a detailed current-scenario guide,
including purpose, setup, numbered actions, success criteria, adjustment rules,
prescribed runs, and the original source. An optional compact panel can stay on
top of Kovaak's and always reflects the same saved session state.

Progress combines the rank summary, nine skills, benchmark detail, and history.
Library holds complete routines, scenarios, warm-up references, and deathmatch
game-transfer guidance. Secondary utilities, import, settings, and backup live
under Tools.

## Development

```powershell
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
python -m compileall -q core models ui tests
.\scripts\check_plan1_coverage.ps1
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
