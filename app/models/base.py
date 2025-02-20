from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ResearchRequest(BaseModel):
    query: str
    context: Optional[Dict[str, Any]] = None
    parameters: Optional[Dict[str, Any]] = None

class ResearchResponse(BaseModel):
    result: str
    confidence: float
    sources: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None 