# Aim Companion 1.9.5

This release fixes automatic installation of downloaded updates.

## What changed

- The updater now waits for both processes created by the packaged app to exit
  before replacing the executable, preventing a file-lock race.
- After a verified update installs successfully, Aim Companion restarts
  automatically.
- Automatic update-check failures are shown in the status bar instead of being
  silently ignored.
- Includes the v1.9.4 routine-selection improvements: complete routines and hnA
  scenario instructions appear immediately when selected.

Existing scores, settings, training history, routines, and automatic update
preferences are preserved during installation.
