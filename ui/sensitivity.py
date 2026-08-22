from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QPushButton, QVBoxLayout, QWidget,
)

GAMES = {
    "Valorant": {"yaw": 0.07},
    "Apex Legends": {"yaw": 0.022},
    "CS2": {"yaw": 0.022},
    "Overwatch 2": {"yaw": 0.0066},
    "Fortnite": {"yaw": 0.0055},
    "R6 Siege": {"yaw": 0.0023},
    "Quake Champions": {"yaw": 0.0083},
    "Kovaak's": {"yaw": 0.031},
}


def convert_sensitivity(dpi, source_game, source_sensitivity, target_game):
    source_yaw = GAMES[source_game]["yaw"]
    target_yaw = GAMES[target_game]["yaw"]
    cm360 = (360 / (source_sensitivity * source_yaw)) * (2.54 / dpi)
    target = 360 / ((cm360 / 2.54) * dpi * target_yaw)
    return target, cm360


class SensitivityCalculator(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._calculate()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        title = QLabel("Sensitivity converter")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        root.addWidget(title)
        subtitle = QLabel("Match the same physical mouse distance across games. Results update automatically.")
        subtitle.setObjectName("mutedText")
        root.addWidget(subtitle)

        columns = QHBoxLayout()
        columns.setSpacing(12)
        input_card = self._card()
        form = QGridLayout(input_card)
        form.setContentsMargins(18, 16, 18, 18)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.addWidget(self._section("Input"), 0, 0, 1, 2)

        self.dpi_input = QDoubleSpinBox()
        self.dpi_input.setRange(100, 20000)
        self.dpi_input.setValue(1600)
        self.dpi_input.setDecimals(0)
        self.dpi_input.setSuffix(" DPI")
        self.source_game = QComboBox()
        self.source_game.addItems(GAMES)
        self.source_game.setCurrentText("Valorant")
        self.source_sens = QDoubleSpinBox()
        self.source_sens.setRange(0.001, 1000)
        self.source_sens.setValue(0.28)
        self.source_sens.setDecimals(4)
        self.target_game = QComboBox()
        self.target_game.addItems(GAMES)
        self.target_game.setCurrentText("Kovaak's")

        fields = [
            ("Mouse DPI", self.dpi_input),
            ("Source game", self.source_game),
            ("Source sensitivity", self.source_sens),
            ("Target game", self.target_game),
        ]
        for row, (label, widget) in enumerate(fields, 1):
            form.addWidget(QLabel(label), row, 0)
            form.addWidget(widget, row, 1)
        form.setColumnStretch(1, 1)
        columns.addWidget(input_card, 1)

        result_card = self._card()
        result = QVBoxLayout(result_card)
        result.setContentsMargins(18, 16, 18, 18)
        result.setSpacing(8)
        result.addWidget(self._section("Equivalent sensitivity"))
        self.target_label = QLabel()
        self.target_label.setFont(QFont("Segoe UI", 26, QFont.Weight.Bold))
        self.target_label.setStyleSheet("color: #a6e3a1;")
        result.addWidget(self.target_label)
        self.target_game_label = QLabel()
        self.target_game_label.setStyleSheet("color: #cdd6f4; font-weight: bold;")
        result.addWidget(self.target_game_label)
        self.distance_label = QLabel()
        self.distance_label.setObjectName("mutedText")
        result.addWidget(self.distance_label)
        result.addStretch()
        copy = QPushButton("Copy target sensitivity")
        copy.setObjectName("primaryButton")
        copy.clicked.connect(self._copy_result)
        result.addWidget(copy)
        columns.addWidget(result_card, 1)
        root.addLayout(columns)

        conversions_card = self._card()
        conversions = QVBoxLayout(conversions_card)
        conversions.setContentsMargins(18, 14, 18, 18)
        conversions.setSpacing(10)
        conversions.addWidget(self._section("Same cm/360 in every supported game"))
        self.games_grid = QGridLayout()
        self.games_grid.setHorizontalSpacing(10)
        self.games_grid.setVerticalSpacing(10)
        conversions.addLayout(self.games_grid)
        root.addWidget(conversions_card)
        root.addStretch()

        self.dpi_input.valueChanged.connect(self._calculate)
        self.source_sens.valueChanged.connect(self._calculate)
        self.source_game.currentTextChanged.connect(self._calculate)
        self.target_game.currentTextChanged.connect(self._calculate)

    def _calculate(self, *_args):
        dpi = self.dpi_input.value()
        source = self.source_game.currentText()
        target = self.target_game.currentText()
        target_sens, cm360 = convert_sensitivity(dpi, source, self.source_sens.value(), target)
        self._result_value = f"{target_sens:.4f}"
        self.target_label.setText(self._result_value)
        self.target_game_label.setText(f"in {target}")
        self.distance_label.setText(f"Physical distance: {cm360:.1f} cm/360  •  {int(dpi)} DPI")

        while self.games_grid.count():
            item = self.games_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, game in enumerate(GAMES):
            sensitivity, _ = convert_sensitivity(dpi, source, self.source_sens.value(), game)
            tile = QFrame()
            tile.setObjectName("conversionTile")
            tile.setStyleSheet("QFrame#conversionTile { background: #0d1527; border: 1px solid #263149; border-radius: 7px; }")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(12, 9, 12, 9)
            name = QLabel(game)
            name.setStyleSheet("color: #7f849c;")
            tile_layout.addWidget(name)
            value = QLabel(f"{sensitivity:.4f}")
            value.setStyleSheet("color: #cdd6f4; font-weight: bold;")
            tile_layout.addWidget(value)
            self.games_grid.addWidget(tile, index // 4, index % 4)
            self.games_grid.setColumnStretch(index % 4, 1)

    def _copy_result(self):
        QApplication.clipboard().setText(self._result_value)

    @staticmethod
    def _card():
        frame = QFrame()
        frame.setObjectName("toolCard")
        frame.setStyleSheet("QFrame#toolCard { background: #11192b; border: 1px solid #263149; border-radius: 9px; }")
        return frame

    @staticmethod
    def _section(text):
        label = QLabel(text)
        label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        label.setStyleSheet("color: #cdd6f4;")
        return label
