import unittest
from unittest.mock import patch
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from core.recommender import (
    AIM_GLOSSARY, GAME_WARMUP_TARGETS, GUIDANCE, ROUTINES, SCENARIOS,
    generate_routine, get_game_options, get_training_guidance,
    generate_quick_scenario, get_scenario_info,
)
from models.config import (
    TrainingConfig, build_routine, _detect_kovaaks_stats, score_scenario,
    get_warmup_scenarios, _scenario_difficulty,
)
from models.database import Database
from models.score import BenchmarkInfo, CategoryScore, PlayerProfile, SubcategoryScore
from core.kovaaks_launcher import game_deep_link, scenario_deep_link
from core.run_tracker import KovaaksRunTracker
from core.scenario_duration import quick_block_plan, scenario_duration_seconds
from core.scenario_files import (
    find_scenario_file, installed_scenario_names, scenario_search_dirs,
)
from core.warmups import GAME_WARMUP_ROUTINES, RECOMMENDED_WARMUP_ROUTINE


def make_profile(measured=True):
    structure = {
        "Clicking": ("Static", "Dynamic", "Linear"),
        "Tracking": ("Precise", "Reactive", "Control"),
        "Switching": ("Speed", "Evasive", "Stability"),
    }
    energy = 100.0
    categories = []
    for category_name, subcategory_names in structure.items():
        subcategories = []
        for subcategory_name in subcategory_names:
            benchmark = BenchmarkInfo(
                name=f"Test {category_name} {subcategory_name}",
                scenario="Test",
                category=category_name,
                subcategory=subcategory_name,
                difficulty="Novice",
                best_score=1.0 if measured else 0.0,
            )
            subcategories.append(SubcategoryScore(
                name=subcategory_name,
                category=category_name,
                benchmarks=[benchmark],
                energy=energy,
                tier="Iron",
            ))
            energy += 25.0
        categories.append(CategoryScore(category_name, subcategories))
    return PlayerProfile(
        difficulty="Novice",
        categories=categories,
        overall_energy=200.0,
        overall_tier="Silver",
    )


def make_config(**overrides):
    values = dict(
        session_minutes=30,
        warmup_minutes=5,
        cooldown_minutes=5,
        focus="balanced",
        prioritize_installed=False,
        variety_seed=123,
        kovaaks_install_dir="Z:/path-that-does-not-exist",
    )
    values.update(overrides)
    return TrainingConfig(**values)


class RecommenderTests(unittest.TestCase):
    def test_quick_blocks_respect_long_scenario_durations(self):
        air = quick_block_plan("Air Angelic Dodge")
        self.assertEqual(air["scenario_seconds"], 300)
        self.assertEqual(air["runs"], 1)
        self.assertEqual(air["estimated_minutes"], 5)

        named = quick_block_plan("Tracking challenge - 5 minutes")
        self.assertEqual(named["runs"], 1)
        self.assertEqual(named["estimated_minutes"], 5)

    def test_installed_scenario_timelimit_is_used_for_quick_block(self):
        with tempfile.TemporaryDirectory() as scenarios_dir:
            path = os.path.join(scenarios_dir, "Custom Track.sce")
            with open(path, "w", encoding="utf-8") as file:
                file.write("Name=Custom Track\nTimelimit=90.0\n")
            seconds, source = scenario_duration_seconds(
                "custom track", scenarios_dir
            )
            plan = quick_block_plan("custom track", scenarios_dir)
            self.assertEqual((seconds, source), (90, "scenario file"))
            self.assertEqual(plan["runs"], 2)
            self.assertEqual(plan["estimated_minutes"], 3)

    def test_two_minute_scenario_becomes_a_four_minute_micro_block(self):
        with tempfile.TemporaryDirectory() as scenarios_dir:
            path = os.path.join(scenarios_dir, "Two Minute Track.sce")
            with open(path, "w", encoding="utf-8") as file:
                file.write("Name=Two Minute Track\nTimelimit=120.0\n")
            plan = quick_block_plan("Two Minute Track", scenarios_dir)
            self.assertEqual(plan["runs"], 2)
            self.assertEqual(plan["estimated_minutes"], 4)

    def test_workshop_scenario_is_detected_and_timed(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            steamapps_dir = os.path.join(temporary_dir, "steamapps")
            local_dir = os.path.join(
                steamapps_dir, "common", "FPSAimTrainer", "FPSAimTrainer",
                "Saved", "SaveGames", "Scenarios",
            )
            workshop_dir = os.path.join(
                steamapps_dir, "workshop", "content", "824270", "123456"
            )
            os.makedirs(local_dir)
            os.makedirs(workshop_dir)
            workshop_file = os.path.join(workshop_dir, "Workshop Track.sce")
            with open(workshop_file, "w", encoding="utf-8") as file:
                file.write("Name=Workshop Track\nTimelimit=120.0\n")

            directories = scenario_search_dirs(local_dir)
            self.assertEqual(
                find_scenario_file("workshop track", directories), workshop_file
            )
            self.assertIn("workshop track", installed_scenario_names(directories))
            plan = quick_block_plan("Workshop Track", directories)
            self.assertEqual(plan["scenario_seconds"], 120)
            self.assertEqual(plan["runs"], 2)
            self.assertEqual(plan["estimated_minutes"], 4)
            self.assertEqual(plan["duration_source"], "scenario file")

    def test_online_scenario_duration_is_learned_from_result_csv(self):
        with tempfile.TemporaryDirectory() as stats_dir:
            path = os.path.join(
                stats_dir,
                "Long Online Track - Challenge - 2026.08.20-10.05.00 Stats.csv",
            )
            with open(path, "w", encoding="utf-8") as file:
                file.write(
                    "Score:,100\nScenario:,Long Online Track\n"
                    "Challenge Start:,10:00:00.000\nPause Duration:,0\n"
                )
            seconds, source = scenario_duration_seconds(
                "Long Online Track", stats_dir=stats_dir
            )
            plan = quick_block_plan("Long Online Track", stats_dir=stats_dir)
            self.assertEqual((seconds, source), (300, "recent result"))
            self.assertEqual(plan["runs"], 1)

    def test_installed_status_is_only_a_small_tiebreaker(self):
        scenario = {
            "name": "Example Scenario",
            "category": "Tracking",
            "subcategory": "Precise",
            "difficulty": "Novice",
            "official_recommended": True,
        }
        base = score_scenario(
            scenario, [], "Silver", {"example scenario"}, "balanced", False
        )
        preferred = score_scenario(
            scenario, [], "Silver", {"example scenario"}, "balanced", True
        )
        self.assertEqual(preferred - base, 1.0)

    def test_kovaaks_stats_folder_is_resolved_outside_savegames(self):
        savegames = os.path.join(
            "G:", "SteamLibrary", "steamapps", "common", "FPSAimTrainer",
            "FPSAimTrainer", "Saved", "SaveGames",
        )
        expected = os.path.join(
            "G:", "SteamLibrary", "steamapps", "common", "FPSAimTrainer",
            "FPSAimTrainer", "stats",
        )
        self.assertEqual(_detect_kovaaks_stats(savegames), expected)

    def test_live_tracker_counts_only_new_matching_kovaaks_runs(self):
        with tempfile.TemporaryDirectory() as stats_dir:
            old_path = os.path.join(
                stats_dir,
                "Smoothbot Voltaic - Challenge - 2026.08.20-10.00.00 Stats.csv",
            )
            with open(old_path, "w", encoding="utf-8") as file:
                file.write("Score: , 100\n")
            tracker = KovaaksRunTracker(stats_dir)
            tracker.start("Smoothbot Voltaic", target_runs=3)

            other_path = os.path.join(
                stats_dir,
                "Other Scenario - Challenge - 2026.08.20-10.01.00 Stats.csv",
            )
            with open(other_path, "w", encoding="utf-8") as file:
                file.write("Score: , 200\n")
            matching_path = os.path.join(
                stats_dir,
                "Smoothbot Voltaic - Challenge - 2026.08.20-10.02.00 Stats.csv",
            )
            with open(matching_path, "w", encoding="utf-8") as file:
                file.write("Score: , 300\n")

            self.assertEqual(len(tracker.poll()), 1)
            self.assertEqual(tracker.completed_runs, 1)
            self.assertEqual(tracker.poll(), [])

    def test_scenario_completion_history_counts_blocks_runs_and_warmups(self):
        db = Database(":memory:")
        self.assertEqual(
            db.get_scenario_completion("Smoothbot Voltaic")["completed_blocks"], 0
        )
        db.record_scenario_completion("Smoothbot Voltaic", runs=3, warmup=True)
        totals = db.record_scenario_completion(
            "smoothbot voltaic", runs=3, warmup=False
        )
        self.assertEqual(totals["completed_blocks"], 2)
        self.assertEqual(totals["completed_runs"], 6)
        self.assertEqual(totals["warmup_blocks"], 1)
        db.close()

    def test_scenario_attempt_count_uses_imported_kovaaks_results(self):
        db = Database(":memory:")
        from models.score import Score
        db.insert_score(Score(
            benchmark_name="Revolving Tracking",
            scenario="Revolving Tracking",
            category="Tracking",
            subcategory="Control",
            difficulty="Unknown",
            score=100,
            timestamp=datetime.now(),
        ), "result-1.csv")
        self.assertEqual(db.get_scenario_attempt_count("revolving tracking"), 1)
        db.close()

    def test_kovaaks_deep_links_use_correct_app_and_encode_scenario(self):
        self.assertEqual(game_deep_link(), "steam://rungameid/824270")
        self.assertEqual(
            scenario_deep_link("Gravity Strafes a+"),
            "steam://run/824270/?action=jump-to-scenario;name=Gravity%20Strafes%20a%2B",
        )

    def test_offline_guidance_covers_sources_and_every_s5_skill(self):
        expected = {
            "Clicking_Static", "Clicking_Dynamic", "Clicking_Linear",
            "Tracking_Precise", "Tracking_Reactive", "Tracking_Control",
            "Switching_Speed", "Switching_Evasive", "Switching_Stability",
        }
        self.assertEqual(set(GUIDANCE["categories"]), expected)
        self.assertEqual(len(GUIDANCE["sources"]), 7)
        self.assertTrue(all(source["url"].startswith("https://") for source in GUIDANCE["sources"]))
        for key in expected:
            category, subcategory = key.split("_", 1)
            item = get_training_guidance(category, subcategory)
            self.assertTrue(item["goal"])
            self.assertTrue(item["cue"])
            self.assertTrue(item["avoid"])
            self.assertTrue(item["progress"])
        self.assertGreaterEqual(len(AIM_GLOSSARY["terms"]), 30)
        self.assertIn("Deliberate practice", AIM_GLOSSARY["terms"])
        self.assertIn("learning_zone", GUIDANCE["mindset"])
        self.assertEqual(len(GUIDANCE["mindset"]["reflection_prompt"]), 3)

    def test_all_supplied_voltaic_sources_are_indexed(self):
        scenario_data = json.loads(
            (Path(__file__).parents[1] / "data" / "recommended_scenarios.json").read_text(
                encoding="utf-8"
            )
        )
        scenario_count = sum(
            len(category["scenarios"])
            for category in scenario_data["categories"].values()
        )
        self.assertGreaterEqual(scenario_count, 200)
        self.assertEqual(
            {routine["kind"] for routine in ROUTINES},
            {"game", "issue", "fundamentals"},
        )
        self.assertGreaterEqual(len(ROUTINES), 44)
        self.assertTrue(all(routine["share_code"] for routine in ROUTINES))

    def test_catalog_covers_every_benchmark_subcategory(self):
        expected = {
            ("Clicking", "Static"), ("Clicking", "Dynamic"),
            ("Clicking", "Linear"), ("Tracking", "Precise"),
            ("Tracking", "Reactive"), ("Tracking", "Control"),
            ("Switching", "Speed"), ("Switching", "Evasive"),
            ("Switching", "Stability"),
        }
        actual = {
            tuple(target.split("_", 1))
            for scenario in SCENARIOS
            for target in scenario.get(
                "recommendation_targets",
                [f"{scenario.get('category')}_{scenario.get('subcategory')}"]
            )
        }
        self.assertTrue(expected.issubset(actual))
        self.assertFalse(any(not s.get("category") or not s.get("subcategory") for s in SCENARIOS))

    def test_balanced_mode_allocates_time_across_categories(self):
        routine = build_routine(make_profile(), make_config())
        totals = {}
        for exercise in routine["exercises"]:
            totals[exercise["category"]] = totals.get(exercise["category"], 0) + exercise["duration_min"]
        self.assertEqual(set(totals), {"Clicking", "Tracking", "Switching"})
        self.assertLessEqual(max(totals.values()) - min(totals.values()), 1)
        self.assertEqual(sum(totals.values()), 20)

    def test_category_focus_is_diverse_and_fills_budget(self):
        routine = build_routine(make_profile(), make_config(focus="switching"))
        self.assertEqual(routine["training_minutes"], 20)
        self.assertEqual({e["category"] for e in routine["exercises"]}, {"Switching"})
        # The supplied Voltaic sheet combines Evasive and Stability as
        # Evasive/SmoothTS instead of presenting them as separate buckets.
        self.assertEqual(
            {e["subcategory"] for e in routine["exercises"]},
            {"Speed", "Evasive"},
        )

    def test_unmeasured_profile_uses_balanced_starter(self):
        routine = build_routine(
            make_profile(measured=False), make_config(focus="weakest")
        )
        self.assertFalse(routine["has_measured_weaknesses"])
        self.assertIn("Complete Routine", routine["source_routine"])
        self.assertIn("Balanced starter", routine["focus_label"])
        self.assertEqual(routine["weakness_areas"], [])

    def test_general_balanced_mode_uses_rank_fundamentals(self):
        routine = build_routine(make_profile(), make_config(focus="balanced"))
        self.assertTrue(routine["source_routine"].startswith("Silver —"))
        self.assertIn("Complete Routine", routine["source_routine"])

    def test_every_game_context_can_generate_its_official_routine(self):
        for game in get_game_options()[1:]:
            with self.subTest(game=game):
                routine = build_routine(
                    make_profile(), make_config(focus="balanced", game=game)
                )
                self.assertTrue(routine["source_routine"])
                source = next(
                    item for item in ROUTINES
                    if item["name"] == routine["source_routine"]
                )
                self.assertEqual(source["kind"], "game")
                self.assertEqual(source["group"], game)

    def test_session_budget_is_never_exceeded(self):
        for session, warmup, cooldown in ((15, 15, 15), (15, 10, 10), (16, 15, 0)):
            with self.subTest(session=session, warmup=warmup, cooldown=cooldown):
                routine = build_routine(
                    make_profile(),
                    make_config(
                        session_minutes=session,
                        warmup_minutes=warmup,
                        cooldown_minutes=cooldown,
                    ),
                )
                self.assertEqual(routine["total_minutes"], session)
                self.assertEqual(
                    routine["warmup_minutes"]
                    + routine["training_minutes"]
                    + routine["cooldown_minutes"],
                    session,
                )

    def test_warmup_scenarios_match_declared_warmup(self):
        for minutes in (0, 1, 5, 13):
            with self.subTest(minutes=minutes):
                routine = build_routine(
                    make_profile(),
                    make_config(
                        session_minutes=30,
                        warmup_minutes=minutes,
                        cooldown_minutes=0,
                    ),
                )
                self.assertEqual(
                    sum(item["duration_min"] for item in routine["warmup_scenarios"]),
                    routine["warmup_minutes"],
                )

    def test_recommended_four_step_warmup_is_used_in_order(self):
        routine = build_routine(
            make_profile(),
            make_config(session_minutes=30, warmup_minutes=14, cooldown_minutes=0),
        )
        self.assertEqual(
            [item["scenario"] for item in routine["warmup_scenarios"]],
            [item["scenario"] for item in RECOMMENDED_WARMUP_ROUTINE],
        )
        self.assertEqual(
            [item["duration_min"] for item in routine["warmup_scenarios"]],
            [5, 3, 3, 3],
        )

    def test_apex_and_counterstrike_use_game_specific_warmups(self):
        cases = {
            "Apex Legends": (10, ["fuglaaXYLongstrafes", "CloseLongStrafes"]),
            "Valorant & Counterstrike": (
                10, ["MicroshotSpeed", "1wall5targets_pasu", "TileFrenzyMini"]
            ),
        }
        for context, (minutes, expected) in cases.items():
            with self.subTest(context=context):
                warmup = get_warmup_scenarios(
                    SCENARIOS, set(), total_minutes=minutes, context=context
                )
                self.assertEqual([item["scenario"] for item in warmup], expected)
                self.assertEqual(
                    [item["duration_min"] for item in warmup],
                    [item["duration_min"] for item in GAME_WARMUP_ROUTINES[context]],
                )

    def test_seed_controls_exercises_and_warmup(self):
        first = build_routine(make_profile(), make_config(), day=3)
        second = build_routine(make_profile(), make_config(), day=3)
        self.assertEqual(first["exercises"], second["exercises"])
        self.assertEqual(first["warmup_scenarios"], second["warmup_scenarios"])

    def test_public_options_affect_generation(self):
        defaults = make_config(focus="weakest")
        with patch("core.recommender.TrainingConfig.load", return_value=defaults):
            routine = generate_routine(
                make_profile(), available_minutes=30,
                focus_weakest=False, include_tracking=False, day=4,
            )
        self.assertEqual(routine["focus"], "balanced")
        self.assertNotIn("Tracking", {e["category"] for e in routine["exercises"]})

    def test_premade_routine_has_metadata_and_fills_training_time(self):
        routine = build_routine(make_profile(), make_config(focus="weakest"))
        self.assertEqual(routine["training_minutes"], 20)
        self.assertTrue(routine["source_routine"])
        self.assertTrue(all(e["category"] and e["subcategory"] for e in routine["exercises"]))
        self.assertTrue(routine["theory_summary"])
        self.assertTrue(routine["session_cues"])
        self.assertTrue(routine["progression_guidance"])
        self.assertEqual(len(routine["guidance_sources"]), 7)
        self.assertTrue(all(e["coaching_cue"] for e in routine["exercises"]))
        self.assertEqual(routine["practice_mode"], "Learning Zone")
        self.assertEqual(len(routine["reflection_prompt"]), 3)

    def test_weakest_mode_preserves_balanced_support(self):
        routine = build_routine(make_profile(), make_config(focus="weakest"))
        allocation = routine["focus_allocation"]
        self.assertIsNotNone(allocation)
        self.assertEqual(allocation["primary_minutes"], 13)
        self.assertEqual(allocation["support_minutes"], 7)
        primary_total = sum(
            exercise["duration_min"] for exercise in routine["exercises"]
            if exercise["category"] == allocation["primary_category"]
        )
        support_categories = {
            exercise["category"] for exercise in routine["exercises"]
            if exercise["category"] != allocation["primary_category"]
        }
        self.assertLessEqual(primary_total, 13)
        self.assertEqual(support_categories, {"Tracking", "Switching"})
        self.assertEqual(routine["training_minutes"], 20)

    def test_quick_scenario_rotates_categories_and_never_repeats_recent_pick(self):
        recent = []
        categories = []
        for index in range(4):
            recommendation = generate_quick_scenario(
                make_profile(), recent_names=recent,
                rotation_index=index, config=make_config(),
            )
            self.assertGreaterEqual(recommendation["runs"], 1)
            self.assertLessEqual(recommendation["runs"], 3)
            self.assertNotIn(recommendation["scenario"], recent)
            recent.append(recommendation["scenario"])
            categories.append(recommendation["category"])
        self.assertEqual(set(categories), {"Clicking", "Tracking", "Switching"})
        self.assertEqual(categories.count("Clicking"), 2)

    def test_benchmark_weakness_repeats_without_dropping_other_categories(self):
        recommendations = [
            generate_quick_scenario(
                make_profile(), rotation_index=index, config=make_config()
            )
            for index in range(4)
        ]
        self.assertEqual(
            [item["category"] for item in recommendations],
            ["Clicking", "Tracking", "Clicking", "Switching"],
        )
        self.assertEqual(recommendations[0]["selection_basis"], "benchmark weakness")
        self.assertTrue(all(
            item["selection_basis"] == "skill maintenance"
            for item in recommendations[1:]
        ))

    def test_all_nine_benchmark_subcategories_receive_maintenance(self):
        selected = {
            generate_quick_scenario(
                make_profile(), rotation_index=index, config=make_config()
            )["target_label"]
            for index in range(16)
        }
        self.assertEqual(len(selected), 9)

    def test_game_context_does_not_override_core_micro_progression(self):
        general = [
            generate_quick_scenario(
                make_profile(), rotation_index=index,
                config=make_config(game="General / Fundamentals"),
            )["target_label"]
            for index in range(12)
        ]
        for game in ("Apex Legends", "Valorant & Counterstrike"):
            selected = [
                generate_quick_scenario(
                    make_profile(), rotation_index=index,
                    config=make_config(game=game),
                )["target_label"]
                for index in range(12)
            ]
            self.assertEqual(selected, general)

    def test_micro_pick_authoritatively_matches_its_declared_target(self):
        for game in ["General / Fundamentals", *GAME_WARMUP_TARGETS]:
            recent = []
            for index in range(9):
                recommendation = generate_quick_scenario(
                    make_profile(), recent_names=recent[-3:],
                    rotation_index=index, config=make_config(game=game),
                )
                scenario = get_scenario_info(recommendation["scenario"])
                declared = set(scenario.get("recommendation_targets") or [
                    f"{scenario.get('category')}_{scenario.get('subcategory')}"
                ])
                selected = recommendation["target_label"].replace(" · ", "_")
                self.assertIn(selected, declared)
                recent.append(recommendation["scenario"])

    def test_routine_exercises_do_not_inherit_every_playlist_target(self):
        dynamic = get_scenario_info("1w2t TE Reload")
        pasu = get_scenario_info("1w4t Pasu Raspberry Grandmaster")
        self.assertEqual(dynamic["recommendation_targets"], ["Clicking_Dynamic"])
        self.assertEqual(pasu["recommendation_targets"], ["Clicking_Dynamic"])

    def test_rank_and_size_names_infer_safe_quick_difficulty(self):
        self.assertEqual(
            _scenario_difficulty({"name": "Pasu Grandmaster", "difficulty": "Unknown"}),
            "Advanced",
        )
        self.assertEqual(
            _scenario_difficulty({"name": "Smoothbot Diamond", "difficulty": "Unknown"}),
            "Intermediate",
        )
        self.assertEqual(
            _scenario_difficulty({"name": "Controlsphere Easy", "difficulty": "Unknown"}),
            "Novice",
        )

    def test_target_subcategory_rank_controls_quick_difficulty(self):
        profile = make_profile()
        profile.overall_tier = "Master"
        recommendation = generate_quick_scenario(
            profile, rotation_index=0, config=make_config()
        )
        self.assertEqual(recommendation["target_tier"], "Iron")
        scenario = get_scenario_info(recommendation["scenario"])
        self.assertIn(_scenario_difficulty(scenario), {"Novice", "Unknown"})

    def test_quick_warmup_is_controlled_tracking_for_three_runs(self):
        recommendation = generate_quick_scenario(
            make_profile(), warmup=True, config=make_config()
        )
        self.assertEqual(recommendation["runs"], 3)
        self.assertEqual(recommendation["category"], "Tracking")
        self.assertIn(recommendation["subcategory"], {"Precise", "Control"})

    def test_game_warmups_match_each_games_aiming_demands(self):
        for context, targets in GAME_WARMUP_TARGETS.items():
            with self.subTest(context=context):
                recommendation = generate_quick_scenario(
                    make_profile(), warmup=True, warmup_context=context,
                    config=make_config(),
                )
                compound = (
                    f"{recommendation['category']}_{recommendation['subcategory']}"
                )
                self.assertIn(compound, targets)
                self.assertEqual(recommendation["warmup_context"], context)

    def test_low_sensitivity_mode_avoids_continuous_turn_scenarios(self):
        recent = []
        blocked_hints = ("revolving", "360", "centering i 180")
        for index in range(12):
            recommendation = generate_quick_scenario(
                make_profile(), warmup=True, recent_names=recent,
                rotation_index=index,
                config=make_config(avoid_continuous_turns=True),
            )
            name = recommendation["scenario"].casefold()
            self.assertFalse(any(hint in name for hint in blocked_hints), name)
            recent.append(recommendation["scenario"])


if __name__ == "__main__":
    unittest.main()
