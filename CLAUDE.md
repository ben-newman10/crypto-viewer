# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Structure

This is a cryptocurrency portfolio tracking application with a React/TypeScript frontend and Python FastAPI backend.

**Frontend (React + Vite):**
- Located in `/src/` directory
- Uses Chakra UI for component library, React Router for pages, React Query for data fetching and caching
- Design tokens live in `src/theme/tokens.ts`; the Chakra theme in `src/theme/index.ts` exposes them
  as semantic tokens (`bg.surface`, `fg.muted`, `gain.fg`, ...). Components reference semantic tokens
  only — no one-off colours, radii or shadows.
- Pages: `src/pages/DashboardPage.tsx`, `src/pages/CoinPage.tsx`, `src/pages/NotFoundPage.tsx`
- Main components: `Portfolio.tsx` (holdings), `Recommendations.tsx` (AI analysis),
  `components/portfolio/*` (summary, table, mobile cards), `components/common/*` (shared primitives)
- Data hooks: `src/hooks/usePortfolio.ts` (`usePortfolio`, `useCoin`)
- Formatting helpers: `src/lib/format.ts`; typed API client: `src/lib/api.ts`
- Vite dev server runs on port 5173 with API proxy to backend

**Backend (Python FastAPI):**
- Located in `/server_py/` directory
- FastAPI application with routers for crypto and recommendations endpoints
- Services are injected via `app/dependencies.py` (`Depends(get_coinbase_service)` /
  `Depends(get_ai_service)`) — routers never construct services at import time
- Integrates with Coinbase Advanced Trade API for real-time crypto data
- Uses OpenAI for crypto analysis and recommendations
- Runs on port 3001 in development

## Common Development Commands

**Frontend:**
```bash
npm run dev          # Start frontend dev server (also starts backend)
npm run build        # Type-check (tsc -b) and build for production
npm run typecheck    # Type-check only
npm run lint         # Run ESLint
npm run preview      # Preview production build
```

**Backend:**
```bash
cd server_py
python run.py        # Start backend server directly
pytest              # Run all tests
pytest test_*.py     # Run specific test files
```

**End-to-end tests:**
```bash
npx playwright test  # Starts backend (test mode) + preview build, then runs the suite
npm run test:e2e:ui  # Interactive runner
```

**Full Development Setup:**
```bash
npm run dev          # Starts both frontend and backend concurrently
```

## Architecture

**Data Flow:**
1. Frontend components use React Query to fetch data from `/api/*` endpoints
2. Vite dev server proxies API requests to FastAPI backend on port 3001
   (target overridable via `VITE_API_PROXY_TARGET`)
3. Backend services (`coinbase_service.py`, `ai_service.py`) handle external API calls
4. Real-time updates via 30-second polling intervals

**Key Services:**
- `coinbase_service.py`: Handles Coinbase API integration for portfolio and price data
- `ai_service.py`: OpenAI integration for crypto analysis and recommendations
- API routers in `/routers/` handle endpoint logic

**Notable data contracts:**
- `/api/crypto/price/{pair}` answers **200 with an `error` key** when the upstream lookup fails,
  so the frontend must handle a successful response that carries no price
- Fiat balances (e.g. `GBP`) appear in the portfolio but have no tradeable pair; the UI treats them
  as cash valued 1:1 and never requests a price for them
- Portfolio balances come from `get_portfolios` + `get_portfolio_breakdown` (`spot_positions`), **not**
  `get_accounts`. The accounts endpoint omits staked funds entirely — a staked ETH holding reports
  `available_balance` *and* `hold` as zero there — so reading it dropped staked assets from the
  portfolio. `balance` is the total **including** staked funds; `available` is only what can be
  traded, so a fully staked holding legitimately shows `available: "0.00"`.
- `/api/crypto/portfolio` **raises on failure** (→ 500) rather than returning `[]`, so a credential or
  network error surfaces as a retryable error instead of a misleading "no holdings" state. An empty
  list means the account genuinely holds nothing. `get_accounts` remains a fallback if the breakdown
  endpoint is unavailable, with the known limitation that it cannot see staked funds.

**Environment Setup:**
- Backend requires `.env` file in `server_py/` with `COINBASE_API_KEY` and `COINBASE_API_SECRET`
- Uses Python virtual environment in `server_py/venv/`
- Frontend dependencies managed via npm

## Accessibility

The UI targets WCAG 2.1 AA. When changing the UI, preserve:
- Landmarks (`header`/`nav`/`main`/`footer`), the skip link, and a single `<h1>` per page
- Ordered headings — markdown from the AI endpoint is shifted down a level in `Recommendations.tsx`
- Gain/loss conveyed by icon + sign + hidden direction word, never colour alone
- `aria-live` regions for polled data (portfolio total, AI analysis)
- Contrast: semantic `*.fg` tokens are chosen to clear 4.5:1 on `bg.surface` and their `*.subtle`
  backgrounds in both themes. Do not fade them with `opacity`.
- `prefers-reduced-motion`: CSS handles transitions/animations (`src/index.css`); JS-driven motion
  uses `useReducedMotion`.

Automated axe-core scans run in `e2e/accessibility.spec.ts` and fail on any critical or serious
violation.

## Testing

Backend tests use pytest and cover:
- AI service functionality (`test_ai_service.py`)
- Coinbase service integration (`test_coinbase_service.py`)
- API router endpoints (`test_crypto_router.py`, `test_recommendations_router.py`)

Run tests with: `cd server_py && pytest`

### Test mode (no third-party calls)

`CRYPTO_VIEWER_TEST_MODE=1` makes `app/dependencies.py` return the fakes in
`app/services/fakes/` instead of the real Coinbase/OpenAI clients. `conftest.py` enables it for
pytest, and `playwright.config.ts` enables it for the backend it starts. Fixture data lives in
`app/services/fakes/fixtures.py`.

Per-request scenarios (empty portfolio, upstream errors, slow responses) are selected with the
`cv_test_scenario` cookie; flags are defined in `app/services/fakes/scenarios.py` and mirrored in
`e2e/support/scenarios.ts` — **keep those two files in sync**.

### E2E suite

`e2e/` contains the Playwright suite. `playwright.config.ts` starts a test-mode backend on 3101 and
serves the production build on 4173 with `/api` proxied to it, so tests exercise real HTTP between
frontend and backend. `e2e/support/fixtures.ts` fails any test whose browser reaches a non-local
host. Screenshots are written to `screenshots/` by `e2e/responsive-screenshots.spec.ts`.
