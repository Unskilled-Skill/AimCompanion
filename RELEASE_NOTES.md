# Aim Companion 1.8.3

This hotfix restores application startup after the Training Methods redesign.

## What changed

- Fixed a fatal callback error triggered when automatic score synchronization
  refreshed the Training Methods view during startup.
- Restored the shared profile-refresh contract on the redesigned view.
- Added regression coverage and a timed startup smoke test.

Existing scores, settings, training history, routines, and automatic update
preferences are preserved during installation.
