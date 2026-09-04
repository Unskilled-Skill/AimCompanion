from PyQt6.QtWidgets import QLabel

from ui.app_shell import AppShell


def test_shell_has_exactly_five_primary_destinations(qtbot):
    destinations = {
        key: QLabel(key)
        for key in ("home", "session", "progress", "library", "tools")
    }
    shell = AppShell(destinations)
    qtbot.addWidget(shell)
    assert shell.destination_keys == (
        "home", "session", "progress", "library", "tools"
    )
    assert tuple(shell.nav_buttons) == shell.destination_keys


def test_shell_navigation_emits_destination_and_changes_widget(qtbot):
    destinations = {
        key: QLabel(key)
        for key in ("home", "session", "progress", "library", "tools")
    }
    shell = AppShell(destinations)
    qtbot.addWidget(shell)
    with qtbot.waitSignal(shell.destination_changed) as signal:
        shell.navigate("session")
    assert signal.args == ["session"]
    assert shell.currentWidget() is destinations["session"]


def test_shell_rejects_missing_destination():
    try:
        AppShell({"home": QLabel("home")})
    except ValueError as error:
        assert "exactly" in str(error)
    else:
        raise AssertionError("missing destinations were accepted")
