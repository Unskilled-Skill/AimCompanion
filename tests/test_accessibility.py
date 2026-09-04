import pytest
from PyQt6.QtWidgets import QAbstractButton, QComboBox

from core.service_health import ServiceStatus
from tests.test_main_session_integration import _window


def _visible_controls(page):
    return [
        widget for widget in page.findChildren((QAbstractButton, QComboBox))
        if widget.isVisibleTo(page) and widget.focusPolicy().value != 0
    ]


@pytest.mark.parametrize(
    "destination", ["home", "session", "progress", "library", "tools"],
)
def test_destination_has_named_focusable_controls(
    qtbot, monkeypatch, tmp_path, destination,
):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.show()
        window.shell.navigate(destination)
        controls = _visible_controls(window.shell.currentWidget())
        assert controls
        assert all(
            control.accessibleName()
            or (control.text() if isinstance(control, QAbstractButton) else control.currentText())
            for control in controls
        )
    finally:
        window.close()


def test_status_not_conveyed_by_color_only(qtbot, monkeypatch, tmp_path):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.status_indicator.update_service(ServiceStatus(
            "scores", "error", "Import failed", "Bad CSV",
        ))
        assert "failed" in window.status_indicator.text().casefold()
    finally:
        window.close()
