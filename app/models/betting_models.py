from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from enum import Enum

class SportType(str, Enum):
    FOOTBALL = "football"
    BASKETBALL = "basketball"
    BASEBALL = "baseball"
    HOCKEY = "hockey"
    SOCCER = "soccer"
    OTHER = "other"

class QueryAnalysis(BaseModel):
    """Initial analysis of user query"""
    raw_query: str = Field(description="Original user query")
    sport_type: SportType = Field(description="Identified sport type")
    is_deep_research: bool = Field(description="Whether this requires deep research")
    confidence_score: float = Field(description="Confidence score between 0 and 1")
    required_data_sources: List[str] = Field(description="List of required data sources")

class Citation(BaseModel):
    """Citation for a piece of information"""
    url: str = Field(description="Source URL")
    title: Optional[str] = Field(None, description="Title of the source")
    snippet: Optional[str] = Field(None, description="Relevant excerpt from the source")
    published_date: Optional[str] = Field(None, description="Publication date if available")

class QuickResearchResult(BaseModel):
    """Result from quick research flow using Perplexity AI"""
    summary: str = Field(description="Brief summary of findings")
    key_points: List[str] = Field(description="Key betting insights")
    confidence_score: float = Field(description="Confidence in the analysis")
    deep_research_recommended: bool = Field(description="Whether deep research is recommended")
    citations: Optional[List[Citation]] = Field(default=[], description="Sources cited in the research")
    related_questions: Optional[List[str]] = Field(default=[], description="Related betting questions to consider")
    last_updated: str = Field(description="Timestamp of when this research was conducted")

class DataPoint(BaseModel):
    """Individual data point from various sources"""
    source: str = Field(description="Source of the data")
    timestamp: str = Field(description="When this data was collected/published")
    content: dict = Field(description="The actual data content")
    relevance_score: float = Field(description="How relevant this data is to the query")

class DeepResearchResult(BaseModel):
    """Comprehensive research result"""
    summary: str = Field(description="Detailed analysis summary")
    historical_data: List[DataPoint] = Field(description="Historical performance data")
    current_odds: dict = Field(description="Current betting odds")
    key_insights: List[str] = Field(description="Key betting insights")
    risk_factors: List[str] = Field(description="Identified risk factors")
    confidence_score: float = Field(description="Overall confidence in the analysis")
    supporting_data: List[DataPoint] = Field(description="Supporting data points") 