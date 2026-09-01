# Task 7 report — phase documentation and executable audit

## Changed files

- `README.md` — added the user-facing official calculation formula, nine-subcategory completeness rule, provenance/checksum limitations, offline behavior, automatic watcher, manual fallback, and retry behavior.
- `RELEASE_NOTES.md` — added the benchmark-accuracy, import, offline, checksum, and daily-lag release notes.
- `docs/benchmark-data-provenance.md` — added the detailed definition metadata, calculation rules, import lifecycle, failure/retry semantics, offline boundary, and known daily Voltaic lag.

No production code, tests, or benchmark data were changed.

## Verification evidence

Working directory: `D:\DEV\aim training\.worktrees\coaching-core-redesign`

Command:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q
```

Exact output:

```text
........................................................................ [ 44%]
......................................... [ 69%]
.................................................                        [100%]
162 passed, 31 subtests passed in 11.89s
```

Command:

```powershell
python -m compileall -q core models ui tests
```

Exact result: exit code `0`; no output.

Command:

```powershell
git diff --check
```

Exact result: exit code `0`; no whitespace errors. Git emitted these existing
working-copy conversion warnings:

```text
warning: in the working copy of 'README.md', LF will be replaced by CRLF the next time Git touches it
warning: in the working copy of 'RELEASE_NOTES.md', LF will be replaced by CRLF the next time Git touches it
```

## Self-review

- Confirmed the implementation uses active version `kovaaks_s5`, retrieval time `2026-08-30T00:00:00+02:00`, nine required subcategories, and local checksum `072a6178ec71340be7bb26b1bbdf77952ef23c3f537e2ec4e1dc64e72e109b0b`.
- Confirmed `BenchmarkCalculator` selects the best eligible score per benchmark, the maximum scenario energy per subcategory, and the nine-value harmonic mean; incomplete coverage returns no overall energy/tier.
- Confirmed the main rank display builds from the Best score mode. Documentation labels latest/recent/average views as alternate local score-input views and explicitly rejects arithmetic averages as official Voltaic overall energy.
- Confirmed the 750 ms `ScoreDirectoryWatcher`, background `ScoreSyncWorker`, manual `ScoreImporter` routes, deterministic path ordering, duplicate handling, persisted import failures, retry behavior, and successful-failure clearing are described without adding behavior claims.
- Confirmed the checksum language is limited to local bundled-payload integrity and does not claim remote authenticity, freshness, or a currently shipped remote sync adapter.
- Searched the changed documentation for stale arithmetic-mean and unsupported authenticity/sync claims; none were found. The arithmetic wording present is an explicit warning that such averages are not official.

## Concerns and boundaries

- The bundled definition is a last-known-good offline snapshot retrieved on
  2026-08-30. Public Voltaic benchmark/profile data can follow a daily update
  cycle, and the shipped code does not currently refresh or validate a remote
  profile. The documentation calls out that freshness boundary.
- `git diff --check` is clean; only the two LF-to-CRLF conversion warnings were
  emitted by Git.

## Fix Round 1 review evidence

Review fixes applied:

- Corrected startup wording to “immediately schedules a 750-ms-debounced
  recovery scan,” which distinguishes scheduling from execution after the
  debounce interval.
- Clarified that the header tier/energy and Skill Matrix use the Best-score
  official rank, while Dashboard and status text may reflect the selected
  score-input view. This matches `MainWindow._update_tier_label()` and
  `_rebuild_profile()`.

Documentation claim search:

```powershell
rg -n -i "immediate|immediately|recovery scan|750.?ms|Best score|header|Skill Matrix|Dashboard|status bar|arithmetic|authenticat|remote.*sync|sync.*remote|freshness|daily" README.md RELEASE_NOTES.md docs/benchmark-data-provenance.md task-7-report.md
```

The search found the corrected `immediately schedules a` / `750-ms-debounced
recovery scan` wording, the explicit Best/header/Skill Matrix versus
Dashboard/status distinction, and only warning language for arithmetic
averages, remote authenticity/freshness, and the known daily lag.

Focused implementation tests:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_score_watcher.py tests/test_score_importer.py tests/test_analyzer_official_profile.py -q
```

Exact output:

```text
....................                                                     [100%]
20 passed in 6.66s
```

Full suite:

```powershell
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q
```

Exact output:

```text
........................................................................ [ 44%]
......................................... [ 69%]
.................................................                        [100%]
162 passed, 31 subtests passed in 11.66s
```

Whitespace check:

```powershell
git diff --check
```

Exact result: exit code `0`; no whitespace errors. Git emitted only its
LF-to-CRLF conversion warnings for `README.md` and
`docs/benchmark-data-provenance.md`.

Fix Round 1 concerns: none. The fix remains documentation-only.
