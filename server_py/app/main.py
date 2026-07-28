"""
Main application module for the Crypto Viewer backend.
Sets up FastAPI application with CORS middleware and API routers.
"""

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import is_test_mode
from .routers import crypto, recommendations

# Load environment variables from .env file for configuration
load_dotenv()

# Initialize FastAPI application
app = FastAPI(
    title="Crypto Viewer API",
    description="Backend API for cryptocurrency portfolio tracking and analysis",
    version="1.0.0"
)

# Configure Cross-Origin Resource Sharing (CORS)
# This allows the frontend application to make requests to the backend.
# Origins are configurable so that a preview build served on a different port
# (as the E2E suite does) can be allowed without editing code.
_default_origins = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173"
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", _default_origins).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all HTTP headers
)

# Include routers for different API endpoints
# Each router handles a specific aspect of the application
app.include_router(
    crypto.router,
    prefix="/api/crypto",
    tags=["crypto"]
)
app.include_router(
    recommendations.router,
    prefix="/api/recommendations",
    tags=["recommendations"]
)

@app.get("/")
async def root():
    """
    Root endpoint of the API.
    Provides a simple health check and API information.

    Returns:
        dict: Basic API information and status
    """
    return {
        "message": "Crypto Viewer API",
        "status": "online",
        "version": "1.0.0",
        # Surfaced so the E2E harness can assert it is talking to a backend
        # wired up with fake third-party clients before running any test.
        "test_mode": is_test_mode(),
    }
