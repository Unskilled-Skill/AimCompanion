import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QFileDialog

from models.database import Database
from models.score import BenchmarkInfo, CategoryScore, PlayerProfile, SubcategoryScore
from ui.dashboard import DashboardWidget
from ui.export import ExportWidget
from ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _incomplete_profile():
    return PlayerProfile(
        overall_energy=None,
        overall_tier="Unranked",
        calculation_method="voltaic_official",
    )


def _official_profile_for_export():
    subcategory = SubcategoryScore(
        name="Static",
        category="Clicking",
        benchmarks=[
            BenchmarkInfo(
                name="VT 1w4ts Novice S5",
                scenario="VT 1w4ts Novice S5",
                category="Clicking",
                subcategory="Static",
                difficulty="Novice",
                attempts=1,
                best_score=820,
                latest_score=820,
                energy=100,
                tier="Iron",
            )
        ],
        combined_score=820,
        energy=100,
        tier="Iron",
    )
    return PlayerProfile(
        categories=[
            CategoryScore(
                name="Clicking",
                subcategories=[subcategory],
                combined_score=820,
                energy=100,
                tier="Iron",
            )
        ],
        overall_energy=100,
        overall_tier="Iron",
        calculation_method="voltaic_official",
    )


def test_incomplete_dashboard_and_main_rank_label_render_without_energy(app):
    profile = _incomplete_profile()
    dashboard = DashboardWidget(profile)
    tier_label = SimpleNamespace(setText=lambda value: setattr(tier_label, "text", value), setStyleSheet=lambda value: None)
    energy_label = SimpleNamespace(setText=lambda value: setattr(energy_label, "text", value))
    window = SimpleNamespace(
        rank_profile=profile,
        tier_label=tier_label,
        energy_label=energy_label,
        _overall_energy_text=MainWindow._overall_energy_text,
    )

    MainWindow._update_tier_label(window)

    assert profile.overall_tier == "Unranked"
    assert energy_label.text == "Overall energy unavailable"
    dashboard.deleteLater()


def test_official_export_marks_category_aggregates_as_non_official(app, tmp_path, monkeypatch):
    database = Database(":memory:")
    widget = ExportWidget(_official_profile_for_export(), database)
    destination = tmp_path / "report.txt"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(destination), "")
    )

    widget._export_progress_report()

    report = destination.read_text(encoding="utf-8")
    assert "Clicking: 820 combined score (local compatibility view)" in report
    assert "Static: 100.0 official energy (Iron)" in report
    assert "Clicking: 820 (Iron, 100.0 energy)" not in report
    widget.deleteLater()
    database.close()
