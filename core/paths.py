import os
import shutil
from pathlib import Path


APP_NAME = "AimCompanion"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_DATA_DIR = PROJECT_ROOT / "data"


def bundled_path(*parts: str) -> str:
    return str(PROJECT_ROOT.joinpath(*parts))


def user_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / APP_NAME
    return Path.home() / ".aim_companion"


def writable_path(filename: str, migrate_legacy: bool = True) -> str:
    directory = user_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / filename
    legacy = BUNDLED_DATA_DIR / filename
    if migrate_legacy and not destination.exists() and legacy.exists():
        shutil.copy2(legacy, destination)
    return str(destination)
