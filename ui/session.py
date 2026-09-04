"""Guided training session destination."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .scenario_guide import ScenarioGuideWidget


class SessionWidget(QWidget):
    """Render session state and emit user intents without owning session state."""

    launch_requested = pyqtSignal()
    manual_run_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    restart_requested = pyqtSignal()
    next_requested = pyqtSignal()
    overlay_enabled_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("panel")
        header_layout = QVBoxLayout(header)
        self.title_label = QLabel("No active session")
        self.title_label.setObjectName("sectionTitle")
        self.title_label.setWordWrap(True)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.evidence_label = QLabel()
        self.evidence_label.setWordWrap(True)
        self.evidence_label.setAccessibleName("Recommendation evidence")
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.status_label)
        header_layout.addWidget(self.evidence_label)
        layout.addWidget(header)

        guide_panel = QFrame()
        guide_panel.setObjectName("panel")
        guide_layout = QVBoxLayout(guide_panel)
        guide_layout.addWidget(QLabel("Current scenario — detailed guide"))
        self.guide = ScenarioGuideWidget()
        self.run_progress = self.guide.run_progress
        guide_layout.addWidget(self.guide)
        layout.addWidget(guide_panel)

        overview_panel = QFrame()
        overview_panel.setObjectName("panel")
        overview_layout = QVBoxLayout(overview_panel)
        overview_layout.addWidget(QLabel("Routine overview"))
        self.overview = QListWidget()
        self.overview.setAccessibleName("Full routine overview")
        overview_layout.addWidget(self.overview)
        layout.addWidget(overview_panel)

        controls_panel = QFrame()
        controls_panel.setObjectName("panel")
        controls = QVBoxLayout(controls_panel)
        advance_row = QHBoxLayout()
        advance_row.addWidget(QLabel("Run detection"))
        self.advance_mode = QComboBox()
        self.advance_mode.addItems(("Automatic with manual fallback", "Manual only"))
        self.advance_mode.setAccessibleName("Run detection mode")
        advance_row.addWidget(self.advance_mode, 1)
        self.overlay_checkbox = QCheckBox("Show compact always-on-top panel")
        self.overlay_checkbox.setAccessibleName("Show compact training panel")
        advance_row.addWidget(self.overlay_checkbox)
        controls.addLayout(advance_row)

        actions = QHBoxLayout()
        self.launch_button = QPushButton("Launch in KovaaK's")
        self.manual_button = QPushButton("Count completed run")
        self.pause_button = QPushButton("Pause / resume")
        self.restart_button = QPushButton("Restart scenario")
        self.next_button = QPushButton("Next recommendation")
        self.stop_button = QPushButton("Stop session")
        for button in self.action_controls():
            button.setAccessibleName(button.text())
            actions.addWidget(button)
        controls.addLayout(actions)
        layout.addWidget(controls_panel)
        layout.addStretch()

        scroll.setWidget(content)
        root.addWidget(scroll)
        self.launch_button.clicked.connect(self.launch_requested)
        self.manual_button.clicked.connect(self.manual_run_requested)
        self.pause_button.clicked.connect(self.pause_requested)
        self.stop_button.clicked.connect(self.stop_requested)
        self.restart_button.clicked.connect(self.restart_requested)
        self.next_button.clicked.connect(self.next_requested)
        self.overlay_checkbox.toggled.connect(self.overlay_enabled_changed)

    def action_controls(self):
        return (
            self.launch_button,
            self.manual_button,
            self.pause_button,
            self.restart_button,
            self.next_button,
            self.stop_button,
        )

    def set_state(self, view_model):
        self._view_model = view_model
        self.title_label.setText(f"{view_model.title} · {view_model.mode.replace('_', ' ').title()}")
        self.status_label.setText(
            f"{view_model.status.title()} · {view_model.progress_text}"
        )
        self.evidence_label.setText(
            view_model.evidence.summary if view_model.evidence else "Source-backed routine order"
        )
        self.guide.set_guide(view_model.current_guide)
        self.overview.clear()
        for index, step in enumerate(view_model.steps, 1):
            marker = "✓" if step.completed else "•"
            item = QListWidgetItem(
                f"{marker} {index}. {step.scenario} — {step.run_text}"
            )
            self.overview.addItem(item)
        self.launch_button.setEnabled(view_model.can_launch)
        active = view_model.status in ("running", "paused")
        self.manual_button.setEnabled(active)
        self.pause_button.setEnabled(active)
        self.restart_button.setEnabled(active)
        self.stop_button.setEnabled(active)
        self.next_button.setEnabled(view_model.can_advance)

    def progress_text(self):
        return self._view_model.progress_text
