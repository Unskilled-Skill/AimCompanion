"""Guided training session destination."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .scenario_guide import ScenarioGuideWidget


class SessionWidget(QWidget):
    """Render session state and emit user intents without owning session state."""

    launch_requested = pyqtSignal()
    manual_run_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    restart_requested = pyqtSignal()
    next_requested = pyqtSignal()
    warmup_requested = pyqtSignal()
    step_by_step_requested = pyqtSignal()
    full_routine_requested = pyqtSignal()
    overlay_enabled_changed = pyqtSignal(bool)
    recheck_scenario_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._view_model = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.session_stack = QStackedWidget()
        self.session_stack.setObjectName("sessionStack")
        self.empty_state = self._build_empty_state()
        self.active_session = self._build_active_session()
        self.session_stack.addWidget(self.empty_state)
        self.session_stack.addWidget(self.active_session)
        self.session_stack.setCurrentWidget(self.empty_state)
        root.addWidget(self.session_stack)

        self.launch_button.clicked.connect(self.launch_requested)
        self.manual_button.clicked.connect(self.manual_run_requested)
        self.pause_button.clicked.connect(self.pause_requested)
        self.stop_button.clicked.connect(self.stop_requested)
        self.restart_button.clicked.connect(self.restart_requested)
        self.next_button.clicked.connect(self.next_requested)
        self.warmup_button.clicked.connect(self.warmup_requested)
        self.step_button.clicked.connect(self.step_by_step_requested)
        self.full_button.clicked.connect(self.full_routine_requested)
        self.overlay_checkbox.toggled.connect(self.overlay_enabled_changed)
        self.recheck_button.clicked.connect(self.recheck_scenario_requested)

    def _build_empty_state(self):
        page = QWidget()
        page.setObjectName("sessionEmptyState")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 30, 8, 20)
        layout.setSpacing(18)

        hero = QFrame()
        hero.setObjectName("sessionEmptyHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 26, 28, 26)
        eyebrow = QLabel("READY WHEN YOU ARE")
        eyebrow.setObjectName("sessionEyebrow")
        title = QLabel("What do you want to train?")
        title.setObjectName("sessionEmptyTitle")
        copy = QLabel(
            "Choose a session type. Aim Companion will build the routine and guide "
            "you through every scenario."
        )
        copy.setObjectName("sessionSupportingText")
        copy.setWordWrap(True)
        hero_layout.addWidget(eyebrow)
        hero_layout.addWidget(title)
        hero_layout.addWidget(copy)
        layout.addWidget(hero)

        choices = QHBoxLayout()
        choices.setSpacing(14)
        warmup_card, self.warmup_button = self._mode_card(
            "QUICK PREP", "Warm-up",
            "Prepare your aim for a game or for the routine you plan to train.",
            "Start warm-up",
        )
        step_card, self.step_button = self._mode_card(
            "ADAPTIVE · RECOMMENDED", "Step-by-Step",
            "Train one recommended weakness at a time and stop whenever you need.",
            "Start step-by-step", featured=True,
        )
        full_card, self.full_button = self._mode_card(
            "STRUCTURED", "Full Routine",
            "Complete every scenario in a source-backed routine from start to finish.",
            "Start full routine",
        )
        choices.addWidget(warmup_card, 1, Qt.AlignmentFlag.AlignTop)
        choices.addWidget(step_card, 1, Qt.AlignmentFlag.AlignTop)
        choices.addWidget(full_card, 1, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(choices)
        layout.addStretch()
        return page

    @staticmethod
    def _mode_card(eyebrow, title, copy, button_text, featured=False):
        card = QFrame()
        card.setObjectName("sessionModeCard")
        card.setProperty("featured", featured)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(9)
        eyebrow_label = QLabel(eyebrow)
        eyebrow_label.setObjectName("sessionEyebrow")
        title_label = QLabel(title)
        title_label.setObjectName("sessionModeTitle")
        copy_label = QLabel(copy)
        copy_label.setObjectName("sessionSupportingText")
        copy_label.setWordWrap(True)
        button = QPushButton(button_text)
        button.setAccessibleName(button_text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if featured:
            button.setObjectName("primaryButton")
        card_layout.addWidget(eyebrow_label)
        card_layout.addWidget(title_label)
        card_layout.addWidget(copy_label)
        card_layout.addStretch()
        card_layout.addWidget(button)
        return card, button

    def _build_active_session(self):
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("sessionScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("sessionContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 18)
        layout.setSpacing(14)

        header = QFrame()
        header.setObjectName("sessionHero")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 18, 22, 18)
        heading = QVBoxLayout()
        heading.setSpacing(4)
        eyebrow = QLabel("ACTIVE SESSION")
        eyebrow.setObjectName("sessionEyebrow")
        self.title_label = QLabel("No active session")
        self.title_label.setObjectName("sessionTitle")
        self.title_label.setWordWrap(True)
        self.evidence_label = QLabel()
        self.evidence_label.setObjectName("sessionSupportingText")
        self.evidence_label.setWordWrap(True)
        self.evidence_label.setAccessibleName("Recommendation evidence")
        heading.addWidget(eyebrow)
        heading.addWidget(self.title_label)
        heading.addWidget(self.evidence_label)
        header_layout.addLayout(heading, 1)
        summary = QFrame()
        summary.setObjectName("sessionProgressSummary")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(16, 11, 16, 11)
        self.status_label = QLabel()
        self.status_label.setObjectName("sessionStatusPill")
        self.position_label = QLabel()
        self.position_label.setObjectName("sessionPosition")
        summary_layout.addWidget(self.status_label)
        summary_layout.addWidget(self.position_label)
        header_layout.addWidget(summary)
        layout.addWidget(header)

        workspace = QHBoxLayout()
        workspace.setSpacing(14)
        self.guide_panel = QFrame()
        self.guide_panel.setObjectName("sessionGuideCard")
        guide_layout = QVBoxLayout(self.guide_panel)
        guide_layout.setContentsMargins(22, 18, 22, 18)
        guide_layout.setSpacing(10)
        guide_label = QLabel("CURRENT SCENARIO · COMPLETE GUIDE")
        guide_label.setObjectName("sessionEyebrow")
        guide_layout.addWidget(guide_label)
        self.guide = ScenarioGuideWidget()
        self.run_progress = self.guide.run_progress
        guide_layout.addWidget(self.guide, 0, Qt.AlignmentFlag.AlignTop)
        self.availability_label = QLabel()
        self.availability_label.setObjectName("sessionWarning")
        self.availability_label.setWordWrap(True)
        self.availability_label.setAccessibleName("Scenario installation guidance")
        self.availability_label.hide()
        guide_layout.addWidget(self.availability_label)
        self.recheck_button = QPushButton("Recheck installed scenarios")
        self.recheck_button.setAccessibleName(self.recheck_button.text())
        self.recheck_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.recheck_button.hide()
        guide_layout.addWidget(
            self.recheck_button, alignment=Qt.AlignmentFlag.AlignLeft,
        )
        guide_layout.addStretch()
        workspace.addWidget(self.guide_panel, 3)

        self.overview_panel = QFrame()
        self.overview_panel.setObjectName("sessionQueueCard")
        overview_layout = QVBoxLayout(self.overview_panel)
        overview_layout.setContentsMargins(18, 18, 18, 18)
        overview_layout.setSpacing(10)
        queue_eyebrow = QLabel("ROUTINE QUEUE")
        queue_eyebrow.setObjectName("sessionEyebrow")
        self.queue_title = QLabel("Every scenario in this session")
        self.queue_title.setObjectName("sessionQueueTitle")
        self.queue_summary = QLabel()
        self.queue_summary.setObjectName("sessionSupportingText")
        self.overview = QListWidget()
        self.overview.setObjectName("sessionRoutineList")
        self.overview.setAccessibleName("Full routine overview")
        overview_layout.addWidget(queue_eyebrow)
        overview_layout.addWidget(self.queue_title)
        overview_layout.addWidget(self.queue_summary)
        overview_layout.addWidget(self.overview, 1)
        workspace.addWidget(self.overview_panel, 2)
        layout.addLayout(workspace, 1)

        self.controls_panel = QFrame()
        self.controls_panel.setObjectName("sessionControls")
        controls = QVBoxLayout(self.controls_panel)
        controls.setContentsMargins(18, 14, 18, 14)
        controls.setSpacing(11)
        advance_row = QHBoxLayout()
        advance_row.setSpacing(10)
        options_label = QLabel("SESSION OPTIONS")
        options_label.setObjectName("sessionEyebrow")
        advance_row.addWidget(options_label)
        advance_row.addStretch()
        detection_label = QLabel("Run detection")
        detection_label.setObjectName("sessionOptionLabel")
        advance_row.addWidget(detection_label)
        self.advance_mode = QComboBox()
        self.advance_mode.addItems(("Automatic with manual fallback", "Manual only"))
        self.advance_mode.setAccessibleName("Run detection mode")
        advance_row.addWidget(self.advance_mode)
        self.overlay_checkbox = QCheckBox("Show compact always-on-top panel")
        self.overlay_checkbox.setAccessibleName("Show compact training panel")
        advance_row.addWidget(self.overlay_checkbox)
        controls.addLayout(advance_row)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.launch_button = QPushButton("Launch in KovaaK's")
        self.launch_button.setObjectName("primaryButton")
        self.manual_button = QPushButton("Count completed run")
        self.pause_button = QPushButton("Pause / resume")
        self.restart_button = QPushButton("Restart scenario")
        self.next_button = QPushButton("Next recommendation")
        self.stop_button = QPushButton("Stop session")
        self.stop_button.setObjectName("dangerButton")
        for button in self.action_controls():
            button.setAccessibleName(button.text())
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            actions.addWidget(button)
        controls.addLayout(actions)
        layout.addWidget(self.controls_panel)

        scroll.setWidget(content)
        root.addWidget(scroll)
        return page

    def action_controls(self):
        return (
            self.launch_button,
            self.manual_button,
            self.pause_button,
            self.restart_button,
            self.next_button,
            self.stop_button,
        )

    def set_state(self, view_model):
        self._view_model = view_model
        self.session_stack.setCurrentWidget(self.active_session)
        mode = view_model.mode.replace("_", " ").title()
        self.title_label.setText(f"{view_model.title} · {mode}")
        self.status_label.setText(view_model.status.upper())
        completed = sum(step.completed for step in view_model.steps)
        total = len(view_model.steps)
        current = min(completed + 1, total) if total else 0
        self.position_label.setText(
            f"Scenario {current} of {total}  ·  {view_model.progress_text}"
        )
        self.queue_summary.setText(f"{completed} complete · {total - completed} remaining")
        self.evidence_label.setText(
            view_model.evidence.summary
            if view_model.evidence else "Source-backed routine order"
        )
        self.guide.set_guide(view_model.current_guide)
        self.overview.clear()
        for index, step in enumerate(view_model.steps, 1):
            if step.completed:
                state = "Complete"
            elif index == current:
                state = "Now"
            else:
                state = "Up next"
            item = QListWidgetItem(
                f"{index}.  {step.scenario}\n     {state}  ·  {step.run_text}"
            )
            item.setData(Qt.ItemDataRole.UserRole, state.casefold().replace(" ", "_"))
            self.overview.addItem(item)
        self.launch_button.setEnabled(view_model.can_launch)
        active = view_model.status in ("running", "paused")
        self.manual_button.setEnabled(active)
        self.pause_button.setEnabled(active)
        self.restart_button.setEnabled(active)
        self.stop_button.setEnabled(active)
        self.next_button.setEnabled(view_model.can_advance)

    def progress_text(self):
        return self._view_model.progress_text

    def set_scenario_availability(self, result, guide=None):
        missing = result.state == "missing"
        self.launch_button.setEnabled(
            bool(self._view_model and self._view_model.can_launch and not missing)
        )
        self.availability_label.setVisible(missing)
        self.recheck_button.setVisible(missing)
        if missing and guide is not None:
            self.availability_label.setText(
                "Scenario is not installed\n" + "\n".join(
                    f"{index}. {step}" for index, step in enumerate(guide.steps, 1)
                )
            )
