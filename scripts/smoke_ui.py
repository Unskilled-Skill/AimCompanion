"""Construct and navigate every primary destination without user data."""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parents[1]))

from PyQt6.QtWidgets import QApplication
from models import config
from models.database import Database
from ui import main_window


def main():
    with tempfile.TemporaryDirectory(prefix="aim-companion-smoke-") as directory:
        root = Path(directory)
        stats = root / "stats"
        stats.mkdir()
        config.CONFIG_PATH = str(root / "config.json")
        main_window.Database = lambda: Database(str(root / "smoke.sqlite3"))
        main_window.TrainingConfig.get_stats_dir = lambda self: str(stats)
        main_window.automatic_updates_supported = lambda: False
        app = QApplication.instance() or QApplication([])
        window = main_window.MainWindow()
        window.show()
        for destination in window.shell.destination_keys:
            window.shell.navigate(destination)
            app.processEvents()
        window.close()
        app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
