# Aim Companion 1.6.0

This release turns Today into a multi-mode training workspace.

## What changed

- Added a persistent segmented mode selector to Today.
- Added Focused block mode for the existing adaptive 3-5 minute workflow.
- Added Full routine mode for session setup, generated routines, and playlists.
- Added Deathmatch mode as a first-class daily training workflow with the full
  eight-match Valorant transfer checklist and coaching.
- Each mode now hides controls belonging to other workflows, reducing page
  density and preventing unrelated actions from competing for attention.
- Full routine mode presents session setup before its generated routine.
- Starting a focused block from Home always selects the matching mode.
- Reused one deathmatch component between Today and Training Guide so progress
  stays consistent across both views and app restarts.

Existing scores, settings, training history, routines, and automatic update
preferences are preserved during installation.
