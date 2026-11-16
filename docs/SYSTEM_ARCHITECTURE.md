# SYSTEM ARCHITECTURE — Morph-Traider

## 1. High-Level Architectural Overview

Morph-Traider is architected as a **Modular Flask Monolith** paired with a **Static-Built TypeScript/React SPA**, engineered specifically for **WSGI Shared Hosting**.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        SHARED HOSTING ENVIRONMENT                            │
│                                                                              │
│  ┌─────────────────────┐         HTTPS / REST Polling         ┌────────────┐ │
│  │ Browser Client      │ ◄──────────────────────────────────► │ WSGI Entry │ │
│  │ Solid-Glass React   │    (Static Assets served by Flask)   │  wsgi.py   │ │
│  └─────────────────────┘                                      └─────┬──────┘ │
│                                                                     │        │
│  ┌─────────────────────┐    Signed HTTP POST (/api/v1/tasks/tick)   ▼        │
│  │ Host Cron Scheduler │ ───────────────────────────────────► ┌────────────┐ │
│  │ (e.g. every 1 min)  │                                      │   Flask    │ │
│  └─────────────────────┘                                      │  Monolith  │ │
│                                                               └─────┬──────┘ │
│  ┌─────────────────────┐    Signed Webhook (/api/v1/signals/...)    │        │
│  │ TradingView / TG    │ ───────────────────────────────────────────┘        │
│  └─────────────────────┘                                                     │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                   PERSISTENT SQL STORAGE (SQLite WAL / PostgreSQL)      │ │
│  │  signals | market_snapshots | ai_assessments | decisions | risk_events  │ │
│  │  paper_wallets | paper_orders | positions | task_locks | audit_logs     │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└───────────────┬──────────────────────────────────────────┬───────────────────┘
                │ HTTPS (Outbound Only)                    │ HTTPS (Outbound Only)
                ▼                                          ▼
   ┌──────────────────────────┐               ┌──────────────────────────┐
   │ Official Nobitex REST API│               │ External AI Provider API │
   │  (Public Data Only in    │               │ (OpenAI-compatible /     │
   │   Paper Trading Mode)    │               │  Gemini / Anthropic etc.)│
   └──────────────────────────┘               └──────────────────────────┘
```

---

## 2. Modular Backend Directory Blueprint (`app/`)

Business logic lives inside `app/modules/` and `app/services/`, strictly decoupled from Flask `request`/`Response` objects in `app/blueprints/`. Empty placeholder packages will **not** be created prematurely; directories are introduced incrementally per `docs/ROADMAP.md`.

```text
Morph-Traider/
├── wsgi.py                        # Standard WSGI entrypoint for Passenger/Gunicorn/uWSGI
├── pyproject.toml                 # Python 3.11+ dependencies & pytest/ruff config
├── .env.example                   # Safe template (TRADING_MODE=paper, no real keys)
├── app/
│   ├── __init__.py                # create_app() Flask application factory
│   ├── config.py                  # Pydantic/typed config + hard Paper-Trading safety guards
│   ├── extensions.py              # db (SQLAlchemy), migrate (Flask-Migrate)
│   ├── core/
│   │   ├── security/              # Auth tokens, webhook HMAC verification, cron signatures
│   │   ├── logging/               # Structured JSON/file logging safe for shared hosts
│   │   ├── exceptions/            # Domain, exchange, risk, and safety-lock exceptions
│   │   └── utilities/             # UTC clock, Decimal/Rial-Toman math, idempotency helpers
│   ├── blueprints/                # Thin HTTP adapters (REST + SPA static fallback)
│   │   ├── auth/                  # Operator session / API token authentication
│   │   ├── dashboard/             # Aggregated KPIs, system health, static SPA serving
│   │   ├── signals/               # Webhook receivers (TradingView, Telegram) & signal feed
│   │   ├── trading/               # Orders, decisions, risk telemetry, kill-switch API
│   │   ├── portfolio/             # Paper balances, equity curve, capital allocation
│   │   ├── settings/              # Non-secret strategy/risk parameters & adapter status
│   │   └── api/                   # Versioned `/api/v1` router & `/api/v1/tasks/tick` cron hook
│   ├── modules/                   # Pure domain modules (framework-independent contracts)
│   │   ├── exchanges/
│   │   │   └── nobitex/           # Isolated Nobitex client, DTOs, rate limiter, unit converter
│   │   ├── market_data/           # Ticker/orderbook/OHLCV normalization & caching in DB
│   │   ├── signal_engine/         # Source-independent signal parsers & deduplication
│   │   ├── technical_analysis/    # Deterministic indicators (EMA, RSI, ATR, structure, volume)
│   │   ├── ai_engine/             # Provider-independent AI validator & structured schemas
│   │   ├── decision_engine/       # Synthesizes TA + Market Context + AI advisory verdict
│   │   ├── risk_management/       # Final deterministic gatekeeper (sizing, drawdown, caps)
│   │   ├── paper_trading/         # Simulated Nobitex order matching, spread/fee/slippage ledger
│   │   ├── execution/             # Execution router (hard-locked to PaperBroker in Phase 0–8)
│   │   ├── position_management/   # Open position tracking, TP/SL monitoring, PnL accounting
│   │   └── reporting/             # Performance metrics, audit trail, drawdown & win-rate stats
│   ├── models/                    # SQLAlchemy ORM models
│   ├── repositories/              # Data-access layer encapsulating SQL queries & transactions
│   ├── services/                  # Application orchestrators wiring repositories + modules
│   ├── tasks/                     # Idempotent cron jobs, SQL lease locking, catch-up runner
│   ├── templates/                 # Fallback/minimal server templates if SPA not yet built
│   └── static/                    # Compiled frontend bundle output (`app/static/spa/`)
├── migrations/                    # Flask-Migrate / Alembic schema revisions
├── frontend/                      # TypeScript + React + Vite + Tailwind CSS source workspace
└── tests/                         # Unit, integration, risk-safety, and recovery test suites
```

---

## 3. Autonomous Signal-to-Execution Pipeline & Safety Authority

Every signal passes through a strict, auditable, linear pipeline persisted at each stage in SQL:

```
[1. Signal Ingestion]  (Telegram | TradingView Webhook | Internal Strategy)
        │  Normalizes symbol, direction (BUY/SELL), entry zone, SL/TP, idempotency_key
        ▼
[2. Market Data Snapshot]  (Nobitex Public API)
        │  Fetches current best bid/ask, spread, 24h volume, recent OHLCV; checks staleness
        ▼
[3. Deterministic Technical Analysis]
        │  Computes trend alignment, RSI/momentum, ATR volatility, support/resistance, R:R ratio
        ▼
[4. Provider-Independent AI Validation]  (Advisory Only)
        │  Inputs: NormalizedSignal + MarketSnapshot + TAReport + Portfolio Exposure Summary
        │  Output Schema (Pydantic):
        │    verdict: "APPROVE" | "REJECT" | "WAIT"
        │    confidence: Decimal (0.00 - 1.00)
        │    contradictions: list[str]
        │    rationale: str
        │  Fail-Safe Rule: Timeout / HTTP 5xx / Quota / Schema Error => verdict="WAIT" (safe halt)
        ▼
[5. Decision Engine]
        │  Combines deterministic TA score + AI verdict.
        │  Only advances candidate order if TA passes threshold AND AI verdict == "APPROVE"
        │  (or explicit operator-configured deterministic fallback policy for WAIT).
        ▼
[6. Deterministic Risk Management Gate]  ◄── FINAL UNCONDITIONAL AUTHORITY
        │  Hard checks (any failure REJECTS the trade regardless of AI confidence):
        │    - Global Kill-Switch == OFF
        │    - TRADING_MODE == "paper" verified
        │    - Max risk per trade (e.g., <= 1.0% of paper equity)
        │    - Max daily drawdown cap not breached
        │    - Max concurrent open positions & max per-asset allocation cap
        │    - Nobitex minimum order notional & tick/lot precision compliance
        │    - Price staleness <= max_quote_age_seconds & spread <= max_spread_bps
        ▼
[7. Execution Router]
        │  Hard-gated to `PaperTradingBroker` (Live Nobitex Spot Broker disabled behind 4 locks)
        ▼
[8. Paper Trading Broker & Position Manager]
           Simulates fill against real Nobitex orderbook top-of-book + slippage + fee tier,
           updates `paper_wallets` & `positions` atomically in a single SQL transaction.
```

---

## 4. Shared-Hosting Execution, Scheduling & Recovery Model

Shared hosting environments (cPanel, DirectAdmin, Passenger WSGI, LiteSpeed Python) routinely **recycle or kill idle Python worker processes**, restrict thread spawning, and prohibit persistent daemons like Celery or Redis. Morph-Traider handles this natively:

### 4.1 Zero Critical In-Memory State
- No open orders, cooldown timers, rate-limit counters, locks, or signal queues live in Python globals.
- Every state transition is committed to SQLite (configured with `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`) or PostgreSQL.

### 4.2 Cron-Triggered Idempotent Task Runner
1. **Trigger**: Standard hosting cron job runs every 1 minute (e.g., `curl -sS -X POST -H "X-Cron-Signature: ..." https://domain.tld/api/v1/tasks/tick`).
2. **Authentication**: Constant-time HMAC/token verification (`CRON_SECRET_TOKEN`) rejects unauthorized callers with HTTP `403`.
3. **Database Lease Locking (`task_locks` table)**:
   - Before executing a job (`poll_market_data`, `evaluate_pending_signals`, `update_paper_positions`), the runner executes an atomic conditional `INSERT`/`UPDATE` acquiring a lease (`locked_until = now_utc + lease_seconds`, `owner_run_id`).
   - If another WSGI worker already holds an unexpired lease, the duplicate cron call exits cleanly in `<10ms` with `{ "status": "skipped_locked" }`.
   - If a previous worker crashed mid-task, its lease expires automatically after `lease_seconds` (e.g., 55s), allowing automatic self-healing recovery on the next tick.
4. **Time-Budgeted Batching & Catch-Up**:
   - Each `/tasks/tick` invocation enforces a strict wall-clock budget (e.g., 20 seconds, well below typical 30–60s WSGI request timeouts).
   - Missed intervals (e.g., host maintenance downtime) are detected via `last_completed_at` in `scheduled_tasks` and reconciled safely by re-syncing latest Nobitex market prices before evaluating any pending SL/TP or signals (preventing stale-price fills).

### 4.3 Optional VPS Upgrade Path (Documented, Never Mandatory)
When migrating from shared hosting to a dedicated VPS later, **zero domain or module code changes are required**:
- Switch `SQLALCHEMY_DATABASE_URI` from SQLite to PostgreSQL.
- Run Gunicorn behind Nginx.
- Optionally enable an in-process or standalone `APScheduler` CLI runner calling the exact same `TaskOrchestratorService.run_tick()` method used by `/api/v1/tasks/tick`.
- Optionally enable WebSocket push notifications alongside the existing REST polling client.

---

## 5. Nobitex Exchange Integration & Capability Verification Matrix

All exchange logic is isolated inside `app/modules/exchanges/nobitex/` behind `ExchangePublicDataProtocol` and `ExchangeSpotTradingProtocol`.

### 5.1 Source of Truth & Currency Safety
- **Official Source**: `https://apidocs.nobitex.ir/`
- **Critical Rial (`RLS`) vs. Toman (`IRT`) Safety Rule**:
  - In Iranian crypto markets and Nobitex API responses, fiat pairs are denominated in **Iranian Rial (`RLS`)** (`1 IRT = 10 RLS`), whereas traders and external signals frequently quote prices in **Toman (`IRT`)** or **Tether (`USDT`)**.
  - Morph-Traider stores all monetary quantities using exact `Decimal` representations paired with an explicit `CurrencyUnit` enum (`RLS`, `IRT`, `USDT`, plus base crypto symbol) and enforces unit normalization at the `nobitex` adapter boundary so a 10x Rial/Toman mismatch can never occur.

### 5.2 Verified vs. To-Be-Verified Capability Matrix

Because `https://apidocs.nobitex.ir/` renders detailed endpoint schemas dynamically via a client-side SPA, Phase 0 strictly separates **verified facts** from **items requiring live verification in Phase 3 before coding endpoint URLs**:

| Capability Area | Status in Phase 0 | Verified Facts (`apidocs.nobitex.ir`) & Design Rules | Verification Required Before Phase 3 / Phase 8 Coding |
| :--- | :--- | :--- | :--- |
| **Official Documentation Portal** | **VERIFIED** | `https://apidocs.nobitex.ir/` is live and organized into: Getting Started (`شروع به کار`), Authentication (`احراز هویت`), API Key (`کلید API`), Market Info (`اطلاعات بازار` — 5 endpoints), Spot Trading (`معاملات اسپات` — 6 endpoints), Deposit Address, Withdrawal, and General Considerations (`ملاحظات عمومی`). | Inspect exact SPA sub-routes during Phase 3 Task 3.1 to lock exact path versions (`v2`/`v3`), query params, and response JSON schemas. |
| **Authentication & API Keys** | **VERIFIED CONCEPT / SCHEMA PENDING** | User panel API key generation and authenticated/signed request flow (`ساخت کلید از پنل کاربری و ارسال اولین درخواست امضاشده`). | Confirm exact header format (`Authorization: Token <key>` vs. HMAC signature headers) and read-only vs. spot-trade key scope flags before Phase 8. **Not needed for Paper Trading public data.** |
| **Public Market Data** | **CATEGORY VERIFIED (5 endpoints)** | Official docs expose 5 public Market Information endpoints (orderbook, market stats/tickers, recent trades, OHLCV/UDF candles, market list/options). | Confirm exact endpoint paths, symbol naming convention (e.g., `BTCIRT` vs `btc-rls`), and candle resolution strings against live public responses in Phase 3. |
| **Spot Order Lifecycle** | **CATEGORY VERIFIED (6 endpoints)** | Official docs expose 6 Spot Trading endpoints covering order placement, order status lookup, order listing, and order status update/cancellation. | Confirm exact payload fields, `clientOrderId` idempotency support, and maker/taker fee fields before Phase 8 interface binding. |
| **Account / Wallet Balances** | **ADAPTER PLANNED** | Required for future live balance reconciliation; simulated locally in `paper_wallets` during Phases 1–8. | Confirm exact wallet list endpoint path and locked-balance vs. available-balance fields in official docs. |
| **Rate Limits & Precision** | **ASSUMPTION FLAGGED** | Nobitex enforces per-endpoint rate limits, tick sizes, and minimum notional order sizes (`ملاحظات عمومی`). | Extract exact rate-limit quotas (req/min) and per-market precision/minimum notional tables from official docs; implement conservative configurable token-bucket defaults in Phase 3. |
| **Official Sandbox / Testnet** | **UNVERIFIED (ASSUME NONE)** | No public testnet URL was advertised on the `apidocs.nobitex.ir` landing overview. | Morph-Traider's internal `PaperTradingBroker` provides 100% local execution simulation using live public market data, removing any reliance on an external exchange sandbox. |
| **Withdrawals (`برداشت`)** | **PERMANENTLY EXCLUDED** | Although Nobitex documents Rial/crypto withdrawal endpoints (`برداشت ریالی`), Morph-Traider **forbids** implementing any withdrawal client method. | None — permanently prohibited by `PROJECT_CHARTER.md`. |

---

## 6. AI Engine Architecture (Provider-Independent)

Located in `app/modules/ai_engine/`:

1. **Core Contract (`AIValidatorProviderProtocol`)**:
   - `evaluate_signal(context: AISignalEvaluationRequest) -> AISignalAssessment`
2. **Supported Adapter Strategy**:
   - Outbound HTTPS REST calls via `httpx` with strict connect/read timeouts (e.g., `connect=3.0s`, `read=12.0s`).
   - Pluggable adapters: `OpenAICompatibleAdapter` (covers OpenAI, OpenRouter, DeepSeek, Groq, vLLM endpoints), `GeminiAdapter`, `AnthropicAdapter`, and `DeterministicMockAIAdapter` (for offline unit testing and zero-cost dry runs).
3. **Structured Output Enforcement**:
   - Responses are validated strictly through Pydantic (`verdict: Literal["APPROVE", "REJECT", "WAIT"]`, `confidence_score`, `risk_flags`, `contradictory_evidence`, `market_regime_summary`, `reasoning_summary`, `latency_ms`, `token_usage`).
4. **Cost, Quota & Failure Resilience**:
   - Signals failing fast deterministic pre-filters (invalid symbol, duplicate signal, wide spread, Risk Kill-Switch active, weak TA baseline) are rejected **before** calling the AI API to conserve quota and latency.
   - Circuit-breaker counters stored in SQL (`provider_health`) temporarily cool down failing providers and safely default assessments to `WAIT` with explicit audit reason `AI_UNAVAILABLE_SAFE_HALT`.

---

## 7. Frontend Architecture & `SOLID-GLASS` Design System Specification

### 7.1 Technical & Deployment Model
- **Stack**: TypeScript (strict), React 18+, Vite, Tailwind CSS, Recharts, Lucide icons (clean geometric stroke icons).
- **Build & Shared-Hosting Delivery**:
  - Node.js is used **only** during development/CI (`npm run build`).
  - Vite outputs hashed static assets into `app/static/spa/`.
  - Flask serves `/api/v1/*` JSON routes and serves `app/static/spa/index.html` for SPA client routes—requiring **zero Node.js process** on shared hosting.
- **Data Transport**:
  - Configurable visibility-aware REST polling hook (`usePollingQuery`): e.g., 5s–10s when tab is focused, backed off to 30s–60s when backgrounded, with manual refresh and request deduplication to protect shared-hosting CPU.
  - Abstracted behind a `RealtimeTransport` interface so WebSockets can be plugged in optionally on a VPS.

### 7.2 Brand Identity & `SOLID-GLASS` Visual Language
- **Aesthetic Direction**: Premium institutional crypto trading terminal fused with high-contrast Swiss/editorial precision.
- **Core Philosophy (`SOLID-GLASS`)**:
  - **Solid Confident Surfaces (80% of viewport)**: Crisp, opaque surfaces for all data tables, PnL figures, order parameters, charts, and risk gauges—guaranteeing instant legibility and low GPU overhead.
  - **Selective Glass Surfaces (20% of viewport)**: Controlled translucency (`backdrop-blur-md`, subtle 1px specular border, restrained elevation shadow) reserved strictly for sticky top navigation, floating command/filter bars, modal drawers, toast overlays, and status pills.
  - **Zero SaaS Cliché**: No purple/indigo gradients, no neon rainbow badges, no gratuitous glow clutter.

### 7.3 Design Tokens

| Token Role | Light / Editorial Surface Mode | Dark / Terminal Surface Mode | Usage |
| :--- | :--- | :--- | :--- |
| **Canvas Primary** | `#FFFFFF` (Pure White) | `#0A0A0B` (Deep Obsidian Black) | Primary page & workspace background |
| **Surface Solid** | `#F7F7F8` / `#FFFFFF` | `#111113` / `#161619` | Primary data cards, tables, chart containers |
| **Surface Glass** | `rgba(255, 255, 255, 0.76)` + `blur(12px)` | `rgba(17, 17, 19, 0.74)` + `blur(12px)` | Sticky header, floating drawers, contextual overlays |
| **Ink Primary** | `#0A0A0B` | `#FFFFFF` | Headlines, prices, primary metrics |
| **Ink Secondary** | `#52525B` | `#A1A1AA` | Labels, timestamps, axis ticks |
| **Border Hairline** | `rgba(10, 10, 11, 0.10)` | `rgba(255, 255, 255, 0.10)` | Crisp 1px structural dividers |
| **Brand Vivid Orange** | `#FF5500` (Hover: `#E04B00`) | `#FF5500` (Hover: `#FF6B1A`) | Primary CTAs, active nav indicator, Paper Mode badge, primary chart accent |
| **Orange Subtle Wash** | `rgba(255, 85, 0, 0.08)` | `rgba(255, 85, 0, 0.14)` | Active row highlight, focus rings, selected tabs |
| **Semantic Functional** | Emerald `#10B981` / Crimson `#EF4444` / Amber `#F59E0B` | Emerald `#10B981` / Crimson `#EF4444` / Amber `#F59E0B` | Used **sparingly** for strictly financial Buy/Profit, Sell/Loss/Kill-Switch, and Wait/Warning states |

### 7.4 Typography, Spacing & Component Rules
- **Typography**:
  - UI & Editorial Headings: Clean geometric sans (`Inter` / `Plus Jakarta Sans`, tight tracking `-0.02em` on display KPIs).
  - Financial Numerals, Orderbooks, Hashes & Timestamps: `JetBrains Mono` with mandatory `font-variant-numeric: tabular-nums` so live-updating prices and Rial/Toman columns never jitter horizontally.
- **Spacing & Grid**: 4px base unit (`8px` compact table cells, `16px`/`24px` card padding, 12-column desktop terminal grid collapsing cleanly to single-column stacked cards + slide-over navigation on mobile).
- **Reusable Core Component Kit**:
  - `SolidCard`, `GlassPanel`, `ActionButton` (Vivid Orange primary, Solid Black/White secondary, Danger Kill-Switch), `DataGridTable` (sticky header, tabular numerals, skeleton loader, rich empty state), `StatusBadge` (`PAPER MODE — LOCKED`, `APPROVE`, `REJECT`, `WAIT`), `MetricStatTile`, `DrawerInspector`.

### 7.5 Dashboard Information Architecture (13 Mandatory Modules)
1. **Sophisticated Collapsible Sidebar**: Route navigation, persistent `PAPER TRADING ONLY` safety lock emblem, quick risk status summary.
2. **Solid-Glass Sticky Top Bar**: Active Nobitex market ticker strip (`BTC/IRT`, `USDT/IRT`), Exchange & AI connectivity pills, Cron Heartbeat indicator, Theme switcher, Emergency Risk Kill-Switch trigger.
3. **Portfolio Overview**: Total Paper Equity (`IRT` & `USDT` equivalent), 24h/All-Time simulated PnL, available vs. allocated buying power.
4. **Capital Allocation**: Interactive breakdown of cash reserves vs. spot asset exposure vs. max allocation caps.
5. **Performance Charts**: Equity curve & drawdown area/line charts (`Recharts`) styled in Vivid Orange and Monochrome ink.
6. **Active Paper Positions**: Entry price, current Nobitex mark price, unrealized PnL, deterministic SL/TP levels, holding duration.
7. **Signal Monitoring Feed**: Live stream of normalized Telegram, TradingView, and Internal signals with pipeline stage badges.
8. **AI Validation Inspector**: Expandable structured drawer displaying AI verdict (`APPROVE`/`REJECT`/`WAIT`), confidence, identified contradictions, latency, and model metadata.
9. **Risk Monitoring Panel**: Daily drawdown meter, per-trade risk utilization, rejected-trade reason breakdown, active safety locks.
10. **Trading History Ledger**: Immutable log of simulated fills, simulated fees, slippage, and closed-trade realized PnL.
11. **Exchange Connection Status**: Nobitex public API latency, rate-limit budget utilization, last quote freshness timestamp.
12. **System Health & Shared-Hosting Telemetry**: Database WAL status, last cron tick execution time, task lock state, missed-tick recovery counter.
13. **Notifications & Audit Activity Log**: Chronological operator/system audit trail with severity filters.
