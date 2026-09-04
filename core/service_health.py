"""Shared service-health records for persistent UI status."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
import sqlite3


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ServiceStatus:
    service: str
    state: Literal["ok", "busy", "warning", "error", "offline"]
    summary: str
    details: str
    recovery_action: str = ""
    updated_at: datetime = field(default_factory=utc_now)


class ServiceHealthStore:
    """Persist the most recent explicit state of each external service."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    def update(self, status: ServiceStatus):
        with self.connection:
            self.connection.execute("""
                INSERT INTO service_health (
                    service, state, summary, details, recovery_action, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(service) DO UPDATE SET
                    state=excluded.state, summary=excluded.summary,
                    details=excluded.details,
                    recovery_action=excluded.recovery_action,
                    updated_at=excluded.updated_at
            """, (
                status.service, status.state, status.summary, status.details,
                status.recovery_action, status.updated_at.isoformat(),
            ))

    def all(self):
        return {
            row["service"]: ServiceStatus(
                row["service"], row["state"], row["summary"], row["details"],
                row["recovery_action"], datetime.fromisoformat(row["updated_at"]),
            )
            for row in self.connection.execute("SELECT * FROM service_health")
        }

    def highest_severity(self):
        severity = {"ok": 0, "busy": 1, "offline": 2, "warning": 2, "error": 3}
        statuses = self.all().values()
        return max(
            statuses,
            key=lambda item: (severity.get(item.state, 0), item.updated_at),
            default=None,
        )
