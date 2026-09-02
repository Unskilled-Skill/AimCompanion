"""Immutable value objects used by the benchmark definition boundary."""

from dataclasses import dataclass
from datetime import datetime
import re


def normalize_alias(value: str) -> str:
    """Normalize an alias for punctuation- and whitespace-insensitive lookup."""

    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


@dataclass(frozen=True)
class BenchmarkDefinition:
    name: str
    scenario: str
    aliases: tuple[str, ...]
    category: str
    subcategory: str
    difficulty: str
    targets: tuple[tuple[float, float], ...]
    energy_cap: float | None
    uncap_overall_energy: float | None


@dataclass(frozen=True)
class DefinitionSet:
    version: str
    source_url: str
    retrieved_at: datetime
    sha256: str
    active: bool
    required_subcategories: tuple[str, ...]
    ranks: tuple[tuple[str, float], ...]
    benchmarks: tuple[BenchmarkDefinition, ...]
