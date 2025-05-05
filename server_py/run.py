import uvicorn
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG to show debug-level logs
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=3001, reload=True)