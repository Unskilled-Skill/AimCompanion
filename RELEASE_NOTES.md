# Unreleased

## Benchmark accuracy and score imports

- Official Voltaic S5 energy now selects the maximum eligible scenario energy
  per subcategory and combines all nine required subcategories with the
  harmonic-mean formula documented in the [benchmark provenance note](docs/benchmark-data-provenance.md).
- Overall official energy and rank remain unavailable until all nine required
  subcategories have valid scores. Novice and Intermediate energy are uncapped;
  Advanced scenarios use Voltaic's documented conditional cap.
- Kovaak's CSV changes are imported by a debounced background watcher. A changed
  path is re-imported by content identity, while malformed or unreadable files
  remain visible and retryable without blocking valid files in the same batch.
- Lifetime Best is the official rank input. Latest, 7-day, 30-day, and recent
  average views are labeled as local current-form analytics.
- Public Voltaic data can lag its daily update cycle. The bundled snapshot's
  checksum protects local integrity but does not authenticate or establish
  freshness of the remote publication.

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
