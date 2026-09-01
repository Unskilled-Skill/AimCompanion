from datetime import datetime, timedelta

import pytest

from core.analyzer import build_profile
from core.benchmarks import DefinitionRepository
from core.benchmarks.calculator import BenchmarkCalculator
from models.database import Database
from models.score import PlayerProfile, Score


_NOVICE_ENERGIES = (100, 200, 300, 400, 100, 200, 300, 400, 100)


def _score_for(definition, score, timestamp):
    return Score(
        benchmark_name=definition.name,
        scenario=definition.scenario,
        category=definition.category,
        subcategory=definition.subcategory,
        difficulty=definition.difficulty,
        score=score,
        timestamp=timestamp,
    )


@pytest.fixture
def db_with_s5_scores(tmp_path):
    definitions = DefinitionRepository.bundled().load_active()
    database = Database(str(tmp_path / "scores.sqlite"))
    selected = {}
    for definition in definitions.benchmarks:
        if definition.difficulty == "Novice":
            selected.setdefault(
                f"{definition.category} / {definition.subcategory}", definition
            )

    for index, (subcategory, energy) in enumerate(
        zip(definitions.required_subcategories, _NOVICE_ENERGIES)
    ):
        definition = selected[subcategory]
        target_index = (energy // 100) - 1
        database.insert_score(
            _score_for(
                definition,
                definition.targets[target_index][0],
                datetime(2026, 8, 30) + timedelta(minutes=index),
            ),
            csv_path=f"score-{index}.csv",
        )

    yield database
    database.close()


def test_build_profile_exposes_official_harmonic_energy(db_with_s5_scores):
    profile = build_profile(db_with_s5_scores, difficulty="Novice")
    result = BenchmarkCalculator(DefinitionRepository.bundled().load_active()).calculate(
        db_with_s5_scores.get_best_scores(), "Novice"
    )

    assert profile.overall_energy == pytest.approx(5400 / 31)
    assert profile.overall_energy == pytest.approx(result.overall_energy)
    assert profile.overall_tier == "Iron"
    assert profile.calculation_method == "voltaic_official"
    assert profile.definition_version == "kovaaks_s5"


def test_build_profile_is_unranked_until_all_nine_subcategories_are_measured(
    db_with_s5_scores,
):
    db_with_s5_scores.conn.execute(
        "DELETE FROM scores WHERE benchmark_name = ?",
        ("VT ControlTS Novice S5",),
    )
    db_with_s5_scores.conn.commit()

    profile = build_profile(db_with_s5_scores, difficulty="Novice")

    assert profile.overall_energy is None
    assert profile.overall_tier == "Unranked"
    assert [
        f"{subcategory.category} / {subcategory.name}"
        for subcategory in profile.get_weakest_subcategories(n=9)
    ] == [
        "Clicking / Static",
        "Tracking / Reactive",
        "Clicking / Dynamic",
        "Tracking / Control",
        "Clicking / Linear",
        "Switching / Speed",
        "Tracking / Precise",
        "Switching / Evasive",
    ]


def test_build_profile_preserves_benchmark_attempt_best_and_latest_values(
    db_with_s5_scores,
):
    db_with_s5_scores.insert_score(
        Score(
            benchmark_name="VT 1w4ts Novice S5",
            scenario="VT 1w4ts Novice S5",
            category="Clicking",
            subcategory="Static",
            difficulty="Novice",
            score=410,
            timestamp=datetime(2026, 9, 1),
        ),
        csv_path="latest-static.csv",
    )

    profile = build_profile(db_with_s5_scores, difficulty="Novice")
    benchmark = next(
        benchmark
        for category in profile.categories
        for subcategory in category.subcategories
        for benchmark in subcategory.benchmarks
        if benchmark.name == "VT 1w4ts Novice S5"
    )

    assert benchmark.attempts == 2
    assert benchmark.best_score == 820
    assert benchmark.latest_score == 410


def test_profile_from_result_exposes_selected_scenario_as_one_attempt(
    db_with_s5_scores,
):
    result = BenchmarkCalculator(DefinitionRepository.bundled().load_active()).calculate(
        db_with_s5_scores.get_best_scores(), "Novice"
    )

    profile = PlayerProfile.from_result(result)
    benchmark = next(
        benchmark
        for category in profile.categories
        for subcategory in category.subcategories
        for benchmark in subcategory.benchmarks
        if benchmark.name == "VT 1w4ts Novice S5"
    )

    assert benchmark.attempts == 1
    assert benchmark.best_score == 820
    assert benchmark.latest_score == 820
