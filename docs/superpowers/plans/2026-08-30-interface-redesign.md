# Interface Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fragmented navigation with a coaching-first Home, guided Session, unified Progress, reference Library, and secondary Tools experience, including an optional compact training panel.

**Architecture:** Keep one application shell and bind purpose-built widgets to benchmark/coaching/session view models. The main and compact session surfaces subscribe to the same coordinator state. Existing specialized widgets are composed into the new destinations before obsolete navigation and manual-observation controls are removed.

**Tech Stack:** Python 3.12, PyQt6 Widgets, existing QSS and matplotlib charts, pytest with offscreen Qt

**Spec:** `docs/superpowers/specs/2026-08-30-coaching-core-redesign.md`

## Global Constraints

- Top-level navigation contains exactly Home, Session, Progress, Library, and Tools.
- Home leads with one coaching conclusion and three large training actions.
- Selecting a routine displays the complete routine plus detailed source-backed instructions.
- Session guidance includes purpose, setup, steps, success, required runs, source, and source-backed adjustments when present.
- Main and compact session surfaces share one state and cannot advance independently.
- Charts and raw statistics follow plain-language coaching conclusions.
- Deathmatch guidance belongs in Library, not primary training modes.
- Manual game observations are removed from the active interface.
- Sync/import/update failures use a persistent expandable indicator rather than only modal dialogs.
- Keyboard focus, accessible names, contrast, scalable layouts, and non-color status cues are required.

---

## File structure

- `ui/app_shell.py`: five-destination navigation, top bar, status indicator host.
- `ui/home.py`: coaching summary, evidence, three primary actions, recent progress.
- `ui/session.py`: detailed guided current-scenario surface and plan overview.
- `ui/session_overlay.py`: compact always-on-top representation of the same session state.
- `ui/progress_hub.py`: Summary, Skills, Benchmarks, History tabs.
- `ui/library.py`: routines, scenarios, warm-ups, deathmatch, game-transfer references.
- `ui/tools.py`: secondary utility tabs and manual import.
- `ui/status_indicator.py`: persistent aggregate service health.
- `ui/view_models.py`: immutable presentation records and text formatting.
- `core/service_health.py`: shared in-memory service status type; persistence is added by the reliability plan.
- `ui/main_window.py`: composition and lifecycle only.
- `ui/routines.py`: retired primary surface; reusable guide rendering extracted before deletion.

### Task 1: Presentation models and source-backed guide formatting

**Files:**
- Create: `ui/view_models.py`
- Create: `ui/scenario_guide.py`
- Modify: `ui/routines.py`
- Test: `tests/test_session_view_models.py`

**Interfaces:**
- Produces: `HomeViewModel`, `SessionViewModel`, `ScenarioGuideViewModel`, `ProgressViewModel`, `build_session_view(state, evidence)`, and `ScenarioGuideWidget.set_guide(view_model)`.
- Consumes: benchmark profile, `CoachingSummary`, `RecommendationEvidence`, and `SessionState`.

- [ ] **Step 1: Write failing omission and completeness tests**

```python
def test_source_guide_exposes_all_authored_fields(session_state):
    view = build_session_view(session_state, evidence=None)
    guide = view.current_guide
    assert guide.purpose
    assert guide.setup
    assert guide.steps
    assert guide.success
    assert guide.required_runs == session_state.current_step.required_runs
    assert guide.source == "hnA TacFPS Aim Guide"

def test_absent_adjustment_is_omitted_not_invented(session_state_without_adjust):
    guide = build_session_view(session_state_without_adjust, evidence=None).current_guide
    assert guide.adjustment is None
```

- [ ] **Step 2: Run and verify the view-model module is missing**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_session_view_models.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement immutable presentation records**

```python
@dataclass(frozen=True)
class ScenarioGuideViewModel:
    scenario: str
    purpose: str
    setup: str
    steps: tuple[str, ...]
    success: str
    adjustment: str | None
    required_runs: int
    completed_runs: int
    source: str
    source_url: str

@dataclass(frozen=True)
class SessionStepViewModel:
    scenario: str
    completed: bool
    run_text: str

@dataclass(frozen=True)
class SessionViewModel:
    mode: str
    title: str
    status: str
    progress_text: str
    current_guide: ScenarioGuideViewModel
    steps: tuple[SessionStepViewModel, ...]
    can_launch: bool
    can_advance: bool
    evidence: RecommendationEvidence | None

@dataclass(frozen=True)
class HomeViewModel:
    rank_text: str
    next_rank_text: str
    headline: str
    evidence_text: str
    confidence_text: str
    recent_progress: tuple[str, ...]

@dataclass(frozen=True)
class ProgressViewModel:
    conclusion: str
    missing_subcategories: tuple[str, ...]
    definition_version: str
```

Map `focus` to purpose and `performance_guide` keys directly. Extract the existing routine-detail rendering into `ScenarioGuideWidget`; it must create the adjustment section only when `adjustment` is not `None`.

- [ ] **Step 4: Add accessible label tests and commit**

```python
def test_guide_sections_have_accessible_names(qtbot, guide_widget, guide):
    guide_widget.set_guide(guide)
    assert guide_widget.run_progress.accessibleName() == "Scenario run progress"
    assert guide_widget.source_link.accessibleName() == "Open source guidance"
```

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_session_view_models.py -v`
Expected: PASS.

```powershell
git add ui/view_models.py ui/scenario_guide.py ui/routines.py tests/test_session_view_models.py
git commit -m "refactor: extract source-backed session guidance"
```

### Task 2: Five-destination application shell and status indicator

**Files:**
- Create: `ui/app_shell.py`
- Create: `ui/status_indicator.py`
- Create: `core/service_health.py`
- Modify: `ui/main_window.py`
- Modify: `style.qss`
- Test: `tests/test_app_shell.py`
- Test: `tests/test_status_indicator.py`

**Interfaces:**
- Produces: `ServiceStatus`, `AppShell.navigate(destination)`, `AppShell.destination_changed(str)`, `StatusIndicator.update_service(ServiceStatus)`, and `StatusIndicator.details_requested`.
- Consumes: five QWidget destinations and service status records.

- [ ] **Step 1: Write failing navigation and status tests**

```python
def test_shell_has_exactly_five_primary_destinations(shell):
    assert shell.destination_keys == ("home", "session", "progress", "library", "tools")

def test_status_selects_highest_severity_and_keeps_text(status_indicator):
    status_indicator.update_service(ServiceStatus("scores", "error", "Import failed", "Bad CSV"))
    status_indicator.update_service(ServiceStatus("updates", "busy", "Checking", ""))
    assert status_indicator.summary_text() == "Import failed"
    assert status_indicator.accessibleDescription() == "Bad CSV"
```

- [ ] **Step 2: Run and verify missing widgets**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_app_shell.py tests/test_status_indicator.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement shell and persistent indicator**

```python
DESTINATIONS = (
    ("home", "Home"),
    ("session", "Session"),
    ("progress", "Progress"),
    ("library", "Library"),
    ("tools", "Tools"),
)
SEVERITY = {"ok": 0, "busy": 1, "warning": 2, "error": 3}

@dataclass(frozen=True)
class ServiceStatus:
    service: str
    state: Literal["ok", "busy", "warning", "error", "offline"]
    summary: str
    details: str
    recovery_action: str = ""
    updated_at: datetime = field(default_factory=utc_now)
```

Use a `QStackedWidget`, checkable navigation buttons, and a top-bar indicator that is always present. The expanded status popover lists service, state text, timestamp, details, and recovery action. Include a text/icon state in addition to color.

- [ ] **Step 4: Replace `MainWindow` page ownership with shell composition**

`MainWindow` creates the five destinations, passes them to `AppShell`, routes score/sync/updater events to `StatusIndicator`, and retains setup/update/window-geometry lifecycle. Remove the nine-page sidebar creation after all destinations are wired.

- [ ] **Step 5: Run shell/startup tests and commit**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_app_shell.py tests/test_status_indicator.py tests/test_aim_hub.py -v`
Expected: PASS and exactly five page keys.

```powershell
git add core/service_health.py ui/app_shell.py ui/status_indicator.py ui/main_window.py style.qss tests
git commit -m "feat: add coaching-first application shell"
```

### Task 3: Coaching-first Home

**Files:**
- Create: `ui/home.py`
- Modify: `ui/dashboard.py`
- Modify: `ui/main_window.py`
- Test: `tests/test_home.py`

**Interfaces:**
- Produces: `HomeWidget.start_warmup`, `.start_step_by_step`, `.start_full_routine`, and `.set_view_model(HomeViewModel)`.
- Consumes: `CoachingSummary`, profile, recent session summary, and benchmark freshness.

- [ ] **Step 1: Write failing action and evidence tests**

```python
def test_home_places_three_training_actions_before_details(home, qtbot):
    assert [button.text() for button in home.primary_actions] == [
        "Warm-up", "Step-by-Step Training", "Full Routine"
    ]
    assert home.layout().indexOf(home.action_panel) < home.layout().indexOf(home.recent_progress)

def test_home_shows_evidence_and_confidence(home, summary):
    home.set_view_model(home_view(summary))
    assert summary.evidence.summary in home.evidence_label.text()
    assert summary.evidence.confidence.title() in home.confidence_label.text()
```

- [ ] **Step 2: Run and verify Home is missing**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_home.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement Home and action routing**

The top card shows rank/next rank, actionable weakness, trend, freshness confidence, and expandable evidence. The three action buttons emit intent only; `MainWindow` builds/loads a plan through domain services, starts it through `SessionCoordinator`, and navigates to Session.

```python
self.warmup_button.clicked.connect(self.start_warmup)
self.step_button.clicked.connect(self.start_step_by_step)
self.full_button.clicked.connect(self.start_full_routine)
```

- [ ] **Step 4: Retire Home/Today duplicate entry points and commit**

Keep reusable KPI widgets from `ui/dashboard.py`, but remove code that launches an old quick flow or navigates to Today.

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_home.py tests/test_aim_hub.py tests/test_training_intelligence.py -v`
Expected: PASS.

```powershell
git add ui/home.py ui/dashboard.py ui/main_window.py tests
git commit -m "feat: combine Home and Today around coaching actions"
```

### Task 4: Guided Session screen

**Files:**
- Create: `ui/session.py`
- Modify: `ui/main_window.py`
- Test: `tests/test_session_widget.py`

**Interfaces:**
- Produces: `SessionWidget.launch_requested`, `.manual_run_requested`, `.pause_requested`, `.stop_requested`, `.restart_requested`, `.next_requested`, `.set_state(SessionViewModel)`.
- Consumes: `ScenarioGuideWidget`, `SessionCoordinator`, and main/overview presentation models.

- [ ] **Step 1: Write failing detail and control-state tests**

```python
def test_selected_routine_shows_full_overview_and_current_guide(session_widget, full_view):
    session_widget.set_state(full_view)
    assert session_widget.overview.count() == len(full_view.steps)
    assert session_widget.guide.scenario_title.text() == full_view.current_guide.scenario
    assert session_widget.run_progress.maximum() == full_view.current_guide.required_runs

def test_next_disabled_until_step_complete(session_widget, running_view, completed_view):
    session_widget.set_state(running_view)
    assert not session_widget.next_button.isEnabled()
    session_widget.set_state(completed_view)
    assert session_widget.next_button.isEnabled()
```

- [ ] **Step 2: Run and verify Session widget is missing**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_session_widget.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement guided view and coordinator bindings**

Use a scrollable guide column, progress/control bar, and collapsible overview. Show evidence only for adaptive steps. The automatic/manual-next preference is a visible selector; manual Next remains disabled until completion.

```python
session_widget.launch_requested.connect(coordinator.launch_current)
session_widget.manual_run_requested.connect(coordinator.confirm_manual_run)
session_widget.pause_requested.connect(coordinator.pause)
session_widget.stop_requested.connect(lambda: coordinator.stop("user"))
```

- [ ] **Step 4: Add keyboard and scalable-layout assertions**

```python
def test_session_controls_are_keyboard_reachable(session_widget):
    controls = session_widget.action_controls()
    assert all(control.focusPolicy() != Qt.FocusPolicy.NoFocus for control in controls)
    assert all(control.accessibleName() for control in controls)
```

Avoid fixed widths on the guide and overview. Use minimum sizes only for compact controls.

- [ ] **Step 5: Run and commit**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_session_widget.py tests/test_session_view_models.py -v`
Expected: PASS.

```powershell
git add ui/session.py ui/main_window.py tests/test_session_widget.py
git commit -m "feat: add detailed guided session screen"
```

### Task 5: Shared-state compact overlay

**Files:**
- Create: `ui/session_overlay.py`
- Modify: `ui/session.py`
- Modify: `ui/main_window.py`
- Test: `tests/test_session_overlay.py`

**Interfaces:**
- Produces: `SessionOverlay.set_state(SessionViewModel)`, `.pause_requested`, `.stop_requested`, `.expanded_changed(bool)`.
- Consumes: the same `SessionCoordinator.on_state_changed` stream as `SessionWidget`.

- [ ] **Step 1: Write failing shared-state tests**

```python
def test_overlay_and_main_render_same_progress(main_session, overlay, view):
    main_session.set_state(view)
    overlay.set_state(view)
    assert overlay.progress.text() == main_session.progress_text()

def test_overlay_is_collapsed_by_default(overlay):
    assert overlay.is_expanded() is False
    assert overlay.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
```

- [ ] **Step 2: Run and verify overlay is missing**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_session_overlay.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement compact and expanded states**

Collapsed content is scenario, `completed / required` runs, primary cue, Pause, Stop, and Expand. Expanded content reuses `ScenarioGuideWidget`. Overlay buttons emit requests to the coordinator; they never mutate or copy session state.

- [ ] **Step 4: Persist opt-in visibility and geometry**

Default `overlay_enabled` to false. Store geometry and enabled state through existing settings. Show the overlay only while a session is active and the preference is enabled; hiding it does not pause or stop the session.

- [ ] **Step 5: Run and commit**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_session_overlay.py tests/test_session_widget.py -v`
Expected: PASS.

```powershell
git add ui/session_overlay.py ui/session.py ui/main_window.py tests/test_session_overlay.py
git commit -m "feat: add shared-state compact training panel"
```

### Task 6: Unified Progress hub

**Files:**
- Create: `ui/progress_hub.py`
- Modify: `ui/progress.py`
- Modify: `ui/skill_overview.py`
- Modify: `ui/stats.py`
- Modify: `ui/timeline.py`
- Test: `tests/test_progress_hub.py`

**Interfaces:**
- Produces: `ProgressHub.set_profile(profile, coaching_summary, freshness)` with tabs Summary, Skills, Benchmarks, History.
- Consumes: existing charts/tables and official profile.

- [ ] **Step 1: Write failing tab and conclusion-first tests**

```python
def test_progress_has_four_named_views(progress_hub):
    assert progress_hub.tab_names() == ("Summary", "Skills", "Benchmarks", "History")

def test_summary_text_precedes_charts(progress_hub, profile_view):
    progress_hub.set_view_model(profile_view)
    assert progress_hub.summary_layout.indexOf(progress_hub.conclusion) < progress_hub.summary_layout.indexOf(progress_hub.chart_container)
```

- [ ] **Step 2: Run and verify Progress hub is missing**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_progress_hub.py -v`
Expected: FAIL.

- [ ] **Step 3: Compose existing detail widgets behind conclusions**

Summary displays official rank, next-rank distance, weakness, trend, and freshness. Skills contains the nine subcategories. Benchmarks contains scenario targets/history and definition version. History contains session and trend detail. Incomplete rank must render `Unranked — benchmark N missing subcategories`, never energy `0` as Iron.

- [ ] **Step 4: Run and commit**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_progress_hub.py tests/test_progress_logic.py tests/test_training_intelligence.py -v`
Expected: PASS.

```powershell
git add ui/progress_hub.py ui/progress.py ui/skill_overview.py ui/stats.py ui/timeline.py tests/test_progress_hub.py
git commit -m "feat: merge skill and progress views"
```

### Task 7: Library, Tools, and obsolete-flow removal

**Files:**
- Create: `ui/library.py`
- Modify: `ui/tools.py`
- Modify: `ui/scenarios.py`
- Modify: `ui/deathmatch.py`
- Modify: `ui/routines.py`
- Modify: `ui/main_window.py`
- Test: `tests/test_library_and_tools.py`

**Interfaces:**
- Produces: `LibraryWidget` sections Routines, Scenarios, Warm-ups, Game Transfer; `ToolsWidget` secondary utility tabs.
- Consumes: existing routine/scenario/deathmatch/reference widgets and utility widgets.

- [ ] **Step 1: Write failing placement and removal tests**

```python
def test_deathmatch_is_library_reference_not_primary_mode(library, shell):
    assert "Deathmatch" in library.game_transfer_titles()
    assert "deathmatch" not in shell.destination_keys

def test_manual_game_observations_are_not_constructed(library, tools, home):
    assert not any(widget.objectName() == "game_observation" for widget in all_children(library, tools, home))
```

- [ ] **Step 2: Run and verify library is missing**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_library_and_tools.py -v`
Expected: FAIL.

- [ ] **Step 3: Compose Library and move secondary utilities**

Library routine selection emits `full_routine_requested(source_id)` and opens full source details before starting. Tools contains Sessions, Calendar, Compare, Routine Builder, Sensitivity, Backup, Settings, and Manual Import. Remove active UI calls to `record_game_observation`, `get_open_game_observations`, and `resolve_game_observation`; do not drop the historical table.

- [ ] **Step 4: Delete retired RoutineWidget paths after replacements pass**

Remove Home/Today/deathmatch mode switching, daily JSON state, game-review controls, and duplicate full-routine rendering from `ui/routines.py`. Keep only reusable components still imported; if none remain, delete the file and update imports.

- [ ] **Step 5: Run and commit**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_library_and_tools.py tests/test_scenario_browser.py tests/test_tool_logic.py tests/test_aim_hub.py -v`
Expected: PASS.

```powershell
git add ui tests
git commit -m "feat: organize references and secondary tools"
```

### Task 8: Accessibility, visual smoke, and interface phase gate

**Files:**
- Modify: `style.qss`
- Modify: `tests/test_aim_hub.py`
- Create: `tests/test_accessibility.py`
- Create: `scripts/smoke_ui.py`
- Modify: `README.md`
- Modify: `RELEASE_NOTES.md`

**Interfaces:**
- Verifies: keyboard navigation, accessible names, no clipped primary views at supported minimum window size, and all five destinations construct offscreen.

- [ ] **Step 1: Write failing accessibility smoke tests**

```python
@pytest.mark.parametrize("destination", ["home", "session", "progress", "library", "tools"])
def test_destination_has_named_focusable_controls(main_window, destination):
    main_window.shell.navigate(destination)
    controls = visible_focusable_controls(main_window.shell.currentWidget())
    assert controls
    assert all(control.accessibleName() or control.text() for control in controls)

def test_status_not_conveyed_by_color_only(status_indicator):
    status_indicator.update_service(ServiceStatus("scores", "error", "Import failed", "Bad CSV"))
    assert "failed" in status_indicator.text().casefold()
```

- [ ] **Step 2: Run and confirm failures identify unnamed controls**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/test_accessibility.py -v`
Expected: FAIL listing specific unnamed controls.

- [ ] **Step 3: Add names, focus, contrast, and scalable layout fixes**

Use visible focus styles in `style.qss`, replace fixed content widths/heights with layouts and scroll areas, and set accessible names/descriptions for icon-only and custom controls. Keep the established dark visual identity.

- [ ] **Step 4: Add a five-page construction smoke script**

```python
app = QApplication.instance() or QApplication([])
window = MainWindow()
for destination in window.shell.destination_keys:
    window.shell.navigate(destination)
    app.processEvents()
window.close()
```

- [ ] **Step 5: Run the interface phase gate**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python scripts/smoke_ui.py`
Expected: exit code 0.
Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q`
Expected: all tests PASS.
Run: `git diff --check`
Expected: no output.

- [ ] **Step 6: Commit interface verification and docs**

```powershell
git add style.qss tests/test_accessibility.py tests/test_aim_hub.py scripts/smoke_ui.py README.md RELEASE_NOTES.md
git commit -m "test: verify redesigned application interface"
```
