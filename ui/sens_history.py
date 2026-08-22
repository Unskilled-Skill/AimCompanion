import json
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QDoubleSpinBox, QPushButton, QComboBox,
    QLineEdit, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from models.database import Database


class SensitivityHistory(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Sensitivity History")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        subtitle = QLabel("Track sensitivity changes over time")
        subtitle.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(subtitle)

        form_row = QHBoxLayout()
        form_row.addWidget(QLabel("Game:"))
        self.game_combo = QComboBox()
        self.game_combo.addItems(["Valorant", "Apex Legends", "CS2", "Overwatch 2", "Kovaak's", "Other"])
        self.game_combo.setStyleSheet(
            "QComboBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background-color: #1a1a2a; color: white; }"
        )
        form_row.addWidget(self.game_combo)

        form_row.addWidget(QLabel("DPI:"))
        self.dpi_input = QDoubleSpinBox()
        self.dpi_input.setRange(100, 20000)
        self.dpi_input.setValue(1600)
        self.dpi_input.setStyleSheet(
            "QDoubleSpinBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
        )
        form_row.addWidget(self.dpi_input)

        form_row.addWidget(QLabel("Sens:"))
        self.sens_input = QDoubleSpinBox()
        self.sens_input.setRange(0.001, 1000)
        self.sens_input.setDecimals(4)
        self.sens_input.setValue(0.28)
        self.sens_input.setStyleSheet(
            "QDoubleSpinBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
        )
        form_row.addWidget(self.sens_input)

        add_btn = QPushButton("Log Change")
        add_btn.setStyleSheet(
            "QPushButton { background-color: #4a9eff; color: white; border-radius: 4px; padding: 8px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3a8eef; }"
        )
        add_btn.clicked.connect(self._add_entry)
        form_row.addWidget(add_btn)
        layout.addLayout(form_row)

        self.history_list = QListWidget()
        self.history_list.setStyleSheet(
            "QListWidget { background-color: #1a1a2a; color: white; border-radius: 4px; border: 1px solid #333; }"
            "QListWidget::item { padding: 6px 8px; border-bottom: 1px solid #222; }"
        )
        layout.addWidget(self.history_list)

    def _add_entry(self):
        game = self.game_combo.currentText()
        dpi = self.dpi_input.value()
        sens = self.sens_input.value()

        key = "sensitivity_history"
        existing = self.db.get_settings_value(key, "[]")
        try:
            history = json.loads(existing)
        except json.JSONDecodeError:
            history = []

        history.append({
            "game": game,
            "dpi": dpi,
            "sens": sens,
            "date": datetime.now().isoformat(),
        })

        self.db.set_settings_value(key, json.dumps(history))
        self._refresh()

    def _refresh(self):
        self.history_list.clear()
        existing = self.db.get_settings_value("sensitivity_history", "[]")
        try:
            history = json.loads(existing)
        except json.JSONDecodeError:
            history = []

        for entry in reversed(history):
            date_str = entry["date"][:10]
            item = QListWidgetItem(
                f"{date_str} | {entry['game']} | DPI: {int(entry['dpi'])} | Sens: {entry['sens']:.4f}"
            )
            self.history_list.addItem(item)

    def update_profile(self, profile):
        pass
