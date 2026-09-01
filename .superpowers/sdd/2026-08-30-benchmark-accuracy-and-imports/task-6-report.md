# Task 6 report: background score watcher and UI integration

## Result

Added `ScoreDirectoryWatcher`, which watches the configured Kovaak's score
directory with a 750 ms single-shot debounce and imports batches on a
background `ScoreSyncWorker`. `MainWindow` owns the watcher for its lifecycle.
Manual and automatic imports now use `ScoreImporter.import_paths()` and pass
the resulting `ImportBatchResult` to the same refresh callback used by watcher
batches.

## Lifecycle design

- `start()` is idempotent, watches the configured directory plus its parent,
  and schedules a non-blocking recovery scan. Watching the parent lets the
  watcher re-add the configured path after a delete/recreate cycle.
- A burst restarts one 750 ms single-shot timer. When a timer expires during an
  active worker, the watcher retains one pending-rescan flag; its finished
  handler schedules exactly one follow-up scan. No second worker can be
  created while the active worker exists.
- `stop()` is idempotent, stops the timer, removes watcher paths, prevents any
  follow-up work, and waits for only the current worker (with a 3-second
  shutdown bound). `MainWindow.closeEvent()` calls it before closing the DB.
- A missing configured directory emits the existing failure/status route. If
  it is recreated, the parent watch re-registers it safely.
- `ScoreSyncWorker.completed` now carries the complete `ImportBatchResult`, so
  MainWindow rebuilds its profile once for every successful batch, including a
  zero-import recovery batch where the existing refresh behaviour calls for it.

## TDD evidence

### RED

Command:

```text
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_score_watcher.py tests/test_aim_hub.py -v
```

Observed output before the watcher production module existed:

```text
collecting ... collected 5 items / 1 error

ImportError while importing test module '...\\tests\\test_score_watcher.py'.
tests\\test_score_watcher.py:10: in <module>
    from core.score_watcher import ScoreDirectoryWatcher
E   ModuleNotFoundError: No module named 'core.score_watcher'
============================== 1 error in 0.62s ==============================
```

### GREEN

Focused Qt range:

```text
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_score_watcher.py tests/test_aim_hub.py -v
============================= 10 passed in 7.75s =============================
```

Full suite:

```text
$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q
159 passed, 31 subtests passed in 11.25s
```

Additional verification:

```text
git diff --check
exit 0

python -m compileall -q core ui
compile_exit=0
```

## Files changed

- `core/score_watcher.py` (new watcher and lifecycle state machine)
- `core/sync_worker.py` (emit `ImportBatchResult`)
- `ui/main_window.py` (watcher ownership, refresh callback, shutdown)
- `ui/import_widget.py` (manual/automatic coordinator path)
- `requirements-dev.txt` (pytest-qt range)
- `tests/test_score_watcher.py` (real temporary DB/directory and Qt signal
  coverage)
- `tests/test_aim_hub.py` (manual coordinator regression and MainWindow smoke)

## Self-review

Reviewed worker ownership and queued Qt signals: the watcher retains the
worker until `finished`, avoiding deletion while its thread is still running.
It only clears and schedules a pending scan from that completion point.
Parent-directory events that do not affect the score-directory watch are
ignored, preventing application-DB writes from producing redundant batches.
The manual import regression asserts both durable malformed-file bookkeeping
and precisely one profile-refresh callback, which the earlier hand-written UI
loop could not provide.

## Concerns

None. `QFileSystemWatcher` platform notifications remain inherently
best-effort; the startup recovery scan and explicit Sync scores action provide
the intended recovery path if an operating-system event is missed.
