"""Pure-Python implementation of the official benchmark energy rules."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING

from .definitions import BenchmarkDefinition, DefinitionSet, normalize_alias

if TYPE_CHECKING:
    from models.score import Score


@dataclass(frozen=True)
class ScenarioEnergy:
    benchmark_name: str
    scenario: str
    score: float
    energy: float


@dataclass(frozen=True)
class SubcategoryEnergy:
    name: str
    energy: float
    selected_scenario: str
    scenarios: tuple[ScenarioEnergy, ...]


@dataclass(frozen=True)
class BenchmarkResult:
    definition_version: str
    difficulty: str
    subcategories: Mapping[str, SubcategoryEnergy]
    overall_energy: float | None
    overall_tier: str | None
    missing_subcategories: tuple[str, ...]


def harmonic_mean(values: Sequence[float]) -> float:
    """Return the harmonic mean of positive energy values."""

    if not values or any(value <= 0 for value in values):
        raise ValueError("harmonic mean requires positive energies")
    return len(values) / sum(1.0 / value for value in values)


def score_to_energy(definition: BenchmarkDefinition, score: float) -> float:
    """Interpolate a score on one benchmark's piecewise-linear energy curve."""

    value = float(score)
    if not isfinite(value) or value <= 0:
        return 0.0

    first_score, first_energy = definition.targets[0]
    if value <= first_score:
        return first_energy * value / first_score

    for (lower_score, lower_energy), (upper_score, upper_energy) in zip(
        definition.targets, definition.targets[1:]
    ):
        if value <= upper_score:
            return lower_energy + (upper_energy - lower_energy) * (
                (value - lower_score) / (upper_score - lower_score)
            )

    if len(definition.targets) == 1:
        return first_energy * value / first_score

    previous_score, previous_energy = definition.targets[-2]
    last_score, last_energy = definition.targets[-1]
    return last_energy + (last_energy - previous_energy) * (
        (value - last_score) / (last_score - previous_score)
    )


class BenchmarkCalculator:
    """Calculate a definition-versioned official result from imported scores."""

    def __init__(self, definitions: DefinitionSet):
        self._definitions = definitions
        self._definitions_by_alias = self._build_alias_index(definitions)

    def calculate(self, scores: Iterable[Score], difficulty: str) -> BenchmarkResult:
        """Calculate best-per-scenario and best-per-subcategory official energy."""

        raw_scores = self._best_scores(scores, difficulty)
        capped = self._subcategory_energies(raw_scores, capped=True)
        missing = self._missing_subcategories(capped)
        if missing:
            return BenchmarkResult(
                definition_version=self._definitions.version,
                difficulty=difficulty,
                subcategories=capped,
                overall_energy=None,
                overall_tier=None,
                missing_subcategories=missing,
            )

        capped_overall = harmonic_mean([item.energy for item in capped.values()])
        if self._should_uncap(capped_overall, raw_scores):
            subcategories = self._subcategory_energies(raw_scores, capped=False)
            overall_energy = harmonic_mean([item.energy for item in subcategories.values()])
        else:
            subcategories = capped
            overall_energy = capped_overall

        return BenchmarkResult(
            definition_version=self._definitions.version,
            difficulty=difficulty,
            subcategories=subcategories,
            overall_energy=overall_energy,
            overall_tier=self._tier_for(overall_energy),
            missing_subcategories=(),
        )

    @staticmethod
    def _build_alias_index(
        definitions: DefinitionSet,
    ) -> dict[str, BenchmarkDefinition]:
        index = {}
        for definition in definitions.benchmarks:
            for alias in (definition.name, definition.scenario, *definition.aliases):
                index[normalize_alias(alias)] = definition
        return index

    def _best_scores(
        self, scores: Iterable[Score], difficulty: str
    ) -> dict[BenchmarkDefinition, float]:
        best: dict[BenchmarkDefinition, float] = {}
        for imported in scores:
            definition = self._definition_for_score(imported)
            if definition is None or definition.difficulty != difficulty:
                continue
            value = float(imported.score)
            if not isfinite(value):
                continue
            current = best.get(definition)
            if current is None or value > current:
                best[definition] = value
        return best

    def _definition_for_score(self, imported: Score) -> BenchmarkDefinition | None:
        for candidate in (imported.benchmark_name, imported.scenario):
            if isinstance(candidate, str):
                definition = self._definitions_by_alias.get(normalize_alias(candidate))
                if definition is not None:
                    return definition
        return None

    def _subcategory_energies(
        self, scores: Mapping[BenchmarkDefinition, float], *, capped: bool
    ) -> dict[str, SubcategoryEnergy]:
        subcategories: dict[str, SubcategoryEnergy] = {}
        for name in self._definitions.required_subcategories:
            scenarios = []
            for definition in self._definitions.benchmarks:
                if f"{definition.category} / {definition.subcategory}" != name:
                    continue
                score = scores.get(definition)
                if score is None:
                    continue
                raw_energy = score_to_energy(definition, score)
                energy = min(raw_energy, definition.energy_cap) if capped else raw_energy
                scenarios.append(
                    ScenarioEnergy(
                        benchmark_name=definition.name,
                        scenario=definition.scenario,
                        score=score,
                        energy=energy,
                    )
                )
            if scenarios:
                selected = max(scenarios, key=lambda item: item.energy)
                subcategories[name] = SubcategoryEnergy(
                    name=name,
                    energy=selected.energy,
                    selected_scenario=selected.scenario,
                    scenarios=tuple(scenarios),
                )
        return subcategories

    def _missing_subcategories(
        self, subcategories: Mapping[str, SubcategoryEnergy]
    ) -> tuple[str, ...]:
        return tuple(
            name
            for name in self._definitions.required_subcategories
            if name not in subcategories or subcategories[name].energy <= 0
        )

    @staticmethod
    def _should_uncap(
        capped_overall: float, scores: Mapping[BenchmarkDefinition, float]
    ) -> bool:
        thresholds = {
            definition.uncap_overall_energy
            for definition in scores
            if definition.uncap_overall_energy is not None
        }
        return bool(thresholds) and capped_overall >= min(thresholds)

    def _tier_for(self, energy: float) -> str:
        tier = self._definitions.ranks[0][0]
        for name, threshold in self._definitions.ranks:
            if energy >= threshold:
                tier = name
            else:
                break
        return tier
