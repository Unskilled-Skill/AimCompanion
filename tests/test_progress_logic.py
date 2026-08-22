import unittest
from datetime import datetime, timedelta

from ui.progress import next_target_for_score, padded_date_limits


class ProgressLogicTests(unittest.TestCase):
    def test_next_target_uses_official_tier_order(self):
        benchmark = {
            "targets": {"Silver": 745, "Iron": 555, "Gold": 800, "Bronze": 660}
        }
        target, completed = next_target_for_score(benchmark, 700)
        self.assertEqual((target[0], target[1]), ("Silver", 745.0))
        self.assertFalse(completed)

    def test_next_target_reports_highest_target_cleared(self):
        benchmark = {"targets": {"Iron": 555, "Bronze": 660}}
        target, completed = next_target_for_score(benchmark, 700)
        self.assertEqual(target[0], "Bronze")
        self.assertTrue(completed)

    def test_single_date_gets_twelve_hour_padding(self):
        date = datetime(2026, 8, 22, 12, 0)
        start, end = padded_date_limits([date])
        self.assertEqual(start, date - timedelta(hours=12))
        self.assertEqual(end, date + timedelta(hours=12))

    def test_date_range_padding_tracks_real_span(self):
        start = datetime(2026, 8, 1)
        end = datetime(2026, 8, 11)
        lower, upper = padded_date_limits([start, end])
        self.assertEqual(lower, start - timedelta(hours=19, minutes=12))
        self.assertEqual(upper, end + timedelta(hours=19, minutes=12))


if __name__ == "__main__":
    unittest.main()
