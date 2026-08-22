import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTextEdit, QMessageBox, QLineEdit,
    QComboBox, QListWidget, QListWidgetItem, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from models.database import Database
from models.score import PlayerProfile
from core.recommender import generate_routine, get_scenario_info, SCENARIOS, SCENARIO_MAP, get_installed_scenario_names
from models.config import TrainingConfig, FOCUS_OPTIONS


class RoutineBuilder(QWidget):
    scenario_added = pyqtSignal(dict)

    def __init__(self, profile: PlayerProfile, db: Database):
        super().__init__()
        self.profile = profile
        self.db = db
        self.custom_routine = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Custom Routine Builder")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        subtitle = QLabel("Manually build your own routine by selecting scenarios")
        subtitle.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(subtitle)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search scenarios...")
        self.search.setStyleSheet(
            "QLineEdit { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 6px; border: 1px solid #333; }"
        )
        self.search.textChanged.connect(self._filter_list)
        search_row.addWidget(self.search)

        self.filter_cat = QComboBox()
        self.filter_cat.addItems(["All", "Clicking", "Tracking", "Switching"])
        self.filter_cat.setStyleSheet(
            "QComboBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background-color: #1a1a2a; color: white; }"
        )
        self.filter_cat.currentTextChanged.connect(self._filter_list)
        search_row.addWidget(self.filter_cat)
        left_layout.addLayout(search_row)

        self.available_list = QListWidget()
        self.available_list.setStyleSheet(
            "QListWidget { background-color: #1a1a2a; color: white; border-radius: 4px; border: 1px solid #333; }"
            "QListWidget::item { padding: 4px 8px; }"
            "QListWidget::item:selected { background-color: #4a9eff; }"
        )
        self.available_list.itemDoubleClicked.connect(self._add_scenario)
        left_layout.addWidget(self.available_list)

        add_btn = QPushButton("Add Selected ->")
        add_btn.clicked.connect(self._add_selected)
        left_layout.addWidget(add_btn)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        right_layout.addWidget(QLabel("Current Routine:"))

        self.routine_list = QListWidget()
        self.routine_list.setStyleSheet(
            "QListWidget { background-color: #1a1a2a; color: white; border-radius: 4px; border: 1px solid #333; }"
            "QListWidget::item { padding: 4px 8px; }"
            "QListWidget::item:selected { background-color: #ff9944; }"
        )
        self.routine_list.itemDoubleClicked.connect(self._remove_scenario)
        right_layout.addWidget(self.routine_list)

        btn_row = QHBoxLayout()
        remove_btn = QPushButton("<- Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        btn_row.addWidget(remove_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_routine)
        btn_row.addWidget(clear_btn)
        right_layout.addLayout(btn_row)

        save_row = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Routine name...")
        self.name_input.setStyleSheet(
            "QLineEdit { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 6px; border: 1px solid #333; }"
        )
        save_row.addWidget(self.name_input)

        save_btn = QPushButton("Save Routine")
        save_btn.setStyleSheet(
            "QPushButton { background-color: #44ff88; color: #111; border-radius: 4px; padding: 8px; font-weight: bold; }"
            "QPushButton:hover { background-color: #33ee77; }"
        )
        save_btn.clicked.connect(self._save_routine)
        save_row.addWidget(save_btn)
        right_layout.addLayout(save_row)

        splitter.addWidget(right)
        splitter.setSizes([400, 400])
        layout.addWidget(splitter, stretch=1)

        self._populate_available()

    def _populate_available(self):
        self.available_list.clear()
        installed = {name.casefold() for name in get_installed_scenario_names()}
        for s in SCENARIOS:
            inst = " [INSTALLED]" if s["name"].casefold() in installed else ""
            self.available_list.addItem(f"{s['name']} ({s['category']}/{s['subcategory']}){inst}")

    def _filter_list(self):
        text = self.search.text().lower()
        cat = self.filter_cat.currentText()
        installed = {name.casefold() for name in get_installed_scenario_names()}
        self.available_list.clear()
        for s in SCENARIOS:
            if text and text not in s["name"].lower():
                continue
            if cat != "All" and s.get("category", "") != cat:
                continue
            inst = " [INSTALLED]" if s["name"].casefold() in installed else ""
            self.available_list.addItem(f"{s['name']} ({s['category']}/{s['subcategory']}){inst}")

    def _add_scenario(self, item):
        name = item.text().split(" (")[0]
        if name not in [e["scenario"] for e in self.custom_routine]:
            self.custom_routine.append({"scenario": name, "duration_min": 3})
            self.routine_list.addItem(f"{name} (3min)")

    def _add_selected(self):
        for item in self.available_list.selectedItems():
            self._add_scenario(item)

    def _remove_scenario(self, item):
        name = item.text().split(" (")[0]
        self.custom_routine = [e for e in self.custom_routine if e["scenario"] != name]
        self.routine_list.takeItem(self.routine_list.row(item))

    def _remove_selected(self):
        for item in self.routine_list.selectedItems():
            self._remove_scenario(item)

    def _clear_routine(self):
        self.custom_routine.clear()
        self.routine_list.clear()

    def _save_routine(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Enter a routine name")
            return
        if not self.custom_routine:
            QMessageBox.warning(self, "Error", "Add at least one scenario")
            return

        routine_data = {
            "name": name,
            "exercises": self.custom_routine,
            "focus": "custom",
            "session_minutes": sum(e.get("duration_min", 3) for e in self.custom_routine),
        }

        self.db.save_routine(name, json.dumps(routine_data))
        self.name_input.clear()
        QMessageBox.information(self, "Saved", f"Routine '{name}' saved!")

    def update_profile(self, profile):
        self.profile = profile
