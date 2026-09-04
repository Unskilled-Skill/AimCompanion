from datetime import datetime, timezone

from core.session_coordinator import SessionCoordinator
from core.sessions import SessionMode, SessionPlan, SessionStatus, SessionStep
from core.sessions.repository import SessionRepository
from models.database import Database
from models.score import Score


class FakeTracker:
    def __init__(self, events=None):
        self.events = events if events is not None else []

    def start(self, scenario, target_runs=3):
        self.events.append(("track", scenario, target_runs))

    def stop(self):
        self.events.append(("stop",))


def _plan(runs=2):
    step = SessionStep(
        scenario="Static A",
        required_runs=runs,
        estimated_seconds=180,
        category="Clicking",
        subcategory="Static",
        guide={"steps": ["Move directly."]},
        source="Fixture",
        source_url="https://example.test/source",
    )
    return SessionPlan(
        mode=SessionMode.FULL_ROUTINE,
        source_id="Fixture",
        source_version="v1",
        steps=(step,),
        official_steps=(step,),
    )


def _score(scenario="Static A", value=100, second=0):
    return Score(
        benchmark_name=scenario,
        scenario=scenario,
        category="Clicking",
        subcategory="Static",
        difficulty="Novice",
        score=value,
        timestamp=datetime(2026, 9, 4, 18, 0, second, tzinfo=timezone.utc),
    )


def _coordinator(database, events=None):
    return SessionCoordinator(
        SessionRepository(database.conn),
        FakeTracker(events),
        launcher=lambda scenario: (events.append(("launch", scenario)) if events is not None else None) or True,
    )


def test_detected_and_manual_runs_use_same_state_transition():
    automatic_db = Database(":memory:")
    manual_db = Database(":memory:")
    try:
        automatic = _coordinator(automatic_db)
        manual = _coordinator(manual_db)
        automatic.start(_plan())
        manual.start(_plan())

        automatic.confirm_detected_runs([_score()])
        manual.confirm_manual_run()
        assert automatic.state.confirmed_runs == manual.state.confirmed_runs == 1
    finally:
        automatic_db.close()
        manual_db.close()


def test_wrong_scenario_result_does_not_advance():
    database = Database(":memory:")
    try:
        coordinator = _coordinator(database)
        coordinator.start(_plan())
        coordinator.confirm_detected_runs([_score("Different Scenario")])
        assert coordinator.state.confirmed_runs == 0
    finally:
        database.close()


def test_same_detected_result_is_durably_counted_once():
    database = Database(":memory:")
    try:
        repository = SessionRepository(database.conn)
        first = SessionCoordinator(repository, FakeTracker(), launcher=lambda _: True)
        first.start(_plan())
        score = _score()
        first.confirm_detected_runs([score])

        resumed_repository = SessionRepository(database.conn)
        second = SessionCoordinator(resumed_repository, FakeTracker(), launcher=lambda _: True)
        second.state = resumed_repository.load_active()
        second.state = second.resume()
        second.confirm_detected_runs([score])
        assert second.state.confirmed_runs == 1
    finally:
        database.close()


def test_tracker_starts_before_deep_link_launch():
    database = Database(":memory:")
    events = []
    try:
        coordinator = _coordinator(database, events)
        coordinator.start(_plan(runs=3))
        assert coordinator.launch_current() is True
        assert events == [
            ("track", "Static A", 3),
            ("launch", "Static A"),
        ]
    finally:
        database.close()


def test_every_transition_is_saved_and_observed():
    database = Database(":memory:")
    observed = []
    try:
        repository = SessionRepository(database.conn)
        coordinator = SessionCoordinator(
            repository,
            FakeTracker(),
            launcher=lambda _: True,
            on_state_changed=observed.append,
        )
        coordinator.start(_plan(runs=1))
        coordinator.confirm_manual_run()

        assert coordinator.state.status is SessionStatus.COMPLETED
        assert observed[-1] == coordinator.state
        row = database.conn.execute(
            "SELECT status FROM session_state ORDER BY plan_id DESC LIMIT 1"
        ).fetchone()
        assert row["status"] == "completed"
    finally:
        database.close()


def test_restart_step_resets_progress_and_stops_tracker():
    database = Database(":memory:")
    events = []
    try:
        coordinator = _coordinator(database, events)
        coordinator.start(_plan())
        coordinator.confirm_manual_run()
        coordinator.restart_step()
        assert coordinator.state.confirmed_runs == 0
        assert events == [("stop",)]
    finally:
        database.close()
