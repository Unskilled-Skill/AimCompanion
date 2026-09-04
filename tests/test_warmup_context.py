import json
from pathlib import Path

from core.sessions.builders import build_warmup_plan
from core.sessions.repository import WarmupPreference, WarmupPreferenceRepository
from models.database import Database


def test_last_warmup_context_is_selected_without_prompt():
    database = Database(":memory:")
    try:
        preferences = WarmupPreferenceRepository(database.conn)
        preferences.set("game", "Valorant & Counterstrike")
        assert preferences.get() == WarmupPreference(
            context="game", target_id="Valorant & Counterstrike"
        )
    finally:
        database.close()


def test_invalid_stored_context_falls_back_without_modal_state():
    database = Database(":memory:")
    try:
        database.conn.execute("""
            INSERT INTO warmup_preference (id, context, target_id)
            VALUES (1, 'invalid', '')
        """)
        assert WarmupPreferenceRepository(database.conn).get() == WarmupPreference(
            context="game", target_id="Valorant & Counterstrike"
        )
    finally:
        database.close()


def test_routine_warmup_covers_multiple_skills_when_catalog_permits():
    payload = json.loads(
        (Path(__file__).parents[1] / "data" / "tacfps_guide.json").read_text(
            encoding="utf-8"
        )
    )
    plan = build_warmup_plan("routine", payload["routines"][0]["name"])
    assert len({(step.category, step.subcategory) for step in plan.steps}) >= 2


def test_schema_version_six_contains_warmup_and_rotation_tables(tmp_path):
    database = Database(str(tmp_path / "preferences.sqlite3"))
    try:
        assert database.schema_version >= 6
        assert {"warmup_preference", "coaching_rotation_state"} <= database.table_names()
    finally:
        database.close()
