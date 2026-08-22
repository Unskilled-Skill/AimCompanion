import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QSplitter, QVBoxLayout, QWidget,
)

from core.recommender import SCENARIOS, get_installed_scenario_names
from models.database import Database
from models.score import PlayerProfile


class RoutineBuilder(QWidget):
    scenario_added = pyqtSignal(dict)

    def __init__(self, profile: PlayerProfile, db: Database):
        super().__init__()
        self.profile = profile
        self.db = db
        self.custom_routine = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        top = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Routine builder")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        title_block.addWidget(title)
        subtitle = QLabel("Create a reusable manual routine. Each scenario is a focused 3-minute block.")
        subtitle.setObjectName("mutedText")
        title_block.addWidget(subtitle)
        top.addLayout(title_block)
        top.addStretch()
        self.routine_summary = QLabel("0 blocks  •  0 min")
        self.routine_summary.setStyleSheet("color: #94e2d5; font-weight: bold;")
        top.addWidget(self.routine_summary)
        root.addLayout(top)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_library_panel())
        splitter.addWidget(self._build_routine_panel())
        splitter.setSizes([580, 480])
        root.addWidget(splitter, 1)
        self._populate_available()

    def _build_library_panel(self):
        panel = self._card()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(9)
        heading = QHBoxLayout()
        heading.addWidget(self._section("Scenario library"))
        heading.addStretch()
        self.available_count = QLabel()
        self.available_count.setObjectName("mutedText")
        heading.addWidget(self.available_count)
        layout.addLayout(heading)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by scenario name…")
        self.search.textChanged.connect(self._filter_list)
        filters.addWidget(self.search, 1)
        self.filter_cat = QComboBox()
        self.filter_cat.addItems(["All skills", "Clicking", "Tracking", "Switching"])
        self.filter_cat.setFixedWidth(140)
        self.filter_cat.currentTextChanged.connect(self._filter_list)
        filters.addWidget(self.filter_cat)
        layout.addLayout(filters)

        self.available_list = QListWidget()
        self.available_list.setAlternatingRowColors(True)
        self.available_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.available_list.itemDoubleClicked.connect(self._add_scenario)
        layout.addWidget(self.available_list, 1)
        add = QPushButton("Add selected  →")
        add.setObjectName("primaryButton")
        add.clicked.connect(self._add_selected)
        layout.addWidget(add)
        return panel

    def _build_routine_panel(self):
        panel = self._card()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(9)
        layout.addWidget(self._section("Current routine"))
        helper = QLabel("Double-click an item to remove it.")
        helper.setObjectName("mutedText")
        layout.addWidget(helper)
        self.routine_list = QListWidget()
        self.routine_list.setAlternatingRowColors(True)
        self.routine_list.itemDoubleClicked.connect(self._remove_scenario)
        layout.addWidget(self.routine_list, 1)

        actions = QHBoxLayout()
        remove = QPushButton("Remove selected")
        remove.setObjectName("secondaryButton")
        remove.clicked.connect(self._remove_selected)
        actions.addWidget(remove)
        clear = QPushButton("Clear")
        clear.setObjectName("secondaryButton")
        clear.clicked.connect(self._clear_routine)
        actions.addWidget(clear)
        layout.addLayout(actions)

        save = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Routine name")
        save.addWidget(self.name_input, 1)
        save_btn = QPushButton("Save routine")
        save_btn.setObjectName("primaryButton")
        save_btn.clicked.connect(self._save_routine)
        save.addWidget(save_btn)
        layout.addLayout(save)
        return panel

    def _populate_available(self):
        self._filter_list()

    def _filter_list(self, *_args):
        text = self.search.text().casefold()
        selected_category = self.filter_cat.currentText()
        installed = {name.casefold() for name in get_installed_scenario_names()}
        self.available_list.clear()
        count = 0
        for scenario in SCENARIOS:
            if text and text not in scenario["name"].casefold():
                continue
            if selected_category != "All skills" and scenario.get("category", "") != selected_category:
                continue
            installed_label = "  •  installed" if scenario["name"].casefold() in installed else ""
            self.available_list.addItem(
                f"{scenario['name']}    {scenario['category']} / {scenario['subcategory']}{installed_label}"
            )
            count += 1
        self.available_count.setText(f"{count} shown")

    def _add_scenario(self, item):
        name = item.text().split("    ")[0]
        if name not in [entry["scenario"] for entry in self.custom_routine]:
            self.custom_routine.append({"scenario": name, "duration_min": 3})
            self.routine_list.addItem(f"{len(self.custom_routine)}.  {name}    3 min")
            self._update_summary()

    def _add_selected(self):
        for item in self.available_list.selectedItems():
            self._add_scenario(item)

    def _remove_scenario(self, item):
        row = self.routine_list.row(item)
        if 0 <= row < len(self.custom_routine):
            self.custom_routine.pop(row)
        self.routine_list.takeItem(row)
        self._rebuild_routine_list()

    def _remove_selected(self):
        for item in list(self.routine_list.selectedItems()):
            self._remove_scenario(item)

    def _clear_routine(self):
        self.custom_routine.clear()
        self.routine_list.clear()
        self._update_summary()

    def _rebuild_routine_list(self):
        self.routine_list.clear()
        for index, entry in enumerate(self.custom_routine, 1):
            self.routine_list.addItem(f"{index}.  {entry['scenario']}    {entry.get('duration_min', 3)} min")
        self._update_summary()

    def _update_summary(self):
        minutes = sum(entry.get("duration_min", 3) for entry in self.custom_routine)
        self.routine_summary.setText(f"{len(self.custom_routine)} blocks  •  {minutes} min")

    def _save_routine(self):
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Routine name needed", "Enter a name for this routine.")
            return
        if not self.custom_routine:
            QMessageBox.warning(self, "Routine is empty", "Add at least one scenario first.")
            return
        routine_data = {
            "name": name,
            "exercises": self.custom_routine,
            "focus": "custom",
            "session_minutes": sum(entry.get("duration_min", 3) for entry in self.custom_routine),
        }
        self.db.save_routine(name, json.dumps(routine_data))
        self.name_input.clear()
        QMessageBox.information(self, "Routine saved", f"{name} is ready to use.")

    @staticmethod
    def _card():
        frame = QFrame()
        frame.setObjectName("toolCard")
        frame.setStyleSheet("QFrame#toolCard { background: #11192b; border: 1px solid #263149; border-radius: 9px; }")
        return frame

    @staticmethod
    def _section(text):
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        label.setStyleSheet("color: #cdd6f4;")
        return label

    def update_profile(self, profile):
        self.profile = profile
        self._filter_list()
