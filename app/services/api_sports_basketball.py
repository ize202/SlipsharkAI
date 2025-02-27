"""
NBA API Service using RapidAPI
This module provides a clean interface to the NBA API endpoints from RapidAPI.
"""

from typing import Optional, Dict, Any, List, TypeVar, Generic
from datetime import datetime, UTC
import os
import logging
import httpx
import json
import asyncio
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
from dataclasses import dataclass
from langfuse.decorators import observe

# Configure logging
logger = logging.getLogger(__name__)

# Type Variables
T = TypeVar('T')

class NBAApiError(Exception):
    """Base exception for NBA API errors"""
    pass

class RateLimitError(NBAApiError):
    """Raised when API rate limit is exceeded"""
    pass

class AuthenticationError(NBAApiError):
    """Raised when API authentication fails"""
    pass

@dataclass
class NBAApiConfig:
    """Configuration for NBA API"""
    api_key: str
    base_url: str = "https://v2.nba.api-sports.io"
    host: str = "v2.nba.api-sports.io"
    
    @classmethod
    def from_env(cls) -> 'NBAApiConfig':
        """Create config from environment variables"""
        api_key = os.getenv("API_SPORTS_KEY")
        if not api_key:
            raise ValueError("API_SPORTS_KEY environment variable is not set")
        return cls(api_key=api_key)

class GameStatus(str, Enum):
    """Game status enumeration"""
    NOT_STARTED = "1"
    LIVE = "2"
    FINISHED = "3"
    POSTPONED = "4"
    DELAYED = "5"
    CANCELLED = "6"

class CachePolicy(BaseModel):
    """Cache policy configuration"""
    ttl: int  # Time to live in seconds
    stale_while_revalidate: bool = False

class CacheConfig:
    """Cache configuration for different endpoints"""
    TEAMS = CachePolicy(ttl=86400)  # 24 hours
    GAMES = CachePolicy(ttl=300)     # 5 minutes
    STANDINGS = CachePolicy(ttl=3600) # 1 hour
    STATISTICS = CachePolicy(ttl=3600) # 1 hour

class APIResponse(BaseModel, Generic[T]):
    """Generic API response model"""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    get: str
    parameters: Dict[str, Any]
    errors: List[str]
    results: int
    response: T

class Team(BaseModel):
    """Team model"""
    id: int
    name: str
    nickname: str
    code: str
    city: Optional[str] = None
    logo: Optional[str] = None
    allStar: Optional[bool] = None
    nbaFranchise: Optional[bool] = None
    leagues: Optional[Dict[str, Any]] = None

class Game(BaseModel):
    """Game model"""
    id: int
    league: str
    season: int
    date: Dict[str, Any]
    stage: int
    status: Dict[str, Any]
    periods: Dict[str, Any]
    arena: Dict[str, Any]
    teams: Dict[str, Any]
    scores: Dict[str, Any]
    officials: List[str]
    timesTied: Optional[int] = None
    leadChanges: Optional[int] = None
    nugget: Optional[str] = None

class TeamStatistics(BaseModel):
    """Team statistics model"""
    games: int
    fastBreakPoints: int
    pointsInPaint: int
    biggestLead: int
    secondChancePoints: int
    pointsOffTurnovers: int
    longestRun: int
    points: int
    fgm: int
    fga: int
    fgp: str
    ftm: int
    fta: int
    ftp: str
    tpm: int
    tpa: int
    tpp: str
    offReb: int
    defReb: int
    totReb: int
    assists: int
    pFouls: int
    steals: int
    turnovers: int
    blocks: int
    plusMinus: int

class NBAApiClient:
    """Low-level NBA API client"""
    
    def __init__(self, config: NBAApiConfig):
        """Initialize the NBA API client"""
        self.config = config
        self.headers = {
            'x-apisports-key': config.api_key,
            'x-apisports-host': config.host
        }
        self.client: Optional[httpx.AsyncClient] = None
        
    async def __aenter__(self) -> 'NBAApiClient':
        """Async context manager entry"""
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            headers=self.headers,
            timeout=30.0
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
            self.client = None

    async def _make_request(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the NBA API with retries and error handling"""
        if not self.client:
            raise RuntimeError("Client not initialized. Use async with context manager.")
            
        params = params or {}
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Making request to {endpoint} with params: {params}")
                response = await self.client.get(endpoint, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                # Check rate limits
                remaining = response.headers.get('x-ratelimit-remaining')
                if remaining and int(remaining) < 10:
                    logger.warning(f"Rate limit running low: {remaining} requests remaining")
                
                # Check for API errors
                if data.get("errors") and data["errors"]:
                    error_msg = json.dumps(data["errors"])
                    if any("rate limit" in str(err).lower() for err in data["errors"]):
                        raise RateLimitError(f"Rate limit exceeded: {error_msg}")
                    raise NBAApiError(f"API returned errors: {error_msg}")
                
                return data
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise AuthenticationError("Invalid API key")
                if e.response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"Rate limit hit, waiting {wait_time}s before retry")
                        await asyncio.sleep(wait_time)
                        continue
                    raise RateLimitError("Rate limit exceeded after retries")
                raise NBAApiError(f"HTTP error {e.response.status_code}: {str(e)}")
                
            except httpx.RequestError as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Request error, waiting {wait_time}s before retry")
                    await asyncio.sleep(wait_time)
                    continue
                raise NBAApiError(f"Request failed after {max_retries} retries: {str(e)}")

class NBATeamService:
    """Service for NBA team operations"""
    
    def __init__(self, client: NBAApiClient):
        self.client = client
        self._team_cache: Dict[str, Team] = {}
        
    async def list_teams(self, league: str = "standard") -> List[Team]:
        """Get list of NBA teams"""
        data = await self.client._make_request("teams", {"league": league})
        return [Team(**team) for team in data.get("response", [])]
        
    async def get_team_statistics(
        self, 
        team_id: int, 
        season: str = "2023"
    ) -> TeamStatistics:
        """Get team statistics"""
        data = await self.client._make_request(
            "teams/statistics",
            {"id": team_id, "season": season}
        )
        return TeamStatistics(**data["response"])

class NBAGameService:
    """Service for NBA game operations"""
    
    def __init__(self, client: NBAApiClient):
        self.client = client
        
    async def list_games(
        self,
        season: str = "2023",
        league: str = "standard",
        team_id: Optional[int] = None,
        date: Optional[str] = None,
        live: bool = False
    ) -> List[Game]:
        """Get list of games with optional filters"""
        params = {
            "season": season,
            "league": league
        }
        if team_id:
            params["team"] = team_id
        if date:
            params["date"] = date
        if live:
            params["live"] = "all"
            
        data = await self.client._make_request("games", params)
        return [Game(**game) for game in data.get("response", [])]
        
    async def get_game_statistics(self, game_id: int) -> Dict[str, Any]:
        """Get statistics for a specific game"""
        data = await self.client._make_request(
            "games/statistics",
            {"id": game_id}
        )
        return data.get("response", {})

class NBAService:
    """Main NBA service facade"""
    
    def __init__(self):
        self.config = NBAApiConfig.from_env()
        self.client = NBAApiClient(self.config)
        self.teams = NBATeamService(self.client)
        self.games = NBAGameService(self.client)
        
    async def __aenter__(self) -> 'NBAService':
        """Async context manager entry"""
        await self.client.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)
