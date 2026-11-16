# AGENTS.md — Morph-Traider Operating Manual

This document is the canonical operating specification for all AI coding agents and contributors working on **Morph-Traider** (the AI-Powered Nobitex Trading System). Every rule below is mandatory.

---

## 1. Session Startup & Memory Recovery Protocol

Never rely exclusively on conversation history. The repository is the single source of truth.

At the **start of every session**, before proposing changes or writing code:

1. Read these four files in order:
   - `AGENTS.md`
   - `docs/CURRENT_STATE.md`
   - `docs/NEXT_TASK.md`
   - `docs/ROADMAP.md`
2. Read relevant architecture references (`docs/PROJECT_CHARTER.md`, `docs/SYSTEM_ARCHITECTURE.md`, `docs/TECHNICAL_DECISIONS.md`) when touching module boundaries, database schemas, exchange interfaces, or UI design tokens.
3. Inspect Git status (`git status`, `git log -n 5` once Git is initialized) and verify the actual files on disk match `docs/CURRENT_STATE.md` before continuing.
4. Start non-trivial implementation tasks in **Plan Mode** when architectural or multi-file design choices exist.

---

## 2. Context Budget & Interruption Recovery Rules

1. **30% Context Budget Ceiling**: Never consume more than approximately **30% of the available context window** during a single working session.
2. **Single-Task Discipline**: Execute **one small, independently testable task at a time**. Never attempt to implement multiple major roadmap phases in a single session.
3. **Checkpoint Before Stopping**: Before ending a session—or immediately when approaching the 30% context ceiling—write a clean recovery checkpoint by updating:
   - `docs/CURRENT_STATE.md` (what is implemented, tested, and verified on disk right now)
   - `docs/NEXT_TASK.md` (the exact next small, self-contained task to execute)
   - `docs/ROADMAP.md` (status checkboxes/markers if task or phase status changed)

---

## 3. Work Execution Protocol

Follow this strict lifecycle for every task:

1. **Inspect** — Check existing directories, modules, tests, and config before creating or editing any file.
2. **Implement** — Keep changes focused strictly on the active task in `docs/NEXT_TASK.md`. Do not create speculative empty directories or unused boilerplate.
3. **Test & Verify** — Run automated tests (`uv run pytest` for backend, `npm run build` / `npm test` for frontend once initialized) and verify behavior before claiming completion. Report test output faithfully.
4. **Document** — Update `docs/CURRENT_STATE.md`, `docs/NEXT_TASK.md`, and `docs/ROADMAP.md` immediately after verification.
5. **Checkpoint** — Leave the workspace in a clean, runnable, recoverable state.

---

## 4. Financial Safety Invariants (NON-NEGOTIABLE)

1. **PAPER TRADING ONLY**: All initial phases operate strictly in simulated paper-trading mode (`TRADING_MODE=paper`).
2. **Zero Real Orders**: No live spot or margin order submission may be active. Any future Nobitex live execution adapter must remain behind hard, disabled-by-default multi-gate configuration locks requiring explicit human authorization.
3. **Zero Withdrawal Capabilities**: Never implement withdrawal endpoints, withdrawal models, or request withdrawal API key scopes under any circumstance.
4. **Zero Secrets in Repository**: Never commit, hardcode, or log real Nobitex API tokens, webhook secrets, Telegram tokens, or AI provider keys in source files, tests, or documentation. Use `.env.example` with safe dummy placeholders only.
5. **No Automatic Live Transition**: No code path, AI output, scheduled job, or performance metric may automatically switch the system from paper trading to live trading.
6. **Deterministic Risk Authority Over AI**:
   - AI modules may only return structured advisory assessments (`APPROVE`, `REJECT`, `WAIT`).
   - AI must **never** directly call execution services or bypass deterministic risk controls.
   - If an AI provider times out, errors, or returns malformed data, the pipeline must **fail safe** (defaulting to `WAIT` or `REJECT`, never `APPROVE`).

---

## 5. Architecture & Shared-Hosting Constraints

 Rank architectural decisions strictly by `docs/PROJECT_CHARTER.md` priorities:

1. **Target Environment**: Ordinary Python-compatible **shared hosting** via standard **WSGI** (`wsgi.py` with Passenger / Gunicorn / uWSGI).
2. **Backend Stack**: Python 3.11+, **Flask** modular monolith (Flask Blueprints, Flask-SQLAlchemy, Flask-Migrate, Pydantic, HTTPX/Requests, SQLite default with WAL mode + PostgreSQL compatibility).
3. **No Mandatory Heavy Infrastructure**: Do **not** require Redis, Celery, Docker, Kubernetes, RabbitMQ/Kafka, microservices, persistent daemon workers, or local LLMs. (VPS features like APScheduler background workers or WebSockets must remain strictly optional upgrades.)
4. **Stateless Workers & Cron-Safe Tasks**: Never store critical trading, lock, or portfolio state in process memory. Periodic tasks must execute safely via hosting cron hitting an authenticated internal endpoint (`/api/v1/tasks/tick`) guarded by database lease locks and idempotency keys.
5. **Frontend Stack & `SOLID-GLASS` Design**: React + TypeScript + Vite + Tailwind CSS + Recharts built into static assets served by Flask (Node.js is build-time only). Enforce the **Morph-Traider `SOLID-GLASS`** visual system: Pure White (`#FFFFFF`), Deep Black (`#0A0A0B`), and Vivid Orange (`#FF5500`) accents—high-contrast solid data surfaces paired with selective glass panels.
6. **Nobitex Source of Truth**: Use official Nobitex documentation (`https://apidocs.nobitex.ir/`) as the sole source of truth. Never invent endpoints or assume Rial (`RLS`) vs. Toman (`IRT`) units—always convert and label monetary units explicitly.

---

## 6. Workspace Tooling & Security Hygiene

- Write and edit files exclusively via dedicated file tools (`Write` / `Edit`), never via shell heredocs or redirections.
- When running Python commands on this workstation, prefer `uv run ...` so virtual environment paths resolve cleanly.
- Never pass untrusted dynamic input to shell subprocesses or dynamic server-side string templates.
