# NEXT TASK — Task 1.1: Bootstrap Flask WSGI Application Factory, Safety Config & Health Endpoint

## 1. Objective

Create the minimal, production-clean **Python + Flask WSGI backend foundation** (`Phase 1 / Task 1.1`) configured for shared hosting, SQLite WAL persistence, and hard-locked **Paper Trading Only** enforcement—verified with an automated `pytest` test suite.

Do **not** implement trading logic, Nobitex HTTP clients, AI adapters, or frontend code in this task.

---

## 2. Pre-Flight Recovery Checklist (Mandatory Before Coding)

1. Read `AGENTS.md`, `docs/CURRENT_STATE.md`, `docs/NEXT_TASK.md`, and `docs/ROADMAP.md`.
2. Check Git status (`git status`, `git branch`) to see if `github.com/AGlegendery/Morph-traider` has been initialized since Phase 0, and inspect the workspace directory tree.

---

## 3. Scope & Files to Create

1. **`pyproject.toml`**:
   - Target Python `>=3.11`.
   - Core lightweight dependencies suitable for shared hosting: `flask`, `flask-sqlalchemy`, `flask-migrate`, `pydantic`, `pydantic-settings` (or typed `os.environ` + `pydantic`), `python-dotenv`, `httpx`.
   - Dev dependencies: `pytest`.
2. **`.env.example`**:
   - Safe placeholder configuration only (`FLASK_ENV=development`, `TRADING_MODE=paper`, `ALLOW_LIVE_NOBITEX_ORDERS=false`, `DATABASE_URL=sqlite:///instance/morph_traider.db`, placeholder `SECRET_KEY` and `CRON_SECRET_TOKEN`). Zero real secrets.
3. **`app/config.py`**:
   - Typed configuration classes (`Config`, `DevelopmentConfig`, `TestingConfig`, `ProductionConfig`).
   - **Hard Financial Safety Guard**: Validate at startup that `TRADING_MODE == "paper"` and `ALLOW_LIVE_NOBITEX_ORDERS is False`; raise a dedicated `FinancialSafetyLockError` immediately if any configuration attempts to enable live trading in Phase 1.
4. **`app/core/exceptions/__init__.py`**:
   - Base `MorphTraiderError` and `FinancialSafetyLockError`.
5. **`app/extensions.py`**:
   - `db = SQLAlchemy()` and `migrate = Migrate()`, plus SQLite connection event listener enabling `PRAGMA journal_mode=WAL`, `PRAGMA foreign_keys=ON`, and `PRAGMA busy_timeout=5000` when using SQLite.
6. **`app/__init__.py`**:
   - `create_app(config_override=None)` application factory initializing config, safety assertions, extensions, and registering the initial API blueprint.
7. **`app/blueprints/api/__init__.py`**:
   - `GET /api/v1/health` returning structured JSON:
     - `status`: `"ok"`
     - `service`: `"morph-traider"`
     - `trading_mode`: `"paper"`
     - `live_orders_enabled`: `false`
     - `database`: `"ok"` (verified via lightweight `SELECT 1`)
     - `timestamp_utc`: ISO-8601 UTC string
8. **`wsgi.py`**:
   - Standard WSGI entrypoint (`application = create_app()`) compatible with cPanel Passenger, Gunicorn, and uWSGI.
9. **`tests/conftest.py` & `tests/test_app_foundation.py`**:
   - Automated tests covering:
     1. App factory boots cleanly in `TestingConfig` with isolated SQLite DB.
     2. `GET /api/v1/health` returns HTTP `200` with `trading_mode == "paper"` and `live_orders_enabled is False`.
     3. Attempting to boot `create_app` with `TRADING_MODE="live"` or `ALLOW_LIVE_NOBITEX_ORDERS=True` raises `FinancialSafetyLockError` and refuses to start.
     4. `wsgi.py` exposes a valid WSGI callable.

---

## 4. Acceptance Criteria & Completion Steps

1. All tests pass via `uv run pytest`.
2. Zero real credentials, zero heavy dependencies (no Redis/Celery/Docker), and zero empty speculative module folders created.
3. Update `docs/CURRENT_STATE.md`, mark Task 1.1 `[x]` in `docs/ROADMAP.md`, and write **Task 1.2** into `docs/NEXT_TASK.md` before finishing.
