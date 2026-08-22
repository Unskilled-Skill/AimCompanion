import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

with open(os.path.join(DATA_DIR, "benchmarks.json"), "r") as f:
    BENCHMARKS = json.load(f)

with open(os.path.join(DATA_DIR, "tiers.json"), "r") as f:
    TIERS = json.load(f)


def get_benchmark(scenario_name: str) -> dict | None:
    for b in BENCHMARKS:
        if b["scenario"] == scenario_name:
            return b
    return None


def get_benchmarks_by_difficulty(difficulty: str) -> list[dict]:
    return [b for b in BENCHMARKS if b["difficulty"] == difficulty]


def get_subcategories() -> list[str]:
    return sorted(set(b["subcategory"] for b in BENCHMARKS))


def get_categories() -> list[str]:
    return sorted(set(b["category"] for b in BENCHMARKS))


def get_benchmarks_by_subcategory(category: str, subcategory: str) -> list[dict]:
    return [b for b in BENCHMARKS if b["category"] == category and b["subcategory"] == subcategory]


TIER_ENERGY_MAP = {t["name"]: t["min_energy"] for t in TIERS}


def score_to_energy(benchmark_name_or_score, score: float = None) -> float:
    if isinstance(benchmark_name_or_score, (int, float)):
        b_name = None
        sc = float(benchmark_name_or_score)
    else:
        b_name = benchmark_name_or_score
        sc = float(score) if score is not None else 0.0

    if sc <= 0:
        return 0.0

    b = get_benchmark(b_name) if b_name else None
    if b and "targets" in b and b["targets"]:
        targets = b["targets"]
        points = []
        for tier_name, target_score in targets.items():
            if tier_name in TIER_ENERGY_MAP:
                points.append((TIER_ENERGY_MAP[tier_name], float(target_score)))
        points.sort(key=lambda x: x[0])

        if not points:
            return sc / 50.0

        max_cap = 1300.0
        diff = b.get("difficulty", "")
        if diff == "Novice":
            max_cap = 500.0
        elif diff == "Intermediate":
            max_cap = 700.0

        if sc <= points[0][1]:
            if points[0][1] > 0 and points[0][0] > 0:
                res = points[0][0] * (sc / points[0][1])
                return min(res, max_cap)
            return 0.0

        for i in range(len(points) - 1):
            e1, s1 = points[i]
            e2, s2 = points[i + 1]
            if s1 <= sc <= s2:
                if s2 == s1:
                    return min(float(e1), max_cap)
                res = e1 + (e2 - e1) * ((sc - s1) / (s2 - s1))
                return min(res, max_cap)

        e_last, s_last = points[-1]
        if len(points) >= 2:
            e_prev, s_prev = points[-2]
            slope = (e_last - e_prev) / (s_last - s_prev) if s_last != s_prev else 0.0
            res = e_last + slope * (sc - s_last)
        else:
            res = e_last * (sc / s_last) if s_last > 0 else 0.0

        return min(res, max_cap)

    return sc / 50.0


def energy_to_score(benchmark_name: str, energy: float) -> float:
    if energy <= 0:
        return 0.0

    b = get_benchmark(benchmark_name) if benchmark_name else None
    if b and "targets" in b and b["targets"]:
        targets = b["targets"]
        points = []
        for tier_name, target_score in targets.items():
            if tier_name in TIER_ENERGY_MAP:
                points.append((TIER_ENERGY_MAP[tier_name], float(target_score)))
        points.sort(key=lambda x: x[0])

        if not points:
            return energy * 50.0

        if energy <= points[0][0]:
            if points[0][0] > 0:
                return points[0][1] * (energy / points[0][0])
            return points[0][1]

        for i in range(len(points) - 1):
            e1, s1 = points[i]
            e2, s2 = points[i + 1]
            if e1 <= energy <= e2:
                if e2 == e1:
                    return float(s1)
                return s1 + (s2 - s1) * ((energy - e1) / (e2 - e1))

        e_last, s_last = points[-1]
        if len(points) >= 2:
            e_prev, s_prev = points[-2]
            slope = (s_last - s_prev) / (e_last - e_prev) if e_last != e_prev else 0.0
            return s_last + slope * (energy - e_last)
        else:
            return s_last * (energy / e_last) if e_last > 0 else 0.0

    return energy * 50.0


def energy_to_tier(energy: float) -> str:
    for tier in reversed(TIERS):
        if energy >= tier["min_energy"]:
            return tier["name"]
    return TIERS[0]["name"]


def get_tier_info(tier_name: str) -> dict:
    for t in TIERS:
        if t["name"] == tier_name:
            return t
    return TIERS[0]

