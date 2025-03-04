from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from exa_search import process_query

app = FastAPI(
    title="Sports Research API",
    description="API for real-time sports information using GPT-4 and Exa search",
    version="1.0.0"
)

class ResearchRequest(BaseModel):
    query: str

class ResearchResponse(BaseModel):
    answer: str

@app.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest):
    """
    Process a sports-related query and return researched information.
    
    Args:
        request: ResearchRequest containing the query
        
    Returns:
        ResearchResponse containing the answer
        
    Raises:
        HTTPException: If there's an error processing the query
    """
    try:
        response = process_query(request.query)
        return ResearchResponse(answer=response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "Sports Research API is running"} 