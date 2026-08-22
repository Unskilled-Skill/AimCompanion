import unittest
import tempfile
from datetime import datetime, timedelta

from models.score import Score
from ui.comparison import build_comparison_rows
from ui.dashboard import DashboardWidget
from ui.sensitivity import convert_sensitivity
from ui.routines import prepare_scenario_launch


def score(name, value, day):
    return Score(
        benchmark_name=name,
        scenario=name,
        category="Clicking",
        subcategory="Static",
        difficulty="Novice",
        score=value,
        timestamp=datetime(2026, 8, 1) + timedelta(days=day),
    )


class ToolLogicTests(unittest.TestCase):
    def test_dashboard_next_tier_uses_energy_thresholds(self):
        self.assertEqual(DashboardWidget._next_tier(317.4)["name"], "Gold")

    def test_dashboard_next_tier_stops_after_highest_rank(self):
        self.assertIsNone(DashboardWidget._next_tier(99999))

    def test_comparison_uses_early_and_recent_samples(self):
        rows = build_comparison_rows([
            score("A", 100, 0), score("A", 110, 1), score("A", 120, 2),
            score("A", 130, 3), score("A", 140, 4), score("A", 150, 5),
        ])
        self.assertEqual(rows[0]["early"], 110)
        self.assertEqual(rows[0]["recent"], 140)
        self.assertAlmostEqual(rows[0]["delta_pct"], 27.2727, places=3)

    def test_single_attempt_is_baseline_not_a_false_trend(self):
        row = build_comparison_rows([score("A", 100, 0)])[0]
        self.assertIsNone(row["delta_pct"])

    def test_sensitivity_round_trip_preserves_value(self):
        converted, _ = convert_sensitivity(1600, "Valorant", 0.28, "Kovaak's")
        restored, _ = convert_sensitivity(1600, "Kovaak's", converted, "Valorant")
        self.assertAlmostEqual(restored, 0.28, places=6)

    def test_online_scenario_launch_does_not_require_local_file(self):
        recommendation = {
            "scenario": "MicroshotSpeed",
            "runs": 3,
            "estimated_minutes": 3,
        }
        with tempfile.TemporaryDirectory() as directory:
            path = prepare_scenario_launch(recommendation, [directory], directory)
        self.assertIsNone(path)
        self.assertFalse(recommendation["installed"])
        self.assertEqual(recommendation["runs"], 3)


if __name__ == "__main__":
    unittest.main()
