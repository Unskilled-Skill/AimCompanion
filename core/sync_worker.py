from PyQt6.QtCore import QThread, pyqtSignal

from core.parser import import_all_scores
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
            self.completed.emit(import_all_scores(db, self.stats_dir))
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            if db:
                db.close()
