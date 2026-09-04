from core.sessions.builders import build_full_routine_plan, next_full_routine_resume


def _routine():
    return {
        "name": "Five",
        "source": "Fixture v1",
        "source_url": "https://example.test/source",
        "targets": ["Clicking_Static"],
        "exercises": [
            {
                "scenario": name,
                "prescribed_runs": 7,
                "duration_min": 7,
                "performance_guide": {"steps": [f"Do {name}"]},
            }
            for name in "ABCDE"
        ],
    }


def test_resume_after_b_runs_c_d_e_a_b_then_stops():
    plan = build_full_routine_plan(_routine(), resume_index=2)
    assert [step.scenario for step in plan.steps] == ["C", "D", "E", "A", "B"]
    assert [step.scenario for step in plan.official_steps] == list("ABCDE")
    assert plan.start_boundary == 2
    assert len(plan.steps) == 5


def test_partial_scenario_restarts_full_requirement():
    plan = build_full_routine_plan(_routine(), resume_index=2)
    assert plan.steps[0].scenario == "C"
    assert plan.steps[0].required_runs == 7
    assert plan.initial_confirmed_runs == 0


def test_completed_wrapped_cycle_resets_next_session_to_a():
    assert next_full_routine_resume(2, step_count=5, completed_cycle=True) == 0


def test_unfinished_cycle_keeps_first_unfinished_boundary():
    assert next_full_routine_resume(2, step_count=5, completed_cycle=False) == 2


def test_resume_boundary_wraps_safely():
    plan = build_full_routine_plan(_routine(), resume_index=7)
    assert [step.scenario for step in plan.steps] == ["C", "D", "E", "A", "B"]
    assert plan.start_boundary == 2
