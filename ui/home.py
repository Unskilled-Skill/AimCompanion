"""Conclusion-first Home destination."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class HomeWidget(QWidget):
    start_warmup = pyqtSignal()
    start_step_by_step = pyqtSignal()
    start_full_routine = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        conclusion = QFrame()
        conclusion.setObjectName("panel")
        conclusion_layout = QVBoxLayout(conclusion)
        self.headline_label = QLabel("Choose how you want to train")
        self.headline_label.setObjectName("sectionTitle")
        self.headline_label.setWordWrap(True)
        self.rank_label = QLabel()
        self.next_rank_label = QLabel()
        self.weakness_label = QLabel()
        self.trend_label = QLabel()
        self.confidence_label = QLabel()
        for label in (
            self.rank_label, self.next_rank_label, self.weakness_label,
            self.trend_label, self.confidence_label,
        ):
            label.setWordWrap(True)
        self.evidence_label = QLabel()
        self.evidence_label.setWordWrap(True)
        self.evidence_label.setAccessibleName("Recommendation evidence")
        conclusion_layout.addWidget(self.headline_label)
        conclusion_layout.addWidget(self.rank_label)
        conclusion_layout.addWidget(self.next_rank_label)
        conclusion_layout.addWidget(self.weakness_label)
        conclusion_layout.addWidget(self.trend_label)
        conclusion_layout.addWidget(self.confidence_label)
        conclusion_layout.addWidget(self.evidence_label)
        layout.addWidget(conclusion)

        self.action_panel = QFrame()
        self.action_panel.setObjectName("primaryActionPanel")
        actions = QHBoxLayout(self.action_panel)
        self.warmup_button = QPushButton("Warm-up")
        self.step_button = QPushButton("Step-by-Step Training")
        self.full_button = QPushButton("Full Routine")
        self.primary_actions = (
            self.warmup_button, self.step_button, self.full_button,
        )
        for button in self.primary_actions:
            button.setObjectName("primaryTrainingAction")
            button.setMinimumHeight(56)
            button.setAccessibleName(button.text())
            actions.addWidget(button)
        self.warmup_button.clicked.connect(self.start_warmup)
        self.step_button.clicked.connect(self.start_step_by_step)
        self.full_button.clicked.connect(self.start_full_routine)
        layout.addWidget(self.action_panel)

        self.recent_progress = QFrame()
        self.recent_progress.setObjectName("panel")
        recent_layout = QVBoxLayout(self.recent_progress)
        recent_layout.addWidget(QLabel("Recent progress"))
        self.recent_label = QLabel("No completed sessions yet")
        self.recent_label.setWordWrap(True)
        recent_layout.addWidget(self.recent_label)
        layout.addWidget(self.recent_progress)
        layout.addStretch()

    def set_view_model(self, view_model):
        self.headline_label.setText(view_model.headline)
        self.rank_label.setText(view_model.rank_text)
        self.next_rank_label.setText(view_model.next_rank_text)
        self.weakness_label.setText(
            f"Primary weakness: {view_model.weakness_text}"
            if view_model.weakness_text else ""
        )
        self.trend_label.setText(view_model.trend_text)
        self.confidence_label.setText(view_model.confidence_text)
        self.evidence_label.setText(view_model.evidence_text)
        self.recent_label.setText(
            "\n".join(view_model.recent_progress)
            if view_model.recent_progress else "No completed sessions yet"
        )
