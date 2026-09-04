"""Per-subcategory benchmark freshness measured in completed training blocks."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal


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
