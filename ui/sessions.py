import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QScrollArea, QFrame, QPushButton, QTextEdit,
    QSpinBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from models.database import Database


class SessionLogger(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self._build_ui()
        self._refresh_history()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Training Sessions")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        stats_row = QHBoxLayout()
        self.total_sessions_lbl = QLabel()
        self.total_sessions_lbl.setStyleSheet("color: white;")
        stats_row.addWidget(self.total_sessions_lbl)
        self.total_minutes_lbl = QLabel()
        self.total_minutes_lbl.setStyleSheet("color: white;")
        stats_row.addWidget(self.total_minutes_lbl)
        self.last_session_lbl = QLabel()
        self.last_session_lbl.setStyleSheet("color: white;")
        stats_row.addWidget(self.last_session_lbl)
        stats_row.addStretch()
        layout.addLayout(stats_row)
        self._update_stats()

        new_header = QLabel("Log New Session")
        new_header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        new_header.setStyleSheet("color: #4a9eff;")
        layout.addWidget(new_header)

        form_row = QHBoxLayout()
        form_row.addWidget(QLabel("Duration (min):"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(5, 480)
        self.duration_spin.setValue(60)
        self.duration_spin.setStyleSheet(
            "QSpinBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
        )
        form_row.addWidget(self.duration_spin)

        form_row.addWidget(QLabel("Focus:"))
        self.focus_combo = QComboBox()
        self.focus_combo.addItems(["weakest", "balanced", "clicking", "tracking", "switching"])
        self.focus_combo.setStyleSheet(
            "QComboBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background-color: #1a1a2a; color: white; }"
        )
        form_row.addWidget(self.focus_combo)
        form_row.addStretch()
        layout.addLayout(form_row)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Notes (optional)...")
        self.notes_input.setMaximumHeight(60)
        self.notes_input.setStyleSheet(
            "QTextEdit { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; border: 1px solid #333; }"
        )
        layout.addWidget(self.notes_input)

        log_btn = QPushButton("Log Session")
        log_btn.setStyleSheet(
            "QPushButton { background-color: #4a9eff; color: white; border-radius: 4px; padding: 8px 16px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3a8eef; }"
        )
        log_btn.clicked.connect(self._log_session)
        layout.addWidget(log_btn)

        history_header = QLabel("Session History")
        history_header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        history_header.setStyleSheet("color: #4a9eff;")
        layout.addWidget(history_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll, stretch=1)

    def _update_stats(self):
        total = self.db.get_total_sessions()
        minutes = self.db.get_total_training_minutes()
        last = self.db.get_last_session_date()
        self.total_sessions_lbl.setText(f"Sessions: {total}")
        self.total_minutes_lbl.setText(f"Total: {minutes}min ({minutes // 60}h{minutes % 60}m)")
        self.last_session_lbl.setText(
            f"Last: {last[:10] if last else 'Never'}"
        )

    def _log_session(self):
        duration = self.duration_spin.value()
        focus = self.focus_combo.currentText()
        notes = self.notes_input.toPlainText().strip()
        self.db.log_session(focus, duration, notes)
        self.notes_input.clear()
        self._update_stats()
        self._refresh_history()

    def _refresh_history(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sessions = self.db.get_sessions(limit=30)
        for s in sessions:
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet("""
                QFrame { background-color: #1e1e2e; border-radius: 6px; padding: 8px; border-left: 3px solid #4a9eff; }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(3)

            top = QHBoxLayout()
            date_lbl = QLabel(s["timestamp"][:16].replace("T", " "))
            date_lbl.setStyleSheet("color: #ccc; font-size: 10px;")
            top.addWidget(date_lbl)
            dur_lbl = QLabel(f"{s['duration_minutes']}min")
            dur_lbl.setStyleSheet("color: #44ff88; font-weight: bold;")
            top.addWidget(dur_lbl)
            focus_lbl = QLabel(s["focus"])
            focus_lbl.setStyleSheet("color: #ff9944;")
            top.addWidget(focus_lbl)
            top.addStretch()
            card_layout.addLayout(top)

            if s["notes"]:
                notes_lbl = QLabel(s["notes"])
                notes_lbl.setStyleSheet("color: #aaa; font-size: 10px;")
                notes_lbl.setWordWrap(True)
                card_layout.addWidget(notes_lbl)

            self.scroll_layout.addWidget(card)

        if not sessions:
            no_sessions = QLabel("No sessions logged yet")
            no_sessions.setStyleSheet("color: #666; font-style: italic;")
            self.scroll_layout.addWidget(no_sessions)

    def update_profile(self, profile):
        pass
