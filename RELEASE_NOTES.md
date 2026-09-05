# Aim Companion 2.0.2

This update makes guided sessions easier to read and control without removing
any routine or coaching detail.

## Session workspace refresh

- Reorganized the active session into a prominent routine summary, complete
  current-scenario guide, full routine queue, and clearly grouped controls.
- Kept every source-backed purpose, setup step, instruction, success criterion,
  adjustment, progress value, routine item, source link, and session action.
- Added a polished empty state with direct Warm-up, Step-by-Step, and Full
  Routine starts.
- Made the routine queue read-only, added status-specific visual states, and
  kept all controls visible at narrow and high-scale window sizes.
- Fixed sidebar navigation so the top heading always matches the selected area.

# Aim Companion 2.0.1

This update gives Home a cleaner, user-first coaching dashboard.

## Home dashboard refresh

- Reorganized the recommendation into a prominent Today's Coaching Focus card.
- Added plain-language guidance for Warm-up, Step-by-Step Training, and Full
  Routine so the right session is easier to choose before starting.
- Grouped current rank, priority weakness, confidence, recent coverage, and
  benchmark readiness into compact, scannable cards.
- Improved spacing, typography, contrast, hover states, and keyboard-accessible
  training actions while preserving all existing behavior and user data.
- Restricted the installer upgrade smoke test to disposable CI runners so it
  cannot alter a developer's installed application registration.

# Aim Companion 2.0.0

This release rebuilds Aim Companion around guided, resumable coaching while
preserving existing scores, settings, and training history.

## Coaching-first interface

- Replaced the crowded Today workflow with five destinations: Home, Session,
  Progress, Library, and Tools.
- Selecting a full routine now opens a guided Session view with the complete
  routine and the detailed hnA source instructions for the current scenario.
- Added an opt-in always-on-top compact training panel sharing the same durable
  progress state as the main Session screen.
- Consolidated official rank conclusions, skills, benchmarks, and history into
  one Progress area; moved routines, warm-ups, and deathmatch guidance into the
  reference Library.

## Guided coaching and durable sessions

- Added explicit Warm-up, Step-by-Step Training, and Full Routine session
  models with save-after-run persistence and crash recovery.
- Full Routine keeps exact authored order and prescribed runs. An interrupted
  routine resumes with unfinished material, completes one circular pass, and
  then resets to the official start.
- Step-by-Step recommendations prioritize due benchmark checks, then use a
  deterministic 50/30/20 weakness rotation with visible evidence and confidence.
- Benchmark freshness is tracked per subcategory and becomes due after 12
  relevant completed non-warm-up blocks.
- The last warm-up context is remembered; warm-ups never advance Full Routine
  progress or freshness counters.
- Automatic and manual run confirmations use the same durable transition.
  Fatigue coaching remains disabled until explicitly enabled, and historical
  game observations no longer influence active recommendations.

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
