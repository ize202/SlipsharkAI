"""
Main entry point for the Sports Research API.
This file is used to start the FastAPI application.
"""
import os
import sys
import logging
import traceback

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
logger.info(f"Added to Python path: {os.path.dirname(os.path.abspath(__file__))}")

try:
    # First try to fix the directory structure if needed
    logger.info("Ensuring directory structure is correct...")
    try:
        from fix_directory_structure import fix_directory_structure
        fix_directory_structure()
    except Exception as e:
        logger.error(f"Failed to fix directory structure: {str(e)}")
        traceback.print_exc()
    
    # Try to import the FastAPI app
    logger.info("Trying to import FastAPI app...")
    try:
        from app.api import app
        logger.info("Successfully imported FastAPI app!")
    except ImportError as e:
        logger.error(f"Failed to import app/api.py: {str(e)}")
        traceback.print_exc()
        
        # Try to create a minimal FastAPI app as a fallback
        logger.info("Creating minimal FastAPI app as fallback...")
        from fastapi import FastAPI
        app = FastAPI(
            title="Sports Research API (Fallback)",
            description="Minimal fallback mode due to import errors",
        )
        
        @app.get("/")
        async def root():
            return {
                "status": "error",
                "message": "Running in fallback mode due to import errors",
                "error": str(e)
            }
        
        @app.get("/health")
        async def health():
            return {
                "status": "unhealthy",
                "error": "Running in fallback mode",
                "details": str(e)
            }
    
    # This allows the app to be run with `python main.py`
    if __name__ == "__main__":
        import uvicorn
        port = int(os.environ.get("PORT", 8000))
        logger.info(f"Starting uvicorn server on port {port}...")
        uvicorn.run(app, host="0.0.0.0", port=port)
except Exception as e:
    logger.critical(f"Critical error in main.py: {str(e)}")
    traceback.print_exc()
    
    # Try to create an absolute minimal application as a last resort
    try:
        import uvicorn
        from fastapi import FastAPI
        emergency_app = FastAPI(title="Emergency Fallback API")
        
        @emergency_app.get("/")
        async def emergency_root():
            return {
                "status": "critical_error",
                "message": "Application failed to start properly",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
        
        port = int(os.environ.get("PORT", 8000))
        logger.info(f"Starting emergency fallback on port {port}...")
        uvicorn.run(emergency_app, host="0.0.0.0", port=port)
    except Exception as final_e:
        logger.critical(f"Failed to start emergency fallback: {str(final_e)}")
        sys.exit(1) 