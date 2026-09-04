"""Reusable source-backed scenario guidance widget."""

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
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

        self.scenario_title = QLabel()
        self.scenario_title.setObjectName("sessionScenarioTitle")
        self.scenario_title.setWordWrap(True)
        layout.addWidget(self.scenario_title)

        self.purpose_label = self._section("Purpose", layout)
        self.setup_label = self._section("Setup", layout)
        self.steps_label = self._section("What to do", layout)
        self.success_label = self._section("Success criteria", layout)
        self.adjustment_label = self._section("Source adjustment", layout)

        self.run_progress = QProgressBar()
        self.run_progress.setAccessibleName("Scenario run progress")
        self.run_progress.setTextVisible(True)
        layout.addWidget(self.run_progress)

        self.source_link = QPushButton("Open source guidance")
        self.source_link.setAccessibleName("Open source guidance")
        self.source_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.source_link.clicked.connect(self._open_source)
        layout.addWidget(self.source_link, alignment=Qt.AlignmentFlag.AlignLeft)
        self._source_url = ""

    @staticmethod
    def _section(title, layout):
        label = QLabel()
        label.setWordWrap(True)
        label.setAccessibleName(title)
        layout.addWidget(label)
        return label

    def set_guide(self, view_model):
        self.scenario_title.setText(view_model.scenario)
        self.purpose_label.setText(f"Purpose\n{view_model.purpose}")
        self.setup_label.setText(f"Setup\n{view_model.setup}")
        numbered = "\n".join(
            f"{index}. {step}" for index, step in enumerate(view_model.steps, 1)
        )
        self.steps_label.setText(f"What to do\n{numbered}")
        self.success_label.setText(f"Success criteria\n{view_model.success}")
        if view_model.adjustment is None:
            self.adjustment_label.hide()
            self.adjustment_label.clear()
        else:
            self.adjustment_label.setText(
                f"Source adjustment\n{view_model.adjustment}"
            )
            self.adjustment_label.show()
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
