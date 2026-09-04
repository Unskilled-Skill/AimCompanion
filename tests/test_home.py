from ui.home import HomeWidget
from ui.view_models import HomeViewModel


def _view():
    return HomeViewModel(
        rank_text="Silver · 317 energy",
        next_rank_text="Next: Gold at 400 energy",
        headline="Train Clicking / Static next",
        evidence_text="Based on the lowest current subcategory.",
        confidence_text="High confidence",
        recent_progress=("Static A · 3 runs",),
        weakness_text="Clicking / Static",
        trend_text="+2.0% recent trend",
    )


def test_home_places_three_training_actions_before_details(qtbot):
    home = HomeWidget()
    qtbot.addWidget(home)
    assert [button.text() for button in home.primary_actions] == [
        "Warm-up", "Step-by-Step Training", "Full Routine"
    ]
    assert home.layout().indexOf(home.action_panel) < home.layout().indexOf(
        home.insights_panel
    )


def test_home_shows_evidence_and_confidence(qtbot):
    home = HomeWidget()
    qtbot.addWidget(home)
    view = _view()
    home.set_view_model(view)
    assert view.evidence_text in home.evidence_label.text()
    assert "High" in home.confidence_label.text()
    assert view.headline in home.headline_label.text()


def test_home_actions_emit_intent_only(qtbot):
    home = HomeWidget()
    qtbot.addWidget(home)
    with qtbot.waitSignal(home.start_step_by_step):
        home.step_button.click()


def test_home_explains_each_training_choice_before_starting(qtbot):
    home = HomeWidget()
    qtbot.addWidget(home)

    assert "before" in home.warmup_description.text().casefold()
    assert "weakness" in home.step_description.text().casefold()
    assert "complete" in home.full_description.text().casefold()
    assert home.step_button.property("recommended") is True


def test_home_groups_progress_and_readiness_as_dashboard_cards(qtbot):
    home = HomeWidget()
    qtbot.addWidget(home)

    assert home.focus_card.objectName() == "homeFocusCard"
    assert home.recent_progress.objectName() == "homeInsightCard"
    assert home.readiness_card.objectName() == "homeInsightCard"
    assert home.layout().indexOf(home.training_choices) < home.layout().indexOf(
        home.insights_panel
    )


def test_home_view_model_populates_compact_focus_summary(qtbot):
    home = HomeWidget()
    qtbot.addWidget(home)
    home.set_view_model(_view())

    assert home.rank_value.text() == "Silver · 317 energy"
    assert home.weakness_value.text() == "Clicking / Static"
    assert home.confidence_value.text() == "High confidence"
    assert home.readiness_value.text() == "Next: Gold at 400 energy"
