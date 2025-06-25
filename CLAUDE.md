# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Structure

This is a cryptocurrency portfolio tracking application with a React/TypeScript frontend and Python FastAPI backend.

**Frontend (React + Vite):**
- Located in `/src/` directory
- Uses Chakra UI for component library
- React Query for data fetching and caching
- Main components: `Portfolio.tsx` (portfolio display), `Recommendations.tsx` (AI recommendations)
- Vite dev server runs on port 5173 with API proxy to backend

**Backend (Python FastAPI):**
- Located in `/server_py/` directory  
- FastAPI application with routers for crypto and recommendations endpoints
- Integrates with Coinbase Advanced Trade API for real-time crypto data
- Uses OpenAI for crypto analysis and recommendations
- Runs on port 3001 in development

## Common Development Commands

**Frontend:**
```bash
npm run dev          # Start frontend dev server (also starts backend)
npm run build        # Build for production
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

**Full Development Setup:**
```bash
npm run dev          # Starts both frontend and backend concurrently
```

## Architecture

**Data Flow:**
1. Frontend components use React Query to fetch data from `/api/*` endpoints
2. Vite dev server proxies API requests to FastAPI backend on port 3001
3. Backend services (`coinbase_service.py`, `ai_service.py`) handle external API calls
4. Real-time updates via 30-second polling intervals

**Key Services:**
- `coinbase_service.py`: Handles Coinbase API integration for portfolio and price data
- `ai_service.py`: OpenAI integration for crypto analysis and recommendations
- API routers in `/routers/` handle endpoint logic

**Environment Setup:**
- Backend requires `.env` file in `server_py/` with `COINBASE_API_KEY` and `COINBASE_API_SECRET`
- Uses Python virtual environment in `server_py/venv/`
- Frontend dependencies managed via npm

## Testing

Backend tests use pytest and cover:
- AI service functionality (`test_ai_service.py`)
- Coinbase service integration (`test_coinbase_service.py`) 
- API router endpoints (`test_crypto_router.py`, `test_recommendations_router.py`)

Run tests with: `cd server_py && pytest`