import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from core.training_methods import TRAINING_METHODS
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

    def test_lists_all_training_methods_and_renders_selected_method(self):
        self.assertEqual(self.widget.method_list.count(), len(TRAINING_METHODS))
        target = next(
            self.widget.method_list.item(index)
            for index in range(self.widget.method_list.count())
            if self.widget.method_list.item(index).data(Qt.ItemDataRole.UserRole)
            == "speed_stopping"
        )
        self.widget.method_list.setCurrentItem(target)
        self.assertEqual(self.widget.method_title.text(), "Speed and stopping")
        self.assertIn("voxTS Voltaic mini", self.widget.session_label.text())
        self.assertFalse(self.widget.source_button.isHidden())

    def test_search_filters_methods_and_action_emits_method_id(self):
        self.widget.search_input.setText("crosshair placement")
        self.assertGreaterEqual(self.widget.method_list.count(), 1)
        target = next(
            self.widget.method_list.item(index)
            for index in range(self.widget.method_list.count())
            if self.widget.method_list.item(index).data(Qt.ItemDataRole.UserRole)
            == "deathmatch_crosshair"
        )
        self.widget.method_list.setCurrentItem(target)
        received = []
        self.widget.train_requested.connect(received.append)
        self.widget.train_button.click()
        self.assertEqual(received, ["deathmatch_crosshair"])


if __name__ == "__main__":
    unittest.main()
