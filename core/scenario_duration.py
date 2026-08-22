import math
import os
import re
from datetime import datetime, timedelta

from core.scenario_files import find_scenario_file


# Online scenarios are not always stored as local .sce files. Keep verified
# exceptions here so long-form challenges never become accidental 15m blocks.
KNOWN_DURATION_SECONDS = {
    "air angelic dodge": 300,
}


def _duration_from_name(name: str) -> int | None:
    lowered = name.casefold()
    minute_match = re.search(r"(?:^|\D)(\d+)\s*(?:min|minute)s?(?:\D|$)", lowered)
    if minute_match:
        return int(minute_match.group(1)) * 60
    second_match = re.search(r"(?:^|\D)(\d+)\s*(?:sec|second)s?(?:\D|$)", lowered)
    if second_match:
        return int(second_match.group(1))
    standalone_seconds = re.search(r"(?:^|\D)(\d{2,3})s(?:\D|$)", lowered)
    if standalone_seconds:
        return int(standalone_seconds.group(1))
    return None


def _duration_from_scenario_file(path: str) -> int | None:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as file:
            for line in file:
                if line.casefold().startswith("timelimit="):
                    return max(1, round(float(line.split("=", 1)[1].strip())))
    except (OSError, ValueError):
        return None
    return None


_STATS_FILENAME = re.compile(
    r"^(.+?)\s*-\s*Challenge\s*-\s*"
    r"(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2})\s*Stats\.csv$",
    re.IGNORECASE,
)


def _duration_from_recent_results(name: str, stats_dir: str) -> int | None:
    if not stats_dir or not os.path.isdir(stats_dir):
        return None
    key = name.strip().casefold()
    durations = []
    for filename in os.listdir(stats_dir):
        match = _STATS_FILENAME.match(filename)
        if not match or match.group(1).strip().casefold() != key:
            continue
        try:
            end = datetime.strptime(match.group(2), "%Y.%m.%d-%H.%M.%S")
        except ValueError:
            continue
        start_text = None
        pause_seconds = 0.0
        try:
            with open(
                os.path.join(stats_dir, filename), "r",
                encoding="utf-8", errors="ignore",
            ) as file:
                for line in file:
                    if line.startswith("Challenge Start:,"):
                        start_text = line.split(",", 1)[1].strip()
                    elif line.startswith("Pause Duration:,"):
                        pause_seconds = float(line.split(",", 1)[1].strip() or 0)
        except (OSError, ValueError):
            continue
        if not start_text:
            continue
        try:
            start_time = datetime.strptime(start_text, "%H:%M:%S.%f").time()
        except ValueError:
            continue
        start = datetime.combine(end.date(), start_time)
        if start > end:
            start -= timedelta(days=1)
        elapsed = round((end - start).total_seconds() - pause_seconds)
        if 5 <= elapsed <= 3600:
            durations.append(elapsed)
    return max(durations) if durations else None


def scenario_duration_seconds(
    name: str, scenarios_dir="", stats_dir: str = ""
) -> tuple[int, str]:
    """Return estimated challenge seconds and the source of that estimate."""
    key = name.strip().casefold()
    scenario_path = find_scenario_file(name, scenarios_dir)
    if scenario_path:
        duration = _duration_from_scenario_file(scenario_path)
        if duration:
            return duration, "scenario file"
    duration = _duration_from_recent_results(name, stats_dir)
    if duration:
        return duration, "recent result"
    if key in KNOWN_DURATION_SECONDS:
        return KNOWN_DURATION_SECONDS[key], "verified exception"
    duration = _duration_from_name(name)
    if duration:
        return duration, "scenario name"
    return 60, "standard estimate"


def quick_block_plan(
    name: str, scenarios_dir: str = "", stats_dir: str = "", target_minutes: int = 3,
    maximum_runs: int = 3,
) -> dict:
    seconds, source = scenario_duration_seconds(name, scenarios_dir, stats_dir)
    target_seconds = max(60, target_minutes * 60)
    runs = max(1, min(maximum_runs, math.ceil(target_seconds / seconds)))
    total_seconds = runs * seconds
    return {
        "runs": runs,
        "scenario_seconds": seconds,
        "estimated_minutes": max(1, math.ceil(total_seconds / 60)),
        "duration_source": source,
    }
