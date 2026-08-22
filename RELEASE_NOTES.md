# Aim Companion 1.0.6

This release fixes online warm-up scenarios getting stuck on "Waiting for download."

## What changed

- Online scenarios now open immediately through Kovaak's official Steam deep link.
- Removed the incorrect requirement for an online scenario to create a local `.sce` file.
- Kovaak's can now download and load MicroshotSpeed, 1wall5targets_pasu, TileFrenzyMini, and other online scenarios directly.
- Local scenario files are still used when available to read exact time limits.
- Automatic run tracking remains active for online scenarios through Kovaak's result files.
- Updated the Today status text to explain whether timing is local or the scenario will be loaded online.

Existing scores, settings, routines, and training history are preserved during installation.
This build is not Authenticode-signed; use the matching `.sha256` asset to verify
installer integrity.
