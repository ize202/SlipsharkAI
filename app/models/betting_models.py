from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime

class SportType(str, Enum):
    """Supported sports for betting analysis"""
    BASKETBALL = "basketball"
    FOOTBALL = "football"
    BASEBALL = "baseball"
    HOCKEY = "hockey"
    SOCCER = "soccer"
    OTHER = "other"

class Citation(BaseModel):
    """Citation for research sources"""
    url: str
    title: Optional[str] = None
    snippet: Optional[str] = None
    published_date: Optional[str] = None

class DataPoint(BaseModel):
    """Data point from a specific source"""
    source: str
    content: Any
    timestamp: Optional[datetime] = None

class BettingInsight(BaseModel):
    """Key betting insight with supporting data"""
    category: str = Field(description="Category of insight (e.g., odds, performance, injury)")
    insight: str = Field(description="The actual insight")
    impact: str = Field(description="How this affects betting decisions")
    confidence: float = Field(description="Confidence score for this insight (0-1)")
    supporting_data: Optional[List[str]] = Field(default=[], description="Data points supporting this insight")

class RiskFactor(BaseModel):
    """Identified risk factor for the bet"""
    factor: str = Field(description="Description of the risk factor")
    severity: str = Field(description="low, medium, or high")
    mitigation: Optional[str] = Field(description="Possible ways to mitigate this risk")

class QueryAnalysis(BaseModel):
    """Analysis of the user's betting query"""
    raw_query: str = Field(description="The original query text")
    sport_type: SportType = Field(description="Type of sport being bet on")
    teams: Dict[str, str] = Field(
        default={},
        description="Teams mentioned in the query (e.g., {'team1': 'Denver Nuggets', 'team2': 'Indiana Pacers'})"
    )
    players: List[str] = Field(
        default=[],
        description="Players mentioned in the query"
    )
    bet_type: str = Field(
        default="",
        description="Type of bet (spread, moneyline, over/under, etc.)"
    )
    odds_mentioned: Optional[str] = Field(
        default=None,
        description="Any specific odds or lines mentioned in the query"
    )
    game_date: Optional[str] = Field(
        default=None,
        description="Date of the game if mentioned"
    )
    matchup_focus: Optional[str] = Field(
        default=None,
        description="Specific matchup or aspect of interest"
    )
    is_deep_research: bool = Field(
        default=False,
        description="Whether this query requires deep research"
    )
    confidence_score: float = Field(
        default=0.5,
        description="Confidence in the query analysis (0-1)"
    )
    required_data_sources: List[str] = Field(
        default=[],
        description="Data sources needed for analysis"
    )

class QuickResearchResult(BaseModel):
    """Result from quick research flow using Perplexity AI"""
    summary: str = Field(description="Brief summary of findings")
    key_points: List[str] = Field(description="Key betting insights")
    confidence_score: float = Field(description="Confidence in the analysis")
    deep_research_recommended: bool = Field(description="Whether deep research is recommended")
    citations: Optional[List[Citation]] = Field(default=[], description="Sources cited in the research")
    related_questions: Optional[List[str]] = Field(default=[], description="Related betting questions to consider")
    last_updated: str = Field(description="Timestamp of when this research was conducted")
    conversational_response: Optional[str] = Field(default=None, description="Natural language conversational response")

class DeepResearchResult(BaseModel):
    """Comprehensive research result using multiple data sources"""
    summary: str = Field(description="Executive summary of the analysis")
    insights: List[BettingInsight] = Field(description="Key betting insights with supporting data")
    risk_factors: List[RiskFactor] = Field(description="Identified risk factors")
    recommended_bet: Optional[str] = Field(description="Recommended betting action")
    odds_analysis: Dict[str, Any] = Field(description="Detailed odds analysis")
    historical_context: Optional[str] = Field(description="Relevant historical betting patterns")
    confidence_score: float = Field(description="Overall confidence in the analysis (0-1)")
    citations: List[Citation] = Field(description="All sources used in the analysis")
    last_updated: str = Field(description="Timestamp of when this research was conducted")
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata about the analysis")
    conversational_response: Optional[str] = Field(default=None, description="Natural language conversational response")

class BetHistory(BaseModel):
    """Model for bet details entries"""
    entry_id: str
    bet_type: str
    sport: str
    game_id: Optional[str] = None
    odds: Optional[float] = None
    boost_applied: Optional[bool] = None
    boost_percentage: Optional[float] = None
    cash_out_available: Optional[bool] = None
    early_payout: Optional[bool] = None
    void_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

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

class PerplexityResponse(BaseModel):
    """Response from Perplexity AI API"""
    content: str = Field(description="Main content/summary of the response")
    citations: List[Citation] = Field(default=[], description="Sources cited in the response")
    related_questions: List[str] = Field(default=[], description="Related questions suggested by Perplexity")
    key_points: List[str] = Field(default=[], description="Key points extracted from the analysis")
    confidence_score: float = Field(default=0.5, description="Confidence score in the analysis (0-1)")
    deep_research_recommended: bool = Field(default=False, description="Whether deep research is recommended") 