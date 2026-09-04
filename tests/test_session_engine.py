from datetime import datetime, timezone

import pytest

from core.sessions import (
    InvalidSessionTransition,
    SessionEngine,
    SessionMode,
    SessionPlan,
    SessionStatus,
    SessionStep,
)


NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


def _step(name: str, runs: int = 2) -> SessionStep:
    return SessionStep(
        scenario=name,
        required_runs=runs,
        estimated_seconds=180,
        category="Clicking",
        subcategory="Static",
        guide={"purpose": f"Train {name}"},
        source="Fixture",
        source_url="https://example.test/source",
    )


@pytest.fixture
def plan() -> SessionPlan:
    steps = (_step("A"), _step("B", runs=1))
    return SessionPlan(
        mode=SessionMode.FULL_ROUTINE,
        source_id="fixture",
        source_version="1",
        steps=steps,
        official_steps=steps,
    )


def test_confirming_required_runs_advances_to_next_step(plan):
    state = SessionEngine.start(plan, now=NOW)
    state = SessionEngine.confirm_run(state, now=NOW)
    assert state.current_step_index == 0
    assert state.confirmed_runs == 1

    state = SessionEngine.confirm_run(state, now=NOW)
    assert state.current_step_index == 1
    assert state.confirmed_runs == 0


def test_last_required_run_completes_without_invalid_current_step(plan):
    state = SessionEngine.start(plan, now=NOW)
    state = SessionEngine.confirm_run(state, now=NOW)
    state = SessionEngine.confirm_run(state, now=NOW)
    state = SessionEngine.confirm_run(state, now=NOW)

    assert state.status is SessionStatus.COMPLETED
    assert state.current_step.scenario == "B"
    assert state.confirmed_runs == 1


def test_stopped_session_rejects_more_runs(plan):
    state = SessionEngine.stop(
        SessionEngine.start(plan, now=NOW), reason="user", now=NOW
    )
    with pytest.raises(InvalidSessionTransition, match="stopped"):
        SessionEngine.confirm_run(state, now=NOW)


def test_restart_step_discards_partial_runs(plan):
    state = SessionEngine.confirm_run(SessionEngine.start(plan, now=NOW), now=NOW)
    assert SessionEngine.restart_step(state, now=NOW).confirmed_runs == 0


def test_confirm_run_rejects_paused_state(plan):
    state = SessionEngine.pause(SessionEngine.start(plan, now=NOW), now=NOW)
    with pytest.raises(InvalidSessionTransition, match="paused"):
        SessionEngine.confirm_run(state, now=NOW)


def test_pause_resume_and_stop_preserve_immutable_prior_state(plan):
    running = SessionEngine.start(plan, now=NOW)
    paused = SessionEngine.pause(running, now=NOW)
    resumed = SessionEngine.resume(paused, now=NOW)
    stopped = SessionEngine.stop(resumed, reason="user", now=NOW)

    assert running.status is SessionStatus.RUNNING
    assert paused.status is SessionStatus.PAUSED
    assert resumed.status is SessionStatus.RUNNING
    assert stopped.status is SessionStatus.STOPPED
    assert stopped.stop_reason == "user"


def test_invalid_plan_rejects_nonpositive_runs():
    with pytest.raises(ValueError, match="required_runs"):
        _step("broken", runs=0)


def test_empty_plan_is_only_allowed_as_step_by_step_draft():
    draft = SessionPlan(
        mode=SessionMode.STEP_BY_STEP,
        source_id="adaptive",
        source_version="1",
        steps=(),
        official_steps=(),
    )
    with pytest.raises(ValueError, match="no steps"):
        SessionEngine.start(draft, now=NOW)

    with pytest.raises(ValueError, match="at least one step"):
        SessionPlan(
            mode=SessionMode.FULL_ROUTINE,
            source_id="broken",
            source_version="1",
            steps=(),
            official_steps=(),
        )


def test_guide_is_deeply_read_only_at_mapping_boundary():
    source = {"purpose": "original"}
    step = SessionStep(
        scenario="A",
        required_runs=1,
        estimated_seconds=180,
        category="Clicking",
        subcategory="Static",
        guide=source,
        source="Fixture",
        source_url="https://example.test/source",
    )
    source["purpose"] = "mutated"

    assert step.guide["purpose"] == "original"
    with pytest.raises(TypeError):
        step.guide["purpose"] = "blocked"
