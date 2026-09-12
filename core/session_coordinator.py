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
        self.detection_enabled = True
        self.state: SessionState | None = None
        self._tracking_scenario_key = ""

    def start(self, plan: SessionPlan) -> SessionState:
        self.state = self.repository.create(plan)
        self._tracking_scenario_key = ""
        self._arm_current_tracker()
        self.on_state_changed(self.state)
        return self.state

    def launch_current(self) -> bool:
        state = self._require_state()
        if state.status is not SessionStatus.RUNNING:
            raise ValueError(f"cannot launch a {state.status.value} session")
        # Ensure tracker is ready for the current step
        self._arm_current_tracker()
        # Try launching the specific scenario; if that fails (e.g., missing locally), fall back to opening Kovaak's game.
        launched = bool(self.launcher(state.current_step.scenario))
        if not launched:
            try:
                from core.kovaaks_launcher import open_kovaaks
                launched = bool(open_kovaaks())
            except Exception as e:
                print(f"Failed to launch Kovaak's: {e}")
        return launched

    def confirm_detected_runs(self, scores) -> SessionState:
        state = self._require_state()
        if not self.detection_enabled:
            return state
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
            self._after_run_transition(previous_index)
        return state

    def confirm_manual_run(self) -> SessionState:
        previous_index = self._require_state().current_step_index
        state = self._apply(lambda s: SessionEngine.confirm_run(s))
        self._after_run_transition(previous_index)
        return state

    def _after_run_transition(self, previous_index: int) -> None:
        state = self._require_state()
        if state.status is not SessionStatus.RUNNING:
            self._stop_tracker()
        elif state.current_step_index != previous_index:
            self._tracking_scenario_key = ""
            self._arm_current_tracker()
            if self.automatic_next:
                self.launch_current()

    def set_detection_enabled(self, enabled: bool) -> None:
        self.detection_enabled = bool(enabled)
        if not enabled:
            self._stop_tracker()
        elif self.state is not None:
            self._arm_current_tracker()

    def skip_step(self) -> SessionState:
        previous_index = self._require_state().current_step_index
        state = self._apply(SessionEngine.skip_step)
        self._after_run_transition(previous_index)
        return state

    def pause(self) -> SessionState:
        self._stop_tracker()
        return self._apply(lambda state: SessionEngine.pause(state))

    def resume(self) -> SessionState:
        state = self._apply(lambda state: SessionEngine.resume(state))
        self._arm_current_tracker()
        return state

    def restart_step(self) -> SessionState:
        self._stop_tracker()
        state = self._apply(lambda state: SessionEngine.restart_step(state))
        if state.status is SessionStatus.RUNNING:
            self._arm_current_tracker()
        return state

    def stop(self, reason: str = "user") -> SessionState:
        self._stop_tracker()
        return self._apply(lambda state: SessionEngine.stop(state, reason=reason))

    def _arm_current_tracker(self) -> None:
        state = self._require_state()
        if not self.detection_enabled or state.status is not SessionStatus.RUNNING:
            return
        scenario_key = _scenario_key(state.current_step.scenario)
        if self._tracking_scenario_key == scenario_key:
            return
        remaining = state.current_step.required_runs - state.confirmed_runs
        self.tracker.start(state.current_step.scenario, target_runs=remaining)
        self._tracking_scenario_key = scenario_key

    def _stop_tracker(self) -> None:
        self.tracker.stop()
        self._tracking_scenario_key = ""

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
