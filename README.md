# Morph-Traider

**Modular, Autonomous AI-Powered Nobitex Trading System (Paper-Trading First, Shared-Hosting Native)**

Morph-Traider is a production-oriented, modular trading platform designed for the **Nobitex** cryptocurrency exchange (`https://apidocs.nobitex.ir/`). It combines multi-source signal ingestion, deterministic technical analysis, provider-independent AI validation, strict deterministic risk controls, and a simulated paper-trading ledger behind a **Solid-Glass** institutional trading terminal UI.

---

## Financial Safety Notice

- **PAPER TRADING ONLY**: Morph-Traider runs exclusively in simulated paper-trading mode (`TRADING_MODE=paper`).
- **No Live Orders**: Live order execution is disabled at the configuration, service, and adapter levels until explicitly authorized in a future post-audit phase.
- **No Withdrawals**: Withdrawal APIs and withdrawal key scopes are permanently excluded by design.
- **Deterministic Risk Authority**: AI reasoning (`APPROVE` | `REJECT` | `WAIT`) is strictly advisory and can never bypass deterministic risk limits or directly submit orders.

---

## Technology Stack

- **Backend**: Python 3.11+, Flask Modular Monolith (WSGI), Flask-SQLAlchemy, Flask-Migrate, Pydantic, HTTPX, SQLite (WAL) / PostgreSQL.
- **Automation**: Shared-hosting cron + HMAC-protected idempotent task runner with SQL lease locking (optional APScheduler upgrade on VPS).
- **Frontend**: TypeScript, React, Vite, Tailwind CSS, Recharts — compiled into static assets served directly by Flask in production (zero runtime Node.js requirement).
- **Design Language**: **SOLID-GLASS** — Pure White (`#FFFFFF`), Deep Black (`#0A0A0B`), and Vivid Orange (`#FF5500`) institutional trading interface.

---

## Repository Documentation & Memory Index

Start every development session by reading the canonical project governance and state files:

1. [`AGENTS.md`](AGENTS.md) — Mandatory agent operating protocol, 30% context budget rule, and financial safety invariants.
2. [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md) — Vision, scope boundaries, safety governance, and ranked architectural priorities.
3. [`docs/SYSTEM_ARCHITECTURE.md`](docs/SYSTEM_ARCHITECTURE.md) — Modular Flask blueprint/module layout, signal-to-trade pipeline, shared-hosting execution model, Nobitex capability matrix, and `SOLID-GLASS` frontend design specification.
4. [`docs/TECHNICAL_DECISIONS.md`](docs/TECHNICAL_DECISIONS.md) — Architecture Decision Records (ADRs) explaining stack, hosting, database, AI, and safety choices.
5. [`docs/ROADMAP.md`](docs/ROADMAP.md) — Incremental phase-by-phase delivery roadmap.
6. [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md) — Verified snapshot of current implementation state.
7. [`docs/NEXT_TASK.md`](docs/NEXT_TASK.md) — Single next actionable, independently testable implementation task.
