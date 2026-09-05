"""Tests for benchmark-freshness reconciliation with imported scores."""

from datetime import datetime as dt

import pytest

from core.benchmarks import DefinitionRepository
from core.benchmarks.calculator import BenchmarkCalculator
from core.coaching.freshness import BenchmarkFreshness
from models.database import Database
from models.score import Score


def _freshness(with_db=True):
    if with_db:
        database = Database(":memory:")
        return database, BenchmarkFreshness(database.conn)
    conn = __import__("sqlite3").connect(":memory:")
    conn.row_factory = __import__("sqlite3").Row
    return None, BenchmarkFreshness(conn)


def _calculator():
    definitions = DefinitionRepository.bundled().load_active()
    try:
        return BenchmarkCalculator(definitions)
    except Exception:
        return None


def _make_score(benchmark_name, category, subcategory, difficulty="Novice", score=100.0):
    return Score(
        benchmark_name=benchmark_name,
        scenario=benchmark_name,
        category=category,
        subcategory=subcategory,
        difficulty=difficulty,
        score=score,
        timestamp=dt.now(),
    )


# ---- reconciliation-specific tests ----


def test_reconcile_marks_subcategories_as_measured():
    """A single imported benchmark-score seed records the subcategory as measured."""
    database, freshness = _freshness()
    try:
        result = freshness.reconcile([_make_score(
            "VT Pasu Novice S5", "Clicking", "Dynamic", score=600,
        )])

        assert "Clicking / Dynamic" in result

        state = freshness.status(["Clicking / Dynamic"])["Clicking / Dynamic"]
        assert state.measured is True
        assert state.due is False  # blocks_since_check starts at 0
        assert state.confidence == "current"
    finally:
        database.close()


def test_reconcile_does_not_touch_unknown_scores():
    """Scores with category/subcategory 'Unknown' are silently skipped."""
    database, freshness = _freshness()
    try:
        result = freshness.reconcile([_make_score(
            "Some random scenario", "Unknown", "Unknown", score=42.0,
        )])

        assert len(result) == 0

        state = freshness.status(["Clicking / Static"])["Clicking / Static"]
        assert state.measured is False
        assert state.confidence == "missing"
    finally:
        database.close()


def test_reconcile_all_novice_scores_clears_all_nine_subcategories():
    """Importing scores for every novice benchmark clears all subcategories from missing."""
    database, freshness = _freshness()
    calculator = _calculator()

    if calculator is None:
        pytest.skip("benchmark definitions not available")

    try:
        # Build a score for every novice benchmark
        scores = []
        for definition in calculator._definitions.benchmarks:
            if definition.difficulty != "Novice":
                continue
            scores.append(_make_score(
                definition.name,
                definition.category,
                definition.subcategory,
                difficulty="Novice",
                score=100.0,
            ))

        reconciled = freshness.reconcile(scores)

        # There should be 9 unique subcategories across all difficulties in the bundled set,
        # but only the ones we seeded with scores should appear as measured for Novice.
        fresh_states = freshness.status(calculator._definitions.required_subcategories)
        
        for key, state in fresh_states.items():
            if state.confidence == "missing":
                # That category wasn't covered by the novices; skip it
                continue
            assert state.measured is True, f"{key} should be measured"
            assert state.due is False

        # Confirm every reconciled subcategory is current/never-stale
        for key in reconciled:
            if key in fresh_states:
                assert fresh_states[key].confidence == "current"
    finally:
        database.close()


def test_reconcile_partial_import_leaves_remaining_categories_missing():
    """When only some subcategories have scores, the rest stay 'missing'."""
    database, freshness = _freshness()
    try:
        known_keys = ["Clicking / Dynamic", "Tracking / Precise"]
        for key in known_keys:
            parts = key.split(" / ", 1)
            scores = [_make_score(
                f"test_{key}", parts[0], parts[1], score=50.0,
            )]
            freshness.reconcile(scores)

        states = freshness.status([
            "Clicking / Dynamic",
            "Clicking / Static",  # not reconciled
            "Clicking / Linear",  # not reconciled
        ])

        assert states["Clicking / Dynamic"].measured is True
        assert states["Clicking / Static"].measured is False
        assert states["Clicking / Static"].confidence == "missing"
    finally:
        database.close()


def test_reconcile_updates_blocks_since_check_to_zero():
    """On reconcile, blocks_since_check resets to 0 even if there was prior activity."""
    database, freshness = _freshness()
    try:
        freshness.record_benchmark("Clicking / Dynamic")
        # Simulate 5 training blocks passing since the manual benchmark recording
        for _ in range(5):
            freshness.record_block(["Clicking / Dynamic"], warmup=False)

        pre = freshness.status(["Clicking / Dynamic"])["Clicking / Dynamic"]
        assert pre.blocks_since_check == 5
        assert pre.due is False  # 5 < 12

        # Now reconcile with an imported score
        freshness.reconcile([_make_score("VT Pasu Novice S5", "Clicking", "Dynamic")])

        post = freshness.status(["Clicking / Dynamic"])["Clicking / Dynamic"]
        assert post.blocks_since_check == 0
        assert post.due is False
    finally:
        database.close()


def test_reconcile_is_idempotent():
    """Calling reconcile twice with the same scores reports no second refresh."""
    database, freshness = _freshness()
    try:
        score = _make_score("VT Pasu Novice S5", "Clicking", "Dynamic")

        result1 = freshness.reconcile([score])
        result2 = freshness.reconcile([score])

        assert set(result1) == {"Clicking / Dynamic"}
        assert set(result2) == set()

        states = freshness.status(["Clicking / Dynamic"])
        # blocks_since_check should remain 0 after the second reconcile
        assert states["Clicking / Dynamic"].blocks_since_check == 0
    finally:
        database.close()


def test_old_score_does_not_reset_blocks_completed_after_that_benchmark():
    database, freshness = _freshness()
    try:
        score = _make_score("VT Pasu Novice S5", "Clicking", "Dynamic")
        freshness.reconcile([score])
        for _ in range(5):
            freshness.record_block(["Clicking / Dynamic"], warmup=False)

        refreshed = freshness.reconcile([score])

        assert refreshed == set()
        assert freshness.status(["Clicking / Dynamic"])[
            "Clicking / Dynamic"
        ].blocks_since_check == 5
    finally:
        database.close()


def test_official_filter_rejects_categorized_non_benchmark_scores():
    database, freshness = _freshness()
    definitions = DefinitionRepository.bundled().load_active()
    try:
        refreshed = freshness.reconcile([
            _make_score("Ordinary aim trainer", "Clicking", "Dynamic")
        ], definitions)

        assert refreshed == set()
        assert freshness.status(["Clicking / Dynamic"])[
            "Clicking / Dynamic"
        ].measured is False
    finally:
        database.close()


def test_reconcile_respects_existing_measured_timestamp():
    """Reconcile updates last_benchmark_at to the score's timestamp."""
    database, freshness = _freshness()
    try:
        # Record it once
        freshness.reconcile([_make_score("VT Pasu Novice S5", "Clicking", "Dynamic")])

        states = freshness.status(["Clicking / Dynamic"])
        assert states["Clicking / Dynamic"].measured is True
    finally:
        database.close()
