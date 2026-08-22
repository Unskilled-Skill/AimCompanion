from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QComboBox, QPushButton, QSizePolicy,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from models.score import PlayerProfile
from models.database import Database
from models.benchmark import (
    TIERS, get_benchmarks_by_difficulty, score_to_energy, energy_to_tier,
)
from models.config import TrainingConfig
from core.kovaaks_launcher import open_kovaaks_scenario


class ProgressWidget(QWidget):
    def __init__(self, profile: PlayerProfile, db: Database):
        super().__init__()
        self.profile = profile
        self.db = db
        self.config = TrainingConfig.load()
        self.benchmark_defs = get_benchmarks_by_difficulty(profile.difficulty)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(10)
        selector_label = QLabel("S5 benchmark")
        selector_label.setStyleSheet("color: #bac2de;")
        selector_label.setFont(QFont("Segoe UI", 11))
        selector_row.addWidget(selector_label)

        self.scenario_combo = QComboBox()
        self.scenario_combo.addItems([b["name"] for b in self.benchmark_defs])
        self.scenario_combo.currentTextChanged.connect(self._on_scenario_changed)
        selector_row.addWidget(self.scenario_combo, 1)
        self.measurement_status = QLabel()
        self.measurement_status.setObjectName("mutedText")
        selector_row.addWidget(self.measurement_status)
        selector_row.addStretch()
        layout.addLayout(selector_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        open_benchmark = QPushButton("Open benchmark")
        open_benchmark.setObjectName("secondaryButton")
        open_benchmark.clicked.connect(self._open_selected_benchmark)
        action_row.addWidget(open_benchmark)
        check_next = QPushButton("Check next")
        check_next.setObjectName("primaryButton")
        check_next.setToolTip("Open an unmeasured benchmark, then the least recently checked one")
        check_next.clicked.connect(self._check_next_benchmark)
        action_row.addWidget(check_next)
        official_profile = QPushButton("Voltaic profile")
        official_profile.setObjectName("secondaryButton")
        official_profile.setToolTip("Open your authoritative Voltaic S5 rank")
        official_profile.clicked.connect(self._open_voltaic_profile)
        action_row.addWidget(official_profile)
        action_row.addWidget(QLabel("Range"))
        self.range_combo = QComboBox()
        self.range_combo.addItems(["30 days", "90 days", "1 year", "All time"])
        self.range_combo.setCurrentText("90 days")
        self.range_combo.currentTextChanged.connect(self._on_range_changed)
        action_row.addWidget(self.range_combo)
        action_row.addStretch()
        layout.addLayout(action_row)
        official_note = QLabel(
            "Check next opens one official benchmark. Complete a few attempts, then "
            "Sync scores; Voltaic remains the authoritative S5 rank source."
        )
        official_note.setObjectName("mutedText")
        official_note.setWordWrap(True)
        layout.addWidget(official_note)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(2, 6, 2, 6)
        self.scroll_layout.setSpacing(16)

        self.energy_chart_frame = QFrame()
        self.energy_chart_frame.setObjectName("progressCard")
        self.energy_chart_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.energy_chart_frame.setStyleSheet("""
            QFrame#progressCard {
                background-color: #181825;
                border-radius: 10px;
                padding: 18px;
                border: 1px solid #313244;
            }
        """)
        self.energy_chart_layout = QVBoxLayout(self.energy_chart_frame)
        self.energy_chart_layout.setSpacing(10)
        self.scroll_layout.addWidget(self.energy_chart_frame)

        self.chart_frame = QFrame()
        self.chart_frame.setObjectName("progressCard")
        self.chart_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.chart_frame.setStyleSheet("""
            QFrame#progressCard {
                background-color: #181825;
                border-radius: 10px;
                padding: 18px;
                border: 1px solid #313244;
            }
        """)
        self.chart_layout = QVBoxLayout(self.chart_frame)
        self.chart_layout.setSpacing(10)
        self.scroll_layout.addWidget(self.chart_frame)

        self.stats_frame = QFrame()
        self.stats_frame.setObjectName("progressCard")
        self.stats_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.stats_frame.setStyleSheet("""
            QFrame#progressCard {
                background-color: #181825;
                border-radius: 10px;
                padding: 18px;
                border: 1px solid #313244;
            }
        """)
        self.stats_layout = QVBoxLayout(self.stats_frame)
        self.stats_layout.setSpacing(10)
        self.scroll_layout.addWidget(self.stats_frame)

        self.history_frame = QFrame()
        self.history_frame.setObjectName("progressCard")
        self.history_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.history_frame.setStyleSheet("""
            QFrame#progressCard {
                background-color: #181825;
                border-radius: 10px;
                padding: 18px;
                border: 1px solid #313244;
            }
        """)
        self.history_layout = QVBoxLayout(self.history_frame)
        self.history_layout.setSpacing(4)
        self.scroll_layout.addWidget(self.history_frame)

        self.scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        self._build_energy_chart()

        if self.benchmark_defs:
            self._on_scenario_changed(self.benchmark_defs[0]["name"])

    def _selected_definition(self):
        name = self.scenario_combo.currentText()
        return next((item for item in self.benchmark_defs if item["name"] == name), None)

    def _open_selected_benchmark(self):
        benchmark = self._selected_definition()
        if benchmark:
            open_kovaaks_scenario(benchmark["scenario"])

    def _check_next_benchmark(self):
        if not self.benchmark_defs:
            return
        unmeasured = [
            benchmark for benchmark in self.benchmark_defs
            if not self.db.get_score_history(benchmark["name"])
        ]
        if unmeasured:
            selected = unmeasured[0]
        else:
            selected = min(
                self.benchmark_defs,
                key=lambda benchmark: self.db.get_score_history(
                    benchmark["name"]
                )[-1].timestamp,
            )
        self.scenario_combo.setCurrentText(selected["name"])
        self._open_selected_benchmark()

    def _open_voltaic_profile(self):
        QDesktopServices.openUrl(QUrl(self.config.voltaic_profile_url))

    def _update_measurement_status(self, name: str):
        history = self.db.get_score_history(name) if name else []
        if not history:
            self.measurement_status.setText("Not measured")
            self.measurement_status.setStyleSheet("color: #f9e2af; font-weight: bold;")
            return
        last = history[-1].timestamp.strftime("%b %d")
        self.measurement_status.setText(f"{len(history)} attempts  ·  last {last}")
        self.measurement_status.setStyleSheet("color: #94e2d5; font-weight: bold;")

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _filtered_history(self, history):
        days = {"30 days": 30, "90 days": 90, "1 year": 365}.get(
            self.range_combo.currentText()
        )
        if not days:
            return history
        cutoff = datetime.now() - timedelta(days=days)
        return [score for score in history if score.timestamp >= cutoff]

    def _on_range_changed(self, _value):
        self._build_energy_chart()
        self._on_scenario_changed(self.scenario_combo.currentText())

    def _build_energy_chart(self):
        self._clear_layout(self.energy_chart_layout)

        title = QLabel("Energy Progression Over Time")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        self.energy_chart_layout.addWidget(title)

        fig = Figure(figsize=(10, 3.5), dpi=100)
        fig.patch.set_facecolor("#11111b")
        fig.subplots_adjust(left=0.07, right=0.98, top=0.92, bottom=0.32)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#181825")

        colors = {
            "clicking": "#89b4fa",
            "tracking": "#a6e3a1",
            "switching": "#fab387",
        }

        for cat in self.profile.categories:
            if not cat.subcategories:
                continue
            for sub in cat.subcategories:
                for bench in sub.benchmarks:
                    history = self._filtered_history(
                        self.db.get_score_history(bench.name)
                    )
                    if len(history) < 2:
                        continue
                    energies = [score_to_energy(bench.name, s.score) for s in history]
                    dates = [score.timestamp for score in history]
                    ax.plot(dates, energies,
                           color=colors.get(cat.name, "#cdd6f4"),
                           linewidth=1.8, alpha=0.85)

        for t in TIERS[1:]:
            if t["min_energy"] > 0:
                ax.axhline(y=t["min_energy"], color=t["color"],
                          linewidth=0.8, alpha=0.4, linestyle="--")

        ax.set_ylabel("Energy", color="#bac2de", fontsize=10, labelpad=8)
        ax.set_xlabel("Date", color="#bac2de", fontsize=10, labelpad=8)
        ax.tick_params(colors="#a6adc8", labelsize=9, length=4)
        ax.spines["bottom"].set_color("#45475a")
        ax.spines["left"].set_color("#45475a")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, alpha=0.12, color="#585b70", linestyle="-")
        fig.autofmt_xdate(rotation=25)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(200)
        canvas.setMinimumWidth(0)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.energy_chart_layout.addWidget(canvas)

        legend_row = QHBoxLayout()
        legend_row.setContentsMargins(4, 4, 0, 0)
        legend_row.setSpacing(20)
        for name, color in colors.items():
            swatch = QLabel()
            swatch.setFixedSize(16, 16)
            swatch.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
            legend_row.addWidget(swatch)
            lbl = QLabel(name.capitalize())
            lbl.setFont(QFont("Segoe UI", 10))
            lbl.setStyleSheet(f"color: {color};")
            legend_row.addWidget(lbl)
        legend_row.addStretch()
        self.energy_chart_layout.addLayout(legend_row)

    def _on_scenario_changed(self, name: str):
        if not name:
            return

        self._update_measurement_status(name)

        self._clear_layout(self.chart_layout)
        self._clear_layout(self.stats_layout)
        self._clear_layout(self.history_layout)

        history = self._filtered_history(self.db.get_score_history(name))

        if not history:
            benchmark = self._selected_definition() or {}
            no_data = QLabel(
                "Not measured yet\n\n"
                f"{benchmark.get('category', 'Aim')} / {benchmark.get('subcategory', 'General')}"
                "  ·  Play this official benchmark to establish your baseline."
            )
            no_data.setStyleSheet("color: #7f849c; font-style: italic; padding: 20px;")
            no_data.setFont(QFont("Segoe UI", 11))
            no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data.setWordWrap(True)
            self.chart_layout.addWidget(no_data)
            self.stats_frame.hide()
            self.history_frame.hide()
            return

        self.stats_frame.show()
        self.history_frame.show()

        scores = [s.score for s in history]

        fig = Figure(figsize=(10, 3.5), dpi=100)
        fig.patch.set_facecolor("#11111b")
        fig.subplots_adjust(left=0.07, right=0.98, top=0.90, bottom=0.28)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#181825")
        dates = [score.timestamp for score in history]
        ax.plot(dates, scores, color="#89b4fa", linewidth=1.4, marker="o", markersize=4, alpha=0.65)
        if len(scores) >= 3:
            rolling = [
                sum(scores[max(0, i - 4):i + 1]) / len(scores[max(0, i - 4):i + 1])
                for i in range(len(scores))
            ]
            ax.plot(dates, rolling, color="#a6e3a1", linewidth=2.5, label="5-run average")
            ax.legend(facecolor="#181825", labelcolor="#cdd6f4")

        if len(scores) > 1:
            best_idx = scores.index(max(scores))
            ax.annotate(
                f"Best: {max(scores):.0f}",
                xy=(dates[best_idx], max(scores)),
                xytext=(0, 22), textcoords="offset points",
                fontsize=10, color="#a6e3a1", fontweight="bold",
                ha="left",
                arrowprops=dict(arrowstyle="-", color="#a6e3a1", lw=0.8),
            )

        ax.set_title(name, color="#cdd6f4", fontsize=13, fontweight="bold", pad=12)
        ax.set_ylabel("Score", color="#bac2de", fontsize=10, labelpad=8)
        ax.tick_params(colors="#a6adc8", labelsize=9, length=4)
        ax.spines["bottom"].set_color("#45475a")
        ax.spines["left"].set_color("#45475a")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, alpha=0.12, color="#585b70", linestyle="-")
        fig.autofmt_xdate(rotation=25)

        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(200)
        canvas.setMinimumWidth(0)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.chart_layout.addWidget(canvas)

        title = QLabel(f"Statistics - {name}")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        self.stats_layout.addWidget(title)

        best = max(scores)
        first = scores[0]
        latest = scores[-1]
        improvement = latest - first

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        stats_row.addWidget(self._stat("Attempts", str(len(scores)), "#89b4fa"))
        stats_row.addWidget(self._stat("Best", f"{best:.1f}", "#a6e3a1"))
        stats_row.addWidget(self._stat("Latest", f"{latest:.1f}", "#cdd6f4"))
        stats_row.addWidget(self._stat("First", f"{first:.1f}", "#7f849c"))
        delta_color = "#a6e3a1" if improvement >= 0 else "#f38ba8"
        stats_row.addWidget(self._stat("Change", f"{improvement:+.1f}", delta_color))
        stats_row.addStretch()
        self.stats_layout.addLayout(stats_row)

        recent_window = scores[-3:]
        recent_average = sum(recent_window) / len(recent_window)
        previous_window = scores[-6:-3]
        if previous_window:
            previous_average = sum(previous_window) / len(previous_window)
            trend = recent_average - previous_average
            trend_pct = (
                trend / previous_average * 100 if previous_average else 0.0
            )
            trend_color = "#a6e3a1" if trend >= 0 else "#f38ba8"
            consistency = QLabel(
                f"Recent consistency  ·  last {len(recent_window)} avg "
                f"{recent_average:.1f}  ·  previous {len(previous_window)} avg "
                f"{previous_average:.1f}  ·  {trend:+.1f} ({trend_pct:+.1f}%)"
            )
            consistency.setStyleSheet(f"color: {trend_color}; font-weight: bold;")
        else:
            consistency = QLabel(
                f"Recent consistency  ·  last {len(recent_window)} avg "
                f"{recent_average:.1f}  ·  more attempts needed for a trend"
            )
            consistency.setStyleSheet("color: #a6adc8;")
        self.stats_layout.addWidget(consistency)

        history_title = QLabel("Run History")
        history_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        history_title.setStyleSheet("color: #cdd6f4;")
        self.history_layout.addWidget(history_title)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(4, 0, 4, 4)
        header_row.setSpacing(0)
        for h, w in [("#", 40), ("Date", 160), ("Score", 80), ("Change", 80)]:
            lbl = QLabel(h)
            lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            lbl.setStyleSheet("color: #89b4fa; padding: 6px 8px;")
            lbl.setFixedWidth(w)
            header_row.addWidget(lbl)
        header_row.addStretch()
        self.history_layout.addLayout(header_row)

        for i, s in enumerate(reversed(history), 1):
            row = QHBoxLayout()
            row.setContentsMargins(4, 0, 4, 0)
            row.setSpacing(0)

            bg = "#1e1e2e" if i % 2 == 0 else "#181825"
            row_widget = QFrame()
            row_widget.setStyleSheet(f"QFrame {{ background-color: {bg}; border-radius: 4px; }}")
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 2, 0, 2)
            row_layout.setSpacing(0)

            row_layout.addWidget(self._history_cell(str(i), "#7f849c", 40))
            row_layout.addWidget(self._history_cell(s.timestamp.strftime("%Y-%m-%d %H:%M"), "#a6adc8", 160))
            row_layout.addWidget(self._history_cell(f"{s.score:.1f}", "#cdd6f4", 80))

            if i > 1:
                prev_score = history[-(i + 1)].score
                delta = s.score - prev_score
                color = "#a6e3a1" if delta >= 0 else "#f38ba8"
                row_layout.addWidget(self._history_cell(f"{delta:+.1f}", color, 80))
            else:
                row_layout.addWidget(self._history_cell("-", "#45475a", 80))

            row_layout.addStretch()
            self.history_layout.addWidget(row_widget)

    def _stat(self, label: str, value: str, color: str) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #11111b;
                border-radius: 8px;
                padding: 14px;
                border: 1px solid #313244;
                border-left: 4px solid {color};
            }}
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(6)

        lbl = QLabel(label)
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet("color: #a6adc8;")
        layout.addWidget(lbl)

        val = QLabel(value)
        val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        val.setStyleSheet(f"color: {color};")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(val)

        return frame

    def _history_cell(self, text: str, color: str, width: int = 80) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 9))
        lbl.setStyleSheet(f"color: {color}; padding: 5px 8px;")
        lbl.setFixedWidth(width)
        return lbl

    def update_profile(self, profile: PlayerProfile):
        current = self.scenario_combo.currentText()
        self.profile = profile
        self.benchmark_defs = get_benchmarks_by_difficulty(profile.difficulty)
        names = [benchmark["name"] for benchmark in self.benchmark_defs]
        self.scenario_combo.blockSignals(True)
        self.scenario_combo.clear()
        self.scenario_combo.addItems(names)
        if current in names:
            self.scenario_combo.setCurrentText(current)
        self.scenario_combo.blockSignals(False)
        self._build_energy_chart()
        if self.scenario_combo.currentText():
            self._on_scenario_changed(self.scenario_combo.currentText())
