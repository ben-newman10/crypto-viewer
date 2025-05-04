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
- `GET /api/recommendations` - Get AI-powered recommendations for your portfolio

## Development

The server uses FastAPI with the following structure:
- `app/` - Main application directory
  - `main.py` - FastAPI application setup and configuration
  - `routers/` - API route handlers
  - `services/` - Business logic and external service integrations