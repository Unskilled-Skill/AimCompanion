import json
import os
import tempfile
import unittest
from unittest.mock import patch

from models.config import TrainingConfig


class TrainingConfigPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, "config.json")

    def tearDown(self):
        self.directory.cleanup()

    def test_invalid_json_falls_back_to_defaults(self):
        with open(self.path, "w", encoding="utf-8") as file:
            file.write('{"session_minutes":')

        with patch("models.config.CONFIG_PATH", self.path):
            config = TrainingConfig.load()

        self.assertEqual(config, TrainingConfig())

    def test_non_object_json_falls_back_to_defaults(self):
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump(["not", "a", "config"], file)

        with patch("models.config.CONFIG_PATH", self.path):
            config = TrainingConfig.load()

        self.assertEqual(config, TrainingConfig())

    def test_save_replaces_config_with_complete_json(self):
        config = TrainingConfig(session_minutes=75, game="Valorant")

        with patch("models.config.CONFIG_PATH", self.path):
            config.save()

        with open(self.path, encoding="utf-8") as file:
            saved = json.load(file)
        self.assertEqual(saved["session_minutes"], 75)
        self.assertEqual(saved["game"], "Valorant")
        self.assertEqual(os.listdir(self.directory.name), ["config.json"])


if __name__ == "__main__":
    unittest.main()
