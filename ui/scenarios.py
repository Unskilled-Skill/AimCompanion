from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QScrollArea, QFrame, QPushButton, QGridLayout,
    QCheckBox, QMessageBox,
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont

from models.database import Database
from models.config import TrainingConfig
from core.kovaaks_launcher import open_kovaaks, open_kovaaks_scenario
from core.playlist_export import export_playlist
from core.recommender import (
    get_installed_scenario_names, get_scenario_description, SCENARIOS,
)
from core.scenario_files import scenario_key


class ScenarioBrowser(QWidget):
    status_changed = pyqtSignal(str)

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.all_scenarios = [
            scenario for scenario in SCENARIOS
            if scenario.get("official_recommended")
        ]
        self.installed = set()
        self.refresh_installed(populate=False)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pack_row = QHBoxLayout()
        pack_copy = QVBoxLayout()
        pack_title = QLabel("Recommended scenario pack")
        pack_title.setObjectName("smallTitle")
        self.pack_status = QLabel()
        self.pack_status.setObjectName("mutedText")
        pack_copy.addWidget(pack_title)
        pack_copy.addWidget(self.pack_status)
        pack_row.addLayout(pack_copy, 1)
        self.download_all_btn = QPushButton()
        self.download_all_btn.setObjectName("primaryButton")
        self.download_all_btn.clicked.connect(self._download_recommended_pack)
        pack_row.addWidget(self.download_all_btn)
        layout.addLayout(pack_row)

        search_row = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search scenarios...")
        self.search_input.textChanged.connect(self._filter)
        search_row.addWidget(self.search_input)

        self.category_filter = QComboBox()
        self.category_filter.addItems(["All", "Clicking", "Tracking", "Switching"])
        self.category_filter.currentTextChanged.connect(self._filter)
        search_row.addWidget(self.category_filter)

        self.subcat_filter = QComboBox()
        self.subcat_filter.addItems([
            "All", "Static", "Dynamic", "Linear",
            "Control", "Precise", "Reactive",
            "Speed", "Evasive", "Stability"
        ])
        self.subcat_filter.currentTextChanged.connect(self._filter)
        search_row.addWidget(self.subcat_filter)

        self.diff_filter = QComboBox()
        self.diff_filter.addItems(["All", "Novice", "Intermediate", "Advanced", "Unknown"])
        self.diff_filter.currentTextChanged.connect(self._filter)
        search_row.addWidget(self.diff_filter)

        self.installed_only = QCheckBox("Installed")
        self.installed_only.stateChanged.connect(self._filter)
        search_row.addWidget(self.installed_only)

        self.fav_only = QCheckBox("Favorites")
        self.fav_only.stateChanged.connect(self._filter)
        search_row.addWidget(self.fav_only)

        layout.addLayout(search_row)

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: #888;")
        layout.addWidget(self.count_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QGridLayout(self.scroll_content)
        self.scroll_layout.setSpacing(6)
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll, stretch=1)

        self._filter()

    def refresh_installed(self, populate=True):
        self.installed = {
            scenario_key(name) for name in get_installed_scenario_names()
        }
        if populate and hasattr(self, "search_input"):
            self._filter()

    def _missing_scenarios(self):
        return [
            scenario for scenario in self.all_scenarios
            if scenario_key(scenario["name"]) not in self.installed
        ]

    def _update_pack_status(self):
        missing = len(self._missing_scenarios())
        total = len(self.all_scenarios)
        installed = total - missing
        self.pack_status.setText(
            f"{installed} of {total} recommended scenarios available locally"
        )
        self.download_all_btn.setText(
            f"Download all missing ({missing})" if missing else "Pack installed"
        )
        self.download_all_btn.setEnabled(missing > 0)

    def _download_recommended_pack(self):
        missing = self._missing_scenarios()
        if not missing:
            return
        try:
            path = export_playlist(
                missing, name="Aim Companion Recommended Scenarios",
                output_dir=TrainingConfig.load().get_playlists_dir(),
            )
        except OSError as error:
            QMessageBox.critical(
                self, "Could not create scenario pack", str(error)
            )
            return

        launched = open_kovaaks()
        self.status_changed.emit(
            f"Created download playlist with {len(missing)} missing scenarios"
        )
        message = QMessageBox(self)
        message.setWindowTitle("Scenario pack ready")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText(
            f"Created a playlist with {len(missing)} missing recommended scenarios."
        )
        message.setInformativeText(
            "Open Local Playlists in Kovaak's and select "
            "'Aim Companion Recommended Scenarios'. Current Kovaak's versions "
            "automatically download missing playlist scenarios. The app will "
            "refresh their installed status when you return."
            + ("" if launched else " Open Kovaak's manually to continue.")
        )
        message.setDetailedText(f"Playlist file: {path}")
        message.exec()

    def _play_scenario(self, name):
        if open_kovaaks_scenario(name):
            self.status_changed.emit(
                f"Opening {name}; Kovaak's will download it if needed"
            )
        else:
            QMessageBox.warning(
                self, "Could not open Kovaak's",
                "Open Kovaak's through Steam and search for the scenario name.",
            )

    def _filter(self):
        text = self.search_input.text().lower()
        cat = self.category_filter.currentText()
        subcat = self.subcat_filter.currentText()
        diff = self.diff_filter.currentText()
        inst_only = self.installed_only.isChecked()
        fav_only = self.fav_only.isChecked()
        favs = {f["item_name"] for f in self.db.get_favorites("scenario")}

        results = []
        for s in self.all_scenarios:
            name = s.get("name", "")
            if text and text not in name.lower():
                continue
            if cat != "All" and s.get("category", "") != cat:
                continue
            if subcat != "All" and s.get("subcategory", "") != subcat:
                continue
            if diff != "All" and s.get("difficulty", "") != diff:
                continue
            if inst_only and scenario_key(name) not in self.installed:
                continue
            if fav_only and name not in favs:
                continue
            results.append(s)

        self.count_label.setText(f"{len(results)} official scenarios")
        self._update_pack_status()
        self._populate(results, favs)

    def _populate(self, scenarios, favs):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        cols = 2
        for i, s in enumerate(scenarios):
            row, col = divmod(i, cols)
            card = self._card(s, favs)
            self.scroll_layout.addWidget(card, row, col)

    def _card(self, s, favs):
        name = s.get("name", "Unknown")
        cat = s.get("category", "")
        subcat = s.get("subcategory", "")
        diff = s.get("difficulty", "")
        inst = scenario_key(name) in self.installed
        is_fav = name in favs
        has_info = s.get("instructions") or s.get("technique")
        has_routine = s.get("routine")

        border = "#263149"
        if inst and is_fav:
            border = "#ff9944"
        elif inst:
            border = "#44ff88"
        elif is_fav:
            border = "#ff9944"

        frame = QFrame()
        frame.setObjectName("scenarioCard")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(f"""
            QFrame#scenarioCard {{
                background-color: #11192b;
                border-radius: 9px;
                border-left: 3px solid {border};
                padding: 8px;
            }}
        """)

        layout = QVBoxLayout(frame)
        layout.setSpacing(3)
        layout.setContentsMargins(8, 6, 8, 6)

        name_lbl = QLabel(name)
        name_lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: white;")
        name_lbl.setWordWrap(True)
        layout.addWidget(name_lbl)

        meta = QLabel(f"{cat} / {subcat} / {diff}")
        meta.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(meta)

        description = QLabel(get_scenario_description(s))
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        layout.addWidget(description)

        tags_row = QHBoxLayout()
        if inst:
            tags_row.addWidget(self._tag("INSTALLED", "#44ff88"))
        if is_fav:
            tags_row.addWidget(self._tag("FAV", "#ff9944"))
        if has_info:
            tags_row.addWidget(self._tag("INFO", "#4a9eff"))
        if has_routine:
            tags_row.addWidget(self._tag("ROUTINE", "#bb88ff"))
        tags_row.addStretch()
        play = QPushButton("Play" if inst else "Download & play")
        play.setObjectName("quietButton")
        play.setToolTip(
            "Open this scenario through its official Steam URI. "
            "Kovaak's downloads it automatically when needed."
        )
        play.clicked.connect(
            lambda checked=False, scenario=name: self._play_scenario(scenario)
        )
        tags_row.addWidget(play)
        layout.addLayout(tags_row)

        return frame

    def _tag(self, text, color):
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {color};")
        return lbl
