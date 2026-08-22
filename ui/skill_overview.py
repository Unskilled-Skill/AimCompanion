from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from core.kovaaks_launcher import open_kovaaks_scenario
from core.training_intelligence import (
    build_skill_intelligence, detect_fatigue, plan_benchmark_checks,
)


class SkillOverviewWidget(QWidget):
    """Nine-skill Voltaic evidence, weakness, maintenance, and promotion view."""

    def __init__(self, profile, db):
        super().__init__()
        self.profile = profile
        self.db = db
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        content = QWidget()
        self.layout = QVBoxLayout(content)
        self.layout.setSpacing(12)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self._render()

    @staticmethod
    def _age(days):
        if days >= 999:
            return "never"
        if days == 0:
            return "today"
        return f"{days}d ago"

    def _render(self):
        self._clear(self.layout)
        skills = build_skill_intelligence(self.profile, self.db)
        title = QLabel("Well-rounded aim matrix")
        title.setObjectName("sectionTitle")
        self.layout.addWidget(title)
        copy = QLabel(
            "Voltaic benchmark ranks define skill. Confidence tells you whether the "
            "measurement is trustworthy; training age protects strong skills from decay."
        )
        copy.setObjectName("mutedText")
        copy.setWordWrap(True)
        self.layout.addWidget(copy)

        fatigue = detect_fatigue(self.db)
        if fatigue:
            warning = QLabel(
                f"Fatigue warning - {fatigue['scenario']} - "
                f"{abs(fatigue['drop_pct']):.1f}% below baseline. Stop and recover."
            )
            warning.setStyleSheet("color: #f38ba8; font-weight: bold; padding: 10px;")
            warning.setWordWrap(True)
            self.layout.addWidget(warning)

        checks = plan_benchmark_checks(skills, 3)
        if checks:
            check_frame = QFrame()
            check_frame.setObjectName("focusPanel")
            check_layout = QVBoxLayout(check_frame)
            heading = QLabel("Benchmark checks due")
            heading.setObjectName("smallTitle")
            check_layout.addWidget(heading)
            for check in checks:
                row = QHBoxLayout()
                label = QLabel(f"{check['name']} - {check['reason']}")
                label.setWordWrap(True)
                row.addWidget(label, 1)
                button = QPushButton("Check now")
                button.setObjectName("quietButton")
                button.clicked.connect(
                    lambda checked=False, scenario=check["scenario"]:
                    open_kovaaks_scenario(scenario)
                )
                row.addWidget(button)
                check_layout.addLayout(row)
            self.layout.addWidget(check_frame)

        confidence_colors = {
            "high": "#a6e3a1", "medium": "#f9e2af", "low": "#f38ba8",
        }
        priority_order = {
            skill["key"]: index + 1
            for index, skill in enumerate(
                sorted(skills, key=lambda item: item["priority"], reverse=True)[:3]
            )
        }
        for skill in skills:
            card = QFrame()
            card.setObjectName("skillCard")
            grid = QGridLayout(card)
            grid.setContentsMargins(14, 10, 14, 10)

            name = QLabel(f"{skill['category']} - {skill['subcategory']}")
            name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            grid.addWidget(name, 0, 0)

            priority = priority_order.get(skill["key"])
            priority_label = QLabel(f"Focus #{priority}" if priority else "Maintenance")
            priority_label.setStyleSheet(
                "color: #89b4fa; font-weight: bold;" if priority else "color: #7f849c;"
            )
            grid.addWidget(priority_label, 1, 0)

            confidence = QLabel(
                f"Evidence: {skill['confidence'].title()} - {skill['attempts']} runs"
            )
            confidence.setStyleSheet(
                f"color: {confidence_colors[skill['confidence']]}; font-weight: bold;"
            )
            grid.addWidget(confidence, 1, 1)
            grid.addWidget(
                QLabel(f"Rank: {skill['tier']} - {skill['energy']:.0f} energy"),
                0, 1,
            )

            trend = (
                "need 6 runs" if skill["trend_pct"] is None else
                f"{skill['trend_pct']:+.1f}% - {skill['progression']}"
            )
            grid.addWidget(QLabel(f"Trend: {trend}"), 2, 0)
            grid.addWidget(QLabel(
                f"Last trained: {self._age(skill['training_age_days'])}"
            ), 2, 1)
            next_rank = (
                f"{skill['next_tier']} - {skill['energy_gap']:.0f} energy"
                if skill["next_tier"] else "Highest rank"
            )
            target = QLabel(f"Next: {next_rank}")
            if skill["target_scores"]:
                target.setToolTip("\n".join(
                    f"{name}: {score:.1f}"
                    for name, score in skill["target_scores"].items()
                ))
            target.setWordWrap(True)
            grid.addWidget(target, 3, 0, 1, 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            self.layout.addWidget(card)

        effectiveness = sorted(
            self.db.get_scenario_effectiveness_summary().values(),
            key=lambda item: (
                item.get("measured_blocks", 0),
                item.get("average_delta_pct") or -999,
            ),
            reverse=True,
        )
        measured = [
            item for item in effectiveness if item.get("measured_blocks", 0) >= 2
        ][:5]
        if measured:
            panel = QFrame()
            panel.setObjectName("nextSteps")
            panel_layout = QVBoxLayout(panel)
            panel_layout.addWidget(QLabel("Your most measured scenario responses"))
            for item in measured:
                panel_layout.addWidget(QLabel(
                    f"{item['scenario']} - {item['measured_blocks']} measured blocks - "
                    f"{item['average_delta_pct']:+.1f}% average response"
                ))
            self.layout.addWidget(panel)
        self.layout.addStretch()

    def update_profile(self, profile):
        self.profile = profile
        self._render()

    def _clear(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear(item.layout())
