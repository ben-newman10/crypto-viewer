"""
Server entry point for the Crypto Viewer backend.
Configures and launches the FastAPI application using Uvicorn ASGI server.

The server runs in development mode with auto-reload enabled
and detailed logging for easier debugging.
"""

import uvicorn
import logging

# Configure detailed logging for development
# Debug level ensures maximum visibility of application behavior
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Crypto Viewer API server...")
    
    # Run the FastAPI application with Uvicorn
    # Host: 0.0.0.0 allows external connections
    # Port: 3001 to avoid conflicts with common development ports
    # Reload: True enables auto-reload on code changes
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=3001,
        reload=True,
        log_level="debug"
    )