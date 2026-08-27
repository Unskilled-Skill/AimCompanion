import os
import tempfile
import unittest

from core.parser import import_all_scores
from models.database import Database


class ScoreImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db = Database(":memory:")

    def tearDown(self):
        self.db.close()
        self.directory.cleanup()

    def _write_score(self, filename: str):
        path = os.path.join(self.directory.name, filename)
        with open(path, "w", encoding="utf-8") as file:
            file.write("Scenario:,Test\nScore:,123.0\n")
        return path

    def test_duplicate_score_files_are_not_reparsed_on_later_syncs(self):
        first = self._write_score(
            "Test - Challenge - 2026.01.01-12.00.00 Stats.csv"
        )
        duplicate = self._write_score(
            "Test  - Challenge - 2026.01.01-12.00.00 Stats.csv"
        )

        self.assertEqual(import_all_scores(self.db, self.directory.name), 1)
        self.assertEqual(
            self.db.get_imported_score_paths(), {first, duplicate}
        )
        self.assertEqual(import_all_scores(self.db, self.directory.name), 0)


if __name__ == "__main__":
    unittest.main()
