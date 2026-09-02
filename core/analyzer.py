from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta

from core.benchmarks import DefinitionRepository
from core.benchmarks.calculator import BenchmarkCalculator
from models.benchmark import energy_to_score
from models.database import Database
from models.profile import PlayerProfile, profile_from_benchmark_result


def build_profile(
    db: Database, difficulty: str = "Novice", score_mode: str = "best"
) -> PlayerProfile:
    definitions = DefinitionRepository.bundled().load_active()
    calculator = BenchmarkCalculator(definitions)
    score_mode = score_mode if score_mode in {
        "best", "latest", "recent_7", "recent_30", "average"
    } else "best"
    all_scores = db.get_all_scores()
    scores = _select_scores(all_scores, calculator, difficulty, score_mode)
    result = calculator.calculate(scores, difficulty)
    histories = defaultdict(list)
    for score in all_scores:
        definition = calculator.definition_for_score(score)
        if definition is not None and definition.difficulty == difficulty:
            histories[definition.name].append(score)
    return profile_from_benchmark_result(
        result,
        definitions,
        histories,
        calculation_method=(
            "voltaic_official" if score_mode == "best" else "local_current_form"
        ),
        score_input_mode=score_mode,
    )


def _select_scores(scores, calculator, difficulty: str, score_mode: str):
    """Canonicalize scenario aliases before applying score-mode reductions."""
    grouped = defaultdict(list)
    for score in scores:
        definition = calculator.definition_for_score(score)
        if definition is not None and definition.difficulty == difficulty:
            grouped[definition].append(score)

    selected = []
    cutoff = None
    if score_mode == "recent_7":
        cutoff = datetime.now() - timedelta(days=7)
    elif score_mode == "recent_30":
        cutoff = datetime.now() - timedelta(days=30)

    for definition in sorted(grouped, key=lambda item: item.name):
        attempts = grouped.get(definition, [])
        if cutoff is not None:
            attempts = [item for item in attempts if item.timestamp >= cutoff]
        if not attempts:
            continue
        if score_mode == "best":
            selected.append(max(attempts, key=lambda item: (item.score, item.timestamp)))
        elif score_mode in {"latest", "recent_7", "recent_30"}:
            selected.append(max(attempts, key=lambda item: item.timestamp))
        else:
            recent = sorted(attempts, key=lambda item: item.timestamp, reverse=True)[:5]
            latest = recent[0]
            selected.append(
                replace(
                    latest,
                    benchmark_name=definition.name,
                    scenario=definition.scenario,
                    category=definition.category,
                    subcategory=definition.subcategory,
                    difficulty=definition.difficulty,
                    score=sum(item.score for item in recent) / len(recent),
                )
            )
    return selected


def identify_weaknesses(profile: PlayerProfile) -> list[dict]:
    weaknesses = []
    overall = profile.overall_energy
    for cat in profile.categories:
        for sub in cat.subcategories:
            for bench in sub.benchmarks:
                if bench.best_score <= 0:
                    continue
                if overall and overall > 0:
                    relative_gap = (overall - bench.energy) / overall
                else:
                    relative_gap = 0.0
                abs_gap = (overall - bench.energy) if overall is not None else 0.0
                if abs_gap > 0:
                    weaknesses.append({
                        "benchmark": bench,
                        "subcategory": sub.name,
                        "category": cat.name,
                        "score": bench.best_score,
                        "energy": bench.energy,
                        "tier": bench.tier,
                        "gap": abs_gap,
                        "relative_gap": relative_gap,
                        "priority": relative_gap * 100,
                    })
    weaknesses.sort(key=lambda weakness: weakness["priority"], reverse=True)
    return weaknesses


def get_improvement_suggestions(profile: PlayerProfile) -> list[dict]:
    suggestions = []
    weakest = profile.get_weakest_subcategories(5)
    overall = profile.overall_energy or 0.0

    if overall < 200:
        target_pct = 0.30
    elif overall < 500:
        target_pct = 0.20
    elif overall < 800:
        target_pct = 0.15
    else:
        target_pct = 0.10

    for sub in weakest:
        target_energy = sub.energy * (1.0 + target_pct)
        if target_energy <= sub.energy:
            target_energy = sub.energy + 10

        recommended_benchmark = None
        if sub.benchmarks:
            best_benchmark = max(sub.benchmarks, key=lambda benchmark: benchmark.energy)
            target_score = energy_to_score(best_benchmark.name, target_energy)
            recommended_benchmark = best_benchmark.name
        else:
            target_score = energy_to_score(None, target_energy)

        suggestions.append({
            "subcategory": sub.name,
            "category": sub.category,
            "current_energy": sub.energy,
            "target_energy": target_energy,
            "target_score": target_score,
            "current_tier": sub.tier,
            "benchmarks": [benchmark.name for benchmark in sub.benchmarks],
            "recommended_benchmark": recommended_benchmark,
            "improvement_pct": target_pct,
        })

    return suggestions
