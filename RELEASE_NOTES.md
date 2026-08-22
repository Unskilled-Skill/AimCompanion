# Aim Companion 1.0.1

Aim Companion now starts with zero mandatory setup.

## What changed

- Removed the blocking first-launch setup dialog.
- Automatically reads Steam's configured library folders.
- Automatically detects Kovaak's, its stats folder, and playlists across drives.
- Automatically imports scores and starts with safe general-training defaults.
- Settings remain available for optional overrides.
- Score syncing now consistently respects an overridden Kovaak's folder.

The adaptive nine-skill training engine, verified automatic updater, and all
version 1.0 features remain included.

## Installation

Download `AimCompanion-Setup.exe` and run it. Existing scores, settings, and
training history in `%LOCALAPPDATA%\AimCompanion` are preserved.

This build is not Authenticode-signed, so Windows SmartScreen may show an Unknown
Publisher warning. The matching `.sha256` file verifies installer integrity.
