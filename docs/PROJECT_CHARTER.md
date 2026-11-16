# PROJECT CHARTER — Morph-Traider

## 1. Executive Summary & Mission

**Morph-Traider** is a modular, autonomous, AI-assisted cryptocurrency trading system built for the **Nobitex** spot exchange (`https://apidocs.nobitex.ir/`).

Its primary mission is to evaluate multi-source trading signals through a transparent, deterministic technical and risk pipeline augmented by provider-independent AI reasoning—executing **exclusively in simulated paper-trading mode** during initial deployment while maintaining clean adapter boundaries for future human-authorized Nobitex spot execution.

Critically, Morph-Traider is engineered from the ground up to run reliably on **ordinary Python-compatible shared hosting** (WSGI, restricted RAM/CPU, SQLite/PostgreSQL, cron-based automation, zero mandatory daemons) paired with an institutional-grade **Solid-Glass** React/TypeScript trading dashboard compiled into static assets.

---

## 2. Ranked Architectural Priorities

Every technical trade-off in Morph-Traider must obey this strict priority order:

1. **Shared-Hosting Compatibility** — Deployable via standard WSGI (`wsgi.py`) on constrained Python shared hosts with zero root access, zero Docker, zero Redis/Celery requirement, and zero permanently running background worker dependencies.
2. **Financial Safety** — Paper trading only by default; zero withdrawal capabilities; zero hardcoded secrets; deterministic risk controls holding absolute veto power over AI and signal sources.
3. **Reliability** — Safe failure modes when external APIs (Nobitex, AI providers, webhooks) degrade or time out; atomic database state transitions.
4. **Modular Flask Architecture** — Clean separation between HTTP blueprints, domain modules, service interfaces, repositories, and persistence models.
5. **Persistent State & Recoverability** — Zero reliance on ephemeral in-memory worker state; idempotent cron tasks with database lease locks and missed-execution recovery; persistent repository memory for AI coding sessions.
6. **AI Provider Independence** — Pluggable AI adapter contract supporting external LLM APIs without vendor lock-in or local GPU/LLM hosting requirements.
7. **TypeScript Frontend Quality** — Premium, responsive, high-contrast **Solid-Glass** (`#FFFFFF` / `#0A0A0B` / `#FF5500`) institutional trading interface built with React, TypeScript, Vite, Tailwind CSS, and Recharts.
8. **Maintainability** — Small, independently testable modules, strict typing (Python type hints + Pydantic + TypeScript strict mode), and comprehensive ADRs.
9. **Scalability** — Clean zero-rewrite upgrade path from shared hosting (SQLite + cron + REST polling) to VPS hosting (PostgreSQL + Gunicorn + optional APScheduler/WebSocket).
10. **Performance** — Lightweight memory footprint, efficient SQLite WAL indexing, bounded HTTP timeouts, and selective glass rendering in the UI.

---

## 3. Mandatory Functional Scope

1. **Source-Independent Signal Ingestion**: Normalize signals originating from Telegram channels/bots, TradingView Webhooks, and built-in deterministic internal strategies into a canonical `NormalizedSignal` schema.
2. **Market Data & Technical Analysis**: Ingest public Nobitex market data (orderbooks, tickers/stats, candles) with strict Rial (`RLS`) / Toman (`IRT`) and USDT precision handling, computing deterministic technical indicators.
3. **AI-Assisted Signal Validation**: Evaluate signal thesis, technical confluence, contradictory indicators, and market regime through a provider-independent AI interface returning structured `APPROVE`, `REJECT`, or `WAIT` assessments.
4. **Deterministic Decision & Risk Engine**: Enforce position sizing, max drawdown, per-trade risk caps, symbol exposure limits, cooldowns, stale-price checks, and kill-switches. **Deterministic risk controls always override AI recommendations.**
5. **Paper Trading Broker & Portfolio Ledger**: Simulate realistic spot order fills (incorporating Nobitex bid/ask spread, slippage estimates, maker/taker fee tiers, and minimum order sizes) with double-entry balance and position tracking.
6. **Future-Ready Nobitex Spot Adapter**: Architect full interfaces for Nobitex authentication, account balances, spot order placement, status polling, and cancellation—kept strictly disabled behind multi-gate configuration locks until explicitly authorized after Paper Trading verification.
7. **Solid-Glass Institutional Dashboard**: Provide real-time visibility (via configurable REST polling) into portfolio equity, capital allocation, active paper positions, incoming signals, AI reasoning logs, trade history, risk telemetry, Nobitex connectivity, and task health.

---

## 4. Explicit Non-Goals & Prohibitions

- **No Microservices**: Morph-Traider is a single modular Flask monolith serving prebuilt static frontend assets.
- **No Mandatory Infrastructure Bloat**: Redis, Celery, Kafka, RabbitMQ, Docker, Kubernetes, and persistent Node.js runtime servers are strictly forbidden as baseline requirements.
- **No Local LLMs**: Never require local model weights (`llama.cpp`, `ollama`, PyTorch/CUDA) on the application host.
- **No Unsupervised AI Trading**: AI never calls order execution methods, never alters risk limits, and never triggers live-mode transitions.
- **No Withdrawal Functionality**: Deposit-address generation or fund withdrawals (`برداشت ریالی` / crypto withdrawals) are permanently out of scope.
- **No Unverified Exchange Endpoints**: Never fabricate Nobitex endpoints, parameters, or rate limits; every endpoint must trace to `https://apidocs.nobitex.ir/`.

---

## 5. Financial Safety & Authorization Governance

Transitioning beyond `TRADING_MODE=paper` is prohibited during Phases 0–8. Even when the future live spot adapter interface is implemented for completeness, activating live spot execution in a future release will require **all** of the following simultaneous human-controlled gates:

1. Explicit environment variable `TRADING_MODE=live_spot` (default hardcoded to `paper`).
2. Secondary cryptographic/boolean confirmation flag `ALLOW_LIVE_NOBITEX_ORDERS=true` (default `false`).
3. Presence of trade-only (non-withdrawal) Nobitex API credentials loaded solely from host environment variables.
4. Explicit operator unlock action recorded in the persistent audit log with Risk Kill-Switch disengaged.
