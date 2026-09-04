from pathlib import Path

from core import updater


def test_spec_collects_versioned_benchmark_data():
    text = Path("AimCompanion.spec").read_text(encoding="utf-8")
    assert "benchmark_definitions" in text


def test_installer_and_updater_expect_same_asset_name():
    assert updater.INSTALLER_ASSET == "AimCompanion-Setup.exe"
    assert "AimCompanion-Setup" in Path("installer.iss").read_text(encoding="utf-8")
