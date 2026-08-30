# Benchmark Accuracy and Imports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the incorrect arithmetic Voltaic calculation with a versioned official-rule benchmark engine and continuously import Kovaak's results without blocking the UI.

**Architecture:** Add a pure-Python benchmark package whose definition repository and calculator are independent of PyQt, then adapt the existing profile model around its result. Add versioned SQLite migrations and a pure import coordinator; a thin Qt watcher schedules debounced import batches and informs `MainWindow` through signals.

**Tech Stack:** Python 3.12, dataclasses, JSON, SQLite, PyQt6, `unittest`/pytest, existing Kovaak's CSV parser

**Spec:** `docs/superpowers/specs/2026-08-30-coaching-core-redesign.md`

## Global Constraints

- The highest eligible scenario energy in each subcategory determines subcategory energy.
- Overall official energy is the harmonic mean of all nine required subcategories and is unavailable until all nine are measured.
- Every definition set records version, source URL, retrieval time, checksum, aliases, thresholds, caps, and active status.
- Local Kovaak's CSV files remain authoritative for detailed history.
- Automatic importing must retain a manual fallback and must not block application startup.
- Do not label arithmetic averages as official Voltaic energy.
- Preserve existing user scores and settings; back up before schema migration.
- Core benchmark code must not import PyQt.
- Stable releases are published through the verified GitHub release/update path only after all plan tests pass.

---

## File structure

- `core/benchmarks/definitions.py`: immutable benchmark definition types and JSON validation.
- `core/benchmarks/calculator.py`: score interpolation, caps, best-per-subcategory selection, harmonic mean, rank.
- `core/benchmarks/repository.py`: bundled/cache definition loading by version.
- `data/benchmark_definitions/voltaic-kovaaks-s5.json`: versioned bundled definition snapshot.
- `models/profile.py`: profile view models populated from a benchmark result.
- `models/migrations.py`: ordered, transactional SQLite schema migrations.
- `core/score_importer.py`: deterministic import batches and results.
- `core/score_watcher.py`: Qt filesystem watcher/debounce adapter.
- `core/parser.py`: retain parsing; delegate batch import to `ScoreImporter`.
- `core/analyzer.py`: build profiles through `BenchmarkCalculator`.
- `models/database.py`: expose schema version, definition metadata, and import error persistence.
- `ui/main_window.py`: start/stop watcher and rebuild UI after a completed batch.

### Task 1: Versioned benchmark definitions

**Files:**
- Create: `core/benchmarks/__init__.py`
- Create: `core/benchmarks/definitions.py`
- Create: `core/benchmarks/repository.py`
- Create: `data/benchmark_definitions/voltaic-kovaaks-s5.json`
- Test: `tests/test_benchmark_definitions.py`

**Interfaces:**
- Produces: `BenchmarkDefinition`, `DefinitionSet`, `DefinitionRepository.load_active() -> DefinitionSet`, and `DefinitionRepository.load(version: str) -> DefinitionSet`.
- Consumes: bundled JSON through `core.paths.bundled_path`.

- [ ] **Step 1: Write the failing definition-validation tests**

```python
def test_definition_set_requires_nine_subcategories(tmp_path):
    path = write_definition(tmp_path, subcategories=["Clicking / Static"])
    with pytest.raises(ValueError, match="exactly nine"):
        DefinitionRepository(path.parent).load("test")

def test_active_definition_has_verifiable_provenance():
    definitions = DefinitionRepository.bundled().load_active()
    assert definitions.version == "kovaaks_s5"
    assert definitions.source_url.startswith("https://app.voltaic.gg/")
    assert len(definitions.sha256) == 64
    assert len(definitions.required_subcategories) == 9
```

- [ ] **Step 2: Run the tests and verify the missing package failure**

Run: `python -m pytest tests/test_benchmark_definitions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.benchmarks'`.

- [ ] **Step 3: Add immutable definitions and strict JSON parsing**

```python
@dataclass(frozen=True)
class BenchmarkDefinition:
    name: str
    scenario: str
    aliases: tuple[str, ...]
    category: str
    subcategory: str
    difficulty: str
    targets: tuple[tuple[float, float], ...]
    energy_cap: float
    uncap_overall_energy: float | None

@dataclass(frozen=True)
class DefinitionSet:
    version: str
    source_url: str
    retrieved_at: datetime
    sha256: str
    active: bool
    required_subcategories: tuple[str, ...]
    ranks: tuple[tuple[str, float], ...]
    benchmarks: tuple[BenchmarkDefinition, ...]
```

`DefinitionRepository` must calculate the SHA-256 of the canonical `definitions` payload, compare it with the stored checksum, reject duplicate normalized aliases, reject non-increasing target points, and reject any set whose `required_subcategories` count is not nine.

- [ ] **Step 4: Convert the existing S5 data into the versioned snapshot**

Build the top-level payload with this exact shape, then serialize it as JSON:

```python
payload = {
    "version": "kovaaks_s5",
    "source_url": "https://app.voltaic.gg/benchmarks",
    "retrieved_at": "2026-08-30T00:00:00+02:00",
    "active": True,
    "required_subcategories": [
        "Clicking / Static", "Clicking / Dynamic", "Clicking / Linear",
        "Tracking / Precise", "Tracking / Reactive", "Tracking / Control",
        "Switching / Speed", "Switching / Evasive", "Switching / Stability",
    ],
    "ranks": converted_tiers,
    "definitions": converted_benchmarks,
}
payload["sha256"] = DefinitionRepository.canonical_sha256(payload["definitions"])
```

Populate `ranks` from `data/tiers.json` and `definitions` from `data/benchmarks.json`; compute and insert the checksum with a one-off call to the repository's canonicalization helper. Do not hand-copy or alter target values during conversion.

- [ ] **Step 5: Run focused and existing benchmark tests**

Run: `python -m pytest tests/test_benchmark_definitions.py tests/test_progress_logic.py tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Commit the definition boundary**

```powershell
git add core/benchmarks data/benchmark_definitions tests/test_benchmark_definitions.py
git commit -m "feat: add versioned benchmark definitions"
```

### Task 2: Official benchmark calculator

**Files:**
- Create: `core/benchmarks/calculator.py`
- Test: `tests/test_benchmark_calculator.py`

**Interfaces:**
- Consumes: `DefinitionSet` and `Iterable[Score]`.
- Produces: `ScenarioEnergy`, `SubcategoryEnergy`, `BenchmarkResult`, and `BenchmarkCalculator.calculate(scores, difficulty) -> BenchmarkResult`.

- [ ] **Step 1: Write failing rule tests**

```python
def test_subcategory_uses_highest_scenario_energy(s5, scores_for_all_nine):
    scores_for_all_nine += [score("VT PGT Novice S5", 3050), score("VT Snake Track Novice S5", 1)]
    result = BenchmarkCalculator(s5).calculate(scores_for_all_nine, "Novice")
    precise = result.subcategories["Tracking / Precise"]
    assert precise.energy == max(item.energy for item in precise.scenarios)

def test_overall_is_harmonic_mean(s5, one_score_per_subcategory):
    result = BenchmarkCalculator(s5).calculate(one_score_per_subcategory, "Novice")
    energies = [item.energy for item in result.subcategories.values()]
    assert result.overall_energy == pytest.approx(len(energies) / sum(1 / value for value in energies))

def test_overall_is_unmeasured_until_all_nine_exist(s5, one_score_per_subcategory):
    result = BenchmarkCalculator(s5).calculate(one_score_per_subcategory[:-1], "Novice")
    assert result.overall_energy is None
    assert result.missing_subcategories == ("Switching / Stability",)
```

- [ ] **Step 2: Verify failures describe missing calculator symbols**

Run: `python -m pytest tests/test_benchmark_calculator.py -v`
Expected: FAIL because `BenchmarkCalculator` is not defined.

- [ ] **Step 3: Implement interpolation, cap, aggregation, and tier selection**

```python
@dataclass(frozen=True)
class ScenarioEnergy:
    benchmark_name: str
    scenario: str
    score: float
    energy: float

@dataclass(frozen=True)
class SubcategoryEnergy:
    name: str
    energy: float
    selected_scenario: str
    scenarios: tuple[ScenarioEnergy, ...]

@dataclass(frozen=True)
class BenchmarkResult:
    definition_version: str
    difficulty: str
    subcategories: Mapping[str, SubcategoryEnergy]
    overall_energy: float | None
    overall_tier: str | None
    missing_subcategories: tuple[str, ...]

def harmonic_mean(values: Sequence[float]) -> float:
    if not values or any(value <= 0 for value in values):
        raise ValueError("harmonic mean requires positive energies")
    return len(values) / sum(1.0 / value for value in values)
```

Use piecewise-linear interpolation between rank targets and linear interpolation from zero to the first target. Select the best imported score per benchmark, then the highest scenario energy per required subcategory. Apply the definition's conditional cap for the first pass; if the capped overall energy reaches `uncap_overall_energy`, recalculate with raw scenario energies. Do not average scenarios.

- [ ] **Step 4: Add boundary and alias tests**

```python
@pytest.mark.parametrize("score,expected", [(0, 0), (540, 300), (640, 400)])
def test_exact_targets_map_to_exact_energy(s5, score, expected):
    definition = s5.find("VT Floating Heads Novice S5")
    assert score_to_energy(definition, score) == pytest.approx(expected)

def test_alias_resolves_to_one_definition(s5):
    assert s5.find("  vt-floating heads novice s5 ").name == "VT Floating Heads Novice S5"

def test_advanced_energy_uncaps_only_after_overall_threshold(advanced_s5, advanced_scores):
    below = BenchmarkCalculator(advanced_s5).calculate(advanced_scores, "Advanced")
    assert max(item.energy for sub in below.subcategories.values() for item in sub.scenarios) <= 1200
    above = BenchmarkCalculator(advanced_s5).calculate(raise_all_subcategories(advanced_scores), "Advanced")
    assert max(item.energy for sub in above.subcategories.values() for item in sub.scenarios) > 1200
```

- [ ] **Step 5: Run the calculator suite**

Run: `python -m pytest tests/test_benchmark_calculator.py tests/test_benchmark_definitions.py -v`
Expected: PASS.

- [ ] **Step 6: Commit the official calculation**

```powershell
git add core/benchmarks/calculator.py tests/test_benchmark_calculator.py
git commit -m "fix: calculate official Voltaic benchmark energy"
```

### Task 3: Profile compatibility adapter

**Files:**
- Create: `models/profile.py`
- Modify: `models/score.py`
- Modify: `models/benchmark.py`
- Modify: `core/analyzer.py`
- Test: `tests/test_analyzer_official_profile.py`

**Interfaces:**
- Consumes: `BenchmarkResult` from Task 2.
- Produces: `PlayerProfile.from_result(result) -> PlayerProfile`; existing widgets continue reading `categories`, `overall_energy`, `overall_tier`, and `get_weakest_subcategories()`.

- [ ] **Step 1: Write a failing integration test using all nine subcategories**

```python
def test_build_profile_exposes_official_harmonic_energy(db_with_s5_scores):
    profile = build_profile(db_with_s5_scores, difficulty="Novice")
    result = BenchmarkCalculator(DefinitionRepository.bundled().load_active()).calculate(
        db_with_s5_scores.get_best_scores(), "Novice"
    )
    assert profile.overall_energy == pytest.approx(result.overall_energy)
    assert profile.calculation_method == "voltaic_official"
    assert profile.definition_version == "kovaaks_s5"
```

- [ ] **Step 2: Confirm the current arithmetic result fails the assertion**

Run: `python -m pytest tests/test_analyzer_official_profile.py -v`
Expected: FAIL because `PlayerProfile` has no `calculation_method` and uses arithmetic means.

- [ ] **Step 3: Adapt the profile without duplicating calculation rules**

```python
@dataclass
class PlayerProfile:
    difficulty: str = "Novice"
    categories: list[CategoryScore] = field(default_factory=list)
    overall_energy: float | None = None
    overall_tier: str = "Unranked"
    definition_version: str = ""
    calculation_method: str = "voltaic_official"

    @classmethod
    def from_result(cls, result: BenchmarkResult) -> "PlayerProfile":
        return profile_from_benchmark_result(result)
```

Move view-model construction to `models/profile.py`. Make `core/analyzer.build_profile()` load the requested definition and call the calculator once. Keep deprecated helpers in `models/benchmark.py` as thin calls into the active definition calculator until all UI callers are migrated.

- [ ] **Step 4: Replace arithmetic-model assertions throughout the existing suite**

Update fixtures to provide all nine required subcategories when they expect an overall rank. Assertions for incomplete data must expect `overall_energy is None` and `overall_tier == "Unranked"`.

- [ ] **Step 5: Run all profile and recommendation compatibility tests**

Run: `python -m pytest tests/test_analyzer_official_profile.py tests/test_recommender.py tests/test_progress_logic.py tests/test_tool_logic.py -v`
Expected: PASS.

- [ ] **Step 6: Commit the profile adapter**

```powershell
git add models/profile.py models/score.py models/benchmark.py core/analyzer.py tests
git commit -m "refactor: build profiles from official benchmark results"
```

### Task 4: Versioned database migrations and benchmark metadata

**Files:**
- Create: `models/migrations.py`
- Modify: `models/database.py`
- Test: `tests/test_migrations.py`

**Interfaces:**
- Produces: `apply_migrations(connection, backup_path_factory) -> int`; schema version `2`; database methods `save_definition_metadata()`, `record_import_error()`, and `clear_import_error()`.
- Consumes: an existing SQLite connection and explicit backup destination callback.

- [ ] **Step 1: Write failing migration and preservation tests**

```python
def test_v1_database_is_backed_up_and_migrated_without_score_loss(tmp_path):
    path = create_legacy_database(tmp_path, score_count=3)
    db = Database(str(path))
    assert db.schema_version == 2
    assert len(db.get_all_scores()) == 3
    assert list(tmp_path.glob("*.pre-v2.sqlite3"))

def test_migration_adds_definition_and_import_status_tables(migrated_db):
    names = migrated_db.table_names()
    assert {"benchmark_definition_sets", "import_failures", "schema_migrations"} <= names
```

- [ ] **Step 2: Run and confirm schema symbols are missing**

Run: `python -m pytest tests/test_migrations.py -v`
Expected: FAIL because `Database.schema_version` is absent.

- [ ] **Step 3: Implement ordered transactional migrations**

```python
MIGRATIONS = (
    Migration(1, "baseline", baseline_existing_schema),
    Migration(2, "benchmark_metadata", add_benchmark_metadata_tables),
)

def apply_migrations(conn: sqlite3.Connection, backup: Callable[[int], Path]) -> int:
    current = read_schema_version(conn)
    pending = [item for item in MIGRATIONS if item.version > current]
    if pending and current > 0:
        backup(current)
    for migration in pending:
        with conn:
            migration.apply(conn)
            record_migration(conn, migration)
    return MIGRATIONS[-1].version
```

`read_schema_version` returns version 1 when `schema_migrations` is absent but the legacy `scores` and `settings` tables exist. That legacy detection ensures an existing user database is backed up before migration 2; a brand-new empty database starts at version 0 and needs no pre-migration backup.

`benchmark_definition_sets` stores version, source URL, retrieval time, checksum, active flag, and JSON payload. `import_failures` stores path, error text, first/last failure time, and retry count. Do not delete or rewrite legacy tables.

- [ ] **Step 4: Test rollback on a deliberately failing migration**

```python
def test_failed_migration_rolls_back_its_schema_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(migrations, "MIGRATIONS", migrations.MIGRATIONS + (failing_migration(),))
    with pytest.raises(RuntimeError, match="forced migration failure"):
        Database(str(tmp_path / "aim.db"))
    assert "half_created" not in sqlite_table_names(tmp_path / "aim.db")
```

- [ ] **Step 5: Run migration and database suites**

Run: `python -m pytest tests/test_migrations.py tests/test_database.py -v`
Expected: PASS.

- [ ] **Step 6: Commit migrations**

```powershell
git add models/migrations.py models/database.py tests/test_migrations.py
git commit -m "feat: add recoverable database migrations"
```

### Task 5: Deterministic import batches

**Files:**
- Create: `core/score_importer.py`
- Modify: `core/parser.py`
- Modify: `core/sync_worker.py`
- Test: `tests/test_score_importer.py`

**Interfaces:**
- Produces: `ImportBatchResult(imported, duplicates, failed, paths)` and `ScoreImporter.import_paths(paths) -> ImportBatchResult`.
- Consumes: `Database`, `parse_csv_file(path) -> Score | None`, and explicit filesystem paths.

- [ ] **Step 1: Write failing duplicate, ordering, and malformed-file tests**

```python
def test_batch_imports_out_of_order_files_by_score_timestamp(importer, newer, older):
    result = importer.import_paths([newer, older])
    assert result.imported == 2
    assert [score.timestamp for score in importer.db.get_all_scores()] == [older.timestamp, newer.timestamp]

def test_duplicate_score_marks_second_path_without_duplicating_row(importer, same_run_copies):
    result = importer.import_paths(same_run_copies)
    assert result.imported == 1
    assert result.duplicates == 1

def test_malformed_file_isolated_and_recorded(importer, malformed, valid):
    result = importer.import_paths([malformed, valid])
    assert result.imported == 1
    assert result.failed == 1
    assert importer.db.get_import_failure(str(malformed))["retry_count"] == 1
```

- [ ] **Step 2: Run and verify the importer is missing**

Run: `python -m pytest tests/test_score_importer.py -v`
Expected: FAIL with missing `core.score_importer`.

- [ ] **Step 3: Implement one-transaction batch behavior**

```python
@dataclass(frozen=True)
class ImportBatchResult:
    imported: int
    duplicates: int
    failed: int
    paths: tuple[str, ...]

class ScoreImporter:
    def import_paths(self, paths: Iterable[str]) -> ImportBatchResult:
        ordered = sorted({os.path.abspath(path) for path in paths})
        # Parse each path independently, record failures, insert valid scores,
        # and mark duplicate paths in one Database transaction.
```

Keep `import_all_scores()` as a compatibility wrapper that enumerates CSV files and returns `ScoreImporter(...).import_paths(paths).imported`. Ensure database reads remain timestamp ordered instead of relying on discovery order.

- [ ] **Step 4: Run parser and import tests**

Run: `python -m pytest tests/test_score_importer.py tests/test_parser.py tests/test_database.py -v`
Expected: PASS.

- [ ] **Step 5: Commit the import coordinator**

```powershell
git add core/score_importer.py core/parser.py core/sync_worker.py models/database.py tests/test_score_importer.py
git commit -m "feat: import score files in resilient batches"
```

### Task 6: Background watcher and UI integration

**Files:**
- Create: `core/score_watcher.py`
- Modify: `ui/main_window.py`
- Modify: `ui/import_widget.py`
- Modify: `requirements-dev.txt`
- Test: `tests/test_score_watcher.py`
- Test: `tests/test_aim_hub.py`

**Interfaces:**
- Produces: `ScoreDirectoryWatcher.batch_completed(ImportBatchResult)`, `.batch_failed(str)`, `.start()`, and `.stop()`.
- Consumes: configured stats directory, DB path, `QFileSystemWatcher`, and `ScoreSyncWorker`.

- [ ] **Step 1: Add the Qt test fixture dependency and write failing debounce/startup tests**

Add `pytest-qt>=4.4,<5` to `requirements-dev.txt`, run `python -m pip install -r requirements-dev.txt`, then add these tests with a temporary score directory:

```python
def test_burst_of_changes_emits_one_debounced_batch(qtbot, watcher, write_score):
    write_score("first.csv")
    write_score("second.csv")
    with qtbot.waitSignal(watcher.batch_completed, timeout=2000) as signal:
        watcher.notify_directory_changed()
        watcher.notify_directory_changed()
    assert signal.args[0].imported == 2

def test_start_performs_recovery_scan(qtbot, watcher_with_existing_score):
    with qtbot.waitSignal(watcher_with_existing_score.batch_completed, timeout=2000):
        watcher_with_existing_score.start()
```

- [ ] **Step 2: Run and verify the watcher module is missing**

Run: `python -m pytest tests/test_score_watcher.py -v`
Expected: FAIL with missing `ScoreDirectoryWatcher`.

- [ ] **Step 3: Implement a 750 ms single-shot debounce**

```python
class ScoreDirectoryWatcher(QObject):
    batch_completed = pyqtSignal(object)
    batch_failed = pyqtSignal(str)

    def __init__(self, db_path: str, stats_dir: str, parent=None):
        super().__init__(parent)
        self._timer = QTimer(self, interval=750, singleShot=True)
        self._timer.timeout.connect(self._scan)
```

`start()` registers the directory and immediately schedules a scan. Directory changes restart the timer. `_scan()` refuses to create a second worker while one is running and schedules another scan if events arrived during that batch. `stop()` stops the timer, removes watched paths, and waits only for an already-running worker during application shutdown.

- [ ] **Step 4: Connect the watcher to the application lifecycle**

`MainWindow.__init__` creates the watcher after setup, connects success to `_on_sync_complete`, connects failure to `_on_sync_failed`, and starts it. `closeEvent` stops it before closing the database. Manual import calls the same `ScoreImporter` path and triggers the same profile refresh callback.

- [ ] **Step 5: Run watcher and offscreen startup tests**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_score_watcher.py tests/test_aim_hub.py -v`
Expected: PASS with one import batch per event burst.

- [ ] **Step 6: Run the full phase gate**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q`
Expected: all tests PASS; no official-energy assertion uses arithmetic averaging.

- [ ] **Step 7: Commit the watcher integration**

```powershell
git add core/score_watcher.py ui/main_window.py ui/import_widget.py tests/test_score_watcher.py tests/test_aim_hub.py
git commit -m "feat: watch Kovaak's scores continuously"
```

### Task 7: Phase documentation and executable audit

**Files:**
- Modify: `README.md`
- Modify: `RELEASE_NOTES.md`
- Create: `docs/benchmark-data-provenance.md`

**Interfaces:**
- Documents: official calculation, definition version/checksum, offline behavior, automatic/manual importing, and known daily Voltaic lag.

- [ ] **Step 1: Add exact user-facing documentation**

Document this formula:

```text
subcategory energy = max(eligible scenario energies in that subcategory)
overall energy = 9 / sum(1 / subcategory energy for all nine subcategories)
```

State that no overall official energy is shown until all nine subcategories have a valid score and that definitions are versioned from `https://app.voltaic.gg/benchmarks`.

- [ ] **Step 2: Run executable verification and whitespace checks**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q`
Expected: PASS.
Run: `python -m compileall -q core models ui tests`
Expected: exit code 0.
Run: `git diff --check`
Expected: no output.

- [ ] **Step 3: Commit phase documentation**

```powershell
git add README.md RELEASE_NOTES.md docs/benchmark-data-provenance.md
git commit -m "docs: explain benchmark accuracy and imports"
```
