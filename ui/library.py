"""Reference library for authored routines, scenarios, warm-ups, and transfer."""

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox, QLabel, QListWidget, QPushButton, QScrollArea, QTabWidget,
    QVBoxLayout, QWidget,
)

from core.recommender import TACFPS_GUIDE
from core.warmups import GAME_WARMUP_ROUTINES, RECOMMENDED_WARMUP_ROUTINE
from .deathmatch import DeathmatchProgressWidget


class LibraryWidget(QTabWidget):
    full_routine_requested = pyqtSignal(str)

    def __init__(self, db, scenario_widget, parent=None):
        super().__init__(parent)
        self._routines = TACFPS_GUIDE["routines"]
        self._routine_page = self._build_routines()
        self.addTab(self._routine_page, "Routines")
        self.addTab(scenario_widget, "Scenarios")
        self.addTab(self._build_warmups(), "Warm-ups")
        self._deathmatch = DeathmatchProgressWidget(db, show_source=True)
        self.addTab(self._deathmatch, "Game Transfer")
        self._show_routine(0)

    def _build_routines(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.routine_selector = QComboBox()
        self.routine_selector.setAccessibleName("Select source routine")
        self.routine_selector.addItems(item["name"] for item in self._routines)
        self.routine_selector.currentIndexChanged.connect(self._show_routine)
        layout.addWidget(self.routine_selector)
        self.routine_description = QLabel()
        self.routine_description.setWordWrap(True)
        layout.addWidget(self.routine_description)
        self.exercise_list = QListWidget()
        self.exercise_list.setAccessibleName("Routine exercises and instructions")
        layout.addWidget(self.exercise_list, 1)
        self.source_button = QPushButton()
        self.source_button.setAccessibleName("Open original routine source")
        self.source_button.clicked.connect(self._open_source)
        layout.addWidget(self.source_button)
        start = QPushButton("Start this full routine")
        start.setAccessibleName(start.text())
        start.clicked.connect(
            lambda: self.full_routine_requested.emit(
                self._routines[self.routine_selector.currentIndex()]["name"]
            )
        )
        layout.addWidget(start)
        return page

    def _build_warmups(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel(
            "Warm-ups remember the last context you used. Game warm-ups prepare "
            "game-specific control; routine warm-ups cover the skills used by that routine."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        for game, steps in GAME_WARMUP_ROUTINES.items():
            copy = QLabel(
                f"{game}\n" + "\n".join(
                    f"• {step['scenario']} — {step.get('cue', '')}" for step in steps
                )
            )
            copy.setWordWrap(True)
            layout.addWidget(copy)
        general = QLabel(
            "General routine warm-up\n" + "\n".join(
                f"• {step['scenario']} — {step.get('cue', '')}"
                for step in RECOMMENDED_WARMUP_ROUTINE
            )
        )
        general.setWordWrap(True)
        layout.addWidget(general)
        layout.addStretch()
        scroll.setWidget(page)
        return scroll

    def _show_routine(self, index):
        if not 0 <= index < len(self._routines):
            return
        routine = self._routines[index]
        guidance = "\n".join(f"• {item}" for item in routine["author_guidance"])
        self.routine_description.setText(
            f"{routine['description']}\n\nHow to perform the routine\n{guidance}"
        )
        self.exercise_list.clear()
        for exercise in routine["exercises"]:
            guide = exercise["performance_guide"]
            steps = " ".join(
                f"{number}. {text}" for number, text in enumerate(guide["steps"], 1)
            )
            adjustment = guide.get("adjust")
            text = (
                f"{exercise['scenario']} — {exercise['duration']}\n"
                f"Purpose: {exercise['focus']}\nSetup: {guide['setup']}\n"
                f"What to do: {steps}\nSuccess: {guide['success']}"
            )
            if adjustment:
                text += f"\nAdjustment: {adjustment}"
            self.exercise_list.addItem(text)
        self._source_url = routine["source_url"]
        self.source_button.setText(f"Source: {routine['source']}")

    def _open_source(self):
        QDesktopServices.openUrl(QUrl(self._source_url))

    def game_transfer_titles(self):
        return ("Deathmatch",)
