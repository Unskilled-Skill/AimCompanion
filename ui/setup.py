import os

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QVBoxLayout,
)

from core.recommender import get_game_options
from models.config import TrainingConfig


class SetupDialog(QDialog):
    """First-run and reusable application settings dialog."""

    def __init__(self, parent=None, first_run=False):
        super().__init__(parent)
        self.first_run = first_run
        self.config = TrainingConfig.load()
        self.setWindowTitle("Aim Companion preferences")
        self.setMinimumWidth(700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(16)
        title = QLabel("Preferences")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        description = QLabel(
            "Aim Companion detects Kovaak's and chooses safe defaults automatically. "
            "Change something here only when you want an override."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        self.install_path = QLineEdit(self.config.kovaaks_install_dir)
        self.install_path.setPlaceholderText("Auto-detect, or choose the FPSAimTrainer folder")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.install_path, 1)
        path_row.addWidget(browse)
        form.addRow("Kovaak's folder", path_row)

        detected = self.config.get_stats_dir()
        self.stats_status = QLabel(
            f"Score sync: {detected}" if os.path.isdir(detected)
            else "Score sync folder was not detected yet"
        )
        self.stats_status.setObjectName("mutedText")
        self.stats_status.setWordWrap(True)
        form.addRow("Detection", self.stats_status)

        self.profile_url = QLineEdit(self.config.voltaic_profile_url)
        self.profile_url.setPlaceholderText("https://app.voltaic.gg/your-profile (optional)")
        form.addRow("Voltaic profile", self.profile_url)

        self.game = QComboBox()
        self.game.setMaximumWidth(360)
        self.game.addItems(get_game_options())
        if self.config.game in get_game_options():
            self.game.setCurrentText(self.config.game)
        form.addRow("Training context", self.game)

        self.minutes = QSpinBox()
        self.minutes.setRange(15, 120)
        self.minutes.setSuffix(" min")
        self.minutes.setValue(self.config.session_minutes)
        self.minutes.setMaximumWidth(160)
        form.addRow("Default session", self.minutes)

        self.prefer_installed = QCheckBox("Prefer installed scenarios when fit is equal")
        self.prefer_installed.setChecked(self.config.prioritize_installed)
        form.addRow("Scenario choice", self.prefer_installed)

        self.avoid_turns = QCheckBox("Avoid continuous-turn scenarios")
        self.avoid_turns.setChecked(self.config.avoid_continuous_turns)
        form.addRow("Low sensitivity", self.avoid_turns)

        self.automatic_updates = QCheckBox(
            "Automatically check GitHub for verified Aim Companion updates"
        )
        self.automatic_updates.setChecked(self.config.automatic_updates)
        self.automatic_updates.setToolTip(
            "Checks the public release version on startup. Updates are installed only after confirmation."
        )
        form.addRow("Updates", self.automatic_updates)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "Choose FPSAimTrainer folder", self.install_path.text()
        )
        if path:
            self.install_path.setText(path)

    def _save(self):
        install_path = self.install_path.text().strip()
        if install_path and not os.path.isdir(install_path):
            QMessageBox.warning(self, "Folder not found", "Choose an existing folder or leave it blank for auto-detection.")
            return
        profile_url = self.profile_url.text().strip()
        if profile_url and not profile_url.startswith(("https://app.voltaic.gg/", "http://app.voltaic.gg/")):
            QMessageBox.warning(self, "Invalid profile", "Enter a Voltaic profile URL or leave it blank.")
            return

        self.config.kovaaks_install_dir = install_path
        self.config.voltaic_profile_url = profile_url
        self.config.game = self.game.currentText()
        if self.first_run:
            self.config.warmup_context = (
                "Aim training" if self.config.game == "General / Fundamentals"
                else self.config.game
            )
        self.config.session_minutes = self.minutes.value()
        self.config.prioritize_installed = self.prefer_installed.isChecked()
        self.config.avoid_continuous_turns = self.avoid_turns.isChecked()
        self.config.automatic_updates = self.automatic_updates.isChecked()
        self.config.save()
        self.accept()
