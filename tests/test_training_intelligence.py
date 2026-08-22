import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta

from core.recommender import generate_quick_scenario
from core.training_intelligence import (
    build_adaptive_schedule, build_scenario_signals, build_skill_intelligence,
    detect_fatigue, plan_benchmark_checks,
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
        self.db = Database(":memory:")
        self.profile = make_profile()

    def tearDown(self):
        self.db.close()

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


if __name__ == "__main__":
    unittest.main()
