# Aim Companion 1.8.2

This release keeps authored training plans optional at startup.

## What changed

- Today now always opens on Focused block with Adaptive weakness selected.
- hnA, full routines, and deathmatch plans activate only after the user chooses
  them for the current session.
- Cleared stale preferred-routine state when Today initializes.
- Isolated automated UI tests from the real saved application configuration so
  development checks cannot change the installed app's selected training mode.

Existing scores, settings, training history, routines, and automatic update
preferences are preserved during installation.
