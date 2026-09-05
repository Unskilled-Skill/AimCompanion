"""Reusable source-backed scenario guidance widget."""

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ScenarioGuideWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scenario_title = QLabel()
        self.scenario_title.setObjectName("sessionScenarioTitle")
        self.scenario_title.setWordWrap(True)
        layout.addWidget(self.scenario_title)

        details = QGridLayout()
        details.setSpacing(10)
        purpose_card, self.purpose_label = self._section("Purpose")
        setup_card, self.setup_label = self._section("Setup")
        steps_card, self.steps_label = self._section("What to do")
        success_card, self.success_label = self._section("Success criteria")
        self.adjustment_card, self.adjustment_label = self._section("Source adjustment")
        details.addWidget(purpose_card, 0, 0)
        details.addWidget(setup_card, 0, 1)
        details.addWidget(steps_card, 1, 0, 1, 2)
        details.addWidget(success_card, 2, 0, 1, 2)
        details.addWidget(self.adjustment_card, 3, 0, 1, 2)
        details.setColumnStretch(0, 1)
        details.setColumnStretch(1, 1)
        layout.addLayout(details)

        progress_label = QLabel("RUN PROGRESS")
        progress_label.setObjectName("sessionEyebrow")
        layout.addWidget(progress_label)
        self.run_progress = QProgressBar()
        self.run_progress.setObjectName("sessionRunProgress")
        self.run_progress.setAccessibleName("Scenario run progress")
        self.run_progress.setTextVisible(True)
        layout.addWidget(self.run_progress)

        self.source_link = QPushButton("Open source guidance")
        self.source_link.setObjectName("sessionSourceButton")
        self.source_link.setAccessibleName("Open source guidance")
        self.source_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.source_link.clicked.connect(self._open_source)
        layout.addWidget(self.source_link, alignment=Qt.AlignmentFlag.AlignLeft)
        self._source_url = ""

    @staticmethod
    def _section(title):
        card = QFrame()
        card.setObjectName("sessionGuideSection")
        section_layout = QVBoxLayout(card)
        section_layout.setContentsMargins(13, 11, 13, 12)
        section_layout.setSpacing(5)
        heading = QLabel(title.upper())
        heading.setObjectName("sessionGuideSectionTitle")
        label = QLabel()
        label.setObjectName("sessionGuideSectionBody")
        label.setWordWrap(True)
        label.setAccessibleName(title)
        section_layout.addWidget(heading)
        section_layout.addWidget(label)
        return card, label

    def set_guide(self, view_model):
        self.scenario_title.setText(view_model.scenario)
        self.purpose_label.setText(view_model.purpose)
        self.setup_label.setText(view_model.setup)
        self.steps_label.setText("\n".join(
            f"{index}. {step}" for index, step in enumerate(view_model.steps, 1)
        ))
        self.success_label.setText(view_model.success)
        if view_model.adjustment is None:
            self.adjustment_card.hide()
            self.adjustment_label.hide()
            self.adjustment_label.clear()
        else:
            self.adjustment_label.setText(view_model.adjustment)
            self.adjustment_label.show()
            self.adjustment_card.show()
        self.run_progress.setRange(0, view_model.required_runs)
        self.run_progress.setValue(view_model.completed_runs)
        self.run_progress.setFormat(
            f"{view_model.completed_runs} / {view_model.required_runs} runs"
        )
        self._source_url = view_model.source_url
        self.source_link.setText(
            f"Source: {view_model.source}" if view_model.source else "Source unavailable"
        )
        self.source_link.setEnabled(bool(view_model.source_url))

    def _open_source(self):
        if self._source_url:
            QDesktopServices.openUrl(QUrl(self._source_url))
