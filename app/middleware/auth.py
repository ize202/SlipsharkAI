"""
Authentication middleware for the Sports Research API.
Provides API key validation for all non-public endpoints.
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from app.config.auth import API_KEY, API_KEY_NAME, is_public_endpoint
import logging

logger = logging.getLogger(__name__)

class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware that checks for a valid API key in the request header.
    Public endpoints (defined in config.auth) are exempt from this check.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Log all requests
        logger.info(f"Request: {request.method} {request.url.path}")
        
        # Check if this is a public endpoint
        if is_public_endpoint(request.url.path, request.method):
            logger.info(f"Public endpoint: {request.method} {request.url.path}")
            return await call_next(request)
        
        # Get API key from header
        api_key = request.headers.get(API_KEY_NAME)
        logger.info(f"API Key header: {API_KEY_NAME}={api_key}")
        
        # Validate API key
        if not api_key:
            logger.warning(f"Missing API key for request to {request.url.path}")
            return self._unauthorized_response("API Key header is missing")
        
        if api_key != API_KEY:
            logger.warning(f"Invalid API key used for request to {request.url.path}")
            logger.debug(f"Expected: {API_KEY}, Got: {api_key}")
            return self._unauthorized_response("Invalid API Key")
        
        # API key is valid, proceed with the request
        logger.info(f"Valid API key for request to {request.url.path}")
        return await call_next(request)
    
    def _unauthorized_response(self, detail: str):
        """
        Create a standardized unauthorized response.
        """
        from fastapi.responses import JSONResponse
        
        logger.info(f"Returning unauthorized response: {detail}")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail},
            headers={"WWW-Authenticate": API_KEY_NAME},
        ) 