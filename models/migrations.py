"""Ordered, transactional SQLite schema migrations for Aim Companion."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


class UnsafeMigrationOperationError(RuntimeError):
    """Raised when a migration attempts an operation that breaks atomicity."""


class MigrationConnection:
    """The transaction-safe SQLite operations available to migration functions."""

    def __init__(self, connection: sqlite3.Connection):
        self._connection = connection

    def execute(self, sql: str, parameters: object = ()) -> sqlite3.Cursor:
        self._ensure_transaction_safe(sql)
        return self._connection.execute(sql, parameters)

    def executemany(self, sql: str, parameters: object) -> sqlite3.Cursor:
        self._ensure_transaction_safe(sql)
        return self._connection.executemany(sql, parameters)

    def executescript(self, script: str) -> None:
        raise UnsafeMigrationOperationError(
            "executescript is not permitted in migrations; use execute for each statement"
        )

    @staticmethod
    def _ensure_transaction_safe(sql: str) -> None:
        transaction_controls = (
            "BEGIN", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE",
        )
        if MigrationConnection._leading_token(sql) in transaction_controls:
            raise UnsafeMigrationOperationError(
                "transaction control is not permitted in migrations"
            )

    @staticmethod
    def _leading_token(sql: str) -> str:
        """Read one SQLite token after whitespace and leading comments only."""
        position = 0
        while True:
            while position < len(sql) and (
                sql[position].isspace() or sql[position] in {"\ufeff", ";"}
            ):
                position += 1
            if sql.startswith("--", position):
                newline = sql.find("\n", position + 2)
                if newline == -1:
                    return ""
                position = newline + 1
                continue
            if sql.startswith("/*", position):
                comment_end = sql.find("*/", position + 2)
                if comment_end == -1:
                    return ""
                position = comment_end + 2
                continue
            break

        token_end = position
        while token_end < len(sql) and sql[token_end].isalpha():
            token_end += 1
        return sql[position:token_end].upper()


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: Callable[[MigrationConnection], None]


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }


def _ensure_columns(
    connection: MigrationConnection, table: str, columns: dict[str, str],
) -> None:
    existing = {
        row[1] for row in connection.execute(f"PRAGMA table_info({table})")
    }
    for name, definition in columns.items():
        if name not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _create_schema_migrations_table(connection: MigrationConnection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        )
    """)


def baseline_existing_schema(connection: MigrationConnection) -> None:
    """Create the pre-migration schema without rewriting any existing data."""
    _create_schema_migrations_table(connection)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS scores (
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
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_scores_benchmark ON scores(benchmark_name)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_scores_timestamp ON scores(timestamp)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            duration_minutes INTEGER DEFAULT 0,
            focus TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            routine_json TEXT DEFAULT '[]',
            source TEXT DEFAULT 'manual',
            scenario TEXT DEFAULT '',
            runs INTEGER DEFAULT 0,
            warmup INTEGER DEFAULT 0,
            baseline_score REAL,
            outcome_score REAL,
            score_delta_pct REAL
        )
    """)
    _ensure_columns(connection, "sessions", {
        "source": "TEXT DEFAULT 'manual'",
        "scenario": "TEXT DEFAULT ''",
        "runs": "INTEGER DEFAULT 0",
        "warmup": "INTEGER DEFAULT 0",
        "baseline_score": "REAL",
        "outcome_score": "REAL",
        "score_delta_pct": "REAL",
    })
    connection.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            UNIQUE(item_type, item_name)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS scenario_completions (
            scenario TEXT PRIMARY KEY COLLATE NOCASE,
            completed_blocks INTEGER NOT NULL DEFAULT 0,
            completed_runs INTEGER NOT NULL DEFAULT 0,
            warmup_blocks INTEGER NOT NULL DEFAULT 0,
            last_completed_at TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS block_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            scenario TEXT NOT NULL COLLATE NOCASE,
            rating TEXT NOT NULL,
            notes TEXT DEFAULT '',
            category TEXT DEFAULT '',
            subcategory TEXT DEFAULT ''
        )
    """)
    _ensure_columns(connection, "block_feedback", {
        "category": "TEXT DEFAULT ''",
        "subcategory": "TEXT DEFAULT ''",
    })
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_feedback_scenario ON block_feedback(scenario)"
    )
    connection.execute("""
        CREATE TABLE IF NOT EXISTS game_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            game TEXT DEFAULT '',
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            issue TEXT NOT NULL,
            notes TEXT DEFAULT '',
            resolved_at TEXT
        )
    """)
    connection.execute("""
        CREATE INDEX IF NOT EXISTS idx_game_observations_open
        ON game_observations(resolved_at, category, subcategory)
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS imported_files (
            csv_path TEXT PRIMARY KEY,
            imported_at TEXT NOT NULL
        )
    """)


def add_benchmark_metadata_tables(connection: MigrationConnection) -> None:
    """Add durable definition provenance and import-failure state."""
    _create_schema_migrations_table(connection)
    connection.execute("""
        INSERT OR IGNORE INTO schema_migrations (version, name, applied_at)
        VALUES (1, 'baseline', ?)
    """, (datetime.now().isoformat(timespec="seconds"),))
    connection.execute("""
        CREATE TABLE IF NOT EXISTS benchmark_definition_sets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL UNIQUE,
            source_url TEXT NOT NULL,
            retrieved_at TEXT NOT NULL,
            checksum TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0, 1)),
            payload_json TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS import_failures (
            path TEXT PRIMARY KEY,
            error_text TEXT NOT NULL,
            first_failed_at TEXT NOT NULL,
            last_failed_at TEXT NOT NULL,
            retry_count INTEGER NOT NULL DEFAULT 1
        )
    """)


def add_score_import_identity(connection: MigrationConnection) -> None:
    """Track the content last imported for each normalized score path."""
    _ensure_columns(connection, "imported_files", {"content_sha256": "TEXT"})


def add_guided_session_tables(connection: MigrationConnection) -> None:
    """Persist immutable plans, current state, and confirmed run boundaries."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS session_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL CHECK(mode IN ('warmup', 'step_by_step', 'full_routine')),
            source_id TEXT NOT NULL,
            source_version TEXT NOT NULL,
            start_boundary INTEGER NOT NULL DEFAULT 0,
            initial_confirmed_runs INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS session_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL REFERENCES session_plans(id) ON DELETE CASCADE,
            execution_index INTEGER NOT NULL,
            official_index INTEGER NOT NULL,
            scenario TEXT NOT NULL,
            required_runs INTEGER NOT NULL CHECK(required_runs > 0),
            estimated_seconds INTEGER NOT NULL CHECK(estimated_seconds > 0),
            category TEXT NOT NULL,
            subcategory TEXT NOT NULL,
            guide_json TEXT NOT NULL,
            source TEXT NOT NULL,
            source_url TEXT NOT NULL,
            UNIQUE(plan_id, execution_index),
            UNIQUE(plan_id, official_index)
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS session_state (
            plan_id INTEGER PRIMARY KEY REFERENCES session_plans(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK(status IN ('ready', 'running', 'paused', 'stopped', 'completed')),
            current_step_index INTEGER NOT NULL,
            confirmed_runs INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            stop_reason TEXT NOT NULL DEFAULT '',
            owner_token TEXT NOT NULL DEFAULT ''
        )
    """)
    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS one_active_session
        ON session_state((1))
        WHERE status IN ('ready', 'running', 'paused')
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS session_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL REFERENCES session_plans(id) ON DELETE CASCADE,
            step_index INTEGER NOT NULL,
            run_index INTEGER NOT NULL,
            confirmed_at TEXT NOT NULL,
            confirmation_source TEXT NOT NULL DEFAULT 'state',
            UNIQUE(plan_id, step_index, run_index)
        )
    """)


def add_subcategory_activity(connection: MigrationConnection) -> None:
    """Track benchmark age in relevant completed blocks."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS subcategory_activity (
            subcategory TEXT PRIMARY KEY,
            measured INTEGER NOT NULL DEFAULT 0 CHECK(measured IN (0, 1)),
            blocks_since_check INTEGER NOT NULL DEFAULT 0 CHECK(blocks_since_check >= 0),
            last_benchmark_at TEXT,
            updated_at TEXT NOT NULL
        )
    """)


def add_coaching_preferences(connection: MigrationConnection) -> None:
    """Remember warm-up intent and accepted recommendation rotation."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS warmup_preference (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            context TEXT NOT NULL,
            target_id TEXT NOT NULL
        )
    """)


def add_session_run_identity(connection: MigrationConnection) -> None:
    """Prevent one detected Kovaak's result from advancing twice."""
    _ensure_columns(connection, "session_runs", {"result_identity": "TEXT"})
    connection.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS unique_session_result_identity
        ON session_runs(result_identity)
        WHERE result_identity IS NOT NULL AND result_identity != ''
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS coaching_rotation_state (
            id INTEGER PRIMARY KEY CHECK(id = 1),
            cursor INTEGER NOT NULL DEFAULT 0 CHECK(cursor >= 0),
            last_scenario TEXT NOT NULL DEFAULT '',
            last_subcategory TEXT NOT NULL DEFAULT ''
        )
    """)


MIGRATIONS = (
    Migration(1, "baseline", baseline_existing_schema),
    Migration(2, "benchmark_metadata", add_benchmark_metadata_tables),
    Migration(3, "score_import_identity", add_score_import_identity),
    Migration(4, "guided_sessions", add_guided_session_tables),
    Migration(5, "subcategory_activity", add_subcategory_activity),
    Migration(6, "coaching_preferences", add_coaching_preferences),
    Migration(7, "session_run_identity", add_session_run_identity),
)


def read_schema_version(connection: sqlite3.Connection) -> int:
    tables = _table_names(connection)
    if "schema_migrations" in tables:
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()
        return int(row[0])
    if {"scores", "settings"} <= tables:
        return 1
    return 0


def _backup_database(
    connection: sqlite3.Connection, destination: Path,
) -> None:
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing pre-migration backup: {destination}"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = sqlite3.connect(destination)
    try:
        connection.backup(backup)
    finally:
        backup.close()


def record_migration(connection: MigrationConnection, migration: Migration) -> None:
    connection.execute("""
        INSERT OR IGNORE INTO schema_migrations (version, name, applied_at)
        VALUES (?, ?, ?)
    """, (
        migration.version,
        migration.name,
        datetime.now().isoformat(timespec="seconds"),
    ))


def apply_migrations(
    connection: sqlite3.Connection,
    backup_path_factory: Callable[[int], Path],
) -> int:
    """Apply each pending migration atomically, backing up existing schemas first."""
    current = read_schema_version(connection)
    pending = [migration for migration in MIGRATIONS if migration.version > current]
    if pending and current > 0:
        _backup_database(connection, backup_path_factory(current))
    if pending and current >= 1:
        savepoint = "repair_baseline"
        connection.execute(f"SAVEPOINT {savepoint}")
        migration_connection = MigrationConnection(connection)
        try:
            baseline_existing_schema(migration_connection)
            baseline = next(item for item in MIGRATIONS if item.version == 1)
            record_migration(migration_connection, baseline)
        except Exception:
            try:
                connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            except sqlite3.Error:
                pass
            raise
        else:
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
    for migration in pending:
        savepoint = f"migration_{migration.version}"
        connection.execute(f"SAVEPOINT {savepoint}")
        migration_connection = MigrationConnection(connection)
        try:
            migration.apply(migration_connection)
            record_migration(migration_connection, migration)
        except Exception:
            try:
                connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                connection.execute(f"RELEASE SAVEPOINT {savepoint}")
            except sqlite3.Error:
                pass
            raise
        else:
            connection.execute(f"RELEASE SAVEPOINT {savepoint}")
    return read_schema_version(connection)
