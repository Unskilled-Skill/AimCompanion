from dataclasses import replace
from datetime import datetime

import pytest

from core.benchmarks import DefinitionRepository
from core.benchmarks.calculator import (
    BenchmarkCalculator,
    harmonic_mean,
    score_to_energy,
)
from models.score import Score
from models.benchmark import energy_to_score


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


def scores_at_energy(definitions, difficulty: str, desired_energy: float) -> list[Score]:
    selected = {}
    for definition in definitions.benchmarks:
        if definition.difficulty == difficulty:
            selected.setdefault(f"{definition.category} / {definition.subcategory}", definition)
    scores = []
    for definition in selected.values():
        first_score, first_energy = definition.targets[0]
        if desired_energy <= first_energy:
            target_score = first_score * desired_energy / first_energy
        else:
            lower_score, lower_energy = definition.targets[-2]
            upper_score, upper_energy = definition.targets[-1]
            for lower, upper in zip(definition.targets, definition.targets[1:]):
                lower_score, lower_energy = lower
                upper_score, upper_energy = upper
                if desired_energy <= upper_energy:
                    break
            slope = (upper_score - lower_score) / (upper_energy - lower_energy)
            target_score = lower_score + (desired_energy - lower_energy) * slope
        scores.append(
            score(
                definition.name,
                target_score,
                difficulty,
            )
        )
    return scores


def test_subcategory_uses_highest_scenario_energy(s5, scores_for_all_nine):
    scores_for_all_nine += [
        score("VT PGT Novice S5", 3050),
        score("VT Snake Track Novice S5", 1),
    ]

    result = BenchmarkCalculator(s5).calculate(scores_for_all_nine, "Novice")

    precise = result.subcategories["Tracking / Precise"]
    assert precise.energy == max(item.energy for item in precise.scenarios)


def test_overall_is_harmonic_mean(s5):
    desired = (100, 200, 300, 400, 100, 200, 300, 400, 100)
    selected = {}
    for definition in s5.benchmarks:
        if definition.difficulty == "Novice":
            selected.setdefault(f"{definition.category} / {definition.subcategory}", definition)
    inputs = []
    for subcategory, energy in zip(s5.required_subcategories, desired):
        definition = selected[subcategory]
        first_score, first_energy = definition.targets[0]
        if energy == first_energy:
            value = first_score
        else:
            target_index = int(energy // 100) - 1
            value = definition.targets[target_index][0]
        inputs.append(score(definition.name, value))

    result = BenchmarkCalculator(s5).calculate(inputs, "Novice")

    assert tuple(item.energy for item in result.subcategories.values()) == pytest.approx(desired)
    assert result.overall_energy == pytest.approx(5400 / 31)


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


@pytest.mark.parametrize(("energy", "expected_tier"), [(99, None), (100, "Iron")])
def test_complete_overall_energy_respects_the_first_rank_boundary(
    s5, energy, expected_tier
):
    result = BenchmarkCalculator(s5).calculate(
        scores_at_energy(s5, "Novice", energy), "Novice"
    )

    assert result.overall_energy == pytest.approx(energy)
    assert result.overall_tier == expected_tier


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


@pytest.mark.parametrize(
    ("difficulty", "baseline_energy"),
    [("Novice", 100), ("Intermediate", 500)],
)
def test_lower_difficulties_are_never_energy_capped(s5, difficulty, baseline_energy):
    scores = scores_at_energy(s5, difficulty, baseline_energy)
    scores[0] = scores_at_energy(s5, difficulty, 1300)[0]

    result = BenchmarkCalculator(s5).calculate(scores, difficulty)

    assert result.subcategories["Clicking / Dynamic"].energy == pytest.approx(1300)
    assert result.overall_energy < 1200


def test_advanced_high_raw_scenario_stays_capped_below_overall_threshold(s5):
    scores = scores_at_energy(s5, "Advanced", 900)
    scores[0] = scores_at_energy(s5, "Advanced", 1300)[0]

    result = BenchmarkCalculator(s5).calculate(scores, "Advanced")

    assert result.subcategories["Clicking / Dynamic"].energy == pytest.approx(1200)
    assert result.overall_energy < 1200


def test_capped_difficulty_without_uncap_threshold_stays_permanently_capped(s5):
    definitions = replace(
        s5,
        benchmarks=tuple(
            replace(item, uncap_overall_energy=None)
            if item.difficulty == "Advanced"
            else item
            for item in s5.benchmarks
        ),
    )

    result = BenchmarkCalculator(definitions).calculate(
        scores_at_energy(definitions, "Advanced", 1300), "Advanced"
    )

    assert result.overall_energy == pytest.approx(1200)


@pytest.mark.parametrize(
    ("benchmark_name", "energy"),
    [
        ("VT Floating Heads Novice S5", 50),
        ("VT Floating Heads Novice S5", 350),
        ("VT Pasu Advanced S5", 1250),
    ],
)
def test_energy_to_score_round_trips_representative_curve_segments(
    benchmark_name, energy
):
    converted_score = energy_to_score(benchmark_name, energy)

    assert score_to_energy(
        next(
            item
            for item in DefinitionRepository.bundled().load_active().benchmarks
            if item.name == benchmark_name
        ),
        converted_score,
    ) == pytest.approx(energy)


def test_mixed_numeric_uncap_thresholds_are_rejected_before_calculation(s5):
    original = next(item for item in s5.benchmarks if item.difficulty == "Advanced")
    changed = replace(
        original,
        uncap_overall_energy=1100,
    )
    definitions = replace(
        s5,
        benchmarks=tuple(changed if item is original else item for item in s5.benchmarks),
    )

    with pytest.raises(ValueError, match="consistent uncap_overall_energy"):
        BenchmarkCalculator(definitions).calculate((), "Advanced")


def test_none_and_numeric_uncap_thresholds_are_rejected_before_calculation(s5):
    original = next(item for item in s5.benchmarks if item.difficulty == "Advanced")
    changed = replace(
        original,
        uncap_overall_energy=None,
    )
    definitions = replace(
        s5,
        benchmarks=tuple(changed if item is original else item for item in s5.benchmarks),
    )

    with pytest.raises(ValueError, match="consistent uncap_overall_energy"):
        BenchmarkCalculator(definitions).calculate((), "Advanced")
