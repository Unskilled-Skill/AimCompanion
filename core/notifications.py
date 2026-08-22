import os
from PyQt6.QtWidgets import QSystemTrayIcon, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QIcon, QPainter, QPixmap


class NotificationManager:
    def __init__(self):
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon()
            icon_path = os.path.join(os.path.dirname(__file__), "..", "data", "icon.png")
            if os.path.exists(icon_path):
                self.tray.setIcon(QIcon(icon_path))
            else:
                icon = QApplication.windowIcon()
                if icon.isNull():
                    pixmap = QPixmap(32, 32)
                    pixmap.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(pixmap)
                    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                    painter.setBrush(QBrush(QColor("#89b4fa")))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(2, 2, 28, 28, 8, 8)
                    painter.end()
                    icon = QIcon(pixmap)
                self.tray.setIcon(icon)
            self.tray.show()

    def notify(self, title: str, message: str, duration_ms: int = 5000):
        if self.tray:
            self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, duration_ms)

    def notify_warning(self, title: str, message: str):
        if self.tray:
            self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Warning, 5000)

    def notify_pb(self, scenario: str, old_score: float, new_score: float):
        delta = new_score - old_score
        self.notify(
            "New Personal Best!",
            f"{scenario}\n{old_score:.0f} -> {new_score:.0f} (+{delta:.0f})",
        )
