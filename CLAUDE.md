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
  `components/portfolio/*` (summary, table, mobile cards),
  `components/recommendations/*` (per-asset card, confidence/action badges, evidence
  disclosure), `components/common/*` (shared primitives)
- Data hooks: `src/hooks/usePortfolio.ts` (`usePortfolio`, `useCoin`)
- Formatting helpers: `src/lib/format.ts`; typed API client: `src/lib/api.ts`
- Vite dev server runs on port 5173 with API proxy to backend

**Backend (Python FastAPI):**
- Located in `/server_py/` directory
- FastAPI application with routers for crypto and recommendations endpoints
- Services are injected via `app/dependencies.py` (`Depends(get_coinbase_service)` /
  `Depends(get_ai_service)` / `Depends(get_market_context_service)`) — routers never
  construct services at import time
- Integrates with Coinbase Advanced Trade API for real-time crypto data
- Uses OpenAI (structured outputs) for crypto analysis and recommendations
- Typed contracts live in `app/schemas/`: `grounding.py` (what the model may reference)
  and `recommendation.py` (what it may return, and what the API serves)
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
- `coinbase_service.py`: Coinbase API integration for portfolio, price and candle data
  (`get_candles` takes a granularity/window; `get_historical_data` is the fixed 24h chart feed)
- `market_context_service.py`: CoinGecko + alternative.me Fear & Greed. Optional by design —
  a failure degrades to `unavailable` fields, never to an error
- `indicators.py`: RSI, MACD, SMAs, crossover state, volatility, drawdown. Pure functions,
  returning `None` rather than an approximation when the series is too short
- `context_builder.py`: assembles the typed grounding context from the above
- `ai_service.py`: the OpenAI call — structured outputs, `temperature=0.25`, validated reply
- `groundedness.py`: verifies every model claim against the context
- `recommendation_service.py`: orchestrates the whole run and injects the disclaimer
- `recommendation_log.py`: append-only JSONL audit log
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
- `/api/recommendations/` returns **structured JSON**, not prose: `status`, `summary`,
  `recommendations[]`, `disclaimer`, `groundedness` and the grounding `context`.
  A model that is unconfigured or unreachable is a **200 with `status="unavailable"`**,
  not a 500 — the portfolio data is still good. A 500 means the portfolio itself failed.

**Recommendation pipeline rules (non-negotiable):**
- Indicators are computed in code. The model is never asked to do arithmetic on a series.
- The model may reference only fields present in the grounding context, cited by exact name.
- A metric that cannot be computed is emitted with `status="unavailable"` and a reason —
  never omitted. Silently dropping it would *raise* the completeness ratio and therefore
  the confidence ceiling, which is the opposite of what a missing signal should do.
- Final confidence is `min(model_confidence, data_ceiling)`, downgraded further on a failed
  groundedness check. See the rubric in `app/schemas/grounding.py`; it is the single source
  used by the prompt, the ceiling and the docs — change it in one place.
- The disclaimer (`config.DISCLAIMER`) is injected server-side. Never ask the model for it.
- A supporting fact whose value the model misquoted is served with the **measured** value and
  `verified: false`; one citing an unknown or unavailable field is dropped entirely.

**Environment Setup:**
- Backend requires `.env` file in `server_py/` with `COINBASE_API_KEY` and `COINBASE_API_SECRET`
- Uses Python virtual environment in `server_py/venv/`
- Frontend dependencies managed via npm

## Accessibility

The UI targets WCAG 2.1 AA. When changing the UI, preserve:
- Landmarks (`header`/`nav`/`main`/`footer`), the skip link, and a single `<h1>` per page
- Ordered headings — the AI panel is an `<h2>`, each recommendation card an `<h3>`, and markdown
  in the summary is shifted down a level in `Recommendations.tsx`
- Gain/loss conveyed by icon + sign + hidden direction word, never colour alone
- Confidence and buy/sell/hold badges follow the same rule: icon + word + colour together
  (`components/recommendations/badges.tsx`)
- The disclaimer stays inside the analysis panel, attached to the recommendations themselves —
  not moved to the page footer
- `aria-live` regions for polled data (portfolio total, AI analysis)
- Contrast: semantic `*.fg` tokens are chosen to clear 4.5:1 on `bg.surface` and their `*.subtle`
  backgrounds in both themes. Do not fade them with `opacity`.
- `prefers-reduced-motion`: CSS handles transitions/animations (`src/index.css`); JS-driven motion
  uses `useReducedMotion`.

Automated axe-core scans run in `e2e/accessibility.spec.ts` and fail on any critical or serious
violation.

## Testing

Backend tests use pytest and cover:
- AI service seam: the fake, prompt construction and response handling (`test_ai_service.py`)
- Coinbase service integration (`test_coinbase_service.py`)
- Technical indicators, including their refusal to compute on short series (`test_indicators.py`)
- Grounding context assembly and graceful degradation (`test_context_builder.py`)
- Groundedness verification and the confidence rubric (`test_groundedness.py`)
- API router endpoints (`test_crypto_router.py`, `test_recommendations_router.py`)

Run tests with: `cd server_py && pytest`

### Test mode (no third-party calls)

`CRYPTO_VIEWER_TEST_MODE=1` makes `app/dependencies.py` return the fakes in
`app/services/fakes/` instead of the real Coinbase/OpenAI clients. `conftest.py` enables it for
pytest, and `playwright.config.ts` enables it for the backend it starts. Fixture data lives in
`app/services/fakes/fixtures.py`.

Per-request scenarios (empty portfolio, upstream errors, slow responses, thin grounding data,
an ungrounded model) are selected with the `cv_test_scenario` cookie; flags are defined in
`app/services/fakes/scenarios.py` and mirrored in `e2e/support/scenarios.ts` —
**keep those two files in sync**.

`FakeAIService` returns a *structured* payload, and builds its supporting facts out of the
grounding context it is handed rather than from a fixture of its own. That is deliberate: it
means the groundedness check is doing real work in tests instead of comparing one fixture
against another.

### E2E suite

`e2e/` contains the Playwright suite. `playwright.config.ts` starts a test-mode backend on 3101 and
serves the production build on 4173 with `/api` proxied to it, so tests exercise real HTTP between
frontend and backend. `e2e/support/fixtures.ts` fails any test whose browser reaches a non-local
host. Screenshots are written to `screenshots/` by `e2e/responsive-screenshots.spec.ts`.
