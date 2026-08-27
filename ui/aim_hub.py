import os
import json
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QGridLayout, QTextEdit, QStackedWidget, QComboBox,
    QToolButton, QMenu, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont, QColor

from models.database import Database
from models.score import PlayerProfile
from models.benchmark import TIERS, score_to_energy, energy_to_tier
from core.recommender import (
    AIM_GLOSSARY, GUIDANCE, TACFPS_GUIDE, get_scenario_info, SCENARIOS,
)
from core.kovaaks_launcher import open_kovaaks
from core.playlist_export import export_playlist
from models.config import TrainingConfig
from core.warmups import RECOMMENDED_WARMUP_ROUTINE, RECOMMENDED_WARMUP_MINUTES

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

VDIM_SCHEDULE = {
    0: {"focus": "Clicking I", "subcats": ["Static", "Linear"], "color": "#4a9eff",
        "desc": "Smoothness & Precision clicking"},
    1: {"focus": "Clicking II", "subcats": ["Dynamic"], "color": "#4a9eff",
        "desc": "Speed clicking, overshoot training"},
    2: {"focus": "Tracking I", "subcats": ["Precise", "Reactive"], "color": "#44ff88",
        "desc": "Precision and reactive tracking"},
    3: {"focus": "Tracking II", "subcats": ["Control"], "color": "#44ff88",
        "desc": "Strafing and control tracking"},
    4: {"focus": "Switching I", "subcats": ["Speed", "Evasive"], "color": "#ff4444",
        "desc": "Target switching, speed + reactivity"},
    5: {"focus": "Switching II", "subcats": ["Stability"], "color": "#ff4444",
        "desc": "Evasive + stability switching"},
    6: {"focus": "Rest / Review", "subcats": [], "color": "#888888",
        "desc": "Review progress, plan next week, optional light practice"},
}

PLATEAU_CAUSES = [
    {
        "cause": "Wrong Sensitivity",
        "symptoms": "Scores keep dropping or feel inconsistent",
        "fix": "Stick with ONE sens for at least 2 weeks. Frequent changes prevent motor learning. "
               "Your current sensitivity is a personal preference — don't change it unless you're sure.",
        "diagnostic": "Try this: If your wrist is tense, you may be too high sens. If your arm is tired, too low.",
    },
    {
        "cause": "No Warm-up",
        "symptoms": "First few attempts are terrible, then you improve",
        "fix": "Always do 10-15 min warmup before any serious practice. "
               "Use slow tracking (smooth pursuit) first, then medium speed clicking, then target switching.",
        "diagnostic": "If your first 5 attempts are 10%+ below your average, you need a longer warmup.",
    },
    {
        "cause": "Fatigue / Overtraining",
        "symptoms": "Scores drop after 30 minutes, feel tired, can't focus",
        "fix": "Stop when scores start dropping. 30-45 min focused > 2 hours mindless grinding. "
               "Take 5-min breaks every 20 min. Sleep 7-9 hours.",
        "diagnostic": "Track when your scores peak. If it's after only 10 min and drops after 20, you're fatigued.",
    },
    {
        "cause": "Wrong Drill Mix",
        "symptoms": "Some scenarios improve but overall rank stalls",
        "fix": "Rotate between subcategories weekly. Don't just grind one type. "
               "Use the VDIM weekly rotation to cover everything.",
        "diagnostic": "Check your tier breakdown — if some categories are 2+ tiers above others, rebalance.",
    },
    {
        "cause": "No Game Transfer",
        "symptoms": "Kovaak's scores go up but in-game performance doesn't improve",
        "fix": "After every aim training session, spend 10-15 min in Deathmatch (Valorant/CS2). "
               "Focus on applying ONE technique per session. Review your VODs.",
        "diagnostic": "Record 5 games. Watch for: Are you overflicking? Underflicking? Not tracking?",
    },
    {
        "cause": "Hardware / Posture",
        "symptoms": "Inconsistent performance, arm/wrist pain, jittery aim",
        "fix": "Use 1000Hz+ mouse polling. Check your grip — don't squeeze too hard. "
               "Sit up straight. Wrist should hover, not press into desk.",
        "diagnostic": "Try different grip styles (palm, claw, fingertip). Consistency improves with comfort.",
    },
    {
        "cause": "Scenarios Too Hard/Easy",
        "symptoms": "Either getting 90%+ (too easy) or <30% (too hard) consistently",
        "fix": "Aim for 40-70% accuracy on scenarios. This is the 'zone of proximal development'. "
               "If too easy, increase difficulty by 1 tier. If too hard, decrease by 1 tier.",
        "diagnostic": "Look at your accuracy. 85%+ = too easy. 20% = too hard. Sweet spot is 40-70%.",
    },
    {
        "cause": "No Sleep / Nutrition",
        "symptoms": "Reaction time feels slow, aim is sluggish, can't focus",
        "fix": "Sleep is when motor skills consolidate. 7-9 hours minimum. "
               "Stay hydrated during sessions. Eat protein for recovery.",
        "diagnostic": "Track sleep vs. performance. Most people see 5-10% improvement with proper sleep.",
    },
]

FLICK_TECHNIQUES = [
    {
        "name": "Undershoot Bias (Recommended)",
        "desc": "Aim slightly short of target, then make a micro-adjustment. "
                "Better than overshooting because you never lose track of the target.",
        "when_to_use": "Most scenarios, especially static and linear. Good for beginners.",
    },
    {
        "name": "Dead Stop Technique",
        "desc": "Flick to target and stop dead. No correction needed. "
                "Requires precise initial flick calibration.",
        "when_to_use": "When you have consistent flick accuracy. Advanced technique.",
    },
    {
        "name": "Rebound Flick",
        "desc": "Flick past the target, then snap back. Works because the rebound "
                "is assisted by the mouse stopping naturally.",
        "when_to_use": "For long-distance flicks. Can feel more natural than dead stop.",
    },
    {
        "name": "Two-Step Flick",
        "desc": "First flick gets you close, second flick is a small correction. "
                "More consistent than one big flick.",
        "when_to_use": "Building consistency. Good transition from undershoot bias.",
    },
]

WARMUP_PROTOCOL = [
    {
        "name": step["scenario"], "scenario": step["scenario"],
        "duration": step["duration_min"],
        "color": "#44ff88" if step["category"] == "Tracking" else "#4a9eff",
        "desc": step["cue"],
    }
    for step in RECOMMENDED_WARMUP_ROUTINE
]


class AimHubWidget(QWidget):
    open_routine = pyqtSignal(str)
    open_scenarios = pyqtSignal()

    def __init__(self, profile: PlayerProfile, db: Database):
        super().__init__()
        self.profile = profile
        self.db = db
        self._warmup_timer = QTimer()
        self._warmup_timer.timeout.connect(self._tick_warmup)
        self._warmup_seconds_left = 0
        self._warmup_step = 0
        self._build_ui()
        self._populate_all()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 8, 12)
        self.content_layout.setSpacing(12)
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def _populate_all(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._add_voltaic_foundations()
        self._add_tacfps_guide()
        self._add_technique_library()
        self._add_issue_and_transfer_guidance()
        self._add_mindset_and_glossary()
        self.content_layout.addStretch()

    def _card(self, title, color="#ffffff", expanded=False):
        frame = QFrame()
        frame.setObjectName("aimHubCard")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(f"""
            QFrame#aimHubCard {{
                background-color: #11192b;
                border-radius: 12px;
                border: 1px solid #202a40;
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 12, 18, 14)
        layout.setSpacing(6)

        if title:
            toggle = QToolButton()
            toggle.setText(("▾  " if expanded else "›  ") + title)
            toggle.setCheckable(True)
            toggle.setChecked(expanded)
            toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
            toggle.setStyleSheet(
                f"QToolButton {{ color: {color}; font-size: 12pt; font-weight: bold; "
                "text-align: left; border: none; padding: 4px 0; }}"
            )
            layout.addWidget(toggle)
            body = QWidget()
            body_layout = QVBoxLayout(body)
            body_layout.setContentsMargins(0, 8, 0, 0)
            body_layout.setSpacing(8)
            body.setVisible(expanded)
            toggle.toggled.connect(body.setVisible)
            toggle.toggled.connect(
                lambda checked, button=toggle, name=title: button.setText(
                    ("▾  " if checked else "›  ") + name
                )
            )
            layout.addWidget(body)
            return frame, body_layout

        return frame, layout

    def _text(self, text, color="#dddddd", bold=False, size=11):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        weight = QFont.Weight.Bold if bold else QFont.Weight.Normal
        lbl.setFont(QFont("Segoe UI", size, weight))
        lbl.setStyleSheet(f"color: {color}; font-size: {size}pt;")
        return lbl

    def _add_voltaic_foundations(self):
        card, layout = self._card("How to practise a routine", "#89b4fa", expanded=True)
        layout.addWidget(self._text(
            GUIDANCE["session_method"]["summary"], "#cdd6f4", bold=True
        ))
        for index, step in enumerate(GUIDANCE["session_method"]["steps"], 1):
            layout.addWidget(self._text(f"{index}. {step}", "#bac2de", size=10))

        summary_row = QHBoxLayout()
        principle = QFrame()
        principle.setObjectName("guideSummary")
        principle_layout = QVBoxLayout(principle)
        principle_layout.addWidget(self._text("Technique first", "#a6e3a1", True, 11))
        principle_layout.addWidget(self._text(GUIDANCE["principles"][0], "#a6adc8", size=10))
        summary_row.addWidget(principle, 1)
        progression = QFrame()
        progression.setObjectName("guideSummary")
        progression_layout = QVBoxLayout(progression)
        progression_layout.addWidget(self._text("Progress deliberately", "#f9e2af", True, 11))
        progression_layout.addWidget(self._text(
            GUIDANCE["difficulty_and_progression"]["summary"], "#a6adc8", size=10
        ))
        summary_row.addWidget(progression, 1)
        layout.addLayout(summary_row)

        source_label = QLabel(
            "Original resources: " + " · ".join(
                f'<a href="{source["url"]}" style="color:#89b4fa">{source["title"]}</a>'
                for source in GUIDANCE["sources"]
            )
        )
        source_label.setWordWrap(True)
        source_label.setOpenExternalLinks(True)
        source_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(source_label)
        source_label.hide()
        sources = QToolButton()
        sources.setText(f"Original references ({len(GUIDANCE['sources'])})  ▾")
        sources.setObjectName("quietButton")
        sources.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        source_menu = QMenu(sources)
        for source in GUIDANCE["sources"]:
            action = source_menu.addAction(source["title"])
            action.triggered.connect(
                lambda checked=False, url=source["url"]: QDesktopServices.openUrl(QUrl(url))
            )
        sources.setMenu(source_menu)
        layout.addWidget(sources, 0, Qt.AlignmentFlag.AlignLeft)
        self.content_layout.addWidget(card)

    def _add_tacfps_guide(self):
        card, layout = self._card(
            "TacFPS: speed, stopping, and clean pathing", "#f9e2af"
        )
        layout.addWidget(self._text(TACFPS_GUIDE["scope"], "#cdd6f4", True, 10))

        for concept in TACFPS_GUIDE["concepts"]:
            layout.addWidget(self._text("- " + concept, "#bac2de", size=10))

        layout.addWidget(self._text("PRACTICE RULES", "#71809b", True, 9))
        for rule in TACFPS_GUIDE["practice_rules"]:
            layout.addWidget(self._text("- " + rule, "#a6adc8", size=10))

        self.tacfps_routine_combo = QComboBox()
        for routine in TACFPS_GUIDE["routines"]:
            self.tacfps_routine_combo.addItem(routine["name"], routine)
        layout.addWidget(self.tacfps_routine_combo)
        self.tacfps_routine_summary = self._text("", "#f9e2af", True, 10)
        self.tacfps_exercises = self._text("", "#bac2de", size=10)
        layout.addWidget(self.tacfps_routine_summary)
        layout.addWidget(self.tacfps_exercises)
        self.tacfps_routine_combo.currentIndexChanged.connect(
            self._update_tacfps_routine
        )
        self._update_tacfps_routine()

        actions = QHBoxLayout()
        install = QPushButton("Install 3 Aimgud routines")
        install.setObjectName("primaryButton")
        install.clicked.connect(self._install_tacfps_playlists)
        actions.addWidget(install)
        source = QPushButton("Open original guide")
        source.setObjectName("quietButton")
        source.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(TACFPS_GUIDE["source_url"]))
        )
        actions.addWidget(source)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addWidget(self._text(
            "Rotation: " + TACFPS_GUIDE["rotation"], "#94e2d5", size=10
        ))
        self.content_layout.addWidget(card)

    def _update_tacfps_routine(self):
        routine = self.tacfps_routine_combo.currentData()
        if not routine:
            return
        self.tacfps_routine_summary.setText(
            f"{routine['description']} {routine['sensitivity']}"
        )
        lines = [
            f"{exercise['duration']}  |  {exercise['scenario']}\n"
            f"    {exercise['focus']}"
            for exercise in routine["exercises"]
        ]
        self.tacfps_exercises.setText("\n".join(lines))

    def _install_tacfps_playlists(self):
        output_dir = TrainingConfig.load().get_playlists_dir()
        paths = []
        try:
            for routine in TACFPS_GUIDE["routines"]:
                scenarios = [
                    {
                        "name": exercise["scenario"],
                        "count": exercise["duration_min"],
                    }
                    for exercise in routine["exercises"]
                ]
                paths.append(export_playlist(
                    scenarios,
                    name=routine["playlist_name"],
                    output_dir=output_dir,
                ))
        except OSError as error:
            QMessageBox.critical(self, "Could not install routines", str(error))
            return

        launched = open_kovaaks()
        message = QMessageBox(self)
        message.setWindowTitle("Aimgud routines installed")
        message.setIcon(QMessageBox.Icon.Information)
        message.setText("Installed all three Aimgud routines in Kovaak's Local Playlists.")
        message.setInformativeText(
            "Open Local Playlists and select a routine. Kovaak's will fetch any "
            "referenced scenarios that are missing."
            + ("" if launched else " Open Kovaak's manually to continue.")
        )
        message.setDetailedText("\n".join(paths))
        message.exec()

    def _add_technique_library(self):
        card, layout = self._card("Technique by skill", "#94e2d5", expanded=True)
        layout.addWidget(self._text(
            "Choose the category shown beside an exercise to see its goal and execution cue.",
            "#a6adc8", size=10,
        ))
        self.skill_combo = QComboBox()
        for key, guidance in GUIDANCE["categories"].items():
            self.skill_combo.addItem(guidance["title"], key)
        layout.addWidget(self.skill_combo, 0, Qt.AlignmentFlag.AlignLeft)
        detail = QFrame()
        detail.setObjectName("guideDetail")
        detail_layout = QVBoxLayout(detail)
        self.skill_goal = self._text("", "#cdd6f4", size=10)
        self.skill_do = self._text("", "#a6e3a1", size=10)
        self.skill_avoid = self._text("", "#f38ba8", size=10)
        self.skill_progress = self._text("", "#f9e2af", size=10)
        for label in (self.skill_goal, self.skill_do, self.skill_avoid, self.skill_progress):
            detail_layout.addWidget(label)
        layout.addWidget(detail)
        self.skill_combo.currentIndexChanged.connect(self._update_skill_guidance)
        self._update_skill_guidance()
        self.content_layout.addWidget(card)

    def _update_skill_guidance(self):
        guidance = GUIDANCE["categories"].get(self.skill_combo.currentData(), {})
        self.skill_goal.setText("Goal  ·  " + guidance.get("goal", ""))
        self.skill_do.setText("Do  ·  " + guidance.get("cue", ""))
        self.skill_avoid.setText("Avoid  ·  " + guidance.get("avoid", ""))
        self.skill_progress.setText("Progress  ·  " + guidance.get("progress", ""))

    def _add_issue_and_transfer_guidance(self):
        card, layout = self._card("Target a problem or a game", "#fab387")
        layout.addWidget(self._text(
            "Issue routines isolate a recurring control problem. Game routines choose a "
            "useful drill mix, but the skill still has to be integrated with movement, "
            "positioning, and decisions inside the game.", "#a6adc8", size=10,
        ))

        selector_row = QHBoxLayout()
        issue_block = QVBoxLayout()
        issue_block.addWidget(self._text("ISSUE ROUTINE", "#71809b", True, 9))
        self.issue_combo = QComboBox()
        self.issue_combo.addItems(GUIDANCE["issues"].keys())
        issue_block.addWidget(self.issue_combo)
        selector_row.addLayout(issue_block, 1)
        game_block = QVBoxLayout()
        game_block.addWidget(self._text("GAME TRANSFER", "#71809b", True, 9))
        self.transfer_combo = QComboBox()
        self.transfer_combo.addItems(GUIDANCE["game_transfer"].keys())
        game_block.addWidget(self.transfer_combo)
        selector_row.addLayout(game_block, 1)
        layout.addLayout(selector_row)
        self.issue_guidance_label = self._text("", "#fab387", size=10)
        self.transfer_guidance_label = self._text("", "#89b4fa", size=10)
        layout.addWidget(self.issue_guidance_label)
        layout.addWidget(self.transfer_guidance_label)
        self.issue_combo.currentTextChanged.connect(self._update_context_guidance)
        self.transfer_combo.currentTextChanged.connect(self._update_context_guidance)
        self._update_context_guidance()
        self.content_layout.addWidget(card)

    def _update_context_guidance(self):
        issue = self.issue_combo.currentText()
        game = self.transfer_combo.currentText()
        self.issue_guidance_label.setText(
            issue + "  ·  " + GUIDANCE["issues"].get(issue, "")
        )
        self.transfer_guidance_label.setText(
            game + "  ·  " + GUIDANCE["game_transfer"].get(game, "")
        )

    def _add_mindset_and_glossary(self):
        card, layout = self._card("Practice mindset and terminology", "#cba6f7")
        zones = QHBoxLayout()
        learning = QFrame()
        learning.setObjectName("guideSummary")
        learning_layout = QVBoxLayout(learning)
        learning_layout.addWidget(self._text("Learning Zone", "#cba6f7", True, 11))
        learning_layout.addWidget(self._text(
            GUIDANCE["mindset"]["learning_zone"], "#a6adc8", size=10
        ))
        zones.addWidget(learning, 1)
        performance = QFrame()
        performance.setObjectName("guideSummary")
        performance_layout = QVBoxLayout(performance)
        performance_layout.addWidget(self._text("Performance Zone", "#89b4fa", True, 11))
        performance_layout.addWidget(self._text(
            GUIDANCE["mindset"]["performance_zone"], "#a6adc8", size=10
        ))
        zones.addWidget(performance, 1)
        layout.addLayout(zones)

        reflection = "  →  ".join(GUIDANCE["mindset"]["reflection_prompt"])
        layout.addWidget(self._text("Review each block  ·  " + reflection, "#94e2d5", True, 10))
        layout.addWidget(self._text(
            "Reset  ·  " + GUIDANCE["mindset"]["reset_action"], "#f9e2af", size=10
        ))

        glossary_row = QHBoxLayout()
        glossary_label = QLabel("TERM")
        glossary_label.setObjectName("fieldLabel")
        glossary_row.addWidget(glossary_label)
        self.glossary_combo = QComboBox()
        self.glossary_combo.addItems(AIM_GLOSSARY["terms"].keys())
        glossary_row.addWidget(self.glossary_combo, 1)
        layout.addLayout(glossary_row)
        self.glossary_definition = self._text("", "#bac2de", size=10)
        layout.addWidget(self.glossary_definition)
        self.glossary_combo.currentTextChanged.connect(self._update_glossary_definition)
        self._update_glossary_definition()
        self.content_layout.addWidget(card)

    def _update_glossary_definition(self):
        term = self.glossary_combo.currentText()
        self.glossary_definition.setText(
            term + "  ·  " + AIM_GLOSSARY["terms"].get(term, "")
        )

    def _add_today_focus(self):
        today = datetime.now().weekday()
        day_info = VDIM_SCHEDULE.get(today, VDIM_SCHEDULE[0])

        card, layout = self._card(f"Today: {day_info['focus']}", day_info["color"])
        layout.addWidget(self._text(day_info["desc"], "#cccccc"))

        if day_info["subcats"]:
            subcats_text = "Focus areas: " + " & ".join(day_info["subcats"])
            layout.addWidget(self._text(subcats_text, day_info["color"], bold=True))

            scenarios = self._get_scenarios_for_subcats(day_info["subcats"])
            if scenarios:
                layout.addWidget(self._text("\nSuggested scenarios:", "#aaaaaa", bold=True))
                for s in scenarios[:5]:
                    layout.addWidget(self._text(f"  {s['name']}", "#cccccc"))

            if self.profile:
                for cat in self.profile.categories:
                    for sub in cat.subcategories:
                        if sub.name in day_info["subcats"]:
                            energy = sub.energy
                            tier = energy_to_tier(energy)
                            layout.addWidget(self._text(
                                f"  {sub.name}: {sub.combined_score:.0f} ({tier})", "#888888"
                            ))
        else:
            layout.addWidget(self._text("Rest day! Review your progress and plan next week.", "#888888"))

        self.content_layout.addWidget(card)

    def _add_weekly_rotation(self):
        card, layout = self._card("VDIM Weekly Rotation", "#bb88ff")
        layout.addWidget(self._text(
            "Voltaic's recommended weekly schedule. Each day targets specific subcategories.",
            "#aaaaaa"
        ))

        today = datetime.now().weekday()
        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        grid = QGridLayout()
        grid.setSpacing(6)

        for i, day_name in enumerate(days):
            info = VDIM_SCHEDULE[i]
            is_today = (i == today)

            day_card = QFrame()
            bg = "#2a2a3e" if is_today else "#1a1a2e"
            border = f"2px solid {info['color']}" if is_today else "1px solid #333"
            day_card.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg};
                    border-radius: 6px;
                    padding: 8px;
                    border: {border};
                }}
            """)
            day_layout = QVBoxLayout(day_card)
            day_layout.setSpacing(4)

            day_label = QLabel(day_name)
            day_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            day_label.setStyleSheet(f"color: {info['color']};")
            if is_today:
                day_label.setText(f"  {day_name}  (TODAY)")
            day_layout.addWidget(day_label)

            focus_label = QLabel(info["focus"])
            focus_label.setStyleSheet("color: #ddd; font-size: 10pt;")
            day_layout.addWidget(focus_label)

            if info["subcats"]:
                subs = QLabel(", ".join(info["subcats"]))
                subs.setStyleSheet("color: #999; font-size: 9pt;")
                day_layout.addWidget(subs)

            grid.addWidget(day_card, 0, i)

        layout.addLayout(grid)
        self.content_layout.addWidget(card)

    def _add_warmup_protocol(self):
        card, layout = self._card("Structured Warmup Protocol", "#44ff88")
        layout.addWidget(self._text(
            "Always warm up before serious practice. Start slow, build speed gradually. "
            f"Complete the scenarios in order. Total time: {RECOMMENDED_WARMUP_MINUTES} minutes.",
            "#aaaaaa"
        ))

        for i, step in enumerate(WARMUP_PROTOCOL):
            step_card = QFrame()
            step_card.setStyleSheet(f"""
                QFrame {{
                    background-color: #1a1a2e;
                    border-radius: 6px;
                    padding: 10px;
                    border-left: 3px solid {step['color']};
                }}
            """)
            step_layout = QHBoxLayout(step_card)

            num_label = QLabel(f"Step {i + 1}")
            num_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            num_label.setStyleSheet(f"color: {step['color']};")
            num_label.setFixedWidth(50)
            step_layout.addWidget(num_label)

            info_layout = QVBoxLayout()
            info_layout.addWidget(self._text(step["name"], step["color"], bold=True, size=11))
            info_layout.addWidget(self._text(step["desc"], "#cccccc", size=10))

            dur_label = QLabel(f"{step['duration']} min")
            dur_label.setStyleSheet(f"color: {step['color']}; font-size: 10pt; font-weight: bold;")
            dur_label.setFixedWidth(50)
            dur_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            step_layout.addLayout(info_layout)
            step_layout.addWidget(dur_label)

            layout.addWidget(step_card)

        self.content_layout.addWidget(card)

    def _add_y4mz_playlist(self):
        card, layout = self._card("Y4MZ Practical Playlist (Full Routine)", "#ffaa00")
        layout.addWidget(self._text(
            "Complete warmup routine with technique instructions. Play all on 103 Overwatch FOV. "
            "Each scenario 3x through. ~27 min total.",
            "#aaaaaa"
        ))

        playlist = [
            {"name": "Extra Controlsphere", "technique": "Make heavy use of both smooth wrist and arm movements in a slow and controlled manner. Your goal is to be as smooth as possible. If you find the target too small to stay smooth, use an easier version.", "goal": "As high accuracy as you can get"},
            {"name": "RawMouseControlClicking3", "technique": "Small movements around the distance you would adjust when holding an angle. Fast-paced clicking now which will slow down later.", "goal": "> 90% accuracy"},
            {"name": "1w2ts Micro++", "technique": "Similar to previous, but with slightly expanded angles. Wide swings, off angles, etc.", "goal": "> 90% accuracy"},
            {"name": "Reflex Micro++ flick reload small", "technique": "Same as previous but one less target and now reflex, working to improve reactions and making clean lines target to target. Pushing for score is not as important as clean flicks.", "goal": "> 80% accuracy"},
            {"name": "beanClick Micro 30% Smaller", "technique": "Once again focusing on accuracy, now leading your shots slightly or quickly adjusting to compensate for target movement. Fairly small at max range, normal size version is a good alternative if you're struggling to maintain accuracy.", "goal": ">75% accuracy"},
            {"name": "1w2t smallflicks small 60s", "technique": "Further expanding our angles, just about as wide as I think is reasonable to practice in a real game outside of going for frag movie clips or insanely lucky shots. Take your time, worry about speed later.", "goal": ">90% accuracy"},
            {"name": "skyClick Heads", "technique": "Wider angles, more targets, now moving again. Try the 30% larger version if you're having difficulty or experiencing frustration.", "goal": ">75% accuracy"},
            {"name": "Valorant Peek Strafing Robots", "technique": "Strafe back and forth between the middle wall, counter strafe and try to 1 tap or burst fire your target down. Don't spray and don't run and gun. Only headshots kill.", "goal": "Be honest with yourself and don't cheat yourself for score gains"},
            {"name": "Revolving Tracking Strafes", "technique": "Track the bot as smoothly as possible. Staying smooth with a little reactivity, large arm movements to finish warming up before going into games. Try the 80% version if it's too fast.", "goal": "Smooth tracking"},
        ]

        for i, item in enumerate(playlist):
            item_card = QFrame()
            item_card.setStyleSheet(f"""
                QFrame {{
                    background-color: #1a1a2e;
                    border-radius: 6px;
                    padding: 10px;
                    border-left: 3px solid #ffaa00;
                }}
            """)
            item_layout = QVBoxLayout(item_card)
            item_layout.setSpacing(4)

            name_row = QHBoxLayout()
            num = QLabel(f"{i + 1}.")
            num.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            num.setStyleSheet("color: #ffaa00;")
            num.setFixedWidth(20)
            name_lbl = QLabel(item["name"])
            name_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            name_lbl.setStyleSheet("color: #ffaa00;")
            name_row.addWidget(num)
            name_row.addWidget(name_lbl)
            name_row.addStretch()
            item_layout.addLayout(name_row)

            item_layout.addWidget(self._text(item["technique"], "#cccccc", size=10))
            item_layout.addWidget(self._text(f"Goal: {item['goal']}", "#44ff88", size=9))

            layout.addWidget(item_card)

        layout.addWidget(self._text(
            "Credits: Voltaic - canner, jborgor, patys, Gored, Pauer, Fallen, Daan, Empyrean, "
            "Hasin, Viscose, MrChang, HotRodRe, sini, clover, Y4MZ",
            "#666666", size=9
        ))

        self.content_layout.addWidget(card)

    def _add_recommended_by_category(self):
        card, layout = self._card("Recommended Scenarios by Category", "#bb88ff")
        layout.addWidget(self._text(
            "Voltaic's recommended scenarios organized by what they train. "
            "Pick 3-5 from each category you're weak in.",
            "#aaaaaa"
        ))

        rec_path = os.path.join(DATA_DIR, "recommended_scenarios.json")
        if os.path.exists(rec_path):
            with open(rec_path, "r") as f:
                rec_data = json.load(f)

            categories = rec_data.get("categories", {})
            for cat_key, cat_info in categories.items():
                cat_card = QFrame()
                cat_card.setStyleSheet(f"""
                    QFrame {{
                        background-color: #1a1a2e;
                        border-radius: 6px;
                        padding: 10px;
                        border-left: 3px solid {cat_info.get('color', '#bb88ff')};
                    }}
                """)
                cat_layout = QVBoxLayout(cat_card)
                cat_layout.setSpacing(4)

                cat_layout.addWidget(self._text(
                    cat_info["name"], cat_info.get("color", "#bb88ff"), bold=True, size=11
                ))

                scenarios = cat_info.get("scenarios", [])
                for s in scenarios[:8]:
                    cat_layout.addWidget(self._text(f"  {s}", "#cccccc", size=10))
                if len(scenarios) > 8:
                    cat_layout.addWidget(self._text(
                        f"  +{len(scenarios) - 8} more...", "#888888", size=9
                    ))

                layout.addWidget(cat_card)

        self.content_layout.addWidget(card)

    def _add_four_week_cycle(self):
        card, layout = self._card("4-Week Training Cycle", "#ffaa00")
        layout.addWidget(self._text(
            "Optimal cycle: Benchmark Week -> Focused Work (70% weak, 30% strong) -> "
            "Deload -> Re-benchmark. Repeat.",
            "#aaaaaa"
        ))

        weeks = [
            ("Week 1", "Benchmark & Assess", "Run all VT benchmarks. Identify weak spots. Set goals.",
             "#4a9eff"),
            ("Week 2", "Focused Training", "70% time on weaknesses, 30% on strengths. Push difficulty.",
             "#44ff88"),
            ("Week 3", "Progressive Overload", "Increase scenario difficulty. Add corrections. Build speed.",
             "#ff9944"),
            ("Week 4", "Deload & Re-test", "Light week. Re-benchmark. Compare to Week 1.",
             "#ff4444"),
        ]

        for week_name, title, desc, color in weeks:
            week_card = QFrame()
            week_card.setStyleSheet(f"""
                QFrame {{
                    background-color: #1a1a2e;
                    border-radius: 6px;
                    padding: 10px;
                    border-left: 3px solid {color};
                }}
            """)
            week_layout = QHBoxLayout(week_card)

            week_lbl = QLabel(week_name)
            week_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            week_lbl.setStyleSheet(f"color: {color};")
            week_lbl.setFixedWidth(70)
            week_layout.addWidget(week_lbl)

            info_layout = QVBoxLayout()
            info_layout.addWidget(self._text(title, color, bold=True, size=11))
            info_layout.addWidget(self._text(desc, "#cccccc", size=10))
            week_layout.addLayout(info_layout)

            layout.addWidget(week_card)

        layout.addWidget(self._text(
            "Key insight: Progress is NON-LINEAR. Small fluctuations are normal. "
            "Focus on the trend over 3-4 weeks, not individual sessions.",
            "#ffaa00", bold=True
        ))

        self.content_layout.addWidget(card)

    def _add_plateau_diagnostic(self):
        card, layout = self._card("Plateau Diagnostic (8 Common Causes)", "#ff4444")
        layout.addWidget(self._text(
            "If scores stall for 2+ weeks, one of these is probably the cause.",
            "#aaaaaa"
        ))

        for i, cause in enumerate(PLATEAU_CAUSES):
            cause_card = QFrame()
            cause_card.setStyleSheet(f"""
                QFrame {{
                    background-color: #1a1a2e;
                    border-radius: 6px;
                    padding: 10px;
                    border: 1px solid #333;
                }}
            """)
            cause_layout = QVBoxLayout(cause_card)
            cause_layout.setSpacing(4)

            cause_layout.addWidget(self._text(
                f"{i + 1}. {cause['cause']}", "#ff4444", bold=True, size=11
            ))
            cause_layout.addWidget(self._text(
                f"Symptoms: {cause['symptoms']}", "#cccccc", size=10
            ))
            cause_layout.addWidget(self._text(
                f"Fix: {cause['fix']}", "#44ff88", size=10
            ))
            cause_layout.addWidget(self._text(
                f"Diagnostic: {cause['diagnostic']}", "#4a9eff", size=9
            ))

            layout.addWidget(cause_card)

        self.content_layout.addWidget(card)

    def _add_flick_techniques(self):
        card, layout = self._card("Flick Techniques", "#bb88ff")
        layout.addWidget(self._text(
            "Different techniques for different situations. Undershoot bias is recommended for most people.",
            "#aaaaaa"
        ))

        for tech in FLICK_TECHNIQUES:
            tech_card = QFrame()
            tech_card.setStyleSheet(f"""
                QFrame {{
                    background-color: #1a1a2e;
                    border-radius: 6px;
                    padding: 10px;
                    border-left: 3px solid #bb88ff;
                }}
            """)
            tech_layout = QVBoxLayout(tech_card)

            tech_layout.addWidget(self._text(tech["name"], "#bb88ff", bold=True, size=11))
            tech_layout.addWidget(self._text(tech["desc"], "#cccccc", size=10))
            tech_layout.addWidget(self._text(f"When: {tech['when_to_use']}", "#888888", size=9))

            layout.addWidget(tech_card)

        layout.addWidget(self._text(
            "Common mistake: Rushing long flicks. Take your time on the first flick. "
            "Wrist for short flicks, arm for long ones.",
            "#ffaa00", bold=True
        ))

        self.content_layout.addWidget(card)

    def _add_game_transfer(self):
        card, layout = self._card("Game Transfer (Critical!)", "#ff9944")
        layout.addWidget(self._text(
            "Kovaak's scores mean nothing if they don't transfer to your game. "
            "After every training session, do this:",
            "#aaaaaa"
        ))

        transfer_steps = [
            ("Deathmatch (10-15 min)", "Play 1-2 DMs. Focus on applying ONE technique from today's training."),
            ("VOD Review (5 min)", "Watch your last game. Did you overflick? Underflick? Miss tracking?"),
            ("Crosshair Placement", "In-game, keep crosshair at head level. Pre-aim common angles."),
            ("Movement + Aim", "Practice counter-strafing while aiming. Don't stand still."),
        ]

        for title, desc in transfer_steps:
            step_card = QFrame()
            step_card.setStyleSheet(f"""
                QFrame {{
                    background-color: #1a1a2e;
                    border-radius: 6px;
                    padding: 10px;
                    border-left: 3px solid #ff9944;
                }}
            """)
            step_layout = QVBoxLayout(step_card)
            step_layout.addWidget(self._text(title, "#ff9944", bold=True, size=11))
            step_layout.addWidget(self._text(desc, "#cccccc", size=10))
            layout.addWidget(step_card)

        layout.addWidget(self._text(
            "5-min VOD review is more valuable than 5 more minutes of Kovaak's.",
            "#ff9944", bold=True
        ))

        self.content_layout.addWidget(card)

    def _add_session_tips(self):
        card, layout = self._card("Research-Backed Session Tips", "#4a9eff")

        tips = [
            "Keep sessions under 45 min. Aim improvement is neurological — CNS fatigues fast.",
            "If scores drop 10%+ from your peak, STOP. You're reinforcing bad habits.",
            "Practice at 80% speed first. Build speed AFTER accuracy.",
            "Don't change sensitivity during a plateau. Stick with it for 2+ weeks.",
            "Sleep 7-9 hours. Motor skills consolidate during sleep.",
            "Stay hydrated during sessions. Dehydration = slower reaction time.",
            "Train at the same time each day. Consistent schedule = consistent results.",
            "Quality > Quantity. 20 focused minutes > 2 hours of autopilot.",
        ]

        for tip in tips:
            layout.addWidget(self._text(f"  {tip}", "#cccccc", size=10))

        self.content_layout.addWidget(card)

    def _get_scenarios_for_subcats(self, subcats):
        results = []
        for s in SCENARIOS:
            if s.get("subcategory") in subcats:
                results.append(s)
        results.sort(key=lambda x: x.get("difficulty", 0))
        return results[:8]

    def _tick_warmup(self):
        if self._warmup_seconds_left <= 0:
            self._warmup_timer.stop()
            return
        self._warmup_seconds_left -= 1

    def update_profile(self, profile):
        self.profile = profile
        self._populate_all()
