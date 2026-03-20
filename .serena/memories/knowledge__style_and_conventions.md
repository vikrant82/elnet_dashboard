# Style and Conventions

## Python backend conventions

- Module-level logger pattern: `logger = logging.getLogger(__name__)`
- Favor short-lived SQLite connections per operation with guarded `try/except/finally`
- Prefer explicit JSON contracts in dashboard endpoints for frontend live widgets
- Keep time handling timezone-aware at boundaries; store/query DB timestamps as UTC-compatible values
- Reuse small query/serialization helpers in dashboard views to avoid endpoint SQL duplication

## Frontend/dashboard conventions

- Single-template dashboard architecture with inline CSS/JS (no frontend build system)
- Use CSS custom properties for theming (`--bg`, `--text-primary`, etc.)
- Theme behavior is dark-first with optional light toggle, persisted in localStorage
- Use Plotly with `Plotly.react` for efficient rerenders
- Debounce graph updates tied to controls
- Keep UX state persistence lightweight (`localStorage`) for interval/group/chart mode
- For comparison overlays, keep timestamp alignment identical to base series buckets
- For sparse comparison data, return `null` values and render with `connectgaps: false`

## Practical guidance

- For new live widgets, prefer adding narrowly scoped JSON endpoints (`/live_*`) and polling from the template
- Keep visual density balanced: key status cards near top, secondary cards compact
- For chart comparison features, expose clear metadata (e.g., `sample_count`, requested vs available days)
- Avoid TODO/FIXME comments in source; track future work in `tasks__todo`