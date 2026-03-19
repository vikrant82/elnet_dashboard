# Active Tasks

## Current

- No active implementation tasks at the moment.

## Recently Completed

- Modernized dashboard UI to dark-first layout with theme switcher.
- Added live usage dial with periodic refresh.
- Added `/live_status` endpoint for live metrics and health/staleness metadata.
- Added `/live_trend` endpoint and sparkline visualization.
- Added chart mode toggle (`₹`, `W`, `Both`) with default `W`.
- Persisted chart controls/mode in localStorage.
- Reworked layout to keep month usage and recharge cards compact below primary cards.

## Follow-up Ideas (optional)

- Make rupee-to-watts tariff configurable from backend config/env (currently fixed client-side constant).
- Add a quick dashboard QA checklist to README for visual regression checks.
