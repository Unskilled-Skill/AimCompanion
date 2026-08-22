from collections import defaultdict
from datetime import datetime, timedelta
from statistics import mean, pstdev

from models.benchmark import TIERS, energy_to_score, score_to_energy


def _days_since(timestamp: str | None) -> int:
    if not timestamp:
        return 999
    try:
        return max(0, (datetime.now() - datetime.fromisoformat(timestamp)).days)
    except (TypeError, ValueError):
        return 999


def _next_tier(current: str):
    for index, tier in enumerate(TIERS):
        if tier["name"] == current and index + 1 < len(TIERS):
            return TIERS[index + 1]
    return None


def build_skill_intelligence(profile, db) -> list[dict]:
    """Build evidence, progression, maintenance, and next-rank data for all skills."""
    last_training = db.get_last_training_by_focus()
    skill_feedback = db.get_skill_feedback_summary()
    skills = []
    for category in profile.categories:
        for subcategory in category.subcategories:
            points = []
            benchmark_health = []
            for benchmark in subcategory.benchmarks:
                history = db.get_score_history(benchmark.name)
                energies = [score_to_energy(benchmark.name, score.score) for score in history]
                points.extend((score.timestamp, energy) for score, energy in zip(history, energies))
                benchmark_health.append({
                    "name": benchmark.name,
                    "scenario": benchmark.scenario,
                    "attempts": len(history),
                    "last_tested": history[-1].timestamp.isoformat() if history else None,
                    "current_score": history[-1].score if history else 0.0,
                })

            points.sort(key=lambda item: item[0])
            recent = [energy for _, energy in points[-6:]]
            attempts = len(points)
            measured_benchmarks = sum(1 for item in benchmark_health if item["attempts"])
            coverage = measured_benchmarks / max(1, len(benchmark_health))
            last_tested = points[-1][0].isoformat() if points else None
            recency_days = _days_since(last_tested)
            recency_score = 1.0 if recency_days <= 14 else 0.7 if recency_days <= 30 else 0.4 if recency_days <= 60 else 0.1
            confidence_score = min(1.0, (
                coverage * 0.45 + min(1.0, attempts / 12) * 0.30 + recency_score * 0.25
            ))
            confidence = "high" if confidence_score >= 0.75 else "medium" if confidence_score >= 0.45 else "low"
            consistency = (
                pstdev(recent) / mean(recent)
                if len(recent) >= 3 and mean(recent) else None
            )
            trend_pct = None
            if len(points) >= 6:
                previous = mean(energy for _, energy in points[-6:-3])
                current = mean(energy for _, energy in points[-3:])
                trend_pct = ((current - previous) / previous * 100) if previous else None
            progression = "hold"
            if confidence != "low" and trend_pct is not None:
                if trend_pct >= 4 and (consistency is None or consistency <= 0.15):
                    progression = "advance"
                elif trend_pct <= -8:
                    progression = "regress"

            focus_key = f"{category.name} / {subcategory.name}"
            feedback = skill_feedback.get(focus_key.casefold(), {})
            latest_rating = feedback.get("latest_rating")
            if latest_rating == "too_easy":
                progression = "advance"
            elif latest_rating == "too_hard":
                progression = "regress"
            training_days = _days_since(last_training.get(focus_key))
            next_tier = _next_tier(subcategory.tier)
            target_scores = {}
            if next_tier:
                target_scores = {
                    benchmark.name: energy_to_score(
                        benchmark.name, next_tier["min_energy"]
                    )
                    for benchmark in subcategory.benchmarks
                }
            skills.append({
                "key": f"{category.name}_{subcategory.name}",
                "category": category.name,
                "subcategory": subcategory.name,
                "energy": subcategory.energy,
                "tier": subcategory.tier,
                "attempts": attempts,
                "coverage": coverage,
                "last_tested": last_tested,
                "test_age_days": recency_days,
                "confidence": confidence,
                "confidence_score": confidence_score,
                "consistency": consistency,
                "trend_pct": trend_pct,
                "progression": progression,
                "latest_feedback": latest_rating,
                "last_trained": last_training.get(focus_key),
                "training_age_days": training_days,
                "next_tier": next_tier["name"] if next_tier else None,
                "next_energy": next_tier["min_energy"] if next_tier else None,
                "energy_gap": max(0, next_tier["min_energy"] - subcategory.energy) if next_tier else 0,
                "target_scores": target_scores,
                "benchmarks": benchmark_health,
            })

    max_energy = max((skill["energy"] for skill in skills), default=0)
    scale = max(1.0, max_energy)
    for skill in skills:
        weakness = max(0.0, (max_energy - skill["energy"]) / scale)
        overdue = min(1.0, skill["training_age_days"] / 21)
        evidence_factor = 0.5 + skill["confidence_score"] * 0.5
        skill["weakness_severity"] = weakness
        skill["priority"] = (weakness * 0.7 + overdue * 0.3) * evidence_factor
        skill["benchmark_due"] = (
            skill["confidence"] == "low" or skill["test_age_days"] > 30
        )
    return skills


def build_adaptive_schedule(skills: list[dict]) -> list[dict]:
    """Weight weak/stale skills while including every benchmark subcategory."""
    if not skills:
        return []
    ranked = sorted(skills, key=lambda item: item["priority"], reverse=True)
    remaining = {}
    for skill in ranked:
        repeats = 1
        if skill["confidence"] != "low" and skill["weakness_severity"] >= 0.12:
            repeats += 1
        if skill["confidence"] != "low" and skill["weakness_severity"] >= 0.30:
            repeats += 1
        if skill["training_age_days"] > 21:
            repeats = min(3, repeats + 1)
        remaining[skill["key"]] = repeats

    schedule = []
    last_category = None
    while any(remaining.values()):
        available = [
            skill for skill in ranked
            if remaining[skill["key"]] > 0 and skill["category"] != last_category
        ] or [skill for skill in ranked if remaining[skill["key"]] > 0]
        selected = max(
            available,
            key=lambda item: (item["priority"], remaining[item["key"]]),
        )
        schedule.append(selected)
        remaining[selected["key"]] -= 1
        last_category = selected["category"]
    return schedule


def plan_benchmark_checks(skills: list[dict], limit: int = 5) -> list[dict]:
    checks = []
    for skill in skills:
        if not skill["benchmark_due"] and skill["energy_gap"] > 20:
            continue
        candidates = sorted(
            skill["benchmarks"],
            key=lambda item: (item["attempts"] > 0, item["attempts"], item["last_tested"] or ""),
        )
        if not candidates:
            continue
        benchmark = candidates[0]
        reason = (
            "Unmeasured benchmark" if benchmark["attempts"] == 0 else
            "Low-confidence skill estimate" if skill["confidence"] == "low" else
            "Benchmark is over 30 days old" if skill["test_age_days"] > 30 else
            f"Close to {skill['next_tier']}"
        )
        checks.append({**benchmark, "skill_key": skill["key"], "reason": reason})
    return checks[:limit]


def build_scenario_signals(db) -> dict[str, dict]:
    feedback = db.get_scenario_feedback_summary()
    effectiveness = db.get_scenario_effectiveness_summary()
    keys = set(feedback) | set(effectiveness)
    signals = {}
    for key in keys:
        ratings = feedback.get(key, {}).get("ratings", {})
        average_delta = effectiveness.get(key, {}).get("average_delta_pct")
        adjustment = 0.0
        adjustment += min(3.0, max(-3.0, (average_delta or 0) / 5))
        adjustment += ratings.get("productive", 0) * 1.5
        adjustment -= ratings.get("too_hard", 0) * 2
        adjustment -= ratings.get("too_easy", 0) * 0.5
        if ratings.get("discomfort"):
            adjustment -= 100
        signals[key] = {
            "adjustment": adjustment,
            "ratings": ratings,
            "average_delta_pct": average_delta,
        }
    return signals


def detect_fatigue(db) -> dict | None:
    grouped = defaultdict(list)
    for score in reversed(db.get_recent_raw_scores(80)):
        grouped[score.scenario.casefold()].append(score)
    eligible = [scores for scores in grouped.values() if len(scores) >= 6]
    if not eligible:
        return None
    scores = max(eligible, key=lambda items: items[-1].timestamp)
    if datetime.now() - scores[-1].timestamp > timedelta(hours=6):
        return None
    recent = mean(score.score for score in scores[-3:])
    baseline_window = scores[-8:-3]
    baseline = mean(score.score for score in baseline_window)
    drop_pct = ((recent - baseline) / baseline * 100) if baseline else 0.0
    if drop_pct > -10:
        return None
    return {
        "scenario": scores[-1].scenario,
        "recent_average": recent,
        "baseline_average": baseline,
        "drop_pct": drop_pct,
        "message": "Recent performance is over 10% below baseline; stop and recover.",
    }
