# Crypto Viewer Python Backend

This is the FastAPI backend for the Crypto Viewer application that interfaces with Coinbase Advanced Trade API and OpenAI for crypto analysis.

## Setup

1. Create a Python virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables in `.env`:
```
COINBASE_API_KEY=your_api_key
COINBASE_API_SECRET=your_api_secret
OPENAI_API_KEY=your_openai_api_key

# Optional
OPENAI_MODEL=gpt-4.1                    # must support structured outputs
CRYPTO_VIEWER_EXTERNAL_MARKET_DATA=1    # CoinGecko + Fear & Greed lookups
CRYPTO_VIEWER_RECOMMENDATION_LOG=logs/recommendations.jsonl
```

## Running the Server

1. Activate the virtual environment (if not already active):
```bash
source venv/bin/activate  # On Windows use: venv\Scripts\activate
```

2. Start the server:
```bash
python run.py
```

The server will start on `http://localhost:3001` with hot reloading enabled.

## API Endpoints

- `GET /api/crypto/portfolio` - Get user's crypto portfolio
- `GET /api/crypto/price/{product_id}` - Get current price for a crypto pair
- `GET /api/crypto/historical/{product_id}` - Get historical data for a crypto pair
- `GET /api/recommendations/` - Grounded, confidence-rated recommendations
- `GET /api/recommendations/analysis` - Alias of the above

## Development

The server uses FastAPI with the following structure:
- `app/` - Main application directory
  - `main.py` - FastAPI application setup and configuration
  - `config.py` - Environment switches and the injected disclaimer constant
  - `dependencies.py` - Service providers (real clients, or fakes in test mode)
  - `routers/` - API route handlers
  - `schemas/` - Typed contracts: `grounding.py` (what the model may cite, plus the
    confidence rubric) and `recommendation.py` (what it may return, and what is served)
  - `services/` - Business logic and external service integrations

### The recommendation pipeline

`services/recommendation_service.py` runs each request in order:

1. `context_builder.py` gathers portfolio, prices and 300 daily candles, computes
   indicators via `indicators.py`, and adds market context from
   `market_context_service.py`. Anything that cannot be computed becomes a field with
   `status="unavailable"` and a reason — never a missing key.
2. `ai_service.py` calls OpenAI with structured outputs against that closed field list
   and validates the reply.
3. `groundedness.py` re-checks every claim against the context: invented or unavailable
   fields are dropped, misquoted numbers are corrected to the measured value. One retry
   is made with the specific corrections named; a still-failing run is downgraded.
4. The disclaimer is injected from `config.DISCLAIMER`, and
   `recommendation_log.py` appends the context, output and check result to
   `logs/recommendations.jsonl` for later calibration against actual price movement.

See the repository README for the confidence rubric and what is out of scope.