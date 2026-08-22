# Aim Companion 1.0.3

This release rebuilds Progress around useful benchmark states instead of empty charts.

## What changed

- Replaced the oversized controls and panels with a compact benchmark workspace.
- Added full-width summaries for attempts, best, latest, change, and the next official Voltaic target.
- Added a clear baseline action when a benchmark has no recorded attempts.
- Replaced single-point timelines with a useful baseline-to-next-rank progress view.
- Only shows score and energy charts when enough data exists to form a real trend.
- Fixed chart date bounds, title clipping, category colors, and sparse-data whitespace.
- Added a compact recent-attempt history and stable recent-average comparison.

Existing scores, settings, and training history are preserved during installation.
This build is not Authenticode-signed; use the matching `.sha256` asset to verify
installer integrity.
