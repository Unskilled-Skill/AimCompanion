import json
import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QLabel, QPushButton

from models.database import Database
from ui.scenarios import ScenarioBrowser


class ScenarioBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = Database(":memory:")
        installed = patch(
            "ui.scenarios.get_installed_scenario_names", return_value=set()
        )
        self.addCleanup(installed.stop)
        installed.start()
        self.browser = ScenarioBrowser(self.db)

    def tearDown(self):
        self.browser.deleteLater()
        self.app.processEvents()
        self.db.close()

    def test_scenario_cards_can_download_and_play_directly(self):
        button = next(
            item for item in self.browser.findChildren(QPushButton)
            if item.text() == "Download & play"
        )

        with patch("ui.scenarios.open_kovaaks_scenario", return_value=True) as launch:
            button.click()

        launch.assert_called_once()

    def test_scenario_cards_show_a_visible_description(self):
        card = self.browser._card(self.browser.all_scenarios[0], set())
        labels = [label.text() for label in card.findChildren(QLabel)]
        self.assertTrue(any("Focus" in text or "Train" in text or "Build" in text for text in labels))

    def test_recommended_pack_contains_every_missing_scenario(self):
        with tempfile.TemporaryDirectory() as directory:
            config = type(
                "Config", (), {"get_playlists_dir": lambda self: directory}
            )()
            with (
                patch("ui.scenarios.TrainingConfig.load", return_value=config),
                patch("ui.scenarios.open_kovaaks", return_value=True),
                patch("ui.scenarios.QMessageBox.exec", return_value=0),
            ):
                self.browser._download_recommended_pack()

            path = os.path.join(
                directory, "Aim Companion Recommended Scenarios.json"
            )
            with open(path, encoding="utf-8") as file:
                playlist = json.load(file)

        names = [item["scenarioName"] for item in playlist["scenarioList"]]
        self.assertEqual(len(names), len(self.browser.all_scenarios))
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(item["playCount"] == 1 for item in playlist["scenarioList"]))


if __name__ == "__main__":
    unittest.main()
