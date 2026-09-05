"""UI-neutral training session domain."""

from .engine import InvalidSessionTransition, SessionEngine
from .builders import (
    build_full_routine_plan,
    build_warmup_plan,
    build_benchmark_check_plan,
    append_step_by_step_recommendation,
    next_full_routine_resume,
)
from .model import (
    SessionMode,
    SessionPlan,
    SessionState,
    SessionStatus,
    SessionStep,
)
from .repository import SessionRepository
from .repository import WarmupPreference, WarmupPreferenceRepository

__all__ = [
    "InvalidSessionTransition",
    "build_full_routine_plan",
    "build_warmup_plan",
    "build_benchmark_check_plan",
    "append_step_by_step_recommendation",
    "next_full_routine_resume",
    "SessionEngine",
    "SessionMode",
    "SessionPlan",
    "SessionRepository",
    "WarmupPreference",
    "WarmupPreferenceRepository",
    "SessionState",
    "SessionStatus",
    "SessionStep",
]
