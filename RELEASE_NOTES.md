# Aim Companion 1.7.0

This release adds consistent visible descriptions throughout training.

## What changed

- Every recommended Scenario Library card now shows what the scenario trains
  or the authored execution instruction when one is available.
- Every supplied routine now has a visible purpose, including the 44 routines
  whose source data did not include description text.
- Generated full routines show the overall routine purpose beneath the source.
- Every main and warm-up exercise in a generated routine shows its individual
  purpose or authored execution focus.
- Description generation is centralized so the library, routine selector, and
  generated sessions use the same wording and source priority.
- Fixed full-routine export to use Kovaak's current `scenarioName` and
  `playCount` playlist fields.

Existing scores, settings, training history, routines, and automatic update
preferences are preserved during installation.
