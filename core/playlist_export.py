import json
import os
from datetime import datetime
from models.config import _detect_kovaaks_playlists


def export_playlist(scenarios: list[dict], name: str = None, output_dir: str = None) -> str | None:
    if output_dir is None:
        output_dir = _detect_kovaaks_playlists()

    if not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if not name:
        name = f"VT_Training_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    playlist = {
        "playlistName": name,
        "scenarioList": []
    }

    for s in scenarios:
        playlist["scenarioList"].append({
            "scenario_name": s["name"],
            "play_Count": s.get("count", 1)
        })

    filepath = os.path.join(output_dir, f"{name}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(playlist, f, indent=2)

    return filepath
