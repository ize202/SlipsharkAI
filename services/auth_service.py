from fastapi import HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
import os

class AuthService:
    def __init__(self):
        self.api_key = os.getenv("API_KEY")
        if not self.api_key:
            raise Exception("API_KEY environment variable not set")
        if not self.api_key.startswith("sk_v1_"):
            raise Exception("Invalid API_KEY format. Please generate a new key using generate_key.py")
        
        # Initialize API key header checker
        self.api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

    async def verify_api_key(self, api_key: str = Security(APIKeyHeader(name="X-API-Key", auto_error=True))) -> str:
        """
        Verify that the API key is valid and has the correct format.
        Will automatically raise 403 if header is missing due to auto_error=True
        """
        if not api_key.startswith("sk_v1_"):
            raise HTTPException(
                status_code=403,
                detail="Invalid API key format. Please use a newly generated key."
            )
        
        if api_key != self.api_key:
            raise HTTPException(
                status_code=403,
                detail="Could not validate API key"
            )
        return api_key

# Create a singleton instance
auth_service = AuthService()
# Export the verify function directly
verify_api_key = auth_service.verify_api_key 