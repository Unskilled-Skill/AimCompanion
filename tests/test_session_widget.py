from datetime import datetime, timezone

from PyQt6.QtCore import Qt

from core.sessions import SessionEngine, SessionMode, SessionPlan, SessionStep
from ui.session import SessionWidget
from ui.view_models import build_session_view


def _view(completed=False):
    steps = tuple(
        SessionStep(
            scenario=name,
            required_runs=1,
            estimated_seconds=180,
            category="Clicking",
            subcategory="Static",
            guide={
                "purpose": f"Train {name}",
                "setup": "Normal sensitivity",
                "steps": ["Move directly", "Confirm target"],
                "success": "Clean stop",
            },
            source="hnA TacFPS Aim Guide",
            source_url="https://example.test/source",
        )
        for name in ("A", "B", "C")
    )
    plan = SessionPlan(
        SessionMode.FULL_ROUTINE, "Full fixture", "v1", steps, steps
    )
    state = SessionEngine.start(
        plan, now=datetime(2026, 9, 4, tzinfo=timezone.utc)
    )
    if completed:
        for _ in steps:
            state = SessionEngine.confirm_run(state)
    return build_session_view(state, None)


def test_selected_routine_shows_full_overview_and_current_guide(qtbot):
    widget = SessionWidget()
    qtbot.addWidget(widget)
    view = _view()
    widget.set_state(view)
    assert widget.overview.count() == len(view.steps)
    assert widget.guide.scenario_title.text() == view.current_guide.scenario
    assert widget.run_progress.maximum() == view.current_guide.required_runs


def test_next_disabled_until_step_complete(qtbot):
    widget = SessionWidget()
    qtbot.addWidget(widget)
    widget.set_state(_view(False))
    assert not widget.next_button.isEnabled()
    widget.set_state(_view(True))
    assert widget.next_button.isEnabled()


def test_session_controls_are_keyboard_reachable(qtbot):
    widget = SessionWidget()
    qtbot.addWidget(widget)
    widget.set_state(_view())
    controls = widget.action_controls()
    assert all(control.focusPolicy() != Qt.FocusPolicy.NoFocus for control in controls)
    assert all(control.accessibleName() for control in controls)


def test_controls_emit_intents_without_mutating_view(qtbot):
    widget = SessionWidget()
    qtbot.addWidget(widget)
    view = _view()
    widget.set_state(view)
    with qtbot.waitSignal(widget.manual_run_requested):
        widget.manual_button.click()
    assert widget.progress_text() == view.progress_text
