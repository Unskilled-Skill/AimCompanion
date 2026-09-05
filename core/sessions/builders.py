"""Build source-backed plans without changing authored routine content."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypeVar
from dataclasses import replace
from datetime import datetime, timezone

from core.recommender import infer_routine_target
from core.warmups import GAME_WARMUP_ROUTINES, RECOMMENDED_WARMUP_ROUTINE

from .model import SessionMode, SessionPlan, SessionStep
from .model import SessionState, SessionStatus


T = TypeVar("T")
DATA_DIR = Path(__file__).parents[2] / "data"


def rotate_once(items: Sequence[T], start: int) -> tuple[T, ...]:
    if not items:
        raise ValueError("routine must contain at least one scenario")
    index = start % len(items)
    return tuple(items[index:]) + tuple(items[:index])


def _positive_int(value: object, field: str) -> int:
    try:
        converted = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a positive integer") from error
    if converted <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return converted


def _step_from_source(
    exercise: Mapping[str, object], routine: Mapping[str, object]
) -> SessionStep:
    prescribed = exercise.get("prescribed_runs", exercise.get("duration_min"))
    required_runs = _positive_int(prescribed, "prescribed runs")
    duration_minutes = _positive_int(
        exercise.get("duration_min", required_runs), "duration_min"
    )
    category, subcategory = infer_routine_target(
        str(exercise.get("scenario", "")),
        list(routine.get("targets", ())),
        dict(exercise),
    )
    guide = exercise.get("performance_guide", {})
    if not isinstance(guide, Mapping):
        raise ValueError("performance_guide must be an object")
    return SessionStep(
        scenario=str(exercise.get("scenario", "")),
        required_runs=required_runs,
        estimated_seconds=duration_minutes * 60,
        category=category,
        subcategory=subcategory,
        guide=dict(guide),
        source=str(routine.get("source", "")),
        source_url=str(routine.get("source_url", "")),
    )


def build_full_routine_plan(
    routine: Mapping[str, object], resume_index: int
) -> SessionPlan:
    exercises = routine.get("exercises", ())
    if not isinstance(exercises, Sequence) or isinstance(exercises, (str, bytes)):
        raise ValueError("routine exercises must be a sequence")
    authored = tuple(_step_from_source(item, routine) for item in exercises)
    boundary = resume_index % len(authored) if authored else 0
    return SessionPlan(
        mode=SessionMode.FULL_ROUTINE,
        source_id=str(routine.get("name", "")),
        source_version=str(
            routine.get("version") or routine.get("source") or "unversioned"
        ),
        steps=rotate_once(authored, boundary),
        official_steps=authored,
        start_boundary=boundary,
        initial_confirmed_runs=0,
    )


def next_full_routine_resume(
    completed_boundary: int, step_count: int, completed_cycle: bool
) -> int:
    if step_count <= 0:
        raise ValueError("step_count must be positive")
    if completed_cycle:
        return 0
    return completed_boundary % step_count


def _warmup_step(item: Mapping[str, object], source_id: str) -> SessionStep:
    minutes = _positive_int(item.get("duration_min", 1), "duration_min")
    cue = str(item.get("cue", "")).strip()
    guide = {"steps": [cue]} if cue else {}
    return SessionStep(
        scenario=str(item.get("scenario", "")),
        required_runs=_positive_int(item.get("prescribed_runs", minutes), "prescribed runs"),
        estimated_seconds=minutes * 60,
        category=str(item.get("category", "General")),
        subcategory=str(item.get("subcategory", "Mixed")),
        guide=guide,
        source="Aim Companion warm-up catalog",
        source_url="",
    )


def _routine_warmup_items(target_id: str) -> list[Mapping[str, object]]:
    payload = json.loads((DATA_DIR / "tacfps_guide.json").read_text(encoding="utf-8"))
    routine = next(
        (item for item in payload.get("routines", ()) if item.get("name") == target_id),
        None,
    )
    if routine is None:
        raise ValueError(f"unknown routine warm-up target: {target_id}")
    target_categories = {
        str(target).split("_", 1)[0]
        for target in routine.get("targets", ())
        if "_" in str(target)
    }
    preferred = [
        item
        for item in RECOMMENDED_WARMUP_ROUTINE
        if item.get("category") in target_categories
    ]
    candidates = preferred + [
        item for item in RECOMMENDED_WARMUP_ROUTINE if item not in preferred
    ]
    selected: list[Mapping[str, object]] = []
    seen_skills: set[tuple[object, object]] = set()
    for item in candidates:
        skill = (item.get("category"), item.get("subcategory"))
        if skill in seen_skills:
            continue
        selected.append(item)
        seen_skills.add(skill)
        if len(selected) == 3:
            break
    return selected


def build_warmup_plan(context: str, target_id: str) -> SessionPlan:
    if context == "game":
        items = GAME_WARMUP_ROUTINES.get(target_id)
        if items is None:
            raise ValueError(f"unknown game warm-up target: {target_id}")
    elif context == "routine":
        items = _routine_warmup_items(target_id)
    else:
        raise ValueError(f"unknown warm-up context: {context}")
    steps = tuple(_warmup_step(item, target_id) for item in items)
    return SessionPlan(
        mode=SessionMode.WARMUP,
        source_id=f"{context}:{target_id}",
        source_version="warmup-v1",
        steps=steps,
        official_steps=steps,
    )


def build_benchmark_check_plan(
    definitions, due_subcategories: Sequence[str], difficulty: str,
) -> SessionPlan:
    due = set(due_subcategories)
    ordered = tuple(
        item for key in definitions.required_subcategories
        if key in due
        for item in definitions.benchmarks
        if (
            f"{item.category} / {item.subcategory}" == key
            and item.difficulty.casefold() == difficulty.casefold()
        )
    )
    if not ordered:
        raise ValueError("no official benchmark scenarios match the due areas")
    steps = tuple(
        SessionStep(
            scenario=item.scenario,
            required_runs=1,
            estimated_seconds=60,
            category=item.category,
            subcategory=item.subcategory,
            guide={
                "purpose": f"Refresh the official {item.category} / {item.subcategory} benchmark.",
                "setup": "Use your normal benchmark sensitivity and settings.",
                "steps": ["Complete one scored benchmark run with your normal technique."],
                "success": "Finish the run so Kovaak's writes a result for Aim Companion to import.",
            },
            source=f"Voltaic {definitions.version} benchmark",
            source_url=definitions.source_url,
        )
        for item in ordered
    )
    return SessionPlan(
        mode=SessionMode.STEP_BY_STEP,
        source_id=f"Aim Companion {difficulty} Benchmark Check",
        source_version=definitions.version,
        steps=steps,
        official_steps=steps,
    )


def append_step_by_step_recommendation(state: SessionState, recommendation) -> SessionState:
    if state.plan.mode is not SessionMode.STEP_BY_STEP:
        raise ValueError("recommendations can only extend step-by-step sessions")
    if state.status is SessionStatus.STOPPED:
        raise ValueError("cannot append to a stopped session")
    if state.plan.steps and state.status is not SessionStatus.COMPLETED:
        raise ValueError("previous block must be completed before appending")
    seconds = max(180, min(300, int(recommendation.estimated_seconds)))
    step = SessionStep(
        scenario=recommendation.scenario,
        required_runs=max(1, round(seconds / 60)),
        estimated_seconds=seconds,
        category=recommendation.category,
        subcategory=recommendation.subcategory,
        guide=dict(recommendation.guide),
        source=recommendation.source,
        source_url=recommendation.source_url,
    )
    steps = state.plan.steps + (step,)
    plan = SessionPlan(
        mode=SessionMode.STEP_BY_STEP,
        source_id=state.plan.source_id,
        source_version=state.plan.source_version,
        steps=steps,
        official_steps=steps,
    )
    return replace(
        state,
        plan=plan,
        status=SessionStatus.RUNNING,
        current_step_index=len(steps) - 1,
        confirmed_runs=0,
        updated_at=datetime.now(timezone.utc),
        stop_reason="",
    )
