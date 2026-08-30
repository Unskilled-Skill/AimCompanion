# Coaching-Core Redesign Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan set task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Coordinate the four independently testable implementation plans for Aim Companion 2.0.0.

**Architecture:** Execute the plans in dependency order. Each plan ends with a full-suite gate and preserves a usable application; the final plan publishes the verified Windows release.

**Tech Stack:** Python 3.12, PyQt6, SQLite, pytest, Ruff, PyInstaller, Inno Setup, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-08-30-coaching-core-redesign.md`

## Global Constraints

- Read the approved specification and the active child plan before changing code.
- Use test-driven development for every feature and bug-fix task.
- Use a fresh isolated git worktree before executing the first child plan.
- Commit after each child-plan task and run that task's focused test command first.
- Do not begin a dependent plan until the preceding plan's full phase gate passes.
- Preserve user data and unrelated working-tree changes.
- Publish only the final verified stable application update to GitHub as version 2.0.0.

---

## Execution order

- [ ] **Plan 1: Benchmark accuracy and automatic imports**

Execute `docs/superpowers/plans/2026-08-30-benchmark-accuracy-and-imports.md` completely. Required gate: official best-per-subcategory harmonic calculation, recoverable migrations, deterministic import batches, background watcher, and full test suite pass.

- [ ] **Plan 2: Coaching and session engine**

Execute `docs/superpowers/plans/2026-08-30-coaching-and-session-engine.md` completely. It consumes Plan 1's `BenchmarkResult`, `PlayerProfile`, migrations, and importer events. Required gate: all three modes, circular Full Routine resume, 12-block freshness, 50/30/20 evidence-backed recommendations, and full test suite pass.

- [ ] **Plan 3: Interface redesign**

Execute `docs/superpowers/plans/2026-08-30-interface-redesign.md` completely. It consumes Plan 2's session/coaching APIs. Required gate: five destinations, detailed source guidance, shared compact panel, accessibility smoke, and full test suite pass.

- [ ] **Plan 4: Synchronization, reliability, and release**

Execute `docs/superpowers/plans/2026-08-30-sync-reliability-and-release.md` completely. It consumes the benchmark, session, coaching, status, and UI boundaries from Plans 1–3. Required gate: last-known-good official sync, public profile validation, offline/status recovery, exact scenario installation, CI/package checks, GitHub version 2.0.0 publication, and preceding-version updater verification.

## Specification coverage map

| Specification sections | Owning plan and tasks |
|---|---|
| 1–3 Purpose, principles, scope | All plan global constraints and phase documentation tasks |
| 4 Information architecture | Interface Tasks 2–7 |
| 5 System architecture | Benchmark Tasks 1–6; Coaching Tasks 1–7; Interface Tasks 1–2; Reliability Tasks 1–5 |
| 6 Benchmark correctness and synchronization | Benchmark Tasks 1–3; Reliability Tasks 1–3 |
| 7 Benchmark health | Coaching Task 4 |
| 8 Recommendation model | Coaching Task 5 |
| 9 Training modes | Coaching Tasks 1–2 and 6–7; Interface Tasks 3–4 |
| 10 Session interface and compact panel | Interface Tasks 1, 4, and 5 |
| 11 Persistence and recovery | Benchmark Task 4; Coaching Task 3 |
| 12 Automatic score importing | Benchmark Tasks 5–6 |
| 13 Missing scenarios | Reliability Task 5 |
| 14 Status and failure handling | Interface Task 2; Reliability Task 4 |
| 15 Privacy and security | Reliability Tasks 1–4 and 7 |
| 16 Testing and acceptance | Every task test cycle; Interface Task 8; Reliability Tasks 6–8 |
| 17 Delivery phases | This execution order |
| 18 GitHub release and auto-update | Reliability Tasks 7–8 |
| 19 Success criteria | Four plan phase gates plus Reliability Task 8 |

## Cross-plan type contract

- Plan 1 owns `DefinitionSet`, `BenchmarkResult`, `PlayerProfile`, `ImportBatchResult`, and `ScoreDirectoryWatcher`.
- Plan 2 owns `SessionPlan`, `SessionState`, `SessionCoordinator`, `RecommendationEvidence`, and `CoachingSummary`.
- Plan 3 owns `ServiceStatus`, presentation models, and the five destination widgets.
- Plan 4 extends `ServiceStatus` with `ServiceHealthStore`; it must import, not duplicate, all earlier types.

## Completion gate

The redesign is complete only when all child-plan checkboxes are complete, the complete offscreen test/coverage/compile/UI/package suite passes, GitHub Actions publishes version 2.0.0, `scripts/verify_release.py` validates the public assets, and the updater successfully upgrades the preceding stable installer in an isolated Windows test directory.
