# Import config first to initialize LangTrace
from app.config import *

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
from pydantic import BaseModel
from typing import Union
from .chains.betting_chain import BettingResearchChain
from .models.betting_models import QuickResearchResult, DeepResearchResult
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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the betting research chain
betting_chain = BettingResearchChain()

class QueryRequest(BaseModel):
    query: str
    force_deep_research: bool = False

class ExtendResearchRequest(BaseModel):
    original_query: str
    quick_result: QuickResearchResult

@app.get("/")
async def root():
    return {"message": "Welcome to Sports Research AI API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/analyze", response_model=Union[QuickResearchResult, DeepResearchResult])
async def analyze_betting_query(request: QueryRequest):
    """
    Analyze a sports betting query and return either quick or deep research results
    """
    try:
        result = await betting_chain.process_query(
            request.query,
            force_deep_research=request.force_deep_research
        )
        return result
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/extend", response_model=DeepResearchResult)
async def extend_research(request: ExtendResearchRequest):
    """
    Extend a quick research result into a deep research analysis
    """
    try:
        result = await betting_chain.extend_research(
            request.quick_result,
            request.original_query
        )
        return result
    except Exception as e:
        logger.error(f"Error extending research: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) 