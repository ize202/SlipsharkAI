from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Union, Any
from datetime import datetime
import json

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

class Citation(BaseModel):
    """Citation for a source used in research"""
    url: str = Field(description="URL of the source")
    title: Optional[str] = Field(default=None, description="Title of the source")
    snippet: Optional[str] = Field(default=None, description="Relevant snippet from the source")
    published_date: Optional[str] = Field(default=None, description="Publication date of the source")
    
    def model_dump(self) -> dict:
        """Convert the model to a dictionary"""
        return {
            "url": self.url,
            "title": self.title,
            "snippet": self.snippet,
            "published_date": self.published_date
        }

class QueryContext(BaseModel):
    """Optional context for the research request"""
    previous_query_id: Optional[str] = None
    user_id: Optional[str] = None
    user_preferences: Optional[Dict[str, Any]] = None
    bet_history: Optional[Dict[str, Any]] = None

class ResearchContext(BaseModel):
    """Context information for research processing"""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    previous_queries: Optional[List[str]] = Field(default_factory=list)
    preferences: Optional[Dict[str, Any]] = Field(default_factory=dict)
    bet_history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

class ResearchRequest(BaseModel):
    """Main request model for the research endpoint"""
    query: str = Field(..., description="The user's sports betting query")
    mode: ResearchMode = Field(default=ResearchMode.AUTO, description="Research mode to use")
    context: Optional[ResearchContext] = Field(default=None, description="Optional research context")

class QueryAnalysis(BaseModel):
    """Output of the first LLM call - Query Analysis"""
    raw_query: str
    sport_type: SportType
    teams: Dict[str, Optional[str]] = Field(default_factory=dict)
    players: List[str] = Field(default_factory=list)
    bet_type: Optional[str] = None
    odds_mentioned: Optional[str] = Field(default=None, description="Any specific odds or lines mentioned")
    game_date: Optional[str] = Field(default=None, description="Date of the game if mentioned")
    matchup_focus: Optional[str] = Field(default=None, description="Specific matchup or aspect of interest")
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
    """Structure for individual betting insights"""
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

class UserStats(BaseModel):
    """Model for user betting statistics"""
    user_id: str
    entry_type: str
    sport: str
    period: str
    total_entries: Optional[int]
    won_entries: Optional[int]
    total_stake: Optional[float]
    total_payout: Optional[float]
    roi: Optional[float]
    updated_at: Optional[datetime]

class UserPreferences(BaseModel):
    """Model for user betting preferences"""
    user_id: str
    favorite_teams: List[str]
    favorite_leagues: List[str]
    stake_limits: Dict[str, float]
    notification_preferences: Dict[str, bool]
    updated_at: datetime

class BetHistory(BaseModel):
    """Model for user betting history"""
    id: str
    user_id: str
    sport: str
    bet_type: str
    selection: str
    odds: float
    stake: float
    potential_payout: float
    outcome: Optional[str] = None
    placed_at: datetime
    settled_at: Optional[datetime] = None

class ResearchMetadata(BaseModel):
    """Metadata about the research process"""
    query_id: str
    mode_used: ResearchMode
    processing_time: float
    confidence_score: float = Field(ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class QuickResearchResponse(BaseModel):
    """Response model for quick research mode"""
    summary: str = Field(description="Brief summary of findings")
    confidence_score: float = Field(description="Confidence in the analysis")
    deep_research_recommended: bool = Field(description="Whether deep research is recommended")
    citations: List[Citation] = Field(default=[], description="Sources cited in the research")
    related_questions: List[str] = Field(default=[], description="Related betting questions to consider")
    last_updated: str = Field(description="Timestamp of when this research was conducted")
    conversational_response: Optional[str] = Field(default=None, description="Natural language conversational response")

class DeepResearchResponse(BaseModel):
    """Response model for deep research mode"""
    summary: str = Field(description="Executive summary of the analysis")
    insights: List[Insight] = Field(description="Key betting insights with supporting data")
    risk_factors: List[RiskFactor] = Field(description="Identified risk factors")
    recommended_bet: Optional[str] = Field(description="Recommended betting action")
    odds_analysis: Dict[str, Any] = Field(description="Detailed odds analysis")
    historical_context: Optional[str] = Field(description="Relevant historical betting patterns")
    confidence_score: float = Field(description="Overall confidence in the analysis (0-1)")
    citations: List[Citation] = Field(description="All sources used in the analysis")
    last_updated: str = Field(description="Timestamp of when this research was conducted")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata about the analysis")
    conversational_response: Optional[str] = Field(default=None, description="Natural language conversational response")

class ResearchResponse(BaseModel):
    """Final response model returned to the user"""
    summary: str
    insights: List[Insight]
    recommendations: List[str]
    risk_factors: List[RiskFactor]
    sources: List[Source]
    metadata: ResearchMetadata 