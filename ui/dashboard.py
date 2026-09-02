from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from models.benchmark import TIERS
from models.score import PlayerProfile


class DashboardWidget(QWidget):
    """A deliberately small home screen: current level, next action, skill balance."""

    navigate_requested = pyqtSignal(str)
    quick_training_requested = pyqtSignal()

    def __init__(self, profile: PlayerProfile):
        super().__init__()
        self.profile = profile
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 6, 10)
        self.content_layout.setSpacing(18)

        self._build_hero()
        self._build_skills()
        self._build_next_steps()
        self.content_layout.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll)

    def _subcategories(self):
        return [sub for category in self.profile.categories for sub in category.subcategories]

    def _build_hero(self):
        hero = QFrame()
        hero.setObjectName("homeHero")
        layout = QHBoxLayout(hero)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(26)

        rank_block = QVBoxLayout()
        rank_block.setSpacing(5)
        is_official = self.profile.is_official_rank
        eyebrow = QLabel("YOUR OFFICIAL RANK" if is_official else "LOCAL CURRENT FORM")
        eyebrow.setObjectName("eyebrow")
        rank = QLabel(self.profile.overall_tier)
        rank.setObjectName("homeRank")
        rank.setStyleSheet(f"color: {self._tier_color(self.profile.overall_tier)};")
        overall_energy = self.profile.overall_energy
        energy = QLabel(
            f"{overall_energy:.1f} {'official' if is_official else 'local'} energy"
            if overall_energy is not None else "Overall energy unavailable"
        )
        energy.setObjectName("homeEnergy")
        next_tier = self._next_tier(overall_energy)
        explanation = QLabel(
            (
                f"{next_tier['min_energy'] - overall_energy:.1f} energy to "
                f"{next_tier['name']}. "
                if next_tier else
                "Complete all nine benchmark subcategories to receive an official overall energy. "
                if overall_energy is None else
                "Highest tracked tier reached. "
            ) + (
                "Energy determines your official Lifetime Best rank."
                if is_official
                else "This current-form analytic is not an official Voltaic rank."
            )
        )
        explanation.setObjectName("mutedText")
        explanation.setWordWrap(True)
        explanation.setMaximumWidth(390)
        rank_block.addWidget(eyebrow)
        rank_block.addWidget(rank)
        rank_block.addWidget(energy)
        rank_block.addSpacing(5)
        rank_block.addWidget(explanation)
        layout.addLayout(rank_block, 1)

        measured = [
            sub for sub in self._subcategories()
            if any(benchmark.best_score > 0 for benchmark in sub.benchmarks)
        ]
        weakest = min(measured, key=lambda sub: sub.energy) if measured else None
        focus = QFrame()
        focus.setObjectName("focusPanel")
        focus_layout = QVBoxLayout(focus)
        focus_layout.setContentsMargins(18, 16, 18, 16)
        focus_layout.setSpacing(6)
        focus_label = QLabel("RECOMMENDED FOCUS")
        focus_label.setObjectName("eyebrow")
        focus_name = QLabel(self._area_name(weakest))
        focus_name.setObjectName("focusTitle")
        focus_name.setWordWrap(True)
        focus_name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        focus_copy = QLabel(
            f"Your lowest measured skill at {weakest.energy:.0f} energy. Train one short "
            "block; the other skills remain in rotation."
            if weakest else
            "Import or complete Voltaic benchmarks before asking for a weakness-based routine."
        )
        focus_copy.setObjectName("mutedText")
        focus_copy.setWordWrap(True)
        start = QPushButton("Start a 3–5 min block" if weakest else "Import scores")
        start.setObjectName("primaryButton")
        start.setCursor(Qt.CursorShape.PointingHandCursor)
        start.clicked.connect(
            self.quick_training_requested.emit
            if weakest else lambda: self.navigate_requested.emit("import")
        )
        focus_layout.addWidget(focus_label)
        focus_layout.addWidget(focus_name)
        focus_layout.addWidget(focus_copy)
        focus_layout.addStretch()
        focus_layout.addWidget(start, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(focus, 1)

        self.content_layout.addWidget(hero)

    def _build_skills(self):
        heading = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Skill balance")
        title.setObjectName("sectionTitle")
        subtitle = QLabel(
            "Official Lifetime Best skill energy."
            if self.profile.is_official_rank
            else f"Local current form from {self.profile.score_input_label}; not an official rank."
        )
        subtitle.setObjectName("mutedText")
        subtitle.setWordWrap(True)
        subtitle.setMaximumWidth(680)
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        heading.addLayout(title_block, 1)
        heading.addStretch()
        details = QPushButton("Learn the technique")
        details.setObjectName("textButton")
        details.clicked.connect(lambda: self.navigate_requested.emit("aim_hub"))
        heading.addWidget(details)
        self.content_layout.addLayout(heading)

        grid = QGridLayout()
        grid.setSpacing(12)
        for index, category in enumerate(self.profile.categories):
            row, column = divmod(index, 3)
            grid.addWidget(self._skill_card(category), row, column)
            grid.setColumnStretch(column, 1)
        self.content_layout.addLayout(grid)

    def _skill_card(self, category):
        card = QFrame()
        card.setObjectName("skillCard")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(17, 15, 17, 16)
        layout.setSpacing(10)

        header = QHBoxLayout()
        name = QLabel(category.name)
        name.setObjectName("skillName")
        tier = QLabel(
            category.tier
            if self.profile.is_official_rank
            else f"{category.tier} (local)"
        )
        tier.setObjectName("tierPill")
        tier.setStyleSheet(f"color: {self._tier_color(category.tier)};")
        header.addWidget(name)
        header.addStretch()
        header.addWidget(tier)
        layout.addLayout(header)

        for sub in category.subcategories:
            row = QVBoxLayout()
            row.setSpacing(4)
            labels = QHBoxLayout()
            sub_name = QLabel(sub.name)
            sub_name.setObjectName("skillSubName")
            next_tier = self._next_tier(sub.energy)
            gap = (
                f" • {next_tier['min_energy'] - sub.energy:.0f} to {next_tier['name']}"
                if next_tier else " • top tier"
            )
            tier_text = sub.tier if self.profile.is_official_rank else f"{sub.tier} (local)"
            sub_name.setText(f"{sub.name} • {tier_text}")
            value = QLabel(f"{sub.energy:.0f}{gap}")
            value.setObjectName("skillValue")
            labels.addWidget(sub_name)
            labels.addStretch()
            labels.addWidget(value)
            bar = QProgressBar()
            bar.setRange(0, self._energy_cap())
            bar.setValue(max(0, int(sub.energy)))
            bar.setToolTip(f"{sub.tier} · {sub.combined_score:.0f} combined score")
            row.addLayout(labels)
            row.addWidget(bar)
            layout.addLayout(row)
        return card

    def _build_next_steps(self):
        panel = QFrame()
        panel.setObjectName("nextSteps")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(16)

        copy = QVBoxLayout()
        title = QLabel("Want a closer look?")
        title.setObjectName("smallTitle")
        text = QLabel("Explore score history or review the exact scenarios behind your rank.")
        text.setObjectName("mutedText")
        text.setWordWrap(True)
        copy.addWidget(title)
        copy.addWidget(text)
        layout.addLayout(copy, 1)

        progress = QPushButton("View progress")
        progress.setObjectName("quietButton")
        progress.clicked.connect(lambda: self.navigate_requested.emit("progress"))
        scenarios = QPushButton("Browse scenarios")
        scenarios.setObjectName("quietButton")
        scenarios.clicked.connect(lambda: self.navigate_requested.emit("scenarios"))
        layout.addWidget(progress)
        layout.addWidget(scenarios)
        self.content_layout.addWidget(panel)

    def _energy_cap(self):
        return {"Novice": 500, "Intermediate": 700, "Advanced": 1300}.get(
            self.profile.difficulty, 1000
        )

    @staticmethod
    def _area_name(subcategory):
        if not subcategory:
            return "Complete a benchmark first"
        return f"{subcategory.category} · {subcategory.name}"

    @staticmethod
    def _tier_color(tier):
        for item in TIERS:
            if item["name"] == tier:
                return item["color"]
        return "#aab4c5"

    @staticmethod
    def _next_tier(energy):
        if energy is None:
            return None
        return next((tier for tier in TIERS if tier["min_energy"] > energy), None)

    def update_profile(self, profile):
        self.profile = profile
        self._clear_layout(self.content_layout)
        self._build_hero()
        self._build_skills()
        self._build_next_steps()
        self.content_layout.addStretch()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
