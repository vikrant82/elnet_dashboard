# Task Completion Guidance

Because the repository currently has no discovered automated test/lint/format configuration, use a lightweight completion checklist:

1. Review changed files for consistency with existing Flask/SQLite patterns.
2. If Python files changed, run a local smoke check appropriate to the change, typically by starting the Flask app:
   - `export FLASK_APP=power_usage_tracker/app/__init__.py`
   - `flask run`
3. If dashboard/template behavior changed, load the dashboard in a browser and verify key UI states manually.
4. If scheduler/API/storage behavior changed, verify logs and database effects with concise manual checks.
5. If Docker-related files changed, validate with `docker-compose up --build` when practical.

## Known Gap

- Adding a real automated test suite and formatting/linting workflow would materially improve future task completion confidence.