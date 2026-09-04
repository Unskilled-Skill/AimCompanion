from datetime import datetime, timezone

import pytest

from core.coaching.evidence import RecommendationEvidence
from core.coaching.recommender import Recommendation, RotationState
from core.sessions import SessionMode, SessionPlan, SessionState, SessionStatus
from core.sessions.builders import append_step_by_step_recommendation
from core.sessions.repository import SessionRepository
from models.database import Database


NOW = datetime(2026, 9, 4, 16, 0, tzinfo=timezone.utc)


def _recommendation(seconds=240):
    return Recommendation(
        kind="weakness",
        scenario="Static A",
        category="Clicking",
        subcategory="Static",
        priority_rank=1,
        estimated_seconds=seconds,
        guide={"steps": ["Move directly."]},
        evidence=RecommendationEvidence(
            rule="weakness_rotation",
            summary="Priority 1 weakness",
            definition_version="kovaaks_s5",
            confidence="high",
        ),
    )


def _draft(status=SessionStatus.READY):
    plan = SessionPlan(
        mode=SessionMode.STEP_BY_STEP,
        source_id="adaptive",
        source_version="kovaaks_s5",
        steps=(),
        official_steps=(),
    )
    return SessionState(plan, status, 0, 0, NOW, NOW)


def test_step_by_step_block_is_between_three_and_five_minutes():
    state = append_step_by_step_recommendation(_draft(), _recommendation(seconds=900))
    assert 180 <= state.plan.steps[-1].estimated_seconds <= 300
    assert state.status is SessionStatus.RUNNING


def test_next_block_appends_only_after_previous_block_completed():
    running = append_step_by_step_recommendation(_draft(), _recommendation())
    with pytest.raises(ValueError, match="previous block"):
        append_step_by_step_recommendation(running, _recommendation())

    completed = SessionState(
        running.plan,
        SessionStatus.COMPLETED,
        0,
        running.current_step.required_runs,
        NOW,
        NOW,
    )
    continued = append_step_by_step_recommendation(completed, _recommendation())
    assert len(continued.plan.steps) == 2
    assert continued.current_step_index == 1


def test_stopped_step_by_step_session_never_appends():
    with pytest.raises(ValueError, match="stopped"):
        append_step_by_step_recommendation(_draft(SessionStatus.STOPPED), _recommendation())


def test_rotation_state_round_trips():
    database = Database(":memory:")
    try:
        repository = SessionRepository(database.conn)
        state = RotationState(4, "Static B", "Clicking / Static")
        repository.save_rotation_state(state)
        assert repository.load_rotation_state() == state
    finally:
        database.close()
