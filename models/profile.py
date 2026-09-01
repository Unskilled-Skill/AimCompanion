"""Widget-compatible profile views backed by official benchmark results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Iterable, Mapping

from core.benchmarks import DefinitionRepository
from core.benchmarks.calculator import harmonic_mean
from core.benchmarks.definitions import BenchmarkDefinition, DefinitionSet

from models.score import BenchmarkInfo, CategoryScore, SubcategoryScore

if TYPE_CHECKING:
    from core.benchmarks.calculator import BenchmarkResult, ScenarioEnergy
    from models.score import Score


def _tier_for(energy: float, ranks: tuple[tuple[str, float], ...]) -> str:
    tier = ranks[0][0]
    for name, threshold in ranks:
        if energy >= threshold:
            tier = name
        else:
            break
    return tier


def _scenario_by_benchmark(result: BenchmarkResult) -> dict[str, ScenarioEnergy]:
    return {
        scenario.benchmark_name: scenario
        for subcategory in result.subcategories.values()
        for scenario in subcategory.scenarios
    }


def _benchmark_info(
    definition: BenchmarkDefinition,
    scenario: ScenarioEnergy | None,
    history: Iterable[Score],
    ranks: tuple[tuple[str, float], ...],
) -> BenchmarkInfo:
    attempts = tuple(history)
    latest = max(attempts, key=lambda item: item.timestamp, default=None)
    best_score = max(
        (item.score for item in attempts),
        default=scenario.score if scenario is not None else 0.0,
    )
    energy = scenario.energy if scenario is not None else 0.0
    return BenchmarkInfo(
        name=definition.name,
        scenario=definition.scenario,
        category=definition.category,
        subcategory=definition.subcategory,
        difficulty=definition.difficulty,
        latest_score=(
            latest.score
            if latest is not None
            else scenario.score if scenario is not None else 0.0
        ),
        best_score=best_score,
        attempts=len(attempts) if attempts else int(scenario is not None),
        energy=energy,
        tier=_tier_for(energy, ranks),
    )


def profile_from_benchmark_result(
    result: BenchmarkResult,
    definitions: DefinitionSet | None = None,
    histories: Mapping[str, Iterable[Score]] | None = None,
) -> PlayerProfile:
    """Adapt one official result to the profile shape consumed by widgets.

    Category energy is a harmonic display aggregate of its measured official
    subcategories.  It is never used to determine the official overall rank.
    """

    definitions = definitions or DefinitionRepository.bundled().load_active()
    if definitions.version != result.definition_version:
        raise ValueError("profile definitions must match benchmark result version")

    histories = histories or {}
    scenarios = _scenario_by_benchmark(result)
    subcategory_values = result.subcategories
    categories: dict[str, CategoryScore] = {}
    subcategories: dict[str, SubcategoryScore] = {}

    for name in definitions.required_subcategories:
        category_name, subcategory_name = name.split(" / ", 1)
        category = categories.setdefault(category_name, CategoryScore(name=category_name))
        value = subcategory_values.get(name)
        energy = value.energy if value is not None else 0.0
        subcategory = SubcategoryScore(
            name=subcategory_name,
            category=category_name,
            energy=energy,
            tier=_tier_for(energy, definitions.ranks),
        )
        category.subcategories.append(subcategory)
        subcategories[name] = subcategory

    for definition in definitions.benchmarks:
        if definition.difficulty != result.difficulty:
            continue
        name = f"{definition.category} / {definition.subcategory}"
        benchmark = _benchmark_info(
            definition,
            scenarios.get(definition.name),
            histories.get(definition.name, ()),
            definitions.ranks,
        )
        subcategories[name].benchmarks.append(benchmark)

    for category in categories.values():
        for subcategory in category.subcategories:
            subcategory.combined_score = sum(
                benchmark.best_score for benchmark in subcategory.benchmarks
            )
        measured = [
            subcategory.energy
            for subcategory in category.subcategories
            if subcategory.energy > 0
        ]
        category.energy = harmonic_mean(measured) if measured else 0.0
        category.tier = _tier_for(category.energy, definitions.ranks)
        category.calculation_method = "local_compatibility"
        category.combined_score = sum(
            subcategory.combined_score for subcategory in category.subcategories
        )

    return PlayerProfile(
        difficulty=result.difficulty,
        categories=list(categories.values()),
        overall_score=sum(category.combined_score for category in categories.values()),
        overall_energy=result.overall_energy,
        overall_tier=result.overall_tier or "Unranked",
        definition_version=result.definition_version,
        calculation_method="voltaic_official",
    )


@dataclass
class PlayerProfile:
    username: str = ""
    difficulty: str = "Novice"
    categories: list[CategoryScore] = field(default_factory=list)
    overall_score: float = 0.0
    overall_energy: float | None = None
    overall_tier: str = "Unranked"
    last_updated: datetime | None = None
    definition_version: str = ""
    calculation_method: str = "legacy_manual"

    @classmethod
    def from_result(cls, result: BenchmarkResult) -> PlayerProfile:
        return profile_from_benchmark_result(result)

    def recalculate(self):
        """Compatibility path for manually constructed, non-official profiles."""

        if self.calculation_method == "voltaic_official":
            raise RuntimeError("cannot recalculate an official profile with legacy arithmetic")

        for category in self.categories:
            category.recalculate()
        if self.categories:
            self.overall_energy = sum(category.energy for category in self.categories) / len(
                self.categories
            )
        else:
            self.overall_energy = 0.0
        self.overall_score = sum(category.combined_score for category in self.categories)
        from models.benchmark import energy_to_tier

        self.overall_tier = energy_to_tier(self.overall_energy)

    def get_weakest_subcategories(
        self, n: int = 5, measured_only: bool = True
    ) -> list[SubcategoryScore]:
        all_subcategories = [
            subcategory
            for category in self.categories
            for subcategory in category.subcategories
            if not measured_only or subcategory.energy > 0
        ]
        all_subcategories.sort(key=lambda subcategory: subcategory.energy)
        return all_subcategories[:n]

    def get_strongest_subcategories(self, n: int = 3) -> list[SubcategoryScore]:
        all_subcategories = [
            subcategory
            for category in self.categories
            for subcategory in category.subcategories
        ]
        all_subcategories.sort(key=lambda subcategory: subcategory.energy, reverse=True)
        return all_subcategories[:n]
