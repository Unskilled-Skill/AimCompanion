from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTextEdit, QScrollArea, QPushButton, QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from core.recommender import SCENARIOS, SCENARIO_MAP, get_installed_scenarios


class ScenarioDetail(QWidget):
    scenario_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.installed = set(s["name"] for s in get_installed_scenarios())
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Scenario Details")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        self.list_widget = QListWidget()
        self.list_widget.setMaximumWidth(250)
        self.list_widget.setStyleSheet(
            "QListWidget { background-color: #1a1a2a; color: white; border-radius: 4px; border: 1px solid #333; }"
            "QListWidget::item { padding: 4px 8px; }"
            "QListWidget::item:selected { background-color: #4a9eff; }"
        )
        for s in SCENARIOS:
            self.list_widget.addItem(s["name"])
        self.list_widget.currentTextChanged.connect(self._on_select)

        detail_frame = QFrame()
        detail_frame.setFrameShape(QFrame.Shape.StyledPanel)
        detail_frame.setStyleSheet("QFrame { background-color: #1e1e2e; border-radius: 8px; padding: 15px; }")
        self.detail_layout = QVBoxLayout(detail_frame)

        self.name_label = QLabel("Select a scenario")
        self.name_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.name_label.setStyleSheet("color: white;")
        self.detail_layout.addWidget(self.name_label)

        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("color: #888;")
        self.detail_layout.addWidget(self.meta_label)

        self.installed_label = QLabel("")
        self.detail_layout.addWidget(self.installed_label)

        self.technique_label = QLabel("")
        self.technique_label.setWordWrap(True)
        self.technique_label.setStyleSheet("color: #4a9eff; font-size: 12px;")
        self.detail_layout.addWidget(self.technique_label)

        self.instructions_label = QLabel("")
        self.instructions_label.setWordWrap(True)
        self.instructions_label.setStyleSheet("color: #ddd; font-size: 11px;")
        self.detail_layout.addWidget(self.instructions_label)

        self.routine_label = QLabel("")
        self.routine_label.setWordWrap(True)
        self.routine_label.setStyleSheet("color: #bb88ff; font-size: 11px;")
        self.detail_layout.addWidget(self.routine_label)

        self.detail_layout.addStretch()

        splitter_h = QHBoxLayout()
        splitter_h.addWidget(self.list_widget)
        splitter_h.addWidget(detail_frame, stretch=1)
        layout.addLayout(splitter_h)

    def _on_select(self, name):
        if not name:
            return
        info = SCENARIO_MAP.get(name, {})
        cat = info.get("category", "Unknown")
        subcat = info.get("subcategory", "Unknown")
        diff = info.get("difficulty", "Unknown")
        tags = info.get("tags", [])

        self.name_label.setText(name)
        self.meta_label.setText(f"{cat} / {subcat} / {diff}")

        if name in self.installed:
            self.installed_label.setText("INSTALLED")
            self.installed_label.setStyleSheet("color: #44ff88; font-weight: bold; font-size: 12px;")
        else:
            self.installed_label.setText("Not installed")
            self.installed_label.setStyleSheet("color: #888; font-size: 10px;")

        technique = info.get("technique", "")
        self.technique_label.setText(f"Technique: {technique}" if technique else "")

        instructions = info.get("instructions", "")
        self.instructions_label.setText(f"Instructions: {instructions}" if instructions else "")

        routine = info.get("routine", "")
        self.routine_label.setText(f"Routine: {routine}" if routine else "")

        if tags:
            tag_str = "Tags: " + ", ".join(tags)
            self.meta_label.setText(f"{cat} / {subcat} / {diff} | {tag_str}")
