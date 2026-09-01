from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path
import sqlite3

import pytest

from core.score_importer import ScoreImporter
from models.database import Database


def write_score(
    path: Path, timestamp: datetime, score: float = 123.0,
    scenario: str = "Test Scenario",
) -> Path:
    path = path.with_name(
        f"{scenario} - Challenge - {timestamp:%Y.%m.%d-%H.%M.%S} Stats.csv"
    )
    path.write_text("Scenario:," + scenario + "\nScore:," + str(score) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def db(tmp_path: Path):
    database = Database(str(tmp_path / "scores.sqlite3"))
    try:
        yield database
    finally:
        database.close()


@pytest.fixture
def importer(db: Database) -> ScoreImporter:
    return ScoreImporter(db)


def test_batch_imports_out_of_order_files_by_score_timestamp(
    importer: ScoreImporter, tmp_path: Path,
):
    older_timestamp = datetime(2026, 1, 1, 12, 0, 0)
    newer_timestamp = datetime(2026, 1, 2, 12, 0, 0)
    newer = write_score(tmp_path / "newer.csv", newer_timestamp)
    older = write_score(tmp_path / "older.csv", older_timestamp)

    result = importer.import_paths([newer, older])

    assert result.imported == 2
    assert result.duplicates == 0
    assert [score.timestamp for score in importer.db.get_all_scores()] == [
        older_timestamp, newer_timestamp,
    ]


def test_duplicate_score_marks_second_path_without_duplicating_row(
    importer: ScoreImporter, tmp_path: Path,
):
    timestamp = datetime(2026, 1, 1, 12, 0, 0)
    first = write_score(tmp_path / "first.csv", timestamp, scenario="Test Scenario")
    second = write_score(tmp_path / "second.csv", timestamp, scenario="Test Scenario  ")

    result = importer.import_paths([first, second])

    assert result.imported == 1
    assert result.duplicates == 1
    assert len(importer.db.get_all_scores()) == 1
    assert importer.db.get_imported_score_paths() == {
        os.path.normcase(str(first.resolve())),
        os.path.normcase(str(second.resolve())),
    }


def test_malformed_file_isolated_and_recorded(
    importer: ScoreImporter, tmp_path: Path,
):
    malformed = tmp_path / "Malformed - Challenge - 2026.01.01-12.00.00 Stats.csv"
    malformed.write_text("Scenario:,Malformed\n", encoding="utf-8")
    valid = write_score(tmp_path / "valid.csv", datetime(2026, 1, 2, 12, 0, 0))

    result = importer.import_paths([malformed, valid])

    assert result.imported == 1
    assert result.failed == 1
    failure = importer.db.get_import_failure(str(malformed.resolve()))
    assert failure["retry_count"] == 1
    assert "malformed" in failure["error_text"].lower()


def test_parser_exception_is_isolated_and_recorded(
    importer: ScoreImporter, tmp_path: Path,
):
    unreadable = tmp_path / "Unreadable - Challenge - 2026.01.01-12.00.00 Stats.csv"
    unreadable.mkdir()
    valid = write_score(tmp_path / "valid.csv", datetime(2026, 1, 2, 12, 0, 0))

    result = importer.import_paths([unreadable, valid])

    assert result.imported == 1
    assert result.failed == 1
    failure = importer.db.get_import_failure(str(unreadable.resolve()))
    assert "Error" in failure["error_text"]


def test_successful_retry_clears_prior_import_error(
    importer: ScoreImporter, tmp_path: Path,
):
    retry = write_score(tmp_path / "retry.csv", datetime(2026, 1, 1, 12, 0, 0))
    retry.write_text("Scenario:,Retry\n", encoding="utf-8")

    first = importer.import_paths([retry])
    retry.write_text("Scenario:,Retry\nScore:,123.0\n", encoding="utf-8")
    second = importer.import_paths([retry])

    assert first.failed == 1
    assert second.imported == 1
    assert importer.db.get_import_failure(str(retry.resolve())) is None


def test_batch_returns_paths_in_deterministic_normalized_order(
    importer: ScoreImporter, tmp_path: Path,
):
    first = write_score(tmp_path / "z.csv", datetime(2026, 1, 1, 12, 0, 0))
    second = write_score(tmp_path / "a.csv", datetime(2026, 1, 2, 12, 0, 0))

    result = importer.import_paths([first, second, first])

    assert result.paths == tuple(sorted({str(first.resolve()), str(second.resolve())}))


def test_valid_batch_rolls_back_all_path_marks_when_a_later_insert_fails(
    importer: ScoreImporter, tmp_path: Path,
):
    first = write_score(tmp_path / "first.csv", datetime(2026, 1, 1, 12, 0, 0))
    second = write_score(tmp_path / "second.csv", datetime(2026, 1, 2, 12, 0, 0))
    importer.db.conn.execute("""
        CREATE TRIGGER reject_later_score
        BEFORE INSERT ON scores
        WHEN NEW.timestamp = '2026-01-02T12:00:00'
        BEGIN
            SELECT RAISE(ABORT, 'forced insert failure');
        END
    """)

    with pytest.raises(sqlite3.IntegrityError, match="forced insert failure"):
        importer.import_paths([first, second])

    assert importer.db.get_all_scores() == []
    assert importer.db.get_imported_score_paths() == set()
