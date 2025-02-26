# API Authentication System

This directory contains the middleware components for the Sports Research API, including the authentication system.

## Overview

The authentication system uses API keys to protect endpoints from unauthorized access. It follows these principles:

- **Deny by Default**: All endpoints require authentication unless explicitly marked as public
- **Environment-Based**: API keys are configured through environment variables
- **Development Mode**: Automatically generates keys in development for convenience
- **Production Mode**: Requires explicit key setting for security

## Components

The authentication system consists of two main components:

1. **Configuration (`app/config/auth.py`)**:
   - Defines what authentication is (API key validation)
   - Manages API key retrieval and validation
   - Defines which endpoints are public

2. **Middleware (`app/middleware/auth.py`)**:
   - Defines how authentication is applied (as middleware)
   - Intercepts all requests and validates API keys
   - Exempts public endpoints from authentication

## Public vs. Protected Endpoints

The system classifies endpoints as follows:

### Public Endpoints (No Authentication Required)

```python
PUBLIC_ENDPOINTS = {
    "/": {"GET"},
    "/health": {"GET"},
    "/docs": {"GET"},
    "/openapi.json": {"GET"},
    "/redoc": {"GET"},
}
```

### Protected Endpoints (Authentication Required)

All endpoints not listed in `PUBLIC_ENDPOINTS` require authentication, including:
- `/analyze`
- `/extend`
- `/cache/stats`
- `/cache/clear`

## Testing Authentication

Use the script `scripts/test_auth_workflow.py` to test the entire authentication flow:

```bash
python scripts/test_auth_workflow.py
```

## Generating API Keys

Use the script `scripts/generate_api_key.py` to generate secure API keys for production:

```bash
python scripts/generate_api_key.py
```

## Deployment Configuration

When deploying to production:

1. Generate a secure API key:
   ```bash
   python scripts/generate_api_key.py
   ```

2. Set environment variables:
   - `API_KEY`: Your generated secure key
   - `ENVIRONMENT`: Set to `production`

## Client Usage

Clients should include the API key in the `X-API-Key` header:

```python
import requests

API_URL = "https://your-api-url.com"
API_KEY = "your_api_key_here"

response = requests.post(
    f"{API_URL}/analyze",
    json={"query": "Should I bet on the Lakers tonight?"},
    headers={"X-API-Key": API_KEY}
)
``` 