from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QComboBox, QPushButton
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from models.database import Database
from models.score import PlayerProfile
from models.benchmark import TIERS, score_to_energy, energy_to_tier


class TimelineWidget(QWidget):
    def __init__(self, profile: PlayerProfile, db: Database):
        super().__init__()
        self.profile = profile
        self.db = db
        self._build_ui()
        self._build_chart()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Benchmark Timeline")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(header)

        subtitle = QLabel("Track your tier progression over time")
        subtitle.setStyleSheet("color: #7f849c; font-style: italic;")
        subtitle.setFont(QFont("Segoe UI", 10))
        layout.addWidget(subtitle)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addStretch()

        self.period_combo = QComboBox()
        self.period_combo.addItems(["All Time", "Last 30 Days", "Last 90 Days", "Last Year"])
        self.period_combo.currentTextChanged.connect(self._build_chart)
        controls.addWidget(self.period_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._build_chart)
        controls.addWidget(refresh_btn)
        layout.addLayout(controls)

        self.chart_frame = QFrame()
        self.chart_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.chart_frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border-radius: 10px;
                padding: 16px;
                border: 1px solid #313244;
            }
        """)
        self.chart_layout = QVBoxLayout(self.chart_frame)
        layout.addWidget(self.chart_frame, stretch=2)

        self.stats_frame = QFrame()
        self.stats_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.stats_frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border-radius: 10px;
                padding: 16px;
                border: 1px solid #313244;
            }
        """)
        self.stats_layout = QVBoxLayout(self.stats_frame)
        layout.addWidget(self.stats_frame)

    def _build_chart(self):
        for i in range(self.chart_layout.count()):
            item = self.chart_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        for i in range(self.stats_layout.count()):
            item = self.stats_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        period = self.period_combo.currentText()
        days = {"All Time": 9999, "Last 30 Days": 30, "Last 90 Days": 90, "Last Year": 365}
        max_days = days.get(period, 9999)

        benchmarks = self.db.get_all_benchmarks()
        vt_benchmarks = [b for b in benchmarks if b.startswith("VT ")]

        fig = Figure(figsize=(10, 4), dpi=100)
        fig.patch.set_facecolor("#1e1e2e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#181825")

        colors = ["#89b4fa", "#a6e3a1", "#fab387", "#cba6f7", "#f38ba8", "#f9e2af"]
        has_data = False

        for i, bench in enumerate(vt_benchmarks[:6]):
            history = self.db.get_score_history(bench)
            if not history:
                continue

            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(days=max_days)
            history = [h for h in history if h.timestamp >= cutoff]
            if len(history) < 1:
                continue

            has_data = True
            energies = [score_to_energy(bench, s.score) for s in history]
            dates = [(h.timestamp - history[0].timestamp).days for h in history]

            ax.plot(dates, energies, color=colors[i % len(colors)],
                   linewidth=2.5, marker="o", markersize=4, label=bench[:20])

        if has_data:
            for t in TIERS[1:]:
                if t["min_energy"] > 0:
                    ax.axhline(y=t["min_energy"], color=t["color"],
                              linewidth=0.7, alpha=0.35, linestyle="--")

            ax.set_ylabel("Energy", color="#a6adc8", fontsize=10)
            ax.set_xlabel("Days", color="#a6adc8", fontsize=10)
            ax.tick_params(colors="#a6adc8", labelsize=9)
            ax.spines["bottom"].set_color("#45475a")
            ax.spines["left"].set_color("#45475a")
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.grid(True, alpha=0.15, color="#585b70")
            ax.legend(facecolor="#1e1e2e", edgecolor="#45475a", labelcolor="#cdd6f4", fontsize=8)
        else:
            ax.text(0.5, 0.5, "No data for this period", ha="center", va="center",
                   color="#7f849c", fontsize=12, transform=ax.transAxes)

        canvas = FigureCanvasQTAgg(fig)
        self.chart_layout.addWidget(canvas)

        self._build_stats()

    def _build_stats(self):
        title = QLabel("Tier History")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        self.stats_layout.addWidget(title)

        benchmarks = self.db.get_all_benchmarks()
        vt_benchmarks = [b for b in benchmarks if b.startswith("VT ")]

        for bench in vt_benchmarks:
            history = self.db.get_score_history(bench)
            if len(history) < 2:
                continue

            first_e = score_to_energy(bench, history[0].score)
            last_e = score_to_energy(bench, history[-1].score)
            first_tier = energy_to_tier(first_e)
            last_tier = energy_to_tier(last_e)
            delta = last_e - first_e

            row = QHBoxLayout()
            row.setSpacing(12)

            name_lbl = QLabel(bench[:25])
            name_lbl.setStyleSheet("color: #cdd6f4; font-weight: bold;")
            name_lbl.setFont(QFont("Segoe UI", 10))
            name_lbl.setFixedWidth(200)
            row.addWidget(name_lbl)

            first_lbl = QLabel(f"Start: {first_tier}")
            first_lbl.setStyleSheet("color: #a6adc8;")
            first_lbl.setFont(QFont("Segoe UI", 10))
            row.addWidget(first_lbl)

            arrow = QLabel(" -> ")
            arrow.setStyleSheet("color: #585b70;")
            arrow.setFont(QFont("Segoe UI", 10))
            row.addWidget(arrow)

            last_lbl = QLabel(f"Now: {last_tier}")
            from models.benchmark import TIERS
            for t in TIERS:
                if t["name"] == last_tier:
                    last_lbl.setStyleSheet(f"color: {t['color']}; font-weight: bold;")
                    break
            last_lbl.setFont(QFont("Segoe UI", 10))
            row.addWidget(last_lbl)

            delta_color = "#a6e3a1" if delta >= 0 else "#f38ba8"
            delta_lbl = QLabel(f"({delta:+.1f})")
            delta_lbl.setStyleSheet(f"color: {delta_color};")
            delta_lbl.setFont(QFont("Segoe UI", 10))
            row.addWidget(delta_lbl)

            row.addStretch()
            self.stats_layout.addLayout(row)

    def update_profile(self, profile):
        self.profile = profile
