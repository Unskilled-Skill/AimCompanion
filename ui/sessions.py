from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSpinBox, QTextEdit, QVBoxLayout, QWidget,
)

from models.database import Database


class SessionLogger(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self._build_ui()
        self._update_stats()
        self._refresh_history()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        intro = QHBoxLayout()
        intro.addWidget(self._title("Training sessions"))
        intro.addStretch()
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("color: #94e2d5; font-weight: bold;")
        intro.addWidget(self.summary_label)
        root.addLayout(intro)

        form_card = self._card()
        form = QVBoxLayout(form_card)
        form.setContentsMargins(16, 14, 16, 14)
        form.setSpacing(10)
        heading = QHBoxLayout()
        heading.addWidget(self._section("Log a session"))
        heading.addStretch()
        help_text = QLabel("Quick blocks are logged automatically; use this for sessions done outside the app.")
        help_text.setObjectName("mutedText")
        heading.addWidget(help_text)
        form.addLayout(heading)

        fields = QHBoxLayout()
        fields.setSpacing(10)
        fields.addWidget(QLabel("Duration"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(5, 480)
        self.duration_spin.setValue(30)
        self.duration_spin.setSuffix(" min")
        self.duration_spin.setFixedWidth(110)
        fields.addWidget(self.duration_spin)
        fields.addWidget(QLabel("Focus"))
        self.focus_combo = QComboBox()
        self.focus_combo.addItems(["Balanced", "Weakest skill", "Clicking", "Tracking", "Switching"])
        self.focus_combo.setFixedWidth(170)
        fields.addWidget(self.focus_combo)
        fields.addStretch()
        form.addLayout(fields)

        self.notes_input = QTextEdit()
        self.notes_input.setPlaceholderText("Optional note — what felt good, difficult, or worth repeating?")
        self.notes_input.setMaximumHeight(64)
        form.addWidget(self.notes_input)
        log_btn = QPushButton("Save session")
        log_btn.setObjectName("primaryButton")
        log_btn.setMaximumWidth(160)
        log_btn.clicked.connect(self._log_session)
        form.addWidget(log_btn, 0, Qt.AlignmentFlag.AlignRight)
        root.addWidget(form_card)

        history_header = QHBoxLayout()
        history_header.addWidget(self._section("Recent sessions"))
        history_header.addStretch()
        self.history_count = QLabel()
        self.history_count.setObjectName("mutedText")
        history_header.addWidget(self.history_count)
        root.addLayout(history_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(8)
        scroll.setWidget(self.scroll_content)
        root.addWidget(scroll, 1)

    def _update_stats(self):
        total = self.db.get_total_sessions()
        minutes = self.db.get_total_training_minutes()
        last = self.db.get_last_session_date()
        time_text = f"{minutes // 60}h {minutes % 60}m" if minutes >= 60 else f"{minutes} min"
        last_text = last[:10] if last else "never"
        self.summary_label.setText(f"{total} sessions  •  {time_text} total  •  last {last_text}")

    def _log_session(self):
        focus_map = {"Weakest skill": "weakest"}
        focus = focus_map.get(self.focus_combo.currentText(), self.focus_combo.currentText().casefold())
        self.db.log_session(focus, self.duration_spin.value(), self.notes_input.toPlainText().strip())
        self.notes_input.clear()
        self._update_stats()
        self._refresh_history()

    def _refresh_history(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sessions = self.db.get_sessions(limit=30)
        self.history_count.setText(f"Showing {len(sessions)}") if sessions else self.history_count.setText("")
        if not sessions:
            empty = self._card()
            empty_layout = QVBoxLayout(empty)
            empty_layout.setContentsMargins(18, 24, 18, 24)
            title = QLabel("No manual sessions yet")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
            title.setStyleSheet("color: #cdd6f4;")
            empty_layout.addWidget(title)
            note = QLabel("Your quick training blocks still contribute automatically. Log a session here only when you train outside Aim Companion.")
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            note.setWordWrap(True)
            note.setObjectName("mutedText")
            empty_layout.addWidget(note)
            self.scroll_layout.addWidget(empty)
            self.scroll_layout.addStretch()
            return

        for session in sessions:
            card = self._card()
            row = QHBoxLayout(card)
            row.setContentsMargins(14, 10, 14, 10)
            date = QLabel(session["timestamp"][:16].replace("T", "  "))
            date.setFixedWidth(145)
            date.setStyleSheet("color: #a6adc8;")
            row.addWidget(date)
            focus = QLabel((session["focus"] or "General").replace("_", " ").title())
            focus.setStyleSheet("color: #89b4fa; font-weight: bold;")
            row.addWidget(focus)
            row.addStretch()
            if session["notes"]:
                notes = QLabel(session["notes"])
                notes.setMaximumWidth(480)
                notes.setWordWrap(True)
                notes.setStyleSheet("color: #7f849c;")
                row.addWidget(notes)
            duration = QLabel(f"{session['duration_minutes']} min")
            duration.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            row.addWidget(duration)
            self.scroll_layout.addWidget(card)
        self.scroll_layout.addStretch()

    @staticmethod
    def _card():
        card = QFrame()
        card.setObjectName("toolCard")
        card.setStyleSheet("QFrame#toolCard { background: #11192b; border: 1px solid #263149; border-radius: 9px; }")
        return card

    @staticmethod
    def _title(text):
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        label.setStyleSheet("color: #cdd6f4;")
        return label

    @staticmethod
    def _section(text):
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        label.setStyleSheet("color: #cdd6f4;")
        return label

    def update_profile(self, profile):
        self._update_stats()
        self._refresh_history()
