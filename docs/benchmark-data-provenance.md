# Benchmark data and import provenance

This note describes what Aim Companion calculates locally, where the bundled
benchmark definitions came from, and how Kovaak's result files reach the local
database. It deliberately distinguishes local integrity checks from the
authority and freshness of the public Voltaic source.

## Public source and bundled definition

The authoritative public benchmark source is
<https://app.voltaic.gg/benchmarks>. The active bundled definition identifies
that source with these values:

| Field | Value |
| --- | --- |
| Version | `kovaaks_s5` |
| Retrieved at | `2026-08-30T00:00:00+02:00` |
| Bundled file | `data/benchmark_definitions/voltaic-kovaaks-s5.json` |
| Definitions | 54 benchmark definitions |
| Required subcategories | 9 |
| SHA-256 | `072a6178ec71340be7bb26b1bbdf77952ef23c3f537e2ec4e1dc64e72e109b0b` |

The repository canonicalizes the JSON `definitions` array (sorted keys and
compact JSON encoding) and compares its SHA-256 digest with the stored value
before loading the definition set. This detects accidental or incomplete local
edits. A matching local digest does **not** authenticate the remote Voltaic
publication, prove that the snapshot is the newest publication, or replace
remote validation.

The snapshot is a bundled last-known-good copy. Benchmark calculation and local
score importing therefore continue without network access. The shipped phase
does not yet include an official remote definition/profile synchronization
adapter; the source URL and retrieval time are provenance metadata, not a claim
that the app currently refreshes that URL.

## Official energy calculation

For a selected difficulty, the calculator resolves benchmark names and aliases,
keeps the highest imported score for each matching benchmark, and converts that
score through the definition's piecewise-linear target curve. The first pass
applies each definition's energy cap. A subcategory is measured when it has at
least one eligible positive-energy scenario, and its energy is the highest
eligible scenario energy in that subcategory:

```text
subcategory energy = max(eligible scenario energies in that subcategory)
```

The official overall value is calculated only from all nine required
subcategories, using the harmonic mean:

```text
overall energy = 9 / sum(1 / subcategory energy for all nine subcategories)
```

If any required subcategory has no valid score, overall official energy and rank
are unavailable (`Unranked`). The calculator does not average scenarios or
subcategories for the official overall result. If the capped overall energy
reaches the definition's configured uncap threshold, it recalculates from raw
scenario energies; otherwise the cap remains in force.

The main rank display is built from the Best score view. Latest, recent, and
average selections are alternate local views over different score inputs; an
arithmetic average of attempts is not an official Voltaic overall energy.

## Automatic and manual importing

Once the main window has finished its initial setup, a `ScoreDirectoryWatcher`
observes the configured Kovaak's stats directory. It schedules an immediate
recovery scan and debounces bursts of directory events for 750 ms. Each batch
runs in a `QThread`, leaving the Qt UI responsive; a second worker is not
started while one is already running. A completion rebuilds the profile once.

Manual fallback is always available from the Import scores view:

- Drag and drop CSV files.
- Choose CSV files with the file picker.
- Click **Import from Kovaak's** to scan the configured stats folder.

All three routes call the same UI-free `ScoreImporter` used by the watcher.
Paths are normalized and ordered deterministically. Existing imported paths are
skipped, and a score with the same scenario, timestamp, and score is counted as
a duplicate rather than inserted as another history row. Database reads return
score history in timestamp order.

## Failure, retry, and offline behavior

Each file is parsed independently. A malformed, unsupported, or unreadable CSV
increments the batch failure count and persists its path, error text, first and
last failure times, and retry count in the local `import_failures` table. Other
valid files in that batch still commit when the database write succeeds. A
database write failure rolls back the valid part of that transaction. Failed
paths are not marked as imported, so a later watcher scan or manual import
retries them. A successful retry clears the stored failure; it does not discard
the local score history.

The importer, definition repository, calculator, and database operate on local
files. A missing stats directory is surfaced as a watcher failure, while the
bundled definition snapshot still permits offline calculation. Existing local
Kovaak's CSV files remain the authority for detailed score history.

## Known daily Voltaic lag

Voltaic's public benchmark/profile information can follow a daily update cycle.
As a result, a local result or a public Voltaic observation may temporarily be
newer than the other. The app reports its local definition retrieval time and
uses the bundled snapshot; it does not currently fetch or validate a remote
profile in the background. Compare the local calculation timestamp with the
external Voltaic observation time rather than treating a temporary difference
as a local checksum failure.
