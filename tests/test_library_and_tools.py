from PyQt6.QtWidgets import QLabel

from models.database import Database
from ui.app_shell import DESTINATIONS
from ui.library import LibraryWidget
from ui.tools import ToolsWidget


def test_deathmatch_is_library_reference_not_primary_mode(qtbot):
    database = Database(":memory:")
    try:
        library = LibraryWidget(database, QLabel("Scenario browser"))
        qtbot.addWidget(library)
        assert "Deathmatch" in library.game_transfer_titles()
        assert "deathmatch" not in tuple(key for key, _ in DESTINATIONS)
    finally:
        database.close()


def test_selected_routine_exposes_full_source_detail(qtbot):
    database = Database(":memory:")
    try:
        library = LibraryWidget(database, QLabel("Scenario browser"))
        qtbot.addWidget(library)
        assert library.exercise_list.count() == 7
        assert "What to do" in library.exercise_list.item(0).text()
        assert "hnA TacFPS Aim Guide" in library.source_button.text()
    finally:
        database.close()


def test_manual_game_observation_ui_is_not_constructed(qtbot):
    database = Database(":memory:")
    try:
        library = LibraryWidget(database, QLabel("Scenario browser"))
        tools = ToolsWidget(None, database)
        qtbot.addWidget(library)
        qtbot.addWidget(tools)
        children = library.findChildren(object) + tools.findChildren(object)
        assert not any(
            getattr(widget, "objectName", lambda: "")() == "game_observation"
            for widget in children
        )
    finally:
        database.close()
