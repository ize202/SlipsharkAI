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

class PlayerBirth(BaseModel):
    """Player birth information"""
    date: Optional[str] = None
    country: Optional[str] = None

class PlayerNBA(BaseModel):
    """Player NBA information"""
    start: int
    pro: int

class PlayerHeight(BaseModel):
    """Player height information"""
    feets: Optional[str] = None
    inches: Optional[str] = None
    meters: Optional[str] = None

class PlayerWeight(BaseModel):
    """Player weight information"""
    pounds: Optional[str] = None
    kilograms: Optional[str] = None

class PlayerLeague(BaseModel):
    """Player league information"""
    standard: Optional[dict] = None

class Player(BaseModel):
    """Player information"""
    id: int
    firstname: str
    lastname: str
    birth: PlayerBirth
    nba: PlayerNBA
    height: PlayerHeight
    weight: PlayerWeight
    college: Optional[str] = None
    affiliation: Optional[str] = None
    leagues: PlayerLeague

class PlayerStatistics(BaseModel):
    """Player statistics"""
    player: Dict[str, Any]  # Raw player data
    team: Dict[str, Any]  # Raw team data
    points: Optional[int] = None
    pos: Optional[str] = None
    min: Optional[str] = None
    fgm: Optional[int] = None
    fga: Optional[int] = None
    fgp: Optional[str] = None
    ftm: Optional[int] = None
    fta: Optional[int] = None
    ftp: Optional[str] = None
    tpm: Optional[int] = None
    tpa: Optional[int] = None
    tpp: Optional[str] = None
    offReb: Optional[int] = None
    defReb: Optional[int] = None
    totReb: Optional[int] = None
    assists: Optional[int] = None
    pFouls: Optional[int] = None
    steals: Optional[int] = None
    turnovers: Optional[int] = None
    blocks: Optional[int] = None
    plusMinus: Optional[str] = None
    games_played: Optional[int] = None
    games_started: Optional[int] = None

class StandingConference(BaseModel):
    """Standing conference information"""
    name: str
    rank: int
    win: int
    loss: int
    gamesBehind: Optional[str] = None

class StandingDivision(BaseModel):
    """Standing division information"""
    name: str
    rank: int
    win: int
    loss: int
    gamesBehind: Optional[str] = None

class StandingRecord(BaseModel):
    """Standing record information"""
    home: int
    away: int
    total: int
    percentage: str
    lastTen: Optional[int] = None

class Standing(BaseModel):
    """Standing information"""
    league: str
    season: int
    team: Team
    conference: StandingConference
    division: StandingDivision
    win: StandingRecord
    loss: StandingRecord
    gamesBehind: Optional[str] = None
    streak: int
    winStreak: bool
    tieBreakerPoints: Optional[float] = None

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
        # API returns a list, take the first item
        if not data["response"]:
            raise NBAApiError(f"No statistics found for team {team_id}")
        return TeamStatistics(**data["response"][0])

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

class NBASeasonService:
    """Service for NBA season operations"""
    
    def __init__(self, client: NBAApiClient):
        self.client = client
        
    async def list_seasons(self) -> List[int]:
        """Get list of available seasons"""
        data = await self.client._make_request("seasons")
        return data.get("response", [])

class NBALeagueService:
    """Service for NBA league operations"""
    
    def __init__(self, client: NBAApiClient):
        self.client = client
        
    async def list_leagues(self) -> List[str]:
        """Get list of available leagues"""
        data = await self.client._make_request("leagues")
        return data.get("response", [])

class NBAPlayerService:
    """Service for NBA player operations"""
    
    def __init__(self, client: NBAApiClient):
        self.client = client
        
    async def get_players(
        self,
        season: str,
        team_id: Optional[int] = None,
        name: Optional[str] = None,
        country: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Player]:
        """Get list of players with optional filters"""
        params = {"season": season}
        if team_id:
            params["team"] = team_id
        if name:
            params["name"] = name
        if country:
            params["country"] = country
        if search and len(search) >= 3:
            params["search"] = search
            
        data = await self.client._make_request("players", params)
        return [Player(**player) for player in data.get("response", [])]
        
    async def get_player_statistics(
        self,
        player_id: Optional[int] = None,
        game_id: Optional[int] = None,
        team_id: Optional[int] = None,
        season: Optional[str] = None
    ) -> List[PlayerStatistics]:
        """Get player statistics with optional filters"""
        # API requires at least one parameter
        if not any([player_id, game_id, team_id, season]):
            raise ValueError("At least one parameter (player_id, game_id, team_id, or season) is required")
            
        params = {}
        if player_id:
            params["id"] = player_id
        if game_id:
            params["game"] = game_id
        if team_id:
            params["team"] = team_id
        if season:
            params["season"] = season
            
        try:
            data = await self.client._make_request("players/statistics", params)
            if not data.get("response"):
                logger.warning(f"No statistics found for player (id={player_id}, game={game_id}, team={team_id}, season={season})")
                return []
                
            return [PlayerStatistics(**stats) for stats in data.get("response", [])]
        except Exception as e:
            logger.error(f"Error getting player statistics: {str(e)}")
            raise NBAApiError(f"Failed to get player statistics: {str(e)}")

class NBAStandingService:
    """Service for NBA standings operations"""
    
    def __init__(self, client: NBAApiClient):
        self.client = client
        
    async def get_standings(
        self,
        league: str,
        season: str,
        team_id: Optional[int] = None,
        conference: Optional[str] = None,
        division: Optional[str] = None
    ) -> List[Standing]:
        """Get standings with optional filters"""
        params = {
            "league": league,
            "season": season
        }
        if team_id:
            params["team"] = team_id
        if conference:
            params["conference"] = conference.lower()
        if division:
            params["division"] = division.lower()
            
        data = await self.client._make_request("standings", params)
        return [Standing(**standing) for standing in data.get("response", [])]

class NBAService:
    """NBA API service"""
    def __init__(self, config: NBAApiConfig):
        """Initialize the NBA API service"""
        self.client = NBAApiClient(config)
        self.teams = NBATeamService(self.client)
        self.games = NBAGameService(self.client)
        self.seasons = NBASeasonService(self.client)
        self.leagues = NBALeagueService(self.client)
        self.players = NBAPlayerService(self.client)
        self.standings = NBAStandingService(self.client)
        
    async def __aenter__(self) -> 'NBAService':
        """Async context manager entry"""
        await self.client.__aenter__()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)

   