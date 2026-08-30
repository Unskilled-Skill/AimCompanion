# Coaching and Session Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic evidence-backed recommendations and durable Warm-up, Step-by-Step, and Full Routine sessions that can be stopped and resumed safely.

**Architecture:** Pure domain modules own plans, state transitions, freshness, and recommendation selection. A repository serializes domain state to SQLite, while a coordinator connects imported runs and launch actions to the session engine. UI work is deliberately deferred to the interface plan.

**Tech Stack:** Python 3.12, dataclasses/enums, JSON, SQLite, existing benchmark engine and Kovaak's launcher, pytest

**Spec:** `docs/superpowers/specs/2026-08-30-coaching-core-redesign.md`

## Global Constraints

- Modes are exactly `warmup`, `step_by_step`, and `full_routine`.
- Full Routine preserves authored scenario order and prescribed runs.
- A partial scenario restarts with its full prescribed run count next time.
- A wrapped routine stops before repeating its starting scenario and resets to official order after completion.
- Step-by-Step blocks are 3–5 minutes and may be stopped after any block.
- Due benchmark checks precede weakness work.
- Weakness rotation targets 50/30/20 with scenario and subcategory repeat prevention.
- Benchmark freshness is per subcategory and due after 12 relevant non-warm-up blocks.
- Warm-up context is remembered and does not change routine progress or freshness counters.
- Manual game observations are not recommendation inputs.
- Every recommendation contains evidence and confidence.
- Authored source guidance may be displayed verbatim from bundled structured data; absent corrections remain absent.

---

## File structure

- `core/sessions/model.py`: session enums and immutable plan/step/state records.
- `core/sessions/engine.py`: legal state transitions and circular Full Routine behavior.
- `core/sessions/builders.py`: source-exact routine and context-aware warm-up plan construction.
- `core/sessions/repository.py`: SQLite serialization and crash recovery.
- `core/coaching/freshness.py`: 12-block subcategory counters.
- `core/coaching/evidence.py`: structured coaching evidence and rendering.
- `core/coaching/recommender.py`: due-check precedence and deterministic 50/30/20 rotation.
- `core/coaching/summary.py`: Home conclusion model.
- `core/session_coordinator.py`: bridges runs, launching, repository, and domain engine.
- `models/migrations.py`: session, progress, counter, evidence, and preference tables.

### Task 1: Session domain model and legal transitions

**Files:**
- Create: `core/sessions/__init__.py`
- Create: `core/sessions/model.py`
- Create: `core/sessions/engine.py`
- Test: `tests/test_session_engine.py`

**Interfaces:**
- Produces: `SessionMode`, `SessionStatus`, `SessionStep`, `SessionPlan`, `SessionState`, and `SessionEngine` methods `start()`, `confirm_run()`, `pause()`, `resume()`, `stop()`, `restart_step()`.
- Consumes: no database or UI types.

- [ ] **Step 1: Write failing transition tests**

```python
def test_confirming_required_runs_advances_to_next_step(plan):
    state = SessionEngine.start(plan)
    state = SessionEngine.confirm_run(state)
    assert state.current_step_index == 0
    state = SessionEngine.confirm_run(state)
    assert state.current_step_index == 1
    assert state.confirmed_runs == 0

def test_stopped_session_rejects_more_runs(plan):
    state = SessionEngine.stop(SessionEngine.start(plan), reason="user")
    with pytest.raises(InvalidSessionTransition, match="stopped"):
        SessionEngine.confirm_run(state)
```

- [ ] **Step 2: Run and verify missing session package**

Run: `python -m pytest tests/test_session_engine.py -v`
Expected: FAIL with missing `core.sessions`.

- [ ] **Step 3: Implement immutable domain records**

```python
class SessionMode(StrEnum):
    WARMUP = "warmup"
    STEP_BY_STEP = "step_by_step"
    FULL_ROUTINE = "full_routine"

class SessionStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    COMPLETED = "completed"

@dataclass(frozen=True)
class SessionStep:
    scenario: str
    required_runs: int
    estimated_seconds: int
    category: str
    subcategory: str
    guide: Mapping[str, object]
    source: str
    source_url: str

@dataclass(frozen=True)
class SessionPlan:
    mode: SessionMode
    source_id: str
    source_version: str
    steps: tuple[SessionStep, ...]
    official_steps: tuple[SessionStep, ...]
    start_boundary: int = 0
    initial_confirmed_runs: int = 0

@dataclass(frozen=True)
class SessionState:
    plan: SessionPlan
    status: SessionStatus
    current_step_index: int
    confirmed_runs: int
    started_at: datetime
    updated_at: datetime
    stop_reason: str = ""

    @property
    def current_step(self) -> SessionStep:
        return self.plan.steps[self.current_step_index]
```

All `SessionEngine` methods return a replaced state and validate transitions. A run advances only when `confirmed_runs == required_runs`; no UI callback mutates fields directly.

- [ ] **Step 4: Add overrun, pause, restart, and completion tests**

```python
def test_restart_step_discards_partial_runs(plan):
    state = SessionEngine.confirm_run(SessionEngine.start(plan))
    assert SessionEngine.restart_step(state).confirmed_runs == 0

def test_confirm_run_rejects_paused_state(plan):
    with pytest.raises(InvalidSessionTransition, match="paused"):
        SessionEngine.confirm_run(SessionEngine.pause(SessionEngine.start(plan)))
```

- [ ] **Step 5: Run and commit**

Run: `python -m pytest tests/test_session_engine.py -v`
Expected: PASS.

```powershell
git add core/sessions tests/test_session_engine.py
git commit -m "feat: add durable session state machine"
```

### Task 2: Source-exact builders and circular Full Routine resume

**Files:**
- Create: `core/sessions/builders.py`
- Modify: `core/training_methods.py`
- Modify: `core/warmups.py`
- Test: `tests/test_session_builders.py`
- Test: `tests/test_full_routine_resume.py`

**Interfaces:**
- Produces: `build_full_routine_plan(routine, resume_index) -> SessionPlan`, `build_warmup_plan(context, target_id) -> SessionPlan`, and `next_full_routine_resume(completed_boundary, step_count, completed_cycle) -> int`.
- Consumes: bundled `data/tacfps_guide.json`, existing Voltaic routines, and warm-up definitions.

- [ ] **Step 1: Write failing exactness and wrap tests**

```python
def test_full_routine_keeps_authored_order_and_runs(hna_speed_stopping):
    plan = build_full_routine_plan(hna_speed_stopping, resume_index=0)
    assert [step.scenario for step in plan.steps] == [item["scenario"] for item in hna_speed_stopping["exercises"]]
    assert [step.required_runs for step in plan.steps] == [item["duration_min"] for item in hna_speed_stopping["exercises"]]

def test_resume_after_b_runs_c_d_e_a_b_then_stops(five_step_routine):
    plan = build_full_routine_plan(five_step_routine, resume_index=2)
    assert [step.scenario for step in plan.steps] == ["C", "D", "E", "A", "B"]
    assert plan.start_boundary == 2
```

- [ ] **Step 2: Verify the builder functions are missing**

Run: `python -m pytest tests/test_session_builders.py tests/test_full_routine_resume.py -v`
Expected: FAIL on missing builder imports.

- [ ] **Step 3: Implement rotation without altering authored content**

```python
def rotate_once(items: Sequence[T], start: int) -> tuple[T, ...]:
    if not items:
        raise ValueError("routine must contain at least one scenario")
    index = start % len(items)
    return tuple(items[index:]) + tuple(items[:index])

def build_full_routine_plan(routine: Mapping[str, object], resume_index: int) -> SessionPlan:
    authored = tuple(step_from_source(item, routine) for item in routine["exercises"])
    return SessionPlan(
        mode=SessionMode.FULL_ROUTINE,
        source_id=str(routine["name"]),
        source_version=str(routine["source"]),
        steps=rotate_once(authored, resume_index),
        official_steps=authored,
        start_boundary=resume_index,
    )
```

`step_from_source` copies `performance_guide` keys exactly. It does not create `adjust` or mistakes keys when absent.

- [ ] **Step 4: Add partial-scenario and reset tests**

```python
def test_partial_scenario_restarts_full_requirement(next_session_for_partial_c):
    assert next_session_for_partial_c.steps[0].scenario == "C"
    assert next_session_for_partial_c.steps[0].required_runs == 7
    assert next_session_for_partial_c.initial_confirmed_runs == 0

def test_completed_wrapped_cycle_resets_next_session_to_a(five_step_routine):
    assert next_full_routine_resume(completed_boundary=2, step_count=5, completed_cycle=True) == 0
```

- [ ] **Step 5: Run source exactness tests and commit**

Run: `python -m pytest tests/test_session_builders.py tests/test_full_routine_resume.py tests/test_training_intelligence.py -v`
Expected: PASS, including existing hnA run-count assertions.

```powershell
git add core/sessions/builders.py core/training_methods.py core/warmups.py tests
git commit -m "feat: build resumable source-exact routines"
```

### Task 3: Session migrations and repository

**Files:**
- Modify: `models/migrations.py`
- Create: `core/sessions/repository.py`
- Test: `tests/test_session_repository.py`

**Interfaces:**
- Produces: `SessionRepository.create(plan) -> SessionState`, `.save(state)`, `.load_active() -> SessionState | None`, `.finish(state)`, `.full_routine_resume(source_id) -> int`.
- Consumes: SQLite connection and JSON serialization of Task 1 domain records.

- [ ] **Step 1: Write failing round-trip and crash recovery tests**

```python
def test_active_state_round_trips_after_each_run(repository, plan):
    state = repository.create(plan)
    state = SessionEngine.confirm_run(state)
    repository.save(state)
    assert repository.load_active() == state

def test_partial_step_recovers_at_zero_runs_for_next_session(repository, full_plan):
    state = SessionEngine.confirm_run(repository.create(full_plan))
    repository.save(SessionEngine.stop(state, reason="user"))
    resumed = repository.build_resumed_full_plan(full_plan.source_id)
    assert resumed.steps[0].scenario == full_plan.steps[0].scenario
    assert resumed.initial_confirmed_runs == 0
```

- [ ] **Step 2: Verify repository symbols are missing**

Run: `python -m pytest tests/test_session_repository.py -v`
Expected: FAIL with missing repository module.

- [ ] **Step 3: Add schema version 3 session tables**

Create tables `session_plans`, `session_steps`, `session_state`, and `session_runs`. Enforce one active session with a partial unique index on statuses `ready`, `running`, and `paused`. Store source order and execution order separately; use foreign keys and `ON DELETE CASCADE` only for new session-owned rows.

```sql
CREATE UNIQUE INDEX one_active_session
ON session_state((1))
WHERE status IN ('ready', 'running', 'paused');
```

- [ ] **Step 4: Implement transactional save and recovery**

```python
def save(self, state: SessionState) -> None:
    with self._connection:
        self._update_state_row(state)
        self._replace_confirmed_run_rows(state)
```

On application recovery, an active `running` state becomes `paused` with stop reason `application_recovered`; confirmed runs remain. Starting a later session after a user-stopped partial Full Routine restarts the step from zero.

- [ ] **Step 5: Run migration/repository tests and commit**

Run: `python -m pytest tests/test_session_repository.py tests/test_migrations.py tests/test_database.py -v`
Expected: PASS.

```powershell
git add models/migrations.py core/sessions/repository.py tests/test_session_repository.py
git commit -m "feat: persist and recover training sessions"
```

### Task 4: Per-subcategory benchmark freshness

**Files:**
- Create: `core/coaching/__init__.py`
- Create: `core/coaching/freshness.py`
- Modify: `models/migrations.py`
- Test: `tests/test_benchmark_freshness.py`

**Interfaces:**
- Produces: `FreshnessState`, `BenchmarkFreshness.record_block(subcategories, warmup)`, `.record_benchmark(subcategory)`, and `.status(required_subcategories) -> Mapping[str, FreshnessState]`.
- Consumes: SQLite `subcategory_activity` rows.

- [ ] **Step 1: Write failing 12-block tests**

```python
def test_subcategory_is_due_on_twelfth_relevant_block(freshness):
    freshness.record_benchmark("Clicking / Static")
    for _ in range(11):
        freshness.record_block(["Clicking / Static"], warmup=False)
    assert freshness.status(["Clicking / Static"])["Clicking / Static"].due is False
    freshness.record_block(["Clicking / Static"], warmup=False)
    assert freshness.status(["Clicking / Static"])["Clicking / Static"].due is True

def test_warmup_does_not_advance_counter(freshness):
    freshness.record_benchmark("Tracking / Reactive")
    freshness.record_block(["Tracking / Reactive"], warmup=True)
    assert freshness.status(["Tracking / Reactive"])["Tracking / Reactive"].blocks_since_check == 0
```

- [ ] **Step 2: Run and confirm missing freshness module**

Run: `python -m pytest tests/test_benchmark_freshness.py -v`
Expected: FAIL.

- [ ] **Step 3: Add schema version 4 and freshness service**

```python
@dataclass(frozen=True)
class FreshnessState:
    subcategory: str
    measured: bool
    blocks_since_check: int
    due: bool
    confidence: Literal["missing", "stale", "current"]
```

Missing is always due. Measured values are current for counters 0–11 and stale/due at 12. Benchmark completion resets only the exact subcategory row.

- [ ] **Step 4: Run and commit**

Run: `python -m pytest tests/test_benchmark_freshness.py tests/test_migrations.py -v`
Expected: PASS.

```powershell
git add core/coaching models/migrations.py tests/test_benchmark_freshness.py
git commit -m "feat: track benchmark freshness by training blocks"
```

### Task 5: Evidence-backed deterministic recommendations

**Files:**
- Create: `core/coaching/evidence.py`
- Create: `core/coaching/recommender.py`
- Create: `core/coaching/summary.py`
- Modify: `core/recommender.py`
- Modify: `core/training_intelligence.py`
- Test: `tests/test_coaching_recommender.py`
- Test: `tests/test_coaching_summary.py`

**Interfaces:**
- Produces: `Recommendation`, `RecommendationEvidence`, `RotationState`, `CoachingRecommender.next(context) -> Recommendation`, and `build_coaching_summary(profile, trends, freshness) -> CoachingSummary`.
- Consumes: official profile, trend summaries, scenario catalog, freshness, recent recommendations, opt-in fatigue flag.

- [ ] **Step 1: Write failing precedence, distribution, and evidence tests**

```python
def test_due_benchmark_precedes_weakness_work(context_with_due_static):
    pick = CoachingRecommender().next(context_with_due_static)
    assert pick.kind == "benchmark_check"
    assert pick.subcategory == "Clicking / Static"

def test_rotation_is_fifty_thirty_twenty_without_consecutive_subcategories(context):
    picks = generate_picks(context, count=10)
    assert Counter(p.priority_rank for p in picks) == Counter({1: 5, 2: 3, 3: 2})
    assert all(left.subcategory != right.subcategory for left, right in pairwise(picks))

def test_recommendation_explains_inputs(context):
    pick = CoachingRecommender().next(context)
    assert pick.evidence.rule == "weakness_rotation"
    assert pick.evidence.definition_version == "kovaaks_s5"
    assert pick.evidence.summary
```

- [ ] **Step 2: Verify current recommender fails the new contract**

Run: `python -m pytest tests/test_coaching_recommender.py tests/test_coaching_summary.py -v`
Expected: FAIL because recommendation evidence and rotation state are absent.

- [ ] **Step 3: Implement a ten-slot deterministic schedule**

```python
ROTATION = (1, 2, 1, 3, 1, 2, 1, 3, 1, 2)

@dataclass(frozen=True)
class RotationState:
    cursor: int = 0
    last_scenario: str = ""
    last_subcategory: str = ""

@dataclass(frozen=True)
class RecommendationEvidence:
    rule: str
    summary: str
    definition_version: str
    confidence: Literal["low", "medium", "high"]
    score_ids: tuple[int, ...]
    trend_window: int
    blocks_since_benchmark: int | None

@dataclass(frozen=True)
class Recommendation:
    kind: Literal["benchmark_check", "weakness", "trend", "coverage"]
    scenario: str
    category: str
    subcategory: str
    priority_rank: int
    estimated_seconds: int
    guide: Mapping[str, object]
    evidence: RecommendationEvidence

@dataclass(frozen=True)
class ScenarioCandidate:
    scenario: str
    category: str
    subcategory: str
    estimated_seconds: int
    guide: Mapping[str, object]

@dataclass(frozen=True)
class CoachingSummary:
    headline: str
    rank_text: str
    next_rank_text: str
    weakness_text: str
    trend_text: str
    evidence: RecommendationEvidence

@dataclass(frozen=True)
class RecommendationContext:
    profile: PlayerProfile
    freshness: Mapping[str, FreshnessState]
    trends: Mapping[str, float]
    candidates: tuple[ScenarioCandidate, ...]
    rotation: RotationState
    fatigue_coaching_enabled: bool = False
```

At each cursor, try the assigned priority first, then other priorities only to prevent a consecutive scenario/subcategory or to handle no suitable candidate. Persist the cursor after a block is accepted, not when merely previewed. Manual observations must not appear in `RecommendationContext`.

- [ ] **Step 4: Remove observation influence and gate fatigue**

Delete observation reads from active recommendation paths in `core/recommender.py`, `core/training_intelligence.py`, and `models/config.py`. Retain database methods for historical compatibility. Add `fatigue_coaching_enabled: bool = False` to coaching preferences and ignore fatigue signals unless true.

- [ ] **Step 5: Run legacy and new recommendation tests**

Run: `python -m pytest tests/test_coaching_recommender.py tests/test_coaching_summary.py tests/test_recommender.py tests/test_training_intelligence.py -v`
Expected: PASS after replacing tests that expected manual observations to change picks with tests proving they do not.

- [ ] **Step 6: Commit recommendation core**

```powershell
git add core/coaching core/recommender.py core/training_intelligence.py models/config.py tests
git commit -m "feat: recommend training with evidence and rotation"
```

### Task 6: Warm-up preference and Step-by-Step plan continuation

**Files:**
- Modify: `core/sessions/builders.py`
- Modify: `core/sessions/repository.py`
- Modify: `models/migrations.py`
- Test: `tests/test_warmup_context.py`
- Test: `tests/test_step_by_step_session.py`

**Interfaces:**
- Produces: `WarmupPreferenceRepository.get()`, `.set(context, target_id)` and `append_step_by_step_recommendation(state, recommendation) -> SessionState`.
- Consumes: `Recommendation` and source-backed scenario guide catalog.

- [ ] **Step 1: Write failing preference and block-duration tests**

```python
def test_last_warmup_context_is_selected_without_prompt(preferences):
    preferences.set("game", "Valorant")
    assert preferences.get() == WarmupPreference(context="game", target_id="Valorant")

def test_step_by_step_block_is_between_three_and_five_minutes(recommendation):
    state = append_step_by_step_recommendation(empty_step_state(), recommendation)
    assert 180 <= state.plan.steps[-1].estimated_seconds <= 300
```

- [ ] **Step 2: Run and verify missing APIs**

Run: `python -m pytest tests/test_warmup_context.py tests/test_step_by_step_session.py -v`
Expected: FAIL.

- [ ] **Step 3: Add schema version 5 preference and rotation state**

Store one `warmup_preference` row and one `coaching_rotation_state` row. Context values are constrained to `game` and `routine`; invalid stored values fall back to `game`/`Valorant` without a modal prompt.

```python
@dataclass(frozen=True)
class WarmupPreference:
    context: Literal["game", "routine"]
    target_id: str
```

- [ ] **Step 4: Implement broad routine warm-ups and incremental plans**

Routine-specific warm-up candidates must cover at least two distinct subcategories represented by the target routine when the source catalog permits. Game-specific candidates come from the exact selected game context. Step-by-Step appends one block only after the previous block completes and the user has not stopped.

- [ ] **Step 5: Run and commit**

Run: `python -m pytest tests/test_warmup_context.py tests/test_step_by_step_session.py tests/test_session_builders.py -v`
Expected: PASS.

```powershell
git add core/sessions models/migrations.py tests/test_warmup_context.py tests/test_step_by_step_session.py
git commit -m "feat: remember warmups and extend step training"
```

### Task 7: Session coordinator and run confirmation

**Files:**
- Create: `core/session_coordinator.py`
- Modify: `core/run_tracker.py`
- Modify: `core/kovaaks_launcher.py`
- Test: `tests/test_session_coordinator.py`

**Interfaces:**
- Produces: `SessionCoordinator.start(plan)`, `.launch_current()`, `.confirm_detected_runs(scores)`, `.confirm_manual_run()`, `.pause()`, `.stop()`, and observer callback `on_state_changed(SessionState)`.
- Consumes: `SessionRepository`, `SessionEngine`, `KovaaksRunTracker`, and launcher functions.

- [ ] **Step 1: Write failing automatic/manual parity tests**

```python
def test_detected_and_manual_runs_use_same_state_transition(coordinators):
    automatic, manual = coordinators
    automatic.confirm_detected_runs([matching_score()])
    manual.confirm_manual_run()
    assert automatic.state.confirmed_runs == manual.state.confirmed_runs == 1

def test_wrong_scenario_result_does_not_advance(coordinator):
    coordinator.confirm_detected_runs([score_for("Different Scenario")])
    assert coordinator.state.confirmed_runs == 0
```

- [ ] **Step 2: Run and confirm coordinator is missing**

Run: `python -m pytest tests/test_session_coordinator.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement coordinator with save-after-transition**

```python
def _apply(self, transition: Callable[[SessionState], SessionState]) -> SessionState:
    self.state = transition(self.state)
    self.repository.save(self.state)
    self.on_state_changed(self.state)
    return self.state
```

Canonicalize scenario names with the existing launcher normalization. `launch_current()` starts the tracker before opening the deep link. Automatic/manual next is a preference consumed only after a step reaches its required run count.

- [ ] **Step 4: Verify crash boundary and full phase**

Run: `python -m pytest tests/test_session_coordinator.py tests/test_session_repository.py tests/test_full_routine_resume.py -v`
Expected: PASS.
Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q`
Expected: all tests PASS.

- [ ] **Step 5: Commit coordinator**

```powershell
git add core/session_coordinator.py core/run_tracker.py core/kovaaks_launcher.py tests/test_session_coordinator.py
git commit -m "feat: coordinate guided training sessions"
```

### Task 8: Phase documentation and verification

**Files:**
- Modify: `README.md`
- Modify: `RELEASE_NOTES.md`
- Create: `docs/training-modes.md`

**Interfaces:**
- Documents: mode semantics, circular resume example, manual fallback, 12-block freshness, evidence, and fatigue opt-in.

- [ ] **Step 1: Document the exact resume example**

Include `A -> B -> C -> D -> E`, previous stop after B, next execution `C -> D -> E -> A -> B -> stop`, and reset to A on the following session. State that a partially completed scenario restarts all prescribed runs.

- [ ] **Step 2: Run the phase gate**

Run: `$env:QT_QPA_PLATFORM='offscreen'; python -m pytest -q`
Expected: PASS.
Run: `python -m compileall -q core models ui tests`
Expected: exit code 0.
Run: `git diff --check`
Expected: no output.

- [ ] **Step 3: Commit documentation**

```powershell
git add README.md RELEASE_NOTES.md docs/training-modes.md
git commit -m "docs: explain coaching and training sessions"
```
