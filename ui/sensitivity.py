from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QFrame, QGridLayout, QPushButton, QDoubleSpinBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

GAMES = {
    "Valorant": {"sens_type": "multiplier", "yaw": 0.07},
    "Apex Legends": {"sens_type": "multiplier", "yaw": 0.022},
    "CS2": {"sens_type": "multiplier", "yaw": 0.022},
    "Overwatch 2": {"sens_type": "multiplier", "yaw": 0.0066},
    "Fortnite": {"sens_type": "multiplier", "yaw": 0.0055},
    "R6 Siege": {"sens_type": "multiplier", "yaw": 0.0023},
    "Quake Champions": {"sens_type": "multiplier", "yaw": 0.0083},
    "Kovaak's": {"sens_type": "multiplier", "yaw": 0.031},
}


class SensitivityCalculator(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Sensitivity Calculator")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        subtitle = QLabel("Convert sensitivity between games")
        subtitle.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(subtitle)

        form = QGridLayout()
        form.setSpacing(10)

        form.addWidget(QLabel("DPI:"), 0, 0)
        self.dpi_input = QDoubleSpinBox()
        self.dpi_input.setRange(100, 20000)
        self.dpi_input.setValue(1600)
        self.dpi_input.setStyleSheet(
            "QDoubleSpinBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
        )
        form.addWidget(self.dpi_input, 0, 1)

        form.addWidget(QLabel("Source Game:"), 1, 0)
        self.source_game = QComboBox()
        self.source_game.addItems(GAMES.keys())
        self.source_game.setStyleSheet(
            "QComboBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background-color: #1a1a2a; color: white; }"
        )
        self.source_game.setCurrentText("Valorant")
        form.addWidget(self.source_game, 1, 1)

        form.addWidget(QLabel("Source Sensitivity:"), 2, 0)
        self.source_sens = QDoubleSpinBox()
        self.source_sens.setRange(0.001, 1000)
        self.source_sens.setValue(0.28)
        self.source_sens.setDecimals(4)
        self.source_sens.setStyleSheet(
            "QDoubleSpinBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
        )
        form.addWidget(self.source_sens, 2, 1)

        form.addWidget(QLabel("Target Game:"), 3, 0)
        self.target_game = QComboBox()
        self.target_game.addItems(GAMES.keys())
        self.target_game.setStyleSheet(
            "QComboBox { background-color: #1a1a2a; color: white; border-radius: 4px; padding: 5px; }"
            "QComboBox::drop-down { border: none; }"
            "QComboBox QAbstractItemView { background-color: #1a1a2a; color: white; }"
        )
        self.target_game.setCurrentText("Kovaak's")
        form.addWidget(self.target_game, 3, 1)

        layout.addLayout(form)

        calc_btn = QPushButton("Calculate")
        calc_btn.setStyleSheet(
            "QPushButton { background-color: #4a9eff; color: white; border-radius: 4px; padding: 8px 16px; font-weight: bold; }"
            "QPushButton:hover { background-color: #3a8eef; }"
        )
        calc_btn.clicked.connect(self._calculate)
        layout.addWidget(calc_btn)

        self.result_frame = QFrame()
        self.result_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.result_frame.setStyleSheet("""
            QFrame { background-color: #1e1e2e; border-radius: 8px; padding: 15px; border: 1px solid #333; }
        """)
        self.result_layout = QVBoxLayout(self.result_frame)
        layout.addWidget(self.result_frame)

        self._calculate()

    def _calculate(self):
        while self.result_layout.count():
            item = self.result_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        dpi = self.dpi_input.value()
        source = self.source_game.currentText()
        target = self.target_game.currentText()
        sens = self.source_sens.value()

        source_yaw = GAMES[source]["yaw"]
        target_yaw = GAMES[target]["yaw"]

        cm360_source = (360 / (sens * source_yaw)) * (2.54 / dpi)
        target_sens = 360 / ((cm360_source / 2.54) * dpi * target_yaw)

        result_lbl = QLabel("Result")
        result_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        result_lbl.setStyleSheet("color: #4a9eff;")
        self.result_layout.addWidget(result_lbl)

        sens_val = QLabel(f"{target_sens:.4f}")
        sens_val.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        sens_val.setStyleSheet("color: #44ff88;")
        sens_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_layout.addWidget(sens_val)

        details = QLabel(f"cm/360: {cm360_source:.1f}cm | DPI: {int(dpi)}")
        details.setStyleSheet("color: #aaa;")
        details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.result_layout.addWidget(details)

        all_games = QHBoxLayout()
        all_games.setSpacing(15)
        for game_name, game_data in GAMES.items():
            if game_name == source:
                continue
            game_yaw = game_data["yaw"]
            game_sens = 360 / ((cm360_source / 2.54) * dpi * game_yaw)
            game_lbl = QLabel(f"{game_name}: {game_sens:.4f}")
            game_lbl.setStyleSheet("color: #ccc; font-size: 10px;")
            all_games.addWidget(game_lbl)
        all_games.addStretch()
        self.result_layout.addLayout(all_games)
