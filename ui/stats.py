from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QComboBox, QPushButton, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from datetime import datetime, timedelta
from models.database import Database
from models.score import PlayerProfile
from models.benchmark import TIERS, score_to_energy, energy_to_tier


class StatsSummary(QWidget):
    def __init__(self, profile: PlayerProfile, db: Database):
        super().__init__()
        self.profile = profile
        self.db = db
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Stats Summary")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(header)

        controls = QHBoxLayout()
        controls.addStretch()
        self.period_combo = QComboBox()
        self.period_combo.addItems(["This Week", "This Month", "Last 3 Months", "All Time"])
        self.period_combo.currentTextChanged.connect(self._refresh)
        controls.addWidget(self.period_combo)
        layout.addLayout(controls)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(14)
        scroll.setWidget(self.scroll_content)
        layout.addWidget(scroll)

    def _refresh(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        period = self.period_combo.currentText()
        days_map = {"This Week": 7, "This Month": 30, "Last 3 Months": 90, "All Time": 9999}
        days = days_map.get(period, 30)

        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=days)

        all_scores = self.db.get_scores_in_range(cutoff.isoformat(), datetime.now().isoformat())
        sessions = self.db.get_sessions(limit=200)
        sessions_in_period = [s for s in sessions
                             if datetime.fromisoformat(s["timestamp"]) >= cutoff]

        overview = self._stat_card("Overview", [
            f"Total Runs: {len(all_scores)}",
            f"Training Sessions: {len(sessions_in_period)}",
            f"Total Training Time: {sum(s['duration_minutes'] for s in sessions_in_period)} min",
            f"Unique Scenarios: {len(set(s.benchmark_name for s in all_scores))}",
        ], "#4a9eff")
        self.scroll_layout.addWidget(overview)

        if all_scores:
            bench_map = {}
            for s in all_scores:
                if s.benchmark_name not in bench_map:
                    bench_map[s.benchmark_name] = []
                bench_map[s.benchmark_name].append(s)

            top_scores = []
            for name, scores in bench_map.items():
                best = max(scores, key=lambda s: s.score)
                top_scores.append((name, best.score, len(scores)))

            top_scores.sort(key=lambda x: x[1], reverse=True)

            best_card = self._stat_card("Top Scores", [
                f"{name}: {score:.0f} ({count} runs)"
                for name, score, count in top_scores[:8]
            ], "#44ff88")
            self.scroll_layout.addWidget(best_card)

        subcat_stats = {}
        for s in all_scores:
            if s.subcategory:
                if s.subcategory not in subcat_stats:
                    subcat_stats[s.subcategory] = {"scores": [], "total": 0}
                subcat_stats[s.subcategory]["scores"].append(s.score)
                subcat_stats[s.subcategory]["total"] += 1

        if subcat_stats:
            subcat_lines = []
            for name, data in sorted(subcat_stats.items(), key=lambda x: -sum(x[1]["scores"])/len(x[1]["scores"])):
                avg = sum(data["scores"]) / len(data["scores"])
                subcat_lines.append(f"{name}: avg {avg:.0f} ({data['total']} runs)")

            subcat_card = self._stat_card("By Subcategory", subcat_lines, "#bb88ff")
            self.scroll_layout.addWidget(subcat_card)

        if sessions_in_period:
            focus_counts = {}
            for s in sessions_in_period:
                f = s.get("focus", "unknown")
                focus_counts[f] = focus_counts.get(f, 0) + 1

            focus_lines = [f"{k}: {v} sessions" for k, v in sorted(focus_counts.items(), key=lambda x: -x[1])]
            focus_card = self._stat_card("Training Focus", focus_lines, "#ff9944")
            self.scroll_layout.addWidget(focus_card)

        self.scroll_layout.addStretch()

    def _stat_card(self, title, lines, color):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #1e1e2e;
                border-radius: 10px;
                padding: 18px;
                border: 1px solid #313244;
                border-left: 4px solid {color};
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(8)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {color};")
        layout.addWidget(title_lbl)

        for line in lines:
            lbl = QLabel(line)
            lbl.setFont(QFont("Segoe UI", 10))
            lbl.setStyleSheet("color: #cdd6f4;")
            layout.addWidget(lbl)

        return frame

    def update_profile(self, profile):
        self.profile = profile
