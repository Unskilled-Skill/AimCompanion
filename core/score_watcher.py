"""Debounced background imports for Kovaak's score directory."""

from __future__ import annotations

import os

from PyQt6.QtCore import QFileSystemWatcher, QObject, QTimer, pyqtSignal

from core.sync_worker import ScoreSyncWorker


class ScoreDirectoryWatcher(QObject):
    """Keep score imports current without blocking the Qt event loop."""

    batch_completed = pyqtSignal(object)
    batch_failed = pyqtSignal(str)

    def __init__(self, db_path: str, stats_dir: str, parent=None):
        super().__init__(parent)
        self._db_path = db_path
        self._stats_dir = os.path.abspath(stats_dir)
        self._parent_dir = os.path.dirname(self._stats_dir)
        self._timer = QTimer(self, interval=750, singleShot=True)
        self._timer.timeout.connect(self._scan)
        self._file_watcher = QFileSystemWatcher(self)
        self._file_watcher.directoryChanged.connect(self._on_directory_changed)
        self._worker = None
        self._rescan_pending = False
        self._started = False

    @property
    def is_started(self) -> bool:
        return self._started

    def start(self):
        """Begin observing the configured directory and schedule recovery."""
        if self._started:
            return
        self._started = True
        self._watch_parent_directory()
        if self._watch_stats_directory():
            self._schedule_scan()

    def stop(self):
        """Stop future scans and finish only the worker already in progress."""
        if not self._started and self._worker is None:
            return
        self._started = False
        self._rescan_pending = False
        self._timer.stop()
        watched_paths = self._file_watcher.directories()
        if watched_paths:
            self._file_watcher.removePaths(watched_paths)

        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.requestInterruption()
            worker.wait(3000)
        if worker is not None and not worker.isRunning():
            self._worker = None

    def notify_directory_changed(self):
        """Request a debounced scan; exposed for explicit refresh actions."""
        if not self._started:
            return
        if not self._watch_stats_directory():
            return
        self._schedule_scan()

    def _on_directory_changed(self, path: str):
        if (
            os.path.normcase(os.path.abspath(path))
            == os.path.normcase(self._parent_dir)
            and self._stats_dir in self._file_watcher.directories()
        ):
            return
        self.notify_directory_changed()

    def _watch_parent_directory(self):
        if not os.path.isdir(self._parent_dir):
            return
        if self._parent_dir not in self._file_watcher.directories():
            self._file_watcher.addPath(self._parent_dir)

    def _watch_stats_directory(self) -> bool:
        if not os.path.isdir(self._stats_dir):
            self.batch_failed.emit(
                f"Configured score directory is not available: {self._stats_dir}"
            )
            return False
        if self._stats_dir not in self._file_watcher.directories():
            if not self._file_watcher.addPath(self._stats_dir):
                self.batch_failed.emit(
                    f"Could not watch score directory: {self._stats_dir}"
                )
                return False
        return True

    def _schedule_scan(self):
        if self._worker is not None and self._worker.isRunning():
            self._rescan_pending = True
        self._timer.start()

    def _scan(self):
        if not self._started:
            return
        if not self._watch_stats_directory():
            return
        if self._worker is not None and self._worker.isRunning():
            self._rescan_pending = True
            return

        self._rescan_pending = False
        worker = ScoreSyncWorker(self._db_path, self._stats_dir, parent=self)
        self._worker = worker
        worker.completed.connect(self._on_worker_completed)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(self._on_worker_finished)
        worker.start()

    def _on_worker_completed(self, result):
        if self.sender() is not self._worker:
            return
        if not self._started:
            return
        self.batch_completed.emit(result)

    def _on_worker_failed(self, message: str):
        if self.sender() is not self._worker:
            return
        if not self._started:
            return
        self.batch_failed.emit(message)

    def _on_worker_finished(self):
        if self.sender() is not self._worker:
            return
        self._worker = None
        if not self._started:
            return
        self._schedule_pending_scan()

    def _schedule_pending_scan(self):
        if self._rescan_pending:
            self._rescan_pending = False
            self._timer.start()
