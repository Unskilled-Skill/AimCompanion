from PyQt6.QtCore import Qt

from tests.test_session_widget import _view
from ui.session import SessionWidget
from ui.session_overlay import SessionOverlay


def test_overlay_and_main_render_same_progress(qtbot):
    main_session = SessionWidget()
    overlay = SessionOverlay()
    qtbot.addWidget(main_session)
    qtbot.addWidget(overlay)
    view = _view()
    main_session.set_state(view)
    overlay.set_state(view)
    assert overlay.progress.text() == main_session.progress_text()


def test_overlay_is_collapsed_and_always_on_top_by_default(qtbot):
    overlay = SessionOverlay()
    qtbot.addWidget(overlay)
    assert overlay.is_expanded() is False
    assert overlay.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


def test_overlay_emits_actions_without_mutating_progress(qtbot):
    overlay = SessionOverlay()
    qtbot.addWidget(overlay)
    overlay.set_state(_view())
    with qtbot.waitSignal(overlay.pause_requested):
        overlay.pause_button.click()
    assert overlay.progress.text() == "0 / 1 runs"
