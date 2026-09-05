"""Per-subcategory benchmark freshness measured in completed training blocks."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from core.benchmarks.definitions import normalize_alias
from models.score import Score


def _as_utc(value: datetime | str) -> datetime:
    timestamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    if timestamp.tzinfo is None:
        timestamp = timestamp.astimezone()
    return timestamp.astimezone(timezone.utc)


@dataclass(frozen=True)
class FreshnessState:
    subcategory: str
    measured: bool
    blocks_since_check: int
    due: bool
    confidence: Literal["missing", "stale", "current"]


class BenchmarkFreshness:
    STALE_AFTER_BLOCKS = 12

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    def record_block(self, subcategories, warmup: bool) -> None:
        if warmup:
            return
        names = sorted({str(name).strip() for name in subcategories if str(name).strip()})
        if not names:
            return
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connection:
            for name in names:
                self.connection.execute("""
                    INSERT INTO subcategory_activity (
                        subcategory, measured, blocks_since_check, updated_at
                    ) VALUES (?, 0, 1, ?)
                    ON CONFLICT(subcategory) DO UPDATE SET
                        blocks_since_check = subcategory_activity.blocks_since_check + 1,
                        updated_at = excluded.updated_at
                """, (name, timestamp))

    def record_benchmark(self, subcategory: str) -> None:
        name = subcategory.strip()
        if not name:
            raise ValueError("subcategory is required")
        timestamp = datetime.now(timezone.utc).isoformat()
        with self.connection:
            self.connection.execute("""
                INSERT INTO subcategory_activity (
                    subcategory, measured, blocks_since_check,
                    last_benchmark_at, updated_at
                ) VALUES (?, 1, 0, ?, ?)
                ON CONFLICT(subcategory) DO UPDATE SET
                    measured = 1,
                    blocks_since_check = 0,
                    last_benchmark_at = excluded.last_benchmark_at,
                    updated_at = excluded.updated_at
            """, (name, timestamp, timestamp))

    def reconcile(self, scores: list["Score"], definitions=None) -> set[str]:
        """Refresh official subcategories only when a newer score is available.

        When definitions are supplied, only scores matching that official
        benchmark set are eligible. Historical scores are idempotent so later
        training blocks remain counted toward the next freshness check.

        Returns the set of subcategory keys that were written/refreshed.
        """

        scored: dict[str, datetime] = {}
        official = None
        if definitions is not None:
            official = {}
            for benchmark in definitions.benchmarks:
                for alias in (
                    benchmark.name, benchmark.scenario, *benchmark.aliases,
                ):
                    official[normalize_alias(alias)] = benchmark

        for score in scores:
            if not isinstance(score, Score):
                continue
            benchmark = None
            if official is not None:
                for candidate in (score.benchmark_name, score.scenario):
                    benchmark = official.get(normalize_alias(candidate))
                    if benchmark is not None:
                        break
                if benchmark is None or (
                    score.difficulty.casefold() != benchmark.difficulty.casefold()
                ):
                    continue
            cat = benchmark.category if benchmark else getattr(score, "category", "")
            sub = benchmark.subcategory if benchmark else getattr(score, "subcategory", "")
            if not cat or not sub or cat == "Unknown" or sub == "Unknown":
                continue
            key = f"{cat} / {sub}"
            ts = _as_utc(score.timestamp)
            if key not in scored or ts > scored[key]:
                scored[key] = ts

        refreshed = set()
        with self.connection:
            for key, ts in scored.items():
                row = self.connection.execute(
                    "SELECT last_benchmark_at FROM subcategory_activity "
                    "WHERE subcategory = ?",
                    (key,),
                ).fetchone()
                if row is not None and row["last_benchmark_at"] is not None:
                    if _as_utc(str(row["last_benchmark_at"])) >= ts:
                        continue
                timestamp = ts.isoformat()
                self.connection.execute("""
                    INSERT INTO subcategory_activity (
                        subcategory, measured, blocks_since_check,
                        last_benchmark_at, updated_at
                    ) VALUES (?, 1, 0, ?, ?)
                    ON CONFLICT(subcategory) DO UPDATE SET
                        measured = 1,
                        blocks_since_check = 0,
                        last_benchmark_at = excluded.last_benchmark_at,
                        updated_at = excluded.updated_at
                """, (key, timestamp, timestamp))
                refreshed.add(key)

        return refreshed

    def status(self, required_subcategories) -> dict[str, FreshnessState]:
        names = tuple(dict.fromkeys(str(name).strip() for name in required_subcategories))
        rows = {
            row["subcategory"]: row
            for row in self.connection.execute(
                "SELECT * FROM subcategory_activity"
            ).fetchall()
        }
        result = {}
        for name in names:
            row = rows.get(name)
            if row is None or not bool(row["measured"]):
                result[name] = FreshnessState(name, False, 0 if row is None else int(row["blocks_since_check"]), True, "missing")
                continue
            blocks = int(row["blocks_since_check"])
            due = blocks >= self.STALE_AFTER_BLOCKS
            result[name] = FreshnessState(
                name,
                True,
                blocks,
                due,
                "stale" if due else "current",
            )
        return result
