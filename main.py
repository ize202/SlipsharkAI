from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from workflow.exa_search import process_query
from services.auth_service import verify_api_key
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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://slipshark.com"],  # Add your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

#--------------------------------
# Models
#--------------------------------
class ResearchRequest(BaseModel):
    query: str
    stream: bool = True  # Default to True for streaming
    maxResults: int | None = None
    platform: str = "mobile"  # Default to mobile if not specified

class ResearchResponse(BaseModel):
    answer: str

#--------------------------------
# Endpoints
#--------------------------------
@app.post("/research")
async def research(
    request: ResearchRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Process a sports-related query and stream the researched information.
    Requires valid API key in X-API-Key header.
    """
    try:
        # Create an async generator for the streaming response
        async def generate_response():
            for chunk in process_query(request.query):
                # Each chunk should be prefixed with 'data: ' and end with two newlines
                # This follows SSE (Server-Sent Events) protocol
                yield f"data: {chunk}\n\n"

        return StreamingResponse(
            generate_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Transfer-Encoding": "chunked",
            }
        )
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