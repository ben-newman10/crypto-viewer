"""
Main application module for the Crypto Viewer backend.
Sets up FastAPI application with CORS middleware and API routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
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
# This allows the frontend application to make requests to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Frontend development server URL
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
        "version": "1.0.0"
    }