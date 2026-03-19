# Project Overview

- **Name:** Power Usage Tracker
- **Purpose:** Flask web app for ELNET electricity meters that polls provider APIs, stores meter readings in SQLite, renders a dashboard, and sends Telegram alerts/summaries.
- **Primary users/use case:** Home users in Indian gated communities wanting better visibility and alerts than the vendor app provides.

## Core capabilities

- Poll live and home-summary ELNET APIs on a schedule
- Persist readings and recharge events to SQLite
- Detect low balance, DG/EB source changes, stale/anomalous data
- Send Telegram notifications for summaries, low balance, DG transitions, and recharges
- Serve a dashboard with usage metrics, recharge history, and Plotly visualizations

## Dashboard UX updates (Mar 2026)

- Dark-first UI refresh with optional light theme toggle
- New live usage dial (0–3.5 kW) with watts readout
- New `GET /live_status` endpoint for live dial/health data
- New `GET /live_trend` endpoint for short-window present-load sparkline
- Live health/staleness indicators and last successful fetch metadata
- Chart Y-axis mode toggle (`₹`, `W`, `Both`) with default `W`
- Chart preferences persisted in localStorage (interval/group/mode)
- Compact “This Month” and “Recent Recharges” cards to use dashboard space better

## Tech Stack

- Python 3.8+ locally; Docker image uses Python 3.9-slim
- Flask 2.0.1 web app
- APScheduler for background jobs
- SQLite for storage
- Requests for API access
- Plotly (browser-side) for charting
- python-dotenv for environment loading
- pytz for timezone handling
- Docker / Docker Compose for containerized deployment
