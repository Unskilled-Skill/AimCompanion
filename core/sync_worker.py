from PyQt6.QtCore import QThread, pyqtSignal

from core.parser import _get_stats_dir, iter_score_csv_paths
from core.score_importer import ScoreImporter
from models.database import Database


class ScoreSyncWorker(QThread):
    completed = pyqtSignal(int)
    failed = pyqtSignal(str)

    def __init__(self, db_path: str, stats_dir: str = None, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.stats_dir = stats_dir

    def run(self):
        db = None
        try:
            db = Database(self.db_path)
            stats_dir = self.stats_dir or _get_stats_dir()
            result = ScoreImporter(db).import_paths(iter_score_csv_paths(stats_dir))
            self.completed.emit(result.imported)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            if db:
                db.close()
