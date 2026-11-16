# NEXT TASK — Task 2.1: Initialize Frontend Workspace (`Vite + React + TS + Tailwind`) & Flask Static SPA Serving

## 1. Objective

Bootstrap the **TypeScript + React + Vite + Tailwind CSS + Recharts** frontend workspace (`frontend/`) configured to compile static production assets directly into `app/static/spa/`, and wire the Flask dashboard blueprint (`app/blueprints/dashboard/`) to serve the compiled SPA cleanly on shared hosting with **zero runtime Node.js requirement**.

---

## 2. Pre-Flight Recovery Checklist (Mandatory Before Coding)

1. Read `AGENTS.md`, `docs/CURRENT_STATE.md`, `docs/NEXT_TASK.md`, and `docs/ROADMAP.md`.
2. Read Section 7 of `docs/SYSTEM_ARCHITECTURE.md` (`SOLID-GLASS` Frontend Architecture & Design System Specification).
3. Inspect `git status` and `git log -n 3`, and confirm `uv run --extra dev pytest` passes before editing.

---

## 3. Scope & Files to Create / Update

1. **`frontend/` Workspace Initialization**:
   - `frontend/package.json`, `frontend/tsconfig.json`, `frontend/vite.config.ts`, `frontend/index.html`.
   - Dependencies: `react`, `react-dom`, `recharts`, `lucide-react`; dev dependencies: `typescript`, `vite`, `@vitejs/plugin-react`, `tailwindcss` (or `@tailwindcss/vite`), `vitest` / `@testing-library/react` (optional lightweight unit runner).
   - Configure `vite.config.ts` so `npm run build` outputs deterministic hashed static assets into `../app/static/spa` (`emptyOutDir: true`) and proxies `/api` to Flask during local `npm run dev`.
2. **Initial TypeScript Entry & Health Connectivity Smoke View**:
   - `frontend/src/main.tsx`, `frontend/src/App.tsx`, `frontend/src/styles/index.css`.
   - Establish foundational `SOLID-GLASS` CSS custom properties (`#FFFFFF`, `#0A0A0B`, `#FF5500`, `Inter` + `JetBrains Mono` `tabular-nums`) and render a clean initial shell verifying `/api/v1/health` types (`trading_mode: "paper"`).
3. **Flask Dashboard Static SPA Blueprint (`app/blueprints/dashboard/__init__.py`)**:
   - Serve compiled static assets and SPA `index.html` fallback for non-`/api/*` routes when `app/static/spa/index.html` exists, or return a clean JSON/HTML build-instructions fallback in dev when the SPA has not been built yet—never intercepting `/api/v1/*` routes or 404 API errors.
   - Register `dashboard_bp` in `app/__init__.py`.
4. **Automated Tests (`tests/test_spa_serving.py`)**:
   - Verify Flask serves SPA `index.html` and static assets from a configured SPA directory, falls back cleanly for client-side routes (e.g., `/portfolio`, `/signals`), and still returns proper JSON `404` for unknown `/api/v1/unknown` paths.
   - Verify `npm run build` (and `tsc --noEmit`) succeeds cleanly in `frontend/`.

---

## 4. Acceptance Criteria & Completion Steps

1. `npm --prefix frontend run build` compiles cleanly with strict TypeScript (`0` errors).
2. `uv run --extra dev pytest -v` passes 100% of backend + SPA serving tests.
3. Keep `app/static/spa/` git-ignored (or document build artifact handling cleanly in `.gitignore`) so Node build artifacts don't bloat source diffs unless explicitly intended for release packaging.
4. Update `docs/CURRENT_STATE.md`, `docs/ROADMAP.md`, and advance `docs/NEXT_TASK.md` to **Task 2.2** (`SOLID-GLASS` Design Tokens & Core Reusable Component Kit).
