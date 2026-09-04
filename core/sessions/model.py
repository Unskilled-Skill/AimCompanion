"""Immutable records shared by all guided training modes."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_freeze(item) for item in value)
    return value


class SessionMode(StrEnum):
    WARMUP = "warmup"
    STEP_BY_STEP = "step_by_step"
    FULL_ROUTINE = "full_routine"


class SessionStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"


@dataclass(frozen=True)
class SessionStep:
    scenario: str
    required_runs: int
    estimated_seconds: int
    category: str
    subcategory: str
    guide: Mapping[str, object]
    source: str
    source_url: str

    def __post_init__(self) -> None:
        if not self.scenario.strip():
            raise ValueError("scenario is required")
        if self.required_runs <= 0:
            raise ValueError("required_runs must be positive")
        if self.estimated_seconds <= 0:
            raise ValueError("estimated_seconds must be positive")
        object.__setattr__(self, "guide", _freeze(self.guide))


@dataclass(frozen=True)
class SessionPlan:
    mode: SessionMode
    source_id: str
    source_version: str
    steps: tuple[SessionStep, ...]
    official_steps: tuple[SessionStep, ...]
    start_boundary: int = 0
    initial_confirmed_runs: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "official_steps", tuple(self.official_steps))
        if not self.source_id.strip():
            raise ValueError("source_id is required")
        if not self.source_version.strip():
            raise ValueError("source_version is required")
        if not self.steps:
            if self.mode is not SessionMode.STEP_BY_STEP:
                raise ValueError("session plan requires at least one step")
            if self.start_boundary != 0 or self.initial_confirmed_runs != 0:
                raise ValueError("empty step-by-step draft must start at zero")
            return
        if not self.official_steps:
            raise ValueError("official_steps requires at least one step")
        if not 0 <= self.start_boundary < len(self.official_steps):
            raise ValueError("start_boundary is outside official_steps")
        if not 0 <= self.initial_confirmed_runs < self.steps[0].required_runs:
            raise ValueError("initial_confirmed_runs is outside the first step")


@dataclass(frozen=True)
class SessionState:
    plan: SessionPlan
    status: SessionStatus
    current_step_index: int
    confirmed_runs: int
    started_at: datetime
    updated_at: datetime
    stop_reason: str = ""

    def __post_init__(self) -> None:
        if not self.plan.steps:
            if self.current_step_index != 0 or self.confirmed_runs != 0:
                raise ValueError("empty plan state must remain at zero")
            return
        if not 0 <= self.current_step_index < len(self.plan.steps):
            raise ValueError("current_step_index is outside the plan")
        required = self.plan.steps[self.current_step_index].required_runs
        upper = required if self.status is SessionStatus.COMPLETED else required - 1
        if not 0 <= self.confirmed_runs <= upper:
            raise ValueError("confirmed_runs is outside the current step")

    @property
    def current_step(self) -> SessionStep:
        if not self.plan.steps:
            raise LookupError("session plan has no steps")
        return self.plan.steps[self.current_step_index]
