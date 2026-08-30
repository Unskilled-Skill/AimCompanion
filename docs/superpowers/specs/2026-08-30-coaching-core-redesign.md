# Aim Companion Coaching-Core Redesign

**Status:** Approved design  
**Date:** 2026-08-30  
**Target:** Aim Companion desktop application  

## 1. Purpose

Aim Companion should make it easier to begin, understand, and finish useful aim-training sessions. It must answer three questions clearly:

1. What should I train today?
2. How do I perform each scenario correctly?
3. Is my aim improving, and what is currently holding it back?

The product is designed first for the current user while remaining safe and understandable for broader public use. Tactical FPS training is the default emphasis, with other game contexts available as secondary choices.

The redesign replaces the fragmented collection of pages and partially overlapping training flows with a coaching core and three explicit training modes: **Warm-up**, **Step-by-Step Training**, and **Full Routine**.

## 2. Product principles

- Coaching and correct execution come before raw statistics.
- Every recommendation explains the evidence behind it.
- Authored routines remain source-exact. The app must not invent instructions, corrections, timings, or scenario substitutions and present them as official.
- Voltaic official definitions and rules determine official benchmark rank and progress.
- Local Kovaak's CSV data is the source for detailed history, trends, and session analysis.
- Training should be easy to start and safe to stop.
- Full routines preserve their official identity; adaptive or shortened training belongs to Step-by-Step mode.
- Synchronization and network failures must never prevent offline training.
- Automatic behavior should have an understandable manual fallback.

## 3. Scope

### 3.1 Included

- Correct, versioned Voltaic benchmark calculation and validation
- Background Kovaak's score importing
- A deterministic, evidence-backed coaching engine
- Warm-up, Step-by-Step, and Full Routine session engines
- Detailed, source-backed scenario guidance
- Persisted routine progress and adaptive circular resume
- A compact optional always-on-top training panel
- Consolidated navigation and progress reporting
- Database migration, crash recovery, and status reporting
- Tested GitHub release and auto-update workflow

### 3.2 Excluded

- Manual game observations as recommendation input
- Invented hnA technique advice not present in the supplied source
- Silent substitutions for unavailable official scenarios
- A visual companion or animated coach
- Community accounts, social features, or cloud score storage
- Treating a shortened or reordered session as an official completed hnA routine

Historical game-observation records may remain in storage for compatibility, but they are removed from the active interface and coaching logic.

## 4. Information architecture

The current top-level navigation is consolidated into five destinations.

### 4.1 Home

Home and Today become one coaching dashboard. It contains:

- Current rank and progress toward the next rank
- Strongest actionable weakness and recent trend
- Benchmark coverage and freshness
- A concise evidence statement for the recommendation
- Three large actions: Warm-up, Step-by-Step Training, and Full Routine
- Recent progress beneath the primary actions
- A small persistent system-status indicator

The page should lead with a conclusion, not a wall of charts. Detailed data remains available through Progress.

### 4.2 Session

Session is the guided execution surface shared by all three modes. The default view shows the current scenario and its complete guidance. A collapsible overview exposes the entire routine or generated plan.

### 4.3 Progress

Skill Matrix and Progress merge into one area with four views:

- Summary
- Skills and weaknesses
- Voltaic benchmarks
- Session history and detailed trends

Plain-language coaching conclusions precede detailed charts and tables.

### 4.4 Library

The Library remains a separate reference area for:

- hnA routines
- Voltaic benchmark material
- Scenario guides
- Warm-ups
- Game-transfer and deathmatch guidance

Deathmatch is reference and game-transfer material, not a fourth primary training mode.

### 4.5 Tools

Tools contains secondary utilities such as sensitivity, calendar, comparison, routine builder, backup, settings, and manual score import.

## 5. System architecture

The application is divided into five systems with explicit boundaries.

### 5.1 Benchmark engine

Responsibilities:

- Store versioned official benchmark definitions
- Normalize scenario aliases
- Convert scores to energy using the selected definition set
- Calculate subcategory and overall benchmark energy using official rules
- Determine rank and next-rank targets
- Synchronize or refresh official definitions
- Validate local results against the configured Voltaic profile
- Retain a usable offline cache

The engine must not depend on UI code or the recommendation engine.

### 5.2 Coaching engine

Responsibilities:

- Produce the Home coaching summary
- Determine benchmark health and due checks
- Rank weaknesses and trends
- Generate Step-by-Step recommendations
- Attach human-readable evidence and confidence to every conclusion
- Enforce rotation and repeat-prevention rules

Manual observations are not inputs.

### 5.3 Session engine

Responsibilities:

- Build immutable session plans from a mode and context
- Track official order, current position, runs, completion, pause, and stop state
- Persist state after each confirmed run and state transition
- Resume Full Routine sessions according to circular-completion rules
- Recover safely after application interruption
- Expose a UI-neutral session model to the main window and compact panel

### 5.4 Application services

Responsibilities:

- Watch and import Kovaak's score files
- Launch scenarios and guide installation when missing
- Synchronize Voltaic data
- Perform backups and database migrations
- Check and apply application updates
- Publish status and actionable errors
- Coordinate the compact panel

### 5.5 UI layer

The UI consumes the other systems through narrow interfaces. It does not calculate ranks, construct recommendation scores, or own session truth. The existing monolithic routine widget should be decomposed by responsibility rather than expanded further.

Existing parsing, database access, source content, launcher behavior, updater behavior, and charts should be reused where correct. Existing modules that mix configuration, discovery, recommendation scoring, and routine construction should be separated incrementally behind tested interfaces.

## 6. Benchmark correctness and synchronization

### 6.1 Official calculation

For a selected Voltaic benchmark definition set:

1. Map each eligible score to the correct scenario and benchmark version.
2. Convert the score to energy according to that definition's thresholds and caps.
3. For each aiming subcategory, select the **highest eligible scenario energy**.
4. Require at least one eligible result in every required subcategory before reporting complete overall benchmark energy.
5. Calculate overall energy as the **harmonic mean of all required subcategory energies**.
6. Determine rank from the official thresholds associated with that definition version.

Arithmetic averaging across attempts, scenarios, subcategories, or categories must not be labeled as official Voltaic energy. Alternative analytics may exist only if clearly named as local statistics.

The audit found that the current arithmetic calculation reports approximately 317.4 energy on the user's current data, while applying the documented best-per-subcategory harmonic calculation produces approximately 345.9. Correctness is therefore a release-blocking foundation item even though the current rank tier remains Silver.

### 6.2 Definition provenance

Every definition set stores:

- Official version identifier
- Retrieval time
- Source location
- Content checksum
- Scenario identities and aliases
- Subcategory membership
- Energy/rank thresholds and caps
- Active or retired status

The currently eligible official version is used for official rank. Older definitions remain available to interpret historical results.

### 6.3 Sync behavior

- Check definitions at startup without blocking the UI, then periodically according to a conservative refresh interval.
- Use a validated cached definition set when offline.
- Import Kovaak's CSV files as local history.
- After each import batch, recalculate locally and request Voltaic profile validation when configured and reachable.
- Show local calculation time, official/profile observation time, and known leaderboard delay separately.
- Never silently overwrite local history because an external value differs.
- Explain mismatches and retain enough metadata to diagnose version, timestamp, alias, or eligibility differences.

The external integration must sit behind a replaceable adapter because a stable public Voltaic API cannot be assumed. The adapter may consume only an official, permitted source. No brittle page scraping should be treated as a permanent correctness dependency.

## 7. Benchmark health

Benchmark freshness is tracked per subcategory using completed non-warm-up training blocks, not elapsed calendar days.

- A subcategory with no valid benchmark is immediately due.
- A subcategory becomes stale after **12 relevant training blocks** since its last valid benchmark check.
- Completing a benchmark resets only its relevant subcategory counter.
- Warm-up activity does not advance benchmark-staleness counters.
- Full Routine and Step-by-Step work advance counters for the subcategories they actually train.

When a benchmark is missing or stale, Step-by-Step recommends the relevant benchmark check before weakness training. Warm-up and Full Routine remain available, but the coaching summary clearly lowers confidence in weakness conclusions.

## 8. Recommendation model

Step-by-Step Training uses a deterministic weighted rotation across the three highest-priority weaknesses:

- Approximately 50% from the weakest priority
- Approximately 30% from the second priority
- Approximately 20% from the third priority

Selection rules:

- A due benchmark check takes precedence over ordinary weakness work.
- Avoid the same scenario consecutively.
- Avoid the same subcategory consecutively where another suitable choice exists.
- Trends, recent coverage, game suitability, and fatigue preferences may adjust choices without obscuring the base weakness priorities.
- Fatigue coaching is optional and off until the user opts in.
- The generated sequence must be deterministic for the same inputs, apart from an explicitly stored rotation cursor or seed.

Every recommendation contains evidence, for example:

> Precise Tracking is recommended because it is your lowest measured subcategory, is 8% below your median subcategory energy, and has not been trained in the last five blocks. Benchmark confidence: current.

Evidence records identify the scores, trend window, freshness state, rule, and definition version used. The UI can summarize this text while allowing the supporting detail to expand.

## 9. Training modes

### 9.1 Warm-up

Warm-up is a short preparatory session, separate from progression work.

Supported contexts:

- **Game-specific:** prepares for the selected game, with tactical FPS defaults.
- **Routine-specific:** prepares the movements and broader skill range required by a selected routine.

The app remembers the last warm-up context and selects it automatically on the next visit. The selector remains visible so it can be changed without answering a blocking prompt. Where context can be inferred from the current session intent, the app may select it automatically.

Stopping a warm-up never alters Full Routine progress. Warm-up results may be stored for history but do not drive benchmark freshness or official progression conclusions.

### 9.2 Step-by-Step Training

Step-by-Step mode presents one focused block at a time and is the adaptive option for limited or uncertain time.

- Each block lasts approximately 3–5 minutes.
- The priority order is: due benchmark check, measured weakness, negative trend, then neglected coverage.
- The user may stop after any block without failing a routine.
- The next block is chosen using the recommendation and repeat-prevention rules.
- The app supports configurable automatic launch or a manual **Next scenario** action.
- The mode continues until the user stops; it does not pretend to be a shortened official routine.

### 9.3 Full Routine

Full Routine preserves exact source content, prescribed runs, official order, and routine identity. The guided view is the default, with the complete routine overview always available.

#### Circular resume rule

If the official sequence is `A -> B -> C -> D -> E` and the previous session completed A and B, the next session begins at C and runs:

`C -> D -> E -> A -> B -> stop`

It stops at the point where that day's cycle began. It must not continue into C again. This produces one complete pass through the routine while prioritizing previously unfinished material. After that wrapped pass completes, the following session resets to the official start at A.

If a scenario was stopped before all prescribed runs were complete, that scenario is considered unfinished and restarts with its full prescribed run count next time. Partial run completion does not reduce the official requirement.

### 9.4 Guided scenario content

Before and during every scenario, the Session screen shows:

- Purpose and trained skill
- Setup
- Source-backed execution steps
- Success criteria
- Prescribed runs and estimated time
- Current run progress
- Source attribution
- Common mistakes and adjustments only when explicitly supported by the source

If the source does not provide a mistake or correction, that field is omitted. Generated advice must never be styled or attributed as hnA guidance.

## 10. Session interface and compact panel

The normal Session screen includes:

- Mode, context, and routine identity
- Current scenario and progress
- Full guidance
- Start or launch action
- Pause, stop, restart, and next controls as appropriate
- Automatic/manual-next preference
- Collapsible plan or routine overview
- Recommendation evidence when the plan is adaptive

An optional always-on-top compact panel is available while Kovaak's is open. It is collapsed by default and displays:

- Current scenario
- Current and required runs
- One primary technique cue
- Pause and stop controls

It can expand to the complete source guide. The compact panel and main Session screen bind to the same session state and cannot advance independently.

## 11. Persistence and recovery

### 11.1 Durable session state

A session plan records:

- Mode and context
- Source and routine version
- Official scenario order
- Generated order when applicable
- Starting boundary and current position
- Required and confirmed runs
- Pause, stop, completion, and recovery states
- Reason for termination
- Whether the next session resumes or resets

State is committed after each detected or manually confirmed run and after every meaningful transition. A crash should lose at most the current unconfirmed run.

### 11.2 Schema evolution

Versioned migrations introduce structures for:

- Benchmark definition sets and aliases
- Sync and validation state
- Session plans and scenario progress
- Confirmed session runs
- Per-subcategory activity counters
- Recommendation evidence
- Warm-up context and preferences

Migrations are incremental, tested against representative existing databases, and preceded by a recoverable backup. Existing scores, sessions, settings, and historical observations are preserved.

## 12. Automatic score importing

A background service monitors the configured Kovaak's score directory.

- New and changed files are imported automatically.
- File events are debounced so incomplete writes are not parsed.
- File identity and score identity prevent duplicate imports.
- Out-of-order files are accepted according to their recorded score timestamps.
- A failed file is isolated and reported without stopping the watcher.
- Manual import remains available as a secondary fallback.
- Each completed batch triggers trend updates, benchmark recalculation, optional profile validation, and active-session run detection.

Startup scanning remains necessary to recover events missed while the app was closed.

## 13. Missing scenarios and installation guidance

Before launching, the app verifies that the selected official scenario can be resolved. When it cannot:

- Explain exactly which scenario is missing.
- Provide source-appropriate installation or subscription steps.
- Offer to open the correct Kovaak's destination where supported.
- Recheck availability after the user completes installation.
- Preserve the current session position.

The app must not silently skip, replace, or rename the scenario. If the user chooses to stop, normal resume rules apply.

## 14. Status and failure handling

A small persistent indicator communicates:

- Score import activity or failure
- Voltaic definition/profile sync state
- Offline cached-data use
- Database migration or recovery issues
- Missing scenarios
- Application update availability or failure

The indicator expands into plain-language details, timestamps, affected features, and recovery actions. Transient network failures do not interrupt local training. Errors must not be reported only through modal dialogs when the user can safely continue.

## 15. Privacy and security

- Do not store Voltaic credentials unless a future official authentication flow requires them and a secure storage mechanism is implemented.
- Prefer a public profile identifier or URL for validation.
- Treat downloaded benchmark definitions and update metadata as untrusted input and validate their schema and integrity.
- Continue checksum verification for application releases.
- Keep user scores and detailed history local unless the user explicitly opts into a supported external integration.

## 16. Testing and acceptance criteria

Core domain logic must be independent of PyQt and tested deterministically.

Required automated coverage includes:

- Official score-to-energy boundaries and caps
- Best-scenario selection within a subcategory
- Nine-subcategory harmonic mean and missing-subcategory behavior
- Rank thresholds for versioned definitions
- Definition alias and historical-version selection
- Profile-validation agreement and mismatch explanations
- Cached offline definitions
- Twelve-block per-subcategory staleness
- 50/30/20 rotation over representative sequences
- Same-scenario and same-subcategory repeat prevention
- Warm-up context memory and counter exclusion
- Full Routine official-order completion
- Circular resume boundary and single wrapped pass
- Partial scenario full-run restart
- Crash recovery after each state transition
- File watcher debounce, duplicate, out-of-order, malformed, and startup-scan behavior
- Missing-scenario installation flow
- Main/compact Session state consistency
- Database migration from existing application data
- Updater metadata, checksum, and prior-version upgrade behavior

CI gates:

- Unit and integration tests
- UI startup smoke test
- Linting with an agreed baseline, then no new violations
- Windows packaging test
- At least 80% coverage for newly introduced benchmark, coaching, and session core modules

Accessibility verification includes keyboard navigation, visible focus, readable contrast, scalable layouts, useful accessible names, and operation without relying on color alone.

## 17. Delivery phases

### Phase 1: Accuracy foundation

- Extract benchmark domain logic
- Implement official calculation rules
- Add versioned definitions and migrations
- Add automatic imports and validation interfaces
- Correct rank/progress displays

### Phase 2: Session engine

- Add durable session plans
- Implement all three modes
- Implement circular Full Routine resume
- Connect run detection and manual confirmation
- Add evidence-backed recommendation rotation

### Phase 3: Interface redesign

- Combine Home and Today
- Add the guided Session screen
- Merge Skill Matrix and Progress
- Reorganize Library and Tools
- Add compact panel
- Remove manual observations from active UI

### Phase 4: Synchronization and hardening

- Complete official definition/profile adapters
- Add offline and mismatch UX
- Add installation guidance
- Complete accessibility and migration testing
- Resolve accumulated lint and architecture debt that affects the redesigned paths

Each phase must leave the stable application usable. Feature flags or migrations may keep unfinished replacement surfaces hidden until their acceptance tests pass.

## 18. GitHub release and auto-update contract

Every stable user-facing release follows this sequence:

1. Run the complete verification suite.
2. Update the application version and release notes.
3. Build the Windows package or installer.
4. Commit and push the release state to GitHub.
5. Create and push the version tag.
6. Publish a GitHub release containing the application asset and checksum.
7. Verify public updater metadata, asset naming, checksum, and download behavior.
8. Test an upgrade from the immediately preceding installed version.

A change is not described as released merely because it exists in the repository. Release completion requires verified GitHub assets and a working updater path. Stable application updates should always be published to GitHub, as requested by the user.

## 19. Success criteria

The redesign is successful when:

- Opening the app immediately explains current progress and the most useful next action.
- Selecting any routine shows the complete routine and detailed source-backed execution guidance.
- A user can start useful training without committing to an hour.
- A user can complete a source-exact full routine across interrupted sessions without repeatedly neglecting later scenarios.
- Local Voltaic rank calculations match the documented official method for the same eligible definition set and inputs.
- Every coaching recommendation exposes evidence and freshness confidence.
- New Kovaak's results appear automatically with a reliable manual fallback.
- Offline, sync, missing-scenario, and update failures are understandable and recoverable.
- A published update is discoverable and installable by the existing application.

