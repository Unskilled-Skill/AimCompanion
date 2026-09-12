from PyQt6.QtWidgets import QLabel, QPushButton

from models.config import TrainingConfig
from models.database import Database
from ui.library import LibraryWidget
from ui.session import SessionWidget
from core.playlist_export import export_playlist


def _window(qtbot, monkeypatch, tmp_path):
    from models import config
    from ui import main_window

    stats_dir = tmp_path / "stats"
    stats_dir.mkdir()
    monkeypatch.setattr(
        main_window, "Database",
        lambda: Database(str(tmp_path / "window.sqlite3")),
    )
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    monkeypatch.setattr(
        main_window.TrainingConfig, "get_stats_dir", lambda self: str(stats_dir),
    )
    monkeypatch.setattr(main_window, "automatic_updates_supported", lambda: False)
    monkeypatch.setattr(
        main_window,
        "export_playlist",
        lambda scenarios, name=None: export_playlist(
            scenarios, name=name, output_dir=str(tmp_path / "playlists"),
        ),
    )
    window = main_window.MainWindow()
    qtbot.addWidget(window)
    return window


def test_home_full_routine_opens_guided_source_backed_session(
    qtbot, monkeypatch, tmp_path,
):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.home_view.full_button.click()
        window.library_destination.start_routine_button.click()
        assert isinstance(window.shell.currentWidget(), SessionWidget)
        assert window.session_view.overview.count() == 7
        assert "hnA TacFPS" in window.session_view.title_label.text()
        assert window.session_view.guide.steps_label.accessibleName() == "What to do"
        assert window.session_view.guide.steps_label.text()
        assert window.session_view.guide.source_link.isEnabled()
    finally:
        window.close()


def test_home_training_modes_create_real_session_plans(
    qtbot, monkeypatch, tmp_path,
):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.home_view.warmup_button.click()
        assert window.session_coordinator.state.plan.mode.value == "warmup"
        window.session_coordinator.stop("test")
        window.home_view.step_button.click()
        assert window.session_coordinator.state.plan.mode.value == "step_by_step"
        assert window.session_view.overview.count() > 0
    finally:
        window.close()


def test_sidebar_session_navigation_updates_page_heading(
    qtbot, monkeypatch, tmp_path,
):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.shell.nav_buttons["session"].click()

        assert window.shell.currentWidget() is window.session_view
        assert window.page_title.text() == "Session"
        assert "current scenario" in window.page_subtitle.text().casefold()
    finally:
        window.close()


def test_empty_session_quick_start_creates_real_session_plan(
    qtbot, monkeypatch, tmp_path,
):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.shell.nav_buttons["session"].click()
        window.session_view.step_button.click()

        assert window.session_coordinator.state is not None
        assert window.session_coordinator.state.plan.mode.value == "step_by_step"
        assert window.session_view.session_stack.currentWidget() is (
            window.session_view.active_session
        )
    finally:
        window.close()


def test_home_full_routine_opens_routine_picker(
    qtbot, monkeypatch, tmp_path,
):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.home_view.full_button.click()

        assert window.shell.currentWidget() is window.library_destination
        assert window.library_destination.currentIndex() == 0
        assert window.session_coordinator.state is None
    finally:
        window.close()


def test_empty_session_full_routine_opens_routine_picker(
    qtbot, monkeypatch, tmp_path,
):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.shell.nav_buttons["session"].click()
        window.session_view.full_button.click()

        assert window.shell.currentWidget() is window.library_destination
        assert window.library_destination.currentIndex() == 0
        assert window.session_coordinator.state is None
    finally:
        window.close()


def test_starting_library_routine_remembers_selection(
    qtbot, monkeypatch, tmp_path,
):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        library = window.library_destination
        library.routine_selector.setCurrentIndex(1)
        start_button = next(
            button for button in library.findChildren(QPushButton)
            if button.text() == "Start this full routine"
        )
        start_button.click()

        selected_name = library._routines[1]["name"]
        assert window.session_coordinator.state.plan.source_id == selected_name
        assert TrainingConfig.load().preferred_routine == selected_name

        restored_library = LibraryWidget(window.db, QLabel("Scenarios"))
        qtbot.addWidget(restored_library)
        assert restored_library.routine_selector.currentText() == selected_name
    finally:
        window.close()


def test_completed_warmup_can_start_the_next_training_recommendation(
    qtbot, monkeypatch, tmp_path,
):
    window = _window(qtbot, monkeypatch, tmp_path)
    window.session_coordinator.launcher = lambda _: True
    try:
        window.home_view.warmup_button.click()
        state = window.session_coordinator.state
        for _ in range(sum(step.required_runs for step in state.plan.steps)):
            window.session_coordinator.confirm_manual_run()

        assert window.session_coordinator.state.status.value == "completed"
        assert window.session_view.next_button.text() == "Start training"

        window.session_view.next_button.click()

        assert window.session_coordinator.state.plan.mode.value == "step_by_step"
        assert window.session_coordinator.state.status.value == "running"
    finally:
        window.close()


def test_due_benchmarks_create_playlist_and_matching_session_queue(
    qtbot, monkeypatch, tmp_path,
):
    playlist_dir = tmp_path / "playlists"
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.home_view.step_button.click()

        plan = window.session_coordinator.state.plan
        playlist = playlist_dir / "Aim Companion Novice Benchmark Check.json"
        assert len(plan.steps) == 18
        assert playlist.is_file()
        payload = __import__("json").loads(playlist.read_text(encoding="utf-8"))
        assert [item["scenarioName"] for item in payload["scenarioList"]] == [
            step.scenario for step in plan.steps
        ]
    finally:
        window.close()
