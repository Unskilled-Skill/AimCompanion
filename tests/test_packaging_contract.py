import os
from pathlib import Path
import subprocess

from core import updater


def test_spec_collects_versioned_benchmark_data():
    text = Path("AimCompanion.spec").read_text(encoding="utf-8")
    assert "benchmark_definitions" in text


def test_installer_and_updater_expect_same_asset_name():
    assert updater.INSTALLER_ASSET == "AimCompanion-Setup.exe"
    assert "AimCompanion-Setup" in Path("installer.iss").read_text(encoding="utf-8")


def test_release_workflow_smoke_tests_upgrade_from_previous_installer():
    workflow = Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    script = Path("scripts/smoke_upgrade.ps1")

    assert script.is_file()
    assert "gh release download" in workflow
    assert "smoke_upgrade.ps1" in workflow

    smoke = script.read_text(encoding="utf-8")
    assert "PreviousInstaller" in smoke
    assert "NewInstaller" in smoke
    assert "ExpectedVersion" in smoke
    assert "ProductVersion" in smoke


def test_upgrade_smoke_refuses_to_change_a_developer_machine():
    environment = os.environ.copy()
    environment.pop("CI", None)
    result = subprocess.run(
        [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", "scripts/smoke_upgrade.ps1",
            "-PreviousInstaller", "missing-previous.exe",
            "-NewInstaller", "missing-new.exe",
            "-ExpectedVersion", "9.9.9",
        ],
        capture_output=True,
        check=False,
        text=True,
        env=environment,
    )

    assert result.returncode != 0
    assert "disposable CI runner" in (result.stdout + result.stderr)
