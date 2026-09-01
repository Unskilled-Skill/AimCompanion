from datetime import datetime

import pytest

from core.benchmarks import DefinitionRepository
from core.benchmarks.calculator import (
    BenchmarkCalculator,
    harmonic_mean,
    score_to_energy,
)
from models.score import Score


@pytest.fixture
def s5():
    return DefinitionRepository.bundled().load_active()


@pytest.fixture
def advanced_s5(s5):
    return s5


def score(name: str, value: float, difficulty: str = "Novice") -> Score:
    return Score(
        benchmark_name=name,
        scenario=name,
        category="",
        subcategory="",
        difficulty=difficulty,
        score=value,
        timestamp=datetime(2026, 8, 30),
    )


def scores_at_first_target(definitions, difficulty: str) -> list[Score]:
    selected = {}
    for definition in definitions.benchmarks:
        if definition.difficulty == difficulty:
            selected.setdefault(f"{definition.category} / {definition.subcategory}", definition)
    return [
        score(definition.name, definition.targets[0][0], difficulty)
        for definition in selected.values()
    ]


@pytest.fixture
def one_score_per_subcategory(s5):
    return scores_at_first_target(s5, "Novice")


@pytest.fixture
def scores_for_all_nine(one_score_per_subcategory):
    return list(one_score_per_subcategory)


@pytest.fixture
def advanced_scores(advanced_s5):
    return scores_at_first_target(advanced_s5, "Advanced")


def raise_all_subcategories(scores: list[Score]) -> list[Score]:
    definitions = DefinitionRepository.bundled().load_active()
    by_name = {definition.name: definition for definition in definitions.benchmarks}
    raised = []
    for imported in scores:
        definition = by_name[imported.benchmark_name]
        previous, last = definition.targets[-2:]
        raised.append(
            score(
                imported.benchmark_name,
                last[0] + (last[0] - previous[0]),
                imported.difficulty,
            )
        )
    return raised


def test_subcategory_uses_highest_scenario_energy(s5, scores_for_all_nine):
    scores_for_all_nine += [
        score("VT PGT Novice S5", 3050),
        score("VT Snake Track Novice S5", 1),
    ]

    result = BenchmarkCalculator(s5).calculate(scores_for_all_nine, "Novice")

    precise = result.subcategories["Tracking / Precise"]
    assert precise.energy == max(item.energy for item in precise.scenarios)


def test_overall_is_harmonic_mean(s5, one_score_per_subcategory):
    result = BenchmarkCalculator(s5).calculate(one_score_per_subcategory, "Novice")

    energies = [item.energy for item in result.subcategories.values()]
    assert result.overall_energy == pytest.approx(len(energies) / sum(1 / value for value in energies))


def test_overall_is_unmeasured_until_all_nine_exist(s5, one_score_per_subcategory):
    result = BenchmarkCalculator(s5).calculate(one_score_per_subcategory[:-1], "Novice")

    assert result.overall_energy is None
    assert result.missing_subcategories == ("Switching / Stability",)


@pytest.mark.parametrize("value, expected", [(0, 0), (540, 300), (640, 400)])
def test_exact_targets_map_to_exact_energy(s5, value, expected):
    definition = next(
        item for item in s5.benchmarks if item.name == "VT Floating Heads Novice S5"
    )

    assert score_to_energy(definition, value) == pytest.approx(expected)


def test_alias_resolves_to_one_definition(s5):
    result = BenchmarkCalculator(s5).calculate(
        [score("  vt-floating heads novice s5 ", 540)], "Novice"
    )

    scenario = result.subcategories["Clicking / Linear"].scenarios[0]
    assert scenario.benchmark_name == "VT Floating Heads Novice S5"
    assert scenario.energy == pytest.approx(300)


def test_best_imported_score_is_selected_once_per_benchmark(s5):
    result = BenchmarkCalculator(s5).calculate(
        [
            score("VT Floating Heads Novice S5", 460),
            score("VT Floating Heads Novice S5", 540),
        ],
        "Novice",
    )

    scenarios = result.subcategories["Clicking / Linear"].scenarios
    assert [(item.score, item.energy) for item in scenarios] == [(540, 300)]


def test_harmonic_mean_rejects_empty_or_non_positive_energies():
    with pytest.raises(ValueError, match="positive energies"):
        harmonic_mean(())
    with pytest.raises(ValueError, match="positive energies"):
        harmonic_mean((100, 0))


def test_overall_tier_uses_highest_reached_definition_rank(s5, one_score_per_subcategory):
    result = BenchmarkCalculator(s5).calculate(one_score_per_subcategory, "Novice")

    assert result.overall_energy == pytest.approx(100)
    assert result.overall_tier == "Iron"


def test_advanced_energy_uncaps_only_after_overall_threshold(
    advanced_s5, advanced_scores
):
    below = BenchmarkCalculator(advanced_s5).calculate(advanced_scores, "Advanced")
    assert max(
        item.energy for sub in below.subcategories.values() for item in sub.scenarios
    ) <= 1200

    above = BenchmarkCalculator(advanced_s5).calculate(
        raise_all_subcategories(advanced_scores), "Advanced"
    )
    assert max(
        item.energy for sub in above.subcategories.values() for item in sub.scenarios
    ) > 1200
