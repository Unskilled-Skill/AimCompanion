"""Immutable presentation records for the redesigned interface."""

from __future__ import annotations

from dataclasses import dataclass

from core.coaching.evidence import RecommendationEvidence
from core.sessions import SessionState, SessionStatus


@dataclass(frozen=True)
class ScenarioGuideViewModel:
    scenario: str
    purpose: str
    setup: str
    steps: tuple[str, ...]
    success: str
    adjustment: str | None
    required_runs: int
    completed_runs: int
    source: str
    source_url: str


@dataclass(frozen=True)
class SessionStepViewModel:
    scenario: str
    completed: bool
    run_text: str


@dataclass(frozen=True)
class SessionViewModel:
    mode: str
    title: str
    status: str
    progress_text: str
    current_guide: ScenarioGuideViewModel
    steps: tuple[SessionStepViewModel, ...]
    can_launch: bool
    can_advance: bool
    evidence: RecommendationEvidence | None


@dataclass(frozen=True)
class HomeViewModel:
    rank_text: str
    next_rank_text: str
    headline: str
    evidence_text: str
    confidence_text: str
    recent_progress: tuple[str, ...]
    weakness_text: str = ""
    trend_text: str = ""


@dataclass(frozen=True)
class ProgressViewModel:
    conclusion: str
    missing_subcategories: tuple[str, ...]
    definition_version: str


def build_home_view(summary, recent_progress=()) -> HomeViewModel:
    return HomeViewModel(
        rank_text=summary.rank_text,
        next_rank_text=summary.next_rank_text,
        headline=summary.headline,
        evidence_text=summary.evidence.summary,
        confidence_text=f"{summary.evidence.confidence.title()} confidence",
        recent_progress=tuple(recent_progress),
        weakness_text=summary.weakness_text,
        trend_text=summary.trend_text,
    )


def build_session_view(
    state: SessionState,
    evidence: RecommendationEvidence | None,
) -> SessionViewModel:
    step = state.current_step
    guide = step.guide
    steps = tuple(
        SessionStepViewModel(
            scenario=item.scenario,
            completed=(
                index < state.current_step_index
                or (
                    state.status is SessionStatus.COMPLETED
                    and index == state.current_step_index
                )
            ),
            run_text=(
                f"{state.confirmed_runs} / {item.required_runs} runs"
                if index == state.current_step_index
                else f"{item.required_runs} runs"
            ),
        )
        for index, item in enumerate(state.plan.steps)
    )
    adjustment = guide.get("adjust", guide.get("adjustment"))
    return SessionViewModel(
        mode=state.plan.mode.value,
        title=state.plan.source_id,
        status=state.status.value,
        progress_text=f"{state.confirmed_runs} / {step.required_runs} runs",
        current_guide=ScenarioGuideViewModel(
            scenario=step.scenario,
            purpose=str(
                guide.get("purpose")
                or f"Train {step.category} / {step.subcategory}."
            ),
            setup=str(guide.get("setup", "")),
            steps=tuple(str(item) for item in guide.get("steps", ())),
            success=str(guide.get("success", "")),
            adjustment=str(adjustment) if adjustment not in (None, "") else None,
            required_runs=step.required_runs,
            completed_runs=state.confirmed_runs,
            source=step.source,
            source_url=step.source_url,
        ),
        steps=steps,
        can_launch=state.status is SessionStatus.RUNNING,
        can_advance=state.status is SessionStatus.COMPLETED,
        evidence=evidence,
    )
