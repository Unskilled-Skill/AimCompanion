from dataclasses import replace
from datetime import datetime, timezone

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView

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


def test_empty_session_offers_all_training_modes(qtbot):
    widget = SessionWidget()
    qtbot.addWidget(widget)

    assert widget.session_stack.currentWidget() is widget.empty_state
    assert widget.warmup_button.text() == "Start warm-up"
    assert widget.step_button.text() == "Start step-by-step"
    assert widget.full_button.text() == "Start full routine"


def test_starting_session_replaces_empty_state_with_complete_detail_view(qtbot):
    widget = SessionWidget()
    qtbot.addWidget(widget)
    view = _view()

    widget.set_state(view)

    assert widget.session_stack.currentWidget() is widget.active_session
    assert widget.guide.scenario_title.text() == "A"
    assert "Move directly" in widget.guide.steps_label.text()
    assert "Clean stop" in widget.guide.success_label.text()
    assert widget.overview.count() == 3


def test_active_session_keeps_controls_visible_without_horizontal_scroll(qtbot):
    widget = SessionWidget()
    qtbot.addWidget(widget)
    widget.resize(900, 720)
    widget.set_state(_view())
    widget.show()
    qtbot.waitExposed(widget)

    assert widget.session_scroll.horizontalScrollBar().maximum() == 0


def test_routine_queue_cannot_create_a_false_selection(qtbot):
    widget = SessionWidget()
    qtbot.addWidget(widget)
    widget.set_state(_view())

    assert widget.overview.selectionMode() == (
        QAbstractItemView.SelectionMode.NoSelection
    )


def test_status_exposes_visual_state_for_paused_session(qtbot):
    widget = SessionWidget()
    qtbot.addWidget(widget)
    widget.set_state(replace(_view(), status="paused"))

    assert widget.status_label.property("sessionStatus") == "paused"
