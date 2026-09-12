# App review — September 11, 2026

This pass reviewed settings, score importing, backup validation, background
watching, and the existing application tests. Existing session changes in the
working directory were retained.

## Fixed

- **Invalid backup could erase current history.** Restore previously copied the
  backup over the open database before migration could reject it. Restore now
  migrates a temporary copy, checks required columns, schema compatibility,
  database integrity and foreign keys, and retains a rollback snapshot during
  replacement. The existing database connection stays open for its consumers.
- **Malformed numeric score could block a whole import batch.** NaN triggered a
  database constraint failure; infinity could enter score history. The parser
  rejects nonfinite scores so the importer can record the failed file while
  retaining valid results from the batch.
- **Saving Settings raised an AttributeError.** The save handler referenced a
  removed routine view. It now refreshes the current views and updates score
  watching and active-session tracking when the configured folder changes.
  Running-session progress is retained; paused sessions stay paused.
- **Manual import ignored the configured installation.** “Import from Kovaak's”
  now uses the same saved folder configuration as background importing.
- SQLite restore errors now appear in the restore failure dialog.

## Verification

Regression tests in `tests/test_review_regressions.py` cover invalid and valid
restores, future schema rejection, nonfinite scores, settings, manual imports,
running/paused tracking, and directory changes during a background worker.
The initial seven failing cases reproduced the reported defects before fixes.
An independent review also exercised both existing legacy backup fixtures.

Validation uses the full pytest suite with coverage, the CI lint scope plus all
modified production modules, bytecode compilation, and the offscreen UI smoke
script. The full suite passed 341 tests and 31 subtests, with 91.27% coverage
of the configured benchmark, coaching, and session modules. Tests use isolated
databases and score folders, not personal history.
On this machine pytest's default temporary directory is inaccessible; a unique
directory under ignored `artifacts/` works.

## Remaining review finding

The **full ZIP restore workflow** still restores the database and config file as
separate operations. A config-copy failure after a successful database restore
can leave mixed state, and restored folder settings are not reapplied to running
services until restart. The database validation fix above addresses invalid
database replacement; it does not make the whole ZIP operation transactional.
A follow-up should stage both files and coordinate the watcher and session
state before applying the restore.

Live interaction with Kovaak's and the packaged Windows installer were not
tested in this pass.

## September 12: algorithms and session UI

- Due checks now select official benchmarks at the chosen difficulty, including
  Linear and Stability, which have no generic training candidates. Continuing
  a session uses the same official check path. Ordinary recommendations filter
  known difficulty levels and use official scenarios for uncovered skills.
- Recommendation selection permits an unavoidable skill repeat after exhausting
  alternatives, while still preferring another scenario within that skill.
- Latest and Average combined score totals now use the selected scores, matching
  their energy calculations. Historical best and latest fields remain available.
- Completing a non-warm-up block updates benchmark freshness in the same
  transaction as saved session progress. Re-saving state does not increment it
  again; skipped and partially completed blocks do not age benchmarks.
- Skip omits a scenario and durably records its actual run count. Queue labels
  distinguish skipped from completed steps, and the last scenario is skippable.
  Schema migration 9 adds skip metadata and backs up existing databases before
  upgrading; recovery preserves existing session progress.
- Manual only disables automatic counting. Tracking follows scenario transitions,
  and paused sessions disable confirmation and offer a clear Resume action.
- Completed full routines offer a working Start training action. Session controls
  remain fixed while the guide and queue scroll, including at compact widths.

The regression cases live in `tests/test_algorithm_ui_regressions.py`. The
updated session layout was also rendered at 1000 × 720 with Windows fonts for
visual inspection. No installer build or live Kovaak's run was performed.

Final verification: **357 tests and 31 subtests passed**, with **91.65% coverage**
of the configured benchmark, coaching, and session modules. Lint, compilation,
and the UI smoke check passed. Independent review found no blockers in skip
persistence, freshness accounting, or migration behavior.
