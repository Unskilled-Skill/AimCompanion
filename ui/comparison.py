from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QComboBox, QDateEdit, QPushButton
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QFont

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from models.database import Database
from models.score import PlayerProfile


class ComparisonWidget(QWidget):
    def __init__(self, profile: PlayerProfile, db: Database):
        super().__init__()
        self.profile = profile
        self.db = db
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Score Comparison")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(header)

        subtitle = QLabel("Compare your scores between two dates")
        subtitle.setStyleSheet("color: #7f849c; font-style: italic;")
        subtitle.setFont(QFont("Segoe UI", 10))
        layout.addWidget(subtitle)

        date_row = QHBoxLayout()
        date_row.setSpacing(8)

        from_label = QLabel("From:")
        from_label.setStyleSheet("color: #cdd6f4;")
        from_label.setFont(QFont("Segoe UI", 10))
        date_row.addWidget(from_label)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        date_row.addWidget(self.date_from)

        to_label = QLabel("To:")
        to_label.setStyleSheet("color: #cdd6f4;")
        to_label.setFont(QFont("Segoe UI", 10))
        date_row.addWidget(to_label)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        date_row.addWidget(self.date_to)

        compare_btn = QPushButton("Compare")
        compare_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #74c7ec; }
        """)
        compare_btn.clicked.connect(self._compare)
        date_row.addWidget(compare_btn)

        date_row.addStretch()
        layout.addLayout(date_row)

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

        self.results_frame = QFrame()
        self.results_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.results_frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e2e;
                border-radius: 10px;
                padding: 16px;
                border: 1px solid #313244;
            }
        """)
        self.results_layout = QVBoxLayout(self.results_frame)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setSpacing(14)
        self.scroll_layout.addWidget(self.chart_frame)
        self.scroll_layout.addWidget(self.results_frame)
        self.scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        self._compare()

    def _compare(self):
        for i in range(self.chart_layout.count()):
            item = self.chart_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        for i in range(self.results_layout.count()):
            item = self.results_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        start = self.date_from.date().toString("yyyy-MM-dd") + "T00:00:00"
        end = self.date_to.date().toString("yyyy-MM-dd") + "T23:59:59"

        scores = self.db.get_scores_in_range(start, end)
        benchmarks = self.db.get_all_benchmarks()

        bench_data = {}
        for b in benchmarks:
            bench_scores = [s for s in scores if s.benchmark_name == b]
            if bench_scores:
                avg = sum(s.score for s in bench_scores) / len(bench_scores)
                best = max(s.score for s in bench_scores)
                first = bench_scores[0].score
                bench_data[b] = {"avg": avg, "best": best, "first": first, "count": len(bench_scores)}

        if not bench_data:
            no_data = QLabel("No scores found in the selected date range")
            no_data.setStyleSheet("color: #7f849c; font-style: italic;")
            no_data.setFont(QFont("Segoe UI", 10))
            self.chart_layout.addWidget(no_data)
            return

        fig = Figure(figsize=(10, 4), dpi=100)
        fig.patch.set_facecolor("#1e1e2e")
        ax = fig.add_subplot(111)
        ax.set_facecolor("#181825")

        names = list(bench_data.keys())[:12]
        avgs = [bench_data[n]["avg"] for n in names]
        bests = [bench_data[n]["best"] for n in names]

        x = range(len(names))
        ax.bar(x, avgs, color="#89b4fa", alpha=0.7, label="Average", width=0.4)
        ax.bar([i + 0.4 for i in x], bests, color="#a6e3a1", alpha=0.7, label="Best", width=0.4)

        ax.set_xticks([i + 0.2 for i in x])
        ax.set_xticklabels([n[:15] for n in names], rotation=45, ha="right", fontsize=9)
        ax.set_ylabel("Score", color="#a6adc8", fontsize=10)
        ax.tick_params(colors="#a6adc8", labelsize=9)
        ax.spines["bottom"].set_color("#45475a")
        ax.spines["left"].set_color("#45475a")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(facecolor="#1e1e2e", edgecolor="#45475a", labelcolor="#cdd6f4")
        ax.grid(True, alpha=0.15, color="#585b70")

        canvas = FigureCanvasQTAgg(fig)
        self.chart_layout.addWidget(canvas)

        title = QLabel("Detailed Comparison")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        self.results_layout.addWidget(title)

        for name in sorted(bench_data.keys()):
            d = bench_data[name]
            row = QHBoxLayout()
            row.setSpacing(12)

            name_lbl = QLabel(name[:25])
            name_lbl.setStyleSheet("color: #cdd6f4; font-weight: bold;")
            name_lbl.setFont(QFont("Segoe UI", 10))
            name_lbl.setFixedWidth(200)
            row.addWidget(name_lbl)

            avg_lbl = QLabel(f"Avg: {d['avg']:.0f}")
            avg_lbl.setStyleSheet("color: #89b4fa;")
            avg_lbl.setFont(QFont("Segoe UI", 10))
            row.addWidget(avg_lbl)

            best_lbl = QLabel(f"Best: {d['best']:.0f}")
            best_lbl.setStyleSheet("color: #a6e3a1;")
            best_lbl.setFont(QFont("Segoe UI", 10))
            row.addWidget(best_lbl)

            delta = d["avg"] - d["first"]
            delta_color = "#a6e3a1" if delta >= 0 else "#f38ba8"
            delta_lbl = QLabel(f"Delta: {delta:+.0f}")
            delta_lbl.setStyleSheet(f"color: {delta_color};")
            delta_lbl.setFont(QFont("Segoe UI", 10))
            row.addWidget(delta_lbl)

            cnt_lbl = QLabel(f"Runs: {d['count']}")
            cnt_lbl.setStyleSheet("color: #a6adc8;")
            cnt_lbl.setFont(QFont("Segoe UI", 10))
            row.addWidget(cnt_lbl)

            row.addStretch()
            self.results_layout.addLayout(row)

    def update_profile(self, profile):
        self.profile = profile
        self._compare()
