"""
Error handling utilities for the Sports Research API.
Provides standardized error responses and exception handling.
"""
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import logging
import traceback
import uuid
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

class APIError(Exception):
    """Base exception class for API errors"""
    def __init__(
        self, 
        message: str, 
        status_code: int = 500, 
        error_code: str = "internal_error",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

class ValidationAPIError(APIError):
    """Validation error in API request"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="validation_error",
            details=details
        )

class AuthenticationAPIError(APIError):
    """Authentication error in API request"""
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="authentication_error",
            details=details
        )

class AuthorizationAPIError(APIError):
    """Authorization error in API request"""
    def __init__(self, message: str = "Not authorized", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="authorization_error",
            details=details
        )

class ResourceNotFoundAPIError(APIError):
    """Resource not found error in API request"""
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="resource_not_found",
            details=details
        )

class RateLimitAPIError(APIError):
    """Rate limit exceeded error in API request"""
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="rate_limit_exceeded",
            details=details
        )

class ServiceUnavailableAPIError(APIError):
    """Service unavailable error in API request"""
    def __init__(self, message: str = "Service temporarily unavailable", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="service_unavailable",
            details=details
        )

class ExternalAPIError(APIError):
    """Error from external API"""
    def __init__(self, message: str, service: str, details: Optional[Dict[str, Any]] = None):
        details = details or {}
        details["service"] = service
        super().__init__(
            message=message,
            status_code=status.HTTP_502_BAD_GATEWAY,
            error_code="external_api_error",
            details=details
        )

def format_validation_errors(errors: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Format validation errors into a more user-friendly structure.
    
    Args:
        errors: List of validation errors
        
    Returns:
        Dictionary mapping field names to lists of error messages
    """
    formatted_errors: Dict[str, List[str]] = {}
    
    for error in errors:
        loc = error.get("loc", [])
        if len(loc) > 0:
            field = str(loc[-1])
            if field not in formatted_errors:
                formatted_errors[field] = []
            formatted_errors[field].append(error.get("msg", "Unknown validation error"))
    
    return formatted_errors

def create_error_response(
    error: Union[APIError, Exception],
    request: Optional[Request] = None,
    include_traceback: bool = False
) -> Dict[str, Any]:
    """
    Create a standardized error response.
    
    Args:
        error: The exception that occurred
        request: Optional request object for additional context
        include_traceback: Whether to include traceback in the response
        
    Returns:
        Standardized error response dictionary
    """
    # Generate a unique error ID for tracking
    error_id = str(uuid.uuid4())
    
    # Get request information if available
    request_info = {}
    if request:
        request_info = {
            "method": request.method,
            "url": str(request.url),
            "client_host": request.client.host if request.client else None,
            "headers": dict(request.headers)
        }
    
    # Create the base response
    response = {
        "error": {
            "id": error_id,
            "timestamp": datetime.utcnow().isoformat(),
            "status_code": 500,
            "error_code": "internal_error",
            "message": str(error)
        }
    }
    
    # Add API error specific fields
    if isinstance(error, APIError):
        response["error"]["status_code"] = error.status_code
        response["error"]["error_code"] = error.error_code
        if error.details:
            response["error"]["details"] = error.details
    
    # Add traceback for debugging if requested
    if include_traceback:
        response["error"]["traceback"] = traceback.format_exception(
            type(error), error, error.__traceback__
        )
    
    # Log the error with context
    log_context = {
        "error_id": error_id,
        "error_type": type(error).__name__,
        "request": request_info
    }
    
    if isinstance(error, APIError):
        log_context["status_code"] = error.status_code
        log_context["error_code"] = error.error_code
        
    logger.error(
        f"API Error: {str(error)}",
        extra={"error_context": log_context}
    )
    
    return response

async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """
    Handle APIError exceptions and return standardized responses.
    
    Args:
        request: The request that caused the exception
        exc: The APIError exception
        
    Returns:
        JSONResponse with standardized error format
    """
    # Get environment to determine if we should include traceback
    include_traceback = request.app.state.environment == "development"
    
    response = create_error_response(
        error=exc,
        request=request,
        include_traceback=include_traceback
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle validation exceptions and return standardized responses.
    
    Args:
        request: The request that caused the exception
        exc: The validation exception
        
    Returns:
        JSONResponse with standardized error format
    """
    # Format validation errors
    errors = format_validation_errors(exc.errors())
    
    # Create a ValidationAPIError with the formatted errors
    api_error = ValidationAPIError(
        message="Request validation failed",
        details={"validation_errors": errors}
    )
    
    return await api_error_handler(request, api_error)

async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle HTTPException and return standardized responses.
    
    Args:
        request: The request that caused the exception
        exc: The HTTP exception
        
    Returns:
        JSONResponse with standardized error format
    """
    # Map HTTP exception to appropriate API error
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        api_error = AuthenticationAPIError(message=exc.detail)
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        api_error = AuthorizationAPIError(message=exc.detail)
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        api_error = ResourceNotFoundAPIError(message=exc.detail)
    elif exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
        api_error = RateLimitAPIError(message=exc.detail)
    else:
        api_error = APIError(
            message=exc.detail,
            status_code=exc.status_code,
            error_code=f"http_{exc.status_code}"
        )
    
    return await api_error_handler(request, api_error)

async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handle general exceptions and return standardized responses.
    
    Args:
        request: The request that caused the exception
        exc: The exception
        
    Returns:
        JSONResponse with standardized error format
    """
    # Get environment to determine if we should include traceback
    include_traceback = request.app.state.environment == "development"
    
    response = create_error_response(
        error=exc,
        request=request,
        include_traceback=include_traceback
    )
    
    return JSONResponse(
        status_code=500,
        content=response
    ) 