from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea
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


class KPIDashboard(QWidget):
    def __init__(self, profile: PlayerProfile, db: Database):
        super().__init__()
        self.profile = profile
        self.db = db
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Key Performance Indicators")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(16)

        self._build_kpi_cards()
        self._build_trend_chart()

        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

    def _build_kpi_cards(self):
        benchmarks = self.db.get_all_benchmarks()
        vt_benchmarks = [b for b in benchmarks if b.startswith("VT ")]

        kpis = []
        for bench in vt_benchmarks:
            history = self.db.get_score_history(bench)
            if not history:
                continue

            latest = history[-1].score
            best = max(h.score for h in history)
            energy = score_to_energy(bench, latest)
            tier = energy_to_tier(energy)

            trend = 0
            if len(history) >= 3:
                recent_avg = sum(h.score for h in history[-3:]) / 3
                older_avg = sum(h.score for h in history[:-3]) / max(len(history) - 3, 1)
                trend = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0

            attempts = len(history)
            kpis.append({
                "name": bench,
                "latest": latest,
                "best": best,
                "energy": energy,
                "tier": tier,
                "trend": trend,
                "attempts": attempts,
                "history": history,
            })

        if not kpis:
            no_data = QLabel("No benchmark data available")
            no_data.setStyleSheet("color: #666; font-style: italic;")
            self.scroll_layout.addWidget(no_data)
            return

        row = QHBoxLayout()
        for i, kpi in enumerate(kpis[:9]):
            card = self._kpi_card(kpi)
            row.addWidget(card)
            if (i + 1) % 3 == 0:
                self.scroll_layout.addLayout(row)
                row = QHBoxLayout()
        if row.count() > 0:
            self.scroll_layout.addLayout(row)

    def _kpi_card(self, kpi):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setMinimumWidth(220)

        trend_color = "#a6e3a1" if kpi["trend"] >= 0 else "#f38ba8"
        trend_arrow = "^" if kpi["trend"] >= 0 else "v"
        if abs(kpi["trend"]) < 1:
            trend_arrow = "-"
            trend_color = "#7f849c"

        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #1e1e2e;
                border-radius: 10px;
                padding: 14px;
                border: 1px solid #313244;
                border-top: 3px solid {trend_color};
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(6)

        name_lbl = QLabel(kpi["name"][:20])
        name_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_lbl.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(name_lbl)

        tier_lbl = QLabel(kpi["tier"])
        for t in TIERS:
            if t["name"] == kpi["tier"]:
                tier_lbl.setStyleSheet(f"color: {t['color']}; font-weight: bold; font-size: 16px;")
                break
        layout.addWidget(tier_lbl)

        score_row = QHBoxLayout()
        score_row.setSpacing(8)
        score_lbl = QLabel(f"{kpi['latest']:.0f}")
        score_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        score_lbl.setStyleSheet("color: #cdd6f4;")
        score_row.addWidget(score_lbl)

        trend_lbl = QLabel(f"{trend_arrow} {kpi['trend']:+.1f}%")
        trend_lbl.setFont(QFont("Segoe UI", 10))
        trend_lbl.setStyleSheet(f"color: {trend_color}; font-weight: bold;")
        score_row.addWidget(trend_lbl)
        score_row.addStretch()
        layout.addLayout(score_row)

        best_lbl = QLabel(f"Best: {kpi['best']:.0f}")
        best_lbl.setStyleSheet("color: #a6adc8; font-size: 9pt;")
        layout.addWidget(best_lbl)

        attempts_lbl = QLabel(f"{kpi['attempts']} attempts")
        attempts_lbl.setStyleSheet("color: #7f849c; font-size: 9pt;")
        layout.addWidget(attempts_lbl)

        spark = self._sparkline(kpi["history"])
        layout.addWidget(spark)

        return frame

    def _sparkline(self, history):
        scores = [h.score for h in history[-15:]]
        fig = Figure(figsize=(2.2, 0.6), dpi=100)
        fig.patch.set_facecolor("#1e1e2e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#181825")
        ax.plot(scores, color="#89b4fa", linewidth=2)
        ax.fill_between(range(len(scores)), scores, alpha=0.25, color="#89b4fa")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        canvas = FigureCanvasQTAgg(fig)
        canvas.setFixedHeight(48)
        return canvas

    def _build_trend_chart(self):
        title = QLabel("Overall Energy Trend")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        self.scroll_layout.addWidget(title)

        fig = Figure(figsize=(10, 3), dpi=100)
        fig.patch.set_facecolor("#1e1e2e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#181825")

        benchmarks = self.db.get_all_benchmarks()
        vt_benchmarks = [b for b in benchmarks if b.startswith("VT ")]

        colors = ["#89b4fa", "#a6e3a1", "#fab387", "#cba6f7", "#f38ba8", "#f9e2af"]
        for i, bench in enumerate(vt_benchmarks):
            history = self.db.get_score_history(bench)
            if len(history) < 2:
                continue
            energies = [score_to_energy(bench, s.score) for s in history]
            ax.plot(range(len(energies)), energies, linewidth=2, alpha=0.85,
                   color=colors[i % len(colors)], label=bench[:15])

        for t in TIERS[1:]:
            if t["min_energy"] > 0:
                ax.axhline(y=t["min_energy"], color=t["color"], linewidth=0.7, alpha=0.35, linestyle="--")

        ax.set_ylabel("Energy", color="#a6adc8", fontsize=10)
        ax.tick_params(colors="#a6adc8", labelsize=9)
        ax.spines["bottom"].set_color("#45475a")
        ax.spines["left"].set_color("#45475a")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, alpha=0.15, color="#585b70")
        handles, labels = ax.get_legend_handles_labels()
        if labels:
            ax.legend(facecolor="#1e1e2e", edgecolor="#45475a", labelcolor="#cdd6f4",
                     fontsize=8, loc="upper left")

        canvas = FigureCanvasQTAgg(fig)
        self.scroll_layout.addWidget(canvas)

    def update_profile(self, profile):
        self.profile = profile
