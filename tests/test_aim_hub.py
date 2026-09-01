import os
import unittest
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core.training_methods import TRAINING_METHODS
from models.database import Database
from ui.aim_hub import AimHubWidget
from ui.import_widget import DragDropImport


def _write_score(path: Path, scenario: str, score: float = 123.0) -> Path:
    result = path / (
        f"{scenario} - Challenge - {datetime(2026, 1, 1, 12, 0, 0):%Y.%m.%d-%H.%M.%S} "
        "Stats.csv"
    )
    result.write_text(
        f"Scenario:,{scenario}\nScore:,{score}\n", encoding="utf-8",
    )
    return result


def test_manual_import_uses_batch_coordinator_and_refreshes_once(qtbot, tmp_path):
    database = Database(str(tmp_path / "scores.sqlite3"))
    refreshed = []
    widget = DragDropImport(database, on_import_complete=refreshed.append)
    qtbot.addWidget(widget)
    valid = _write_score(tmp_path, "Manual import")
    malformed = tmp_path / "Broken - Challenge - 2026.01.01-12.00.00 Stats.csv"
    malformed.write_text("Scenario:,Broken\n", encoding="utf-8")

    try:
        widget._import_files([str(malformed), str(valid)])

        assert len(database.get_all_scores()) == 1
        assert database.get_import_failure(str(malformed.resolve())) is not None
        assert len(refreshed) == 1
        assert refreshed[0].imported == 1
    finally:
        database.close()


def test_main_window_starts_and_stops_score_watcher(qtbot, monkeypatch, tmp_path):
    from models import config
    from ui import main_window

    stats_dir = tmp_path / "stats"
    stats_dir.mkdir()
    _write_score(stats_dir, "Startup import")
    db_path = tmp_path / "window.sqlite3"

    monkeypatch.setattr(main_window, "Database", lambda: Database(str(db_path)))
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(
        main_window.TrainingConfig, "get_stats_dir", lambda self: str(stats_dir),
    )
    monkeypatch.setattr(main_window, "automatic_updates_supported", lambda: False)

    window = main_window.MainWindow()
    qtbot.addWidget(window)
    try:
        qtbot.waitUntil(lambda: len(window.db.get_all_scores()) == 1, timeout=2500)
        assert window.score_watcher is not None
        assert window.score_watcher.is_started
    finally:
        window.close()


class AimHubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = Database(":memory:")
        self.widget = AimHubWidget(None, self.db)

    def tearDown(self):
        self.widget.deleteLater()
        self.app.processEvents()
        self.db.close()

    def test_lists_all_training_methods_and_renders_selected_method(self):
        self.assertEqual(self.widget.method_list.count(), len(TRAINING_METHODS))
        target = next(
            self.widget.method_list.item(index)
            for index in range(self.widget.method_list.count())
            if self.widget.method_list.item(index).data(Qt.ItemDataRole.UserRole)
            == "speed_stopping"
        )
        self.widget.method_list.setCurrentItem(target)
        self.assertEqual(self.widget.method_title.text(), "hnA: Speed and stopping")
        self.assertIn("voxTS Voltaic mini", self.widget.session_label.text())
        self.assertFalse(self.widget.source_button.isHidden())

    def test_search_filters_methods_and_action_emits_method_id(self):
        self.widget.search_input.setText("crosshair placement")
        self.assertGreaterEqual(self.widget.method_list.count(), 1)
        target = next(
            self.widget.method_list.item(index)
            for index in range(self.widget.method_list.count())
            if self.widget.method_list.item(index).data(Qt.ItemDataRole.UserRole)
            == "deathmatch_crosshair"
        )
        self.widget.method_list.setCurrentItem(target)
        received = []
        self.widget.train_requested.connect(received.append)
        self.widget.train_button.click()
        self.assertEqual(received, ["deathmatch_crosshair"])

    def test_profile_refresh_contract_is_supported(self):
        refreshed_profile = object()
        self.widget.update_profile(refreshed_profile)
        self.assertIs(self.widget.profile, refreshed_profile)


if __name__ == "__main__":
    unittest.main()
