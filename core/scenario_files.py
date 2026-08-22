"""Locate Kovaak's scenario files across local and Steam Workshop storage."""

import os
from pathlib import Path
from typing import Iterable


KOVAAKS_APP_ID = "824270"


def scenario_key(name: str) -> str:
    return "".join(character for character in name.casefold() if character.isalnum())


def workshop_scenarios_dir(savegames_dir: str) -> str:
    """Return the Workshop content directory belonging to the Kovaak's install."""
    path = Path(savegames_dir)
    for parent in (path, *path.parents):
        if parent.name.casefold() == "steamapps":
            return str(parent / "workshop" / "content" / KOVAAKS_APP_ID)
    return ""


def scenario_search_dirs(local_scenarios_dir: str) -> list[str]:
    directories = [local_scenarios_dir] if local_scenarios_dir else []
    if local_scenarios_dir:
        savegames_dir = str(Path(local_scenarios_dir).parent)
        workshop_dir = workshop_scenarios_dir(savegames_dir)
        if workshop_dir:
            directories.append(workshop_dir)
    return directories


def iter_scenario_files(directories: str | Iterable[str]):
    if isinstance(directories, str):
        directories = [directories]
    seen = set()
    for directory in directories:
        if not directory or not os.path.isdir(directory):
            continue
        for root, _, filenames in os.walk(directory):
            for filename in filenames:
                if not filename.casefold().endswith(".sce"):
                    continue
                path = os.path.join(root, filename)
                normalized = os.path.normcase(os.path.abspath(path))
                if normalized not in seen:
                    seen.add(normalized)
                    yield path


def find_scenario_file(name: str, directories: str | Iterable[str]) -> str | None:
    wanted = scenario_key(name)
    for path in iter_scenario_files(directories):
        if scenario_key(Path(path).stem) == wanted:
            return path
    return None


def installed_scenario_names(directories: str | Iterable[str]) -> set[str]:
    return {Path(path).stem.casefold() for path in iter_scenario_files(directories)}

