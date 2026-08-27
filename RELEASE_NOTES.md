# Aim Companion 1.3.0

This release adds a recommended scenario pack and faster scenario launching.

## What changed

- Added a Download all missing action for Aim Companion's 242 curated scenarios.
- The action creates a Kovaak's playlist containing only scenarios that are not
  currently available locally, then opens Kovaak's for automatic acquisition.
- Added Play or Download & play directly to every Scenario Library card.
- Installed scenario counts refresh when returning to Aim Companion.
- Scenario detection now compares normalized names across local and Steam
  Workshop storage.
- Choosing Different pick no longer launches Kovaak's before the new scenario
  is confirmed.

Kovaak's does not provide a supported silent API for downloading its entire
50,000+ item Workshop. The scenario pack therefore stays focused on the vetted
set used by Aim Companion's recommendations and routines.

Existing scores, settings, routines, training history, and update preferences
are preserved during installation. This build is not Authenticode-signed; use
the matching `.sha256` asset to verify installer integrity.
