"""Conclusion-first coaching summary for the Home screen."""

from __future__ import annotations

from dataclasses import dataclass

from core.benchmarks import DefinitionRepository
from models.profile import PlayerProfile

from .evidence import RecommendationEvidence
from .freshness import FreshnessState


@dataclass(frozen=True)
class CoachingSummary:
    headline: str
    rank_text: str
    next_rank_text: str
    weakness_text: str
    trend_text: str
    evidence: RecommendationEvidence


def build_coaching_summary(
    profile: PlayerProfile,
    trends: dict[str, float],
    freshness: dict[str, FreshnessState],
) -> CoachingSummary:
    skills = sorted(
        (
            (subcategory.energy, f"{category.name} / {subcategory.name}")
            for category in profile.categories
            for subcategory in category.subcategories
        ),
        key=lambda item: (item[0], item[1]),
    )
    weakness = skills[0][1] if skills else "Not enough benchmark data"
    trend = trends.get(weakness)
    due = [state for state in freshness.values() if state.due]
    confidence = "low" if any(not item.measured for item in due) else "medium" if due else "high"
    if due:
        remaining = len(due) - 1
        suffix = f" + {remaining} more" if remaining else ""
        headline = f"Benchmark check: {due[0].subcategory}{suffix}"
    else:
        headline = f"Train {weakness} next"
    overall = profile.overall_energy
    definitions = DefinitionRepository.bundled().load_active()
    next_rank = next(
        ((name, threshold) for name, threshold in definitions.ranks if overall is None or threshold > overall),
        None,
    )
    return CoachingSummary(
        headline=headline,
        rank_text=(
            f"{profile.overall_tier} · {overall:.1f} energy"
            if overall is not None else "Unranked · complete all nine subcategories"
        ),
        next_rank_text=(
            f"Next: {next_rank[0]} at {next_rank[1]:.0f} energy"
            if next_rank else "Highest listed rank reached"
        ),
        weakness_text=weakness,
        trend_text=f"{trend:+.1f}% recent trend" if trend is not None else "No recent trend yet",
        evidence=RecommendationEvidence(
            rule="home_summary",
            summary=(
                "Confidence is reduced until due benchmark coverage is refreshed."
                if due else "Based on the lowest measured subcategory and recent local trend."
            ),
            definition_version=profile.definition_version,
            confidence=confidence,
            trend_window=6 if trend is not None else 0,
            blocks_since_benchmark=max(
                (state.blocks_since_check for state in due), default=None
            ),
        ),
    )
