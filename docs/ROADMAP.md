# ROADMAP — Morph-Traider

Every phase is decomposed into small, independently testable tasks designed to fit comfortably inside the **30% session context budget**. Never execute multiple major phases in a single session.

---

## Phase 0 — Foundation, Architecture, Design Spec & Persistent Memory [COMPLETED]
- [x] **Task 0.1**: Inspect greenfield workspace and official Nobitex documentation portal (`https://apidocs.nobitex.ir/`).
- [x] **Task 0.2**: Initialize ZCode persistent project memory (`MEMORY.md` + architecture & safety feedback files).
- [x] **Task 0.3**: Create root governance (`AGENTS.md`, `.gitignore`, `README.md`).
- [x] **Task 0.4**: Author `docs/PROJECT_CHARTER.md`, `docs/SYSTEM_ARCHITECTURE.md` (including `SOLID-GLASS` UI spec & shared-hosting execution model), and `docs/TECHNICAL_DECISIONS.md`.
- [x] **Task 0.5**: Author `docs/ROADMAP.md`, `docs/CURRENT_STATE.md`, and define the single next actionable task (`docs/NEXT_TASK.md` -> Task 1.1).

---

## Phase 1 — Backend Core Skeleton, Safety Locks & Cron Task Primitives [NEXT]
- [ ] **Task 1.1**: Bootstrap Flask application factory (`app/__init__.py`), typed `app/config.py` with hard `TRADING_MODE=paper` safety assertions, `wsgi.py`, SQLite WAL + Flask-SQLAlchemy/Migrate setup, `.env.example`, and `/api/v1/health` endpoint + pytest suite.
- [ ] **Task 1.2**: Implement `app/core/` utilities (`Decimal` & `RLS`/`IRT`/`USDT` unit math, UTC time, structured logging, domain exceptions, HMAC signature helpers) with unit tests.
- [ ] **Task 1.3**: Implement SQL-backed `task_locks` & `scheduled_tasks` models, idempotent `TaskOrchestratorService`, and HMAC-protected `POST /api/v1/tasks/tick` cron endpoint with crash/lease-expiry recovery tests.
- [ ] **Task 1.4**: Implement operator authentication blueprint (`app/blueprints/auth/`) and `audit_logs` persistence.

---

## Phase 2 — Frontend Bootstrap & `SOLID-GLASS` Design System Kit
- [ ] **Task 2.1**: Initialize `frontend/` (Vite + React + TypeScript strict + Tailwind CSS + Recharts) configured to build static output into `app/static/spa/`, plus Flask SPA static-serving route and build smoke test.
- [ ] **Task 2.2**: Implement `SOLID-GLASS` design tokens (`#FFFFFF`, `#0A0A0B`, `#FF5500`, `JetBrains Mono` tabular numerals) and core reusable UI primitives (`SolidCard`, `GlassPanel`, `ActionButton`, `StatusBadge`, `DataGridTable`, `MetricStatTile`, `DrawerInspector`).
- [ ] **Task 2.3**: Build the responsive institutional shell (Collapsible Sidebar with persistent `PAPER TRADING ONLY` lock emblem, Sticky Glass Top Bar, visibility-aware REST polling hook, empty/loading/error states).

---

## Phase 3 — Isolated Nobitex Adapter (Public Market Data & Future Contract Interfaces)
- [ ] **Task 3.1**: Verify exact live public endpoint paths/payloads against `https://apidocs.nobitex.ir/`, define `ExchangePublicDataProtocol` & disabled-by-default `ExchangeSpotTradingProtocol` (zero withdrawal methods), and implement `RLS` <-> `IRT` precision/tick rules.
- [ ] **Task 3.2**: Implement `NobitexPublicClient` (`httpx`, SQL-backed rate-limit budget tracker, retries/timeouts, error mapping) with deterministic recorded-fixture tests.
- [ ] **Task 3.3**: Implement `market_data` module & persistence (`market_snapshots`, OHLCV cache) wired into the cron tick runner.

---

## Phase 4 — Source-Independent Signal Ingestion & Deterministic Technical Analysis
- [ ] **Task 4.1**: Implement `signal_engine` canonical `NormalizedSignal` schema, deduplication/idempotency store, and `signals` SQL model.
- [ ] **Task 4.2**: Implement signed TradingView Webhook adapter, Telegram signal parser/webhook adapter, and Internal Strategy signal emitter under `app/blueprints/signals/`.
- [ ] **Task 4.3**: Implement `technical_analysis` deterministic indicator engine (EMA trend alignment, RSI, ATR volatility, support/resistance, R:R calculation) producing structured `TAReport` outputs.

---

## Phase 5 — Provider-Independent AI Validation Engine
- [ ] **Task 5.1**: Define `AIValidatorProviderProtocol`, Pydantic `AISignalAssessment` (`APPROVE` | `REJECT` | `WAIT`), deterministic pre-filter gate, and `DeterministicMockAIAdapter`.
- [ ] **Task 5.2**: Implement external HTTPS AI provider adapter (`OpenAICompatibleAdapter` / `GeminiAdapter`), SQL circuit-breaker quota/health tracking, and strict fail-safe `WAIT` fallback tests on timeout/malformed JSON.

---

## Phase 6 — Decision Engine, Deterministic Risk Gate & Paper Trading Broker
- [ ] **Task 6.1**: Implement `decision_engine` combining `TAReport` + `AISignalAssessment` into candidate trade intents without execution authority.
- [ ] **Task 6.2**: Implement `risk_management` final gatekeeper (Kill-Switch, `TRADING_MODE==paper` assertion, per-trade % risk sizing, daily drawdown cap, max open positions, stale-quote & max-spread rejection) with exhaustive veto unit tests.
- [ ] **Task 6.3**: Implement `paper_trading` simulated spot broker, double-entry `paper_wallets`, realistic Nobitex bid/ask spread + fee simulation, and `execution` router hard-locked to `PaperTradingBroker`.
- [ ] **Task 6.4**: Implement `position_management` & `reporting` modules (open position mark-to-market, deterministic SL/TP triggers on cron ticks, equity curve & PnL metrics).

---

## Phase 7 — Institutional Dashboard Integration & Polish
- [ ] **Task 7.1**: Expose `/api/v1/dashboard`, `/portfolio`, `/signals`, `/trading`, and `/settings` read/control REST endpoints with response schemas matching TypeScript types.
- [ ] **Task 7.2**: Connect all 13 `SOLID-GLASS` dashboard views/panels (Portfolio Overview, Capital Allocation, Equity/Drawdown Recharts, Active Positions, Signal Feed, AI Inspector Drawer, Risk Telemetry, Trade History, Exchange/Cron Health, Kill-Switch).
- [ ] **Task 7.3**: Desktop & mobile responsive QA, accessibility contrast check, loading/error/empty state verification, and static bundle optimization.

---

## Phase 8 — Recovery Hardening, Shared-Hosting Packaging & Security Verification
- [ ] **Task 8.1**: End-to-end interruption & missed-cron recovery test suite (simulating worker kills, expired SQL leases, AI outages, and Nobitex HTTP 429/5xx responses).
- [ ] **Task 8.2**: Shared-hosting deployment guide (Passenger/cPanel `wsgi.py`, cron configuration, SQLite backup & optional VPS upgrade runbook) + full security/safety audit confirming zero live-order paths and zero exposed secrets.
