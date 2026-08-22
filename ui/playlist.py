import json
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QFrame, QScrollArea, QListWidget,
    QListWidgetItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from models.database import Database
from core.recommender import SCENARIOS, get_installed_scenarios
from core.playlist_export import export_playlist


class PlaylistExport(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.playlist = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Playlist Export")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        subtitle = QLabel("Build and export playlists to Kovaak's format")
        subtitle.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(subtitle)

        controls = QHBoxLayout()
        self.name_input = QLabel("Playlist Name:")
        self.name_input.setStyleSheet("color: #ccc;")
        controls.addWidget(self.name_input)

        add_btn = QPushButton("Add Installed Scenarios")
        add_btn.setStyleSheet(
            "QPushButton { background-color: #4a9eff; color: white; border-radius: 4px; padding: 8px; }"
            "QPushButton:hover { background-color: #3a8eef; }"
        )
        add_btn.clicked.connect(self._add_installed)
        controls.addWidget(add_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self._clear)
        controls.addWidget(clear_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.playlist_list = QListWidget()
        self.playlist_list.setStyleSheet(
            "QListWidget { background-color: #1a1a2a; color: white; border-radius: 4px; border: 1px solid #333; }"
            "QListWidget::item { padding: 4px 8px; }"
        )
        layout.addWidget(self.playlist_list, stretch=1)

        export_row = QHBoxLayout()
        self.export_path = QLabel("Path: Auto-detect Kovaak's folder")
        self.export_path.setStyleSheet("color: #888;")
        export_row.addWidget(self.export_path)

        export_btn = QPushButton("Export to Kovaak's")
        export_btn.setStyleSheet(
            "QPushButton { background-color: #44ff88; color: #111; border-radius: 4px; padding: 10px 16px; font-weight: bold; }"
            "QPushButton:hover { background-color: #33ee77; }"
        )
        export_btn.clicked.connect(self._export)
        export_row.addWidget(export_btn)
        layout.addLayout(export_row)

    def _add_installed(self):
        installed = get_installed_scenarios()
        for s in installed:
            name = s["name"]
            if name not in [e["name"] for e in self.playlist]:
                self.playlist.append({"name": name, "count": 1})
                self.playlist_list.addItem(name)

    def _clear(self):
        self.playlist.clear()
        self.playlist_list.clear()

    def _export(self):
        if not self.playlist:
            QMessageBox.warning(self, "Error", "Add scenarios to the playlist first")
            return

        path = export_playlist(self.playlist)
        if path:
            QMessageBox.information(self, "Exported", f"Playlist exported to:\n{path}")
        else:
            QMessageBox.warning(self, "Error", "Could not find Kovaak's folder")

    def update_profile(self, profile):
        pass
