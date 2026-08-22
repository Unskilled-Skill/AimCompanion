"""Official KovaaK's Steam deep links."""

from urllib.parse import quote

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices


KOVAAKS_APP_ID = "824270"

# Keep old saved routines working when a display name was previously stored
# without the spacing expected by Kovaak's online scenario search.
SCENARIO_NAME_ALIASES = {
    "microshotspeed": "Microshot Speed",
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
    return QDesktopServices.openUrl(QUrl.fromEncoded(game_deep_link().encode("utf-8")))


def open_kovaaks_scenario(scenario_name: str) -> bool:
    url = scenario_deep_link(scenario_name)
    return QDesktopServices.openUrl(QUrl.fromEncoded(url.encode("utf-8")))
