"""Regression coverage for the app reliability review."""

import sqlite3
from contextlib import closing
from datetime import datetime

import pytest

from core.score_importer import ScoreImporter
from models.database import Database
from tests.test_score_importer import write_score


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_score_does_not_block_valid_import(tmp_path, value):
    bad = write_score(tmp_path / "bad.csv", datetime(2026, 1, 1), score=value)
    good = write_score(tmp_path / "good.csv", datetime(2026, 1, 2), score=123)
    database = Database(":memory:")
    try:
        result = ScoreImporter(database).import_paths([bad, good])
        assert result.imported == 1
        assert result.failed == 1
        assert [score.score for score in database.get_all_scores()] == [123]
        assert database.get_import_failure(str(bad.resolve())) is not None
    finally:
        database.close()


@pytest.mark.parametrize("current_schema", [False, True])
def test_invalid_restore_preserves_current_history(tmp_path, current_schema):
    backup = tmp_path / "invalid.sqlite3"
    if current_schema:
        source = Database(str(backup))
        source.conn.execute("DROP TABLE scores")
        source.conn.execute("CREATE TABLE scores (wrong TEXT)")
        source.conn.commit()
        source.close()
    else:
        with closing(sqlite3.connect(backup)) as source:
            source.execute("CREATE TABLE scores (wrong TEXT)")
            source.execute("CREATE TABLE settings (key TEXT, value TEXT)")
    database = Database(":memory:")
    try:
        database.log_session("Keep this training", 12)
        database.set_settings_value("review_marker", "keep")
        with pytest.raises((ValueError, sqlite3.Error)):
            database.restore_from(str(backup))
        assert database.get_sessions()[0]["focus"] == "Keep this training"
        assert database.get_settings_value("review_marker") == "keep"
        database.log_session("Still usable", 3)
        assert len(database.get_sessions()) == 2
    finally:
        database.close()


def test_valid_restore_replaces_history_and_keeps_connection(tmp_path):
    backup = tmp_path / "backup.sqlite3"
    source = Database(str(backup))
    source.log_session("Restored", 8)
    source.close()
    database = Database(":memory:")
    connection = database.conn
    try:
        database.log_session("Original", 12)
        database.restore_from(str(backup))
        assert [row["focus"] for row in database.get_sessions()] == ["Restored"]
        assert database.conn is connection
        database.log_session("After restore", 5)
        assert len(database.get_sessions()) == 2
    finally:
        database.close()


def test_saving_settings_refreshes_current_views(qtbot, monkeypatch, tmp_path):
    from tests.test_main_session_integration import _window
    from ui import main_window

    window = _window(qtbot, monkeypatch, tmp_path)
    monkeypatch.setattr(main_window.SetupDialog, "exec", lambda self: 1)
    try:
        window._open_settings()
        assert window.statusBar().currentMessage() == "Settings saved"
    finally:
        window.close()


def test_manual_import_uses_configured_score_directory(qtbot, monkeypatch, tmp_path):
    from models import config
    from ui.import_widget import DragDropImport

    stats = tmp_path / "custom-stats"
    stats.mkdir()
    write_score(stats / "score.csv", datetime(2026, 1, 1), score=456)
    monkeypatch.setattr(config.TrainingConfig, "get_stats_dir", lambda self: str(stats))
    # Ensure the test never scans the user's real installation.
    monkeypatch.setattr("core.parser._detect_kovaaks_stats", lambda: str(tmp_path / "other"))
    database = Database(":memory:")
    widget = DragDropImport(database)
    qtbot.addWidget(widget)
    try:
        widget._auto_import()
        assert [score.score for score in database.get_all_scores()] == [456]
    finally:
        database.close()


@pytest.mark.parametrize("paused", [False, True])
def test_settings_switches_live_tracking_without_losing_progress(
    qtbot, monkeypatch, tmp_path, paused,
):
    from tests.test_main_session_integration import _window
    from tests.test_session_coordinator import _plan
    from ui import main_window

    window = _window(qtbot, monkeypatch, tmp_path)
    new_stats = tmp_path / "new-stats"
    new_stats.mkdir()
    monkeypatch.setattr(main_window.SetupDialog, "exec", lambda self: 1)
    try:
        coordinator = window.session_coordinator
        coordinator.start(_plan(runs=3))
        coordinator.confirm_manual_run()
        if paused:
            coordinator.pause()
        monkeypatch.setattr(
            main_window.TrainingConfig, "get_stats_dir", lambda self: str(new_stats),
        )
        window._open_settings()
        assert coordinator.state.confirmed_runs == 1
        assert coordinator.tracker.active is not paused
        if paused:
            coordinator.resume()
        write_score(
            new_stats / "score.csv", datetime(2026, 1, 1),
            scenario="Static A", score=321,
        )
        window._poll_session_runs()
        assert coordinator.state.confirmed_runs == 2
        with qtbot.waitSignal(window.score_watcher.batch_completed, timeout=4000):
            window.score_watcher.notify_directory_changed()
        assert [score.score for score in window.db.get_all_scores()] == [321]
    finally:
        window.close()


def test_changing_score_folder_waits_for_active_import(qtbot, monkeypatch, tmp_path):
    from core.score_watcher import ScoreDirectoryWatcher
    from tests.test_score_watcher import _DelayedWorker

    old = tmp_path / "old"
    new = tmp_path / "new"
    old.mkdir()
    new.mkdir()
    _DelayedWorker.reset()
    monkeypatch.setattr(_DelayedWorker, "delay_ms", 1200)
    monkeypatch.setattr("core.score_watcher.ScoreSyncWorker", _DelayedWorker)
    watcher = ScoreDirectoryWatcher(str(tmp_path / "scores.sqlite3"), str(old))
    try:
        watcher.start()
        watcher._timer.stop()
        watcher._scan()
        qtbot.waitUntil(lambda: _DelayedWorker.starts == 1)
        watcher.set_stats_dir(str(new))
        qtbot.waitUntil(lambda: _DelayedWorker.starts == 2, timeout=4000)
        assert _DelayedWorker.maximum_active == 1
        assert str(new) in watcher._file_watcher.directories()
        assert str(old) not in watcher._file_watcher.directories()
    finally:
        watcher.stop()


def test_future_backup_is_rejected_without_replacing_history(tmp_path):
    backup = tmp_path / "future.sqlite3"
    source = Database(str(backup))
    source.conn.execute(
        "INSERT INTO schema_migrations (version, name, applied_at) VALUES (999, 'future', '')"
    )
    source.conn.commit()
    source.close()
    database = Database(":memory:")
    try:
        database.log_session("Keep", 12)
        with pytest.raises(ValueError, match="newer version"):
            database.restore_from(str(backup))
        assert database.get_sessions()[0]["focus"] == "Keep"
    finally:
        database.close()
