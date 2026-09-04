"""Persistent, expandable aggregate service-health indicator."""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


SEVERITY = {"ok": 0, "busy": 1, "offline": 2, "warning": 2, "error": 3}


class StatusIndicator(QWidget):
    details_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusIndicator")
        self._statuses = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        row = QHBoxLayout()
        self.state_label = QLabel("OK · Ready")
        self.state_label.setAccessibleName("System status")
        row.addWidget(self.state_label, 1)
        self.details_button = QPushButton("Details")
        self.details_button.setAccessibleName("Expand system status details")
        self.details_button.clicked.connect(self._toggle_details)
        row.addWidget(self.details_button)
        layout.addLayout(row)
        self.details_label = QLabel()
        self.details_label.setWordWrap(True)
        self.details_label.setAccessibleName("System status details")
        self.details_label.hide()
        layout.addWidget(self.details_label)

    def update_service(self, status):
        self._statuses[status.service] = status
        highest = self._highest()
        self.state_label.setText(f"{highest.state.upper()} · {highest.summary}")
        self.setAccessibleDescription(highest.details or highest.summary)
        self._render_details()

    def summary_text(self) -> str:
        return self._highest().summary if self._statuses else "Ready"

    def text(self) -> str:
        """Return the visible status wording for accessibility and smoke checks."""
        return self.state_label.text()

    def _highest(self):
        return max(
            self._statuses.values(),
            key=lambda item: (SEVERITY.get(item.state, 0), item.updated_at),
        )

    def _toggle_details(self):
        self.details_label.setVisible(self.details_label.isHidden())
        self.details_button.setText(
            "Hide details" if not self.details_label.isHidden() else "Details"
        )
        self.details_requested.emit()

    def _render_details(self):
        lines = []
        for status in sorted(
            self._statuses.values(),
            key=lambda item: (-SEVERITY.get(item.state, 0), item.service),
        ):
            timestamp = status.updated_at.astimezone().strftime("%H:%M:%S")
            line = f"{status.service.title()} · {status.state.upper()} · {timestamp}\n{status.details or status.summary}"
            if status.recovery_action:
                line += f"\nAction: {status.recovery_action}"
            lines.append(line)
        self.details_label.setText("\n\n".join(lines))
