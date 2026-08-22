"""Official KovaaK's Steam deep links."""

from urllib.parse import quote

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices


KOVAAKS_APP_ID = "824270"


def game_deep_link() -> str:
    return f"steam://rungameid/{KOVAAKS_APP_ID}"


def scenario_deep_link(scenario_name: str) -> str:
    encoded_name = quote(scenario_name.strip(), safe="")
    return (
        f"steam://run/{KOVAAKS_APP_ID}/?"
        f"action=jump-to-scenario;name={encoded_name}"
    )


def open_kovaaks() -> bool:
    return QDesktopServices.openUrl(QUrl.fromEncoded(game_deep_link().encode("utf-8")))


def open_kovaaks_scenario(scenario_name: str) -> bool:
    url = scenario_deep_link(scenario_name)
    return QDesktopServices.openUrl(QUrl.fromEncoded(url.encode("utf-8")))
