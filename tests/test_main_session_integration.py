from models.database import Database
from ui.session import SessionWidget


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
    window = main_window.MainWindow()
    qtbot.addWidget(window)
    return window


def test_home_full_routine_opens_guided_source_backed_session(
    qtbot, monkeypatch, tmp_path,
):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.home_view.full_button.click()
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
        assert window.session_view.overview.count() == 1
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
