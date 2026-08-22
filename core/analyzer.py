from models.score import PlayerProfile, CategoryScore, SubcategoryScore, BenchmarkInfo
from models.benchmark import BENCHMARKS, get_benchmarks_by_difficulty, energy_to_tier, score_to_energy, energy_to_score
from models.database import Database


def build_profile(db: Database, difficulty: str = "Novice", score_mode: str = "best") -> PlayerProfile:
    if score_mode == "latest":
        raw_scores = db.get_most_recent_per_benchmark()
    elif score_mode == "recent_30":
        raw_scores = db.get_recent_scores_per_benchmark(days=30)
    elif score_mode == "recent_7":
        raw_scores = db.get_recent_scores_per_benchmark(days=7)
    elif score_mode == "average":
        raw_scores = db.get_average_recent_scores()
    else:
        raw_scores = db.get_best_scores()

    benchmark_defs = get_benchmarks_by_difficulty(difficulty)
    valid_names = {b["name"] for b in benchmark_defs}

    best_by_benchmark = {}
    for s in raw_scores:
        if s.benchmark_name not in valid_names:
            continue
        if s.benchmark_name not in best_by_benchmark or s.score > best_by_benchmark[s.benchmark_name].score:
            best_by_benchmark[s.benchmark_name] = s

    subcat_map = {}
    for bdef in benchmark_defs:
        key = (bdef["category"], bdef["subcategory"])
        if key not in subcat_map:
            subcat_map[key] = SubcategoryScore(
                name=bdef["subcategory"],
                category=bdef["category"],
            )
        bi = BenchmarkInfo(
            name=bdef["name"],
            scenario=bdef["scenario"],
            category=bdef["category"],
            subcategory=bdef["subcategory"],
            difficulty=difficulty,
        )
        score_obj = best_by_benchmark.get(bdef["name"])
        if score_obj:
            bi.update_from_score(score_obj)
        subcat_map[key].benchmarks.append(bi)

    cat_map = {}
    for (cat, sub), subcat in subcat_map.items():
        if cat not in cat_map:
            cat_map[cat] = CategoryScore(name=cat)
        cat_map[cat].subcategories.append(subcat)

    profile = PlayerProfile(
        difficulty=difficulty,
        categories=list(cat_map.values()),
    )
    profile.recalculate()
    return profile


def identify_weaknesses(profile: PlayerProfile) -> list[dict]:
    weaknesses = []
    overall = profile.overall_energy
    for cat in profile.categories:
        for sub in cat.subcategories:
            for bench in sub.benchmarks:
                if bench.best_score <= 0:
                    continue
                if overall > 0:
                    relative_gap = (overall - bench.energy) / overall
                else:
                    relative_gap = 0.0
                abs_gap = overall - bench.energy
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
    weaknesses.sort(key=lambda w: w["priority"], reverse=True)
    return weaknesses


def get_improvement_suggestions(profile: PlayerProfile) -> list[dict]:
    suggestions = []
    weakest = profile.get_weakest_subcategories(5)
    overall = profile.overall_energy

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
            best_bench = max(sub.benchmarks, key=lambda b: b.energy)
            target_score = energy_to_score(best_bench.name, target_energy)
            recommended_benchmark = best_bench.name
        else:
            target_score = energy_to_score(None, target_energy)

        suggestions.append({
            "subcategory": sub.name,
            "category": sub.category,
            "current_energy": sub.energy,
            "target_energy": target_energy,
            "target_score": target_score,
            "current_tier": sub.tier,
            "benchmarks": [b.name for b in sub.benchmarks],
            "recommended_benchmark": recommended_benchmark,
            "improvement_pct": target_pct,
        })

    return suggestions

