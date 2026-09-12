"""Behavioral regressions found in the algorithm and session UI review."""

from dataclasses import replace
from datetime import datetime

import pytest

from core.run_tracker import KovaaksRunTracker
from core.session_coordinator import SessionCoordinator
from core.sessions import SessionStatus
from core.sessions.repository import SessionRepository
from models.database import Database
from tests.test_main_session_integration import _window
from tests.test_score_importer import write_score
from tests.test_session_coordinator import _two_step_plan
from tests.test_session_widget import _view
from ui.session import SessionWidget
from ui.view_models import build_session_view


def test_manual_mode_does_not_count_csv_results(qtbot, monkeypatch, tmp_path):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.session_view.advance_mode.setCurrentIndex(1)
        window.session_coordinator.start(_two_step_plan(first_runs=2))
        write_score(tmp_path / "stats" / "score.csv", datetime(2026, 1, 1),
                    scenario="Static A")
        window._poll_session_runs()
        assert window.session_coordinator.state.confirmed_runs == 0
        window.session_view.manual_button.click()
        assert window.session_coordinator.state.confirmed_runs == 1
    finally:
        window.close()


def test_paused_ui_disables_run_confirmation(qtbot):
    widget = SessionWidget()
    qtbot.addWidget(widget)
    widget.set_state(replace(_view(), status="paused"))
    assert not widget.manual_button.isEnabled()
    assert widget.pause_button.text() == "Resume"
    assert widget.pause_button.accessibleName() == "Resume"


def test_completed_full_routine_can_start_training(qtbot, monkeypatch, tmp_path):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        window.session_coordinator.automatic_next = False
        window.session_coordinator.start(_two_step_plan())
        window.session_coordinator.confirm_manual_run()
        window.session_coordinator.confirm_manual_run()
        window.session_view.next_button.click()
        assert window.session_coordinator.state.status is SessionStatus.RUNNING
        assert window.session_coordinator.state.plan.mode.value == "step_by_step"
    finally:
        window.close()


def test_tracking_continues_without_automatic_launch(tmp_path):
    database = Database(":memory:")
    tracker = KovaaksRunTracker(str(tmp_path))
    coordinator = SessionCoordinator(SessionRepository(database.conn), tracker)
    try:
        coordinator.start(_two_step_plan())
        write_score(tmp_path / "first.csv", datetime(2026, 1, 1), scenario="Static A")
        coordinator.confirm_detected_runs(tracker.poll())
        write_score(tmp_path / "second.csv", datetime(2026, 1, 2), scenario="Static B")
        coordinator.confirm_detected_runs(tracker.poll())
        assert coordinator.state.status is SessionStatus.COMPLETED
        assert not tracker.active
    finally:
        database.close()


def test_skip_preserves_actual_runs_and_survives_recovery(qtbot, monkeypatch, tmp_path):
    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        coordinator = window.session_coordinator
        coordinator.automatic_next = False
        coordinator.start(_two_step_plan(first_runs=3, second_runs=2))
        coordinator.confirm_manual_run()
        coordinator.pause()
        window.session_view.skip_button.click()
        assert coordinator.state.status is SessionStatus.PAUSED
        assert coordinator.state.current_step_index == 1
        rows = window.db.conn.execute("SELECT * FROM session_runs").fetchall()
        assert len(rows) == 1  # Only the run actually confirmed before skipping.
        recovered = SessionRepository(window.db.conn).load_active()
        view = build_session_view(recovered, None)
        assert view.steps[0].skipped
        assert not view.steps[0].completed
        assert "1 / 3" in view.steps[0].run_text
        assert "Skipped" in window.session_view.overview.item(0).text()
        assert "Scenario 2 of 2" in window.session_view.position_label.text()
        coordinator.resume()
        window.session_view.skip_button.click()  # Last scenario is skippable too.
        assert coordinator.state.status is SessionStatus.COMPLETED
        assert len(window.db.conn.execute("SELECT * FROM session_runs").fetchall()) == 1
        assert "2 skipped" in window.session_view.queue_summary.text()
        assert not window.session_view.skip_button.isEnabled()
    finally:
        window.close()


def test_recommender_allows_unavoidable_skill_repeat():
    from core.coaching.recommender import CoachingRecommender, RotationState
    from tests.test_coaching_recommender import _context

    context = _context()
    context = replace(context, candidates=context.candidates[:2], rotation=RotationState(
        last_subcategory="Clicking / Static", last_scenario="Static A",
    ))
    assert CoachingRecommender().next(context).scenario == "Static B"


def test_due_benchmark_uses_official_candidates_for_missing_catalog_skills(
    qtbot, monkeypatch, tmp_path,
):
    from core.benchmarks import DefinitionRepository
    from core.coaching.freshness import BenchmarkFreshness

    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        definitions = DefinitionRepository.bundled().load_active()
        freshness = BenchmarkFreshness(window.db.conn)
        for key in definitions.required_subcategories:
            if key != "Clicking / Linear":
                freshness.record_benchmark(key)
        recommendation = window._next_recommendation()
        official = {item.scenario for item in definitions.benchmarks
                    if item.difficulty == "Novice" and item.subcategory == "Linear"}
        assert recommendation.scenario in official
        window._start_step_by_step_home()
        assert all(step.scenario in official for step in window.session_coordinator.state.plan.steps)
    finally:
        window.close()


@pytest.mark.parametrize("mode,expected", [("best", 820), ("latest", 410), ("average", 615)])
def test_profile_totals_use_the_selected_score_mode(mode, expected):
    from core.analyzer import build_profile
    from core.benchmarks import DefinitionRepository
    from tests.test_analyzer_official_profile import _score_for

    definition = next(item for item in DefinitionRepository.bundled().load_active().benchmarks
                      if item.name == "VT 1w4ts Novice S5")
    database = Database(":memory:")
    try:
        database.insert_score(_score_for(definition, 820, datetime(2026, 1, 1)), "old.csv")
        database.insert_score(_score_for(definition, 410, datetime(2026, 1, 2)), "new.csv")
        profile = build_profile(database, difficulty="Novice", score_mode=mode)
        assert profile.overall_score == expected
        static = next(sub for cat in profile.categories for sub in cat.subcategories
                      if sub.name == "Static")
        assert static.combined_score == expected
        assert static.benchmarks[0].best_score == 820
    finally:
        database.close()


def test_completed_blocks_update_freshness_once_and_skips_do_not(tmp_path):
    from core.coaching.freshness import BenchmarkFreshness

    database = Database(":memory:")
    repository = SessionRepository(database.conn)
    coordinator = SessionCoordinator(repository, KovaaksRunTracker(str(tmp_path)))
    freshness = BenchmarkFreshness(database.conn)
    try:
        freshness.record_benchmark("Clicking / Static")
        coordinator.start(_two_step_plan(first_runs=2, second_runs=2))
        coordinator.confirm_manual_run()
        assert freshness.status(["Clicking / Static"])["Clicking / Static"].blocks_since_check == 0
        coordinator.confirm_manual_run()
        repository.save(coordinator.state)
        coordinator.skip_step()
        assert freshness.status(["Clicking / Static"])["Clicking / Static"].blocks_since_check == 1
    finally:
        database.close()


def test_session_actions_stay_on_screen_while_guide_scrolls(qtbot):
    from pathlib import Path
    from PyQt6.QtCore import QPoint
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    previous_style = app.styleSheet()
    app.setStyleSheet(Path("style.qss").read_text(encoding="utf-8"))
    try:
        widget = SessionWidget()
        qtbot.addWidget(widget)
        widget.resize(900, 720)
        widget.set_state(_view())
        widget.show()
        qtbot.waitExposed(widget)
        for position in (0, widget.session_scroll.verticalScrollBar().maximum()):
            widget.session_scroll.verticalScrollBar().setValue(position)
            for button in (*widget.action_controls(), widget.skip_button):
                bottom = button.mapTo(widget, QPoint(0, button.height()))
                assert widget.rect().contains(bottom)
    finally:
        app.setStyleSheet(previous_style)


def test_skipped_step_stays_omitted_after_finishing_remaining_runs(tmp_path):
    database = Database(":memory:")
    coordinator = SessionCoordinator(
        SessionRepository(database.conn), KovaaksRunTracker(str(tmp_path)),
    )
    try:
        coordinator.start(_two_step_plan(first_runs=3, second_runs=2))
        coordinator.confirm_manual_run()
        coordinator.skip_step()
        coordinator.confirm_manual_run()
        coordinator.confirm_manual_run()
        assert coordinator.state.status is SessionStatus.COMPLETED
        assert coordinator.state.skipped_steps == ((0, 1),)
        assert len(database.conn.execute("SELECT * FROM session_runs").fetchall()) == 3
        view = build_session_view(coordinator.state, None)
        assert view.steps[0].skipped and not view.steps[0].completed
        assert view.steps[1].completed
    finally:
        database.close()


def test_warmup_completion_does_not_age_benchmarks(tmp_path):
    from core.coaching.freshness import BenchmarkFreshness
    from core.sessions import SessionMode

    database = Database(":memory:")
    coordinator = SessionCoordinator(
        SessionRepository(database.conn), KovaaksRunTracker(str(tmp_path)),
    )
    try:
        freshness = BenchmarkFreshness(database.conn)
        freshness.record_benchmark("Clicking / Static")
        coordinator.start(replace(_two_step_plan(), mode=SessionMode.WARMUP))
        coordinator.confirm_manual_run()
        coordinator.confirm_manual_run()
        assert freshness.status(["Clicking / Static"])["Clicking / Static"].blocks_since_check == 0
    finally:
        database.close()


def test_continuing_a_benchmark_check_keeps_official_scenarios(qtbot, monkeypatch, tmp_path):
    from core.benchmarks import DefinitionRepository

    window = _window(qtbot, monkeypatch, tmp_path)
    try:
        coordinator = window.session_coordinator
        coordinator.automatic_next = False
        window._start_step_by_step_home()
        while coordinator.state.status is SessionStatus.RUNNING:
            coordinator.confirm_manual_run()
        # Manual confirmations don't provide benchmark scores: checks remain due.
        window._continue_step_by_step()
        official = {item.scenario for item in DefinitionRepository.bundled().load_active().benchmarks
                    if item.difficulty == "Novice"}
        assert coordinator.state.status is SessionStatus.RUNNING
        assert all(step.scenario in official for step in coordinator.state.plan.steps)
        assert all(step.required_runs == 1 for step in coordinator.state.plan.steps)
    finally:
        window.close()


def test_version_eight_session_migrates_without_losing_progress(tmp_path):
    path = str(tmp_path / "upgrade.sqlite3")
    database = Database(path)
    coordinator = SessionCoordinator(
        SessionRepository(database.conn), KovaaksRunTracker(str(tmp_path)),
    )
    coordinator.start(_two_step_plan(first_runs=3))
    coordinator.confirm_manual_run()
    # Reproduce the v8 schema and existing session that an upgrade encounters.
    database.conn.execute("ALTER TABLE session_state DROP COLUMN skipped_steps_json")
    database.conn.execute("DELETE FROM schema_migrations WHERE version = 9")
    database.conn.commit()
    database.close()
    database = Database(path)
    try:
        recovered = SessionRepository(database.conn).load_active()
        assert recovered.status is SessionStatus.PAUSED
        assert recovered.confirmed_runs == 1
        assert recovered.skipped_steps == ()
        assert database.schema_version == 9
        assert (tmp_path / "upgrade.pre-v9.sqlite3").is_file()
    finally:
        database.close()
