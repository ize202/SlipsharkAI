from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from exa_search import process_query
import os
from dotenv import load_dotenv

#--------------------------------
# Environment Setup
#--------------------------------
load_dotenv()

# Validate required environment variables
required_env_vars = {
    "API_KEY": os.getenv("API_KEY"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "EXA_API_KEY": os.getenv("EXA_API_KEY")
}

missing_vars = [var for var, value in required_env_vars.items() if not value]
if missing_vars:
    raise Exception(f"Missing required environment variables: {', '.join(missing_vars)}")

app = FastAPI(
    title="Sports Research API",
    description="API for real-time sports information using GPT-4 and Exa search",
    version="1.0.0"
)

# API Key security scheme
api_key_header = APIKeyHeader(name="X-API-Key")

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """Validate API key"""
    if api_key_header != required_env_vars["API_KEY"]:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )
    return api_key_header

class ResearchRequest(BaseModel):
    query: str

class ResearchResponse(BaseModel):
    answer: str

@app.post("/research", response_model=ResearchResponse)
async def research(
    request: ResearchRequest,
    api_key: str = Depends(get_api_key)
):
    """
    Process a sports-related query and return researched information.
    Requires API key in X-API-Key header.
    """
    try:
        response = process_query(request.query)
        return ResearchResponse(answer=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Health check endpoint (no auth required)"""
    return {
        "status": "ok",
        "message": "Sports Research API is running",
        "version": "1.0.0"
    } 