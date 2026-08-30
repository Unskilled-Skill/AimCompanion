import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.updater import (
    UpdateError, is_newer_version, launch_installer, parse_release, version_tuple,
)


class UpdaterTests(unittest.TestCase):
    def test_semantic_versions_compare_numerically(self):
        self.assertEqual(version_tuple("v1.2"), (1, 2, 0))
        self.assertTrue(is_newer_version("1.10.0", "1.9.9"))
        self.assertFalse(is_newer_version("1.0.0", "1.0.0"))

    def test_release_requires_the_official_installer_asset(self):
        with self.assertRaises(UpdateError):
            parse_release({"tag_name": "v1.1.0", "assets": []})

    def test_release_prefers_github_sha256_digest(self):
        digest = "a" * 64
        release = parse_release({
            "tag_name": "v1.1.0",
            "html_url": "https://example.invalid/release",
            "assets": [{
                "name": "AimCompanion-Setup.exe",
                "browser_download_url": "https://example.invalid/setup.exe",
                "digest": f"sha256:{digest}",
            }],
        })
        self.assertEqual(release["version"], "1.1.0")
        self.assertEqual(release["expected_hash"], digest)

    def test_installer_waits_for_frozen_process_then_restarts_app(self):
        with tempfile.TemporaryDirectory() as directory:
            installer = Path(directory) / "AimCompanion-Setup.exe"
            installer.touch()
            with patch("core.updater.subprocess.Popen") as launch, patch(
                "core.updater.sys.executable", str(Path(directory) / "AimCompanion.exe")
            ):
                launch_installer(str(installer))

        command = launch.call_args.args[0]
        encoded_script = command[command.index("-EncodedCommand") + 1]
        script = base64.b64decode(encoded_script).decode("utf-16le")
        self.assertIn("Get-Process -Name $processName", script)
        self.assertIn("$running.Count -eq 0", script)
        self.assertIn("-Wait -PassThru", script)
        self.assertIn("Start-Process -FilePath $targetPath", script)

    def test_first_launch_completes_without_blocking_dialog(self):
        from ui.main_window import MainWindow

        class SettingsDatabase:
            def __init__(self):
                self.values = {}

            def get_settings_value(self, key):
                return self.values.get(key)

            def set_settings_value(self, key, value):
                self.values[key] = value

        window_shell = type("WindowShell", (), {"db": SettingsDatabase()})()
        MainWindow._run_first_setup(window_shell)
        self.assertEqual(
            window_shell.db.get_settings_value("onboarding_complete"), "1"
        )


if __name__ == "__main__":
    unittest.main()
