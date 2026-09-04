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
        home.recent_progress
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
