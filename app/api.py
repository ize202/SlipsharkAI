# Import config first to initialize LangTrace
from app.config import *

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
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
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import logging

# Load environment variables
load_dotenv()

# Verify OpenAI API key is set
if not os.getenv("OPENAI_API_KEY"):
    raise EnvironmentError("OPENAI_API_KEY environment variable is not set")

app = FastAPI(
    title="Sports Research AI",
    description="AI-powered sports research and analysis system",
    version="1.0.0"
)

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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    return {"status": "healthy"}

@app.post("/analyze", response_model=Union[QuickResearchResult, DeepResearchResult])
@limiter.limit(ANALYZE_RATE_LIMIT, key_func=get_api_key)
async def analyze_betting_query(request: QueryRequest, req: Request):
    """
    Analyze a sports betting query and return either quick or deep research results.
    Rate limited to control costs and prevent abuse.
    """
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
        
        return response
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extend", response_model=DeepResearchResult)
@limiter.limit(EXTEND_RATE_LIMIT, key_func=get_api_key)
async def extend_research(request: ExtendResearchRequest, req: Request):
    """
    Extend a quick research result into a deep research analysis.
    Heavily rate limited due to high resource usage.
    """
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
        
        return response
    except Exception as e:
        logger.error(f"Error extending research: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cache/stats")
@limiter.limit("30/minute", key_func=get_api_key)
async def cache_stats(req: Request):
    """
    Get cache statistics
    """
    try:
        stats = get_cache_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting cache stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cache/clear")
@limiter.limit("10/minute", key_func=get_api_key)
async def clear_cache_endpoint(request: CacheRequest, req: Request):
    """
    Clear cache entries matching the given pattern
    """
    try:
        clear_cache(request.pattern)
        return {"status": "success", "message": f"Cache cleared with pattern: {request.pattern}"}
    except Exception as e:
        logger.error(f"Error clearing cache: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

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
    try:
        stats = await get_usage_stats(request.api_key, request.days)
        return stats
    except Exception as e:
        logger.error(f"Error getting usage stats: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 