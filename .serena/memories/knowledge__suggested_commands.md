# Suggested Commands

## Setup

- Create virtual environment (example): `python3 -m venv .venv && source .venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`
- Create env file: `cp .env.example .env`

## Run Locally

- Recommended Flask app env: `export FLASK_APP=power_usage_tracker/app/__init__.py`
- Start dev server: `flask run`
- Run on all interfaces: `flask run --host=0.0.0.0`

## Docker

- Build and run with compose: `docker-compose up --build`
- Container maps host port `8800` to container port `5000`

## Useful Development Commands (Linux)

- List files: `ls`
- Show current directory: `pwd`
- Search text: `grep -R "pattern" .`
- Find files: `find . -name "*.py"`
- Git status: `git status`
- Git diff: `git diff`

## Validation Status

- No dedicated test suite was found.
- No formatter/linter configuration files were found (`pytest`, `ruff`, `flake8`, `mypy`, `black`, etc.).
- For now, validation is manual/smoke-based unless tooling is added later.