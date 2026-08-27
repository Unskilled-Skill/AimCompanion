import json
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QSpinBox, QCheckBox,
    QMessageBox, QComboBox, QApplication, QSizePolicy, QAbstractSpinBox,
    QProgressBar, QMenu, QToolButton, QLineEdit, QButtonGroup,
)
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QAction, QDesktopServices, QFont

from models.score import PlayerProfile
from models.config import TrainingConfig, FOCUS_OPTIONS, _detect_kovaaks_playlists
from core.recommender import (
    GUIDANCE, ROUTINES, generate_routine, get_game_options,
    get_routine_description,
    get_training_guidance, generate_quick_scenario,
)
from core.kovaaks_launcher import open_kovaaks, open_kovaaks_scenario
from core.playlist_export import export_playlist
from core.scenario_duration import quick_block_plan
from core.scenario_files import find_scenario_file
from core.run_tracker import KovaaksRunTracker
from core.parser import import_all_scores
from core.warmups import get_warmup_routine, warmup_minutes
from core.training_intelligence import (
    build_adaptive_schedule, build_scenario_signals, build_skill_intelligence,
    build_weekly_plan, detect_fatigue,
)
from core.training_methods import METHOD_MAP, methods_for_mode
from ui.deathmatch import DeathmatchProgressWidget

KOVAAKS_PLAYLIST_DIR = _detect_kovaaks_playlists()

REVIEW_ISSUES = (
    ("No recurring error", ""),
    ("Overflicking", "overflicking"),
    ("Curved or jagged path", "curved_path"),
    ("Shaky or tense", "shaky_tense"),
    ("Repeated overcorrection", "overcorrecting"),
    ("Predicting movement", "predicting"),
    ("Inefficient target choice", "target_selection"),
)

SKILL_OPTIONS = tuple(
    (category, subcategory)
    for category, subcategories in (
        ("Clicking", ("Static", "Dynamic", "Linear")),
        ("Tracking", ("Precise", "Reactive", "Control")),
        ("Switching", ("Speed", "Evasive", "Stability")),
    )
    for subcategory in subcategories
)


def prepare_scenario_launch(recommendation, scenario_dirs, stats_dir):
    """Enrich launch timing without requiring online scenarios to exist locally."""
    scenario_path = find_scenario_file(recommendation["scenario"], scenario_dirs)
    recommendation.update(quick_block_plan(
        recommendation["scenario"], scenario_dirs, stats_dir,
    ))
    recommendation["installed"] = bool(scenario_path)
    return scenario_path


class RoutineWidget(QWidget):
    navigate_requested = pyqtSignal(str)

    def __init__(
        self, profile: PlayerProfile, db=None, notifier=None,
        on_scores_updated=None,
    ):
        super().__init__()
        self.profile = profile
        self.db = db
        self.notifier = notifier
        self.on_scores_updated = on_scores_updated
        self.config = TrainingConfig.load()
        self._current_routine = None
        self._current_quick = None
        self._quick_session_completed = False
        self._quick_session_stopped = False
        self._benchmark_scores_pending = False
        self._challenge_notice_shown_this_session = False
        self._run_tracker = KovaaksRunTracker(
            self.config.get_stats_dir()
        )
        self._run_poll_timer = QTimer(self)
        self._run_poll_timer.setInterval(1500)
        self._run_poll_timer.timeout.connect(self._poll_quick_session)
        self._pending_install = None
        self._install_poll_timer = QTimer(self)
        self._install_poll_timer.setInterval(1200)
        self._install_poll_timer.timeout.connect(self._poll_scenario_install)
        self._sync_health_timer = QTimer(self)
        self._sync_health_timer.setInterval(5000)
        self._sync_health_timer.timeout.connect(self._update_sync_health)
        self._daily_state = self._load_daily_state()
        training_blocks = [
            block for block in self._daily_state["blocks"] if not block.get("warmup")
        ]
        warmup_blocks = [
            block for block in self._daily_state["blocks"] if block.get("warmup")
        ]
        self._quick_history = [block["scenario"] for block in training_blocks]
        self._warmup_history = [block["scenario"] for block in warmup_blocks]
        self._quick_rotation = len(training_blocks)
        self._warmup_rotation = len(warmup_blocks)
        self._build_ui()
        self._sync_health_timer.start()

    @staticmethod
    def _today_key():
        return datetime.now().date().isoformat()

    def _load_daily_state(self):
        empty = {"date": self._today_key(), "blocks": []}
        if not self.db:
            return empty
        raw = self.db.get_settings_value("quick_training_daily")
        if not raw:
            return empty
        try:
            state = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return empty
        if state.get("date") != self._today_key() or not isinstance(state.get("blocks"), list):
            return empty
        return state

    def _save_daily_state(self):
        if self.db:
            self.db.set_settings_value(
                "quick_training_daily", json.dumps(self._daily_state)
            )

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        self.content_layout = QVBoxLayout(scroll_content)

        self._build_mode_selector()
        self._build_deathmatch_mode()
        self._build_settings()
        self._build_routine_display()
        self._build_quick_actions()
        self._build_weekly_plan()
        self._build_game_review()
        self._build_share_codes()

        # Today always opens from a neutral recommendation. Authored routines
        # such as hnA must be an explicit choice for the current session.
        configured_mode = "focused"
        self.config.training_mode = configured_mode
        self.config.training_method = "adaptive_weakness"
        self.config.preferred_routine = ""
        self.mode_buttons[configured_mode].setChecked(True)
        self._set_training_mode(configured_mode, persist=False)

        # Select a useful block immediately, but never launch Kovaak's merely
        # because the user opened Today.
        self.show_quick_scenario(False, launch=False)

        self.content_layout.addStretch()
        self.scroll.setWidget(scroll_content)
        layout.addWidget(self.scroll)

    def _build_mode_selector(self):
        frame = QFrame()
        frame.setObjectName("trainingModes")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(4)
        label = QLabel("TRAINING MODE")
        label.setObjectName("fieldLabel")
        mode_row.addWidget(label)
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_buttons = {}
        for key, text in (
            ("focused", "Focused block"),
            ("routine", "Full routine"),
            ("deathmatch", "Deathmatch"),
        ):
            button = QPushButton(text)
            button.setObjectName("modeButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, value=key: self._set_training_mode(value)
            )
            self.mode_group.addButton(button)
            self.mode_buttons[key] = button
            mode_row.addWidget(button)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        method_row = QHBoxLayout()
        method_row.setSpacing(10)
        method_label = QLabel("TRAINING PHILOSOPHY")
        method_label.setObjectName("fieldLabel")
        method_row.addWidget(method_label)
        self.method_combo = QComboBox()
        self.method_combo.setMinimumWidth(250)
        self.method_combo.currentIndexChanged.connect(self._method_changed)
        method_row.addWidget(self.method_combo, 1)
        self.method_duration = QSpinBox()
        self.method_duration.setRange(15, 120)
        self.method_duration.setSuffix(" min")
        self.method_duration.setValue(self.config.session_minutes)
        method_row.addWidget(self.method_duration)
        self.start_method_button = QPushButton()
        self.start_method_button.setObjectName("primaryButton")
        self.start_method_button.clicked.connect(self._start_selected_method)
        method_row.addWidget(self.start_method_button)
        layout.addLayout(method_row)

        detail_row = QHBoxLayout()
        self.method_description = QLabel()
        self.method_description.setObjectName("mutedText")
        self.method_description.setWordWrap(True)
        detail_row.addWidget(self.method_description, 1)
        self.choose_hna_button = QPushButton("Help me choose hnA")
        self.choose_hna_button.setObjectName("quietButton")
        self.choose_hna_button.clicked.connect(self._show_hna_chooser)
        detail_row.addWidget(self.choose_hna_button)
        self.advanced_settings_toggle = QPushButton("Session details")
        self.advanced_settings_toggle.setObjectName("textButton")
        self.advanced_settings_toggle.setCheckable(True)
        self.advanced_settings_toggle.toggled.connect(
            self._toggle_advanced_session_details
        )
        detail_row.addWidget(self.advanced_settings_toggle)
        layout.addLayout(detail_row)
        self.mode_selector_frame = frame
        self.content_layout.addWidget(frame)

    def _populate_methods(self, mode):
        methods = methods_for_mode(mode)
        selected = getattr(self.config, "training_method", "")
        self.method_combo.blockSignals(True)
        self.method_combo.clear()
        for method in methods:
            self.method_combo.addItem(method["title"], method["id"])
        index = self.method_combo.findData(selected)
        self.method_combo.setCurrentIndex(max(0, index))
        self.method_combo.blockSignals(False)
        self._method_changed()

    def _method_changed(self, *args):
        method = METHOD_MAP.get(self.method_combo.currentData())
        if not method:
            return
        description = method["summary"] + "  Best for: " + method["best_for"]
        recommended_id, reason = self._recommended_hna_method()
        if method["id"] == recommended_id:
            description = "Recommended today: " + reason + "  " + description
        self.method_description.setText(description)
        self.method_duration.setValue(
            method.get("duration", self.config.session_minutes)
        )
        self.config.preferred_routine = method.get("preferred_routine", "")
        if method.get("focus"):
            self.config.focus = method["focus"]
            focus_index = self.focus_combo.findData(self.config.focus)
            self.focus_combo.setCurrentIndex(max(0, focus_index))
        if method.get("duration"):
            self.config.session_minutes = method["duration"]
            self.dur_spin.setValue(self.config.session_minutes)
        if method.get("preferred_routine"):
            self.game_combo.setCurrentText("Valorant & Counterstrike")
        if method["mode"] == "deathmatch" and hasattr(
            self, "deathmatch_mode_widget"
        ):
            self.deathmatch_mode_widget.set_plan(
                method.get("deathmatch_blocks", [])
            )
        self.config.training_method = method["id"]
        self.config.save()

    def _start_selected_method(self):
        method = METHOD_MAP.get(self.method_combo.currentData())
        if not method:
            return
        self.config.training_method = method["id"]
        if method["mode"] == "focused":
            self.config.focus = method.get("focus", "weakest")
            focus_index = self.focus_combo.findData(self.config.focus)
            self.focus_combo.setCurrentIndex(max(0, focus_index))
            self.config.save()
            self.show_quick_scenario(False)
        elif method["mode"] == "routine":
            self.config.focus = method.get("focus", "balanced")
            self.config.session_minutes = self.method_duration.value()
            self.dur_spin.setValue(self.config.session_minutes)
            focus_index = self.focus_combo.findData(self.config.focus)
            self.focus_combo.setCurrentIndex(max(0, focus_index))
            if method.get("preferred_routine"):
                self.game_combo.setCurrentText("Valorant & Counterstrike")
            self.config.save()
            self._generate()
            if method["id"] in ("speed_stopping", "speed_precision", "smooth_pathing"):
                cycle = {
                    "speed_stopping": "speed_precision",
                    "speed_precision": "smooth_pathing",
                    "smooth_pathing": "speed_stopping",
                }
                self.config.hna_next_method = cycle[method["id"]]
                self.config.save()
            self.scroll.ensureWidgetVisible(self.routine_frame)
        else:
            self.deathmatch_mode_widget.set_plan(
                method.get("deathmatch_blocks", [])
            )
            self.deathmatch_mode_widget.refresh()
            self.scroll.ensureWidgetVisible(self.deathmatch_mode_frame)

    def select_training_method(self, method_id):
        method = METHOD_MAP.get(method_id)
        if not method:
            return
        self._set_training_mode(method["mode"])
        index = self.method_combo.findData(method_id)
        if index >= 0:
            self.method_combo.setCurrentIndex(index)

    def _recommended_hna_method(self):
        issue_map = {
            "overflicking": (
                "speed_stopping",
                "your latest observation reports overflicking, which points to stopping power",
            ),
            "underflicking": (
                "speed_stopping",
                "your latest observation reports underflicking, which points to acquisition and stopping",
            ),
            "curved_path": (
                "smooth_pathing",
                "your latest observation reports curved or inefficient paths",
            ),
            "overcorrecting": (
                "smooth_pathing",
                "your latest observation reports repeated corrections near the target",
            ),
            "shaky_tense": (
                "smooth_pathing",
                "your latest observation reports shaky or tense movement",
            ),
        }
        if self.db:
            observations = self.db.get_open_game_observations(limit=20)
            for observation in observations:
                issue = (observation.get("issue") or "").casefold()
                if issue in issue_map:
                    return issue_map[issue]
            summaries = self.db.get_skill_feedback_summary()
            recent = sorted(
                summaries.values(),
                key=lambda item: item.get("latest", ""),
                reverse=True,
            )
            for item in recent:
                issue = (item.get("latest_notes") or "").casefold()
                if issue in issue_map:
                    return issue_map[issue]
        next_method = getattr(self.config, "hna_next_method", "speed_stopping")
        if next_method not in ("speed_stopping", "speed_precision", "smooth_pathing"):
            next_method = "speed_stopping"
        return next_method, "it is next in the hnA three-session rotation"

    def _choose_hna_method(self, method_id):
        index = self.method_combo.findData(method_id)
        if index >= 0:
            self.method_combo.setCurrentIndex(index)

    def _show_hna_chooser(self):
        menu = QMenu(self)
        recommended_id, reason = self._recommended_hna_method()
        recommended = METHOD_MAP[recommended_id]
        action = menu.addAction("Recommended: " + recommended["title"])
        action.setToolTip(reason)
        action.triggered.connect(
            lambda checked=False, method_id=recommended_id:
            self._choose_hna_method(method_id)
        )
        menu.addSeparator()
        choices = (
            ("Flick feels slow or hard to stop", "speed_stopping"),
            ("Fast but inconsistent on small targets", "speed_precision"),
            ("Curved path or too many corrections", "smooth_pathing"),
        )
        for label, method_id in choices:
            choice = menu.addAction(label)
            choice.triggered.connect(
                lambda checked=False, value=method_id:
                self._choose_hna_method(value)
            )
        menu.exec(
            self.choose_hna_button.mapToGlobal(
                self.choose_hna_button.rect().bottomLeft()
            )
        )

    def _toggle_advanced_session_details(self, visible):
        self.settings_frame.setVisible(
            visible and self.training_mode == "routine"
        )
        self.advanced_settings_toggle.setText(
            "Hide details" if visible else "Session details"
        )

    def _build_deathmatch_mode(self):
        frame = QFrame()
        frame.setObjectName("deathmatchMode")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)
        title = QLabel("Valorant deathmatch transfer")
        title.setObjectName("smallTitle")
        layout.addWidget(title)
        self.deathmatch_mode_widget = DeathmatchProgressWidget(self.db)
        layout.addWidget(self.deathmatch_mode_widget)
        self.deathmatch_mode_frame = frame
        self.content_layout.addWidget(frame)

    def _set_training_mode(self, mode, persist=True):
        if mode not in self.mode_buttons:
            return
        self.training_mode = mode
        self.mode_buttons[mode].setChecked(True)
        is_focused = mode == "focused"
        is_routine = mode == "routine"
        is_deathmatch = mode == "deathmatch"
        self.deathmatch_mode_frame.setVisible(is_deathmatch)
        self.routine_frame.setVisible(not is_deathmatch)
        self.quick_actions_frame.setVisible(is_focused)
        self.weekly_plan_frame.setVisible(is_focused)
        self.game_review_frame.setVisible(is_focused)
        self.settings_frame.setVisible(is_routine)
        self.settings_frame.setVisible(
            is_routine and self.advanced_settings_toggle.isChecked()
        )
        self.playlist_library_frame.setVisible(
            is_routine and self.library_toggle.isChecked()
        )
        if is_deathmatch:
            self.deathmatch_mode_widget.refresh()
        self.method_duration.setVisible(is_routine)
        self.choose_hna_button.setVisible(is_routine)
        self.advanced_settings_toggle.setVisible(is_routine)
        self.start_method_button.setText({
            "focused": "Start block",
            "routine": "Build routine",
            "deathmatch": "Load checklist",
        }[mode])
        self._populate_methods(mode)
        if persist:
            self.config.training_mode = mode
            self.config.save()
        self.scroll.verticalScrollBar().setValue(0)

    def _build_quick_actions(self):
        frame = QFrame()
        self.quick_actions_frame = frame
        frame.setObjectName("quickTraining")
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(8)

        copy = QVBoxLayout()
        title = QLabel("Today's focused training")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setVisible(False)
        description = QLabel(
            "Train for 3–5 focused minutes, then stop. Return later for a fresh skill."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        description.setVisible(False)
        copy.addWidget(title)
        copy.addWidget(description)
        self.daily_summary = QLabel()
        self.daily_summary.setStyleSheet("color: #94e2d5; font-weight: bold;")
        self.daily_coverage = QLabel()
        self.daily_coverage.setObjectName("mutedText")
        self.daily_coverage.setVisible(False)
        copy.addWidget(self.daily_summary)
        copy.addWidget(self.daily_coverage)
        self.today_phase = QLabel()
        self.today_phase.setObjectName("mutedText")
        self.today_phase.setVisible(False)
        copy.addWidget(self.today_phase)
        self.sync_health = QLabel()
        self.sync_health.setWordWrap(True)
        self.sync_health.setVisible(False)
        copy.addWidget(self.sync_health)
        warmup_context_row = QHBoxLayout()
        self.warmup_context_label = QLabel("Warm up for")
        self.warmup_context_label.setObjectName("mutedText")
        self.warmup_context_label.setVisible(False)
        warmup_context_row.addWidget(self.warmup_context_label)
        self.warmup_context_combo = QComboBox()
        self.warmup_context_combo.setMaximumWidth(280)
        self.warmup_context_combo.addItem("Aim training")
        for game in get_game_options():
            if game != "General / Fundamentals":
                self.warmup_context_combo.addItem(game)
        selected_context = self.warmup_context_combo.findText(
            self.config.warmup_context
        )
        self.warmup_context_combo.setCurrentIndex(max(0, selected_context))
        self.warmup_context_combo.setToolTip(
            "Aim training prepares general control. A game prepares its main aiming demands."
        )
        self.warmup_context_combo.currentTextChanged.connect(
            self._set_warmup_context
        )
        self.warmup_context_combo.setVisible(False)
        warmup_context_row.addWidget(self.warmup_context_combo, 1)
        copy.addLayout(warmup_context_row)
        self.limited_space_check = QCheckBox("Low sensitivity / limited mouse space")
        self.limited_space_check.setChecked(self.config.avoid_continuous_turns)
        self.limited_space_check.setToolTip(
            "Avoid scenarios that require repeated 180° or 360° turns."
        )
        self.limited_space_check.stateChanged.connect(
            self._set_limited_space_preference
        )
        self.limited_space_check.setVisible(False)
        copy.addWidget(self.limited_space_check)
        self._update_daily_progress()
        self._update_sync_health()
        layout.addLayout(copy)

        action_row = QHBoxLayout()
        warmup = QPushButton("Warm up")
        warmup.setObjectName("quietButton")
        warmup.clicked.connect(lambda: self.show_quick_scenario(True))
        action_row.addWidget(warmup)
        self.training_options_toggle = QPushButton("Training options")
        self.training_options_toggle.setObjectName("textButton")
        self.training_options_toggle.setCheckable(True)
        self.training_options_toggle.toggled.connect(self._toggle_training_options)
        action_row.addWidget(self.training_options_toggle)
        action_row.addStretch()
        layout.addLayout(action_row)
        self.content_layout.addWidget(frame)

    def _build_weekly_plan(self):
        frame = QFrame()
        self.weekly_plan_frame = frame
        frame.setObjectName("nextSteps")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(16)

        copy = QVBoxLayout()
        title = QLabel("Weekly training balance")
        title.setObjectName("smallTitle")
        title.setVisible(False)
        self.weekly_focus = QLabel()
        self.weekly_focus.setStyleSheet("color: #94e2d5; font-weight: bold;")
        self.weekly_counts = QLabel()
        self.weekly_counts.setObjectName("mutedText")
        self.weekly_counts.setWordWrap(True)
        self.budget_label = QLabel()
        self.budget_label.setObjectName("mutedText")
        self.budget_label.setWordWrap(True)
        self.budget_label.setVisible(False)
        copy.addWidget(title)
        copy.addWidget(self.weekly_focus)
        copy.addWidget(self.weekly_counts)
        copy.addWidget(self.budget_label)
        layout.addLayout(copy, 1)

        budget = QVBoxLayout()
        budget_label = QLabel("DAILY FPS PLAYTIME")
        budget_label.setObjectName("fieldLabel")
        budget_label.setVisible(False)
        self.fps_budget_spin = QSpinBox()
        self.fps_budget_spin.setRange(30, 600)
        self.fps_budget_spin.setSingleStep(15)
        self.fps_budget_spin.setSuffix(" min")
        self.fps_budget_spin.setValue(self.config.daily_fps_minutes)
        self.fps_budget_spin.setMaximumWidth(140)
        self.fps_budget_spin.valueChanged.connect(self._set_fps_budget)
        self.fps_budget_spin.setVisible(False)
        budget.addWidget(budget_label)
        budget.addWidget(self.fps_budget_spin)
        budget.addStretch()
        layout.addLayout(budget)
        self.weekly_action = QPushButton()
        self.weekly_action.setObjectName("primaryButton")
        self.weekly_action.clicked.connect(self._run_weekly_action)
        layout.addWidget(self.weekly_action, 0, Qt.AlignmentFlag.AlignVCenter)
        self.content_layout.addWidget(frame)
        self._refresh_weekly_plan()

    def _set_fps_budget(self, minutes):
        self.config.daily_fps_minutes = minutes
        self.config.save()
        self._refresh_weekly_plan()

    def _refresh_weekly_plan(self):
        if not hasattr(self, "weekly_focus"):
            return
        plan = build_weekly_plan(self.db, self.config.daily_fps_minutes)
        self._weekly_plan = plan
        completion = "Complete" if plan["today_complete"] else "Next target"
        self.weekly_focus.setText(f"This week  ·  {completion}: {plan['focus_label']}")
        self.weekly_counts.setText(
            "Progress  ·  "
            f"Weakness {plan['weakness_days']}/3  ·  "
            f"Transfer {plan['game_days']}/2  ·  "
            f"Checks {plan['benchmark_days']}/2  ·  "
            f"{plan['remaining_minutes']} min available today"
        )
        budget_text = (
            f"Aim training today  ·  {plan['used_minutes']} min used  ·  "
            f"{plan['remaining_minutes']} min remaining of the flexible "
            f"{plan['aim_cap_minutes']} min guideline"
        )
        self.budget_label.setText(budget_text)
        self.budget_label.setStyleSheet(
            "color: #f9e2af;" if plan["over_budget"] else ""
        )
        self.weekly_action.setText({
            "weakness": "Start focused block",
            "game": "Build transfer routine",
            "benchmark": "View benchmark checks",
        }[plan["focus"]])

    def _run_weekly_action(self):
        focus = self._weekly_plan["focus"]
        if focus == "benchmark":
            self.navigate_requested.emit("skills")
        elif focus == "game":
            self._set_training_mode("routine")
            self._generate()
            self.scroll.ensureWidgetVisible(self.settings_frame)
        else:
            self.show_quick_scenario(False)

    def _build_game_review(self):
        frame = QFrame()
        self.game_review_frame = frame
        frame.setObjectName("nextSteps")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(10)
        header = QHBoxLayout()
        title = QLabel("Post-game observations")
        title.setObjectName("smallTitle")
        header.addWidget(title, 1)
        self.observation_toggle = QPushButton("Log observation")
        self.observation_toggle.setObjectName("textButton")
        self.observation_toggle.setCheckable(True)
        header.addWidget(self.observation_toggle)
        layout.addLayout(header)

        self.observation_form = QWidget()
        form = QVBoxLayout(self.observation_form)
        form.setContentsMargins(0, 0, 0, 0)
        selector_row = QHBoxLayout()
        self.observation_game = QComboBox()
        self.observation_game.addItems(get_game_options()[1:])
        configured = self.config.game
        if configured in get_game_options()[1:]:
            self.observation_game.setCurrentText(configured)
        selector_row.addWidget(self.observation_game, 1)
        self.observation_skill = QComboBox()
        for category, subcategory in SKILL_OPTIONS:
            self.observation_skill.addItem(
                f"{category} · {subcategory}", (category, subcategory)
            )
        selector_row.addWidget(self.observation_skill, 1)
        self.observation_issue = QComboBox()
        for label, issue in REVIEW_ISSUES[1:]:
            self.observation_issue.addItem(label, issue)
        selector_row.addWidget(self.observation_issue, 1)
        for combo in (
            self.observation_game, self.observation_skill,
            self.observation_issue,
        ):
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            combo.setMinimumContentsLength(14)
        form.addLayout(selector_row)
        context_row = QHBoxLayout()
        self.observation_note = QLineEdit()
        self.observation_note.setPlaceholderText("Optional context")
        context_row.addWidget(self.observation_note, 1)
        save = QPushButton("Add observation")
        save.setObjectName("primaryButton")
        save.clicked.connect(self._save_game_observation)
        context_row.addWidget(save)
        form.addLayout(context_row)
        self.observation_form.setVisible(False)
        self.observation_toggle.toggled.connect(self.observation_form.setVisible)
        layout.addWidget(self.observation_form)

        self.observation_list = QVBoxLayout()
        self.observation_list.setSpacing(4)
        layout.addLayout(self.observation_list)
        self.content_layout.addWidget(frame)
        self._refresh_game_observations()

    def _save_game_observation(self):
        if not self.db:
            return
        category, subcategory = self.observation_skill.currentData()
        self.db.record_game_observation(
            self.observation_game.currentText(), category, subcategory,
            self.observation_issue.currentData(),
            self.observation_note.text().strip(),
        )
        self.observation_note.clear()
        self.observation_toggle.setChecked(False)
        self._refresh_game_observations()
        if self.on_scores_updated:
            self.on_scores_updated()

    def _refresh_game_observations(self):
        if not hasattr(self, "observation_list"):
            return
        self._clear_layout(self.observation_list)
        observations = self.db.get_open_game_observations(3) if self.db else []
        if not observations:
            return
        labels = dict(REVIEW_ISSUES)
        for observation in observations:
            row = QHBoxLayout()
            text = (
                f"{observation['game']}  ·  {observation['category']} / "
                f"{observation['subcategory']}  ·  "
                f"{labels.get(observation['issue'], observation['issue'])}"
            )
            if observation["notes"]:
                text += f"  ·  {observation['notes']}"
            label = QLabel(text)
            label.setObjectName("mutedText")
            label.setWordWrap(True)
            label.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
            )
            row.addWidget(label, 1)
            resolve = QPushButton("Resolve")
            resolve.setObjectName("textButton")
            resolve.clicked.connect(
                lambda checked=False, value=observation["id"]:
                self._resolve_game_observation(value)
            )
            row.addWidget(resolve)
            self.observation_list.addLayout(row)

    def _resolve_game_observation(self, observation_id):
        self.db.resolve_game_observation(observation_id)
        self._refresh_game_observations()
        if self.on_scores_updated:
            self.on_scores_updated()

    def _continue_today(self):
        self.show_quick_scenario(False)

    def _today_warmup_minutes(self):
        return (
            warmup_minutes(self.warmup_context_combo.currentText())
            or self.config.warmup_minutes
        )

    def _recommended_warmup_complete(self, blocks):
        completed = {
            block.get("scenario") for block in blocks if block.get("warmup")
        }
        preset = get_warmup_routine(self.warmup_context_combo.currentText())
        if not preset:
            return bool(completed)
        return {step["scenario"] for step in preset} <= completed

    def _show_today_review(self):
        blocks = self._daily_state.get("blocks", [])
        training = [block for block in blocks if not block.get("warmup")]
        minutes = sum(block.get("minutes", 0) for block in blocks)
        runs = sum(block.get("runs", 0) for block in blocks)
        categories = sorted({
            block.get("category") for block in training if block.get("category")
        })
        effectiveness = self.db.get_recent_effectiveness(1) if self.db else []
        effect_text = ""
        if effectiveness:
            result = effectiveness[0]
            if result["score_delta_pct"] is not None:
                effect_text = (
                    f"\nLatest measured response: {result['scenario']} "
                    f"{result['score_delta_pct']:+.1f}% versus its prior baseline.\n"
                )
            else:
                effect_text = "\nMore prior runs are needed to measure training response.\n"
        QMessageBox.information(
            self,
            "Today's review",
            f"You completed {len(training)} training blocks and {runs} runs "
            f"in about {minutes} minutes.\n\n"
            f"Coverage: {', '.join(categories) if categories else 'Warm-up only'}\n"
            f"{effect_text}"
            f"Cooldown: take {self.config.cooldown_minutes} minutes for relaxed, "
            "smooth reps or wrist/shoulder mobility.",
        )

    def _set_warmup_context(self, context):
        self.config.warmup_context = context
        self.config.save()

    def _update_sync_health(self):
        if not hasattr(self, "sync_health"):
            return
        stats_dir = self.config.get_stats_dir()
        if not os.path.isdir(stats_dir):
            self.sync_health.setText("Sync unavailable  ·  Kovaak's stats folder not found")
            self.sync_health.setStyleSheet("color: #f38ba8; font-weight: bold;")
            return
        csv_files = [
            os.path.join(stats_dir, filename)
            for filename in os.listdir(stats_dir)
            if filename.lower().endswith(".csv")
        ]
        if not csv_files:
            self.sync_health.setText("Sync connected  ·  waiting for the first Kovaak's result")
            self.sync_health.setStyleSheet("color: #f9e2af; font-weight: bold;")
            return
        latest = max(csv_files, key=os.path.getmtime)
        age_seconds = max(0, int(datetime.now().timestamp() - os.path.getmtime(latest)))
        if age_seconds < 60:
            age = "just now"
        elif age_seconds < 3600:
            age = f"{age_seconds // 60} min ago"
        elif age_seconds < 86400:
            age = f"{age_seconds // 3600} hr ago"
        else:
            age = datetime.fromtimestamp(os.path.getmtime(latest)).strftime("%b %d")
        self.sync_health.setText(f"Sync connected  ·  last result {age}")
        self.sync_health.setStyleSheet("color: #94e2d5; font-weight: bold;")

    def _set_limited_space_preference(self, _state):
        self.config.avoid_continuous_turns = self.limited_space_check.isChecked()
        self.config.save()
        current = self._current_quick
        if current and self.config.avoid_continuous_turns:
            blocked = ("revolving", "360", "centering i 180")
            if any(hint in current["scenario"].casefold() for hint in blocked):
                self.show_quick_scenario(current["warmup"], launch=False)

    def _build_settings(self):
        frame = QFrame()
        self.settings_frame = frame
        frame.setObjectName("routineSettings")
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame#routineSettings {
                background-color: #11192b;
                border-radius: 12px;
                border: 1px solid #263149;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Session setup")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(title)
        subtitle = QLabel(
            "Set your time and goal. Recommendations use your measured Voltaic performance."
        )
        subtitle.setObjectName("mutedText")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        row1 = QHBoxLayout()
        row1.setSpacing(12)

        duration_block = QVBoxLayout()
        dur_label = QLabel("SESSION LENGTH")
        dur_label.setObjectName("fieldLabel")
        duration_block.addWidget(dur_label)
        self.dur_spin = QSpinBox()
        self.dur_spin.setRange(15, 120)
        self.dur_spin.setValue(self.config.session_minutes)
        self.dur_spin.setSuffix(" min")
        self.dur_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.dur_spin.setToolTip("Type a duration or use the mouse wheel")
        duration_block.addWidget(self.dur_spin)
        row1.addLayout(duration_block, 1)

        warmup_block = QVBoxLayout()
        warmup_label = QLabel("WARM-UP")
        warmup_label.setObjectName("fieldLabel")
        warmup_block.addWidget(warmup_label)
        self.warmup_spin = QSpinBox()
        self.warmup_spin.setRange(0, 15)
        self.warmup_spin.setValue(self.config.warmup_minutes)
        self.warmup_spin.setSuffix(" min")
        self.warmup_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        warmup_block.addWidget(self.warmup_spin)
        row1.addLayout(warmup_block, 1)

        cooldown_block = QVBoxLayout()
        cd_label = QLabel("COOLDOWN")
        cd_label.setObjectName("fieldLabel")
        cooldown_block.addWidget(cd_label)
        self.cd_spin = QSpinBox()
        self.cd_spin.setRange(0, 15)
        self.cd_spin.setValue(self.config.cooldown_minutes)
        self.cd_spin.setSuffix(" min")
        self.cd_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        cooldown_block.addWidget(self.cd_spin)
        row1.addLayout(cooldown_block, 1)
        layout.addLayout(row1)

        choice_row = QHBoxLayout()
        choice_row.setSpacing(12)
        game_block = QVBoxLayout()
        game_label = QLabel("TRAINING CONTEXT")
        game_label.setObjectName("fieldLabel")
        self.game_combo = QComboBox()
        self.game_combo.addItems(get_game_options())
        configured_game = getattr(self.config, "game", "General / Fundamentals")
        if configured_game in get_game_options():
            self.game_combo.setCurrentText(configured_game)
        self.game_combo.setToolTip(
            "General uses Voltaic fundamentals and issue routines. Choose a game "
            "to use its official game-specific routines."
        )
        game_block.addWidget(game_label)
        game_block.addWidget(self.game_combo)
        choice_row.addLayout(game_block, 1)

        focus_layout = QVBoxLayout()
        focus_label = QLabel("FOCUS")
        focus_label.setObjectName("fieldLabel")
        focus_layout.addWidget(focus_label)

        self.focus_combo = QComboBox()
        for key, label in FOCUS_OPTIONS.items():
            self.focus_combo.addItem(label, key)
        focus_index = self.focus_combo.findData(self.config.focus)
        self.focus_combo.setCurrentIndex(max(0, focus_index))
        self.focus_combo.setToolTip(
            "Weakest Areas uses completed benchmarks. Balanced covers all core skills."
        )
        focus_layout.addWidget(self.focus_combo)
        choice_row.addLayout(focus_layout, 1)
        layout.addLayout(choice_row)

        opts = QHBoxLayout()
        self.installed_check = QCheckBox("Prefer installed when equally suitable")
        self.installed_check.setChecked(self.config.prioritize_installed)
        self.installed_check.setToolTip(
            "Installed status only breaks close ties; training fit remains more important."
        )
        opts.addWidget(self.installed_check)
        opts.addStretch()
        layout.addLayout(opts)

        action_row = QHBoxLayout()
        self.generate_btn = QPushButton("Generate routine")
        self.generate_btn.setObjectName("primaryButton")
        self.generate_btn.clicked.connect(self._generate)
        action_row.addWidget(self.generate_btn)
        self.export_btn = QPushButton("Export playlist")
        self.export_btn.setObjectName("quietButton")
        self.export_btn.setEnabled(False)
        self.export_btn.setVisible(False)
        self.export_btn.clicked.connect(self._export)
        action_row.addWidget(self.export_btn)
        self.library_toggle = QPushButton("Official playlists")
        self.library_toggle.setObjectName("quietButton")
        self.library_toggle.setCheckable(True)
        self.library_toggle.toggled.connect(self._toggle_playlist_library)
        action_row.addWidget(self.library_toggle)
        action_row.addStretch()
        layout.addLayout(action_row)

        self.content_layout.addWidget(frame)
        frame.setVisible(False)

    def _toggle_training_options(self, visible):
        self.warmup_context_label.setVisible(visible)
        self.warmup_context_combo.setVisible(visible)
        self.limited_space_check.setVisible(visible)
        self.training_options_toggle.setText(
            "Hide options" if visible else "Training options"
        )

    def _build_routine_display(self):
        self.routine_frame = QFrame()
        self.routine_frame.setObjectName("routineDisplay")
        self.routine_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.routine_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.routine_frame.setStyleSheet("""
            QFrame#routineDisplay {
                background-color: #11192b;
                border-radius: 12px;
                border: 1px solid #263149;
            }
        """)
        self.routine_layout = QVBoxLayout(self.routine_frame)
        self.routine_layout.setContentsMargins(20, 18, 20, 18)
        self.routine_layout.setSpacing(10)

        placeholder = QLabel("Choose “Play scenario” or “Warm up” to get started.")
        placeholder.setStyleSheet("color: #7f849c; font-style: italic;")
        placeholder.setFont(QFont("Segoe UI", 11))
        placeholder.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.routine_layout.addWidget(placeholder)

        self.content_layout.addWidget(self.routine_frame)

    def _build_share_codes(self):
        frame = QFrame()
        frame.setObjectName("playlistLibrary")
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame#playlistLibrary {
                background-color: #11192b;
                border-radius: 12px;
                border: 1px solid #263149;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        title = QLabel("Official Voltaic playlist library")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(title)

        sub = QLabel(
            "Browse all supplied game, issue, and fundamental routines. Paste the "
            "share code in Kovaak's → Online Playlists."
        )
        sub.setStyleSheet("color: #7f849c; font-style: italic;")
        sub.setWordWrap(True)
        layout.addWidget(sub)

        self.official_routine_combo = QComboBox()
        for routine in (item for item in ROUTINES if item.get("share_code")):
            kind = routine.get("kind", "routine").title()
            self.official_routine_combo.addItem(
                f"{kind} · {routine['name']}", routine
            )
        self.official_routine_combo.currentIndexChanged.connect(
            self._update_official_routine_details
        )
        layout.addWidget(self.official_routine_combo)

        details_row = QHBoxLayout()
        details = QVBoxLayout()
        self.official_routine_meta = QLabel()
        self.official_routine_meta.setStyleSheet("color: #a6adc8;")
        self.official_routine_meta.setWordWrap(True)
        self.official_routine_description = QLabel()
        self.official_routine_description.setObjectName("mutedText")
        self.official_routine_description.setWordWrap(True)
        self.official_share_code = QLabel()
        self.official_share_code.setFont(QFont("Consolas", 9))
        self.official_share_code.setStyleSheet("color: #a6e3a1;")
        self.official_share_code.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.official_routine_guidance = QLabel()
        self.official_routine_guidance.setStyleSheet("color: #89b4fa;")
        self.official_routine_guidance.setWordWrap(True)
        details.addWidget(self.official_routine_meta)
        details.addWidget(self.official_routine_description)
        details.addWidget(self.official_share_code)
        details.addWidget(self.official_routine_guidance)
        details_row.addLayout(details, 1)
        copy_btn = QPushButton("Copy code")
        copy_btn.clicked.connect(self._copy_official_share_code)
        details_row.addWidget(copy_btn)
        layout.addLayout(details_row)
        self._update_official_routine_details()

        frame.setVisible(False)
        self.playlist_library_frame = frame
        self.content_layout.addWidget(frame)

    def _toggle_playlist_library(self, visible):
        self.playlist_library_frame.setVisible(visible)
        self.library_toggle.setText(
            "Hide playlists" if visible else "Official playlists"
        )

    def _update_official_routine_details(self):
        routine = self.official_routine_combo.currentData()
        if not routine:
            return
        ranks = ", ".join(routine.get("recommended_ranks", [])) or "All suitable ranks"
        duration = routine.get("duration_minutes", 0)
        maximum = routine.get("duration_max_minutes", duration)
        duration_text = f"{duration} min" if duration == maximum else f"{duration}–{maximum} min"
        self.official_routine_meta.setText(
            f"{routine.get('group', '')} · {duration_text} · {ranks} · "
            f"{len(routine.get('exercises', []))} exercise groups"
        )
        self.official_routine_description.setText(
            get_routine_description(routine)
        )
        self.official_share_code.setText(routine.get("share_code", ""))
        kind = routine.get("kind")
        group = routine.get("group", "")
        if kind == "issue":
            summary = GUIDANCE["issues"].get(group, "")
        elif kind == "game":
            summary = GUIDANCE["game_transfer"].get(group, "")
        else:
            summary = GUIDANCE["difficulty_and_progression"]["summary"]
        cues = []
        for target in routine.get("targets", []):
            if "_" not in target:
                continue
            category, subcategory = target.split("_", 1)
            cue = get_training_guidance(category, subcategory)["cue"]
            if cue not in cues:
                cues.append(cue)
        cue_text = " ".join(f"• {cue}" for cue in cues[:2])
        self.official_routine_guidance.setText(
            "How to use it: " + summary + ("\n" + cue_text if cue_text else "")
        )

    def _copy_official_share_code(self):
        code = self.official_share_code.text().strip()
        if code:
            QApplication.clipboard().setText(code)

    def _get_focus_key(self):
        return self.focus_combo.currentData() or "weakest"

    def show_quick_scenario(
        self, warmup=False, launch=True, warmup_context=None
    ):
        self._install_poll_timer.stop()
        self._pending_install = None
        if self._daily_state.get("date") != self._today_key():
            self._daily_state = {"date": self._today_key(), "blocks": []}
            self._quick_history.clear()
            self._warmup_history.clear()
            self._quick_rotation = 0
            self._warmup_rotation = 0
            self._save_daily_state()
            self._update_daily_progress()
        history = self._warmup_history if warmup else self._quick_history
        rotation = self._warmup_rotation if warmup else self._quick_rotation
        context = (
            warmup_context or self.warmup_context_combo.currentText()
            if warmup else "Aim training"
        )
        preset = get_warmup_routine(context) if warmup else None
        if preset:
            preset_names = {step["scenario"] for step in preset}
            rotation = sum(
                1 for block in self._daily_state.get("blocks", [])
                if block.get("warmup") and block.get("scenario") in preset_names
            )
        recommendation = (
            self._recommended_warmup_step(rotation, context)
            if warmup and get_warmup_routine(context) else
            generate_quick_scenario(
                self.profile, warmup=warmup, recent_names=history[-3:],
                rotation_index=rotation, config=self.config,
                warmup_context=context,
                training_schedule=(
                    build_adaptive_schedule(build_skill_intelligence(self.profile, self.db))
                    if self.db and not warmup else None
                ),
                scenario_signals=(build_scenario_signals(self.db) if self.db else None),
            )
        )
        if warmup:
            self._warmup_rotation += 1
            self._warmup_history.append(recommendation["scenario"])
        else:
            self._quick_rotation += 1
            self._quick_history.append(recommendation["scenario"])
        self._current_quick = recommendation
        self._quick_session_completed = False
        self._quick_session_stopped = False
        self._current_routine = None
        self.export_btn.setVisible(False)
        self._run_tracker.start(recommendation["scenario"], recommendation["runs"])
        self._render_quick_scenario(recommendation)
        self._run_poll_timer.start()
        if launch:
            self._launch_quick_scenario(recommendation)
        self.scroll.verticalScrollBar().setValue(0)

    def _recommended_warmup_step(self, rotation, context="Aim training"):
        routine = get_warmup_routine(context)
        step_number = rotation % len(routine)
        step = routine[step_number]
        plan = quick_block_plan(
            step["scenario"], self.config.get_scenario_dirs(),
            self.config.get_stats_dir(),
        )
        runs = max(
            1, round(step["duration_min"] * 60 / plan["scenario_seconds"])
        )
        return {
            "scenario": step["scenario"],
            "category": step["category"],
            "subcategory": step["subcategory"],
            "runs": runs,
            "estimated_minutes": step["duration_min"],
            "scenario_seconds": plan["scenario_seconds"],
            "duration_source": plan["duration_source"],
            "installed": bool(find_scenario_file(
                step["scenario"], self.config.get_scenario_dirs()
            )),
            "warmup": True,
            "warmup_context": f"{context} · recommended {warmup_minutes(context)}-minute routine",
            "target_label": "Full warm-up",
            "reason": (
                f"Step {step_number + 1} of {len(routine)} "
                "in the recommended warm-up routine."
            ),
            "coaching_cue": step["cue"],
        }

    def _launch_quick_scenario(self, recommendation):
        if hasattr(self, "stop_quick_btn"):
            self.stop_quick_btn.setVisible(True)
        scenario_path = prepare_scenario_launch(
            recommendation, self.config.get_scenario_dirs(), self.config.get_stats_dir()
        )
        # Online scenarios are commonly streamed by Kovaak's and may never be
        # written to SaveGames/Scenarios as a .sce file. A local file improves
        # timing accuracy, but it must never gate launching the official deep link.
        self._run_tracker.target_runs = recommendation["runs"]
        self._show_challenge_mode_notice()
        if self._quick_session_stopped:
            self._quick_session_stopped = False
            self._quick_session_completed = False
            self._run_tracker.start(recommendation["scenario"], recommendation["runs"])
            self._run_poll_timer.start()
            self.quick_run_progress.setValue(0)
            self.quick_run_status.setText(
                f"Ready  ·  0/{recommendation['runs']} runs detected"
            )
            self.quick_run_status.setStyleSheet("color: #89b4fa; font-weight: bold;")
            self.stop_quick_btn.setEnabled(True)
            self.manual_complete_btn.setEnabled(True)
            self.open_quick_btn.setText("Open scenario")
        launched = open_kovaaks_scenario(recommendation["scenario"])
        self.quick_run_status.setText(
            f"Active  ·  {self._run_tracker.completed_runs}/"
            f"{recommendation['runs']} runs detected"
        )
        self.quick_run_status.setStyleSheet("color: #89b4fa; font-weight: bold;")
        if launched and scenario_path:
            launch_text = (
                "Scenario selected  ·  Keep Kovaak's FREEPLAY/CHALLENGE toggle on CHALLENGE."
            )
        elif launched:
            launch_text = (
                "Online scenario requested  ·  Kovaak's will download and load it automatically. "
                "Keep the mode on CHALLENGE."
            )
        else:
            launch_text = "Steam could not open it. Copy the name and search inside Kovaak's."
        self.quick_launch_status.setText(launch_text)
        self.quick_launch_status.setStyleSheet(
            "color: #94e2d5;" if launched else "color: #f38ba8;"
        )

    def _begin_scenario_install(self, recommendation):
        """Wait for an official in-game download before allowing play."""
        self._pending_install = recommendation
        QApplication.clipboard().setText(recommendation["scenario"])
        message = QMessageBox(self)
        message.setWindowTitle("Download scenario first")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText(f"{recommendation['scenario']} is not downloaded yet.")
        message.setInformativeText(
            "Its exact name has been copied. In Kovaak's, open Sandbox > Online "
            "Scenarios, paste the name, and click the download arrow. Aim Companion "
            "will detect the .sce file, read its exact time limit, and then open it."
        )
        message.exec()
        launched = open_kovaaks()
        self.open_quick_btn.setText("Waiting for download...")
        self.open_quick_btn.setEnabled(False)
        self.quick_run_status.setText("Install step  ·  waiting for the scenario file")
        self.quick_run_status.setStyleSheet("color: #f9e2af; font-weight: bold;")
        self.quick_launch_status.setText(
            "Kovaak's opened  ·  Online Scenarios → paste the copied name → click ↓"
            if launched else
            "Steam could not open Kovaak's. Open it manually; the scenario name is copied."
        )
        self.quick_launch_status.setStyleSheet(
            "color: #f9e2af;" if launched else "color: #f38ba8;"
        )
        self._install_poll_timer.start()

    def _apply_downloaded_scenario_data(self, recommendation):
        plan = quick_block_plan(
            recommendation["scenario"],
            self.config.get_scenario_dirs(),
            self.config.get_stats_dir(),
        )
        recommendation.update(plan)
        recommendation["installed"] = True
        self._run_tracker.target_runs = recommendation["runs"]

    def _poll_scenario_install(self):
        recommendation = self._pending_install
        if not recommendation or recommendation is not self._current_quick:
            self._install_poll_timer.stop()
            self._pending_install = None
            return
        path = find_scenario_file(
            recommendation["scenario"], self.config.get_scenario_dirs()
        )
        if not path:
            return
        self._install_poll_timer.stop()
        self._pending_install = None
        self._apply_downloaded_scenario_data(recommendation)
        self._run_tracker.start(recommendation["scenario"], recommendation["runs"])
        self._render_quick_scenario(recommendation)
        self.quick_launch_status.setText(
            f"Downloaded  ·  exact time limit read from {os.path.basename(path)}"
        )
        self.quick_launch_status.setStyleSheet("color: #94e2d5;")
        if self.notifier:
            self.notifier.notify(
                "Scenario ready",
                f"{recommendation['scenario']} was downloaded and checked.",
            )
        QTimer.singleShot(500, lambda: self._launch_quick_scenario(recommendation))

    def _show_challenge_mode_notice(self):
        if (
            self.config.challenge_mode_notice_seen
            or self._challenge_notice_shown_this_session
        ):
            return
        message = QMessageBox(self)
        message.setWindowTitle("Use Kovaak's Challenge mode")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText("Challenge mode is required for automatic run tracking.")
        message.setInformativeText(
            "In Kovaak's, open the pause menu and set the FREEPLAY/CHALLENGE "
            "toggle to CHALLENGE, then press Play. Kovaak's remembers this choice "
            "for later scenarios."
        )
        remember = QCheckBox("I set it to Challenge — don't show this again")
        message.setCheckBox(remember)
        message.exec()
        self._challenge_notice_shown_this_session = True
        if remember.isChecked():
            self.config.challenge_mode_notice_seen = True
            self.config.save()

    def _stop_quick_session(self, recommendation):
        if self._quick_session_completed or self._quick_session_stopped:
            return
        self._install_poll_timer.stop()
        self._pending_install = None
        completed = self._run_tracker.completed_runs
        target = recommendation["runs"]
        self._quick_session_stopped = True
        self._run_tracker.stop()
        self._run_poll_timer.stop()
        label = "Warm-up" if recommendation["warmup"] else "Training"
        self.quick_run_status.setText(f"{label} stopped  ·  {completed}/{target} runs")
        self.quick_run_status.setStyleSheet("color: #f9e2af; font-weight: bold;")
        self.quick_launch_status.setText(
            "Live tracking stopped. Kovaak's remains open; Start again begins a new block."
        )
        self.quick_launch_status.setStyleSheet("color: #a6adc8;")
        self.stop_quick_btn.setEnabled(False)
        self.manual_complete_btn.setEnabled(False)
        self.open_quick_btn.setText("Start again")

    def _complete_quick_block(self, recommendation, advance=True, automated=False):
        newly_completed = not self._quick_session_completed
        if not self._quick_session_completed and self.db:
            self.db.record_scenario_completion(
                recommendation["scenario"],
                runs=recommendation["runs"],
                warmup=recommendation["warmup"],
                duration_minutes=recommendation["estimated_minutes"],
                focus=(
                    "Warm-up" if recommendation["warmup"] else
                    f"{recommendation['category']} / {recommendation['subcategory']}"
                ),
                source="quick_tracked" if automated else "quick_manual",
            )
        if not self._quick_session_completed:
            self._daily_state["blocks"].append({
                "scenario": recommendation["scenario"],
                "category": recommendation["category"],
                "subcategory": recommendation["subcategory"],
                "runs": recommendation["runs"],
                "minutes": recommendation["estimated_minutes"],
                "warmup": recommendation["warmup"],
                "completed_at": datetime.now().isoformat(timespec="seconds"),
            })
            self._quick_session_completed = True
            self._run_tracker.stop()
            self._run_poll_timer.stop()
            self._save_daily_state()
            self._update_daily_progress()
            self._refresh_weekly_plan()
            if self.on_scores_updated:
                QTimer.singleShot(0, self.on_scores_updated)
        if automated:
            label = "Warm-up" if recommendation["warmup"] else "Training block"
            target = recommendation["runs"]
            self.quick_run_status.setText(
                f"{label} complete  ·  {target}/{target} runs"
            )
            self.quick_run_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.quick_run_progress.setValue(recommendation["runs"])
            self.stop_quick_btn.setEnabled(False)
            self.manual_complete_btn.setEnabled(False)
            QApplication.beep()
            if self.notifier:
                self.notifier.notify(
                    f"{label} complete",
                    f"You finished {target} "
                    f"{'run' if target == 1 else 'runs'} of "
                    f"{recommendation['scenario']}.",
                )
        elif newly_completed:
            label = "Warm-up" if recommendation["warmup"] else "Training block"
            self.quick_run_status.setText(f"{label} complete  ·  saved manually")
            self.quick_run_status.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            self.quick_run_progress.setValue(recommendation["runs"])
            self.manual_complete_btn.setEnabled(False)
        if newly_completed and hasattr(self, "finish_quick_btn"):
            self.finish_quick_btn.setVisible(True)
            self.next_quick_btn.setText(
                "Next warm-up step" if recommendation["warmup"] else "Another block"
            )
            self.quick_launch_status.setText(
                "Block saved  ·  You can stop now and return later with a fresh hand."
            )
            self.quick_launch_status.setStyleSheet("color: #94e2d5; font-weight: bold;")
            self.open_quick_btn.setEnabled(False)
            self.stop_quick_btn.setEnabled(False)
            self.feedback_frame.setVisible(True)
            fatigue = detect_fatigue(self.db) if self.db else None
            if fatigue:
                self.quick_launch_status.setText(
                    f"Fatigue warning  ·  {fatigue['scenario']} is "
                    f"{abs(fatigue['drop_pct']):.1f}% below baseline. Stop and recover."
                )
                self.quick_launch_status.setStyleSheet("color: #f38ba8; font-weight: bold;")
                self.next_quick_btn.setEnabled(False)
        if advance and not newly_completed:
            self.show_quick_scenario(recommendation["warmup"])

    def _record_block_feedback(self, recommendation, rating):
        if not self.db:
            return
        issue = self.issue_combo.currentData() or ""
        self.db.record_block_feedback(
            recommendation["scenario"], rating, notes=issue,
            category=recommendation.get("category", ""),
            subcategory=recommendation.get("subcategory", ""),
        )
        observation_id = recommendation.get("observation_id")
        if observation_id:
            self.db.resolve_game_observation(observation_id)
            self._refresh_game_observations()
        labels = {
            "too_easy": "Too easy saved — a harder variant can be considered.",
            "productive": "Productive saved — this scenario gains preference.",
            "too_hard": "Too difficult saved — difficulty will be reduced.",
            "discomfort": "Discomfort saved — this scenario will be avoided.",
        }
        self.feedback_label.setText(labels[rating])
        for button in self.feedback_buttons:
            button.setEnabled(False)
        if rating == "discomfort":
            self.next_quick_btn.setEnabled(False)
            self.quick_launch_status.setText(
                "Stop for now. Physical discomfort is not a productive training signal."
            )
            self.quick_launch_status.setStyleSheet("color: #f38ba8; font-weight: bold;")
        if self.on_scores_updated:
            QTimer.singleShot(0, self.on_scores_updated)

    def _poll_quick_session(self):
        if not self._current_quick or self._quick_session_completed:
            return
        matches = self._run_tracker.poll()
        if not matches:
            return
        if self.db:
            imported = import_all_scores(self.db, self.config.get_stats_dir())
            if imported and any(score.category != "Unknown" for score in matches):
                self._benchmark_scores_pending = True
        self._update_sync_health()
        completed = self._run_tracker.completed_runs
        target = self._run_tracker.target_runs
        self.quick_run_progress.setValue(completed)
        self.quick_run_status.setText(
            f"Current block  ·  {completed}/{target} runs detected"
        )
        self.quick_run_status.setStyleSheet("color: #89b4fa; font-weight: bold;")
        if completed >= target:
            self._complete_quick_block(
                self._current_quick, advance=False, automated=True
            )
            self._benchmark_scores_pending = False

    def _update_daily_progress(self):
        if not hasattr(self, "daily_summary"):
            return
        blocks = self._daily_state.get("blocks", [])
        runs = sum(block.get("runs", 0) for block in blocks)
        minutes = sum(block.get("minutes", 0) for block in blocks)
        warmups = sum(1 for block in blocks if block.get("warmup"))
        training_blocks = [block for block in blocks if not block.get("warmup")]
        counts = {
            category: sum(1 for block in training_blocks if block.get("category") == category)
            for category in ("Clicking", "Tracking", "Switching")
        }
        self.daily_summary.setText(
            f"Today  ·  {len(training_blocks)} blocks  ·  "
            f"{runs} runs  ·  {minutes} min"
            + (f"  ·  {warmups} warm-up" if warmups else "")
        )
        self.daily_coverage.setText(
            "Coverage  ·  " + "  ".join(
                f"{category} {counts[category]}" for category in counts
            )
        )
        if hasattr(self, "today_phase"):
            if training_blocks:
                timestamps = [
                    datetime.fromisoformat(block["completed_at"])
                    for block in training_blocks if block.get("completed_at")
                ]
                elapsed_minutes = (
                    max(0, int((datetime.now() - max(timestamps)).total_seconds() // 60))
                    if timestamps else 0
                )
                when = "just now" if elapsed_minutes < 1 else f"{elapsed_minutes} min ago"
                phase = (
                    f"{len(training_blocks)} focused "
                    f"{'block' if len(training_blocks) == 1 else 'blocks'} today · "
                    f"last {when} · another is optional"
                )
            else:
                phase = "Ready for one short 3–5 minute block"
            self.today_phase.setText(phase)
            if hasattr(self, "continue_today_btn"):
                self.continue_today_btn.setText("Get another block" if training_blocks else "Get one training block")

    def _render_quick_scenario(self, recommendation):
        self._clear_layout(self.routine_layout)
        heading = QLabel(
            f"Warm-up pick  ·  {recommendation['warmup_context']}"
            if recommendation["warmup"] else "RECOMMENDED FOR YOU"
        )
        heading.setObjectName("eyebrow")
        self.routine_layout.addWidget(heading)

        scenario = QLabel(recommendation["scenario"])
        scenario.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        scenario.setStyleSheet("color: #f8fafc;")
        scenario.setWordWrap(True)
        self.routine_layout.addWidget(scenario)

        target_runs = recommendation["runs"]
        per_run_seconds = recommendation.get("scenario_seconds", 60)
        per_run = (
            f"{per_run_seconds / 60:g} min each"
            if per_run_seconds >= 60 else f"{per_run_seconds} sec each"
        )
        meta = QLabel(
            f"{target_runs} {'run' if target_runs == 1 else 'runs'} · "
            f"about {recommendation['estimated_minutes']} min · {per_run} · "
            f"{recommendation['category']} / {recommendation['subcategory']}"
        )
        meta.setStyleSheet("color: #89b4fa; font-weight: bold;")
        meta.setWordWrap(True)
        meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.routine_layout.addWidget(meta)

        self.quick_run_status = QLabel(
            f"Ready  ·  0/{recommendation['runs']} runs detected"
        )
        self.quick_run_status.setStyleSheet("color: #89b4fa; font-weight: bold;")
        self.routine_layout.addWidget(self.quick_run_status)
        self.quick_run_progress = QProgressBar()
        self.quick_run_progress.setRange(0, recommendation["runs"])
        self.quick_run_progress.setValue(0)
        self.quick_run_progress.setTextVisible(False)
        self.quick_run_progress.setFixedHeight(8)
        self.routine_layout.addWidget(self.quick_run_progress)

        history = (
            self.db.get_scenario_completion(recommendation["scenario"])
            if self.db else
            {"completed_blocks": 0, "completed_runs": 0, "warmup_blocks": 0}
        )
        completed = history["completed_blocks"]
        completed_runs = history["completed_runs"]
        history_text = (
            "Never completed yet"
            if completed == 0 else
            f"Completed {completed} {'time' if completed == 1 else 'times'}"
            f"  ·  {completed_runs} total "
            f"{'run' if completed_runs == 1 else 'runs'}"
        )
        detected_runs = (
            self.db.get_scenario_attempt_count(recommendation["scenario"])
            if self.db else 0
        )
        if detected_runs:
            history_text = (
                f"Kovaak's history  ·  {detected_runs} recorded "
                f"{'run' if detected_runs == 1 else 'runs'}"
            )
            if completed:
                history_text += (
                    f"  ·  {completed} completed app "
                    f"{'block' if completed == 1 else 'blocks'}"
                )
        if recommendation["warmup"] and history.get("warmup_blocks"):
            history_text += f"  ·  {history['warmup_blocks']} as warm-up"
        scenario_history = QLabel(history_text)
        scenario_history.setStyleSheet("color: #cba6f7; font-weight: bold;")
        scenario_history.setWordWrap(True)
        scenario_history.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        scenario_history.setVisible(False)
        self.routine_layout.addWidget(scenario_history)

        reason = QLabel(recommendation["reason"])
        reason.setObjectName("mutedText")
        reason.setWordWrap(True)
        reason.setVisible(False)
        self.routine_layout.addWidget(reason)

        cue = QLabel("Technique  ·  " + recommendation["coaching_cue"])
        cue.setStyleSheet("color: #a6e3a1;")
        cue.setWordWrap(True)
        self.routine_layout.addWidget(cue)

        status = QLabel(
            "Downloaded  ·  exact scenario timing available"
            if recommendation["installed"] else
            "Online scenario  ·  Kovaak's will download and load it when you press Start"
        )
        status.setStyleSheet(
            "color: #94e2d5;" if recommendation["installed"] else "color: #f9e2af;"
        )
        status.setWordWrap(True)
        status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        status.setVisible(False)
        self.routine_layout.addWidget(status)
        challenge_required = QLabel(
            "Challenge mode required for live tracking  ·  Free Play does not create a completed-run result."
        )
        challenge_required.setStyleSheet("color: #f9e2af; font-weight: bold;")
        challenge_required.setWordWrap(True)
        challenge_required.setVisible(False)
        self.routine_layout.addWidget(challenge_required)
        self.quick_detail_widgets = (
            scenario_history, reason, status, challenge_required,
        )
        self.quick_launch_status = QLabel("")
        self.quick_launch_status.setWordWrap(True)
        self.routine_layout.addWidget(self.quick_launch_status)

        self.feedback_frame = QFrame()
        self.feedback_frame.setObjectName("focusPanel")
        feedback_layout = QVBoxLayout(self.feedback_frame)
        feedback_layout.setSpacing(8)
        self.feedback_label = QLabel("Review the block while the movement is fresh")
        self.feedback_label.setObjectName("mutedText")
        feedback_layout.addWidget(self.feedback_label)
        issue_row = QHBoxLayout()
        issue_label = QLabel("Recurring error")
        issue_label.setObjectName("mutedText")
        issue_row.addWidget(issue_label)
        self.issue_combo = QComboBox()
        self.issue_combo.setToolTip(
            "Choose the recurring movement error you noticed, not the result of one miss."
        )
        for label, issue in REVIEW_ISSUES:
            self.issue_combo.addItem(label, issue)
        self.issue_combo.setMinimumWidth(205)
        self.issue_combo.setMaximumWidth(360)
        issue_row.addWidget(self.issue_combo)
        issue_row.addStretch()
        feedback_layout.addLayout(issue_row)
        rating_label = QLabel("Difficulty")
        rating_label.setObjectName("mutedText")
        feedback_layout.addWidget(rating_label)
        rating_rows = [QHBoxLayout(), QHBoxLayout()]
        for row in rating_rows:
            row.setSpacing(8)
        self.feedback_buttons = []
        for index, (label, rating) in enumerate((
            ("Too easy", "too_easy"), ("Productive", "productive"),
            ("Too hard", "too_hard"), ("Discomfort", "discomfort"),
        )):
            button = QPushButton(label)
            button.setObjectName("quietButton")
            button.setMaximumWidth(220)
            button.clicked.connect(
                lambda checked=False, value=rating: self._record_block_feedback(
                    recommendation, value
                )
            )
            rating_rows[index // 2].addWidget(button)
            self.feedback_buttons.append(button)
        for row in rating_rows:
            row.addStretch()
            feedback_layout.addLayout(row)
        self.feedback_frame.setVisible(False)
        self.routine_layout.addWidget(self.feedback_frame)

        actions = QHBoxLayout()
        self.open_quick_btn = QPushButton(
            "Start 3–5 min block" if recommendation["installed"] else "Download & start"
        )
        self.open_quick_btn.setObjectName("primaryButton")
        self.open_quick_btn.setToolTip(
            "Use Challenge mode so completed runs can be detected automatically."
        )
        self.open_quick_btn.clicked.connect(
            lambda: self._launch_quick_scenario(recommendation)
        )
        actions.addWidget(self.open_quick_btn)
        self.stop_quick_btn = QPushButton(
            "Stop warm-up" if recommendation["warmup"] else "Stop training"
        )
        self.stop_quick_btn.setObjectName("quietButton")
        self.stop_quick_btn.clicked.connect(
            lambda: self._stop_quick_session(recommendation)
        )
        self.stop_quick_btn.setVisible(False)
        actions.addWidget(self.stop_quick_btn)
        self.next_quick_btn = QPushButton(
            "Different warm-up" if recommendation["warmup"] else "Different pick"
        )
        self.next_quick_btn.setObjectName("quietButton")
        self.next_quick_btn.clicked.connect(
            lambda: self.show_quick_scenario(
                recommendation["warmup"], launch=False
            )
        )
        actions.addWidget(self.next_quick_btn)
        self.finish_quick_btn = QPushButton("Done for now")
        self.finish_quick_btn.setObjectName("primaryButton")
        self.finish_quick_btn.setToolTip("Your block is saved; minimize Aim Companion until later.")
        self.finish_quick_btn.clicked.connect(lambda: self.window().showMinimized())
        self.finish_quick_btn.setVisible(False)
        actions.addWidget(self.finish_quick_btn)
        actions.addStretch()
        more_btn = QToolButton()
        more_btn.setText("More")
        more_btn.setObjectName("quietButton")
        more_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        fallback_menu = QMenu(more_btn)
        details_action = QAction("Show recommendation details", fallback_menu)
        details_action.setCheckable(True)
        details_action.toggled.connect(self._toggle_pick_details)
        fallback_menu.addAction(details_action)
        copy_action = QAction("Copy scenario name", fallback_menu)
        copy_action.triggered.connect(
            lambda: QApplication.clipboard().setText(recommendation["scenario"])
        )
        fallback_menu.addAction(copy_action)
        self.manual_complete_btn = QAction(
            f"Mark {target_runs} "
            f"{'run' if target_runs == 1 else 'runs'} complete manually",
            fallback_menu,
        )
        self.manual_complete_btn.setToolTip(
            "Use only if automatic Kovaak's result detection is unavailable."
        )
        self.manual_complete_btn.triggered.connect(
            lambda: self._complete_quick_block(recommendation, advance=False)
        )
        fallback_menu.addAction(self.manual_complete_btn)
        more_btn.setMenu(fallback_menu)
        actions.addWidget(more_btn)
        self.routine_layout.addLayout(actions)
        self.routine_layout.invalidate()
        QTimer.singleShot(0, self._fit_routine_height)

    def _toggle_pick_details(self, visible):
        for widget in self.quick_detail_widgets:
            widget.setVisible(visible)
        QTimer.singleShot(0, self._fit_routine_height)

    def _generate(self):
        self.config.session_minutes = self.dur_spin.value()
        self.config.warmup_minutes = self.warmup_spin.value()
        self.config.cooldown_minutes = self.cd_spin.value()
        self.config.focus = self._get_focus_key()
        self.config.prioritize_installed = self.installed_check.isChecked()
        self.config.game = self.game_combo.currentText()
        self.config.save()

        routine = generate_routine(self.profile, self.config.session_minutes, config=self.config)
        self._current_routine = routine
        self.generate_btn.setText("Update routine")
        self.export_btn.setEnabled(True)
        self.export_btn.setVisible(True)

        self._clear_layout(self.routine_layout)

        if routine.get("authored_run_plan"):
            header_text = "hnA TacFPS routine ({} prescribed runs)".format(
                routine["training_minutes"]
            )
        else:
            header_text = "Routine ({} min)".format(routine["total_minutes"])
        header = QLabel(header_text)
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        self.routine_layout.addWidget(header)

        focus_lbl = QLabel("Focus: {}".format(routine["focus_label"]))
        focus_lbl.setStyleSheet("color: #fab387;")
        focus_lbl.setFont(QFont("Segoe UI", 10))
        focus_lbl.setWordWrap(True)
        self.routine_layout.addWidget(focus_lbl)

        if routine.get("source_routine"):
            source_lbl = QLabel("Based on: {}".format(routine["source_routine"]))
            source_lbl.setStyleSheet("color: #a6e3a1;")
            source_lbl.setFont(QFont("Segoe UI", 9))
            source_lbl.setWordWrap(True)
            self.routine_layout.addWidget(source_lbl)

        description_lbl = QLabel(routine.get("description", ""))
        description_lbl.setObjectName("mutedText")
        description_lbl.setWordWrap(True)
        self.routine_layout.addWidget(description_lbl)

        if not routine.get("authored_run_plan"):
            weakness_text = ", ".join(routine["weakness_areas"])
            if weakness_text:
                weakness_text = "Measured weaknesses: " + weakness_text
            else:
                weakness_text = "Complete benchmark runs to unlock weakness-based recommendations"
            weakness_lbl = QLabel(weakness_text)
            weakness_lbl.setStyleSheet("color: #a6adc8;")
            weakness_lbl.setFont(QFont("Segoe UI", 10))
            weakness_lbl.setWordWrap(True)
            self.routine_layout.addWidget(weakness_lbl)

        allocation = routine.get("focus_allocation")
        if allocation:
            support_categories = sorted({
                exercise.get("category", "")
                for exercise in routine["exercises"]
                if exercise.get("category") != allocation["primary_category"]
            })
            allocation_text = (
                f"Training split: {allocation['primary_minutes']} min on "
                f"{allocation['primary_skill']} · {allocation['support_minutes']} min "
                f"maintaining {' + '.join(support_categories) or 'other skills'}"
            )
            allocation_label = QLabel(allocation_text)
            allocation_label.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            allocation_label.setWordWrap(True)
            self.routine_layout.addWidget(allocation_label)

        source_guidance = routine.get("source_guidance", [])
        if source_guidance:
            source_frame = QFrame()
            source_frame.setObjectName("sourceRoutineGuide")
            source_layout = QVBoxLayout(source_frame)
            source_layout.setContentsMargins(14, 12, 14, 12)
            source_layout.setSpacing(6)
            source_title = QLabel("hnA TACFPS ROUTINE INSTRUCTIONS")
            source_title.setObjectName("fieldLabel")
            source_layout.addWidget(source_title)
            source_notice = QLabel(
                "Follow these instructions for the intended adaptation. "
                "The execution matters more than the aim-trainer score."
            )
            source_notice.setStyleSheet("color: #f9e2af; font-weight: bold;")
            source_notice.setWordWrap(True)
            source_layout.addWidget(source_notice)
            sensitivity = QLabel(routine.get("source_sensitivity", ""))
            sensitivity.setStyleSheet("color: #94e2d5;")
            sensitivity.setWordWrap(True)
            source_layout.addWidget(sensitivity)
            for index, instruction in enumerate(source_guidance, 1):
                instruction_label = QLabel(f"{index}. {instruction}")
                instruction_label.setObjectName("methodBody")
                instruction_label.setWordWrap(True)
                source_layout.addWidget(instruction_label)
            rotation = routine.get("source_rotation", "")
            if rotation:
                rotation_label = QLabel("Rotation: " + rotation)
                rotation_label.setObjectName("mutedText")
                rotation_label.setWordWrap(True)
                source_layout.addWidget(rotation_label)
            source_button = QPushButton("Open original hnA TacFPS guide")
            source_button.setObjectName("secondaryButton")
            source_button.clicked.connect(
                lambda checked=False, url=routine.get("source_url", ""):
                QDesktopServices.openUrl(QUrl(url))
            )
            source_layout.addWidget(source_button, 0, Qt.AlignmentFlag.AlignLeft)
            self.routine_layout.addWidget(source_frame)

        guide_frame = QFrame()
        guide_frame.setObjectName("routineGuide")
        guide_frame.setStyleSheet(
            "QFrame#routineGuide { background: #181825; border: 1px solid #45475a; "
            "border-left: 3px solid #89b4fa; border-radius: 7px; padding: 10px; }"
        )
        guide_layout = QVBoxLayout(guide_frame)
        guide_layout.setSpacing(5)
        guide_title = QLabel("How to run this routine")
        guide_title.setStyleSheet("color: #89b4fa; font-weight: bold;")
        guide_layout.addWidget(guide_title)
        theory = QLabel(routine.get("theory_summary", ""))
        theory.setStyleSheet("color: #cdd6f4;")
        theory.setWordWrap(True)
        guide_layout.addWidget(theory)
        mindset = QLabel(
            routine.get("practice_mode", "Learning Zone") + "  ·  "
            + routine.get("mindset_cue", "")
        )
        mindset.setStyleSheet("color: #cba6f7;")
        mindset.setWordWrap(True)
        guide_layout.addWidget(mindset)
        for cue in routine.get("session_cues", []):
            cue_label = QLabel("• " + cue)
            cue_label.setStyleSheet("color: #a6adc8;")
            cue_label.setWordWrap(True)
            guide_layout.addWidget(cue_label)
        progression = QLabel("Progression: " + routine.get("progression_guidance", ""))
        progression.setStyleSheet("color: #f9e2af; font-style: italic;")
        progression.setWordWrap(True)
        guide_layout.addWidget(progression)
        reflection = routine.get("reflection_prompt", [])
        if reflection:
            review = QLabel("Review  ·  " + "  →  ".join(reflection))
            review.setStyleSheet("color: #94e2d5;")
            review.setWordWrap(True)
            guide_layout.addWidget(review)
        if routine.get("break_guidance"):
            recovery = QLabel("Session quality  ·  " + routine["break_guidance"])
            recovery.setStyleSheet("color: #fab387;")
            recovery.setWordWrap(True)
            guide_layout.addWidget(recovery)
        if not source_guidance:
            self.routine_layout.addWidget(guide_frame)

        if routine["warmup_minutes"] > 0:
            warmup = QLabel("Warm-up · {} min".format(routine["warmup_minutes"]))
            warmup.setStyleSheet("color: #89b4fa;")
            warmup.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.routine_layout.addWidget(warmup)
            for exercise in routine.get("warmup_scenarios", []):
                warmup_row = QLabel(
                    "  {} · {} min{}".format(
                        exercise["scenario"], exercise["duration_min"],
                        " · installed" if exercise.get("installed") else "",
                    )
                )
                warmup_row.setStyleSheet("color: #a6adc8;")
                warmup_row.setWordWrap(True)
                self.routine_layout.addWidget(warmup_row)
                warmup_description = exercise.get("description", "")
                if warmup_description:
                    warmup_detail = QLabel("    Purpose: " + warmup_description)
                    warmup_detail.setObjectName("mutedText")
                    warmup_detail.setWordWrap(True)
                    self.routine_layout.addWidget(warmup_detail)

        training_label = (
            "Main training · {} prescribed runs".format(routine["training_minutes"])
            if routine.get("authored_run_plan") else
            "Main training · {} min".format(routine["training_minutes"])
        )
        training_header = QLabel(training_label)
        training_header.setStyleSheet("color: #cdd6f4;")
        training_header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.routine_layout.addWidget(training_header)

        shown_cues = set()
        for ex in routine["exercises"]:
            row = QHBoxLayout()
            row.setSpacing(12)

            scenario_lbl = QLabel(ex["scenario"])
            scenario_lbl.setStyleSheet("color: #cdd6f4; font-weight: bold;")
            scenario_lbl.setFont(QFont("Segoe UI", 10))
            scenario_lbl.setWordWrap(True)
            scenario_lbl.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
            )
            row.addWidget(scenario_lbl, 1)

            amount = (
                "{} runs".format(ex["prescribed_runs"])
                if ex.get("prescribed_runs") else
                "{} min".format(ex["duration_min"])
            )
            info = QLabel("{} [{}]".format(amount, ex["subcategory"]))
            info.setStyleSheet("color: #a6adc8;")
            info.setFont(QFont("Segoe UI", 9))
            row.addWidget(info)

            if ex["installed"]:
                inst = QLabel("INSTALLED")
                inst.setStyleSheet("color: #a6e3a1; font-weight: bold;")
                inst.setFont(QFont("Segoe UI", 9))
                row.addWidget(inst)
            else:
                dl = QLabel("DOWNLOAD")
                dl.setStyleSheet("color: #fab387;")
                dl.setFont(QFont("Segoe UI", 9))
                row.addWidget(dl)

            row.addStretch()
            self.routine_layout.addLayout(row)

            description = ex.get("description", "")
            if description:
                prefix = (
                    "    hnA instruction: "
                    if ex.get("authored_instruction") else
                    "    Purpose: "
                )
                description_label = QLabel(prefix + description)
                description_label.setObjectName("mutedText")
                description_label.setWordWrap(True)
                self.routine_layout.addWidget(description_label)

            coaching_cue = ex.get("coaching_cue", "")
            skill_key = (ex.get("category"), ex.get("subcategory"))
            if coaching_cue and skill_key not in shown_cues:
                shown_cues.add(skill_key)
                cue = QLabel("    Technique: " + coaching_cue)
                cue.setStyleSheet("color: #89b4fa;")
                cue.setFont(QFont("Segoe UI", 9))
                cue.setWordWrap(True)
                self.routine_layout.addWidget(cue)

        if routine["cooldown_minutes"] > 0:
            cd = QLabel("Cooldown: {} min".format(routine["cooldown_minutes"]))
            cd.setStyleSheet("color: #89b4fa;")
            cd.setFont(QFont("Segoe UI", 10))
            self.routine_layout.addWidget(cd)

        self.routine_layout.addStretch()
        for label in self.routine_frame.findChildren(QLabel):
            if label.wordWrap():
                label.setSizePolicy(
                    QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
                )
        self.routine_layout.invalidate()
        QTimer.singleShot(0, self._fit_routine_height)

    def _fit_routine_height(self):
        self.routine_frame.setMinimumHeight(0)
        self.routine_layout.activate()
        self.routine_frame.setMinimumHeight(
            max(84, self.routine_layout.sizeHint().height() + 24)
        )

    def _export(self):
        if not self._current_routine:
            return

        scenario_list = []
        all_exercises = (
            self._current_routine.get("warmup_scenarios", [])
            + self._current_routine["exercises"]
        )
        for ex in all_exercises:
            duration = ex["duration_min"]
            if ex.get("prescribed_runs"):
                count = ex["prescribed_runs"]
            elif duration <= 3:
                count = 1
            else:
                count = max(1, round(duration / 3))
            scenario_list.append({"name": ex["scenario"], "count": count})

        try:
            playlist_name = self._current_routine.get("source_playlist_name")
            if not playlist_name:
                playlist_name = "VT Routine - {}min".format(
                    self._current_routine["training_minutes"]
                )
            path = export_playlist(
                scenario_list,
                name=playlist_name,
                output_dir=KOVAAKS_PLAYLIST_DIR,
            )
            QMessageBox.information(
                self, "Exported!",
                "Playlist saved to Kovaaks:\n{}\n\n"
                "Restart Kovaaks, then find it under\nLocal Playlists.".format(path)
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", "Failed to export:\n{}".format(e))

    def update_profile(self, profile: PlayerProfile):
        self.profile = profile
        self._refresh_weekly_plan()
        self._refresh_game_observations()
        # Profile refreshes can happen while Kovaak's is active. Preserve the
        # current session card instead of rebuilding and losing its state.

    def reload_config(self):
        """Apply settings changed from the application-level settings dialog."""
        self.config = TrainingConfig.load()
        self._run_tracker.stats_dir = self.config.get_stats_dir()
        self.dur_spin.setValue(self.config.session_minutes)
        self.warmup_spin.setValue(self.config.warmup_minutes)
        self.cd_spin.setValue(self.config.cooldown_minutes)
        if self.config.game in get_game_options():
            self.game_combo.setCurrentText(self.config.game)
        context_index = self.warmup_context_combo.findText(self.config.warmup_context)
        if context_index >= 0:
            self.warmup_context_combo.setCurrentIndex(context_index)
        focus_index = self.focus_combo.findData(self.config.focus)
        if focus_index >= 0:
            self.focus_combo.setCurrentIndex(focus_index)
        self.installed_check.setChecked(self.config.prioritize_installed)
        self.fps_budget_spin.setValue(self.config.daily_fps_minutes)
        self._refresh_weekly_plan()
        self._update_sync_health()

    def _clear_layout(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.hide()
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
