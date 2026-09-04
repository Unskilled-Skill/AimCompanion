"""SQLite persistence and crash recovery for guided sessions."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from types import MappingProxyType
from uuid import uuid4
from typing import Literal

from .engine import SessionEngine
from .model import SessionMode, SessionPlan, SessionState, SessionStatus, SessionStep


ACTIVE_STATUSES = (
    SessionStatus.READY.value,
    SessionStatus.RUNNING.value,
    SessionStatus.PAUSED.value,
)


@dataclass(frozen=True)
class WarmupPreference:
    context: Literal["game", "routine"]
    target_id: str


class WarmupPreferenceRepository:
    DEFAULT = WarmupPreference("game", "Valorant & Counterstrike")

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row

    def get(self) -> WarmupPreference:
        row = self.connection.execute(
            "SELECT context, target_id FROM warmup_preference WHERE id = 1"
        ).fetchone()
        if (
            row is None
            or row["context"] not in {"game", "routine"}
            or not str(row["target_id"]).strip()
        ):
            return self.DEFAULT
        return WarmupPreference(row["context"], row["target_id"])

    def set(self, context: str, target_id: str) -> WarmupPreference:
        if context not in {"game", "routine"}:
            raise ValueError("warm-up context must be game or routine")
        target = target_id.strip()
        if not target:
            raise ValueError("warm-up target is required")
        with self.connection:
            self.connection.execute("""
                INSERT INTO warmup_preference (id, context, target_id)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    context = excluded.context,
                    target_id = excluded.target_id
            """, (context, target))
        return WarmupPreference(context, target)


def _plain(value: object) -> object:
    if isinstance(value, (Mapping, MappingProxyType)):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_plain(item) for item in value)
    return value


class SessionRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.owner_token = uuid4().hex
        self._plan_ids: dict[int, int] = {}

    def create(self, plan: SessionPlan) -> SessionState:
        active = self.connection.execute(
            "SELECT 1 FROM session_state WHERE status IN (?, ?, ?) LIMIT 1",
            ACTIVE_STATUSES,
        ).fetchone()
        if active:
            raise ValueError("an active session already exists")
        state = SessionEngine.start(plan)
        with self.connection:
            cursor = self.connection.execute("""
                INSERT INTO session_plans (
                    mode, source_id, source_version, start_boundary,
                    initial_confirmed_runs, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                plan.mode.value,
                plan.source_id,
                plan.source_version,
                plan.start_boundary,
                plan.initial_confirmed_runs,
                state.started_at.isoformat(),
            ))
            plan_id = int(cursor.lastrowid)
            self._write_plan_steps(plan_id, plan)
            self._write_state(plan_id, state)
        self._plan_ids[id(plan)] = plan_id
        return state

    def save(self, state: SessionState) -> None:
        plan_id = self._resolve_plan_id(state.plan)
        with self.connection:
            self.connection.execute("""
                UPDATE session_plans
                SET mode = ?, source_id = ?, source_version = ?,
                    start_boundary = ?, initial_confirmed_runs = ?
                WHERE id = ?
            """, (
                state.plan.mode.value,
                state.plan.source_id,
                state.plan.source_version,
                state.plan.start_boundary,
                state.plan.initial_confirmed_runs,
                plan_id,
            ))
            self._write_plan_steps(plan_id, state.plan)
            self._write_state(plan_id, state)
            self._write_confirmed_runs(plan_id, state)

    def finish(self, state: SessionState) -> None:
        if state.status not in {SessionStatus.STOPPED, SessionStatus.COMPLETED}:
            raise ValueError("finish requires a stopped or completed session")
        self.save(state)

    def load_active(self) -> SessionState | None:
        row = self.connection.execute("""
            SELECT * FROM session_state
            WHERE status IN (?, ?, ?)
            ORDER BY updated_at DESC, plan_id DESC
            LIMIT 1
        """, ACTIVE_STATUSES).fetchone()
        if row is None:
            return None
        state = self._state_from_row(row)
        self._plan_ids[id(state.plan)] = int(row["plan_id"])
        if (
            state.status is SessionStatus.RUNNING
            and row["owner_token"] != self.owner_token
        ):
            state = replace(
                state,
                status=SessionStatus.PAUSED,
                stop_reason="application_recovered",
                updated_at=datetime.now(timezone.utc),
            )
            self.save(state)
        return state

    def full_routine_resume(self, source_id: str) -> int:
        row = self.connection.execute("""
            SELECT p.id, s.status, s.current_step_index
            FROM session_plans p
            JOIN session_state s ON s.plan_id = p.id
            WHERE p.mode = ? AND p.source_id = ?
            ORDER BY s.updated_at DESC, p.id DESC
            LIMIT 1
        """, (SessionMode.FULL_ROUTINE.value, source_id)).fetchone()
        if row is None or row["status"] == SessionStatus.COMPLETED.value:
            return 0
        step = self.connection.execute("""
            SELECT official_index FROM session_steps
            WHERE plan_id = ? AND execution_index = ?
        """, (row["id"], row["current_step_index"])).fetchone()
        return int(step["official_index"]) if step is not None else 0

    def build_resumed_full_plan(self, source_id: str) -> SessionPlan:
        row = self.connection.execute("""
            SELECT p.id FROM session_plans p
            JOIN session_state s ON s.plan_id = p.id
            WHERE p.mode = ? AND p.source_id = ?
            ORDER BY s.updated_at DESC, p.id DESC
            LIMIT 1
        """, (SessionMode.FULL_ROUTINE.value, source_id)).fetchone()
        if row is None:
            raise LookupError(f"no stored full routine: {source_id}")
        stored = self._load_plan(int(row["id"]))
        boundary = self.full_routine_resume(source_id)
        official = stored.official_steps
        steps = official[boundary:] + official[:boundary]
        return SessionPlan(
            mode=SessionMode.FULL_ROUTINE,
            source_id=stored.source_id,
            source_version=stored.source_version,
            steps=steps,
            official_steps=official,
            start_boundary=boundary,
            initial_confirmed_runs=0,
        )

    def load_rotation_state(self):
        from core.coaching.recommender import RotationState

        row = self.connection.execute(
            "SELECT cursor, last_scenario, last_subcategory "
            "FROM coaching_rotation_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return RotationState()
        return RotationState(
            cursor=int(row["cursor"]),
            last_scenario=row["last_scenario"],
            last_subcategory=row["last_subcategory"],
        )

    def save_rotation_state(self, state) -> None:
        if state.cursor < 0:
            raise ValueError("rotation cursor cannot be negative")
        with self.connection:
            self.connection.execute("""
                INSERT INTO coaching_rotation_state (
                    id, cursor, last_scenario, last_subcategory
                ) VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    cursor = excluded.cursor,
                    last_scenario = excluded.last_scenario,
                    last_subcategory = excluded.last_subcategory
            """, (state.cursor, state.last_scenario, state.last_subcategory))

    def _resolve_plan_id(self, plan: SessionPlan) -> int:
        known = self._plan_ids.get(id(plan))
        if known is not None:
            return known
        row = self.connection.execute("""
            SELECT p.id FROM session_plans p
            JOIN session_state s ON s.plan_id = p.id
            WHERE p.mode = ? AND p.source_id = ? AND p.source_version = ?
            ORDER BY CASE WHEN s.status IN ('ready', 'running', 'paused') THEN 0 ELSE 1 END,
                     s.updated_at DESC, p.id DESC
            LIMIT 1
        """, (plan.mode.value, plan.source_id, plan.source_version)).fetchone()
        if row is None:
            raise LookupError("session plan has not been created")
        plan_id = int(row["id"])
        self._plan_ids[id(plan)] = plan_id
        return plan_id

    def _write_plan_steps(self, plan_id: int, plan: SessionPlan) -> None:
        self.connection.execute("DELETE FROM session_steps WHERE plan_id = ?", (plan_id,))
        available = list(range(len(plan.official_steps)))
        execution_for_official: dict[int, int] = {}
        for execution_index, executed in enumerate(plan.steps):
            match = next(
                (index for index in available if plan.official_steps[index] is executed),
                None,
            )
            if match is None:
                match = next(
                    (index for index in available if plan.official_steps[index] == executed),
                    None,
                )
            if match is None:
                raise ValueError("execution steps must be a permutation of official steps")
            available.remove(match)
            execution_for_official[match] = execution_index
        if available:
            raise ValueError("execution steps must include every official step once")
        for official_index, step in enumerate(plan.official_steps):
            self.connection.execute("""
                INSERT INTO session_steps (
                    plan_id, execution_index, official_index, scenario,
                    required_runs, estimated_seconds, category, subcategory,
                    guide_json, source, source_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                plan_id,
                execution_for_official[official_index],
                official_index,
                step.scenario,
                step.required_runs,
                step.estimated_seconds,
                step.category,
                step.subcategory,
                json.dumps(_plain(step.guide), ensure_ascii=False, sort_keys=True),
                step.source,
                step.source_url,
            ))

    def _write_state(self, plan_id: int, state: SessionState) -> None:
        self.connection.execute("""
            INSERT INTO session_state (
                plan_id, status, current_step_index, confirmed_runs,
                started_at, updated_at, stop_reason, owner_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id) DO UPDATE SET
                status = excluded.status,
                current_step_index = excluded.current_step_index,
                confirmed_runs = excluded.confirmed_runs,
                started_at = excluded.started_at,
                updated_at = excluded.updated_at,
                stop_reason = excluded.stop_reason,
                owner_token = excluded.owner_token
        """, (
            plan_id,
            state.status.value,
            state.current_step_index,
            state.confirmed_runs,
            state.started_at.isoformat(),
            state.updated_at.isoformat(),
            state.stop_reason,
            self.owner_token,
        ))

    def _write_confirmed_runs(self, plan_id: int, state: SessionState) -> None:
        self.connection.execute("DELETE FROM session_runs WHERE plan_id = ?", (plan_id,))
        for step_index, step in enumerate(state.plan.steps):
            if step_index < state.current_step_index:
                count = step.required_runs
            elif step_index == state.current_step_index:
                count = state.confirmed_runs
            else:
                count = 0
            for run_index in range(count):
                self.connection.execute("""
                    INSERT INTO session_runs (
                        plan_id, step_index, run_index, confirmed_at
                    ) VALUES (?, ?, ?, ?)
                """, (plan_id, step_index, run_index, state.updated_at.isoformat()))

    def _load_plan(self, plan_id: int) -> SessionPlan:
        plan_row = self.connection.execute(
            "SELECT * FROM session_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if plan_row is None:
            raise LookupError(f"unknown session plan: {plan_id}")
        rows = self.connection.execute(
            "SELECT * FROM session_steps WHERE plan_id = ? ORDER BY official_index",
            (plan_id,),
        ).fetchall()
        official = tuple(self._step_from_row(row) for row in rows)
        by_official = {int(row["official_index"]): step for row, step in zip(rows, official)}
        execution_pairs = sorted(
            ((int(row["execution_index"]), int(row["official_index"])) for row in rows)
        )
        steps = tuple(by_official[official_index] for _, official_index in execution_pairs)
        return SessionPlan(
            mode=SessionMode(plan_row["mode"]),
            source_id=plan_row["source_id"],
            source_version=plan_row["source_version"],
            steps=steps,
            official_steps=official,
            start_boundary=int(plan_row["start_boundary"]),
            initial_confirmed_runs=int(plan_row["initial_confirmed_runs"]),
        )

    @staticmethod
    def _step_from_row(row: sqlite3.Row) -> SessionStep:
        return SessionStep(
            scenario=row["scenario"],
            required_runs=int(row["required_runs"]),
            estimated_seconds=int(row["estimated_seconds"]),
            category=row["category"],
            subcategory=row["subcategory"],
            guide=json.loads(row["guide_json"]),
            source=row["source"],
            source_url=row["source_url"],
        )

    def _state_from_row(self, row: sqlite3.Row) -> SessionState:
        return SessionState(
            plan=self._load_plan(int(row["plan_id"])),
            status=SessionStatus(row["status"]),
            current_step_index=int(row["current_step_index"]),
            confirmed_runs=int(row["confirmed_runs"]),
            started_at=datetime.fromisoformat(row["started_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            stop_reason=row["stop_reason"],
        )
