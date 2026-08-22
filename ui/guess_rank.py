import random
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from models.database import Database
from models.benchmark import TIERS, score_to_energy, energy_to_tier, BENCHMARKS
from core.recommender import SCENARIOS


class GuessRank(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.current_score = None
        self.correct_tier = ""
        self._build_ui()
        self._new_question()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Guess the Rank")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        subtitle = QLabel("Test your knowledge of VT tier thresholds")
        subtitle.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(subtitle)

        self.question_frame = QFrame()
        self.question_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.question_frame.setStyleSheet("QFrame { background-color: #1e1e2e; border-radius: 8px; padding: 20px; }")
        q_layout = QVBoxLayout(self.question_frame)

        self.scenario_label = QLabel("")
        self.scenario_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.scenario_label.setStyleSheet("color: white;")
        self.scenario_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        q_layout.addWidget(self.scenario_label)

        self.score_label = QLabel("")
        self.score_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self.score_label.setStyleSheet("color: #4a9eff;")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        q_layout.addWidget(self.score_label)

        q_hint = QLabel("What tier is this score?")
        q_hint.setStyleSheet("color: #888;")
        q_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        q_layout.addWidget(q_hint)

        layout.addWidget(self.question_frame)

        self.answers_layout = QHBoxLayout()
        self.answer_buttons = []
        for tier in TIERS:
            btn = QPushButton(tier["name"])
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #2a2a3a; color: {tier['color']};
                    border-radius: 6px; padding: 10px 12px; font-weight: bold;
                    border: 2px solid #333;
                }}
                QPushButton:hover {{ border-color: {tier['color']}; }}
            """)
            btn.clicked.connect(lambda checked, t=tier["name"]: self._answer(t))
            self.answer_buttons.append(btn)
            self.answers_layout.addWidget(btn)
        layout.addLayout(self.answers_layout)

        self.result_label = QLabel("")
        self.result_label.setFont(QFont("Segoe UI", 14))
        self.result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.result_label)

        self.score_label_stat = QLabel("")
        self.score_label_stat.setStyleSheet("color: #888;")
        self.score_label_stat.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.score_label_stat)

        next_btn = QPushButton("Next Question")
        next_btn.setStyleSheet(
            "QPushButton { background-color: #4a9eff; color: white; border-radius: 4px; padding: 10px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3a8eef; }"
        )
        next_btn.clicked.connect(self._new_question)
        layout.addWidget(next_btn)

        layout.addStretch()

    def _new_question(self):
        bench = random.choice(BENCHMARKS)
        self.current_bench_name = bench["name"]
        targets = bench.get("targets", {})
        if targets:
            t_scores = [float(v) for v in targets.values()]
            min_sc = max(10, int(min(t_scores) * 0.75))
            max_sc = int(max(t_scores) * 1.15)
        else:
            min_sc, max_sc = 300, 1500

        self.current_score = random.randint(min_sc, max_sc)
        actual_energy = score_to_energy(self.current_bench_name, self.current_score)
        self.correct_tier = energy_to_tier(actual_energy)
        self.scenario_label.setText(bench["scenario"])
        self.score_label.setText(f"{self.current_score:,}")
        self.result_label.setText("")
        self.score_label_stat.setText("")

        for btn in self.answer_buttons:
            btn.setEnabled(True)
            btn.setStyleSheet(btn.styleSheet().replace("border: 2px solid #44ff88;", "border: 2px solid #333;"))

    def _answer(self, chosen):
        for btn in self.answer_buttons:
            btn.setEnabled(False)
            if btn.text() == self.correct_tier:
                btn.setStyleSheet(btn.styleSheet().replace("border: 2px solid #333;", "border: 2px solid #44ff88;"))

        if chosen == self.correct_tier:
            self.result_label.setText("Correct!")
            self.result_label.setStyleSheet("color: #44ff88; font-weight: bold;")
        else:
            self.result_label.setText(f"Wrong! It was {self.correct_tier}")
            self.result_label.setStyleSheet("color: #ff4444; font-weight: bold;")

        actual_energy = score_to_energy(self.current_bench_name, self.current_score)
        self.score_label_stat.setText(
            f"Score: {self.current_score:,} | Energy: {actual_energy:.1f} | Tier: {self.correct_tier}"
        )

