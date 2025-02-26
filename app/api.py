# Import config first to initialize LangTrace
from app.config import *

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from typing import Union, Dict, Any, Optional
from .workflows.betting_chain import BettingResearchChain
from .models.betting_models import QuickResearchResult, DeepResearchResult
from .utils.cache import clear_cache, get_cache_stats
from .middleware.auth import APIKeyMiddleware
from .middleware.usage_tracking import UsageTrackingMiddleware, get_usage_stats
from .config.rate_limit import limiter, ANALYZE_RATE_LIMIT, EXTEND_RATE_LIMIT, get_api_key
from .config.auth import verify_api_key
from .config.logging_config import configure_logging, get_logger
from .utils.error_handling import (
    APIError, 
    api_error_handler, 
    validation_exception_handler,
    http_exception_handler,
    general_exception_handler
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

# Attach rate limiter to the app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, limiter.error_handler)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add rate limiting middleware
app.add_middleware(SlowAPIMiddleware)

# Add usage tracking middleware
app.add_middleware(UsageTrackingMiddleware)

# Add API Key authentication middleware
app.add_middleware(APIKeyMiddleware)

# Add request ID middleware
@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """Add a unique request ID to each request for tracking"""
    request_id = request.headers.get("X-Request-ID", f"req_{int(time.time() * 1000)}")
    request.state.request_id = request_id
    
    # Create a logger with request context
    request_logger = get_logger("request", {"request_id": request_id})
    request_logger.info(f"Request started: {request.method} {request.url.path}")
    
    # Process the request and measure timing
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    
    # Log request completion
    request_logger.info(
        f"Request completed: {request.method} {request.url.path} "
        f"- Status: {response.status_code} - Time: {process_time:.4f}s"
    )
    
    return response

# Initialize the betting research chain
betting_chain = BettingResearchChain()

# Mount static files directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

class QueryRequest(BaseModel):
    query: str
    force_deep_research: bool = False

class ExtendResearchRequest(BaseModel):
    original_query: str
    quick_result: QuickResearchResult

class CacheRequest(BaseModel):
    pattern: str = "*"

class UsageStatsRequest(BaseModel):
    api_key: Optional[str] = None
    days: int = 7

@app.get("/")
async def root():
    """Serve the main frontend page"""
    return FileResponse("app/static/index.html")

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    # Include basic system information
    return {
        "status": "healthy",
        "environment": ENVIRONMENT,
        "version": app.version,
        "timestamp": time.time()
    }

@app.post("/analyze", response_model=Union[QuickResearchResult, DeepResearchResult])
@limiter.limit(ANALYZE_RATE_LIMIT, key_func=get_api_key)
async def analyze_betting_query(request: QueryRequest, req: Request):
    """
    Analyze a sports betting query and return either quick or deep research results.
    Rate limited to control costs and prevent abuse.
    """
    request_logger = get_logger("analyze", {"request_id": req.state.request_id})
    request_logger.info(f"Analyzing query: {request.query[:50]}...")
    
    try:
        result = await betting_chain.process_query(
            request.query,
            force_deep_research=request.force_deep_research
        )
        
        # Extract the conversational response if it exists
        conversational_response = result.pop("conversational_response", None)
        
        # Include it in the response body instead of headers
        response = result
        if conversational_response:
            # Add it to the response content
            response["conversational_response"] = conversational_response
        
        request_logger.info(f"Analysis complete: {request.query[:50]}...")
        return response
    except Exception as e:
        request_logger.error(f"Error processing query: {str(e)}", exc_info=True)
        raise

@app.post("/extend", response_model=DeepResearchResult)
@limiter.limit(EXTEND_RATE_LIMIT, key_func=get_api_key)
async def extend_research(request: ExtendResearchRequest, req: Request):
    """
    Extend a quick research result into a deep research analysis.
    Heavily rate limited due to high resource usage.
    """
    request_logger = get_logger("extend", {"request_id": req.state.request_id})
    request_logger.info(f"Extending research for query: {request.original_query[:50]}...")
    
    try:
        result = await betting_chain.extend_research(
            request.quick_result,
            request.original_query
        )
        
        # Extract the conversational response if it exists
        conversational_response = result.pop("conversational_response", None)
        
        # Include it in the response body instead of headers
        response = result
        if conversational_response:
            # Add it to the response content
            response["conversational_response"] = conversational_response
        
        request_logger.info(f"Extended research complete: {request.original_query[:50]}...")
        return response
    except Exception as e:
        request_logger.error(f"Error extending research: {str(e)}", exc_info=True)
        raise

@app.get("/cache/stats")
@limiter.limit("30/minute", key_func=get_api_key)
async def cache_stats(req: Request):
    """
    Get cache statistics
    """
    request_logger = get_logger("cache", {"request_id": req.state.request_id})
    request_logger.info("Retrieving cache statistics")
    
    try:
        stats = get_cache_stats()
        return stats
    except Exception as e:
        request_logger.error(f"Error getting cache stats: {str(e)}", exc_info=True)
        raise

@app.post("/cache/clear")
@limiter.limit("10/minute", key_func=get_api_key)
async def clear_cache_endpoint(request: CacheRequest, req: Request):
    """
    Clear cache entries matching the given pattern
    """
    request_logger = get_logger("cache", {"request_id": req.state.request_id})
    request_logger.info(f"Clearing cache with pattern: {request.pattern}")
    
    try:
        clear_cache(request.pattern)
        return {"status": "success", "message": f"Cache cleared with pattern: {request.pattern}"}
    except Exception as e:
        request_logger.error(f"Error clearing cache: {str(e)}", exc_info=True)
        raise

@app.post("/admin/usage")
@limiter.limit("20/minute", key_func=get_api_key)
async def usage_statistics(
    request: UsageStatsRequest, 
    req: Request,
    api_key: str = Depends(verify_api_key)
):
    """
    Get API usage statistics.
    Admin-only endpoint that requires API key authentication.
    """
    request_logger = get_logger("admin", {"request_id": req.state.request_id})
    request_logger.info(f"Retrieving usage statistics for days: {request.days}")
    
    try:
        stats = await get_usage_stats(request.api_key, request.days)
        return stats
    except Exception as e:
        request_logger.error(f"Error getting usage stats: {str(e)}", exc_info=True)
        raise 