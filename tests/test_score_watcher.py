from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PyQt6.QtCore import QThread, pyqtSignal

from core.score_importer import ImportBatchResult
from core.score_watcher import ScoreDirectoryWatcher


def write_score(directory: Path, name: str, *, score: float = 123.0) -> Path:
    path = directory / (
        f"{name} - Challenge - 2026.01.01-12.00.00 Stats.csv"
    )
    path.write_text(
        f"Scenario:,{name}\nScore:,{score}\n", encoding="utf-8",
    )
    return path


@pytest.fixture
def score_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "stats"
    directory.mkdir()
    return directory


@pytest.fixture
def watcher(tmp_path: Path, score_dir: Path):
    instance = ScoreDirectoryWatcher(
        str(tmp_path / "scores.sqlite3"), str(score_dir),
    )
    try:
        yield instance
    finally:
        instance.stop()


def test_burst_of_changes_emits_one_debounced_batch(qtbot, watcher, score_dir):
    write_score(score_dir, "First")
    write_score(score_dir, "Second", score=456.0)
    completed = []
    watcher.batch_completed.connect(completed.append)
    watcher.start()

    with qtbot.waitSignal(watcher.batch_completed, timeout=2500) as signal:
        watcher.notify_directory_changed()
        watcher.notify_directory_changed()

    assert signal.args[0].imported == 2
    qtbot.wait(900)
    assert len(completed) == 1


def test_start_performs_recovery_scan(qtbot, tmp_path: Path, score_dir: Path):
    write_score(score_dir, "Existing")
    watcher = ScoreDirectoryWatcher(str(tmp_path / "scores.sqlite3"), str(score_dir))
    try:
        with qtbot.waitSignal(watcher.batch_completed, timeout=2500) as signal:
            watcher.start()
        assert signal.args[0].imported == 1
    finally:
        watcher.stop()


def test_missing_configured_directory_surfaces_failure(qtbot, tmp_path: Path):
    watcher = ScoreDirectoryWatcher(
        str(tmp_path / "scores.sqlite3"), str(tmp_path / "missing-stats"),
    )
    try:
        with qtbot.waitSignal(watcher.batch_failed, timeout=1000) as signal:
            watcher.start()
        assert "not available" in signal.args[0].lower()
    finally:
        watcher.stop()


class _DelayedWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    starts = 0
    active = 0
    maximum_active = 0
    delay_ms = 900

    def __init__(self, db_path: str, stats_dir: str, parent=None):
        super().__init__(parent)

    @classmethod
    def reset(cls):
        cls.starts = 0
        cls.active = 0
        cls.maximum_active = 0

    def run(self):
        type(self).starts += 1
        type(self).active += 1
        type(self).maximum_active = max(type(self).maximum_active, type(self).active)
        self.msleep(type(self).delay_ms)
        type(self).active -= 1
        self.completed.emit(ImportBatchResult(0, 0, 0, ()))


def test_changes_during_a_worker_schedule_one_non_overlapping_follow_up(
    qtbot, watcher, monkeypatch,
):
    _DelayedWorker.reset()
    monkeypatch.setattr("core.score_watcher.ScoreSyncWorker", _DelayedWorker)

    watcher.start()
    watcher._timer.stop()
    watcher._scan()
    qtbot.waitUntil(lambda: _DelayedWorker.starts == 1, timeout=1000)
    watcher.notify_directory_changed()
    watcher.notify_directory_changed()
    watcher.notify_directory_changed()

    qtbot.waitUntil(lambda: _DelayedWorker.starts == 2, timeout=3500)
    qtbot.waitUntil(lambda: _DelayedWorker.active == 0, timeout=2000)

    assert _DelayedWorker.maximum_active == 1
    assert _DelayedWorker.starts == 2


def test_stop_prevents_pending_and_follow_up_workers(qtbot, watcher, monkeypatch):
    _DelayedWorker.reset()
    _DelayedWorker.delay_ms = 150
    monkeypatch.setattr("core.score_watcher.ScoreSyncWorker", _DelayedWorker)

    watcher.start()
    watcher._timer.stop()
    watcher._scan()
    qtbot.waitUntil(lambda: _DelayedWorker.starts == 1, timeout=1000)
    watcher.notify_directory_changed()
    watcher.stop()
    qtbot.wait(1000)

    assert _DelayedWorker.starts == 1


def test_stop_defers_shutdown_until_a_worker_exceeds_the_bounded_wait(
    qtbot, watcher, monkeypatch,
):
    _DelayedWorker.reset()
    _DelayedWorker.delay_ms = 150
    monkeypatch.setattr("core.score_watcher.ScoreSyncWorker", _DelayedWorker)
    watcher._shutdown_wait_ms = 10
    watcher.start()
    watcher._timer.stop()
    watcher._scan()
    qtbot.waitUntil(lambda: _DelayedWorker.starts == 1, timeout=1000)

    with qtbot.waitSignal(watcher.shutdown_finished, timeout=1000):
        assert watcher.stop() is False
        assert watcher._worker is not None
        assert watcher._worker.isRunning()

    assert watcher._worker is None


def test_repeated_start_and_stop_are_idempotent(qtbot, watcher):
    watcher.start()
    watcher.start()
    watcher._timer.stop()

    assert watcher.stop() is True
    assert watcher.stop() is True

    watcher.start()
    watcher._timer.stop()
    assert watcher.is_started
    assert watcher.stop() is True
