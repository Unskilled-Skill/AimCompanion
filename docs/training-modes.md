# Training modes and session behavior

Aim Companion uses one durable session model for Warm-up, Step-by-Step
Training, and Full Routine. The normal Session screen and compact panel read the
same state; neither can advance independently.

## Warm-up

Warm-up prepares for either a selected game or a selected routine. The app
remembers the most recent context and uses it on the next visit while keeping
the selector available. A routine warm-up covers multiple represented skills
when the bundled source/catalog permits. Warm-up activity may appear in local
history, but it does not change Full Routine progress or benchmark-freshness
counters.

## Step-by-Step Training

Step-by-Step is the flexible option when available time is uncertain. It shows
one focused 3–5 minute scenario block, saves each confirmed run, and allows the
session to stop after any block.

A missing or stale benchmark check takes precedence. Otherwise, the engine
rotates through the three highest-priority weaknesses with a ten-slot 50/30/20
schedule. It avoids repeating the same scenario or subcategory when another
suitable candidate exists. Previewing a recommendation does not consume its
rotation slot; the cursor advances only after acceptance.

Each recommendation records the rule, a human-readable evidence summary,
definition version, confidence, trend window, and benchmark age when relevant.
Manual game-observation records are retained only for historical compatibility
and are not recommendation inputs. Fatigue coaching is off until the user opts
in.

## Full Routine

Full Routine retains the source identity, exact authored scenario order,
prescribed run counts, and supplied guide fields. A reordered or interrupted
session is not presented as a newly shortened official routine.

For an official routine:

```text
A -> B -> C -> D -> E
```

If the previous session completed A and B, the next execution is:

```text
C -> D -> E -> A -> B -> stop
```

The session stops before C would repeat. That is one complete circular pass,
with previously unfinished material first. After the wrapped pass is complete,
the following session resets to A.

If C was stopped before all prescribed runs were confirmed, C remains the
first unfinished scenario and restarts with its full prescribed run count. A
partial run count never reduces the source requirement.

## Confirmation, stopping, and recovery

Kovaak's result detection and the manual confirmation action use the same state
transition. Results for another scenario are ignored, and a durable result
identity prevents one detected result from being counted twice after restart.
The run tracker begins before the Steam scenario link opens.

The database is updated after every confirmed run and pause, resume, stop, or
completion transition. If the app closes while a session is running, the next
process recovers it as paused. At most the current unconfirmed run can be lost.

## Benchmark freshness

Freshness is independent for each benchmark subcategory. A missing measurement
is immediately due. After a valid check, blocks 0–11 remain current and the
12th relevant completed non-warm-up block makes that subcategory stale. One
block increments each represented subcategory once, regardless of its run
count. Completing a benchmark resets only that exact subcategory.
