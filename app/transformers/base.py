from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from app.config import get_logger
from app.utils.cache import redis_cache

logger = get_logger(__name__)

class CommonTeamInfo(BaseModel):
    """Common team information across sports"""
    id: int
    name: str
    code: str
    logo: Optional[str] = None
    venue: Optional[Dict[str, str]] = None

class CommonGameInfo(BaseModel):
    """Common game information across sports"""
    id: int
    date: datetime
    status: str
    venue: Optional[str] = None
    teams: Dict[str, CommonTeamInfo]
    score: Dict[str, Any]
    statistics: Optional[Dict[str, Any]] = None

class CommonPlayerInfo(BaseModel):
    """Common player information across sports"""
    id: int
    name: str
    position: Optional[str] = None
    team_id: Optional[int] = None
    jersey: Optional[str] = None
    bio: Optional[Dict[str, Any]] = None

class TransformedSportData(BaseModel):
    """Container for transformed sport data"""
    sport_type: str
    team_data: Optional[Dict[str, Any]] = None
    game_data: Optional[List[Dict[str, Any]]] = None
    player_data: Optional[Dict[str, Any]] = None
    league_data: Optional[Dict[str, Any]] = None
    confidence_score: float = Field(default=0.9, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SportDataTransformer(ABC):
    """Base class for sport-specific data transformers"""
    
    def __init__(self):
        self.cache_ttls = {
            "team_basic": timedelta(days=1),
            "team_stats": timedelta(hours=6),
            "game_data": timedelta(minutes=5),
            "player_data": timedelta(hours=12)
        }
    
    @abstractmethod
    async def transform_team_data(
        self, 
        raw_data: Dict[str, Any],
        required_data: List[str]
    ) -> Dict[str, Any]:
        """Transform raw team data to common format"""
        pass
    
    @abstractmethod
    async def transform_game_data(
        self,
        raw_data: Dict[str, Any],
        required_data: List[str]
    ) -> Dict[str, Any]:
        """Transform raw game data to common format"""
        pass
    
    @abstractmethod
    async def transform_player_data(
        self,
        raw_data: Dict[str, Any],
        required_data: List[str]
    ) -> Dict[str, Any]:
        """Transform player data to common format"""
        pass

    @redis_cache(ttl=300, prefix="sport_data")  # 5 minute cache for filtered data
    async def filter_data_for_llm(
        self,
        data: TransformedSportData,
        required_data: List[str]
    ) -> Dict[str, Any]:
        """Filter transformed data based on required fields"""
        filtered_data = {"sport_type": data.sport_type}
        
        if "team_stats" in required_data and data.team_data:
            filtered_data["team_data"] = {
                k: v for k, v in data.team_data.items()
                if k in ["basic_info", "season_stats", "league_info"]
            }
        
        if "recent_games" in required_data and data.game_data:
            filtered_data["game_data"] = data.game_data[:5]  # Last 5 games
            
        if "player_stats" in required_data and data.player_data:
            filtered_data["player_data"] = {
                k: v for k, v in data.player_data.items()
                if k in ["basic_info", "season_stats", "recent_performance"]
            }
            
        return filtered_data

    @abstractmethod
    async def validate_data(self, data: TransformedSportData) -> bool:
        """Validate transformed data for completeness and correctness"""
        pass 