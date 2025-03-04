from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from exa_search import process_query
from auth_service import verify_api_key
import os
from dotenv import load_dotenv

#--------------------------------
# Environment Setup
#--------------------------------
load_dotenv()

# Validate required environment variables
required_env_vars = ["OPENAI_API_KEY", "EXA_API_KEY"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise Exception(f"Missing required environment variables: {', '.join(missing_vars)}")

#--------------------------------
# FastAPI Setup
#--------------------------------
app = FastAPI(
    title="Sports Research API",
    description="API for real-time sports information using GPT-4 and Exa search",
    version="1.0.0"
)

#--------------------------------
# Models
#--------------------------------
class ResearchRequest(BaseModel):
    query: str

class ResearchResponse(BaseModel):
    answer: str

#--------------------------------
# Endpoints
#--------------------------------
@app.post("/research", response_model=ResearchResponse)
async def research(
    request: ResearchRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Process a sports-related query and return researched information.
    Requires valid API key in X-API-Key header.
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