# Aim Companion 1.1.1

This maintenance release improves data safety, background score syncing, and
exports.

## What changed

- Configuration saves are now atomic, preventing an interrupted write from
  leaving the app unable to start.
- Invalid or truncated configuration files now fall back to safe defaults.
- Enabled SQLite write-ahead logging and a longer busy timeout to reduce
  conflicts between background score sync and UI activity.
- Duplicate copies of an already-imported score are remembered instead of
  being parsed again during every sync.
- Score export now includes every attempt rather than only personal bests.
- Session export now includes the full history rather than the latest 1,000.
- Future-dated activity no longer creates an incorrect training streak.

Existing scores, settings, routines, training history, and update preferences
are preserved during installation. This build is not Authenticode-signed; use
the matching `.sha256` asset to verify installer integrity.
