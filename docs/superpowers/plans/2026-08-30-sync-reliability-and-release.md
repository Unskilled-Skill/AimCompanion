# Synchronization, Reliability, and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Synchronize and validate against permitted official Voltaic web data, remain useful offline, guide missing-scenario installation, surface recoverable failures, and prove every GitHub release can update the preceding installed application.

**Architecture:** External integrations implement narrow source protocols and return validated snapshots with provenance. A sync coordinator never replaces the last-known-good cache until validation succeeds. Service-health records feed the persistent UI indicator. Release CI builds, signs with checksums, publishes, and executes an installer/updater contract smoke test.

**Tech Stack:** Python 3.12 standard-library HTTP/HTML/JSON, SQLite, PyQt6 worker threads, GitHub Actions, PyInstaller, Inno Setup, pytest

**Spec:** `docs/superpowers/specs/2026-08-30-coaching-core-redesign.md`

## Global Constraints

- Use only official, permitted Voltaic sources; do not invent a private API contract.
- The integration must remain replaceable because no stable public Voltaic profile API is advertised.
- Failed or malformed remote data never replaces the last-known-good definition cache.
- Local training, importing, and trends remain available offline.
- Store no Voltaic credentials; validation uses a configured public profile/username.
- Local and official timestamps and known daily leaderboard lag remain distinct.
- Missing official scenarios are never silently replaced or skipped.
- A release is incomplete until its GitHub asset, checksum, updater metadata, download, and upgrade path are verified.
- User-facing stable application updates are always published to GitHub.

---

## File structure

- `core/integrations/http.py`: timeout-limited HTTP transport with size/content-type limits.
- `core/integrations/voltaic.py`: official page snapshot extraction and source protocols.
- `core/integrations/validation.py`: compare local benchmark results with public official snapshots.
- `core/definition_sync.py`: last-known-good definition refresh and cache activation.
- `core/profile_sync.py`: post-import validation orchestration.
- `core/service_health.py`: extend the interface plan's shared status type with persistent storage.
- `core/scenario_installer.py`: exact missing-scenario resolution workflow.
- `models/migrations.py`: sync/cache/health tables.
- `ui/status_indicator.py`: render health details and recovery actions.
- `ui/scenarios.py` and `ui/session.py`: installation guidance.
- `scripts/verify_release.py`: release asset/checksum/update contract verifier.
- `.github/workflows/ci.yml`: test/lint/package pull-request gate.
- `.github/workflows/release.yml`: tagged publication and post-publication verification.

### Task 1: Safe HTTP transport and official snapshot extraction

**Files:**
- Create: `core/integrations/__init__.py`
- Create: `core/integrations/http.py`
- Create: `core/integrations/voltaic.py`
- Create: `tests/fixtures/voltaic/benchmarks-page.html`
- Create: `tests/fixtures/voltaic/leaderboard-page.html`
- Test: `tests/test_voltaic_sources.py`

**Interfaces:**
- Produces: `HttpTransport.get(url) -> HttpResponse`, `VoltaicBenchmarkPageSource.fetch() -> RemoteDefinitionSnapshot`, and `VoltaicLeaderboardSource.fetch(username, alias) -> OfficialProfileSnapshot`.
- Consumes: `https://app.voltaic.gg/benchmarks` and the public benchmark leaderboard URL with query parameters `aimtrainer=kovaaks`, `alias=kovaaks_s5`, `metric=energy`, and `username`.

- [ ] **Step 1: Capture sanitized official-page fixtures and write failing parser tests**

Fixtures retain the HTML shell and embedded structured application payload needed for parsing, remove analytics scripts, and contain no authentication cookies or personal credentials.

```python
def test_benchmark_page_extracts_s5_definitions(benchmark_html):
    snapshot = VoltaicBenchmarkPageSource(FakeHttp(benchmark_html)).fetch()
    assert snapshot.alias == "kovaaks_s5"
    assert snapshot.source_url == "https://app.voltaic.gg/benchmarks"
    assert len(snapshot.required_subcategories) == 9
    assert snapshot.definitions

def test_leaderboard_extracts_public_energy_and_update_time(leaderboard_html):
    snapshot = VoltaicLeaderboardSource(FakeHttp(leaderboard_html)).fetch("example", "kovaaks_s5")
    assert snapshot.username == "example"
    assert snapshot.energy > 0
    assert snapshot.observed_at.tzinfo is not None
```

- [ ] **Step 2: Run and verify integration modules are missing**

Run: `python -m pytest tests/test_voltaic_sources.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement bounded transport**

```python
@dataclass(frozen=True)
class HttpResponse:
    url: str
    status: int
    content_type: str
    body: bytes
    fetched_at: datetime

@dataclass(frozen=True)
class RemoteDefinitionSnapshot:
    alias: str
    source_url: str
    fetched_at: datetime
    sha256: str
    required_subcategories: tuple[str, ...]
    definitions: tuple[BenchmarkDefinition, ...]

@dataclass(frozen=True)
class OfficialProfileSnapshot:
    username: str
    benchmark_alias: str
    energy: float
    complete_rank: str
    observed_at: datetime

class HttpTransport:
    def get(self, url: str) -> HttpResponse:
        request = urllib.request.Request(url, headers={"User-Agent": f"AimCompanion/{VERSION}"})
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read(8_000_001)
        if len(body) > 8_000_000:
            raise SourceError("official response exceeds 8 MB")
        return validated_response(response, body)
```

Allow HTTPS and `app.voltaic.gg` only in these source classes. Reject non-200 responses, unexpected content types, redirects to other hosts, invalid UTF-8, and absent provenance fields.

- [ ] **Step 4: Parse embedded structured data defensively**

Extract JSON from application script elements, recursively locate the object whose alias is `kovaaks_s5`, and validate every definition with Task 1's `DefinitionSet` parser. For public validation, locate the exact case-insensitive username record and read its energy, complete rank, benchmark alias, and leaderboard update time. Multiple matching records or missing update time is a `SourceSchemaError`, not a guessed value.

- [ ] **Step 5: Add malformed/redirect/oversize tests**

```python
@pytest.mark.parametrize("payload", ["<html></html>", "<script>{bad}</script>", valid_html_without_s5()])
def test_schema_drift_fails_closed(payload):
    with pytest.raises(SourceSchemaError):
        VoltaicBenchmarkPageSource(FakeHttp(payload)).fetch()
```

- [ ] **Step 6: Run and commit**

Run: `python -m pytest tests/test_voltaic_sources.py -v`
Expected: PASS.

```powershell
git add core/integrations tests/fixtures/voltaic tests/test_voltaic_sources.py
git commit -m "feat: read validated official Voltaic snapshots"
```

### Task 2: Last-known-good definition synchronization

**Files:**
- Create: `core/definition_sync.py`
- Modify: `models/migrations.py`
- Modify: `models/database.py`
- Test: `tests/test_definition_sync.py`

**Interfaces:**
- Produces: `DefinitionSyncService.refresh() -> DefinitionSyncResult` and `.active() -> DefinitionSet`.
- Consumes: `VoltaicBenchmarkPageSource`, bundled definition repository, and SQLite cache.

- [ ] **Step 1: Write failing activation and rollback tests**

```python
def test_valid_new_snapshot_becomes_active(sync_service, newer_snapshot):
    result = sync_service.refresh()
    assert result.changed is True
    assert sync_service.active().sha256 == newer_snapshot.sha256

def test_malformed_remote_keeps_last_known_good(sync_service, source_error):
    before = sync_service.active()
    result = sync_service.refresh()
    assert result.state == "warning"
    assert sync_service.active() == before
```

- [ ] **Step 2: Run and verify service is missing**

Run: `python -m pytest tests/test_definition_sync.py -v`
Expected: FAIL.

- [ ] **Step 3: Add schema version 6 sync/cache tables**

Add `definition_sync_state` and use `benchmark_definition_sets` from the accuracy plan as the cache. Store fetched time, checked time, source URL, checksum, activation time, last error, and active flag. One transaction inserts the validated snapshot and deactivates the prior row.

- [ ] **Step 4: Implement conservative refresh behavior**

```python
@dataclass(frozen=True)
class DefinitionSyncResult:
    state: Literal["current", "updated", "warning", "offline"]
    changed: bool
    checked_at: datetime
    active_version: str
    message: str
```

Refresh at startup only when the last successful check is older than 24 hours. A manual refresh bypasses the interval. Network errors produce `offline`; schema/checksum errors produce `warning`; neither changes the active cache.

- [ ] **Step 5: Run and commit**

Run: `python -m pytest tests/test_definition_sync.py tests/test_benchmark_definitions.py tests/test_migrations.py -v`
Expected: PASS.

```powershell
git add core/definition_sync.py models/migrations.py models/database.py tests/test_definition_sync.py
git commit -m "feat: cache verified benchmark definitions"
```

### Task 3: Post-import public profile validation

**Files:**
- Create: `core/integrations/validation.py`
- Create: `core/profile_sync.py`
- Modify: `core/score_watcher.py`
- Modify: `models/migrations.py`
- Test: `tests/test_profile_validation.py`

**Interfaces:**
- Produces: `validate_profile(local, official) -> ValidationResult` and `ProfileValidationService.after_import(batch, profile_url) -> ValidationResult | None`.
- Consumes: local `BenchmarkResult`, public username parsed from configured Voltaic URL, official leaderboard source.

- [ ] **Step 1: Write failing agreement, lag, and mismatch tests**

```python
def test_matching_energy_validates(local_result, official_snapshot):
    official_snapshot = replace(official_snapshot, energy=round(local_result.overall_energy))
    assert validate_profile(local_result, official_snapshot).state == "matched"

def test_daily_lag_is_visible_not_a_local_overwrite(local_result, older_official):
    result = validate_profile(local_result, older_official)
    assert result.state == "lagging"
    assert result.local_energy == local_result.overall_energy
    assert result.official_observed_at == older_official.observed_at

def test_current_mismatch_lists_definition_and_energy(local_result, current_official):
    result = validate_profile(local_result, replace(current_official, energy=current_official.energy + 20))
    assert result.state == "mismatch"
    assert "kovaaks_s5" in result.details
```

- [ ] **Step 2: Run and verify validation service is missing**

Run: `python -m pytest tests/test_profile_validation.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement explicit timestamps and tolerances**

```python
@dataclass(frozen=True)
class ValidationResult:
    state: Literal["matched", "lagging", "mismatch", "unavailable"]
    local_energy: float | None
    official_energy: float | None
    local_calculated_at: datetime
    official_observed_at: datetime | None
    definition_version: str
    details: str
```

Treat rounded values within one energy point as matched. If official observation predates the newest imported eligible score, classify differing values as lagging. Otherwise classify as mismatch and list energy, version, newest local score time, and official observation time. Never alter scores or local calculation.

- [ ] **Step 4: Trigger validation after non-empty import batches**

`ScoreDirectoryWatcher.batch_completed` schedules profile validation only when `imported > 0`, a public profile is configured, and no validation is already running. Store the result in `profile_validation_state`. Network/schema failure returns unavailable and leaves local training unaffected.

- [ ] **Step 5: Run and commit**

Run: `python -m pytest tests/test_profile_validation.py tests/test_score_watcher.py -v`
Expected: PASS.

```powershell
git add core/integrations/validation.py core/profile_sync.py core/score_watcher.py models/migrations.py tests/test_profile_validation.py
git commit -m "feat: validate local rank after score imports"
```

### Task 4: Persistent service health and offline UX

**Files:**
- Modify: `core/service_health.py`
- Modify: `models/migrations.py`
- Modify: `ui/status_indicator.py`
- Modify: `ui/main_window.py`
- Test: `tests/test_service_health.py`
- Test: `tests/test_status_indicator.py`

**Interfaces:**
- Produces: `ServiceHealthStore.update(ServiceStatus)`, `.all()`, `.highest_severity()`, and recovery-action identifiers.
- Consumes: import, definition sync, profile validation, database, scenario, and updater events.

- [ ] **Step 1: Write failing persistence and recovery-action tests**

```python
def test_error_survives_restart_until_resolved(health_store):
    health_store.update(ServiceStatus("definitions", "warning", "Using cached definitions", "Schema changed", "retry_definition_sync"))
    reopened = reopen_health_store(health_store)
    assert reopened.all()["definitions"].recovery_action == "retry_definition_sync"

def test_success_resolves_persistent_error(health_store):
    health_store.update(error_status("scores"))
    health_store.update(ok_status("scores"))
    assert health_store.all()["scores"].state == "ok"
```

- [ ] **Step 2: Run and verify store is missing**

Run: `python -m pytest tests/test_service_health.py -v`
Expected: FAIL.

- [ ] **Step 3: Add schema version 7 and service store**

Reuse the exact `ServiceStatus` dataclass created by the interface plan. Add `ServiceHealthStore` as the SQLite-backed owner; do not create a second status type in the UI or integration packages.

Register only explicit actions: retry score import, retry definition sync, retry profile validation, open scenario installer, open update details, and open backup recovery. UI dispatches identifiers through a fixed mapping rather than evaluating stored commands.

- [ ] **Step 4: Connect services and verify offline operation**

Definition/profile offline states show cached/local timestamps. Disable only the remote retry while one is active; never disable Warm-up, Step-by-Step, Full Routine, Progress history, or Library because the network is unavailable.

- [ ] **Step 5: Run and commit**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_service_health.py tests/test_status_indicator.py tests/test_definition_sync.py tests/test_profile_validation.py -v`
Expected: PASS.

```powershell
git add core/service_health.py models/migrations.py ui/status_indicator.py ui/main_window.py tests
git commit -m "feat: surface persistent service health"
```

### Task 5: Exact missing-scenario installation guidance

**Files:**
- Create: `core/scenario_installer.py`
- Modify: `core/scenario_files.py`
- Modify: `ui/scenarios.py`
- Modify: `ui/session.py`
- Test: `tests/test_scenario_installer.py`

**Interfaces:**
- Produces: `ScenarioAvailability.resolve(name, directories)`, `ScenarioInstallGuide.for_scenario(step)`, and `ScenarioInstallCoordinator.recheck()`.
- Consumes: exact source scenario name, aliases explicitly authored in source data, workshop/local search paths, and Kovaak's launch/deep link functions.

- [ ] **Step 1: Write failing no-substitution tests**

```python
def test_missing_official_scenario_never_uses_alternative_without_source_permission(installer):
    result = installer.resolve("Exact Official Name", installed={"Similar Name"})
    assert result.state == "missing"
    assert result.resolved_name is None

def test_recheck_preserves_session_step(installer, coordinator, install_exact):
    before = coordinator.state.current_step_index
    install_exact("Exact Official Name")
    assert installer.recheck().state == "installed"
    assert coordinator.state.current_step_index == before
```

- [ ] **Step 2: Run and verify installer is missing**

Run: `python -m pytest tests/test_scenario_installer.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement explicit availability states and instructions**

```python
@dataclass(frozen=True)
class ScenarioInstallGuide:
    scenario: str
    state: Literal["installed", "online_launchable", "missing"]
    steps: tuple[str, ...]
    open_action: Literal["launch_scenario", "open_kovaaks", "none"]
```

Instructions name the exact scenario, tell the user to open Kovaak's Online Scenarios search, search the exact title, download/subscribe, then press Recheck. An authored `alternatives` entry may be offered as a labeled alternative choice but is never automatically selected.

- [ ] **Step 4: Wire Session launch blocking and recovery**

If missing, replace the launch action with the guide and Recheck; keep Pause/Stop available. Successful recheck restores Launch on the same step. Stopping follows ordinary session resume rules.

- [ ] **Step 5: Run and commit**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_scenario_installer.py tests/test_scenario_browser.py tests/test_session_widget.py -v`
Expected: PASS.

```powershell
git add core/scenario_installer.py core/scenario_files.py ui/scenarios.py ui/session.py tests/test_scenario_installer.py
git commit -m "feat: guide exact scenario installation"
```

### Task 6: CI quality gate and dependency policy

**Files:**
- Create: `pyproject.toml`
- Modify: `requirements.txt`
- Modify: `requirements-dev.txt`
- Create: `.github/workflows/ci.yml`
- Modify: `scripts/build_release.ps1`
- Test: `tests/test_packaging_contract.py`

**Interfaces:**
- Establishes: Python 3.12 support, pytest configuration, Ruff baseline/no-new-error gate, 80% new-core coverage gate, compile/startup/package checks.

- [ ] **Step 1: Write packaging contract tests**

```python
def test_spec_collects_versioned_data_files():
    text = Path("AimCompanion.spec").read_text(encoding="utf-8")
    assert "benchmark_definitions" in text

def test_installer_and_updater_expect_same_asset_name():
    assert updater.INSTALLER_ASSET == "AimCompanion-Setup.exe"
    assert "AimCompanion-Setup.exe" in Path("installer.iss").read_text(encoding="utf-8")
```

- [ ] **Step 2: Add exact tool configuration**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.coverage.run]
source = ["core/benchmarks", "core/coaching", "core/sessions"]

[tool.coverage.report]
fail_under = 80
```

Set the reviewed compatible ranges explicitly:

```text
# requirements.txt
PyQt6>=6.11,<6.12
matplotlib>=3.11,<3.12

# requirements-dev.txt
-r requirements.txt
pytest>=9.1,<10
pytest-qt>=4.4,<5
pytest-cov>=7,<8
ruff>=0.16,<0.17
pyinstaller>=6.22,<7
Pillow>=12.3,<13
```

Generate later dependency updates as explicit commits; do not silently float release builds across major versions.

- [ ] **Step 3: Add CI jobs**

CI on pushes and pull requests runs, in order: dependency install, Ruff over every new domain/integration/UI module and its tests, compileall, offscreen pytest with coverage, `scripts/smoke_ui.py`, PyInstaller build, and packaging-contract tests. The existing 233-issue audit remains recorded; modified legacy files must be cleaned for the rules their replacement paths exercise, without auto-fixing unrelated files in one commit.

- [ ] **Step 4: Run the local equivalent**

Run: `python -m ruff check core/benchmarks core/coaching core/sessions core/integrations core/definition_sync.py core/profile_sync.py core/service_health.py core/scenario_installer.py core/score_importer.py core/score_watcher.py core/session_coordinator.py ui/home.py ui/session.py ui/session_overlay.py ui/app_shell.py ui/progress_hub.py ui/library.py ui/status_indicator.py ui/view_models.py tests`
Expected: exit code 0 for all redesigned paths.
Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest --cov --cov-report=term-missing -q`
Expected: PASS and at least 80% for the three new core packages.
Run: `python -m pytest tests/test_packaging_contract.py -v`
Expected: PASS.

- [ ] **Step 5: Commit CI policy**

```powershell
git add pyproject.toml requirements.txt requirements-dev.txt .github/workflows/ci.yml scripts/build_release.ps1 tests/test_packaging_contract.py AimCompanion.spec
git commit -m "ci: gate tests lint coverage and packaging"
```

### Task 7: Published-release and updater verification

**Files:**
- Create: `scripts/verify_release.py`
- Modify: `.github/workflows/release.yml`
- Modify: `scripts/build_release.ps1`
- Modify: `core/updater.py`
- Modify: `tests/test_updater.py`
- Create: `tests/test_release_verifier.py`
- Modify: `README.md`
- Modify: `RELEASE_NOTES.md`

**Interfaces:**
- Produces: `verify_release(repository, tag, previous_installer=None) -> VerificationReport`; updater continues requiring `AimCompanion-Setup.exe` and its SHA-256.
- Consumes: GitHub Releases API, release tag, installer, checksum, version metadata, and an optional previous installed version in CI.

- [ ] **Step 1: Write failing release-contract tests**

```python
def test_release_requires_installer_checksum_and_matching_version(fake_release):
    report = verify_release_payload(fake_release(tag="v2.0.0", app_version="2.0.0"))
    assert report.asset_names == {"AimCompanion-Setup.exe", "AimCompanion-Setup.exe.sha256"}
    assert report.checksum_matches is True

def test_missing_checksum_fails_release(fake_release_without_checksum):
    with pytest.raises(ReleaseVerificationError, match="checksum asset"):
        verify_release_payload(fake_release_without_checksum)
```

- [ ] **Step 2: Run and verify release verifier is missing**

Run: `python -m pytest tests/test_release_verifier.py tests/test_updater.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement verifier and updater metadata checks**

```python
@dataclass(frozen=True)
class VerificationReport:
    tag: str
    asset_names: frozenset[str]
    checksum_matches: bool
    updater_selected_version: str
    download_size: int
```

Download release metadata and both assets through bounded HTTPS, verify the checksum over downloaded installer bytes, confirm `tag.lstrip('v') == VERSION`, and run the updater's release-selection function against the same payload. Never execute an unverified installer.

- [ ] **Step 4: Make post-publication verification a release job**

After `gh release create`, call:

```powershell
python scripts/verify_release.py --repository Unskilled-Skill/AimCompanion --tag $env:GITHUB_REF_NAME
```

The workflow argument and updater API constant must both use `Unskilled-Skill/AimCompanion`, matching `origin`. The job fails if assets are missing, checksum differs, updater ignores the tag, or the downloaded asset is empty.

- [ ] **Step 5: Add preceding-version upgrade smoke**

Keep the previous stable installer as a CI artifact or download it from the preceding GitHub release. Install silently into a temporary Windows test directory, launch once offscreen to confirm the preceding version, run the new verified installer with `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`, then assert `version_info.txt` and `QApplication.applicationVersion()` equal the new tag. Do not target the developer's installed application.

- [ ] **Step 6: Run local release-contract verification**

Run: `python -m pytest tests/test_release_verifier.py tests/test_updater.py tests/test_packaging_contract.py -v`
Expected: PASS.
Run: `git diff --check`
Expected: no output.

- [ ] **Step 7: Commit release verification**

```powershell
git add scripts/verify_release.py .github/workflows/release.yml scripts/build_release.ps1 core/updater.py tests README.md RELEASE_NOTES.md
git commit -m "ci: verify published updates end to end"
```

### Task 8: Final system verification and stable GitHub release

**Files:**
- Modify: `core/version.py`
- Modify: `version_info.txt`
- Modify: `installer.iss`
- Modify: `RELEASE_NOTES.md`

**Interfaces:**
- Delivers: one verified stable Windows release containing all four plans.

- [ ] **Step 1: Run full local verification before versioning**

Run: `python -m ruff check core/benchmarks core/coaching core/sessions core/integrations core/definition_sync.py core/profile_sync.py core/service_health.py core/scenario_installer.py core/score_importer.py core/score_watcher.py core/session_coordinator.py ui/home.py ui/session.py ui/session_overlay.py ui/app_shell.py ui/progress_hub.py ui/library.py ui/status_indicator.py ui/view_models.py tests`
Expected: PASS.
Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest --cov --cov-report=term-missing -q`
Expected: PASS with at least 80% coverage for new core packages.
Run: `python -m compileall -q core models ui tests scripts`
Expected: exit code 0.
Run: `$env:QT_QPA_PLATFORM='offscreen'; python scripts/smoke_ui.py`
Expected: exit code 0.

- [ ] **Step 2: Set one identical release version everywhere**

Update `core/version.py`, `version_info.txt`, `installer.iss`, and release notes to version `2.0.0`. Verify:

Run: `rg -n "VERSION|AppVersion|VersionInfoVersion" core/version.py version_info.txt installer.iss AimCompanion.spec`
Expected: every displayed value is the same semantic version.

- [ ] **Step 3: Build and test the installer**

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_release.ps1`
Expected: tests pass and `dist/AimCompanion-Setup.exe` plus `.sha256` are produced.

- [ ] **Step 4: Commit, tag, and publish to GitHub**

```powershell
git add core/version.py version_info.txt installer.iss RELEASE_NOTES.md
git commit -m "release: publish coaching core redesign"
git push origin main
git tag v2.0.0
git push origin v2.0.0
```

Do not run the tag command until every version file has been read back and confirmed as `2.0.0`.

- [ ] **Step 5: Verify GitHub Actions and updater path**

Run: `gh run watch --exit-status`
Expected: release workflow succeeds.
Run: `python scripts/verify_release.py --repository Unskilled-Skill/AimCompanion --tag v2.0.0`
Expected: installer and checksum match, updater selects the release, and upgrade smoke passes in CI.

- [ ] **Step 6: Record release evidence**

Add the workflow URL, release URL, installer SHA-256, preceding-version upgrade result, and final test counts to the published GitHub release notes. Do not create a post-tag code commit solely for evidence. Only then report the app update as released.
