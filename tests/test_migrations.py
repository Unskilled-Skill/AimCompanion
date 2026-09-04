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


def add_immediately_prior_v1_tables(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute("""
        CREATE TABLE sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 0,
            focus TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            routine_json TEXT DEFAULT '[]'
        )
    """)
    connection.execute("""
        CREATE TABLE imported_files (
            csv_path TEXT PRIMARY KEY,
            imported_at TEXT NOT NULL
        )
    """)
    connection.execute(
        "INSERT INTO sessions (timestamp, focus) VALUES (?, ?)",
        ("2026-08-30T12:00:00", "preserve prior session"),
    )
    connection.execute(
        "INSERT INTO imported_files (csv_path, imported_at) VALUES (?, ?)",
        ("prior.csv", "2026-08-30T12:01:00"),
    )
    connection.commit()
    connection.close()


def create_complete_v1_database(tmp_path: Path) -> Path:
    """Create an unversioned database containing every released v1 object."""
    migrations = importlib.import_module("models.migrations")
    path = create_legacy_database(tmp_path, score_count=1)
    connection = sqlite3.connect(path)
    migrations.baseline_existing_schema(migrations.MigrationConnection(connection))
    connection.execute(
        "INSERT INTO sessions (timestamp, focus, notes) VALUES (?, ?, ?)",
        ("2026-08-30T12:00:00", "Clicking", "preserve session"),
    )
    connection.execute(
        "INSERT INTO favorites (item_type, item_name) VALUES (?, ?)",
        ("scenario", "Preserved favorite"),
    )
    connection.execute("""
        INSERT INTO scenario_completions (
            scenario, completed_blocks, completed_runs, warmup_blocks,
            last_completed_at
        ) VALUES (?, ?, ?, ?, ?)
    """, ("Preserved scenario", 2, 8, 1, "2026-08-30T12:01:00"))
    connection.execute("""
        INSERT INTO block_feedback (
            timestamp, scenario, rating, notes, category, subcategory
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "2026-08-30T12:02:00", "Preserved scenario", "good",
        "preserve feedback", "Clicking", "Static",
    ))
    connection.execute("""
        INSERT INTO game_observations (
            timestamp, game, category, subcategory, issue, notes
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "2026-08-30T12:03:00", "Test game", "Tracking", "Reactive",
        "preserved issue", "preserve observation",
    ))
    connection.execute(
        "INSERT INTO imported_files (csv_path, imported_at) VALUES (?, ?)",
        ("complete-v1.csv", "2026-08-30T12:04:00"),
    )
    connection.execute("DROP TABLE schema_migrations")
    connection.commit()
    connection.close()
    return path


def test_fresh_database_reaches_current_schema_without_pre_migration_backup(tmp_path):
    path = tmp_path / "fresh.sqlite3"

    db = Database(str(path))
    try:
        assert db.schema_version == 4
        assert not list(tmp_path.glob("*.pre-v*.sqlite3"))
    finally:
        db.close()


def test_v1_database_is_backed_up_and_migrated_without_score_or_setting_loss(tmp_path):
    path = create_legacy_database(tmp_path, score_count=3)

    db = Database(str(path))
    try:
        assert db.schema_version == 4
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


def test_partial_inferred_v1_repairs_missing_baseline_objects_before_v2(tmp_path):
    path = create_legacy_database(tmp_path, score_count=1)

    db = Database(str(path))
    try:
        assert len(db.get_all_scores()) == 1
        assert db.get_sessions() == []
        assert db.get_imported_score_paths() == {"legacy-0.csv"}
        assert {
            "sessions",
            "favorites",
            "scenario_completions",
            "block_feedback",
            "game_observations",
            "imported_files",
        } <= db.table_names()
    finally:
        db.close()


def test_complete_v1_upgrades_without_losing_representative_user_rows(tmp_path):
    path = create_complete_v1_database(tmp_path)

    db = Database(str(path))
    try:
        assert db.schema_version == 4
        assert len(db.get_all_scores()) == 1
        assert db.get_settings_value("legacy_preference") == "preserve this exactly"
        assert db.get_sessions()[0]["notes"] == "preserve session"
        assert db.is_favorite("scenario", "Preserved favorite")
        assert db.get_scenario_completion("Preserved scenario")["completed_runs"] == 8
        assert (
            db.get_scenario_feedback_summary()["preserved scenario"]["ratings"]["good"]
            == 1
        )
        assert db.get_open_game_observations()[0]["issue"] == "preserved issue"
        assert db.get_imported_score_paths() == {"legacy-0.csv", "complete-v1.csv"}
    finally:
        db.close()


def test_immediately_prior_v1_repairs_columns_without_losing_rows(tmp_path):
    path = create_legacy_database(tmp_path, score_count=1)
    add_immediately_prior_v1_tables(path)

    db = Database(str(path))
    try:
        session_columns = {
            row["name"] for row in db.conn.execute("PRAGMA table_info(sessions)")
        }
        assert {
            "source",
            "scenario",
            "runs",
            "warmup",
            "baseline_score",
            "outcome_score",
            "score_delta_pct",
        } <= session_columns
        assert db.get_sessions()[0]["focus"] == "preserve prior session"
        assert db.get_imported_score_paths() == {"prior.csv", "legacy-0.csv"}
    finally:
        db.close()


def test_migration_adds_definition_and_import_status_tables(tmp_path):
    db = Database(str(tmp_path / "migrated.sqlite3"))
    try:
        assert {
            "benchmark_definition_sets", "import_failures", "schema_migrations",
        } <= db.table_names()
    finally:
        db.close()


def test_migration_adds_content_identity_to_imported_files(tmp_path):
    db = Database(str(tmp_path / "content-identity.sqlite3"))
    try:
        columns = {
            row["name"] for row in db.conn.execute("PRAGMA table_info(imported_files)")
        }
        assert "content_sha256" in columns
    finally:
        db.close()


def test_v2_database_upgrades_import_identity_without_losing_path_rows(tmp_path):
    migrations = importlib.import_module("models.migrations")
    path = tmp_path / "v2.sqlite3"
    connection = sqlite3.connect(path)
    migration_connection = migrations.MigrationConnection(connection)
    migrations.baseline_existing_schema(migration_connection)
    migrations.add_benchmark_metadata_tables(migration_connection)
    migrations.record_migration(migration_connection, migrations.MIGRATIONS[1])
    connection.execute(
        "INSERT INTO imported_files (csv_path, imported_at) VALUES (?, ?)",
        ("preserved.csv", "2026-08-30T12:00:00"),
    )
    connection.commit()
    connection.close()

    db = Database(str(path))
    try:
        assert db.schema_version == 4
        assert db.get_imported_score_files() == {"preserved.csv": None}
    finally:
        db.close()

    assert len(list(tmp_path.glob("v2.pre-v3.sqlite3"))) == 1


def test_apply_migrations_accepts_a_plain_sqlite_connection(tmp_path):
    migrations = importlib.import_module("models.migrations")
    path = tmp_path / "plain.sqlite3"
    connection = sqlite3.connect(path)
    try:
        assert migrations.apply_migrations(
            connection, lambda version: tmp_path / f"plain.pre-v{version + 1}.sqlite3",
        ) == 4
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
        assert second.schema_version == 4
        assert len(second.get_all_scores()) == 3
        assert list(tmp_path.glob("*.pre-v2.sqlite3")) == backups_after_first_open
        versions = second.conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        ).fetchall()
        assert [row["version"] for row in versions] == [1, 2, 3, 4]
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

    failing = migrations.Migration(4, "forced failure", half_create_then_fail)
    monkeypatch.setattr(
        migrations, "MIGRATIONS", migrations.MIGRATIONS + (failing,),
    )
    path = tmp_path / "failed.sqlite3"

    with pytest.raises(RuntimeError, match="forced migration failure"):
        Database(str(path))

    assert "half_created" not in sqlite_table_names(path)


def test_executescript_migration_cannot_commit_partial_schema(tmp_path, monkeypatch):
    migrations = importlib.import_module("models.migrations")

    def script_then_fail(connection):
        connection.executescript("CREATE TABLE half_created (value TEXT);")
        raise RuntimeError("forced migration failure")

    failing = migrations.Migration(4, "script failure", script_then_fail)
    monkeypatch.setattr(
        migrations, "MIGRATIONS", migrations.MIGRATIONS + (failing,),
    )
    path = tmp_path / "script-failed.sqlite3"

    with pytest.raises(
        migrations.UnsafeMigrationOperationError, match="executescript"
    ):
        Database(str(path))

    assert "half_created" not in sqlite_table_names(path)


def test_migration_cannot_execute_transaction_control_statements(tmp_path, monkeypatch):
    migrations = importlib.import_module("models.migrations")

    def commit_then_fail(connection):
        connection.execute("COMMIT")
        connection.execute("CREATE TABLE half_created (value TEXT)")
        raise RuntimeError("forced migration failure")

    failing = migrations.Migration(4, "commit failure", commit_then_fail)
    monkeypatch.setattr(
        migrations, "MIGRATIONS", migrations.MIGRATIONS + (failing,),
    )
    path = tmp_path / "commit-failed.sqlite3"

    with pytest.raises(
        migrations.UnsafeMigrationOperationError, match="transaction control"
    ):
        Database(str(path))

    assert "half_created" not in sqlite_table_names(path)


@pytest.mark.parametrize("statement", [
    "/* leading comment */ COMMIT",
    "/* first */ -- second\n /* third */ RELEASE SAVEPOINT migration_4",
    "-- leading comment\n\tCOMMIT",
    "\ufeffCOMMIT",
    "; ; -- empty statements\n /* comment */ RELEASE SAVEPOINT migration_4",
])
def test_migration_rejects_comment_prefixed_transaction_control(
    tmp_path, monkeypatch, statement,
):
    migrations = importlib.import_module("models.migrations")

    def control_then_fail(connection):
        connection.execute(statement)
        connection.execute("CREATE TABLE half_created (value TEXT)")
        raise RuntimeError("forced migration failure")

    failing = migrations.Migration(4, "commented control", control_then_fail)
    monkeypatch.setattr(
        migrations, "MIGRATIONS", migrations.MIGRATIONS + (failing,),
    )
    path = tmp_path / "commented-control.sqlite3"

    with pytest.raises(
        migrations.UnsafeMigrationOperationError, match="transaction control"
    ):
        Database(str(path))

    assert "half_created" not in sqlite_table_names(path)


def test_executemany_rejects_comment_prefixed_transaction_control(tmp_path, monkeypatch):
    migrations = importlib.import_module("models.migrations")

    def commit_then_fail(connection):
        connection.executemany("/* comment */ COMMIT", [()])
        raise RuntimeError("forced migration failure")

    failing = migrations.Migration(4, "commented batch control", commit_then_fail)
    monkeypatch.setattr(
        migrations, "MIGRATIONS", migrations.MIGRATIONS + (failing,),
    )
    path = tmp_path / "commented-batch-control.sqlite3"

    with pytest.raises(
        migrations.UnsafeMigrationOperationError, match="transaction control"
    ):
        Database(str(path))


def test_migration_allows_transaction_words_outside_the_leading_token(
    tmp_path, monkeypatch,
):
    migrations = importlib.import_module("models.migrations")

    def create_then_fail(connection):
        connection.execute("""
            CREATE TABLE messages (
                note TEXT DEFAULT 'COMMIT' -- RELEASE is only a trailing comment
            )
        """)
        raise RuntimeError("forced migration failure")

    failing = migrations.Migration(4, "ordinary SQL", create_then_fail)
    monkeypatch.setattr(
        migrations, "MIGRATIONS", migrations.MIGRATIONS + (failing,),
    )
    path = tmp_path / "ordinary-sql.sqlite3"

    with pytest.raises(RuntimeError, match="forced migration failure"):
        Database(str(path))

    assert "messages" not in sqlite_table_names(path)
