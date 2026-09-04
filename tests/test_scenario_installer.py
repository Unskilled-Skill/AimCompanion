from core.scenario_installer import ScenarioAvailability, build_install_guide


def test_missing_official_scenario_never_substitutes_similar_name():
    result = ScenarioAvailability.resolve(
        "Exact Official Name", installed={"Similar Name"},
    )
    assert result.state == "missing"
    assert result.resolved_name is None


def test_exact_match_is_installed_case_insensitively():
    result = ScenarioAvailability.resolve(
        "Exact Official Name", installed={"exact official name"},
    )
    assert result.state == "installed"
    assert result.resolved_name == "exact official name"


def test_missing_guide_names_exact_search_and_recheck_steps():
    guide = build_install_guide("Exact Official Name")
    text = " ".join(guide.steps)
    assert "Exact Official Name" in text
    assert "Online Scenarios" in text
    assert "Recheck" in text
