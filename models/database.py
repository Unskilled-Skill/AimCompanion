import json
import os
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from models.score import Score
from models.migrations import apply_migrations
from core.paths import writable_path

DB_PATH = writable_path("kovaaks.db")


class Database:
    def __init__(
        self,
        db_path: str = DB_PATH,
        backup_path_factory: Callable[[int], Path] | None = None,
    ):
        self.db_path = db_path
        self._backup_path_factory = backup_path_factory or self._default_backup_path
        self.conn = sqlite3.connect(db_path, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout = 10000")
        if db_path != ":memory:":
            self.conn.execute("PRAGMA journal_mode = WAL")
        try:
            self.schema_version = self._create_tables()
        except Exception:
            self.conn.close()
            raise

    def _default_backup_path(self, current_version: int) -> Path:
        """Return a new, adjacent path without overwriting an earlier backup."""
        database_path = Path(self.db_path)
        target_version = current_version + 1
        candidate = database_path.with_name(
            f"{database_path.stem}.pre-v{target_version}.sqlite3"
        )
        sequence = 1
        while candidate.exists():
            candidate = database_path.with_name(
                f"{database_path.stem}.pre-v{target_version}-{sequence}.sqlite3"
            )
            sequence += 1
        return candidate

    def _create_tables(self) -> int:
        return apply_migrations(self.conn, self._backup_path_factory)

    def table_names(self) -> set[str]:
        return {
            row["name"] for row in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }

    def score_exists(self, csv_path: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM scores WHERE csv_path = ?", (csv_path,)
        )
        return cur.fetchone() is not None

    def get_imported_score_paths(self) -> set[str]:
        rows = self.conn.execute(
            """
            SELECT csv_path FROM scores WHERE csv_path IS NOT NULL AND csv_path != ''
            UNION
            SELECT csv_path FROM imported_files
            """
        ).fetchall()
        return {row["csv_path"] for row in rows}

    def mark_score_path_imported(self, csv_path: str, *, commit: bool = True):
        if not csv_path:
            return
        self.conn.execute("""
            INSERT OR IGNORE INTO imported_files (csv_path, imported_at)
            VALUES (?, ?)
        """, (csv_path, datetime.now().isoformat(timespec="seconds")))
        if commit:
            self.conn.commit()

    def score_record_exists(self, score: Score) -> bool:
        row = self.conn.execute("""
            SELECT 1 FROM scores
            WHERE scenario = ? COLLATE NOCASE AND timestamp = ? AND score = ?
            LIMIT 1
        """, (score.scenario, score.timestamp.isoformat(), score.score)).fetchone()
        return row is not None

    def insert_score(
        self, score: Score, csv_path: str = "", *, commit: bool = True,
    ):
        self.conn.execute("""
            INSERT OR REPLACE INTO scores
            (benchmark_name, scenario, category, subcategory, difficulty,
             score, timestamp, kills, hits, misses, fight_time, avg_ttk,
             accuracy, avg_fps, resolution, csv_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            score.benchmark_name, score.scenario, score.category,
            score.subcategory, score.difficulty, score.score,
            score.timestamp.isoformat(), score.kills, score.hits,
            score.misses, score.fight_time, score.avg_ttk,
            score.accuracy, score.avg_fps, score.resolution, csv_path
        ))
        if csv_path:
            self.conn.execute("""
                INSERT OR IGNORE INTO imported_files (csv_path, imported_at)
                VALUES (?, ?)
            """, (csv_path, datetime.now().isoformat(timespec="seconds")))
        if commit:
            self.conn.commit()

    def get_all_scores(self) -> list[Score]:
        rows = self.conn.execute(
            "SELECT * FROM scores ORDER BY timestamp ASC"
        ).fetchall()
        return [self._row_to_score(row) for row in rows]

    def get_latest_scores(self, difficulty: str = None) -> list[Score]:
        query = """
            SELECT s.* FROM scores s
            INNER JOIN (
                SELECT benchmark_name, MAX(timestamp) as max_ts
                FROM scores
                GROUP BY benchmark_name
            ) latest ON s.benchmark_name = latest.benchmark_name
                       AND s.timestamp = latest.max_ts
        """
        rows = self.conn.execute(query).fetchall()
        return [self._row_to_score(r) for r in rows]

    def get_best_scores(self, difficulty: str = None) -> list[Score]:
        query = """
            SELECT s.* FROM scores s
            INNER JOIN (
                SELECT benchmark_name, MAX(score) as max_score
                FROM scores
                GROUP BY benchmark_name
            ) best ON s.benchmark_name = best.benchmark_name
                     AND s.score = best.max_score
        """
        rows = self.conn.execute(query).fetchall()
        return [self._row_to_score(r) for r in rows]

    def get_score_history(self, benchmark_name: str) -> list[Score]:
        rows = self.conn.execute(
            "SELECT * FROM scores WHERE benchmark_name = ? ORDER BY timestamp ASC",
            (benchmark_name,)
        ).fetchall()
        return [self._row_to_score(r) for r in rows]

    def get_all_benchmarks(self) -> list[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT benchmark_name FROM scores ORDER BY benchmark_name"
        ).fetchall()
        return [r["benchmark_name"] for r in rows]

    def get_total_attempts(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM scores").fetchone()
        return row["cnt"]

    def get_most_recent_per_benchmark(self) -> list[Score]:
        rows = self.conn.execute("""
            SELECT s.* FROM scores s
            INNER JOIN (
                SELECT benchmark_name, MAX(timestamp) as max_ts
                FROM scores
                GROUP BY benchmark_name
            ) latest ON s.benchmark_name = latest.benchmark_name
                       AND s.timestamp = latest.max_ts
        """).fetchall()
        return [self._row_to_score(r) for r in rows]

    def get_recent_scores_per_benchmark(self, days: int = 30) -> list[Score]:
        rows = self.conn.execute("""
            SELECT s.* FROM scores s
            INNER JOIN (
                SELECT benchmark_name, MAX(timestamp) as max_ts
                FROM scores
                WHERE timestamp >= datetime('now', ?)
                GROUP BY benchmark_name
            ) recent ON s.benchmark_name = recent.benchmark_name
                       AND s.timestamp = recent.max_ts
        """, (f"-{days} days",)).fetchall()
        return [self._row_to_score(r) for r in rows]

    def get_average_recent_scores(self, n: int = 5) -> list[Score]:
        rows = self.conn.execute("""
            SELECT benchmark_name, AVG(score) as avg_score, COUNT(*) as cnt
            FROM (
                SELECT benchmark_name, score,
                       ROW_NUMBER() OVER (
                           PARTITION BY benchmark_name ORDER BY timestamp DESC
                       ) as rn
                FROM scores
            )
            WHERE rn <= ?
            GROUP BY benchmark_name
        """, (n,)).fetchall()
        results = []
        for r in rows:
            results.append(Score(
                benchmark_name=r["benchmark_name"],
                scenario=r["benchmark_name"],
                category="",
                subcategory="",
                difficulty="",
                score=r["avg_score"],
                timestamp=datetime.now(),
            ))
        return results

    def get_scores_in_range(self, start: str, end: str) -> list[Score]:
        rows = self.conn.execute("""
            SELECT * FROM scores
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp ASC
        """, (start, end)).fetchall()
        return [self._row_to_score(r) for r in rows]

    def get_pbs(self) -> dict:
        rows = self.conn.execute("""
            SELECT benchmark_name, MAX(score) as best_score, MIN(timestamp) as first_date
            FROM scores
            GROUP BY benchmark_name
        """).fetchall()
        return {r["benchmark_name"]: {
            "best_score": r["best_score"],
            "first_date": r["first_date"],
        } for r in rows}

    def get_new_pbs_since(self, since_date: str) -> list[dict]:
        rows = self.conn.execute("""
            SELECT s.benchmark_name, s.score, s.timestamp,
                   (SELECT MAX(score) FROM scores
                    WHERE benchmark_name = s.benchmark_name
                    AND timestamp < s.timestamp) as prev_best
            FROM scores s
            WHERE s.timestamp >= ?
            AND s.score > COALESCE(
                (SELECT MAX(score) FROM scores
                 WHERE benchmark_name = s.benchmark_name
                 AND timestamp < s.timestamp), 0
            )
            ORDER BY s.timestamp DESC
        """, (since_date,)).fetchall()
        return [dict(r) for r in rows]

    def log_session(
        self, focus: str, duration: int, notes: str = "",
        routine_json: str = "[]", timestamp: str = None,
        source: str = "manual", scenario: str = "", runs: int = 0,
        warmup: bool = False,
    ):
        timestamp = timestamp or datetime.now().isoformat(timespec="seconds")
        self.conn.execute("""
            INSERT INTO sessions
                (timestamp, duration_minutes, focus, notes, routine_json,
                 source, scenario, runs, warmup)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp, duration, focus, notes, routine_json, source,
            scenario, runs, 1 if warmup else 0,
        ))
        self.conn.commit()

    def get_sessions(self, limit: int | None = 50) -> list[dict]:
        query = "SELECT * FROM sessions ORDER BY timestamp DESC"
        if limit is None:
            rows = self.conn.execute(query).fetchall()
        else:
            rows = self.conn.execute(f"{query} LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def add_favorite(self, item_type: str, item_name: str):
        self.conn.execute("""
            INSERT OR IGNORE INTO favorites (item_type, item_name) VALUES (?, ?)
        """, (item_type, item_name))
        self.conn.commit()

    def remove_favorite(self, item_type: str, item_name: str):
        self.conn.execute("""
            DELETE FROM favorites WHERE item_type = ? AND item_name = ?
        """, (item_type, item_name))
        self.conn.commit()

    def get_favorites(self, item_type: str = None) -> list[dict]:
        if item_type:
            rows = self.conn.execute(
                "SELECT * FROM favorites WHERE item_type = ?", (item_type,)
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM favorites").fetchall()
        return [dict(r) for r in rows]

    def is_favorite(self, item_type: str, item_name: str) -> bool:
        cur = self.conn.execute(
            "SELECT 1 FROM favorites WHERE item_type = ? AND item_name = ?",
            (item_type, item_name)
        )
        return cur.fetchone() is not None

    def get_last_session_date(self) -> str | None:
        row = self.conn.execute(
            "SELECT MAX(timestamp) as last_date FROM sessions"
        ).fetchone()
        return row["last_date"] if row and row["last_date"] else None

    def get_total_sessions(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as cnt FROM sessions").fetchone()
        return row["cnt"]

    def get_total_training_minutes(self) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(duration_minutes), 0) as total FROM sessions"
        ).fetchone()
        return row["total"]

    def get_settings_value(self, key: str, default: str = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_settings_value(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        self.conn.commit()

    def save_definition_metadata(
        self,
        version: str,
        source_url: str,
        retrieved_at: str,
        checksum: str,
        payload: object,
        active: bool = True,
    ):
        """Persist a benchmark definition snapshot and its provenance."""
        payload_json = (
            payload if isinstance(payload, str)
            else json.dumps(payload, sort_keys=True)
        )
        with self.conn:
            if active:
                self.conn.execute(
                    "UPDATE benchmark_definition_sets SET active = 0 WHERE active = 1"
                )
            self.conn.execute("""
                INSERT INTO benchmark_definition_sets
                    (version, source_url, retrieved_at, checksum, active, payload_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(version) DO UPDATE SET
                    source_url = excluded.source_url,
                    retrieved_at = excluded.retrieved_at,
                    checksum = excluded.checksum,
                    active = excluded.active,
                    payload_json = excluded.payload_json
            """, (
                version, source_url, retrieved_at, checksum, 1 if active else 0,
                payload_json,
            ))

    def record_import_error(
        self, path: str, error_text: str, *, commit: bool = True,
    ):
        """Record a failed file import while retaining its first failure time."""
        failed_at = datetime.now().isoformat(timespec="seconds")
        self.conn.execute("""
            INSERT INTO import_failures
                (path, error_text, first_failed_at, last_failed_at, retry_count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(path) DO UPDATE SET
                error_text = excluded.error_text,
                last_failed_at = excluded.last_failed_at,
                retry_count = import_failures.retry_count + 1
        """, (path, error_text, failed_at, failed_at))
        if commit:
            self.conn.commit()

    def get_import_failure(self, path: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM import_failures WHERE path = ?", (path,)
        ).fetchone()
        if not row:
            normalized = self._normalized_score_path(path)
            if normalized != path:
                row = self.conn.execute(
                    "SELECT * FROM import_failures WHERE path = ?", (normalized,)
                ).fetchone()
        return dict(row) if row else None

    def clear_import_error(self, path: str, *, commit: bool = True):
        self.conn.execute("DELETE FROM import_failures WHERE path = ?", (path,))
        if commit:
            self.conn.commit()

    @staticmethod
    def _normalized_score_path(path: str) -> str:
        return os.path.normcase(os.path.normpath(os.path.abspath(path)))

    def record_scenario_completion(
        self, scenario: str, runs: int = 3, warmup: bool = False,
        duration_minutes: int = 0, focus: str = "", source: str = "quick",
    ) -> dict:
        """Record a completed block in both scenario totals and activity history."""
        completed_at = datetime.now().isoformat(timespec="seconds")
        routine_json = json.dumps([{
            "scenario": scenario,
            "runs": runs,
            "duration_minutes": duration_minutes,
            "warmup": warmup,
        }])
        baseline, outcome, delta_pct = self._scenario_effectiveness(scenario, runs)
        with self.conn:
            self.conn.execute("""
                INSERT INTO scenario_completions
                    (scenario, completed_blocks, completed_runs, warmup_blocks,
                     last_completed_at)
                VALUES (?, 1, ?, ?, ?)
                ON CONFLICT(scenario) DO UPDATE SET
                    completed_blocks = completed_blocks + 1,
                    completed_runs = completed_runs + excluded.completed_runs,
                    warmup_blocks = warmup_blocks + excluded.warmup_blocks,
                    last_completed_at = excluded.last_completed_at
            """, (scenario, runs, 1 if warmup else 0, completed_at))
            self.conn.execute("""
                INSERT INTO sessions
                    (timestamp, duration_minutes, focus, notes, routine_json,
                     source, scenario, runs, warmup, baseline_score,
                     outcome_score, score_delta_pct)
                VALUES (?, ?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                completed_at, duration_minutes, focus, routine_json, source,
                scenario, runs, 1 if warmup else 0, baseline, outcome, delta_pct,
            ))
        return self.get_scenario_completion(scenario)

    def _scenario_effectiveness(self, scenario: str, completed_runs: int):
        rows = self.conn.execute("""
            SELECT score FROM scores
            WHERE scenario = ? COLLATE NOCASE
            ORDER BY timestamp ASC
        """, (scenario,)).fetchall()
        scores = [row["score"] for row in rows]
        if not scores:
            return None, None, None
        outcome_count = min(max(1, completed_runs), len(scores))
        outcome_scores = scores[-outcome_count:]
        baseline_scores = scores[max(0, len(scores) - outcome_count - 5):-outcome_count]
        outcome = sum(outcome_scores) / len(outcome_scores)
        if len(baseline_scores) < 3:
            return None, outcome, None
        baseline = sum(baseline_scores) / len(baseline_scores)
        delta_pct = ((outcome - baseline) / baseline * 100) if baseline else None
        return baseline, outcome, delta_pct

    def get_recent_effectiveness(self, limit: int = 10) -> list[dict]:
        rows = self.conn.execute("""
            SELECT timestamp, scenario, focus, runs, baseline_score,
                   outcome_score, score_delta_pct
            FROM sessions
            WHERE outcome_score IS NOT NULL AND warmup = 0
            ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

    def get_sessions_since(self, timestamp: str) -> list[dict]:
        rows = self.conn.execute("""
            SELECT * FROM sessions
            WHERE timestamp >= ?
            ORDER BY timestamp ASC
        """, (timestamp,)).fetchall()
        return [dict(row) for row in rows]

    def get_benchmark_days_since(self, timestamp: str) -> list[str]:
        rows = self.conn.execute("""
            SELECT DISTINCT DATE(timestamp) AS day
            FROM scores
            WHERE timestamp >= ? AND category != 'Unknown'
            ORDER BY day ASC
        """, (timestamp,)).fetchall()
        return [row["day"] for row in rows if row["day"]]

    def record_game_observation(
        self, game: str, category: str, subcategory: str,
        issue: str, notes: str = "",
    ) -> int:
        cursor = self.conn.execute("""
            INSERT INTO game_observations
                (timestamp, game, category, subcategory, issue, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(timespec="seconds"), game, category,
            subcategory, issue, notes,
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_open_game_observations(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute("""
            SELECT * FROM game_observations
            WHERE resolved_at IS NULL
            ORDER BY timestamp DESC, id DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(row) for row in rows]

    def get_latest_observation_by_skill(self) -> dict[str, dict]:
        observations = self.get_open_game_observations(limit=200)
        latest = {}
        for observation in observations:
            key = (
                f"{observation['category']} / {observation['subcategory']}"
                .casefold()
            )
            latest.setdefault(key, observation)
        return latest

    def resolve_game_observation(self, observation_id: int):
        self.conn.execute("""
            UPDATE game_observations
            SET resolved_at = ?
            WHERE id = ? AND resolved_at IS NULL
        """, (datetime.now().isoformat(timespec="seconds"), observation_id))
        self.conn.commit()

    def record_block_feedback(
        self, scenario: str, rating: str, notes: str = "",
        category: str = "", subcategory: str = "",
    ):
        allowed = {"too_easy", "productive", "too_hard", "discomfort"}
        if rating not in allowed:
            raise ValueError(f"Unknown feedback rating: {rating}")
        self.conn.execute("""
            INSERT INTO block_feedback
                (timestamp, scenario, rating, notes, category, subcategory)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(timespec="seconds"), scenario, rating,
            notes, category, subcategory,
        ))
        self.conn.commit()

    def get_skill_feedback_summary(self) -> dict[str, dict]:
        rows = self.conn.execute("""
            SELECT category, subcategory, rating, COUNT(*) AS count,
                   MAX(timestamp) AS latest
            FROM block_feedback
            WHERE category != '' AND subcategory != ''
            GROUP BY category COLLATE NOCASE, subcategory COLLATE NOCASE, rating
        """).fetchall()
        summaries = {}
        for row in rows:
            key = f"{row['category']} / {row['subcategory']}".casefold()
            item = summaries.setdefault(key, {"ratings": {}})
            item["ratings"][row["rating"]] = row["count"]
        latest_rows = self.conn.execute("""
            SELECT category, subcategory, rating, notes, timestamp
            FROM block_feedback
            WHERE category != '' AND subcategory != ''
            ORDER BY id DESC
        """).fetchall()
        for row in latest_rows:
            key = f"{row['category']} / {row['subcategory']}".casefold()
            item = summaries.setdefault(key, {"ratings": {}})
            if "latest_rating" not in item:
                item["latest"] = row["timestamp"]
                item["latest_rating"] = row["rating"]
                item["latest_notes"] = row["notes"] or ""
        return summaries

    def get_scenario_feedback_summary(self) -> dict[str, dict]:
        rows = self.conn.execute("""
            SELECT scenario, rating, COUNT(*) AS count, MAX(timestamp) AS latest
            FROM block_feedback
            GROUP BY scenario COLLATE NOCASE, rating
        """).fetchall()
        summaries = {}
        for row in rows:
            item = summaries.setdefault(row["scenario"].casefold(), {
                "scenario": row["scenario"], "ratings": {}, "latest": None,
            })
            item["ratings"][row["rating"]] = row["count"]
            if not item["latest"] or row["latest"] > item["latest"]:
                item["latest"] = row["latest"]
        return summaries

    def get_last_training_by_focus(self) -> dict[str, str]:
        rows = self.conn.execute("""
            SELECT focus, MAX(timestamp) AS latest
            FROM sessions
            WHERE warmup = 0 AND focus LIKE '% / %'
            GROUP BY focus COLLATE NOCASE
        """).fetchall()
        return {row["focus"]: row["latest"] for row in rows}

    def get_scenario_effectiveness_summary(self) -> dict[str, dict]:
        rows = self.conn.execute("""
            SELECT scenario, COUNT(score_delta_pct) AS measured_blocks,
                   AVG(score_delta_pct) AS average_delta_pct
            FROM sessions
            WHERE warmup = 0 AND scenario != ''
            GROUP BY scenario COLLATE NOCASE
        """).fetchall()
        return {row["scenario"].casefold(): dict(row) for row in rows}

    def get_recent_raw_scores(self, limit: int = 50) -> list[Score]:
        rows = self.conn.execute("""
            SELECT * FROM scores ORDER BY timestamp DESC LIMIT ?
        """, (limit,)).fetchall()
        return [self._row_to_score(row) for row in rows]

    def get_scenario_completion(self, scenario: str) -> dict:
        row = self.conn.execute("""
            SELECT completed_blocks, completed_runs, warmup_blocks,
                   last_completed_at
            FROM scenario_completions
            WHERE scenario = ? COLLATE NOCASE
        """, (scenario,)).fetchone()
        if not row:
            return {
                "completed_blocks": 0,
                "completed_runs": 0,
                "warmup_blocks": 0,
                "last_completed_at": None,
            }
        return dict(row)

    def get_scenario_attempt_count(self, scenario: str) -> int:
        """Return actual Kovaak's result files imported for this scenario."""
        row = self.conn.execute("""
            SELECT COUNT(*) AS count
            FROM scores
            WHERE scenario = ? COLLATE NOCASE
        """, (scenario,)).fetchone()
        return row["count"] if row else 0

    def save_routine(self, name: str, routine_json: str):
        self.conn.execute("""
            INSERT OR REPLACE INTO favorites (item_type, item_name)
            VALUES ('routine', ?)
        """, (name,))
        self.conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (f"routine_{name}", routine_json)
        )
        self.conn.commit()

    def get_saved_routines(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT item_name FROM favorites WHERE item_type = 'routine'"
        ).fetchall()
        routines = []
        for r in rows:
            name = r["item_name"]
            val = self.get_settings_value(f"routine_{name}")
            if val:
                try:
                    routines.append({"name": name, "data": json.loads(val)})
                except json.JSONDecodeError:
                    pass
        return routines

    def delete_routine(self, name: str):
        self.conn.execute(
            "DELETE FROM favorites WHERE item_type = 'routine' AND item_name = ?",
            (name,)
        )
        self.conn.execute(
            "DELETE FROM settings WHERE key = ?",
            (f"routine_{name}",)
        )
        self.conn.commit()

    def get_streak(self) -> int:
        rows = self.conn.execute("""
            SELECT DISTINCT day FROM (
                SELECT DATE(timestamp) AS day FROM sessions
                UNION
                SELECT DATE(timestamp) AS day FROM scores
                UNION
                SELECT DATE(last_completed_at) AS day FROM scenario_completions
            )
            WHERE day IS NOT NULL
            ORDER BY day DESC
        """).fetchall()
        if not rows:
            return 0

        streak = 0
        today = datetime.now().date()
        previous_day = None
        for r in rows:
            day = datetime.fromisoformat(r["day"]).date()
            if previous_day is None:
                days_ago = (today - day).days
                if 0 <= days_ago <= 1:
                    streak = 1
                else:
                    break
            else:
                if (previous_day - day).days == 1:
                    streak += 1
                else:
                    break
            previous_day = day

        return streak

    def _row_to_score(self, row) -> Score:
        return Score(
            benchmark_name=row["benchmark_name"],
            scenario=row["scenario"],
            category=row["category"],
            subcategory=row["subcategory"],
            difficulty=row["difficulty"],
            score=row["score"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            kills=row["kills"],
            hits=row["hits"],
            misses=row["misses"],
            fight_time=row["fight_time"],
            avg_ttk=row["avg_ttk"],
            accuracy=row["accuracy"],
            avg_fps=row["avg_fps"],
            resolution=row["resolution"],
        )

    def close(self):
        self.conn.close()

    def backup_to(self, destination: str):
        backup = sqlite3.connect(destination)
        try:
            self.conn.backup(backup)
        finally:
            backup.close()

    def restore_from(self, source_path: str):
        source = sqlite3.connect(source_path)
        try:
            tables = {
                row[0] for row in source.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            if "scores" not in tables or "settings" not in tables:
                raise ValueError("This is not an Aim Companion backup")
            source.backup(self.conn)
            self.conn.commit()
            self._create_tables()
        finally:
            source.close()
