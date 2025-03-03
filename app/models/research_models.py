from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
import pytz

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

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class Message(BaseModel):
    """Single message in the conversation"""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ConversationContext(BaseModel):
    """Essential context for maintaining conversation memory"""
    teams: List[str] = Field(default_factory=list)
    players: List[str] = Field(default_factory=list)
    sport: Optional[SportType] = None
    game_date: Optional[str] = None  # Must be string, not datetime
    bet_type: Optional[str] = None
    last_query: Optional[str] = None
    required_data: List[str] = Field(default_factory=list)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class QueryAnalysis(BaseModel):
    """Analysis of user's query"""
    raw_query: str
    sport_type: SportType
    teams: Dict[str, Optional[str]] = Field(default_factory=dict)
    players: List[str] = Field(default_factory=list)
    bet_type: Optional[str] = None
    odds_mentioned: Optional[str] = None
    game_date: Optional[str] = None  # Must be string, not datetime
    required_data: List[str] = Field(default_factory=list)
    recommended_mode: ResearchMode
    confidence_score: float = Field(ge=0.0, le=1.0)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class DataPoint(BaseModel):
    """Data gathered from various sources"""
    source: str
    content: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Custom serialization method"""
        return {
            "source": self.source,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence
        }

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        arbitrary_types_allowed = True

class ClientMetadata(BaseModel):
    """Metadata about the client making the request"""
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the request was made"
    )
    timezone: str = Field(
        default="UTC",
        description="Client's timezone (e.g. 'America/New_York')"
    )
    locale: str = Field(
        default="en-US",
        description="Client's locale"
    )

    @property
    def localized_timestamp(self) -> datetime:
        """Get the timestamp in the client's timezone"""
        tz = pytz.timezone(self.timezone)
        return self.timestamp.astimezone(tz)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class ResearchRequest(BaseModel):
    """Research request with context"""
    query: str = Field(description="The user's sports betting query")
    mode: ResearchMode = Field(default=ResearchMode.AUTO)
    context: Optional[ConversationContext] = None
    conversation_history: Optional[List[Message]] = Field(
        default_factory=list,
        max_items=5
    )
    client_metadata: ClientMetadata = Field(
        default_factory=ClientMetadata,
        description="Metadata about the client making the request"
    )

class ResearchResponse(BaseModel):
    """Unified research response"""
    response: str = Field(description="Natural language response")
    data_points: List[DataPoint] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)
    context_updates: Optional[ConversationContext] = None
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

        json_schema_extra = {
            "example": {
                "response": "The Lakers are 5.5-point favorites tonight against the Pistons. They've been playing well lately, winning 7 of their last 8 games.",
                "data_points": [
                    {
                        "source": "odds_api",
                        "content": {"spread": -5.5, "moneyline": -240},
                        "confidence": 0.95
                    }
                ],
                "suggested_questions": [
                    "How have the Lakers performed against the spread?",
                    "Any injury concerns for either team?"
                ],
                "context_updates": {
                    "teams": ["Lakers", "Pistons"],
                    "sport": "basketball",
                    "game_date": "tonight",
                    "bet_type": "spread"
                },
                "confidence_score": 0.85
            }
        } 