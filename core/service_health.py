"""Shared service-health records for persistent UI status."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


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
