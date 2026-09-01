# Task 5 report: deterministic import batches

## Result

Implemented a UI-free `ScoreImporter` with deterministic path handling and an
`ImportBatchResult`. `core.parser.import_all_scores()` remains a compatibility
wrapper, while `ScoreSyncWorker` invokes the same coordinator directly.

## TDD evidence

### RED

Command:

```text
python -m pytest tests/test_score_importer.py -v
```

Observed result before production code: collection failed with
`ModuleNotFoundError: No module named 'core.score_importer'`.

### GREEN

Commands and observed results:

```text
python -m pytest tests/test_score_importer.py -v
7 passed in 0.18s

python -m pytest tests/test_score_importer.py tests/test_parser.py tests/test_database.py -v
20 passed in 0.38s

python -m pytest -v
152 passed, 31 subtests passed in 3.94s

python -m compileall -q core models
exit 0

git diff --check
exit 0
```

## Behaviour covered

- Imports retain timestamp-ascending history regardless of supplied/discovery order.
- Same logical score at two distinct paths inserts one score and marks both paths.
- `None` parser results and parser exceptions are isolated and retain a useful retryable error.
- A successful retry clears the prior failure record.
- Returned paths are de-duplicated and sorted deterministically.
- A trigger-induced later insert failure rolls back every valid score insert and path mark in the batch.

## Transaction decisions

- Each parse failure is persisted independently after parsing, so a bad file never prevents valid files from being imported.
- All valid score inserts, duplicate path marks, and error clears share one `with db.conn` transaction. Any database error rolls back the full valid portion of the batch.
- Database mutators accept an internal `commit=False` mode only for that transaction; their existing default behaviour still commits for existing callers.
- Stored import keys use `abspath + normpath + normcase` for Windows-safe comparison. The non-case-folded normalized path is retained until parsing, so the file can be opened reliably.

## Files changed

- `core/score_importer.py` (new)
- `core/parser.py`
- `core/sync_worker.py`
- `models/database.py`
- `tests/test_score_importer.py` (new)
- `tests/test_parser.py`
- `tests/test_database.py`

## Self-review

Reviewed the coordinator for circular imports, PyQt imports, path key consistency,
duplicate handling, error-clearing placement, and transaction boundaries. The
coordinator imports only parser/database/model code and has no PyQt dependency.

## Concerns

None. A database-level write failure is intentionally propagated after rolling
back the valid batch so the caller can surface an operational failure; malformed
files remain isolated and retryable.
