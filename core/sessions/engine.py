"""Legal state transitions for durable guided sessions."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .model import SessionPlan, SessionState, SessionStatus


class InvalidSessionTransition(ValueError):
    """Raised when an action is not valid for the current session status."""


def _now(value: datetime | None) -> datetime:
    return value or datetime.now(timezone.utc)


class SessionEngine:
    @staticmethod
    def start(plan: SessionPlan, *, now: datetime | None = None) -> SessionState:
        if not plan.steps:
            raise ValueError("cannot start a plan with no steps")
        timestamp = _now(now)
        return SessionState(
            plan=plan,
            status=SessionStatus.RUNNING,
            current_step_index=0,
            confirmed_runs=plan.initial_confirmed_runs,
            started_at=timestamp,
            updated_at=timestamp,
        )

    @staticmethod
    def confirm_run(
        state: SessionState, *, now: datetime | None = None
    ) -> SessionState:
        SessionEngine._require(state, SessionStatus.RUNNING, "confirm a run")
        completed_runs = state.confirmed_runs + 1
        if completed_runs < state.current_step.required_runs:
            return replace(state, confirmed_runs=completed_runs, updated_at=_now(now))
        if state.current_step_index + 1 < len(state.plan.steps):
            return replace(
                state,
                current_step_index=state.current_step_index + 1,
                confirmed_runs=0,
                updated_at=_now(now),
            )
        return replace(
            state,
            status=SessionStatus.COMPLETED,
            confirmed_runs=state.current_step.required_runs,
            updated_at=_now(now),
        )

    @staticmethod
    def pause(state: SessionState, *, now: datetime | None = None) -> SessionState:
        SessionEngine._require(state, SessionStatus.RUNNING, "pause")
        return replace(state, status=SessionStatus.PAUSED, updated_at=_now(now))

    @staticmethod
    def resume(state: SessionState, *, now: datetime | None = None) -> SessionState:
        SessionEngine._require(state, SessionStatus.PAUSED, "resume")
        return replace(
            state,
            status=SessionStatus.RUNNING,
            stop_reason="",
            updated_at=_now(now),
        )

    @staticmethod
    def stop(
        state: SessionState, *, reason: str, now: datetime | None = None
    ) -> SessionState:
        if state.status not in {
            SessionStatus.READY,
            SessionStatus.RUNNING,
            SessionStatus.PAUSED,
        }:
            raise InvalidSessionTransition(
                f"cannot stop a {state.status.value} session"
            )
        if not reason.strip():
            raise ValueError("stop reason is required")
        return replace(
            state,
            status=SessionStatus.STOPPED,
            stop_reason=reason.strip(),
            updated_at=_now(now),
        )

    @staticmethod
    def restart_step(
        state: SessionState, *, now: datetime | None = None
    ) -> SessionState:
        if state.status not in {SessionStatus.RUNNING, SessionStatus.PAUSED}:
            raise InvalidSessionTransition(
                f"cannot restart a {state.status.value} session step"
            )
        return replace(state, confirmed_runs=0, updated_at=_now(now))

    @staticmethod
    def _require(
        state: SessionState, expected: SessionStatus, action: str
    ) -> None:
        if state.status is not expected:
            raise InvalidSessionTransition(
                f"cannot {action} while session is {state.status.value}"
            )
