from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QFont, QPainter, QColor

from models.score import PlayerProfile
from models.benchmark import TIERS


class HeatmapWidget(QWidget):
    def __init__(self, profile: PlayerProfile):
        super().__init__()
        self.profile = profile
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Aim Heatmap")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        subtitle = QLabel("Visual overview of your strengths and weaknesses")
        subtitle.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(subtitle)

        self.heatmap = HeatmapGrid(self.profile)
        layout.addWidget(self.heatmap, stretch=1)

        legend_row = QHBoxLayout()
        legend_row.addStretch()
        for t in reversed(TIERS[1:]):
            swatch = QLabel("  ")
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(f"background-color: {t['color']}; border-radius: 3px;")
            legend_row.addWidget(swatch)
            name = QLabel(t["name"])
            name.setStyleSheet(f"color: {t['color']}; font-size: 9px;")
            legend_row.addWidget(name)
            legend_row.addSpacing(8)
        legend_row.addStretch()
        layout.addLayout(legend_row)

    def update_profile(self, profile):
        self.profile = profile
        self.heatmap.profile = profile
        self.heatmap.update()


class HeatmapGrid(QWidget):
    def __init__(self, profile: PlayerProfile):
        super().__init__()
        self.profile = profile
        self.setMinimumHeight(300)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        grid = [
            ("Clicking", "Dynamic", "clicking"),
            ("Clicking", "Static", "clicking"),
            ("Clicking", "Linear", "clicking"),
            ("Tracking", "Control", "tracking"),
            ("Tracking", "Precise", "tracking"),
            ("Tracking", "Reactive", "tracking"),
            ("Switching", "Speed", "switching"),
            ("Switching", "Evasive", "switching"),
            ("Switching", "Stability", "switching"),
        ]

        w = self.width()
        h = self.height()
        margin = 40
        cols = 3
        rows = 3
        cell_w = (w - margin * 2 - 20) / cols
        cell_h = (h - margin * 2 - 20) / rows

        painter.setPen(QColor("#4a9eff"))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        col_labels = ["Clicking", "Tracking", "Switching"]
        for c, label in enumerate(col_labels):
            x = margin + c * (cell_w + 10) + cell_w / 2
            painter.drawText(QRect(int(x - 40), 5, 80, 25), Qt.AlignmentFlag.AlignCenter, label)

        row_labels = ["1st", "2nd", "3rd"]
        for r, label in enumerate(row_labels):
            y = margin + r * (cell_h + 10) + cell_h / 2
            painter.drawText(QRect(5, int(y - 12), 30, 24), Qt.AlignmentFlag.AlignCenter, label)

        for i, (cat, subcat, cat_key) in enumerate(grid):
            r, c = divmod(i, cols)
            x = margin + c * (cell_w + 10)
            y = margin + r * (cell_h + 10)

            energy = 0.0
            tier = ""
            for profile_cat in self.profile.categories:
                if profile_cat.name.lower() == cat_key.lower():
                    for s in profile_cat.subcategories:
                        if s.name == subcat:
                            energy = s.energy
                            tier = s.tier
                            break

            color = self._tier_color(tier) if energy > 0 else "#1a1a2a"
            painter.setBrush(QColor(color))
            painter.setPen(QColor("#333"))
            painter.drawRoundedRect(int(x), int(y), int(cell_w), int(cell_h), 8, 8)

            painter.setPen(QColor("white"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            painter.drawText(QRect(int(x), int(y + 5), int(cell_w), 25),
                           Qt.AlignmentFlag.AlignCenter, subcat)

            painter.setFont(QFont("Segoe UI", 9))
            painter.setPen(QColor("#ddd"))
            painter.drawText(QRect(int(x), int(y + 28), int(cell_w), 20),
                           Qt.AlignmentFlag.AlignCenter, f"{energy:.0f}")

            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor("#aaa"))
            painter.drawText(QRect(int(x), int(y + 45), int(cell_w), 20),
                           Qt.AlignmentFlag.AlignCenter, tier if energy > 0 else "—")

    def _tier_color(self, tier):
        for t in TIERS:
            if t["name"] == tier:
                return t["color"]
        return "#1a1a2a"
