from core.coaching.freshness import BenchmarkFreshness
from models.database import Database


def _freshness():
    database = Database(":memory:")
    return database, BenchmarkFreshness(database.conn)


def test_subcategory_is_due_on_twelfth_relevant_block():
    database, freshness = _freshness()
    try:
        freshness.record_benchmark("Clicking / Static")
        for _ in range(11):
            freshness.record_block(["Clicking / Static"], warmup=False)
        current = freshness.status(["Clicking / Static"])["Clicking / Static"]
        assert current.due is False
        assert current.confidence == "current"

        freshness.record_block(["Clicking / Static"], warmup=False)
        stale = freshness.status(["Clicking / Static"])["Clicking / Static"]
        assert stale.due is True
        assert stale.blocks_since_check == 12
        assert stale.confidence == "stale"
    finally:
        database.close()


def test_warmup_does_not_advance_counter():
    database, freshness = _freshness()
    try:
        freshness.record_benchmark("Tracking / Reactive")
        freshness.record_block(["Tracking / Reactive"], warmup=True)
        state = freshness.status(["Tracking / Reactive"])["Tracking / Reactive"]
        assert state.blocks_since_check == 0
    finally:
        database.close()


def test_one_block_increments_each_distinct_subcategory_once():
    database, freshness = _freshness()
    try:
        freshness.record_benchmark("Clicking / Static")
        freshness.record_block(
            ["Clicking / Static", "Clicking / Static"], warmup=False
        )
        state = freshness.status(["Clicking / Static"])["Clicking / Static"]
        assert state.blocks_since_check == 1
    finally:
        database.close()


def test_missing_subcategory_is_due_with_missing_confidence():
    database, freshness = _freshness()
    try:
        state = freshness.status(["Switching / Speed"])["Switching / Speed"]
        assert state.measured is False
        assert state.due is True
        assert state.confidence == "missing"
    finally:
        database.close()


def test_benchmark_resets_only_its_exact_subcategory():
    database, freshness = _freshness()
    try:
        for name in ("Clicking / Static", "Clicking / Dynamic"):
            freshness.record_benchmark(name)
            freshness.record_block([name], warmup=False)
        freshness.record_benchmark("Clicking / Static")
        states = freshness.status(["Clicking / Static", "Clicking / Dynamic"])
        assert states["Clicking / Static"].blocks_since_check == 0
        assert states["Clicking / Dynamic"].blocks_since_check == 1
    finally:
        database.close()


def test_schema_version_five_contains_activity_table(tmp_path):
    database = Database(str(tmp_path / "freshness.sqlite3"))
    try:
        assert database.schema_version == 5
        assert "subcategory_activity" in database.table_names()
    finally:
        database.close()
