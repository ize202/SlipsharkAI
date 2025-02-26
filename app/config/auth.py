"""
Authentication configuration for the Sports Research API.
Provides API key validation and security utilities.
"""
import os
import secrets
from fastapi import Security, HTTPException, Depends, status
from fastapi.security.api_key import APIKeyHeader

# Constants
API_KEY_NAME = "X-API-Key"
API_KEY_ENV_VAR = "API_KEY"

# Initialize API key header checker
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def get_api_key_from_env():
    """
    Get the API key from environment variables.
    If not set, generate a secure random key for development.
    """
    api_key = os.getenv(API_KEY_ENV_VAR)
    if not api_key:
        # For development only - in production, always set API_KEY
        if os.getenv("ENVIRONMENT", "development") == "development":
            api_key = secrets.token_urlsafe(32)
            os.environ[API_KEY_ENV_VAR] = api_key
            print(f"WARNING: Generated temporary API key for development: {api_key}")
            print(f"Set this in your environment or .env file as {API_KEY_ENV_VAR}=<key>")
        else:
            raise EnvironmentError(f"{API_KEY_ENV_VAR} environment variable is not set")
    return api_key

# Get the API key at module load time
API_KEY = get_api_key_from_env()

async def verify_api_key(api_key_header: str = Security(api_key_header)):
    """
    Verify that the API key in the request header matches the expected key.
    This function is used as a FastAPI dependency for protected endpoints.
    """
    if not api_key_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key header is missing",
            headers={"WWW-Authenticate": API_KEY_NAME},
        )
    
    if api_key_header != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": API_KEY_NAME},
        )
    
    return api_key_header

# Public endpoints that don't require API key authentication
PUBLIC_ENDPOINTS = {
    "/": {"GET"},
    "/health": {"GET"},
    "/docs": {"GET"},
    "/openapi.json": {"GET"},
    "/redoc": {"GET"},
}

def is_public_endpoint(path: str, method: str) -> bool:
    """
    Check if an endpoint is public (doesn't require authentication).
    """
    if path in PUBLIC_ENDPOINTS and method in PUBLIC_ENDPOINTS[path]:
        return True
    return False 