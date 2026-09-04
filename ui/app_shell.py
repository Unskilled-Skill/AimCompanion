"""Five-destination application shell."""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .status_indicator import StatusIndicator


DESTINATIONS = (
    ("home", "Home"),
    ("session", "Session"),
    ("progress", "Progress"),
    ("library", "Library"),
    ("tools", "Tools"),
)


class AppShell(QWidget):
    destination_changed = pyqtSignal(str)

    def __init__(self, destinations, topbar=None, status_indicator=None, parent=None):
        super().__init__(parent)
        required = tuple(key for key, _ in DESTINATIONS)
        if tuple(destinations) != required:
            raise ValueError(f"destinations must contain exactly {required}")
        self.destination_keys = required
        self._destinations = destinations
        self.setObjectName("appRoot")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        workspace = QWidget()
        workspace.setObjectName("workspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(24, 18, 24, 18)
        workspace_layout.setSpacing(12)
        if topbar is not None:
            workspace_layout.addWidget(topbar)
        self.status_indicator = status_indicator or StatusIndicator()
        workspace_layout.addWidget(self.status_indicator)
        self.pages = QStackedWidget()
        self.pages.setObjectName("pageStack")
        self.page_indexes = {
            key: self.pages.addWidget(destinations[key]) for key in required
        }
        workspace_layout.addWidget(self.pages, 1)
        root.addWidget(workspace, 1)
        self.navigate("home", emit=False)

    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(190)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 18, 14, 14)
        brand = QLabel("AIM COMPANION")
        brand.setObjectName("brandName")
        layout.addWidget(brand)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons = {}
        for key, label in DESTINATIONS:
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setAccessibleName(f"Open {label}")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda checked=False, destination=key: self.navigate(destination)
            )
            self.nav_group.addButton(button)
            self.nav_buttons[key] = button
            layout.addWidget(button)
        layout.addStretch()
        return sidebar

    def navigate(self, destination: str, *, emit: bool = True):
        if destination not in self.page_indexes:
            raise KeyError(f"unknown destination: {destination}")
        self.pages.setCurrentIndex(self.page_indexes[destination])
        self.nav_buttons[destination].setChecked(True)
        if emit:
            self.destination_changed.emit(destination)

    def currentWidget(self):
        return self.pages.currentWidget()
