import os
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from core.recommender import generate_quick_scenario
from core.training_intelligence import (
    build_adaptive_schedule, build_scenario_signals, build_skill_intelligence,
    build_weekly_plan, detect_fatigue, plan_benchmark_checks,
)
from models.config import TrainingConfig
from models.database import Database
from models.score import (
    BenchmarkInfo, CategoryScore, PlayerProfile, Score, SubcategoryScore,
)


def make_profile():
    structure = {
        "Clicking": ("Static", "Dynamic", "Linear"),
        "Tracking": ("Precise", "Reactive", "Control"),
        "Switching": ("Speed", "Evasive", "Stability"),
    }
    energy = 100.0
    categories = []
    for category, subcategories in structure.items():
        skill_rows = []
        for subcategory in subcategories:
            skill_rows.append(SubcategoryScore(
                name=subcategory,
                category=category,
                benchmarks=[BenchmarkInfo(
                    name=f"Test {category} {subcategory}",
                    scenario=f"Test {category} {subcategory}",
                    category=category,
                    subcategory=subcategory,
                    difficulty="Novice",
                    best_score=5000,
                )],
                energy=energy,
                tier="Iron",
            ))
            energy += 25
        categories.append(CategoryScore(category, skill_rows))
    return PlayerProfile(
        difficulty="Novice", categories=categories,
        overall_energy=200, overall_tier="Silver",
    )


def add_score(db, benchmark, scenario, value, timestamp, category="Clicking", subcategory="Static"):
    db.insert_score(Score(
        benchmark_name=benchmark,
        scenario=scenario,
        category=category,
        subcategory=subcategory,
        difficulty="Novice",
        score=value,
        timestamp=timestamp,
    ), csv_path=f"{scenario}-{timestamp.isoformat()}-{value}")


class TrainingIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.config_save_patcher = patch("models.config.TrainingConfig.save")
        self.config_save_patcher.start()
        self.db = Database(":memory:")
        self.profile = make_profile()

    def tearDown(self):
        self.db.close()
        self.config_save_patcher.stop()

    def test_unmeasured_skills_are_low_confidence_and_planned_for_checks(self):
        skills = build_skill_intelligence(self.profile, self.db)
        self.assertEqual(len(skills), 9)
        self.assertTrue(all(skill["confidence"] == "low" for skill in skills))
        checks = plan_benchmark_checks(skills, limit=3)
        self.assertEqual(len(checks), 3)
        self.assertTrue(all(check["reason"] == "Unmeasured benchmark" for check in checks))

    def test_existing_feedback_database_is_migrated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "legacy.db")
            connection = sqlite3.connect(path)
            connection.execute("""
                CREATE TABLE block_feedback (
                    id INTEGER PRIMARY KEY, timestamp TEXT, scenario TEXT,
                    rating TEXT, notes TEXT
                )
            """)
            connection.commit()
            connection.close()
            migrated = Database(path)
            columns = {
                row["name"]
                for row in migrated.conn.execute("PRAGMA table_info(block_feedback)")
            }
            migrated.close()
            self.assertIn("category", columns)
            self.assertIn("subcategory", columns)

    def test_latest_review_issue_is_carried_into_skill_intelligence(self):
        self.db.record_block_feedback(
            "Static Practice", "productive", notes="overflicking",
            category="Clicking", subcategory="Static",
        )
        skills = build_skill_intelligence(self.profile, self.db)
        static = next(
            skill for skill in skills
            if skill["category"] == "Clicking" and skill["subcategory"] == "Static"
        )
        self.assertEqual(static["latest_issue"], "overflicking")

    def test_adaptive_pick_uses_latest_review_as_its_correction_cue(self):
        self.db.record_block_feedback(
            "Static Practice", "productive", notes="overflicking",
            category="Clicking", subcategory="Static",
        )
        skills = build_skill_intelligence(self.profile, self.db)
        static = next(
            skill for skill in skills
            if skill["category"] == "Clicking" and skill["subcategory"] == "Static"
        )
        recommendation = generate_quick_scenario(
            self.profile, training_schedule=[static],
            config=TrainingConfig(kovaaks_install_dir="Z:/missing"),
        )
        self.assertEqual(recommendation["focus_issue"], "overflicking")
        self.assertIn("stop just short", recommendation["coaching_cue"])

    def test_game_observation_prioritizes_skill_and_closes_after_resolution(self):
        observation_id = self.db.record_game_observation(
            "Apex Legends", "Tracking", "Reactive", "predicting",
            "Guessed close-range direction changes",
        )
        skills = build_skill_intelligence(self.profile, self.db)
        reactive = next(
            skill for skill in skills
            if skill["category"] == "Tracking" and skill["subcategory"] == "Reactive"
        )
        self.assertEqual(reactive["observation_id"], observation_id)
        self.assertEqual(reactive["latest_issue"], "predicting")
        self.assertEqual(reactive["observed_game"], "Apex Legends")
        recommendation = generate_quick_scenario(
            self.profile, training_schedule=[reactive],
            config=TrainingConfig(kovaaks_install_dir="Z:/missing"),
        )
        self.assertEqual(recommendation["observation_id"], observation_id)
        self.assertIn("Apex Legends review", recommendation["reason"])
        self.assertIn("do not guess", recommendation["coaching_cue"])
        self.db.resolve_game_observation(observation_id)
        refreshed = build_skill_intelligence(self.profile, self.db)
        reactive = next(
            skill for skill in refreshed
            if skill["category"] == "Tracking" and skill["subcategory"] == "Reactive"
        )
        self.assertIsNone(reactive["observation_id"])

    def test_weekly_plan_counts_activity_and_applies_twenty_percent_budget(self):
        now = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
        self.db.log_session(
            "Clicking / Static", 12,
            timestamp=now.replace(hour=10).isoformat(),
        )
        self.db.log_session(
            "balanced", 8,
            timestamp=now.replace(hour=11).isoformat(),
        )
        add_score(
            self.db, "Test Clicking Static", "Test Clicking Static", 5000,
            now.replace(hour=12),
        )
        plan = build_weekly_plan(self.db, 120, now=now)
        self.assertEqual(plan["weakness_days"], 1)
        self.assertEqual(plan["game_days"], 1)
        self.assertEqual(plan["benchmark_days"], 1)
        self.assertEqual(plan["aim_cap_minutes"], 24)
        self.assertEqual(plan["used_minutes"], 20)
        self.assertEqual(plan["remaining_minutes"], 4)

    def test_schedule_weights_weakness_but_keeps_all_nine_skills(self):
        skills = []
        categories = ("Clicking", "Tracking", "Switching")
        for index in range(9):
            skills.append({
                "key": f"skill-{index}",
                "category": categories[index // 3],
                "subcategory": f"Sub {index}",
                "priority": 1.0 if index == 0 else 0.1,
                "confidence": "high",
                "weakness_severity": 0.5 if index == 0 else 0.0,
                "training_age_days": 0,
            })
        schedule = build_adaptive_schedule(skills)
        counts = {skill["key"]: 0 for skill in skills}
        for skill in schedule:
            counts[skill["key"]] += 1
        self.assertTrue(all(count >= 1 for count in counts.values()))
        self.assertEqual(counts["skill-0"], 3)

    def test_feedback_changes_skill_progression_and_scenario_signal(self):
        self.db.record_block_feedback(
            "Some Static Scenario", "too_easy",
            category="Clicking", subcategory="Static",
        )
        skills = build_skill_intelligence(self.profile, self.db)
        static = next(skill for skill in skills if skill["key"] == "Clicking_Static")
        self.assertEqual(static["progression"], "advance")
        self.db.record_block_feedback(
            "Some Static Scenario", "too_hard",
            category="Clicking", subcategory="Static",
        )
        static = next(
            skill for skill in build_skill_intelligence(self.profile, self.db)
            if skill["key"] == "Clicking_Static"
        )
        self.assertEqual(static["progression"], "regress")

        self.db.record_block_feedback("Painful Scenario", "discomfort")
        start = datetime.now() - timedelta(minutes=8)
        for index, value in enumerate((100, 100, 100, 100, 100, 110, 110, 110)):
            add_score(
                self.db, "Effective benchmark", "Effective scenario", value,
                start + timedelta(minutes=index),
            )
        self.db.record_scenario_completion("Effective scenario", runs=3)
        signals = build_scenario_signals(self.db)
        self.assertLess(signals["painful scenario"]["adjustment"], -50)
        self.assertGreater(signals["effective scenario"]["adjustment"], 0)
        self.assertAlmostEqual(
            signals["effective scenario"]["average_delta_pct"], 10.0
        )

    def test_fatigue_detects_sustained_drop_not_one_bad_run(self):
        start = datetime.now() - timedelta(minutes=8)
        for index, value in enumerate((100, 100, 100, 100, 100, 80, 80, 80)):
            add_score(
                self.db, "Fatigue benchmark", "Fatigue scenario", value,
                start + timedelta(minutes=index),
            )
        fatigue = detect_fatigue(self.db)
        self.assertIsNotNone(fatigue)
        self.assertAlmostEqual(fatigue["drop_pct"], -20.0)

    def test_confident_trend_advances_and_exposes_next_rank_targets(self):
        benchmark = "Test Clicking Static"
        start = datetime.now() - timedelta(days=5)
        for index, value in enumerate((5000, 5100, 5200, 6000, 6200, 6400)):
            add_score(
                self.db, benchmark, benchmark, value,
                start + timedelta(days=index),
            )
        skill = next(
            item for item in build_skill_intelligence(self.profile, self.db)
            if item["key"] == "Clicking_Static"
        )
        self.assertEqual(skill["confidence"], "high")
        self.assertEqual(skill["progression"], "advance")
        self.assertGreater(skill["target_scores"][benchmark], 0)

    def test_adaptive_target_and_scenario_effectiveness_feed_recommender(self):
        schedule = [{
            "key": "Tracking_Precise", "category": "Tracking",
            "subcategory": "Precise", "tier": "Iron", "progression": "hold",
            "benchmark_due": False, "weakness_severity": 0.4,
        }]
        config = TrainingConfig(
            session_minutes=30, warmup_minutes=5, cooldown_minutes=5,
            focus="balanced", prioritize_installed=False, variety_seed=1,
            kovaaks_install_dir="Z:/missing",
        )
        first = generate_quick_scenario(
            self.profile, config=config, training_schedule=schedule,
        )
        second = generate_quick_scenario(
            self.profile, config=config, training_schedule=schedule,
            scenario_signals={first["scenario"].casefold(): {"adjustment": -100}},
        )
        self.assertEqual(first["category"], "Tracking")
        self.assertEqual(first["subcategory"], "Precise")
        self.assertEqual(first["selection_basis"], "adaptive weakness")
        self.assertNotEqual(first["scenario"], second["scenario"])

    def test_skill_matrix_widget_renders_all_nine_rows(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication, QFrame
        from ui.skill_overview import SkillOverviewWidget

        app = QApplication.instance() or QApplication([])
        widget = SkillOverviewWidget(self.profile, self.db)
        cards = [
            item for item in widget.findChildren(QFrame)
            if item.objectName() == "skillCard"
        ]
        self.assertEqual(len(cards), 9)
        widget.deleteLater()
        app.processEvents()

    def test_home_primary_action_starts_training_without_an_extra_page(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication, QPushButton
        from ui.dashboard import DashboardWidget

        app = QApplication.instance() or QApplication([])
        widget = DashboardWidget(self.profile)
        requested = []
        widget.quick_training_requested.connect(lambda: requested.append(True))
        button = next(
            item for item in widget.findChildren(QPushButton)
            if item.text().startswith("Start a")
        )
        button.click()
        app.processEvents()
        self.assertEqual(requested, [True])
        widget.deleteLater()

    def test_today_page_leads_with_recommendation_and_hides_advanced_controls(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        from ui.routines import RoutineWidget

        app = QApplication.instance() or QApplication([])
        widget = RoutineWidget(self.profile, self.db)

        self.assertIs(
            widget.content_layout.itemAt(0).widget(), widget.mode_selector_frame
        )
        self.assertTrue(widget.mode_buttons["focused"].isChecked())
        self.assertEqual(widget.method_combo.currentData(), "adaptive_weakness")
        self.assertEqual(widget.config.preferred_routine, "")
        self.assertTrue(widget.observation_form.isHidden())
        self.assertTrue(widget.fps_budget_spin.isHidden())
        self.assertTrue(widget.warmup_context_combo.isHidden())

        widget.deleteLater()
        app.processEvents()

    def test_today_training_modes_show_only_their_workflow(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        from ui.routines import RoutineWidget

        app = QApplication.instance() or QApplication([])
        widget = RoutineWidget(self.profile, self.db)

        widget._set_training_mode("deathmatch")
        self.assertFalse(widget.deathmatch_mode_frame.isHidden())
        self.assertTrue(widget.routine_frame.isHidden())
        self.assertTrue(widget.quick_actions_frame.isHidden())
        self.assertEqual(widget.config.training_mode, "deathmatch")

        widget._set_training_mode("routine")
        self.assertFalse(widget.routine_frame.isHidden())
        self.assertTrue(widget.settings_frame.isHidden())
        self.assertTrue(widget.quick_actions_frame.isHidden())
        widget.advanced_settings_toggle.setChecked(True)
        self.assertFalse(widget.settings_frame.isHidden())

        widget._set_training_mode("focused")
        self.assertFalse(widget.routine_frame.isHidden())
        self.assertFalse(widget.quick_actions_frame.isHidden())
        self.assertTrue(widget.settings_frame.isHidden())

        widget.deleteLater()
        app.processEvents()

    def test_training_method_builds_exact_source_routine(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtWidgets import QApplication
        from ui.routines import RoutineWidget

        app = QApplication.instance() or QApplication([])
        widget = RoutineWidget(self.profile, self.db)
        widget.select_training_method("smooth_pathing")

        self.assertEqual(widget.training_mode, "routine")
        self.assertEqual(widget.method_combo.currentData(), "smooth_pathing")
        self.assertEqual(
            widget.config.preferred_routine,
            "hnA TacFPS Routine - Smooth Pathing",
        )
        widget.start_method_button.click()
        self.assertEqual(
            widget._current_routine["source_routine"],
            "hnA TacFPS Routine - Smooth Pathing",
        )
        self.assertTrue(widget._current_routine["authored_run_plan"])
        self.assertEqual(widget._current_routine["warmup_minutes"], 0)
        self.assertEqual(widget._current_routine["cooldown_minutes"], 0)
        self.assertEqual(
            [exercise["prescribed_runs"] for exercise in widget._current_routine["exercises"]],
            [10, 5, 5, 5, 5, 5],
        )
        self.assertTrue(widget._current_routine["source_guidance"])
        self.assertTrue(
            all(
                exercise.get("authored_instruction")
                and exercise.get("description")
                for exercise in widget._current_routine["exercises"]
            )
        )

        widget.select_training_method("deathmatch_accuracy")
        self.assertEqual(
            widget.deathmatch_mode_widget.active_block_ids,
            {"sheriff_accuracy_1", "sheriff_accuracy_2"},
        )
        widget.deleteLater()
        app.processEvents()

    def test_full_routine_export_uses_kovaaks_playlist_fields(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from unittest.mock import patch
        from PyQt6.QtWidgets import QApplication
        from ui.routines import RoutineWidget

        app = QApplication.instance() or QApplication([])
        widget = RoutineWidget(self.profile, self.db)
        widget._current_routine = {
            "training_minutes": 6,
            "warmup_scenarios": [],
            "exercises": [{"scenario": "1w3ts", "duration_min": 6}],
        }
        with tempfile.TemporaryDirectory() as directory, patch(
            "ui.routines.KOVAAKS_PLAYLIST_DIR", directory
        ), patch("ui.routines.QMessageBox.information"):
            widget._export()
            path = os.path.join(directory, "VT Routine - 6min.json")
            with open(path, encoding="utf-8") as file:
                playlist = json.load(file)

        self.assertEqual(
            playlist["scenarioList"],
            [{"scenarioName": "1w3ts", "playCount": 2}],
        )
        widget.deleteLater()
        app.processEvents()

    def test_hna_export_preserves_authored_run_counts(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from unittest.mock import patch
        from PyQt6.QtWidgets import QApplication
        from ui.routines import RoutineWidget

        app = QApplication.instance() or QApplication([])
        widget = RoutineWidget(self.profile, self.db)
        widget.select_training_method("speed_stopping")
        widget.start_method_button.click()

        with tempfile.TemporaryDirectory() as directory, patch(
            "ui.routines.KOVAAKS_PLAYLIST_DIR", directory
        ), patch("ui.routines.QMessageBox.information"):
            widget._export()
            path = os.path.join(directory, "hnA TacFPS 1 - Speed and Stopping.json")
            with open(path, encoding="utf-8") as file:
                playlist = json.load(file)

        self.assertEqual(
            [item["playCount"] for item in playlist["scenarioList"]],
            [7, 5, 3, 5, 5, 5, 5],
        )
        widget.deleteLater()
        app.processEvents()

    def test_different_pick_does_not_launch_before_confirmation(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from unittest.mock import patch
        from PyQt6.QtWidgets import QApplication, QPushButton
        from ui.routines import RoutineWidget

        app = QApplication.instance() or QApplication([])
        widget = RoutineWidget(self.profile, self.db)
        different_pick = next(
            button for button in widget.routine_frame.findChildren(QPushButton)
            if button.text() == "Different pick"
        )

        with patch("ui.routines.open_kovaaks_scenario") as launch:
            different_pick.click()
            app.processEvents()

        launch.assert_not_called()
        widget.deleteLater()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
