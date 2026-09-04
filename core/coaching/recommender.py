"""Deterministic Step-by-Step recommendation selection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from models.profile import PlayerProfile

from .evidence import RecommendationEvidence
from .freshness import FreshnessState


ROTATION = (1, 2, 1, 3, 1, 2, 1, 3, 1, 2)


@dataclass(frozen=True)
class RotationState:
    cursor: int = 0
    last_scenario: str = ""
    last_subcategory: str = ""


@dataclass(frozen=True)
class ScenarioCandidate:
    scenario: str
    category: str
    subcategory: str
    estimated_seconds: int
    guide: Mapping[str, object]
    source: str = "Aim Companion scenario catalog"
    source_url: str = ""


@dataclass(frozen=True)
class Recommendation:
    kind: Literal["benchmark_check", "weakness", "trend", "coverage"]
    scenario: str
    category: str
    subcategory: str
    priority_rank: int
    estimated_seconds: int
    guide: Mapping[str, object]
    evidence: RecommendationEvidence
    source: str = "Aim Companion scenario catalog"
    source_url: str = ""


@dataclass(frozen=True)
class RecommendationContext:
    profile: PlayerProfile
    freshness: Mapping[str, FreshnessState]
    trends: Mapping[str, float]
    candidates: tuple[ScenarioCandidate, ...]
    rotation: RotationState
    fatigue_coaching_enabled: bool = False


class CoachingRecommender:
    def next(self, context: RecommendationContext) -> Recommendation:
        priorities = self._priorities(context.profile)
        due = sorted(
            (state for state in context.freshness.values() if state.due),
            key=lambda state: (
                state.confidence != "missing",
                -state.blocks_since_check,
                state.subcategory,
            ),
        )
        if due:
            state = due[0]
            category, subcategory = self._split_skill(state.subcategory)
            candidate = self._select_candidate(
                context.candidates,
                category,
                subcategory,
                context.rotation,
            )
            priority_rank = priorities.index((category, subcategory)) + 1 if (
                category, subcategory
            ) in priorities else 1
            return self._recommendation(
                "benchmark_check",
                candidate,
                priority_rank,
                RecommendationEvidence(
                    rule="benchmark_due",
                    summary=(
                        f"{state.subcategory} is "
                        f"{'missing' if not state.measured else 'due after ' + str(state.blocks_since_check) + ' blocks'}."
                    ),
                    definition_version=context.profile.definition_version,
                    confidence="low" if not state.measured else "medium",
                    blocks_since_benchmark=state.blocks_since_check,
                ),
            )

        assigned = ROTATION[context.rotation.cursor % len(ROTATION)]
        rank_order = (assigned,) + tuple(rank for rank in (1, 2, 3) if rank != assigned)
        for rank in rank_order:
            if rank > len(priorities):
                continue
            category, subcategory = priorities[rank - 1]
            if (
                context.rotation.last_subcategory == f"{category} / {subcategory}"
                and len(priorities) > 1
            ):
                continue
            try:
                candidate = self._select_candidate(
                    context.candidates,
                    category,
                    subcategory,
                    context.rotation,
                )
            except LookupError:
                continue
            trend = context.trends.get(f"{category} / {subcategory}")
            trend_text = f"; recent trend {trend:+.1f}%" if trend is not None else ""
            freshness = context.freshness.get(f"{category} / {subcategory}")
            confidence = "high" if freshness and freshness.confidence == "current" else "medium"
            return self._recommendation(
                "weakness",
                candidate,
                rank,
                RecommendationEvidence(
                    rule="weakness_rotation",
                    summary=f"Priority {rank} weakness: {category} / {subcategory}{trend_text}.",
                    definition_version=context.profile.definition_version,
                    confidence=confidence,
                    trend_window=6 if trend is not None else 0,
                    blocks_since_benchmark=(
                        freshness.blocks_since_check if freshness else None
                    ),
                ),
            )
        raise LookupError("no suitable recommendation candidate")

    @staticmethod
    def accept(state: RotationState, recommendation: Recommendation) -> RotationState:
        cursor = state.cursor + (recommendation.kind != "benchmark_check")
        return RotationState(
            cursor=cursor,
            last_scenario=recommendation.scenario,
            last_subcategory=f"{recommendation.category} / {recommendation.subcategory}",
        )

    @staticmethod
    def _priorities(profile: PlayerProfile) -> list[tuple[str, str]]:
        skills = [
            (subcategory.energy, category.name, subcategory.name)
            for category in profile.categories
            for subcategory in category.subcategories
        ]
        skills.sort(key=lambda item: (item[0], item[1], item[2]))
        return [(category, subcategory) for _, category, subcategory in skills[:3]]

    @staticmethod
    def _split_skill(value: str) -> tuple[str, str]:
        if " / " not in value:
            raise ValueError(f"invalid subcategory key: {value}")
        return tuple(value.split(" / ", 1))

    @staticmethod
    def _select_candidate(candidates, category, subcategory, rotation):
        matching = sorted(
            (
                candidate for candidate in candidates
                if candidate.category == category and candidate.subcategory == subcategory
            ),
            key=lambda candidate: candidate.scenario.casefold(),
        )
        if not matching:
            raise LookupError(f"no candidate for {category} / {subcategory}")
        alternatives = [
            candidate for candidate in matching
            if candidate.scenario.casefold() != rotation.last_scenario.casefold()
        ]
        return (alternatives or matching)[0]

    @staticmethod
    def _recommendation(kind, candidate, priority_rank, evidence):
        return Recommendation(
            kind=kind,
            scenario=candidate.scenario,
            category=candidate.category,
            subcategory=candidate.subcategory,
            priority_rank=priority_rank,
            estimated_seconds=max(180, min(300, candidate.estimated_seconds)),
            guide=candidate.guide,
            evidence=evidence,
            source=candidate.source,
            source_url=candidate.source_url,
        )
