# Import config first to initialize LangTrace
from app.config import *

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
import os
from typing import Union, Dict, Any, Optional
from app.workflows.research_chain import ResearchChain
from app.models.research_models import ResearchRequest, ResearchResponse
from app.utils.cache import clear_cache, get_cache_stats
from app.middleware.auth import APIKeyMiddleware
from app.middleware.usage_tracking import UsageTrackingMiddleware, get_usage_stats
from app.config.rate_limit import limiter, ANALYZE_RATE_LIMIT, get_api_key, rate_limit_exceeded_handler
from app.config.auth import verify_api_key
from app.config.logging_config import configure_logging, get_logger
from app.utils.error_handling import (
    APIError, 
    api_error_handler, 
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler,
    RateLimitAPIError
)
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import logging
import time

# Load environment variables
load_dotenv()

# Configure logging
configure_logging()
logger = get_logger(__name__)

# Get environment
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Verify OpenAI API key is set
if not os.getenv("OPENAI_API_KEY"):
    raise EnvironmentError("OPENAI_API_KEY environment variable is not set")

app = FastAPI(
    title="Sports Research AI",
    description="AI-powered sports research and analysis system",
    version="1.0.0"
)

# Store environment in app state for error handlers
app.state.environment = ENVIRONMENT

# Register exception handlers
app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this with your frontend origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(SlowAPIMiddleware)

# Add auth middleware
app.add_middleware(APIKeyMiddleware)

# Add usage tracking middleware
app.add_middleware(UsageTrackingMiddleware)

# Initialize research chain
research_chain = ResearchChain()

@app.post("/research", response_model=ResearchResponse)
@limiter.limit(ANALYZE_RATE_LIMIT, key_func=get_api_key)
async def research_endpoint(request: ResearchRequest, req: Request):
    """
    Unified research endpoint that handles both quick and deep research modes.
    
    Args:
        request: ResearchRequest containing the query and mode
        req: FastAPI request object for rate limiting
        
    Returns:
        ResearchResponse containing analysis and insights
    """
    request_logger = get_logger("research", {"request_id": req.state.request_id})
    request_logger.info(f"Processing research request: {request.query[:50]}...")
    
    try:
        response = await research_chain.process_request(request)
        request_logger.info(f"Research complete for: {request.query[:50]}")
        return response
        
    except Exception as e:
        request_logger.error(f"Error processing research request: {str(e)}", exc_info=True)
        raise APIError(
            status_code=500,
            detail="Error processing research request",
            error_type="RESEARCH_ERROR"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    return await get_cache_stats()

@app.post("/cache/clear")
async def clear_cache_endpoint():
    """Clear the cache"""
    await clear_cache()
    return {"status": "cache cleared"}

@app.get("/usage")
async def usage_stats():
    """Get API usage statistics"""
    return await get_usage_stats() 