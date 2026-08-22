from PyQt6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from ui.builder import RoutineBuilder
from ui.calendar import CalendarWidget
from ui.comparison import ComparisonWidget
from ui.sensitivity import SensitivityCalculator
from ui.sessions import SessionLogger


class ToolsWidget(QWidget):
    """Home for useful secondary tools that were previously unreachable."""

    def __init__(self, profile, db):
        super().__init__()
        self.profile = profile
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.sessions = SessionLogger(db)
        self.calendar = CalendarWidget(db)
        self.comparison = ComparisonWidget(profile, db)
        self.builder = RoutineBuilder(profile, db)
        self.sensitivity = SensitivityCalculator()
        self.tabs.addTab(self.sessions, "Sessions")
        self.tabs.addTab(self.calendar, "Calendar")
        self.tabs.addTab(self.comparison, "Compare")
        self.tabs.addTab(self.builder, "Routine builder")
        self.tabs.addTab(self.sensitivity, "Sensitivity")
        layout.addWidget(self.tabs)

    def update_profile(self, profile):
        self.profile = profile
        self.sessions._update_stats()
        self.sessions._refresh_history()
        self.calendar.update_profile(profile)
        self.comparison.update_profile(profile)
        self.builder.update_profile(profile)
