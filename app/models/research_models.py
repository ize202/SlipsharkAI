from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union
from datetime import datetime

class SportType(str, Enum):
    BASKETBALL = "basketball"
    FOOTBALL = "football"
    BASEBALL = "baseball"
    HOCKEY = "hockey"
    SOCCER = "soccer"
    OTHER = "other"

class ResearchMode(str, Enum):
    AUTO = "auto"
    QUICK = "quick"
    DEEP = "deep"

class QueryContext(BaseModel):
    """Optional context for the research request"""
    previous_query_id: Optional[str] = None
    user_id: Optional[str] = None

class ResearchRequest(BaseModel):
    """Main request model for the research endpoint"""
    query: str = Field(..., description="The user's sports betting query")
    mode: ResearchMode = Field(default=ResearchMode.AUTO, description="Research mode to use")
    context: Optional[QueryContext] = Field(default=None, description="Optional query context")

class QueryAnalysis(BaseModel):
    """Output of the first LLM call - Query Analysis"""
    raw_query: str
    sport_type: SportType
    teams: Dict[str, Optional[str]] = Field(default_factory=dict)
    players: List[str] = Field(default_factory=list)
    bet_type: Optional[str] = None
    required_data: List[str] = Field(default_factory=list)
    recommended_mode: ResearchMode
    confidence_score: float = Field(ge=0.0, le=1.0)

class DataPoint(BaseModel):
    """Structure for individual pieces of gathered data"""
    source: str
    content: Union[str, dict]
    timestamp: datetime
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class Insight(BaseModel):
    """Structure for individual insights"""
    category: str
    content: str
    impact: str
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_data: List[str] = Field(default_factory=list)

class RiskFactor(BaseModel):
    """Structure for identified risk factors"""
    factor: str
    severity: str
    mitigation: Optional[str] = None

class Source(BaseModel):
    """Structure for data sources used"""
    name: str
    type: str
    url: Optional[str] = None
    timestamp: datetime
    snippet: Optional[str] = None

class ResearchMetadata(BaseModel):
    """Metadata about the research process"""
    query_id: str
    mode_used: ResearchMode
    processing_time: float
    confidence_score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ResearchResponse(BaseModel):
    """Final response model returned to the user"""
    summary: str
    insights: List[Insight]
    recommendations: List[str]
    risk_factors: List[RiskFactor]
    sources: List[Source]
    metadata: ResearchMetadata 