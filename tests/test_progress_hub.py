from PyQt6.QtWidgets import QLabel

from ui.progress_hub import ProgressHub
from ui.view_models import ProgressViewModel


def _hub(qtbot):
    hub = ProgressHub(*(QLabel(name) for name in ("chart", "skills", "benchmarks", "history")))
    qtbot.addWidget(hub)
    return hub


def test_progress_has_four_named_views(qtbot):
    assert _hub(qtbot).tab_names() == (
        "Summary", "Skills", "Benchmarks", "History",
    )


def test_summary_text_precedes_chart(qtbot):
    hub = _hub(qtbot)
    hub.set_view_model(ProgressViewModel(
        conclusion="Silver · Static is the main weakness",
        missing_subcategories=("Tracking / Reactive",),
        definition_version="voltaic-s5-2026-08-30",
    ))
    assert hub.summary_layout.indexOf(hub.conclusion) < hub.summary_layout.indexOf(hub.chart_container)
    assert "1 missing" in hub.conclusion.text()
