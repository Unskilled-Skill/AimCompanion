import json
import os
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSpinBox, QComboBox, QMessageBox, QSystemTrayIcon
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

from models.database import Database


class TrainingTimer(QWidget):
    exercise_finished = pyqtSignal(str)
    session_finished = pyqtSignal()

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.running = False
        self.paused = False
        self.seconds_left = 0
        self.total_seconds = 0
        self.interval_seconds = 0
        self.break_seconds = 0
        self.is_break = False
        self.exercise_name = ""
        self.session_start_time = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Training Timer")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        self.timer_frame = QFrame()
        self.timer_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.timer_frame.setStyleSheet("""
            QFrame { background-color: #1e1e2e; border-radius: 12px; padding: 20px; }
        """)
        timer_layout = QVBoxLayout(self.timer_frame)
        timer_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.time_label = QLabel("00:00")
        self.time_label.setFont(QFont("Consolas", 48, QFont.Weight.Bold))
        self.time_label.setStyleSheet("color: #4a9eff;")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.addWidget(self.time_label)

        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Segoe UI", 12))
        self.status_label.setStyleSheet("color: #888;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.addWidget(self.status_label)

        self.exercise_label = QLabel("")
        self.exercise_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.exercise_label.setStyleSheet("color: #44ff88;")
        self.exercise_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer_layout.addWidget(self.exercise_label)

        layout.addWidget(self.timer_frame)

        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("Duration (min):"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1, 120)
        self.duration_spin.setValue(3)
        self.duration_spin.setStyleSheet(
            "QSpinBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
        )
        settings_row.addWidget(self.duration_spin)

        settings_row.addWidget(QLabel("Break (sec):"))
        self.break_spin = QSpinBox()
        self.break_spin.setRange(0, 300)
        self.break_spin.setValue(10)
        self.break_spin.setStyleSheet(
            "QSpinBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
        )
        settings_row.addWidget(self.break_spin)

        settings_row.addWidget(QLabel("Intervals:"))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 50)
        self.interval_spin.setValue(1)
        self.interval_spin.setStyleSheet(
            "QSpinBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
        )
        settings_row.addWidget(self.interval_spin)
        settings_row.addStretch()
        layout.addLayout(settings_row)

        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("Start")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #44ff88; color: #111; border-radius: 6px; padding: 10px 20px; font-weight: bold; font-size: 14px; }"
            "QPushButton:hover { background-color: #33ee77; }"
        )
        self.start_btn.clicked.connect(self._toggle)
        btn_row.addWidget(self.start_btn)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setStyleSheet(
            "QPushButton { background-color: #ff4444; color: white; border-radius: 6px; padding: 10px 20px; font-weight: bold; }"
            "QPushButton:hover { background-color: #ee3333; }"
        )
        self.reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(self.reset_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.progress_label = QLabel("")
        self.progress_label.setStyleSheet("color: #888;")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_label)

        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)

    def set_exercise(self, name: str):
        self.exercise_name = name
        self.exercise_label.setText(name)

    def _toggle(self):
        if self.running:
            self._pause()
        else:
            self._start()

    def _start(self):
        if not self.running:
            self.total_seconds = self.duration_spin.value() * 60
            self.seconds_left = self.total_seconds
            self.break_seconds = self.break_spin.value()
            self.interval_seconds = self.interval_spin.value()
            self.is_break = False
            self.session_start_time = time.time()

        self.running = True
        self.paused = False
        self.start_btn.setText("Pause")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #ffaa00; color: #111; border-radius: 6px; padding: 10px 20px; font-weight: bold; font-size: 14px; }"
            "QPushButton:hover { background-color: #ee9900; }"
        )
        self.timer.start(1000)

    def _pause(self):
        self.paused = True
        self.running = False
        self.timer.stop()
        self.start_btn.setText("Resume")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #44ff88; color: #111; border-radius: 6px; padding: 10px 20px; font-weight: bold; font-size: 14px; }"
            "QPushButton:hover { background-color: #33ee77; }"
        )
        self.status_label.setText("Paused")

    def _reset(self):
        self.running = False
        self.paused = False
        self.timer.stop()
        self.seconds_left = 0
        self.time_label.setText("00:00")
        self.status_label.setText("Ready")
        self.start_btn.setText("Start")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #44ff88; color: #111; border-radius: 6px; padding: 10px 20px; font-weight: bold; font-size: 14px; }"
            "QPushButton:hover { background-color: #33ee77; }"
        )
        self.progress_label.setText("")

    def _tick(self):
        if self.seconds_left <= 0:
            self._timer_done()
            return

        self.seconds_left -= 1
        mins = self.seconds_left // 60
        secs = self.seconds_left % 60
        self.time_label.setText(f"{mins:02d}:{secs:02d}")

        if self.is_break:
            self.time_label.setStyleSheet("color: #ffaa00;")
            self.status_label.setText("BREAK")
        else:
            elapsed = self.total_seconds - self.seconds_left
            pct = int(elapsed / self.total_seconds * 100)
            self.progress_label.setText(f"{pct}% complete")

    def _timer_done(self):
        self.timer.stop()

        if self.is_break:
            self.is_break = False
            self.seconds_left = self.total_seconds
            self.time_label.setStyleSheet("color: #4a9eff;")
            self.status_label.setText("Training")
            self.timer.start(1000)
            return

        self.exercise_finished.emit(self.exercise_name)

        if self.break_seconds > 0:
            self.is_break = True
            self.seconds_left = self.break_seconds
            self.time_label.setStyleSheet("color: #ffaa00;")
            self.status_label.setText("BREAK")
            self.timer.start(1000)
        else:
            self._interval_done()

    def _interval_done(self):
        self.running = False
        self.start_btn.setText("Start")
        self.start_btn.setStyleSheet(
            "QPushButton { background-color: #44ff88; color: #111; border-radius: 6px; padding: 10px 20px; font-weight: bold; font-size: 14px; }"
            "QPushButton:hover { background-color: #33ee77; }"
        )
        self.status_label.setText("Done!")
        self.time_label.setText("00:00")
        self.time_label.setStyleSheet("color: #44ff88;")
        self.session_finished.emit()

        duration = int(time.time() - self.session_start_time) if self.session_start_time else 0
        self.progress_label.setText(f"Completed in {duration // 60}m {duration % 60}s")

    def update_profile(self, profile):
        pass
