import json

from PyQt6.QtCore import QEvent, Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QComboBox, QFrame, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPushButton, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget,
)

from core.analyzer import build_profile
from core.notifications import NotificationManager
from core.kovaaks_launcher import open_kovaaks
from core.sync_worker import ScoreSyncWorker
from core.updater import (
    UpdateCheckWorker, UpdateDownloadWorker, automatic_updates_supported,
    is_newer_version, launch_installer,
)
from core.version import VERSION
from models.database import Database
from ui.aim_hub import AimHubWidget
from ui.dashboard import DashboardWidget
from ui.export import ExportWidget
from ui.import_widget import DragDropImport
from ui.progress import ProgressWidget
from ui.routines import RoutineWidget
from ui.scenarios import ScenarioBrowser
from ui.setup import SetupDialog
from ui.tools import ToolsWidget
from ui.skill_overview import SkillOverviewWidget


SCORE_MODES = {
    "Best": "best",
    "Latest": "latest",
    "Last 7 days": "recent_7",
    "Last 30 days": "recent_30",
    "All-time average": "average",
}

DIFFICULTIES = ["Novice", "Intermediate", "Advanced"]


class MainWindow(QMainWindow):
    """Application shell with task-based navigation and global score controls."""

    def __init__(self):
        super().__init__()
        QApplication.instance().installEventFilter(self)
        self.setWindowTitle(f"Aim Companion {VERSION} — Voltaic S5")
        self.setMinimumSize(1120, 760)

        self.db = Database()
        self._load_window_geometry()
        self._run_first_setup()
        self.score_mode = "best"
        self.difficulty = "Novice"
        self.profile = build_profile(
            self.db, difficulty=self.difficulty, score_mode=self.score_mode
        )
        self.training_profile = build_profile(
            self.db, difficulty=self.difficulty, score_mode="average"
        )
        self.rank_profile = build_profile(
            self.db, difficulty=self.difficulty, score_mode="best"
        )
        self.notifier = NotificationManager()
        self._update_checker = None
        self._update_downloader = None

        self._create_views()
        self._build_shell()

        streak = self.db.get_streak()
        streak_text = f"  •  {streak} day streak" if streak > 0 else ""
        self.statusBar().showMessage(
            f"{self.db.get_total_attempts()} total attempts{streak_text}"
        )
        self._check_new_pbs()
        self._sync_worker = None
        QTimer.singleShot(0, self._refresh_scores)
        QTimer.singleShot(5000, self._check_for_updates)

    def _create_views(self):
        self.dashboard = DashboardWidget(self.profile)
        self.dashboard.navigate_requested.connect(self._navigate)
        self.dashboard.quick_training_requested.connect(
            lambda: self._quick_scenario(False)
        )
        self.routine_view = RoutineWidget(
            self.training_profile, self.db, self.notifier,
            on_scores_updated=self._rebuild_profile,
        )
        self.routine_view.navigate_requested.connect(self._navigate)
        self.progress_view = ProgressWidget(self.profile, self.db)
        self.scenario_view = ScenarioBrowser(self.db)
        self.scenario_view.status_changed.connect(self.statusBar().showMessage)
        self.import_view = DragDropImport(self.db, on_import_complete=self._refresh_scores)
        self.export_view = ExportWidget(self.profile, self.db, on_restore=self._rebuild_profile)
        self.aim_hub_view = AimHubWidget(self.profile, self.db)
        self.aim_hub_view.train_requested.connect(self._start_training_method)
        self.tools_view = ToolsWidget(self.profile, self.db)
        self.skill_overview = SkillOverviewWidget(self.rank_profile, self.db)

        self.page_groups = [
            ("START", [
                ("dashboard", "Home", "Your current level and recommended next step", self.dashboard),
                ("routines", "Today", "Complete one focused 3–5 minute block whenever you feel fresh", self.routine_view),
            ]),
            ("LEARN", [
                ("aim_hub", "Training methods", "Choose a philosophy and set up its session", self.aim_hub_view),
                ("scenarios", "Scenario library", "Find official scenarios by skill", self.scenario_view),
            ]),
            ("REVIEW", [
                ("skills", "Skill matrix", "Ranks, confidence, maintenance, and benchmark checks", self.skill_overview),
                ("progress", "Progress", "Review benchmark history and improvement", self.progress_view),
                ("tools", "Training tools", "Sessions, calendar, comparisons, routines, and sensitivity", self.tools_view),
            ]),
            ("DATA", [
                ("import", "Import scores", "Add Kovaak's score files", self.import_view),
                ("export", "Backup data", "Export your benchmark history", self.export_view),
            ]),
        ]

    def eventFilter(self, obj, event):
        """Stop card styles from leaking onto QLabel, which subclasses QFrame in Qt."""
        if (
            obj is self
            and event.type() == QEvent.Type.WindowActivate
            and hasattr(self, "pages")
            and self.pages.currentWidget() is self.scenario_view
        ):
            self.scenario_view.refresh_installed()
        if event.type() == QEvent.Type.Polish and isinstance(obj, QLabel):
            if not obj.property("cleanTextSurface"):
                obj.setProperty("cleanTextSurface", True)
                own_style = obj.styleSheet()
                has_intentional_surface = any(
                    token in own_style.lower() for token in ("background", "border")
                )
                if obj.objectName() != "brandMark" and not has_intentional_surface:
                    obj.setStyleSheet(
                        own_style + "\nbackground: transparent; border: none;"
                    )
        return super().eventFilter(obj, event)

    def _build_shell(self):
        central = QWidget()
        central.setObjectName("appRoot")
        self.setCentralWidget(central)
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        shell.addWidget(self._create_sidebar())

        workspace = QWidget()
        workspace.setObjectName("workspace")
        workspace.setMaximumWidth(1500)
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(24, 18, 24, 18)
        workspace_layout.setSpacing(14)
        workspace_layout.addWidget(self._create_topbar())

        self.pages = QStackedWidget()
        self.pages.setObjectName("pageStack")
        self.page_indexes = {}
        for _, entries in self.page_groups:
            for key, _, _, widget in entries:
                self.page_indexes[key] = self.pages.addWidget(widget)
        self.pages.currentChanged.connect(self._on_page_changed)
        workspace_layout.addWidget(self.pages, 1)
        shell.addWidget(workspace, 1, Qt.AlignmentFlag.AlignHCenter)

        self._navigate("dashboard")

    def _create_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(216)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(8)

        brand_row = QHBoxLayout()
        mark = QLabel("A")
        mark.setObjectName("brandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(36, 36)
        brand_row.addWidget(mark)
        brand = QVBoxLayout()
        name = QLabel("AIM COMPANION")
        name.setObjectName("brandName")
        sub = QLabel(f"VOLTAIC S5 · v{VERSION}")
        sub.setObjectName("brandSub")
        brand.addWidget(name)
        brand.addWidget(sub)
        brand_row.addLayout(brand, 1)
        layout.addLayout(brand_row)

        self.sidebar_tier = QFrame()
        self.sidebar_tier.setObjectName("rankCard")
        tier_layout = QVBoxLayout(self.sidebar_tier)
        tier_layout.setContentsMargins(12, 10, 12, 10)
        tier_caption = QLabel("CURRENT RANK")
        tier_caption.setObjectName("eyebrow")
        self.tier_label = QLabel()
        self.tier_label.setObjectName("rankValue")
        self.energy_label = QLabel()
        self.energy_label.setObjectName("rankMeta")
        tier_layout.addWidget(tier_caption)
        tier_layout.addWidget(self.tier_label)
        tier_layout.addWidget(self.energy_label)
        layout.addWidget(self.sidebar_tier)
        self._update_tier_label()

        nav_scroll = QScrollArea()
        nav_scroll.setObjectName("navScroll")
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_content = QWidget()
        nav_layout = QVBoxLayout(nav_content)
        nav_layout.setContentsMargins(0, 4, 4, 4)
        nav_layout.setSpacing(3)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        for section, entries in self.page_groups:
            section_label = QLabel(section)
            section_label.setObjectName("navSection")
            nav_layout.addWidget(section_label)
            for key, label, description, _ in entries:
                button = QPushButton(label)
                button.setObjectName("navButton")
                button.setCheckable(True)
                button.setToolTip(description)
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(lambda checked=False, page=key: self._navigate(page))
                self.nav_group.addButton(button)
                self.nav_buttons[key] = button
                nav_layout.addWidget(button)
        nav_layout.addStretch()
        nav_scroll.setWidget(nav_content)
        layout.addWidget(nav_scroll, 1)
        return sidebar

    def _create_topbar(self):
        topbar = QFrame()
        topbar.setObjectName("topbar")
        layout = QHBoxLayout(topbar)
        layout.setContentsMargins(18, 12, 14, 12)
        layout.setSpacing(10)

        heading = QVBoxLayout()
        heading.setSpacing(1)
        self.page_title = QLabel("Home")
        self.page_title.setObjectName("pageTitle")
        self.page_subtitle = QLabel("Your rank, scores, and next focus")
        self.page_subtitle.setObjectName("pageSubtitle")
        heading.addWidget(self.page_title)
        heading.addWidget(self.page_subtitle)
        layout.addLayout(heading, 1)

        difficulty_block = QVBoxLayout()
        difficulty_block.setSpacing(2)
        difficulty_label = QLabel("BENCHMARK")
        difficulty_label.setObjectName("fieldLabel")
        self.difficulty_label = difficulty_label
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(DIFFICULTIES)
        self.difficulty_combo.setToolTip("Choose the Voltaic benchmark difficulty")
        self.difficulty_combo.currentTextChanged.connect(self._on_difficulty_changed)
        difficulty_block.addWidget(difficulty_label)
        difficulty_block.addWidget(self.difficulty_combo)
        layout.addLayout(difficulty_block)

        mode_block = QVBoxLayout()
        mode_block.setSpacing(2)
        mode_label = QLabel("SCORE VIEW")
        mode_label.setObjectName("fieldLabel")
        self.mode_label = mode_label
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(SCORE_MODES.keys())
        self.mode_combo.setToolTip("Lifetime Best shows your rank; recent modes show current form")
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        mode_block.addWidget(mode_label)
        mode_block.addWidget(self.mode_combo)
        layout.addLayout(mode_block)

        self.refresh_btn = QPushButton("Sync scores")
        self.refresh_btn.setObjectName("secondaryButton")
        self.refresh_btn.setToolTip("Scan Kovaak's score folder for new runs")
        self.refresh_btn.clicked.connect(self._refresh_scores)
        layout.addWidget(self.refresh_btn, 0, Qt.AlignmentFlag.AlignBottom)

        settings_btn = QPushButton("Settings")
        settings_btn.setObjectName("secondaryButton")
        settings_btn.clicked.connect(self._open_settings)
        layout.addWidget(settings_btn, 0, Qt.AlignmentFlag.AlignBottom)

        launch_btn = QPushButton("Open Kovaak's")
        launch_btn.setObjectName("primaryButton")
        launch_btn.clicked.connect(self._launch_kovaaks)
        layout.addWidget(launch_btn, 0, Qt.AlignmentFlag.AlignBottom)
        return topbar

    def _navigate(self, key):
        if key not in self.page_indexes:
            return
        self.pages.setCurrentIndex(self.page_indexes[key])
        self.nav_buttons[key].setChecked(True)
        for _, entries in self.page_groups:
            for page_key, title, description, _ in entries:
                if page_key == key:
                    self.page_title.setText(title)
                    self.page_subtitle.setText(description)
                    return

    def _quick_scenario(self, warmup=False):
        self._navigate("routines")
        self.routine_view._set_training_mode("focused")
        self.routine_view.show_quick_scenario(warmup)
        recommendation = self.routine_view._current_quick
        self.statusBar().showMessage(
            f"{'Warm-up' if warmup else 'Training'} pick · "
            f"{recommendation['scenario']} · {recommendation['runs']} "
            f"{'run' if recommendation['runs'] == 1 else 'runs'}"
        )

    def _start_training_method(self, method_id):
        self._navigate("routines")
        self.routine_view.select_training_method(method_id)
        self.statusBar().showMessage("Training method ready")

    def _update_tier_label(self):
        self.tier_label.setText(self.rank_profile.overall_tier)
        self.energy_label.setText(f"{self.rank_profile.overall_energy:.1f} energy")
        from models.benchmark import TIERS
        color = "#94a3b8"
        for tier in TIERS:
            if tier["name"] == self.rank_profile.overall_tier:
                color = tier["color"]
                break
        self.tier_label.setStyleSheet(f"color: {color};")

    def _on_mode_changed(self, display_name):
        self.score_mode = SCORE_MODES.get(display_name, "best")
        self._rebuild_profile()

    def _on_difficulty_changed(self, difficulty):
        self.difficulty = difficulty
        self._rebuild_profile()

    def _rebuild_profile(self):
        self.profile = build_profile(
            self.db, difficulty=self.difficulty, score_mode=self.score_mode
        )
        self.training_profile = build_profile(
            self.db, difficulty=self.difficulty, score_mode="average"
        )
        self.rank_profile = build_profile(
            self.db, difficulty=self.difficulty, score_mode="best"
        )
        self._update_tier_label()

        for view in (
            self.dashboard, self.progress_view,
            self.export_view, self.aim_hub_view, self.tools_view,
        ):
            view.update_profile(self.profile)
        self.routine_view.update_profile(self.training_profile)
        self.skill_overview.update_profile(self.rank_profile)

        streak = self.db.get_streak()
        streak_text = f"  •  {streak} day streak" if streak > 0 else ""
        self.statusBar().showMessage(
            f"{self.profile.overall_tier}  •  {self.profile.overall_energy:.1f} energy  •  "
            f"{self.difficulty_combo.currentText()}  •  {self.mode_combo.currentText()}{streak_text}"
        )

    def _refresh_scores(self):
        if self._sync_worker and self._sync_worker.isRunning():
            return
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Syncing…")
        self.statusBar().showMessage("Checking for new Kovaak's scores…")
        from models.config import TrainingConfig
        self._sync_worker = ScoreSyncWorker(
            self.db.db_path, TrainingConfig.load().get_stats_dir(), parent=self
        )
        self._sync_worker.completed.connect(self._on_sync_complete)
        self._sync_worker.failed.connect(self._on_sync_failed)
        self._sync_worker.start()

    def _on_sync_complete(self, imported):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Sync scores")
        self._rebuild_profile()
        self._check_new_pbs()
        self.statusBar().showMessage(
            f"Refresh complete  •  {imported} new scores  •  "
            f"{self.profile.overall_tier} at {self.profile.overall_energy:.1f} energy"
        )

    def _on_sync_failed(self, message):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Sync scores")
        self.statusBar().showMessage(f"Score sync failed: {message}")

    def _check_new_pbs(self):
        last_check = self.db.get_settings_value("last_pb_check") or "2000-01-01T00:00:00"
        new_pbs = self.db.get_new_pbs_since(last_check)
        self.db.set_settings_value(
            "last_pb_check", __import__("datetime").datetime.now().isoformat()
        )
        if new_pbs:
            pb_count = len({pb["benchmark_name"] for pb in new_pbs})
            self.statusBar().showMessage(
                self.statusBar().currentMessage() + f"  •  {pb_count} new personal bests!"
            )
            self.notifier.notify("New personal best!", f"You hit {pb_count} new personal best(s).")

    def _on_page_changed(self, index):
        is_today = self.pages.widget(index) is self.routine_view
        for widget in (
            self.difficulty_label, self.difficulty_combo,
            self.mode_label, self.mode_combo, self.refresh_btn,
        ):
            widget.setVisible(not is_today)
        if self.pages.widget(index) is self.scenario_view:
            self.scenario_view.refresh_installed()

    def _launch_kovaaks(self):
        launched = open_kovaaks()
        if launched:
            self.statusBar().showMessage("Opening Kovaak's through Steam…")
        else:
            QMessageBox.warning(
                self, "Could not open Steam",
                "The Steam URL could not be opened. Start Steam and launch Kovaak's "
                "from your Library instead.",
            )

    def _run_first_setup(self):
        if self.db.get_settings_value("onboarding_complete") == "1":
            return
        # First launch is zero-click: defaults and Steam libraries are detected
        # automatically. The Settings dialog remains available for overrides.
        self.db.set_settings_value("onboarding_complete", "1")

    def _open_settings(self):
        dialog = SetupDialog(self)
        if dialog.exec():
            self.db.set_settings_value("onboarding_complete", "1")
            self.routine_view.reload_config()
            self._check_for_updates()
            self.statusBar().showMessage("Settings saved")

    def _check_for_updates(self):
        if not automatic_updates_supported():
            return
        from models.config import TrainingConfig
        if not TrainingConfig.load().automatic_updates:
            return
        if self._update_checker and self._update_checker.isRunning():
            return
        self._update_checker = UpdateCheckWorker(self)
        self._update_checker.completed.connect(self._on_update_checked)
        self._update_checker.failed.connect(self._on_update_check_failed)
        self._update_checker.start()

    def _on_update_check_failed(self, message):
        self.statusBar().showMessage(
            f"Automatic update check failed: {message}", 15000
        )

    def _on_update_checked(self, release):
        if not is_newer_version(release["version"], VERSION):
            return
        answer = QMessageBox.question(
            self,
            "Aim Companion update available",
            f"Aim Companion {release['version']} is available.\n\n"
            f"You are using {VERSION}. Download and install the verified update now?\n\n"
            "Your scores, settings, and training history will be kept.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.statusBar().showMessage(
            f"Downloading Aim Companion {release['version']} update..."
        )
        self._update_downloader = UpdateDownloadWorker(release, self)
        self._update_downloader.completed.connect(self._install_downloaded_update)
        self._update_downloader.failed.connect(self._on_update_failed)
        self._update_downloader.start()

    def _install_downloaded_update(self, path):
        try:
            launch_installer(path)
        except Exception as error:
            self._on_update_failed(str(error))
            return
        self.statusBar().showMessage("Installing update and restarting Aim Companion...")
        QApplication.instance().quit()

    def _on_update_failed(self, message):
        QMessageBox.warning(
            self, "Update failed",
            f"Aim Companion could not install the update.\n\n{message}",
        )

    def _load_window_geometry(self):
        geo = self.db.get_settings_value("window_geometry")
        if geo:
            try:
                values = json.loads(geo)
                self.resize(values.get("width", 1280), values.get("height", 820))
                return
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
        self.resize(1280, 820)

    def _save_window_geometry(self):
        self.db.set_settings_value(
            "window_geometry",
            json.dumps({"width": self.width(), "height": self.height()}),
        )

    def closeEvent(self, event):
        self._save_window_geometry()
        if self._sync_worker and self._sync_worker.isRunning():
            self._sync_worker.wait(3000)
        for worker in (self._update_checker, self._update_downloader):
            if worker and worker.isRunning():
                worker.requestInterruption()
                worker.wait(22000)
        self.db.close()
        super().closeEvent(event)
