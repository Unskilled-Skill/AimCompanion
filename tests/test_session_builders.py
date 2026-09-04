import json
from pathlib import Path

import pytest

from core.sessions import SessionMode
from core.sessions.builders import build_full_routine_plan, build_warmup_plan
from core.warmups import GAME_WARMUP_ROUTINES


DATA_DIR = Path(__file__).parents[1] / "data"


@pytest.fixture
def hna_speed_stopping():
    payload = json.loads((DATA_DIR / "tacfps_guide.json").read_text(encoding="utf-8"))
    return payload["routines"][0]


def test_full_routine_keeps_authored_order_runs_and_guides(hna_speed_stopping):
    plan = build_full_routine_plan(hna_speed_stopping, resume_index=0)
    exercises = hna_speed_stopping["exercises"]

    assert plan.mode is SessionMode.FULL_ROUTINE
    assert [step.scenario for step in plan.steps] == [item["scenario"] for item in exercises]
    assert [step.required_runs for step in plan.steps] == [item["duration_min"] for item in exercises]
    for step, exercise in zip(plan.steps, exercises):
        expected = exercise["performance_guide"]
        assert set(step.guide) == set(expected)
        for key, value in expected.items():
            assert step.guide[key] == (tuple(value) if isinstance(value, list) else value)
    assert plan.official_steps == plan.steps


def test_explicit_prescribed_runs_override_duration_compatibility_value():
    routine = {
        "name": "Explicit runs",
        "source": "Fixture",
        "source_url": "https://example.test/source",
        "targets": ["Clicking_Static"],
        "exercises": [{
            "scenario": "A",
            "prescribed_runs": 7,
            "duration_min": 3,
            "performance_guide": {"steps": ["Do the source step."]},
        }],
    }
    plan = build_full_routine_plan(routine, resume_index=0)
    assert plan.steps[0].required_runs == 7
    assert plan.steps[0].estimated_seconds == 180


def test_missing_source_correction_keys_remain_absent():
    routine = {
        "name": "No corrections",
        "source": "Fixture",
        "source_url": "https://example.test/source",
        "targets": ["Clicking_Static"],
        "exercises": [{
            "scenario": "A",
            "duration_min": 1,
            "performance_guide": {"setup": "Exact setup"},
        }],
    }
    guide = build_full_routine_plan(routine, 0).steps[0].guide
    assert dict(guide) == {"setup": "Exact setup"}
    assert "adjust" not in guide
    assert "mistakes" not in guide


def test_game_warmup_uses_exact_selected_context_without_prompt():
    plan = build_warmup_plan("game", "Valorant & Counterstrike")
    source = GAME_WARMUP_ROUTINES["Valorant & Counterstrike"]

    assert plan.mode is SessionMode.WARMUP
    assert [step.scenario for step in plan.steps] == [item["scenario"] for item in source]
    assert [step.estimated_seconds for step in plan.steps] == [
        item["duration_min"] * 60 for item in source
    ]


def test_unknown_warmup_context_is_rejected():
    with pytest.raises(ValueError, match="warm-up context"):
        build_warmup_plan("unknown", "anything")
