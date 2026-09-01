# Aim Companion 1.9.5

This release fixes automatic installation of downloaded updates.

## What changed

- Official Voltaic S5 energy now selects the maximum eligible scenario energy
  per subcategory and combines all nine required subcategories with the
  harmonic-mean formula documented in the [benchmark provenance note](docs/benchmark-data-provenance.md).
- Overall official energy and rank remain unavailable until all nine required
  subcategories have valid scores. The active `kovaaks_s5` definition snapshot
  includes a verifiable local checksum and works offline.
- Kovaak's CSV changes are imported by a debounced background watcher. Manual
  file selection and folder import remain available; malformed or unreadable
  files are persisted for retry and successful retries clear their failure.
- Public Voltaic data can lag its daily update cycle. The bundled snapshot's
  checksum protects local integrity but does not authenticate or establish
  freshness of the remote publication.
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
