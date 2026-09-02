"""Deprecated widget helpers backed by the active official definitions."""

from __future__ import annotations

from functools import lru_cache

from core.benchmarks import DefinitionRepository
from core.benchmarks.calculator import score_to_energy as official_score_to_energy
from core.benchmarks.definitions import BenchmarkDefinition, DefinitionSet, normalize_alias


@lru_cache(maxsize=1)
def _active_definitions() -> DefinitionSet:
    return DefinitionRepository.bundled().load_active()


def _definition_for(name: str | None) -> BenchmarkDefinition | None:
    if not isinstance(name, str):
        return None
    normalized = normalize_alias(name)
    for definition in _active_definitions().benchmarks:
        if normalized in {
            normalize_alias(alias)
            for alias in (definition.name, definition.scenario, *definition.aliases)
        }:
            return definition
    return None


def _compatibility_benchmark(definition: BenchmarkDefinition) -> dict:
    ranks = dict(_active_definitions().ranks)
    return {
        "name": definition.name,
        "scenario": definition.scenario,
        "category": definition.category,
        "subcategory": definition.subcategory,
        "difficulty": definition.difficulty,
        "targets": {
            tier: score
            for score, energy in definition.targets
            if (tier := next(
                (name for name, threshold in ranks.items() if threshold == energy), None
            )) is not None
        },
    }


_TIER_COLORS = {
    "Iron": "#808080",
    "Bronze": "#CD7F32",
    "Silver": "#C0C0C0",
    "Gold": "#FFD700",
    "Platinum": "#00CED1",
    "Diamond": "#B9F2FF",
    "Jade": "#00A86B",
    "Master": "#FF4500",
    "Grandmaster": "#9966CC",
    "Nova": "#FF69B4",
    "Astra": "#FFD700",
    "Celestial": "#E6E6FA",
    "Radiant": "#FFFFFF",
}


def _compatibility_tier(name: str, min_energy: float) -> dict:
    return {
        "name": name,
        "min_energy": min_energy,
        "color": _TIER_COLORS.get(name, "#FFFFFF"),
    }


BENCHMARKS = [
    _compatibility_benchmark(definition)
    for definition in _active_definitions().benchmarks
]
TIERS = [
    _compatibility_tier(name, min_energy)
    for name, min_energy in _active_definitions().ranks
]
TIER_ENERGY_MAP = {tier["name"]: tier["min_energy"] for tier in TIERS}


def get_benchmark(scenario_name: str) -> dict | None:
    definition = _definition_for(scenario_name)
    return _compatibility_benchmark(definition) if definition is not None else None


def get_benchmarks_by_difficulty(difficulty: str) -> list[dict]:
    return [
        _compatibility_benchmark(definition)
        for definition in _active_definitions().benchmarks
        if definition.difficulty == difficulty
    ]


def get_subcategories() -> list[str]:
    return sorted({definition.subcategory for definition in _active_definitions().benchmarks})


def get_categories() -> list[str]:
    return sorted({definition.category for definition in _active_definitions().benchmarks})


def get_benchmarks_by_subcategory(category: str, subcategory: str) -> list[dict]:
    return [
        _compatibility_benchmark(definition)
        for definition in _active_definitions().benchmarks
        if definition.category == category and definition.subcategory == subcategory
    ]


def score_to_energy(benchmark_name_or_score, score: float | None = None) -> float:
    """Compatibility wrapper around the reviewed official score curve."""

    if isinstance(benchmark_name_or_score, (int, float)):
        return 0.0
    definition = _definition_for(benchmark_name_or_score)
    if definition is None or score is None:
        return 0.0
    return official_score_to_energy(definition, score)


def energy_to_score(benchmark_name: str | None, energy: float) -> float:
    """Invert the official curve by repeatedly calling its reviewed evaluator."""

    definition = _definition_for(benchmark_name)
    if definition is None or energy <= 0:
        return 0.0

    lower = 0.0
    upper = definition.targets[-1][0]
    while official_score_to_energy(definition, upper) < energy:
        upper *= 2
    for _ in range(64):
        midpoint = (lower + upper) / 2
        if official_score_to_energy(definition, midpoint) < energy:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2


def energy_to_tier(energy: float | None) -> str:
    value = energy or 0.0
    tier = "Unranked"
    for item in TIERS:
        if value >= item["min_energy"]:
            tier = item["name"]
        else:
            break
    return tier


def get_tier_info(tier_name: str) -> dict:
    return next((tier for tier in TIERS if tier["name"] == tier_name), TIERS[0])
