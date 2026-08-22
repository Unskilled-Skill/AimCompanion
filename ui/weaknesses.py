from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from models.score import PlayerProfile
from core.analyzer import identify_weaknesses, get_improvement_suggestions
from models.benchmark import TIERS


class WeaknessWidget(QWidget):
    def __init__(self, profile: PlayerProfile):
        super().__init__()
        self.profile = profile
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.content_layout = QVBoxLayout(scroll_content)

        self._build_weakness_overview()
        self._build_weakness_list()
        self._build_suggestions()

        self.content_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

    def _build_weakness_overview(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border-radius: 10px;
                padding: 20px;
                border: 1px solid #313244;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)

        title = QLabel("Weakness Analysis")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(title)

        weaknesses = identify_weaknesses(self.profile)
        top_weaknesses = [w for w in weaknesses if w["relative_gap"] > 0.05][:5]

        if top_weaknesses:
            desc = QLabel("Your weakest areas compared to your overall level:")
            desc.setStyleSheet("color: #a6adc8;")
            desc.setFont(QFont("Segoe UI", 10))
            layout.addWidget(desc)

            for w in top_weaknesses:
                row = QHBoxLayout()
                row.setSpacing(12)

                name = QLabel(f"{w['category']} - {w['subcategory']}")
                name.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
                name.setStyleSheet("color: #f38ba8;")
                row.addWidget(name)

                gap = QLabel(f"Gap: {w['gap']:.1f} energy")
                gap.setStyleSheet("color: #eba0ac;")
                row.addWidget(gap)

                score = QLabel(f"Score: {w['score']:.0f}")
                score.setStyleSheet("color: #a6adc8;")
                row.addWidget(score)

                row.addStretch()
                layout.addLayout(row)

                progress = QProgressBar()
                max_energy = max(ww["energy"] for ww in weaknesses) if weaknesses else 1
                progress.setValue(int((w["energy"] / max_energy) * 100) if max_energy > 0 else 0)
                progress.setStyleSheet("""
                    QProgressBar {
                        background-color: #181825;
                        border-radius: 6px;
                        height: 10px;
                        border: 1px solid #313244;
                    }
                    QProgressBar::chunk {
                        background-color: #f38ba8;
                        border-radius: 5px;
                    }
                """)
                layout.addWidget(progress)
        else:
            no_weak = QLabel("No significant weaknesses detected - you're well balanced!")
            no_weak.setStyleSheet("color: #a6e3a1;")
            no_weak.setFont(QFont("Segoe UI", 11))
            layout.addWidget(no_weak)

        self.content_layout.addWidget(frame)

    def _build_weakness_list(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border-radius: 10px;
                padding: 20px;
                border: 1px solid #313244;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)

        title = QLabel("All Subcategory Scores")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(title)

        all_subs = []
        for cat in self.profile.categories:
            for sub in cat.subcategories:
                all_subs.append(sub)
        all_subs.sort(key=lambda s: s.energy)

        max_energy = max((s.energy for s in all_subs), default=1) or 1

        for sub in all_subs:
            row = QHBoxLayout()
            row.setSpacing(10)

            cat_label = QLabel(f"{sub.category}")
            cat_label.setFixedWidth(80)
            cat_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            cat_label.setStyleSheet(f"color: {self._get_category_color(sub.category)};")
            row.addWidget(cat_label)

            sub_label = QLabel(sub.name)
            sub_label.setFixedWidth(100)
            sub_label.setFont(QFont("Segoe UI", 10))
            sub_label.setStyleSheet("color: #cdd6f4;")
            row.addWidget(sub_label)

            score_label = QLabel(f"{sub.combined_score:.0f}")
            score_label.setFixedWidth(60)
            score_label.setFont(QFont("Segoe UI", 10))
            score_label.setStyleSheet("color: #cdd6f4;")
            row.addWidget(score_label)

            energy_bar = QProgressBar()
            energy_bar.setFixedWidth(220)
            energy_bar.setMaximum(int(max_energy))
            energy_bar.setValue(int(sub.energy))
            tier_color = self._get_tier_color(sub.tier)
            energy_bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: #181825;
                    border-radius: 6px;
                    height: 10px;
                    border: 1px solid #313244;
                }}
                QProgressBar::chunk {{
                    background-color: {tier_color};
                    border-radius: 5px;
                }}
            """)
            row.addWidget(energy_bar)

            tier_label = QLabel(sub.tier)
            tier_label.setFixedWidth(80)
            tier_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            tier_label.setStyleSheet(f"color: {tier_color};")
            row.addWidget(tier_label)

            row.addStretch()
            layout.addLayout(row)

        self.content_layout.addWidget(frame)

    def _build_suggestions(self):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border-radius: 10px;
                padding: 20px;
                border: 1px solid #313244;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)

        title = QLabel("Improvement Suggestions")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(title)

        suggestions = get_improvement_suggestions(self.profile)

        for s in suggestions:
            row = QFrame()
            row.setStyleSheet("""
                QFrame {
                    background-color: #181825;
                    border-radius: 8px;
                    padding: 12px;
                    border: 1px solid #313244;
                }
            """)
            row_layout = QVBoxLayout(row)
            row_layout.setSpacing(6)

            name = QLabel(f"{s['category']} - {s['subcategory']}")
            name.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            name.setStyleSheet("color: #89b4fa;")
            row_layout.addWidget(name)

            current = QLabel(f"Current: {s['current_energy']:.1f} energy ({s['current_tier']})")
            current.setStyleSheet("color: #a6adc8;")
            row_layout.addWidget(current)

            target = QLabel(f"Target: {s['target_score']:.0f} score ({s['target_energy']:.1f} energy)")
            target.setStyleSheet("color: #a6e3a1;")
            row_layout.addWidget(target)

            layout.addWidget(row)

        self.content_layout.addWidget(frame)

    def _get_category_color(self, category: str) -> str:
        colors = {
            "Clicking": "#ff9944",
            "Tracking": "#44aaff",
            "Switching": "#44ff88",
        }
        return colors.get(category, "#ffffff")

    def _get_tier_color(self, tier: str) -> str:
        for t in TIERS:
            if t["name"] == tier:
                return t["color"]
        return "#808080"

    def update_profile(self, profile: PlayerProfile):
        self.profile = profile
        self._clear_layout(self.content_layout)
        self._build_weakness_overview()
        self._build_weakness_list()
        self._build_suggestions()

    def _clear_layout(self, layout):
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
