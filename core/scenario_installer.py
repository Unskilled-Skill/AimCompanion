"""Exact-name scenario availability and install guidance."""

from dataclasses import dataclass
from typing import Literal

from core.scenario_files import scenario_key


@dataclass(frozen=True)
class AvailabilityResult:
    scenario: str
    state: Literal["installed", "online_launchable", "missing"]
    resolved_name: str | None


@dataclass(frozen=True)
class ScenarioInstallGuide:
    scenario: str
    state: Literal["installed", "online_launchable", "missing"]
    steps: tuple[str, ...]
    open_action: Literal["launch_scenario", "open_kovaaks", "none"]


class ScenarioAvailability:
    @staticmethod
    def resolve(name: str, installed) -> AvailabilityResult:
        wanted = scenario_key(name)
        exact = next(
            (candidate for candidate in installed if scenario_key(candidate) == wanted),
            None,
        )
        if exact is not None:
            return AvailabilityResult(name, "installed", exact)
        return AvailabilityResult(name, "missing", None)


def build_install_guide(scenario: str) -> ScenarioInstallGuide:
    return ScenarioInstallGuide(
        scenario=scenario,
        state="missing",
        steps=(
            "Open Kovaak's and choose Online Scenarios.",
            f'Search for the exact title: "{scenario}".',
            "Download or subscribe to that exact scenario; do not use a similarly named substitute.",
            "Return to Aim Companion and press Recheck.",
        ),
        open_action="open_kovaaks",
    )
