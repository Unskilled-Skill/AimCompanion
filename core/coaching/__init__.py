"""Evidence-backed coaching services."""

from .freshness import BenchmarkFreshness, FreshnessState
from .evidence import RecommendationEvidence
from .recommender import (
    CoachingRecommender,
    Recommendation,
    RecommendationContext,
    RotationState,
    ScenarioCandidate,
)
from .summary import CoachingSummary, build_coaching_summary

__all__ = [
    "BenchmarkFreshness", "FreshnessState", "RecommendationEvidence",
    "CoachingRecommender", "Recommendation", "RecommendationContext",
    "RotationState", "ScenarioCandidate", "CoachingSummary",
    "build_coaching_summary",
]
