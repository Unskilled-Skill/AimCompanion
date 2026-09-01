# Task 3 report: official profile compatibility adapter

## Result

`core.analyzer.build_profile()` now loads the active reviewed definition set,
calculates one `BenchmarkResult`, and adapts that immutable result into the
existing widget-facing `PlayerProfile` shape.  The adapter does not invoke the
legacy arithmetic `recalculate()` path for an official profile.

## TDD evidence

### RED

Command:

```powershell
python -m pytest tests/test_analyzer_official_profile.py -v
```

Initial output after the all-nine and incomplete integration tests were added:

```text
collected 3 items
FAILED test_build_profile_exposes_official_harmonic_energy
  assert 11.111111111111112 == 174.19354838709677 +/- 1.7e-04
FAILED test_build_profile_is_unranked_until_all_nine_subcategories_are_measured
  assert 0.0 is None
FAILED test_build_profile_preserves_benchmark_attempt_best_and_latest_values
  assert 1 == 2
3 failed in 0.21s
```

The hand-derived all-nine oracle is `5400 / 31`: the selected S5 subcategory
energies are `(100, 200, 300, 400, 100, 200, 300, 400, 100)`, whose harmonic
mean is `9 / (3/100 + 2/200 + 2/300 + 2/400)`.  This differs from the old
arithmetic path.

Self-review added one further test before its corresponding adjustment:

```powershell
python -m pytest tests/test_analyzer_official_profile.py::test_profile_from_result_exposes_selected_scenario_as_one_attempt -v
```

```text
FAILED test_profile_from_result_exposes_selected_scenario_as_one_attempt
  assert 0 == 1
1 failed in 0.13s
```

### GREEN

Profile integration test command:

```powershell
python -m pytest tests/test_analyzer_official_profile.py -v
```

```text
4 passed in 0.15s
```

Required compatibility command:

```powershell
python -m pytest tests/test_analyzer_official_profile.py tests/test_recommender.py tests/test_progress_logic.py tests/test_tool_logic.py -v
```

```text
57 passed, 31 subtests passed in 2.59s
```

Full-suite command:

```powershell
python -m pytest -v
```

```text
127 passed, 31 subtests passed in 3.64s
```

## Implementation and compatibility decisions

- Added `models/profile.py` with `PlayerProfile.from_result(result)` and
  `profile_from_benchmark_result(...)`.  It preserves category,
  subcategory, benchmark, overall-energy, tier, and weakest-subcategory view
  contracts; it exposes `definition_version` and `calculation_method`.
- `build_profile()` obtains the active `DefinitionSet`, calls
  `BenchmarkCalculator.calculate()` exactly once, and provides real database
  history to the adapter so benchmark `attempts`, `best_score`, and
  `latest_score` remain accurate.
- Official incompleteness remains `overall_energy=None`; the presentation
  profile maps the absent official tier to `Unranked`.  Measured-only weakest
  subcategories are determined by the official subcategory energy, so a stale
  history value cannot make a missing official result look measured.
- Moved `PlayerProfile` out of `models/score.py`, retaining its old import
  location as a compatibility re-export.  Its arithmetic `recalculate()` is
  retained only for manually constructed non-official profiles and is not
  invoked by the analyzer adapter.
- Replaced legacy interpolation helpers in `models/benchmark.py` with thin
  wrappers around the active definition set and reviewed `score_to_energy`.
  The reverse compatibility helper uses binary search over that reviewed
  evaluator instead of carrying a second interpolation formula.  Tier colors
  remain presentation metadata for existing widgets.
- Updated the trend fixture to use an official S5 benchmark, because unknown
  synthetic names are intentionally no longer assigned arbitrary energy by a
  compatibility helper.

## Self-review

Reviewed the staged behavior and all changed source/test files, including
`git diff --check`.  No whitespace errors were reported.  The adapter uses the
calculator result for official state, maintains nine view-model subcategories,
and the tests cover all-nine harmonic energy, incomplete/unranked state,
weakest measured ordering, history fields, and direct `from_result()` use.

## Concerns

Category energy is a harmonic display aggregate of its measured official
subcategories.  The benchmark standard only defines the nine-subcategory
overall calculation; the category aggregate is compatibility-only and never
influences official overall energy or tier.
