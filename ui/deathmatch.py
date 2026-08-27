import json
from datetime import datetime

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QVBoxLayout, QWidget,
)

from core.recommender import DEATHMATCH_GUIDE


class DeathmatchProgressWidget(QWidget):
    """Reusable daily deathmatch checklist and coaching surface."""

    SETTINGS_KEY = "deathmatch_daily_v1"

    def __init__(self, db, show_summary=True, show_source=True, parent=None):
        super().__init__(parent)
        self.db = db
        self.show_summary = show_summary
        self.show_source = show_source
        self.controls = {}
        self._build_ui()
        self.refresh()

    @staticmethod
    def _today():
        return datetime.now().date().isoformat()

    def _load_state(self):
        empty = {"date": self._today(), "counts": {}}
        if not self.db:
            return empty
        raw = self.db.get_settings_value(self.SETTINGS_KEY)
        if not raw:
            return empty
        try:
            state = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return empty
        if state.get("date") != empty["date"] or not isinstance(
            state.get("counts"), dict
        ):
            return empty
        return state

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        if self.show_summary:
            summary = QLabel(DEATHMATCH_GUIDE["summary"])
            summary.setObjectName("modeSummary")
            summary.setWordWrap(True)
            layout.addWidget(summary)

        for block in DEATHMATCH_GUIDE["blocks"]:
            row = QHBoxLayout()
            copy = QLabel(f"{block['title']}  |  {block['weapon']}")
            copy.setWordWrap(True)
            copy.setObjectName("mutedText")
            row.addWidget(copy, 1)
            if block["matches"] == 1:
                control = QCheckBox("Done")
                control.toggled.connect(self._save_progress)
            else:
                control = QSpinBox()
                control.setRange(0, block["matches"])
                control.setSuffix(f" / {block['matches']}")
                control.valueChanged.connect(self._save_progress)
            self.controls[block["id"]] = control
            row.addWidget(control)
            layout.addLayout(row)

        self.progress_label = QLabel()
        self.progress_label.setObjectName("modeProgress")
        layout.addWidget(self.progress_label)
        self.block_combo = QComboBox()
        for block in DEATHMATCH_GUIDE["blocks"]:
            self.block_combo.addItem(block["title"], block)
        self.block_combo.currentIndexChanged.connect(self._update_details)
        layout.addWidget(self.block_combo)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setObjectName("mutedText")
        layout.addWidget(self.details)
        self._update_details()

        actions = QHBoxLayout()
        reset = QPushButton("Reset today")
        reset.setObjectName("quietButton")
        reset.clicked.connect(self.reset)
        actions.addWidget(reset)
        if self.show_source:
            source = QPushButton("Open original routine")
            source.setObjectName("quietButton")
            source.clicked.connect(
                lambda: QDesktopServices.openUrl(
                    QUrl(DEATHMATCH_GUIDE["source_url"])
                )
            )
            actions.addWidget(source)
        actions.addStretch()
        layout.addLayout(actions)

        guidance = QLabel(
            DEATHMATCH_GUIDE["progression"] + " "
            + DEATHMATCH_GUIDE["review_rule"]
        )
        guidance.setWordWrap(True)
        guidance.setObjectName("modeGuidance")
        layout.addWidget(guidance)

    @staticmethod
    def _completed(control):
        if isinstance(control, QCheckBox):
            return 1 if control.isChecked() else 0
        return control.value()

    def _counts(self):
        return {
            block_id: self._completed(control)
            for block_id, control in self.controls.items()
        }

    def _update_progress_label(self):
        total = sum(block["matches"] for block in DEATHMATCH_GUIDE["blocks"])
        completed = sum(self._counts().values())
        self.progress_label.setText(
            f"Today: {completed} of {total} focused deathmatches complete"
        )

    def _save_progress(self, *args):
        self._update_progress_label()
        if self.db:
            self.db.set_settings_value(self.SETTINGS_KEY, json.dumps({
                "date": self._today(),
                "counts": self._counts(),
            }))

    def refresh(self):
        state = self._load_state()
        for block in DEATHMATCH_GUIDE["blocks"]:
            control = self.controls[block["id"]]
            value = min(
                block["matches"],
                max(0, int(state["counts"].get(block["id"], 0))),
            )
            control.blockSignals(True)
            if isinstance(control, QCheckBox):
                control.setChecked(bool(value))
            else:
                control.setValue(value)
            control.blockSignals(False)
        self._update_progress_label()

    def reset(self):
        for control in self.controls.values():
            control.blockSignals(True)
            if isinstance(control, QCheckBox):
                control.setChecked(False)
            else:
                control.setValue(0)
            control.blockSignals(False)
        self._save_progress()

    def _update_details(self):
        block = self.block_combo.currentData()
        if not block:
            return
        rules = "\n".join("- " + rule for rule in block["rules"])
        self.details.setText(f"Goal: {block['goal']}\n{rules}")

    def showEvent(self, event):
        self.refresh()
        super().showEvent(event)
