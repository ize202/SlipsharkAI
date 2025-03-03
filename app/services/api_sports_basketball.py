"""
NBA API Service using API Sports
This module provides a clean interface to the NBA API endpoints from API Sports.
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
from ..utils.cache import redis_cache
import hashlib

# NBA Team IDs from API Sports dashboard
NBA_TEAM_IDS = {
    # Eastern Conference
    "boston celtics": 2,
    "brooklyn nets": 4,
    "new york knicks": 24,
    "philadelphia 76ers": 27,
    "toronto raptors": 38,
    "chicago bulls": 6,
    "cleveland cavaliers": 7,
    "detroit pistons": 10,
    "indiana pacers": 15,
    "milwaukee bucks": 21,
    "atlanta hawks": 1,
    "charlotte hornets": 5,
    "miami heat": 20,
    "orlando magic": 26,
    "washington wizards": 41,
    
    # Western Conference
    "denver nuggets": 9,
    "minnesota timberwolves": 22,
    "oklahoma city thunder": 25,
    "portland trail blazers": 29,
    "utah jazz": 40,
    "golden state warriors": 11,
    "la clippers": 16,
    "los angeles clippers": 16,
    "los angeles lakers": 17,
    "la lakers": 17,
    "phoenix suns": 28,
    "sacramento kings": 30,
    "dallas mavericks": 8,
    "houston rockets": 14,
    "memphis grizzlies": 19,
    "new orleans pelicans": 23,
    "san antonio spurs": 31,
    
    # Common Aliases
    "sixers": 27,
    "lakers": 17,
    "clippers": 16,
    "warriors": 11,
    "celtics": 2,
    "nets": 3,
    "knicks": 24,
    "raptors": 38,
    "bulls": 6,
    "cavs": 7,
    "pistons": 10,
    "pacers": 15,
    "bucks": 21,
    "hawks": 1,
    "hornets": 5,
    "heat": 20,
    "magic": 26,
    "wizards": 41,
    "nuggets": 9,
    "wolves": 22,
    "timberwolves": 22,
    "thunder": 25,
    "blazers": 29,
    "jazz": 40,
    "suns": 28,
    "kings": 30,
    "mavs": 8,
    "mavericks": 8,
    "rockets": 14,
    "grizzlies": 19,
    "pelicans": 23,
    "spurs": 31
}

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
    """Team statistics model matching API Sports NBA documentation"""
    fastBreakPoints: Optional[int] = 0
    pointsInPaint: Optional[int] = 0
    biggestLead: Optional[int] = 0
    secondChancePoints: Optional[int] = 0
    pointsOffTurnovers: Optional[int] = 0
    longestRun: Optional[int] = 0
    points: Optional[int] = 0
    fgm: Optional[int] = 0
    fga: Optional[int] = 0
    fgp: Optional[str] = "0"
    ftm: Optional[int] = 0
    fta: Optional[int] = 0
    ftp: Optional[str] = "0"
    tpm: Optional[int] = 0
    tpa: Optional[int] = 0
    tpp: Optional[str] = "0"
    offReb: Optional[int] = 0
    defReb: Optional[int] = 0
    totReb: Optional[int] = 0
    assists: Optional[int] = 0
    pFouls: Optional[int] = 0
    steals: Optional[int] = 0
    turnovers: Optional[int] = 0
    blocks: Optional[int] = 0
    plusMinus: Optional[str] = "0"
    min: Optional[str] = "0"

    def __init__(self, **data):
        # Convert plusMinus to string if it's an integer
        if 'plusMinus' in data and isinstance(data['plusMinus'], (int, float)):
            data['plusMinus'] = str(data['plusMinus'])
        super().__init__(**data)

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

def normalize_cache_key(params: Dict[str, Any]) -> str:
    """
    Normalize parameters for cache key generation.
    - Sorts dictionary keys
    - Converts values to strings
    - Handles nested dictionaries
    - Normalizes case for string values
    """
    def normalize_value(value: Any) -> str:
        if isinstance(value, dict):
            return normalize_cache_key(value)
        elif isinstance(value, (list, tuple, set)):
            return ','.join(sorted(str(x).lower() for x in value))
        elif isinstance(value, str):
            return value.lower()
        return str(value)

    if not params:
        return ""
    
    normalized = {
        str(k).lower(): normalize_value(v)
        for k, v in sorted(params.items())
        if v is not None
    }
    
    return hashlib.md5(json.dumps(normalized, sort_keys=True).encode()).hexdigest()

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

    @redis_cache(ttl=300, prefix="nba_api")  # 5 minute default cache
    async def _make_request(
        self, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the NBA API with retries and error handling"""
        if not self.client:
            raise RuntimeError("Client not initialized. Use async with context manager.")
            
        params = params or {}
        
        # Generate normalized cache key
        cache_key = normalize_cache_key({
            "endpoint": endpoint,
            "params": params
        })
        
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                logger.debug(f"Making request to {endpoint} with params: {params} (cache_key: {cache_key})")
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
                
                # Add cache key to response for debugging
                data["_cache_key"] = cache_key
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

    @redis_cache(ttl=3600)  # 1 hour cache
    async def get_standings(
        self,
        league: str = "standard",
        season: str = "2023",
        team_id: Optional[int] = None,
        conference: Optional[str] = None,
        division: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get standings with optional filters
        
        Args:
            league: League name (default: "standard")
            season: Season year (default: "2023")
            team_id: Optional team ID to filter by
            conference: Optional conference to filter by
            division: Optional division to filter by
            
        Returns:
            Dictionary containing standings data
        """
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
            
        return await self._make_request("standings", params)

    @redis_cache(ttl=300, prefix="nba_games")  # 5 minute cache for games
    async def list_games(
        self,
        id: Optional[int] = None,
        date: Optional[str] = None,  # YYYY-MM-DD format
        league: str = "standard",
        season: Optional[str] = None,
        team: Optional[int] = None,
        live: bool = False,
        h2h: Optional[str] = None  # Format: "1-4" for team IDs
    ) -> List[Game]:
        """
        Get list of games with filters as per API Sports NBA documentation.
        
        Args:
            id: The id of the game
            date: Date in YYYY-MM-DD format
            league: League name (default: "standard")
            season: Season year (YYYY format)
            team: Team ID to filter by
            live: Whether to get live games only
            h2h: Head to head games between two teams (format: "teamId1-teamId2")
            
        Returns:
            List of Game objects
        """
        params = {"league": league}
        
        if id:
            params["id"] = id
        if date:
            params["date"] = date
        if season:
            params["season"] = season
        if team:
            params["team"] = team
        if live:
            params["live"] = "all"
        if h2h:
            params["h2h"] = h2h
            
        data = await self._make_request("games", params)
        return [Game(**game) for game in data.get("response", [])]

class NBATeamService:
    """Service for NBA team operations"""
    
    def __init__(self, client: NBAApiClient):
        self.client = client
        self._teams_by_id: Dict[int, Team] = {}  # Cache teams by ID
        
    @redis_cache(ttl=86400, prefix="nba_teams")  # 24 hour cache for teams
    async def list_teams(
        self,
        league: str = "standard",
        conference: Optional[str] = None,
        division: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Team]:
        """Get list of NBA teams"""
        # If we have a search term and it's in our static mapping, optimize the lookup
        if search and len(search) >= 3:
            team_id = NBA_TEAM_IDS.get(search.lower())
            if team_id:
                # Check if we have this team cached
                if team_id in self._teams_by_id:
                    return [self._teams_by_id[team_id]]
                # Otherwise fetch all teams but return only the one we want
                teams = await self._fetch_teams({"league": league})
                return [t for t in teams if t.id == team_id]
        
        # Standard API lookup for other cases
        params = {"league": league}
        if conference:
            params["conference"] = conference
        if division:
            params["division"] = division
        if search and len(search) >= 3:
            params["search"] = search
            
        return await self._fetch_teams(params)
    
    async def _fetch_teams(self, params: Dict[str, Any]) -> List[Team]:
        """Fetch teams from API and update cache"""
        data = await self.client._make_request("teams", params)
        teams = [Team(**team) for team in data.get("response", [])]
        
        # Update our ID cache
        for team in teams:
            self._teams_by_id[team.id] = team
            
        return teams
        
    @redis_cache(ttl=3600, prefix="nba_team_stats")  # 1 hour cache for team stats
    async def get_team_statistics(
        self, 
        team_id: int, 
        season: str = "2023"
    ) -> TeamStatistics:
        """Get team statistics"""
        # Validate team_id is valid
        if team_id not in set(NBA_TEAM_IDS.values()):
            raise NBAApiError(f"Invalid team ID: {team_id}")
            
        data = await self.client._make_request(
            "teams/statistics",
            {"id": team_id, "season": season}
        )
        # API returns a list, take the first item
        if not data["response"]:
            raise NBAApiError(f"No statistics found for team {team_id}")
            
        try:
            stats = data["response"][0]
            # Extract total values from dictionary format
            processed_stats = {}
            for key, value in stats.items():
                if isinstance(value, dict) and "total" in value:
                    processed_stats[key] = value["total"]
                else:
                    processed_stats[key] = value
                    
            return TeamStatistics(**processed_stats)
        except Exception as e:
            logger.error(f"Error parsing team statistics: {str(e)}")
            raise NBAApiError(f"Failed to parse statistics for team {team_id}: {str(e)}")

class NBAGameService:
    """Service for NBA game operations"""
    
    def __init__(self, client: NBAApiClient):
        self.client = client
        
    @redis_cache(ttl=300, prefix="nba_games")  # 5 minute cache for games
    async def list_games(
        self,
        season: Optional[str] = None,
        league: str = "standard",
        team_id: Optional[int] = None,
        date: Optional[str] = None,
        live: bool = False,
        game_id: Optional[int] = None,
        h2h: Optional[str] = None
    ) -> List[Game]:
        """Get list of games with optional filters"""
        params = {}
        if season:
            params["season"] = season
        if league:
            params["league"] = league
        if team_id:
            params["team"] = team_id
        if date:
            params["date"] = date
        if live:
            params["live"] = "all"
        if game_id:
            params["id"] = game_id
        if h2h:
            params["h2h"] = h2h
            
        data = await self.client._make_request("games", params)
        return [Game(**game) for game in data.get("response", [])]
        
    @redis_cache(ttl=3600, prefix="nba_game_stats")  # 1 hour cache for game stats
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
        self._current_season = None  # Cache current season
        
    @redis_cache(ttl=86400, prefix="nba_seasons")  # 24 hour cache
    async def list_seasons(self) -> List[int]:
        """Get list of available seasons"""
        data = await self.client._make_request("seasons")
        seasons = sorted(data.get("response", []), reverse=True)  # Sort descending
        if not seasons:
            # If API fails, default to known supported seasons
            seasons = list(range(2015, 2025))  # API supports 2015-2024
        return seasons

    async def get_current_season(self, client_metadata: Optional[Dict[str, Any]] = None) -> Optional[int]:
        """
        Get the current NBA season based on client metadata timestamp or API data.
        
        Args:
            client_metadata: Optional client metadata containing timestamp
            
        Returns:
            Current season as integer
        """
        try:
            # If we have client metadata with timestamp, use that
            if client_metadata and client_metadata.get("timestamp"):
                timestamp = datetime.fromisoformat(client_metadata["timestamp"].replace("Z", "+00:00"))
                # NBA seasons span calendar years (e.g. 2023-24 season is "2023")
                if timestamp.month <= 6:  # Before July is previous year's season
                    return timestamp.year - 1
                return timestamp.year
                
            # Otherwise use cached season or fetch from API
            if self._current_season is not None:
                return self._current_season
                
            seasons = await self.list_seasons()
            if not seasons:
                logger.error("No seasons returned from API")
                return None
                
            # Get most recent season (first since we sort descending)
            self._current_season = seasons[0]
            return self._current_season
            
        except Exception as e:
            logger.error(f"Error getting current season: {str(e)}")
            return None

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
        
    @redis_cache(ttl=86400, prefix="nba_players")  # 24 hour cache for player info
    async def get_players(
        self,
        season: Optional[str] = None,
        team: Optional[int] = None,
        name: Optional[str] = None,
        country: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Player]:
        """Get list of players with optional filters"""
        params = {}
        if season:
            params["season"] = season
        if team:
            params["team"] = team
        if name:
            params["name"] = name
        if country:
            params["country"] = country
        if search and len(search) >= 3:
            params["search"] = search
            
        data = await self.client._make_request("players", params)
        return [Player(**player) for player in data.get("response", [])]
        
    @redis_cache(ttl=3600, prefix="nba_player_stats")  # 1 hour cache for player stats
    async def get_player_statistics(
        self,
        player_id: Optional[int] = None,
        game_id: Optional[int] = None,
        team: Optional[int] = None,
        season: Optional[str] = None
    ) -> List[PlayerStatistics]:
        """Get player statistics with optional filters. At least one parameter is required."""
        # API requires at least one parameter
        if not any([player_id, game_id, team, season]):
            raise ValueError("At least one parameter (player_id, game_id, team, or season) is required")
            
        params = {}
        if player_id:
            params["id"] = player_id
        if game_id:
            params["game"] = game_id
        if team:
            params["team"] = team
        if season:
            params["season"] = season
            
        try:
            data = await self.client._make_request("players/statistics", params)
            if not data.get("response"):
                logger.warning(f"No statistics found for parameters: id={player_id}, game={game_id}, team={team}, season={season}")
                return []
                
            return [PlayerStatistics(**stats) for stats in data.get("response", [])]
        except Exception as e:
            logger.error(f"Error getting player statistics: {str(e)}")
            raise NBAApiError(f"Failed to get player statistics: {str(e)}")

class NBAStandingService:
    """Service for NBA standings operations"""
    
    def __init__(self, client: NBAApiClient):
        self.client = client
        
    @redis_cache(ttl=3600, prefix="nba_standings")  # 1 hour cache for standings
    async def get_standings(
        self,
        league: str = "standard",
        season: str = "2023",
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

   