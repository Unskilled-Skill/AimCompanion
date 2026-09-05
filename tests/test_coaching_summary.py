from core.coaching.freshness import FreshnessState
from core.coaching.summary import build_coaching_summary
from models.profile import PlayerProfile
from models.score import CategoryScore, SubcategoryScore


def test_summary_leads_with_rank_weakness_trend_and_evidence():
    profile = PlayerProfile(
        categories=[CategoryScore(
            name="Clicking",
            subcategories=[SubcategoryScore(
                name="Static", category="Clicking", energy=120, tier="Iron"
            )],
        )],
        overall_energy=150,
        overall_tier="Iron",
        definition_version="kovaaks_s5",
        calculation_method="voltaic_official",
    )
    freshness = {
        "Clicking / Static": FreshnessState(
            "Clicking / Static", True, 3, False, "current"
        )
    }
    summary = build_coaching_summary(
        profile, {"Clicking / Static": -4.5}, freshness
    )

    assert "Iron" in summary.rank_text
    assert "Clicking / Static" in summary.weakness_text
    assert "-4.5%" in summary.trend_text
    assert summary.headline
    assert summary.evidence.definition_version == "kovaaks_s5"


def test_summary_lowers_confidence_when_benchmark_is_due():
    profile = PlayerProfile(
        categories=[], overall_energy=None, overall_tier="Unranked",
        definition_version="kovaaks_s5", calculation_method="voltaic_official",
    )
    freshness = {
        "Tracking / Reactive": FreshnessState(
            "Tracking / Reactive", False, 0, True, "missing"
        )
    }
    summary = build_coaching_summary(profile, {}, freshness)
    assert summary.evidence.confidence == "low"
    assert "benchmark" in summary.headline.casefold()


def test_due_benchmark_headline_names_the_next_area_and_remaining_count():
    profile = PlayerProfile(
        categories=[], overall_energy=None, overall_tier="Unranked",
        definition_version="kovaaks_s5", calculation_method="voltaic_official",
    )
    freshness = {
        "Clicking / Static": FreshnessState(
            "Clicking / Static", False, 0, True, "missing",
        ),
        "Tracking / Reactive": FreshnessState(
            "Tracking / Reactive", False, 0, True, "missing",
        ),
    }

    summary = build_coaching_summary(profile, {}, freshness)

    assert "Clicking / Static" in summary.headline
    assert "1 more" in summary.headline
