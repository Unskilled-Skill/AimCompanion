from core.service_health import ServiceStatus
from ui.status_indicator import StatusIndicator


def test_status_selects_highest_severity_and_keeps_text(qtbot):
    indicator = StatusIndicator()
    qtbot.addWidget(indicator)
    indicator.update_service(
        ServiceStatus("scores", "error", "Import failed", "Bad CSV")
    )
    indicator.update_service(
        ServiceStatus("updates", "busy", "Checking", "")
    )
    assert indicator.summary_text() == "Import failed"
    assert indicator.accessibleDescription() == "Bad CSV"
    assert "error" in indicator.state_label.text().casefold()


def test_status_details_expand_persistently_and_emit(qtbot):
    indicator = StatusIndicator()
    qtbot.addWidget(indicator)
    indicator.update_service(
        ServiceStatus(
            "scores", "warning", "One file needs attention", "Broken.csv",
            recovery_action="Retry score import",
        )
    )
    with qtbot.waitSignal(indicator.details_requested):
        indicator.details_button.click()
    assert not indicator.details_label.isHidden()
    assert "Broken.csv" in indicator.details_label.text()
    assert "Retry score import" in indicator.details_label.text()
