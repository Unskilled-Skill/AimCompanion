import calendar
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

from models.database import Database


class CalendarWidget(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.current_date = datetime.now()
        self._build_ui()
        self._build_calendar()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QLabel("Training Calendar")
        header.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: white;")
        layout.addWidget(header)

        nav_row = QHBoxLayout()
        prev_btn = QPushButton("<")
        prev_btn.setFixedWidth(40)
        prev_btn.clicked.connect(self._prev_month)
        prev_btn.setStyleSheet(
            "QPushButton { background-color: #2a2a3a; color: white; border-radius: 4px; padding: 5px; }"
            "QPushButton:hover { background-color: #3a3a4a; }"
        )
        nav_row.addWidget(prev_btn)

        self.month_label = QLabel()
        self.month_label.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self.month_label.setStyleSheet("color: white;")
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav_row.addWidget(self.month_label)

        next_btn = QPushButton(">")
        next_btn.setFixedWidth(40)
        next_btn.clicked.connect(self._next_month)
        next_btn.setStyleSheet(
            "QPushButton { background-color: #2a2a3a; color: white; border-radius: 4px; padding: 5px; }"
            "QPushButton:hover { background-color: #3a3a4a; }"
        )
        nav_row.addWidget(next_btn)
        nav_row.addStretch()
        layout.addLayout(nav_row)

        day_names = QHBoxLayout()
        for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            lbl = QLabel(d)
            lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            lbl.setStyleSheet("color: #4a9eff;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            day_names.addWidget(lbl)
        layout.addLayout(day_names)

        self.grid = QGridLayout()
        self.grid.setSpacing(2)
        layout.addLayout(self.grid)

        self.stats_row = QHBoxLayout()
        self.stats_row.addStretch()
        layout.addLayout(self.stats_row)

        self._build_stats()

    def _build_calendar(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        year = self.current_date.year
        month = self.current_date.month
        self.month_label.setText(f"{calendar.month_name[month]} {year}")

        first_day = datetime(year, month, 1)
        start_weekday = (first_day.weekday()) % 7
        days_in_month = calendar.monthrange(year, month)[1]

        session_days = self._get_session_days(year, month)

        day = 1
        for row in range(6):
            for col in range(7):
                if row == 0 and col < start_weekday:
                    continue
                if day > days_in_month:
                    break

                frame = QFrame()
                frame.setFixedSize(60, 50)
                is_today = (day == datetime.now().day and
                           month == datetime.now().month and
                           year == datetime.now().year)
                is_session = day in session_days

                border = "#4a9eff" if is_today else "#333"
                bg = "#1a3a1a" if is_session else "#1a1a2a"
                if is_today:
                    bg = "#1a2a3a"

                frame.setStyleSheet(f"""
                    QFrame {{
                        background-color: {bg};
                        border: 1px solid {border};
                        border-radius: 4px;
                    }}
                """)
                fl = QVBoxLayout(frame)
                fl.setSpacing(0)
                fl.setContentsMargins(2, 2, 2, 2)

                day_lbl = QLabel(str(day))
                day_lbl.setFont(QFont("Segoe UI", 10))
                day_lbl.setStyleSheet("color: white;")
                day_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                fl.addWidget(day_lbl)

                if is_session:
                    dot = QLabel("*")
                    dot.setStyleSheet("color: #44ff88; font-weight: bold;")
                    dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    fl.addWidget(dot)
                else:
                    fl.addWidget(QLabel(""))

                self.grid.addWidget(frame, row, col)
                day += 1

    def _get_session_days(self, year, month):
        rows = self.db.conn.execute(
            "SELECT DISTINCT DATE(timestamp) as day FROM sessions"
        ).fetchall()
        days = set()
        for r in rows:
            d = datetime.fromisoformat(r["day"])
            if d.year == year and d.month == month:
                days.add(d.day)
        return days

    def _build_stats(self):
        while self.stats_row.count():
            item = self.stats_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        sessions = self.db.get_sessions(limit=100)
        total = len(sessions)
        total_min = sum(s["duration_minutes"] for s in sessions)
        streak = self.db.get_streak()

        stats = [
            (f"Total Sessions", str(total), "#4a9eff"),
            (f"Total Time", f"{total_min}min", "#44ff88"),
            (f"Streak", f"{streak}d", "#ff9944"),
        ]

        for label, value, color in stats:
            frame = QFrame()
            frame.setStyleSheet(f"""
                QFrame {{ background-color: #1e1e2e; border-radius: 6px; padding: 8px; border-left: 3px solid {color}; }}
            """)
            fl = QVBoxLayout(frame)
            fl.setSpacing(2)
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #888; font-size: 9px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fl.addWidget(lbl)
            val = QLabel(value)
            val.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            val.setStyleSheet(f"color: {color};")
            val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fl.addWidget(val)
            self.stats_row.addWidget(frame)

        self.stats_row.addStretch()

    def _prev_month(self):
        month = self.current_date.month - 1
        year = self.current_date.year
        if month < 1:
            month = 12
            year -= 1
        self.current_date = datetime(year, month, 1)
        self._build_calendar()

    def _next_month(self):
        month = self.current_date.month + 1
        year = self.current_date.year
        if month > 12:
            month = 1
            year += 1
        self.current_date = datetime(year, month, 1)
        self._build_calendar()

    def update_profile(self, profile):
        pass
