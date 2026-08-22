from collections import defaultdict

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QDateEdit, QFrame, QHeaderView, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from models.database import Database
from models.score import PlayerProfile


def build_comparison_rows(scores):
    """Compare an early sample with a recent sample on each scenario's own scale."""
    grouped = defaultdict(list)
    for score in sorted(scores, key=lambda item: item.timestamp):
        grouped[score.benchmark_name].append(score.score)
    rows = []
    for name, values in grouped.items():
        sample = min(3, max(1, len(values) // 2))
        early = sum(values[:sample]) / sample
        recent = sum(values[-sample:]) / sample
        delta = recent - early
        delta_pct = (delta / early * 100) if early and len(values) >= 2 else None
        rows.append({
            "name": name,
            "early": early,
            "recent": recent,
            "best": max(values),
            "delta": delta,
            "delta_pct": delta_pct,
            "count": len(values),
        })
    return sorted(rows, key=lambda row: (row["delta_pct"] is None, -(row["delta_pct"] or 0), row["name"].casefold()))


class ComparisonWidget(QWidget):
    def __init__(self, profile: PlayerProfile, db: Database):
        super().__init__()
        self.profile = profile
        self.db = db
        self._build_ui()
        self._compare()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        heading = QHBoxLayout()
        title_block = QVBoxLayout()
        title = QLabel("Score change")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        title_block.addWidget(title)
        subtitle = QLabel("Compares your first and latest attempts inside the selected range.")
        subtitle.setObjectName("mutedText")
        title_block.addWidget(subtitle)
        heading.addLayout(title_block)
        heading.addStretch()
        heading.addWidget(QLabel("FROM"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))
        self.date_from.setFixedWidth(125)
        heading.addWidget(self.date_from)
        heading.addWidget(QLabel("TO"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setFixedWidth(125)
        heading.addWidget(self.date_to)
        compare = QPushButton("Update")
        compare.setObjectName("primaryButton")
        compare.clicked.connect(self._compare)
        heading.addWidget(compare)
        root.addLayout(heading)

        self.summary = QLabel()
        self.summary.setStyleSheet("color: #94e2d5; font-weight: bold;")
        root.addWidget(self.summary)

        self.chart_frame = self._card()
        self.chart_layout = QVBoxLayout(self.chart_frame)
        self.chart_layout.setContentsMargins(16, 12, 16, 12)
        self.chart_layout.setSpacing(6)
        root.addWidget(self.chart_frame)

        self.results_frame = self._card()
        results = QVBoxLayout(self.results_frame)
        results.setContentsMargins(14, 12, 14, 14)
        results.setSpacing(8)
        table_title = QLabel("Scenario details")
        table_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        table_title.setStyleSheet("color: #cdd6f4;")
        results.addWidget(table_title)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Scenario", "Early avg", "Recent avg", "Best", "Change", "Runs"])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().hide()
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        results.addWidget(self.table)
        root.addWidget(self.results_frame, 1)

        self.empty_frame = self._card()
        empty_layout = QVBoxLayout(self.empty_frame)
        empty_layout.setContentsMargins(20, 28, 20, 28)
        self.empty_title = QLabel()
        self.empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.empty_title.setStyleSheet("color: #cdd6f4;")
        empty_layout.addWidget(self.empty_title)
        self.empty_note = QLabel()
        self.empty_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_note.setWordWrap(True)
        self.empty_note.setObjectName("mutedText")
        empty_layout.addWidget(self.empty_note)
        root.addWidget(self.empty_frame)
        root.addStretch()

    def _compare(self):
        self._clear_layout(self.chart_layout)
        start = self.date_from.date().toString("yyyy-MM-dd") + "T00:00:00"
        end = self.date_to.date().toString("yyyy-MM-dd") + "T23:59:59"
        rows = build_comparison_rows(self.db.get_scores_in_range(start, end))

        if not rows:
            self.summary.clear()
            self.chart_frame.hide()
            self.results_frame.hide()
            self.empty_frame.show()
            self.empty_title.setText("No scores in this range")
            self.empty_note.setText("Choose a wider date range or sync your Kovaak's scores, then update the comparison.")
            return

        self.empty_frame.hide()
        self.results_frame.show()
        comparable = [row for row in rows if row["delta_pct"] is not None]
        improved = sum(row["delta_pct"] > 0 for row in comparable)
        declined = sum(row["delta_pct"] < 0 for row in comparable)
        self.summary.setText(f"{len(rows)} scenarios  •  {len(comparable)} with a trend  •  {improved} improved  •  {declined} declined")
        self._populate_table(rows)

        if not comparable:
            self.chart_frame.hide()
            return
        self.chart_frame.show()
        title = QLabel("Largest percentage changes")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        self.chart_layout.addWidget(title)
        note = QLabel("Percentage change makes scenarios with different scoring scales comparable.")
        note.setObjectName("mutedText")
        self.chart_layout.addWidget(note)

        shown = sorted(comparable, key=lambda row: abs(row["delta_pct"]), reverse=True)[:10]
        shown.reverse()
        fig = Figure(figsize=(10, max(2.4, len(shown) * 0.38)), dpi=100)
        fig.patch.set_facecolor("#11192b")
        fig.subplots_adjust(left=0.24, right=0.97, top=0.95, bottom=0.20)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#11192b")
        values = [row["delta_pct"] for row in shown]
        labels = [self._short_name(row["name"]) for row in shown]
        colors = ["#a6e3a1" if value >= 0 else "#f38ba8" for value in values]
        bars = ax.barh(range(len(shown)), values, color=colors, alpha=0.85, height=0.62)
        ax.set_yticks(range(len(shown)), labels)
        ax.axvline(0, color="#7f849c", linewidth=0.8)
        ax.set_xlabel("Change (%)", color="#a6adc8", fontsize=9)
        ax.tick_params(colors="#a6adc8", labelsize=8)
        ax.spines[:].set_visible(False)
        ax.grid(axis="x", alpha=0.12, color="#585b70")
        ax.bar_label(bars, labels=[f"{value:+.1f}%" for value in values], padding=4, color="#cdd6f4", fontsize=8)
        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(max(240, len(shown) * 38))
        canvas.setMaximumHeight(max(270, len(shown) * 42))
        self.chart_layout.addWidget(canvas)

    def _populate_table(self, rows):
        self.table.setRowCount(len(rows))
        for row_index, data in enumerate(rows):
            change = "Baseline only" if data["delta_pct"] is None else f"{data['delta_pct']:+.1f}%"
            values = [
                data["name"], f"{data['early']:.1f}", f"{data['recent']:.1f}",
                f"{data['best']:.1f}", change, str(data["count"]),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column > 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == 4 and data["delta_pct"] is not None:
                    item.setForeground(QColor("#a6e3a1" if data["delta_pct"] >= 0 else "#f38ba8"))
                self.table.setItem(row_index, column, item)
        self.table.resizeRowsToContents()

    @staticmethod
    def _short_name(name):
        return name if len(name) <= 28 else name[:27] + "…"

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    @staticmethod
    def _card():
        frame = QFrame()
        frame.setObjectName("toolCard")
        frame.setStyleSheet("QFrame#toolCard { background: #11192b; border: 1px solid #263149; border-radius: 9px; }")
        return frame

    def update_profile(self, profile):
        self.profile = profile
        self._compare()
