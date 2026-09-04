"""Optional compact always-on-top view of the active guided session."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .scenario_guide import ScenarioGuideWidget


class SessionOverlay(QWidget):
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    expanded_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Aim Companion — Current training")
        self.setMinimumWidth(360)
        self._expanded = False
        layout = QVBoxLayout(self)
        self.scenario = QLabel("No active scenario")
        self.scenario.setWordWrap(True)
        self.scenario.setObjectName("sectionTitle")
        self.progress = QLabel("0 / 0 runs")
        self.progress.setAccessibleName("Scenario run progress")
        self.cue = QLabel()
        self.cue.setWordWrap(True)
        layout.addWidget(self.scenario)
        layout.addWidget(self.progress)
        layout.addWidget(self.cue)

        self.guide = ScenarioGuideWidget()
        self.guide.hide()
        layout.addWidget(self.guide)

        actions = QHBoxLayout()
        self.pause_button = QPushButton("Pause / resume")
        self.stop_button = QPushButton("Stop")
        self.expand_button = QPushButton("Expand")
        for button in (self.pause_button, self.stop_button, self.expand_button):
            button.setAccessibleName(button.text())
            actions.addWidget(button)
        layout.addLayout(actions)
        self.pause_button.clicked.connect(self.pause_requested)
        self.stop_button.clicked.connect(self.stop_requested)
        self.expand_button.clicked.connect(self._toggle_expanded)

    def set_state(self, view_model):
        self.scenario.setText(view_model.current_guide.scenario)
        self.progress.setText(view_model.progress_text)
        self.cue.setText(
            view_model.current_guide.steps[0]
            if view_model.current_guide.steps else view_model.current_guide.purpose
        )
        self.guide.set_guide(view_model.current_guide)

    def is_expanded(self):
        return self._expanded

    def _toggle_expanded(self):
        expanded = not self._expanded
        self._expanded = expanded
        self.guide.setVisible(expanded)
        self.expand_button.setText("Collapse" if expanded else "Expand")
        self.expanded_changed.emit(expanded)
