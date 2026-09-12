"""Official KovaaK's Steam deep links."""

from urllib.parse import quote

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices


KOVAAKS_APP_ID = "824270"

# Keep old saved routines working when a display name was previously stored
# without the spacing expected by Kovaak's online scenario search.
SCENARIO_NAME_ALIASES = {
    "microshotspeed": "Microshot Speed",
    "tilefrenzymini": "Tile Frenzy Mini",
}


def canonical_scenario_name(scenario_name: str) -> str:
    cleaned = scenario_name.strip()
    alias_key = "".join(character for character in cleaned.casefold() if character.isalnum())
    return SCENARIO_NAME_ALIASES.get(alias_key, cleaned)


def game_deep_link() -> str:
    return f"steam://rungameid/{KOVAAKS_APP_ID}"


def scenario_deep_link(scenario_name: str) -> str:
    encoded_name = quote(canonical_scenario_name(scenario_name), safe="")
    return (
        f"steam://run/{KOVAAKS_APP_ID}/?"
        f"action=jump-to-scenario;name={encoded_name}"
    )


def open_kovaaks() -> bool:
    """Open Kovaak's via Steam deep link.
    Returns True if the system accepted the URL, False otherwise.
    """
    url = QUrl(game_deep_link())
    result = QDesktopServices.openUrl(url)
    if not result:
        # In environments without Steam or protocol handler, log the URL for debugging
        print(f"Failed to open Kovaak's URL: {url.toString()}")
    return result


def open_kovaaks_scenario(scenario_name: str) -> bool:
    """Open a specific Kovaak's scenario via Steam deep link.
    Returns True if the system accepted the URL, False otherwise.
    """
    url = QUrl(scenario_deep_link(scenario_name))
    result = QDesktopServices.openUrl(url)
    if not result:
        print(f"Failed to open scenario URL: {url.toString()}")
    return result
