import calendar
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from models.database import Database


class CalendarWidget(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.current_date = datetime.now()
        self._build_ui()
        self._build_calendar()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        top = QHBoxLayout()
        title = QLabel("Training calendar")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        top.addWidget(title)
        top.addStretch()
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: #94e2d5; font-weight: bold;")
        top.addWidget(self.stats_label)
        root.addLayout(top)

        card = QFrame()
        card.setStyleSheet("QFrame#calendarCard { background: #11192b; border: 1px solid #263149; border-radius: 10px; }")
        card.setObjectName("calendarCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 16)
        card_layout.setSpacing(10)

        nav = QHBoxLayout()
        prev_btn = QPushButton("‹")
        prev_btn.setObjectName("secondaryButton")
        prev_btn.setFixedWidth(42)
        prev_btn.clicked.connect(self._prev_month)
        nav.addWidget(prev_btn)
        self.month_label = QLabel()
        self.month_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.month_label.setStyleSheet("color: #cdd6f4;")
        nav.addWidget(self.month_label)
        next_btn = QPushButton("›")
        next_btn.setObjectName("secondaryButton")
        next_btn.setFixedWidth(42)
        next_btn.clicked.connect(self._next_month)
        nav.addWidget(next_btn)
        card_layout.addLayout(nav)

        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(7)
        self.grid.setVerticalSpacing(7)
        for col, day in enumerate(["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]):
            label = QLabel(day)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("color: #89b4fa; font-weight: bold;")
            self.grid.addWidget(label, 0, col)
            self.grid.setColumnStretch(col, 1)
        for row in range(1, 7):
            self.grid.setRowStretch(row, 1)
        card_layout.addLayout(self.grid, 1)
        root.addWidget(card, 1)

        legend = QHBoxLayout()
        legend.addWidget(QLabel("●  Training day"))
        legend.itemAt(0).widget().setStyleSheet("color: #a6e3a1;")
        legend.addWidget(QLabel("Outlined  •  Today"))
        legend.itemAt(1).widget().setStyleSheet("color: #89b4fa;")
        legend.addStretch()
        root.addLayout(legend)

    def _build_calendar(self):
        while self.grid.count() > 7:
            item = self.grid.takeAt(7)
            if item.widget():
                item.widget().deleteLater()

        year, month = self.current_date.year, self.current_date.month
        self.month_label.setText(f"{calendar.month_name[month]} {year}")
        session_days = self._get_session_days(year, month)
        first_weekday, days_in_month = calendar.monthrange(year, month)
        today = datetime.now()

        for day in range(1, days_in_month + 1):
            cell_index = first_weekday + day - 1
            row, col = divmod(cell_index, 7)
            is_today = day == today.day and month == today.month and year == today.year
            is_session = day in session_days
            cell = QFrame()
            border = "#89b4fa" if is_today else "#2b374f"
            background = "#142b2c" if is_session else "#0d1527"
            cell.setStyleSheet(f"QFrame {{ background: {background}; border: 1px solid {border}; border-radius: 7px; }}")
            cell.setMinimumHeight(58)
            layout = QVBoxLayout(cell)
            layout.setContentsMargins(8, 6, 8, 6)
            number = QLabel(str(day))
            number.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            number.setStyleSheet("color: #e5eaf5; font-weight: bold;")
            layout.addWidget(number)
            layout.addStretch()
            if is_session:
                dot = QLabel("● trained")
                dot.setStyleSheet("color: #a6e3a1; font-size: 8pt;")
                layout.addWidget(dot)
            self.grid.addWidget(cell, row + 1, col)

        sessions = self.db.get_sessions(limit=1000)
        month_sessions = [s for s in sessions if s["timestamp"].startswith(f"{year:04d}-{month:02d}")]
        month_minutes = sum(s["duration_minutes"] for s in month_sessions)
        self.stats_label.setText(f"This month: {len(month_sessions)} sessions  •  {month_minutes} min  •  streak {self.db.get_streak()} days")

    def _get_session_days(self, year, month):
        rows = self.db.conn.execute("SELECT DISTINCT DATE(timestamp) AS day FROM sessions").fetchall()
        return {datetime.fromisoformat(row["day"]).day for row in rows if datetime.fromisoformat(row["day"]).year == year and datetime.fromisoformat(row["day"]).month == month}

    def _prev_month(self):
        month, year = self.current_date.month - 1, self.current_date.year
        if month < 1:
            month, year = 12, year - 1
        self.current_date = datetime(year, month, 1)
        self._build_calendar()

    def _next_month(self):
        month, year = self.current_date.month + 1, self.current_date.year
        if month > 12:
            month, year = 1, year + 1
        self.current_date = datetime(year, month, 1)
        self._build_calendar()

    def update_profile(self, profile):
        self._build_calendar()
