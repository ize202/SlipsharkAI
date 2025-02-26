"""
Main entry point for the Sports Research API.
This file is used to start the FastAPI application.
"""
import os
import sys

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the FastAPI app
from app.api import app

# This allows the app to be run with `python main.py`
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.api:app", host="0.0.0.0", port=port, reload=False) 