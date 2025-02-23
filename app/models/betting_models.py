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
    raw_query: str
    sport_type: SportType
    is_deep_research: bool
    confidence_score: float
    required_data_sources: List[str]
    bet_type: Optional[str] = None

class QuickResearchResult(BaseModel):
    """Result from quick research flow using Perplexity AI"""
    summary: str = Field(description="Brief summary of findings")
    key_points: List[str] = Field(description="Key betting insights")
    confidence_score: float = Field(description="Confidence in the analysis")
    deep_research_recommended: bool = Field(description="Whether deep research is recommended")
    citations: Optional[List[Citation]] = Field(default=[], description="Sources cited in the research")
    related_questions: Optional[List[str]] = Field(default=[], description="Related betting questions to consider")
    last_updated: str = Field(description="Timestamp of when this research was conducted")

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