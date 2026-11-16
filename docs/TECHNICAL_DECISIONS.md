# TECHNICAL DECISIONS (ADR Log) — Morph-Traider

This document records the foundational Architecture Decision Records (ADRs) established in Phase 0 and explains why each choice fits Morph-Traider's ranked priorities.

---

## ADR-001: Python Flask Modular Monolith (WSGI) Over FastAPI or Microservices

- **Status**: Accepted (Phase 0)
- **Context**: Morph-Traider must run reliably on ordinary Python-compatible shared hosting (cPanel, Passenger, LiteSpeed Python, standard WSGI). Early generic templates often default to FastAPI (ASGI) or multi-container microservices, which struggle on shared hosts that only support WSGI (`wsgi.py`), restrict long-lived async sockets, and enforce tight per-account process/RAM limits.
- **Decision**: Build the backend as a **Python 3.11+ Modular Flask Monolith** using Flask Blueprints (`app/blueprints/`), framework-agnostic domain modules (`app/modules/`), Flask-SQLAlchemy, Flask-Migrate, and Pydantic for strict DTO/schema validation. Expose a standard `wsgi.py` entrypoint compatible with Passenger, Gunicorn, and uWSGI.
- **Consequences**:
  - **Pros**: Universal shared-hosting WSGI compatibility; minimal RAM overhead; single deployable artifact; clean internal boundaries without network serialization overhead.
  - **Cons**: Requires discipline to prevent cross-module coupling (enforced by repository/service layer boundaries).

---

## ADR-002: Static-Built TypeScript + React + Vite Frontend Served by Flask

- **Status**: Accepted (Phase 0)
- **Context**: The product requires a rich, responsive institutional trading UI (`SOLID-GLASS`), while shared hosting typically should not—or cannot—run a permanent Node.js SSR server alongside Python WSGI.
- **Decision**: Develop the dashboard in `frontend/` using **TypeScript, React, Vite, Tailwind CSS, and Recharts**. Compile production builds into static assets (`app/static/spa/`) served directly by Flask (or the host's static web server) alongside `/api/v1/*` JSON endpoints. Use visibility-aware REST polling as the baseline transport, behind a transport abstraction allowing optional WebSockets on a VPS.
- **Consequences**:
  - **Pros**: Node.js is strictly a build-time dependency; zero runtime Node memory usage in production; full TypeScript type safety and component modularity.
  - **Cons**: Frontend builds must be compiled locally or in CI before uploading/deploying to shared hosting.

---

## ADR-003: Cron-Triggered Signed HTTP Task Endpoint + SQL Lease Locks

- **Status**: Accepted (Phase 0)
- **Context**: Autonomous signal evaluation, market data polling, and paper position monitoring require periodic execution, yet shared hosting kills background threads, recycles idle WSGI workers, and lacks Redis/Celery.
- **Decision**:
  1. Expose an HMAC/token-protected endpoint `POST /api/v1/tasks/tick`.
  2. Trigger it via standard shared-hosting cron (e.g., every 1 minute).
  3. Synchronize concurrency using an SQL `task_locks` table with expiring leases (`locked_until`) and idempotency keys, plus missed-interval catch-up logic.
  4. Keep `TaskOrchestratorService` transport-agnostic so an optional `APScheduler` runner can call the exact same service method if later deployed to a VPS.
- **Consequences**:
  - **Pros**: 100% compatible with shared hosting; survives worker restarts and crashes automatically; zero Redis/Celery requirement.
  - **Cons**: Minimum scheduling granularity on shared hosting defaults to cron's 1-minute cadence (mitigated by webhook push ingestion for TradingView/Telegram signals).

---

## ADR-004: SQLite (WAL Mode) Default with Seamless PostgreSQL Portability

- **Status**: Accepted (Phase 0)
- **Context**: Many shared-hosting plans provide local filesystem storage with SQLite out of the box, while higher tiers or VPS upgrades offer PostgreSQL. Financial state (paper balances, positions, audit logs) requires ACID transactions and exact decimal precision.
- **Decision**: Use **Flask-SQLAlchemy + Flask-Migrate** targeting **SQLite (`journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`, `foreign_keys=ON`)** by default for local development and lightweight shared hosting, while avoiding SQLite-only SQL syntax so `DATABASE_URL=postgresql+psycopg://...` works seamlessly when available. Store monetary figures as exact fixed-precision/string-backed `Decimal` columns—never binary `float`.
- **Consequences**:
  - **Pros**: Zero external DB setup required to start; safe concurrent reads during WSGI polling + cron ticks; smooth migration path to PostgreSQL.
  - **Cons**: Write transactions must be kept short and atomic to avoid SQLite write-lock contention.

---

## ADR-005: Provider-Independent AI Engine Subordinate to Deterministic Risk Controls

- **Status**: Accepted (Phase 0)
- **Context**: External AI APIs add valuable contextual reasoning (spotting contradictory indicators or overextended market regimes) but suffer from variable latency, rate quotas, outages, and non-determinism. Furthermore, shared hosts cannot run local LLMs.
- **Decision**:
  1. Define a provider-independent `AIValidatorProviderProtocol` using outbound HTTPS APIs (`httpx`) and Pydantic response schemas (`APPROVE` | `REJECT` | `WAIT`).
  2. Run cheap deterministic pre-checks **before** calling AI to save API costs.
  3. Place the **Deterministic Risk Management Module downstream of AI** as the unconditional final authority.
  4. Treat any AI error, timeout, or invalid payload as a fail-safe non-execution state (`WAIT`).
- **Consequences**:
  - **Pros**: Zero vendor lock-in; zero GPU/RAM burden on shared hosting; impossible for an AI hallucination or outage to submit an unsafe trade.
  - **Cons**: Adds outbound HTTP latency (bounded by strict timeouts) to the signal evaluation pipeline.

---

## ADR-006: Strict Paper-Trading Isolation, Multi-Gate Live Lock & Rial/Toman Unit Safety

- **Status**: Accepted (Phase 0)
- **Context**: Premature live order routing or Rial (`RLS`) vs. Toman (`IRT`) 10x unit confusion poses severe financial risk on Nobitex.
- **Decision**:
  1. Hardcode `TRADING_MODE="paper"` as the default and enforce startup/runtime assertions blocking any non-paper mode throughout Phases 0–8.
  2. Simulate fills locally inside `PaperTradingBroker` using live public Nobitex orderbook snapshots, realistic spread/slippage, and Nobitex spot fee schedules.
  3. Permanently exclude withdrawal endpoints/scopes.
  4. Require explicit `CurrencyUnit` (`RLS`, `IRT`, `USDT`) tagging on every price/amount value object at the Nobitex adapter boundary.
- **Consequences**:
  - **Pros**: Eliminates accidental capital loss during development and validation; catches precision and Rial/Toman bugs safely in simulation.
  - **Cons**: Requires maintaining realistic fee and slippage models in `paper_trading`.

---

## ADR-007: `SOLID-GLASS` Brand & UI Design System (`#FFFFFF` / `#0A0A0B` / `#FF5500`)

- **Status**: Accepted (Phase 0)
- **Context**: Generic admin templates undermine operator situational awareness in trading terminals, while all-glass ("glassmorphism everywhere") interfaces harm text contrast and client rendering performance.
- **Decision**: Establish the bespoke **Morph-Traider `SOLID-GLASS`** design system:
  - Palette anchored on **Pure White (`#FFFFFF`)**, **Deep Black (`#0A0A0B`)**, and **Vivid Orange (`#FF5500`)** accents.
  - **Solid opaque surfaces** for all dense financial tables, charts, risk gauges, and AI reasoning text.
  - **Controlled translucent glass layers** reserved selectively for navigation chrome, floating filter bars, and inspector drawers.
  - Mandatory `tabular-nums` monospace typography for numerical alignment.
- **Consequences**:
  - **Pros**: Distinctive institutional identity, high WCAG contrast readability, fast browser compositing on desktop and mobile.
  - **Cons**: Requires building a disciplined custom token and component kit in Phase 2 before assembling dashboard screens.
