from datetime import datetime, timezone

from PyQt6.QtWidgets import QApplication

from core.sessions import SessionEngine, SessionMode, SessionPlan, SessionStep
from ui.scenario_guide import ScenarioGuideWidget
from ui.view_models import build_session_view


def _state(with_adjust=True):
    guide = {
        "purpose": "Train fast stopping.",
        "setup": "Use normal sensitivity.",
        "steps": ["Snap fast.", "Reacquire immediately."],
        "success": "Aggressive stops without hesitation.",
    }
    if with_adjust:
        guide["adjust"] = "Reduce difficulty below 25% accuracy."
    step = SessionStep(
        scenario="Example",
        required_runs=7,
        estimated_seconds=420,
        category="Clicking",
        subcategory="Static",
        guide=guide,
        source="hnA TacFPS Aim Guide",
        source_url="https://example.test/hna",
    )
    plan = SessionPlan(
        mode=SessionMode.FULL_ROUTINE,
        source_id="hnA example",
        source_version="v1",
        steps=(step,),
        official_steps=(step,),
    )
    return SessionEngine.start(
        plan, now=datetime(2026, 9, 4, tzinfo=timezone.utc)
    )


def test_source_guide_exposes_all_authored_fields():
    state = _state()
    guide = build_session_view(state, evidence=None).current_guide
    assert guide.purpose == "Train fast stopping."
    assert guide.setup == "Use normal sensitivity."
    assert guide.steps == ("Snap fast.", "Reacquire immediately.")
    assert guide.success == "Aggressive stops without hesitation."
    assert guide.required_runs == state.current_step.required_runs
    assert guide.source == "hnA TacFPS Aim Guide"


def test_absent_adjustment_is_omitted_not_invented():
    guide = build_session_view(_state(with_adjust=False), evidence=None).current_guide
    assert guide.adjustment is None


def test_guide_sections_have_accessible_names(qtbot):
    QApplication.instance() or QApplication([])
    widget = ScenarioGuideWidget()
    qtbot.addWidget(widget)
    widget.set_guide(build_session_view(_state(), None).current_guide)
    assert widget.run_progress.accessibleName() == "Scenario run progress"
    assert widget.source_link.accessibleName() == "Open source guidance"
    assert widget.adjustment_label.isVisibleTo(widget)


def test_adjustment_section_hides_when_source_omits_it(qtbot):
    QApplication.instance() or QApplication([])
    widget = ScenarioGuideWidget()
    qtbot.addWidget(widget)
    widget.set_guide(build_session_view(_state(False), None).current_guide)
    assert widget.adjustment_label.isHidden()
