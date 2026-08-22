import os
import re

from core.parser import parse_csv_file


def _scenario_key(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().casefold()


class KovaaksRunTracker:
    """Track new Kovaak's result files for one active scenario block."""

    def __init__(self, stats_dir: str):
        self.stats_dir = stats_dir
        self.active_scenario = ""
        self.target_runs = 0
        self.completed_runs = 0
        self._seen_paths: set[str] = set()

    def _csv_paths(self) -> set[str]:
        if not os.path.isdir(self.stats_dir):
            return set()
        return {
            os.path.join(self.stats_dir, filename)
            for filename in os.listdir(self.stats_dir)
            if filename.lower().endswith(".csv")
        }

    @property
    def active(self) -> bool:
        return bool(self.active_scenario) and self.completed_runs < self.target_runs

    def start(self, scenario: str, target_runs: int = 3):
        self.active_scenario = scenario
        self.target_runs = target_runs
        self.completed_runs = 0
        self._seen_paths = self._csv_paths()

    def stop(self):
        self.active_scenario = ""

    def poll(self) -> list:
        """Return newly completed matching scores since the previous poll."""
        if not self.active:
            return []
        matches = []
        for path in sorted(self._csv_paths() - self._seen_paths):
            # Retry files observed while Kovaak's is still writing them.
            try:
                score = parse_csv_file(path)
            except (OSError, ValueError):
                continue
            if score is None:
                continue
            self._seen_paths.add(path)
            if _scenario_key(score.scenario) != _scenario_key(self.active_scenario):
                continue
            if self.completed_runs >= self.target_runs:
                break
            self.completed_runs += 1
            matches.append(score)
        return matches
