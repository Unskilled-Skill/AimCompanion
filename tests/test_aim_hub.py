import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QCheckBox, QSpinBox

from models.database import Database
from ui.aim_hub import AimHubWidget


class AimHubTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.db = Database(":memory:")
        self.widget = AimHubWidget(None, self.db)

    def tearDown(self):
        self.widget.deleteLater()
        self.app.processEvents()
        self.db.close()

    def test_deathmatch_progress_is_saved_and_reset(self):
        crosshair = self.widget.deathmatch_controls["crosshair_placement"]
        sheriff = self.widget.deathmatch_controls["sheriff_accuracy_1"]
        self.assertIsInstance(crosshair, QSpinBox)
        self.assertIsInstance(sheriff, QCheckBox)

        crosshair.setValue(2)
        sheriff.setChecked(True)
        state = json.loads(self.db.get_settings_value("deathmatch_daily_v1"))
        self.assertEqual(state["counts"]["crosshair_placement"], 2)
        self.assertEqual(state["counts"]["sheriff_accuracy_1"], 1)
        self.assertIn("3 of 8", self.widget.deathmatch_progress.text())

        self.widget._reset_deathmatch_progress()
        self.assertIn("0 of 8", self.widget.deathmatch_progress.text())


if __name__ == "__main__":
    unittest.main()
