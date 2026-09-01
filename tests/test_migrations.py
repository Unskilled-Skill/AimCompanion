import sqlite3
import importlib
from pathlib import Path

import pytest

from models.database import Database


def create_legacy_database(tmp_path: Path, score_count: int = 3) -> Path:
    """Create the unversioned scores/settings schema used by released builds."""
    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("""
        CREATE TABLE scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            benchmark_name TEXT NOT NULL,
            scenario TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            score REAL NOT NULL,
            timestamp TEXT NOT NULL,
            kills INTEGER DEFAULT 0,
            hits INTEGER DEFAULT 0,
            misses INTEGER DEFAULT 0,
            fight_time REAL DEFAULT 0.0,
            avg_ttk REAL DEFAULT 0.0,
            accuracy REAL DEFAULT 0.0,
            avg_fps REAL DEFAULT 0.0,
            resolution TEXT DEFAULT '',
            csv_path TEXT UNIQUE
        )
    """)
    connection.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT)")
    connection.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?)",
        ("legacy_preference", "preserve this exactly"),
    )
    for index in range(score_count):
        connection.execute("""
            INSERT INTO scores (
                benchmark_name, scenario, category, subcategory, difficulty,
                score, timestamp, csv_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "Legacy benchmark", f"Legacy scenario {index}", "Tracking",
            "Reactive", "Intermediate", 100 + index,
            f"2026-08-30T12:00:0{index}", f"legacy-{index}.csv",
        ))
    connection.commit()
    connection.close()
    return path


def sqlite_table_names(path: Path) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        return {
            row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    finally:
        connection.close()


def test_fresh_database_reaches_current_schema_without_pre_migration_backup(tmp_path):
    path = tmp_path / "fresh.sqlite3"

    db = Database(str(path))
    try:
        assert db.schema_version == 2
        assert not list(tmp_path.glob("*.pre-v*.sqlite3"))
    finally:
        db.close()


def test_v1_database_is_backed_up_and_migrated_without_score_or_setting_loss(tmp_path):
    path = create_legacy_database(tmp_path, score_count=3)

    db = Database(str(path))
    try:
        assert db.schema_version == 2
        assert len(db.get_all_scores()) == 3
        assert db.get_settings_value("legacy_preference") == "preserve this exactly"
    finally:
        db.close()

    backups = list(tmp_path.glob("*.pre-v2.sqlite3"))
    assert len(backups) == 1
    backup = sqlite3.connect(backups[0])
    try:
        assert backup.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 3
        assert backup.execute(
            "SELECT value FROM settings WHERE key = 'legacy_preference'"
        ).fetchone()[0] == "preserve this exactly"
        assert "schema_migrations" not in sqlite_table_names(backups[0])
    finally:
        backup.close()


def test_migration_adds_definition_and_import_status_tables(tmp_path):
    db = Database(str(tmp_path / "migrated.sqlite3"))
    try:
        assert {
            "benchmark_definition_sets", "import_failures", "schema_migrations",
        } <= db.table_names()
    finally:
        db.close()


def test_apply_migrations_accepts_a_plain_sqlite_connection(tmp_path):
    migrations = importlib.import_module("models.migrations")
    path = tmp_path / "plain.sqlite3"
    connection = sqlite3.connect(path)
    try:
        assert migrations.apply_migrations(
            connection, lambda version: tmp_path / f"plain.pre-v{version + 1}.sqlite3",
        ) == 2
        assert "schema_migrations" in sqlite_table_names(path)
    finally:
        connection.close()


def test_reopening_migrated_legacy_database_does_not_make_another_backup(tmp_path):
    path = create_legacy_database(tmp_path)
    first = Database(str(path))
    first.close()
    backups_after_first_open = list(tmp_path.glob("*.pre-v2.sqlite3"))

    second = Database(str(path))
    try:
        assert second.schema_version == 2
        assert len(second.get_all_scores()) == 3
        assert list(tmp_path.glob("*.pre-v2.sqlite3")) == backups_after_first_open
        versions = second.conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        assert [row["version"] for row in versions] == [1, 2]
    finally:
        second.close()


def test_definition_metadata_and_import_failures_are_persisted(tmp_path):
    db = Database(str(tmp_path / "metadata.sqlite3"))
    try:
        db.save_definition_metadata(
            version="kovaaks_s5",
            source_url="https://app.voltaic.gg/benchmarks",
            retrieved_at="2026-08-30T12:00:00",
            checksum="a" * 64,
            payload={"version": "kovaaks_s5"},
            active=True,
        )
        db.record_import_error("bad.csv", "malformed result")
        db.record_import_error("bad.csv", "still malformed")

        definition = db.conn.execute(
            "SELECT version, source_url, retrieved_at, checksum, active, payload_json "
            "FROM benchmark_definition_sets"
        ).fetchone()
        failure = db.get_import_failure("bad.csv")
        assert tuple(definition) == (
            "kovaaks_s5", "https://app.voltaic.gg/benchmarks",
            "2026-08-30T12:00:00", "a" * 64, 1,
            '{"version": "kovaaks_s5"}',
        )
        assert failure["error_text"] == "still malformed"
        assert failure["retry_count"] == 2
        assert failure["first_failed_at"] == failure["last_failed_at"]

        db.clear_import_error("bad.csv")
        assert db.get_import_failure("bad.csv") is None
    finally:
        db.close()


def test_failed_migration_rolls_back_its_schema_changes(tmp_path, monkeypatch):
    migrations = importlib.import_module("models.migrations")

    def half_create_then_fail(connection):
        connection.execute("CREATE TABLE half_created (value TEXT)")
        raise RuntimeError("forced migration failure")

    failing = migrations.Migration(3, "forced failure", half_create_then_fail)
    monkeypatch.setattr(
        migrations, "MIGRATIONS", migrations.MIGRATIONS + (failing,),
    )
    path = tmp_path / "failed.sqlite3"

    with pytest.raises(RuntimeError, match="forced migration failure"):
        Database(str(path))

    assert "half_created" not in sqlite_table_names(path)
