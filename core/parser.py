import os
import re
from datetime import datetime
from models.score import Score
from models.benchmark import get_benchmark
from models.config import _detect_kovaaks_stats


def _get_stats_dir():
    return _detect_kovaaks_stats()

FILENAME_PATTERN = re.compile(
    r"^(.+?)\s*-\s*Challenge\s*-\s*(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})\s*Stats\.csv$"
)
SCORE_PATTERN = re.compile(r"^Score:\s*,\s*(.+)$")
SCENARIO_PATTERN = re.compile(r"^Scenario:\s*,\s*(.+)$")
KILLS_PATTERN = re.compile(r"^Kills:\s*,\s*(\d+)$")
HIT_COUNT_PATTERN = re.compile(r"^Hit Count:\s*,\s*(\d+)$")
MISS_COUNT_PATTERN = re.compile(r"^Miss Count:\s*,\s*(\d+)$")
FIGHT_TIME_PATTERN = re.compile(r"^Fight Time:\s*,\s*([\d.]+)$")
AVG_TTK_PATTERN = re.compile(r"^Avg TTK:\s*,\s*([\d.]+)$")
RESOLUTION_PATTERN = re.compile(r"^Resolution:\s*,\s*(.+)$")
AVG_FPS_PATTERN = re.compile(r"^Avg FPS:\s*,\s*([\d.]+)$")


def parse_filename(filename: str) -> tuple[str, datetime] | None:
    match = FILENAME_PATTERN.match(filename)
    if not match:
        return None
    scenario_name = match.group(1).strip()
    timestamp_str = match.group(2)
    try:
        timestamp = datetime.strptime(timestamp_str, "%Y.%m.%d-%H.%M.%S")
    except ValueError:
        return None
    return scenario_name, timestamp


def parse_csv_file(filepath: str) -> Score | None:
    filename = os.path.basename(filepath)
    parsed = parse_filename(filename)
    if not parsed:
        return None
    scenario_name, timestamp = parsed

    score_value = None
    scenario_found = None
    kills = 0
    hits = 0
    misses = 0
    fight_time = 0.0
    avg_ttk = 0.0
    resolution = ""
    avg_fps = 0.0

    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()

            m = SCORE_PATTERN.match(line)
            if m:
                try:
                    score_value = float(m.group(1))
                except ValueError:
                    pass
                continue

            m = SCENARIO_PATTERN.match(line)
            if m:
                scenario_found = m.group(1).strip()
                continue

            m = KILLS_PATTERN.match(line)
            if m:
                kills = int(m.group(1))
                continue

            m = HIT_COUNT_PATTERN.match(line)
            if m:
                hits = int(m.group(1))
                continue

            m = MISS_COUNT_PATTERN.match(line)
            if m:
                misses = int(m.group(1))
                continue

            m = FIGHT_TIME_PATTERN.match(line)
            if m:
                fight_time = float(m.group(1))
                continue

            m = AVG_TTK_PATTERN.match(line)
            if m:
                avg_ttk = float(m.group(1))
                continue

            m = RESOLUTION_PATTERN.match(line)
            if m:
                resolution = m.group(1).strip()
                continue

            m = AVG_FPS_PATTERN.match(line)
            if m:
                avg_fps = float(m.group(1))
                continue

    if score_value is None:
        return None

    benchmark_info = get_benchmark(scenario_name)
    if not benchmark_info:
        benchmark_info = get_benchmark(scenario_found) if scenario_found else None

    if benchmark_info:
        category = benchmark_info["category"]
        subcategory = benchmark_info["subcategory"]
        difficulty = benchmark_info["difficulty"]
        benchmark_name = benchmark_info["name"]
    else:
        category = "Unknown"
        subcategory = "Unknown"
        difficulty = "Unknown"
        benchmark_name = scenario_name

    total_shots = hits + misses
    accuracy = hits / total_shots if total_shots > 0 else 0.0

    return Score(
        benchmark_name=benchmark_name,
        scenario=scenario_name,
        category=category,
        subcategory=subcategory,
        difficulty=difficulty,
        score=score_value,
        timestamp=timestamp,
        kills=kills,
        hits=hits,
        misses=misses,
        fight_time=fight_time,
        avg_ttk=avg_ttk,
        accuracy=accuracy,
        avg_fps=avg_fps,
        resolution=resolution,
    )


def scan_stats_folder(stats_dir: str = None) -> list[tuple[Score, str]]:
    if stats_dir is None:
        stats_dir = _get_stats_dir()
    results = []
    if not os.path.isdir(stats_dir):
        return results

    for filename in os.listdir(stats_dir):
        if not filename.lower().endswith(".csv"):
            continue
        filepath = os.path.join(stats_dir, filename)
        score = parse_csv_file(filepath)
        if score:
            results.append((score, filepath))

    return results


def iter_score_csv_paths(stats_dir: str):
    """Yield result files in deterministic discovery order."""
    if not os.path.isdir(stats_dir):
        return
    for filename in sorted(os.listdir(stats_dir)):
        if filename.lower().endswith(".csv"):
            yield os.path.join(stats_dir, filename)


def import_all_scores(db, stats_dir: str = None) -> int:
    """Compatibility wrapper for callers that only need the inserted count."""
    if stats_dir is None:
        stats_dir = _get_stats_dir()
    from core.score_importer import ScoreImporter

    return ScoreImporter(db).import_paths(iter_score_csv_paths(stats_dir)).imported
