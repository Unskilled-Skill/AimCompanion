"""Application service joining session state, run detection, and launching."""

from __future__ import annotations

import hashlib

from core.kovaaks_launcher import canonical_scenario_name, open_kovaaks_scenario
from core.run_tracker import KovaaksRunTracker
from core.sessions import SessionEngine, SessionPlan, SessionState, SessionStatus
from core.sessions.repository import SessionRepository


def _scenario_key(value: str) -> str:
    return "".join(
        character
        for character in canonical_scenario_name(value).casefold()
        if character.isalnum()
    )


def _result_identity(score) -> str:
    payload = "\x1f".join((
        _scenario_key(score.scenario),
        score.timestamp.isoformat(),
        format(float(score.score), ".17g"),
    ))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class SessionCoordinator:
    def __init__(
        self,
        repository: SessionRepository,
        tracker: KovaaksRunTracker,
        launcher=open_kovaaks_scenario,
        on_state_changed=None,
        automatic_next: bool = False,
    ):
        self.repository = repository
        self.tracker = tracker
        self.launcher = launcher
        self.on_state_changed = on_state_changed or (lambda state: None)
        self.automatic_next = automatic_next
        self.state: SessionState | None = None

    def start(self, plan: SessionPlan) -> SessionState:
        self.state = self.repository.create(plan)
        self.on_state_changed(self.state)
        return self.state

    def launch_current(self) -> bool:
        state = self._require_state()
        if state.status is not SessionStatus.RUNNING:
            raise ValueError(f"cannot launch a {state.status.value} session")
        remaining = state.current_step.required_runs - state.confirmed_runs
        self.tracker.start(state.current_step.scenario, target_runs=remaining)
        return bool(self.launcher(state.current_step.scenario))

    def confirm_detected_runs(self, scores) -> SessionState:
        state = self._require_state()
        for score in scores:
            if state.status is not SessionStatus.RUNNING:
                break
            if _scenario_key(score.scenario) != _scenario_key(state.current_step.scenario):
                continue
            identity = _result_identity(score)
            if self.repository.result_identity_exists(identity):
                continue
            previous_index = state.current_step_index
            state = self._apply(lambda current: SessionEngine.confirm_run(current))
            self.repository.attach_result_identity(state, identity)
            if (
                self.automatic_next
                and state.status is SessionStatus.RUNNING
                and state.current_step_index != previous_index
            ):
                self.launch_current()
        return state

    def confirm_manual_run(self) -> SessionState:
        return self._apply(lambda state: SessionEngine.confirm_run(state))

    def pause(self) -> SessionState:
        self.tracker.stop()
        return self._apply(lambda state: SessionEngine.pause(state))

    def resume(self) -> SessionState:
        return self._apply(lambda state: SessionEngine.resume(state))

    def stop(self, reason: str = "user") -> SessionState:
        self.tracker.stop()
        return self._apply(lambda state: SessionEngine.stop(state, reason=reason))

    def _apply(self, transition) -> SessionState:
        current = self._require_state()
        self.state = transition(current)
        self.repository.save(self.state)
        self.on_state_changed(self.state)
        return self.state

    def _require_state(self) -> SessionState:
        if self.state is None:
            raise RuntimeError("no session has been started")
        return self.state
