from datetime import datetime, timedelta

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.dates import AutoDateLocator, ConciseDateFormatter
from matplotlib.figure import Figure

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from core.kovaaks_launcher import open_kovaaks_scenario
from models.benchmark import TIERS, energy_to_tier, get_benchmarks_by_difficulty, score_to_energy
from models.config import TrainingConfig
from models.database import Database
from models.score import PlayerProfile


CARD_STYLE = """
    QFrame#progressCard {
        background-color: #181825;
        border: 1px solid #313244;
        border-radius: 10px;
    }
"""


def next_target_for_score(benchmark: dict, score: float):
    """Return the next official target above score, or the highest cleared target."""
    targets = benchmark.get("targets", {})
    ordered = []
    for tier in TIERS:
        if tier["name"] in targets:
            ordered.append((tier["name"], float(targets[tier["name"]]), tier["color"]))
    for target in ordered:
        if score < target[1]:
            return target, False
    return (ordered[-1] if ordered else None), True


def padded_date_limits(dates):
    """Create readable limits without Matplotlib's multi-year single-point default."""
    if not dates:
        return None
    start, end = min(dates), max(dates)
    if start == end:
        pad = timedelta(hours=12)
    else:
        pad = max(timedelta(hours=6), (end - start) * 0.08)
    return start - pad, end + pad


class ProgressWidget(QWidget):
    def __init__(self, profile: PlayerProfile, db: Database):
        super().__init__()
        self.profile = profile
        self.db = db
        self.config = TrainingConfig.load()
        self.benchmark_defs = get_benchmarks_by_difficulty(profile.difficulty)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        controls = QFrame()
        controls.setObjectName("progressCard")
        controls.setStyleSheet(CARD_STYLE)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(16, 13, 16, 13)
        controls_layout.setSpacing(9)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(10)
        selector_label = QLabel("BENCHMARK")
        selector_label.setStyleSheet("color: #89b4fa; font-weight: bold;")
        selector_row.addWidget(selector_label)

        self.scenario_combo = QComboBox()
        self.scenario_combo.setMinimumWidth(320)
        self.scenario_combo.setMaximumWidth(560)
        self.scenario_combo.addItems([b["name"] for b in self.benchmark_defs])
        self.scenario_combo.currentTextChanged.connect(self._on_scenario_changed)
        selector_row.addWidget(self.scenario_combo, 1)

        self.measurement_status = QLabel()
        selector_row.addWidget(self.measurement_status)
        selector_row.addStretch()

        range_label = QLabel("RANGE")
        range_label.setStyleSheet("color: #89b4fa; font-weight: bold;")
        selector_row.addWidget(range_label)
        self.range_combo = QComboBox()
        self.range_combo.addItems(["30 days", "90 days", "1 year", "All time"])
        self.range_combo.setCurrentText("90 days")
        self.range_combo.currentTextChanged.connect(self._on_range_changed)
        selector_row.addWidget(self.range_combo)
        controls_layout.addLayout(selector_row)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        open_benchmark = QPushButton("Run benchmark")
        open_benchmark.setObjectName("primaryButton")
        open_benchmark.clicked.connect(self._open_selected_benchmark)
        action_row.addWidget(open_benchmark)
        check_next = QPushButton("Check next benchmark")
        check_next.setObjectName("secondaryButton")
        check_next.setToolTip("Open an unmeasured benchmark, then the least recently checked one")
        check_next.clicked.connect(self._check_next_benchmark)
        action_row.addWidget(check_next)
        official_profile = QPushButton("Open Voltaic profile")
        official_profile.setObjectName("secondaryButton")
        official_profile.clicked.connect(self._open_voltaic_profile)
        action_row.addWidget(official_profile)
        action_row.addStretch()
        hint = QLabel("Play a few attempts, then Sync scores above.")
        hint.setObjectName("mutedText")
        action_row.addWidget(hint)
        controls_layout.addLayout(action_row)
        root.addWidget(controls)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self.scroll_layout = QVBoxLayout(content)
        self.scroll_layout.setContentsMargins(2, 0, 2, 6)
        self.scroll_layout.setSpacing(12)

        self.summary_frame, self.summary_layout = self._card()
        self.detail_frame, self.detail_layout = self._card()
        self.energy_chart_frame, self.energy_chart_layout = self._card()
        self.history_frame, self.history_layout = self._card()
        for frame in (self.summary_frame, self.detail_frame, self.energy_chart_frame, self.history_frame):
            self.scroll_layout.addWidget(frame)
        self.scroll_layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

        self._build_energy_chart()
        if self.benchmark_defs:
            self._on_scenario_changed(self.benchmark_defs[0]["name"])

    @staticmethod
    def _card():
        frame = QFrame()
        frame.setObjectName("progressCard")
        frame.setStyleSheet(CARD_STYLE)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(10)
        return frame, layout

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
        unmeasured = [b for b in self.benchmark_defs if not self.db.get_score_history(b["name"])]
        if unmeasured:
            selected = unmeasured[0]
        else:
            selected = min(
                self.benchmark_defs,
                key=lambda b: self.db.get_score_history(b["name"])[-1].timestamp,
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
        noun = "attempt" if len(history) == 1 else "attempts"
        last = history[-1].timestamp.strftime("%b %d")
        self.measurement_status.setText(f"{len(history)} {noun}  •  last {last}")
        self.measurement_status.setStyleSheet("color: #94e2d5; font-weight: bold;")

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def _filtered_history(self, history):
        days = {"30 days": 30, "90 days": 90, "1 year": 365}.get(self.range_combo.currentText())
        if not days:
            return history
        cutoff = datetime.now() - timedelta(days=days)
        return [score for score in history if score.timestamp >= cutoff]

    def _on_range_changed(self, _value):
        self._build_energy_chart()
        self._on_scenario_changed(self.scenario_combo.currentText())

    def _build_energy_chart(self):
        self._clear_layout(self.energy_chart_layout)
        series = []
        colors = {"clicking": "#89b4fa", "tracking": "#a6e3a1", "switching": "#fab387"}
        for category in self.profile.categories:
            for subcategory in category.subcategories:
                for benchmark in subcategory.benchmarks:
                    history = self._filtered_history(self.db.get_score_history(benchmark.name))
                    if len(history) >= 2:
                        series.append((category.name, benchmark.name, history))

        if not series:
            self.energy_chart_frame.hide()
            return

        self.energy_chart_frame.show()
        self.energy_chart_layout.addWidget(self._section_title("Overall rank movement"))
        subtitle = QLabel("Official benchmark energy over time. Each line is one measured benchmark.")
        subtitle.setObjectName("mutedText")
        self.energy_chart_layout.addWidget(subtitle)

        fig, ax = self._figure()
        all_dates = []
        for category, _name, history in series:
            dates = [score.timestamp for score in history]
            all_dates.extend(dates)
            ax.plot(
                dates, [score_to_energy(_name, score.score) for score in history],
                color=colors.get(category.casefold(), "#cdd6f4"), linewidth=1.8,
                marker="o", markersize=3, alpha=0.8,
            )
        for tier in TIERS[1:]:
            if tier["min_energy"] > 0:
                ax.axhline(tier["min_energy"], color=tier["color"], linewidth=0.7, alpha=0.25, linestyle="--")
        self._style_axis(ax, "Energy", all_dates)
        self.energy_chart_layout.addWidget(self._canvas(fig, 235))

        legend = QHBoxLayout()
        legend.setSpacing(18)
        for name, color in colors.items():
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color};")
            legend.addWidget(dot)
            label = QLabel(name.capitalize())
            label.setStyleSheet("color: #bac2de;")
            legend.addWidget(label)
        legend.addStretch()
        self.energy_chart_layout.addLayout(legend)

    def _on_scenario_changed(self, name: str):
        if not name:
            return
        self._update_measurement_status(name)
        self._clear_layout(self.summary_layout)
        self._clear_layout(self.detail_layout)
        self._clear_layout(self.history_layout)

        benchmark = self._selected_definition() or {}
        history = self._filtered_history(self.db.get_score_history(name))
        self._build_summary(benchmark, history)

        if not history:
            self._build_empty_state(benchmark)
            self.history_frame.hide()
        elif len(history) == 1:
            self._build_baseline_state(benchmark, history[0].score)
            self.history_frame.hide()
        else:
            self._build_score_chart(name, history)
            self._build_history(history)

    def _build_summary(self, benchmark, history):
        category = benchmark.get("category", "Aim")
        subcategory = benchmark.get("subcategory", "General")
        heading = QHBoxLayout()
        heading.addWidget(self._section_title(f"{category} / {subcategory}"))
        heading.addStretch()
        if history:
            best = max(score.score for score in history)
            tier = energy_to_tier(score_to_energy(benchmark.get("name", ""), best))
            badge = QLabel(tier)
            badge.setStyleSheet("background: #313244; color: #cdd6f4; padding: 5px 12px; border-radius: 10px; font-weight: bold;")
            heading.addWidget(badge)
        self.summary_layout.addLayout(heading)

        if not history:
            note = QLabel("No baseline yet. This benchmark will start measuring this skill once you complete it.")
            note.setObjectName("mutedText")
            self.summary_layout.addWidget(note)
            return

        scores = [score.score for score in history]
        best, latest, first = max(scores), scores[-1], scores[0]
        delta = latest - first
        target, completed = next_target_for_score(benchmark, best)
        target_text = "Top target cleared" if completed else (f"{target[0]} at {target[1]:.0f}" if target else "—")
        cards = QHBoxLayout()
        cards.setSpacing(10)
        values = [
            ("ATTEMPTS", str(len(scores)), "#89b4fa"),
            ("BEST", f"{best:.1f}", "#a6e3a1"),
            ("LATEST", f"{latest:.1f}", "#cdd6f4"),
            ("CHANGE", f"{delta:+.1f}", "#a6e3a1" if delta >= 0 else "#f38ba8"),
            ("NEXT TARGET", target_text, target[2] if target else "#f9e2af"),
        ]
        for label, value, color in values:
            cards.addWidget(self._stat(label, value, color), 1)
        self.summary_layout.addLayout(cards)

    def _build_empty_state(self, benchmark):
        self.detail_frame.show()
        title = QLabel("Establish your baseline")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4; margin-top: 12px;")
        self.detail_layout.addWidget(title)
        copy = QLabel("Run this official benchmark 2–3 times. Your best score sets the baseline; later attempts reveal the trend.")
        copy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        copy.setWordWrap(True)
        copy.setStyleSheet("color: #a6adc8;")
        self.detail_layout.addWidget(copy)
        run = QPushButton(f"Run {benchmark.get('scenario', 'benchmark')}")
        run.setObjectName("primaryButton")
        run.setMaximumWidth(280)
        run.clicked.connect(self._open_selected_benchmark)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(run)
        row.addStretch()
        self.detail_layout.addLayout(row)

    def _build_baseline_state(self, benchmark, score):
        self.detail_frame.show()
        self.detail_layout.addWidget(self._section_title("Baseline established"))
        target, completed = next_target_for_score(benchmark, score)
        if target:
            if completed:
                message = QLabel(f"{score:.1f} clears the highest target tracked for this benchmark.")
                progress_value = 100
            else:
                gap = target[1] - score
                message = QLabel(f"{score:.1f} baseline  •  {gap:.1f} points to {target[0]}")
                previous = max((float(v) for v in benchmark.get("targets", {}).values() if float(v) <= score), default=0.0)
                progress_value = int(max(0, min(100, (score - previous) / max(1, target[1] - previous) * 100)))
            message.setStyleSheet("color: #cdd6f4; font-size: 15px; font-weight: bold;")
            self.detail_layout.addWidget(message)
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(progress_value)
            bar.setTextVisible(False)
            bar.setFixedHeight(10)
            color = target[2]
            bar.setStyleSheet(f"QProgressBar {{ background: #11111b; border: 0; border-radius: 5px; }} QProgressBar::chunk {{ background: {color}; border-radius: 5px; }}")
            self.detail_layout.addWidget(bar)
        note = QLabel("Complete one more attempt to unlock a useful trend. A single dot would not tell you whether your aim is improving.")
        note.setWordWrap(True)
        note.setObjectName("mutedText")
        self.detail_layout.addWidget(note)

    def _build_score_chart(self, name, history):
        self.detail_frame.show()
        self.detail_layout.addWidget(self._section_title("Score trend"))
        scores = [score.score for score in history]
        dates = [score.timestamp for score in history]
        fig, ax = self._figure()
        ax.plot(dates, scores, color="#89b4fa", linewidth=1.8, marker="o", markersize=5, alpha=0.9)
        if len(scores) >= 3:
            rolling = [sum(scores[max(0, i - 4):i + 1]) / len(scores[max(0, i - 4):i + 1]) for i in range(len(scores))]
            ax.plot(dates, rolling, color="#a6e3a1", linewidth=2.4, label="5-run average")
            legend = ax.legend(facecolor="#181825", edgecolor="#313244")
            for text in legend.get_texts():
                text.set_color("#cdd6f4")
        best_idx = scores.index(max(scores))
        ax.scatter([dates[best_idx]], [scores[best_idx]], color="#a6e3a1", s=36, zorder=4)
        self._style_axis(ax, "Score", dates)
        self.detail_layout.addWidget(self._canvas(fig, 255))

        recent = scores[-3:]
        if len(scores) >= 6:
            previous = scores[-6:-3]
            trend = sum(recent) / len(recent) - sum(previous) / len(previous)
            text = f"Recent 3-run average: {sum(recent) / len(recent):.1f}  •  trend: {trend:+.1f}"
            color = "#a6e3a1" if trend >= 0 else "#f38ba8"
        else:
            text = f"Recent {len(recent)}-run average: {sum(recent) / len(recent):.1f}  •  6 attempts unlock a stable trend comparison"
            color = "#a6adc8"
        trend_label = QLabel(text)
        trend_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.detail_layout.addWidget(trend_label)

    def _build_history(self, history):
        self.history_frame.show()
        self.history_layout.addWidget(self._section_title("Recent attempts"))
        for index, score in enumerate(reversed(history[-8:])):
            row_widget = QFrame()
            row_widget.setStyleSheet(f"background: {'#1e1e2e' if index % 2 else '#181825'}; border-radius: 5px;")
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(10, 7, 10, 7)
            date = QLabel(score.timestamp.strftime("%b %d, %Y  %H:%M"))
            date.setStyleSheet("color: #a6adc8;")
            row.addWidget(date)
            row.addStretch()
            value = QLabel(f"{score.score:.1f}")
            value.setStyleSheet("color: #cdd6f4; font-weight: bold;")
            row.addWidget(value)
            chronological_index = len(history) - 1 - index
            if chronological_index > 0:
                delta = score.score - history[chronological_index - 1].score
                delta_label = QLabel(f"{delta:+.1f}")
                delta_label.setFixedWidth(70)
                delta_label.setAlignment(Qt.AlignmentFlag.AlignRight)
                delta_label.setStyleSheet(f"color: {'#a6e3a1' if delta >= 0 else '#f38ba8'};")
                row.addWidget(delta_label)
            self.history_layout.addWidget(row_widget)

    @staticmethod
    def _figure():
        fig = Figure(figsize=(10, 2.6), dpi=100)
        fig.patch.set_facecolor("#181825")
        fig.subplots_adjust(left=0.065, right=0.985, top=0.96, bottom=0.22)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#181825")
        return fig, ax

    @staticmethod
    def _style_axis(ax, ylabel, dates):
        ax.set_ylabel(ylabel, color="#bac2de", fontsize=9, labelpad=8)
        ax.tick_params(colors="#a6adc8", labelsize=8, length=3)
        ax.spines["bottom"].set_color("#45475a")
        ax.spines["left"].set_color("#45475a")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, alpha=0.12, color="#585b70")
        limits = padded_date_limits(dates)
        if limits:
            ax.set_xlim(*limits)
        locator = AutoDateLocator(minticks=3, maxticks=7)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(ConciseDateFormatter(locator))

    @staticmethod
    def _canvas(fig, height):
        canvas = FigureCanvasQTAgg(fig)
        canvas.setMinimumHeight(height)
        canvas.setMaximumHeight(height + 30)
        canvas.setMinimumWidth(0)
        canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        return canvas

    @staticmethod
    def _section_title(text):
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        label.setStyleSheet("color: #cdd6f4;")
        return label

    @staticmethod
    def _stat(label, value, color):
        frame = QFrame()
        frame.setMinimumHeight(82)
        frame.setStyleSheet("background: #11111b; border: 1px solid #313244; border-radius: 8px;")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)
        name = QLabel(label)
        name.setStyleSheet("color: #7f849c; font-weight: bold;")
        layout.addWidget(name)
        number = QLabel(value)
        number.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        number.setStyleSheet(f"color: {color};")
        number.setWordWrap(True)
        layout.addWidget(number)
        return frame

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
