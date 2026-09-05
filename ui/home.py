"""User-first coaching dashboard for the Home destination."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class HomeWidget(QWidget):
    start_warmup = pyqtSignal()
    start_step_by_step = pyqtSignal()
    start_full_routine = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(16)

        self.focus_card = QFrame()
        self.focus_card.setObjectName("homeFocusCard")
        focus_layout = QHBoxLayout(self.focus_card)
        focus_layout.setContentsMargins(24, 22, 24, 22)
        focus_layout.setSpacing(28)

        focus_copy = QVBoxLayout()
        focus_copy.setSpacing(8)
        eyebrow = QLabel("TODAY'S COACHING FOCUS")
        eyebrow.setObjectName("homeEyebrow")
        self.headline_label = QLabel("Choose how you want to train")
        self.headline_label.setObjectName("homeFocusTitle")
        self.headline_label.setWordWrap(True)
        self.evidence_label = QLabel()
        self.evidence_label.setObjectName("homeSupportingText")
        self.evidence_label.setWordWrap(True)
        self.evidence_label.setAccessibleName("Recommendation evidence")
        focus_copy.addWidget(eyebrow)
        focus_copy.addWidget(self.headline_label)
        focus_copy.addWidget(self.evidence_label)

        focus_facts = QHBoxLayout()
        focus_facts.setSpacing(10)
        weakness = self._fact("PRIORITY", "Balanced", "Training priority")
        self.weakness_value = weakness[1]
        confidence = self._fact("CONFIDENCE", "Building", "Recommendation confidence")
        self.confidence_value = confidence[1]
        focus_facts.addWidget(weakness[0])
        focus_facts.addWidget(confidence[0])
        focus_facts.addStretch()
        focus_copy.addLayout(focus_facts)
        focus_layout.addLayout(focus_copy, 1)

        rank_panel = QFrame()
        rank_panel.setObjectName("homeRankPanel")
        rank_panel.setMinimumWidth(260)
        rank_layout = QVBoxLayout(rank_panel)
        rank_layout.setContentsMargins(18, 16, 18, 16)
        rank_layout.setSpacing(5)
        rank_caption = QLabel("CURRENT BENCHMARK")
        rank_caption.setObjectName("homeEyebrow")
        self.rank_value = QLabel("Unranked")
        self.rank_value.setObjectName("homeRankValue")
        self.rank_value.setWordWrap(True)
        self.trend_label = QLabel("Complete a session to establish a trend")
        self.trend_label.setObjectName("homeSupportingText")
        self.trend_label.setWordWrap(True)
        rank_layout.addWidget(rank_caption)
        rank_layout.addWidget(self.rank_value)
        rank_layout.addWidget(self.trend_label)
        rank_layout.addStretch()
        focus_layout.addWidget(rank_panel)
        layout.addWidget(self.focus_card)

        choice_heading = QVBoxLayout()
        choice_heading.setSpacing(2)
        title = QLabel("Choose your session")
        title.setObjectName("sectionTitle")
        subtitle = QLabel("Pick what fits your goal and available energy right now.")
        subtitle.setObjectName("homeSupportingText")
        choice_heading.addWidget(title)
        choice_heading.addWidget(subtitle)
        layout.addLayout(choice_heading)

        self.action_panel = QFrame()
        self.action_panel.setObjectName("primaryActionPanel")
        self.training_choices = self.action_panel
        actions = QHBoxLayout(self.action_panel)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(12)

        warmup = self._training_card(
            "WARM-UP", "Warm-up",
            "Prepare your aim before a game or another routine.",
            "Quick · uses your last context",
        )
        self.warmup_description, self.warmup_button = warmup[1], warmup[2]
        step = self._training_card(
            "ADAPTIVE", "Step-by-Step Training",
            "Get one scenario at a time, selected around your current weakness.",
            "Flexible · stop whenever you need", recommended=True,
        )
        self.step_description, self.step_button = step[1], step[2]
        full = self._training_card(
            "STRUCTURED", "Full Routine",
            "Complete a proven routine with every planned scenario and run.",
            "Focused · fixed routine structure",
        )
        self.full_description, self.full_button = full[1], full[2]
        for card in (warmup[0], step[0], full[0]):
            actions.addWidget(card, 1)

        self.primary_actions = (
            self.warmup_button, self.step_button, self.full_button,
        )
        self.warmup_button.clicked.connect(self.start_warmup)
        self.step_button.clicked.connect(self.start_step_by_step)
        self.full_button.clicked.connect(self.start_full_routine)
        layout.addWidget(self.action_panel)

        self.insights_panel = QFrame()
        self.insights_panel.setObjectName("homeInsights")
        insights = QHBoxLayout(self.insights_panel)
        insights.setContentsMargins(0, 0, 0, 0)
        insights.setSpacing(12)

        self.recent_progress = QFrame()
        self.recent_progress.setObjectName("homeInsightCard")
        recent_layout = QVBoxLayout(self.recent_progress)
        recent_layout.setContentsMargins(18, 16, 18, 16)
        recent_layout.setSpacing(7)
        recent_title = QLabel("Recent training coverage")
        recent_title.setObjectName("homeCardTitle")
        self.recent_label = QLabel("No completed sessions yet")
        self.recent_label.setObjectName("homeInsightBody")
        self.recent_label.setWordWrap(True)
        recent_layout.addWidget(recent_title)
        recent_layout.addWidget(self.recent_label)
        recent_layout.addStretch()
        insights.addWidget(self.recent_progress, 1)

        self.readiness_card = QFrame()
        self.readiness_card.setObjectName("homeInsightCard")
        readiness_layout = QVBoxLayout(self.readiness_card)
        readiness_layout.setContentsMargins(18, 16, 18, 16)
        readiness_layout.setSpacing(7)
        readiness_title = QLabel("Benchmark readiness")
        readiness_title.setObjectName("homeCardTitle")
        self.readiness_value = QLabel("Complete benchmark scenarios to unlock guidance")
        self.readiness_value.setObjectName("homeInsightBody")
        self.readiness_value.setWordWrap(True)
        readiness_hint = QLabel(
            "Fresh benchmark coverage improves weakness recommendations."
        )
        readiness_hint.setObjectName("homeSupportingText")
        readiness_hint.setWordWrap(True)
        readiness_layout.addWidget(readiness_title)
        readiness_layout.addWidget(self.readiness_value)
        readiness_layout.addWidget(readiness_hint)
        readiness_layout.addStretch()
        insights.addWidget(self.readiness_card, 1)
        layout.addWidget(self.insights_panel)
        layout.addStretch()

        # Compatibility names used by view-model and integration tests.
        self.rank_label = self.rank_value
        self.next_rank_label = self.readiness_value
        self.weakness_label = self.weakness_value
        self.confidence_label = self.confidence_value

    @staticmethod
    def _fact(caption, value, accessible_name):
        card = QFrame()
        card.setObjectName("homeFact")
        card.setAccessibleName(accessible_name)
        fact_layout = QVBoxLayout(card)
        fact_layout.setContentsMargins(12, 8, 12, 8)
        fact_layout.setSpacing(2)
        caption_label = QLabel(caption)
        caption_label.setObjectName("homeFactCaption")
        value_label = QLabel(value)
        value_label.setObjectName("homeFactValue")
        value_label.setWordWrap(True)
        fact_layout.addWidget(caption_label)
        fact_layout.addWidget(value_label)
        return card, value_label

    @staticmethod
    def _training_card(eyebrow, title, description, meta, recommended=False):
        card = QFrame()
        card.setObjectName("trainingModeCard")
        card.setProperty("recommended", recommended)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(7)

        top = QHBoxLayout()
        eyebrow_label = QLabel(eyebrow)
        eyebrow_label.setObjectName("trainingModeEyebrow")
        top.addWidget(eyebrow_label)
        top.addStretch()
        if recommended:
            badge = QLabel("RECOMMENDED")
            badge.setObjectName("recommendedBadge")
            top.addWidget(badge)
        card_layout.addLayout(top)

        title_label = QLabel(title)
        title_label.setObjectName("trainingModeTitle")
        description_label = QLabel(description)
        description_label.setObjectName("trainingModeDescription")
        description_label.setWordWrap(True)
        meta_label = QLabel(meta)
        meta_label.setObjectName("trainingModeMeta")
        meta_label.setWordWrap(True)
        button = QPushButton(title)
        button.setObjectName("primaryButton" if recommended else "modeStartButton")
        button.setProperty("recommended", recommended)
        button.setMinimumHeight(38)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAccessibleName(f"Start {title}")
        button.setAccessibleDescription(description)
        card_layout.addWidget(title_label)
        card_layout.addWidget(description_label)
        card_layout.addWidget(meta_label)
        card_layout.addStretch()
        card_layout.addWidget(button)
        return card, description_label, button

    def set_view_model(self, view_model):
        self.headline_label.setText(view_model.headline)
        self.rank_value.setText(view_model.rank_text)
        self.readiness_value.setText(view_model.next_rank_text)
        self.weakness_value.setText(view_model.weakness_text or "Balanced coverage")
        self.trend_label.setText(view_model.trend_text)
        self.confidence_value.setText(view_model.confidence_text)
        self.evidence_label.setText(view_model.evidence_text)
        self.recent_label.setText(
            "\n".join(view_model.recent_progress)
            if view_model.recent_progress else "No completed sessions yet"
        )

    def set_benchmark_recommendation(self, due_count: int):
        if due_count > 0:
            noun = "area" if due_count == 1 else "areas"
            self.step_button.setText("Start benchmark playlist")
            self.step_button.setAccessibleName("Start benchmark playlist")
            self.step_description.setText(
                f"Create and run the official scenarios for {due_count} due "
                f"benchmark {noun}."
            )
            return
        self.step_button.setText("Step-by-Step Training")
        self.step_button.setAccessibleName("Start Step-by-Step Training")
        self.step_description.setText(
            "Get one scenario at a time, selected around your current weakness."
        )
