from collections import Counter
from dataclasses import replace

from core.coaching.evidence import RecommendationEvidence
from core.coaching.freshness import FreshnessState
from core.coaching.recommender import (
    CoachingRecommender,
    RecommendationContext,
    RotationState,
    ScenarioCandidate,
)
from models.profile import PlayerProfile
from models.score import CategoryScore, SubcategoryScore


SKILLS = (
    ("Clicking", "Static", 100.0),
    ("Tracking", "Reactive", 200.0),
    ("Switching", "Speed", 300.0),
)


def _profile():
    categories = []
    for category, subcategory, energy in SKILLS:
        categories.append(CategoryScore(
            name=category,
            subcategories=[SubcategoryScore(
                name=subcategory,
                category=category,
                energy=energy,
                tier="Iron",
            )],
        ))
    return PlayerProfile(
        categories=categories,
        overall_energy=180,
        overall_tier="Iron",
        definition_version="kovaaks_s5",
        calculation_method="voltaic_official",
    )


def _context(due_static=False):
    freshness = {}
    candidates = []
    for category, subcategory, _ in SKILLS:
        key = f"{category} / {subcategory}"
        due = due_static and key == "Clicking / Static"
        freshness[key] = FreshnessState(
            subcategory=key,
            measured=True,
            blocks_since_check=12 if due else 2,
            due=due,
            confidence="stale" if due else "current",
        )
        candidates.extend((
            ScenarioCandidate(
                scenario=f"{subcategory} A",
                category=category,
                subcategory=subcategory,
                estimated_seconds=180,
                guide={"steps": [f"Train {subcategory}"]},
            ),
            ScenarioCandidate(
                scenario=f"{subcategory} B",
                category=category,
                subcategory=subcategory,
                estimated_seconds=240,
                guide={"steps": [f"Train {subcategory}"]},
            ),
        ))
    return RecommendationContext(
        profile=_profile(),
        freshness=freshness,
        trends={"Clicking / Static": -3.0},
        candidates=tuple(candidates),
        rotation=RotationState(),
    )


def test_due_benchmark_precedes_weakness_work():
    pick = CoachingRecommender().next(_context(due_static=True))
    assert pick.kind == "benchmark_check"
    assert pick.subcategory == "Static"
    assert pick.evidence.blocks_since_benchmark == 12


def test_rotation_is_fifty_thirty_twenty_without_consecutive_subcategories():
    recommender = CoachingRecommender()
    context = _context()
    picks = []
    for _ in range(10):
        pick = recommender.next(context)
        picks.append(pick)
        context = replace(
            context,
            rotation=recommender.accept(context.rotation, pick),
        )

    assert Counter(pick.priority_rank for pick in picks) == Counter({1: 5, 2: 3, 3: 2})
    assert all(
        left.subcategory != right.subcategory
        for left, right in zip(picks, picks[1:])
    )


def test_recommendation_explains_inputs_and_is_deterministic():
    context = _context()
    first = CoachingRecommender().next(context)
    second = CoachingRecommender().next(context)

    assert first == second
    assert isinstance(first.evidence, RecommendationEvidence)
    assert first.evidence.rule == "weakness_rotation"
    assert first.evidence.definition_version == "kovaaks_s5"
    assert first.evidence.summary
    assert first.evidence.confidence == "high"


def test_preview_does_not_consume_rotation_cursor():
    context = _context()
    recommender = CoachingRecommender()
    recommender.next(context)
    recommender.next(context)
    assert context.rotation.cursor == 0


def test_same_scenario_is_avoided_when_an_alternative_exists():
    context = replace(
        _context(),
        rotation=RotationState(last_scenario="Static A"),
    )
    assert CoachingRecommender().next(context).scenario == "Static B"


def test_estimated_block_duration_is_clamped_to_three_to_five_minutes():
    context = _context()
    candidate = replace(context.candidates[0], estimated_seconds=900)
    context = replace(context, candidates=(candidate,) + context.candidates[1:])
    assert CoachingRecommender().next(context).estimated_seconds == 300
