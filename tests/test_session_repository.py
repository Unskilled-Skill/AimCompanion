from datetime import datetime, timezone

import pytest

from core.sessions import SessionEngine, SessionMode, SessionPlan, SessionStatus, SessionStep
from core.sessions.repository import SessionRepository
from models.database import Database


NOW = datetime(2026, 9, 4, 14, 0, tzinfo=timezone.utc)


def _step(name: str, runs: int = 2, guide=None) -> SessionStep:
    return SessionStep(
        scenario=name,
        required_runs=runs,
        estimated_seconds=runs * 60,
        category="Clicking",
        subcategory="Static",
        guide=guide or {"setup": "Exact", "steps": [f"Do {name}"]},
        source="Fixture",
        source_url="https://example.test/source",
    )


def _full_plan(start=0) -> SessionPlan:
    official = tuple(_step(name, runs=7 if name == "C" else 2) for name in "ABCDE")
    steps = official[start:] + official[:start]
    return SessionPlan(
        mode=SessionMode.FULL_ROUTINE,
        source_id="Five",
        source_version="v1",
        steps=steps,
        official_steps=official,
        start_boundary=start,
    )


@pytest.fixture
def db():
    database = Database(":memory:")
    yield database
    database.close()


def test_active_state_round_trips_after_each_run(db):
    repository = SessionRepository(db.conn)
    state = repository.create(_full_plan())
    state = SessionEngine.confirm_run(state, now=NOW)
    repository.save(state)

    assert repository.load_active() == state


def test_new_repository_recovers_running_session_as_paused(db):
    first = SessionRepository(db.conn)
    state = first.create(_full_plan())
    first.save(SessionEngine.confirm_run(state, now=NOW))

    recovered = SessionRepository(db.conn).load_active()
    assert recovered.status is SessionStatus.PAUSED
    assert recovered.confirmed_runs == 1
    assert recovered.stop_reason == "application_recovered"


def test_partial_step_recovers_at_zero_runs_for_next_session(db):
    repository = SessionRepository(db.conn)
    state = repository.create(_full_plan(start=2))
    state = SessionEngine.confirm_run(state, now=NOW)
    repository.finish(SessionEngine.stop(state, reason="user", now=NOW))

    resumed = repository.build_resumed_full_plan("Five")
    assert resumed.steps[0].scenario == "C"
    assert resumed.steps[0].required_runs == 7
    assert resumed.initial_confirmed_runs == 0


def test_completed_wrapped_cycle_resets_to_official_start(db):
    repository = SessionRepository(db.conn)
    state = repository.create(_full_plan(start=2))
    while state.status is SessionStatus.RUNNING:
        state = SessionEngine.confirm_run(state, now=NOW)
    repository.finish(state)

    resumed = repository.build_resumed_full_plan("Five")
    assert [step.scenario for step in resumed.steps] == list("ABCDE")
    assert resumed.start_boundary == 0


def test_only_one_active_session_is_allowed(db):
    repository = SessionRepository(db.conn)
    repository.create(_full_plan())
    with pytest.raises(ValueError, match="active session"):
        repository.create(_full_plan(start=1))


def test_source_guidance_round_trip_does_not_fill_missing_keys(db):
    repository = SessionRepository(db.conn)
    step = _step("Only setup", runs=1, guide={"setup": "Exact only"})
    plan = SessionPlan(
        mode=SessionMode.WARMUP,
        source_id="guide",
        source_version="v1",
        steps=(step,),
        official_steps=(step,),
    )
    repository.create(plan)

    loaded = repository.load_active()
    assert dict(loaded.current_step.guide) == {"setup": "Exact only"}
    assert "adjust" not in loaded.current_step.guide


def test_schema_migration_adds_session_tables(tmp_path):
    database = Database(str(tmp_path / "sessions.sqlite3"))
    try:
        assert database.schema_version >= 4
        assert {
            "session_plans", "session_steps", "session_state", "session_runs"
        } <= database.table_names()
    finally:
        database.close()
