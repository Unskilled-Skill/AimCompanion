import json
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QScrollArea, QFrame, QPushButton, QGridLayout,
    QTextEdit, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from models.database import Database
from core.recommender import get_installed_scenarios, SCENARIOS


class ScenarioBrowser(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.all_scenarios = [
            scenario for scenario in SCENARIOS
            if scenario.get("official_recommended")
        ]
        self.installed = set(s["name"] for s in get_installed_scenarios())
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        search_row = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search scenarios...")
        self.search_input.textChanged.connect(self._filter)
        search_row.addWidget(self.search_input)

        self.category_filter = QComboBox()
        self.category_filter.addItems(["All", "Clicking", "Tracking", "Switching"])
        self.category_filter.currentTextChanged.connect(self._filter)
        search_row.addWidget(self.category_filter)

        self.subcat_filter = QComboBox()
        self.subcat_filter.addItems([
            "All", "Static", "Dynamic", "Linear",
            "Control", "Precise", "Reactive",
            "Speed", "Evasive", "Stability"
        ])
        self.subcat_filter.currentTextChanged.connect(self._filter)
        search_row.addWidget(self.subcat_filter)

        self.diff_filter = QComboBox()
        self.diff_filter.addItems(["All", "Novice", "Intermediate", "Advanced", "Unknown"])
        self.diff_filter.currentTextChanged.connect(self._filter)
        search_row.addWidget(self.diff_filter)

        self.installed_only = QCheckBox("Installed")
        self.installed_only.stateChanged.connect(self._filter)
        search_row.addWidget(self.installed_only)

        self.fav_only = QCheckBox("Favorites")
        self.fav_only.stateChanged.connect(self._filter)
        search_row.addWidget(self.fav_only)

        layout.addLayout(search_row)

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: #888;")
        layout.addWidget(self.count_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_content)
        self.scroll_layout.setSpacing(6)
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll, stretch=1)

        self._filter()

    def _filter(self):
        text = self.search_input.text().lower()
        cat = self.category_filter.currentText()
        subcat = self.subcat_filter.currentText()
        diff = self.diff_filter.currentText()
        inst_only = self.installed_only.isChecked()
        fav_only = self.fav_only.isChecked()
        favs = {f["item_name"] for f in self.db.get_favorites("scenario")}

        results = []
        for s in self.all_scenarios:
            name = s.get("name", "")
            if text and text not in name.lower():
                continue
            if cat != "All" and s.get("category", "") != cat:
                continue
            if subcat != "All" and s.get("subcategory", "") != subcat:
                continue
            if diff != "All" and s.get("difficulty", "") != diff:
                continue
            if inst_only and name not in self.installed:
                continue
            if fav_only and name not in favs:
                continue
            results.append(s)

        self.count_label.setText(f"{len(results)} official scenarios")
        self._populate(results, favs)

    def _populate(self, scenarios, favs):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 2
        for i, s in enumerate(scenarios):
            row, col = divmod(i, cols)
            card = self._card(s, favs)
            self.scroll_layout.addWidget(card, row, col)

    def _card(self, s, favs):
        name = s.get("name", "Unknown")
        cat = s.get("category", "")
        subcat = s.get("subcategory", "")
        diff = s.get("difficulty", "")
        inst = name in self.installed
        is_fav = name in favs
        has_info = s.get("instructions") or s.get("technique")
        has_routine = s.get("routine")

        border = "#263149"
        if inst and is_fav:
            border = "#ff9944"
        elif inst:
            border = "#44ff88"
        elif is_fav:
            border = "#ff9944"

        frame = QFrame()
        frame.setObjectName("scenarioCard")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(f"""
            QFrame#scenarioCard {{
                background-color: #11192b;
                border-radius: 9px;
                border-left: 3px solid {border};
                padding: 8px;
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setSpacing(3)
        layout.setContentsMargins(8, 6, 8, 6)

        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: white;")
        name_lbl.setWordWrap(True)
        layout.addWidget(name_lbl)

        meta = QLabel(f"{cat} / {subcat} / {diff}")
        meta.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(meta)

        tags_row = QHBoxLayout()
        if inst:
            tags_row.addWidget(self._tag("INSTALLED", "#44ff88"))
        if is_fav:
            tags_row.addWidget(self._tag("FAV", "#ff9944"))
        if has_info:
            tags_row.addWidget(self._tag("INFO", "#4a9eff"))
        if has_routine:
            tags_row.addWidget(self._tag("ROUTINE", "#bb88ff"))
        tags_row.addStretch()
        layout.addLayout(tags_row)

        return frame

    def _tag(self, text, color):
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {color};")
        return lbl
