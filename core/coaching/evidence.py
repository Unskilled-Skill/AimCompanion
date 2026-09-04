"""Structured evidence attached to coaching conclusions."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class RecommendationEvidence:
    rule: str
    summary: str
    definition_version: str
    confidence: Literal["low", "medium", "high"]
    score_ids: tuple[int, ...] = ()
    trend_window: int = 0
    blocks_since_benchmark: int | None = None
