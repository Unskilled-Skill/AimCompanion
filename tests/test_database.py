import os
import tempfile
import unittest
from datetime import datetime, timedelta

from models.database import Database
from models.score import Score


class DatabaseActivityTests(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        self.db = Database(self.path)

    def tearDown(self):
        self.db.close()
        os.unlink(self.path)

    def test_quick_completion_is_also_a_training_session(self):
        self.db.record_scenario_completion(
            "Test Scenario", runs=3, duration_minutes=4,
            focus="Tracking / Reactive", source="quick_tracked",
        )

        sessions = self.db.get_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["scenario"], "Test Scenario")
        self.assertEqual(sessions[0]["runs"], 3)
        self.assertEqual(sessions[0]["duration_minutes"], 4)
        self.assertEqual(sessions[0]["source"], "quick_tracked")
        self.assertEqual(self.db.get_total_training_minutes(), 4)
        self.assertEqual(self.db.get_streak(), 1)

    def test_streak_uses_consecutive_activity_days(self):
        now = datetime.now()
        for offset in (0, 1, 2):
            self.db.log_session(
                "Balanced", 10,
                timestamp=(now - timedelta(days=offset)).isoformat(),
            )

        self.assertEqual(self.db.get_streak(), 3)

    def test_future_activity_does_not_start_a_streak(self):
        future = datetime.now() + timedelta(days=2)
        self.db.log_session("Balanced", 10, timestamp=future.isoformat())

        self.assertEqual(self.db.get_streak(), 0)

    def test_all_scores_returns_every_attempt(self):
        now = datetime.now()
        for index, value in enumerate((100, 110, 105)):
            self.db.insert_score(Score(
                benchmark_name="Test Scenario", scenario="Test Scenario",
                category="Tracking", subcategory="Reactive", difficulty="Novice",
                score=value, timestamp=now + timedelta(seconds=index),
            ), f"attempt-{index}.csv")

        scores = self.db.get_all_scores()

        self.assertEqual([score.score for score in scores], [105, 110, 100])

    def test_unlimited_session_query_returns_full_history(self):
        for index in range(4):
            self.db.log_session("Balanced", 10, timestamp=f"2026-01-0{index + 1}T12:00:00")

        self.assertEqual(len(self.db.get_sessions(limit=2)), 2)
        self.assertEqual(len(self.db.get_sessions(limit=None)), 4)

    def test_file_tracking_is_independent_from_score_rows(self):
        self.db.mark_score_path_imported("duplicate.csv")

        self.assertIn("duplicate.csv", self.db.get_imported_score_paths())
        self.assertFalse(self.db.score_exists("duplicate.csv"))

    def test_file_database_enables_concurrent_access_pragmas(self):
        journal_mode = self.db.conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = self.db.conn.execute("PRAGMA busy_timeout").fetchone()[0]

        self.assertEqual(journal_mode.lower(), "wal")
        self.assertGreaterEqual(busy_timeout, 10_000)

    def test_training_effectiveness_compares_recent_runs_to_baseline(self):
        now = datetime.now()
        for index, value in enumerate((90, 100, 110, 100, 100, 110, 120)):
            score = Score(
                benchmark_name="Test Scenario", scenario="Test Scenario",
                category="Tracking", subcategory="Reactive", difficulty="Novice",
                score=value, timestamp=now + timedelta(seconds=index),
            )
            self.db.insert_score(score, f"score-{index}.csv")
        self.db.record_scenario_completion("Test Scenario", runs=2)

        result = self.db.get_recent_effectiveness(1)[0]
        self.assertAlmostEqual(result["baseline_score"], 100)
        self.assertAlmostEqual(result["outcome_score"], 115)
        self.assertAlmostEqual(result["score_delta_pct"], 15)

    def test_effectiveness_waits_for_three_baseline_runs(self):
        now = datetime.now()
        for index, value in enumerate((100, 110, 120)):
            score = Score(
                benchmark_name="New Scenario", scenario="New Scenario",
                category="Clicking", subcategory="Static", difficulty="Novice",
                score=value, timestamp=now + timedelta(seconds=index),
            )
            self.db.insert_score(score, f"new-score-{index}.csv")
        self.db.record_scenario_completion("New Scenario", runs=2)
        result = self.db.get_recent_effectiveness(1)[0]
        self.assertIsNone(result["baseline_score"])
        self.assertIsNone(result["score_delta_pct"])

    def test_game_observation_inbox_persists_and_resolves(self):
        observation_id = self.db.record_game_observation(
            "Valorant & Counterstrike", "Clicking", "Static",
            "overflicking", "Wide-angle fights",
        )
        open_items = self.db.get_open_game_observations()
        self.assertEqual(len(open_items), 1)
        self.assertEqual(open_items[0]["id"], observation_id)
        by_skill = self.db.get_latest_observation_by_skill()
        self.assertEqual(
            by_skill["clicking / static"]["notes"], "Wide-angle fights"
        )
        self.db.resolve_game_observation(observation_id)
        self.assertEqual(self.db.get_open_game_observations(), [])

    def test_database_backup_can_be_restored(self):
        self.db.log_session("Balanced", 20, "before backup")
        backup_path = self.path + ".backup"
        try:
            self.db.backup_to(backup_path)
            self.db.log_session("Tracking", 10, "after backup")
            self.assertEqual(self.db.get_total_sessions(), 2)
            self.db.restore_from(backup_path)
            self.assertEqual(self.db.get_total_sessions(), 1)
        finally:
            if os.path.exists(backup_path):
                os.unlink(backup_path)

    def test_existing_sessions_schema_is_migrated(self):
        self.db.close()
        os.unlink(self.path)
        import sqlite3
        connection = sqlite3.connect(self.path)
        connection.execute("""
            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 0,
                focus TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                routine_json TEXT DEFAULT '[]'
            )
        """)
        connection.commit()
        connection.close()

        self.db = Database(self.path)
        columns = {
            row["name"]
            for row in self.db.conn.execute("PRAGMA table_info(sessions)")
        }
        self.assertTrue({
            "source", "scenario", "runs", "warmup", "baseline_score",
            "outcome_score", "score_delta_pct",
        } <= columns)


if __name__ == "__main__":
    unittest.main()
