from typing import Optional, Dict, Any, List
import os
import logging
import httpx
from datetime import datetime, timedelta, UTC
from pydantic import BaseModel, Field
from langfuse.decorators import observe

# Set up logging
logger = logging.getLogger(__name__)

class NBATeamStats(BaseModel):
    """NBA team statistics from Goalserve"""
    team_id: str
    name: str
    wins: int
    losses: int
    win_percentage: float
    points_per_game: float
    points_allowed: float
    last_ten: str  # Format: "W-L" (e.g., "7-3")
    streak: str  # Format: "W4" or "L2"
    home_record: str  # Format: "W-L"
    away_record: str  # Format: "W-L"
    conference_rank: int

class NBAPlayerStats(BaseModel):
    """NBA player statistics from Goalserve"""
    player_id: str
    name: str
    position: str
    status: str  # Active, Injured, etc.
    points_per_game: float
    rebounds_per_game: float
    assists_per_game: float
    minutes_per_game: float
    injury_status: Optional[str] = None
    injury_details: Optional[str] = None

class NBAGameOdds(BaseModel):
    """NBA game odds from Goalserve"""
    game_id: str
    start_time: datetime
    home_team: str
    away_team: str
    spread: float
    total: float
    home_moneyline: int
    away_moneyline: int
    last_updated: datetime

class NBASchedule(BaseModel):
    """NBA game schedule from Goalserve"""
    game_id: str
    start_time: datetime
    home_team: str
    away_team: str
    venue: str
    status: str  # scheduled, in_progress, final
    score_home: Optional[int] = None
    score_away: Optional[int] = None

class NBAHeadToHead(BaseModel):
    """Head-to-head comparison from Goalserve"""
    total_games: int
    home_team_wins: int
    away_team_wins: int
    last_five: List[Dict[str, Any]]  # Last 5 meetings
    avg_points_home: float
    avg_points_away: float

class NBAStandings(BaseModel):
    """NBA standings from Goalserve"""
    conference: str
    rank: int
    team_id: str
    team_name: str
    wins: int
    losses: int
    win_percentage: float
    games_back: float
    last_ten: str
    streak: str
    points_for: float
    points_against: float

class NBALiveScore(BaseModel):
    """NBA live score from Goalserve"""
    game_id: str
    status: str  # pregame, live, final
    current_period: Optional[str] = None
    time_remaining: Optional[str] = None
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    last_play: Optional[str] = None
    scoring_leaders: Optional[Dict[str, Any]] = None
    updated_at: datetime

class GoalserveNBAService:
    """Service for interacting with Goalserve NBA API"""
    
    def __init__(self):
        self.api_key = os.getenv("GOALSERVE_API_KEY")
        if not self.api_key:
            raise ValueError("GOALSERVE_API_KEY environment variable is not set")
        
        self.base_url = "https://www.goalserve.com/getfeed"
        self.sport = "basketball"
        self.league = "nba"
        
        # Initialize async client
        self.client = httpx.AsyncClient(timeout=30.0)  # 30 second timeout
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    @observe(name="goalserve_get_upcoming_games")
    async def get_upcoming_games(self, team_name: str) -> List[NBASchedule]:
        """Get upcoming games schedule for an NBA team"""
        try:
            params = {
                "sport": self.sport,
                "league": self.league,
                "key": self.api_key,
                "team": team_name,
                "schedule": "true"
            }
            
            async with self.client as client:
                response = await client.get(f"{self.base_url}/schedule", params=params)
                response.raise_for_status()
                data = response.json()
                
                return [NBASchedule(**game) for game in data.get("games", [])]
                
        except Exception as e:
            logger.error(f"Error getting upcoming games: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_team_stats")
    async def get_team_stats(self, team_name: str) -> NBATeamStats:
        """Get current season statistics for an NBA team"""
        try:
            params = {
                "sport": self.sport,
                "league": self.league,
                "key": self.api_key,
                "team": team_name,
                "stats": "true"
            }
            
            async with self.client as client:
                response = await client.get(f"{self.base_url}/stats", params=params)
                response.raise_for_status()
                data = response.json()
                
                return NBATeamStats(**data.get("team_stats", {}))
                
        except Exception as e:
            logger.error(f"Error getting team stats: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_player_stats")
    async def get_player_stats(self, team_name: str) -> List[NBAPlayerStats]:
        """Get current season statistics for all players on an NBA team"""
        try:
            params = {
                "sport": self.sport,
                "league": self.league,
                "key": self.api_key,
                "team": team_name,
                "players": "true"
            }
            
            async with self.client as client:
                response = await client.get(f"{self.base_url}/players", params=params)
                response.raise_for_status()
                data = response.json()
                
                # TODO: Parse the response and map to list of NBAPlayerStats models
                # This will need to be adjusted based on actual Goalserve API response format
                return [NBAPlayerStats(**player_data) for player_data in data["players"]]
                
        except Exception as e:
            logger.error(f"Error getting player stats: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_game_odds")
    async def get_game_odds(self, team_name: str) -> List[NBAGameOdds]:
        """Get upcoming game odds for an NBA team"""
        try:
            params = {
                "sport": self.sport,
                "league": self.league,
                "key": self.api_key,
                "team": team_name,
                "odds": "true"
            }
            
            async with self.client as client:
                response = await client.get(f"{self.base_url}/odds", params=params)
                response.raise_for_status()
                data = response.json()
                
                # TODO: Parse the response and map to list of NBAGameOdds models
                # This will need to be adjusted based on actual Goalserve API response format
                return [NBAGameOdds(**game_data) for game_data in data["games"]]
                
        except Exception as e:
            logger.error(f"Error getting game odds: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_injuries")
    async def get_injuries(self, team_name: str) -> List[NBAPlayerStats]:
        """Get current injuries for an NBA team"""
        try:
            params = {
                "sport": self.sport,
                "league": self.league,
                "key": self.api_key,
                "team": team_name,
                "injuries": "true"
            }
            
            async with self.client as client:
                response = await client.get(f"{self.base_url}/injuries", params=params)
                response.raise_for_status()
                data = response.json()
                
                return [NBAPlayerStats(**player) for player in data.get("injuries", [])]
                
        except Exception as e:
            logger.error(f"Error getting injuries: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_odds_comparison")
    async def get_odds_comparison(self, game_id: str) -> Dict[str, Any]:
        """Get odds comparison from various bookmakers"""
        try:
            params = {
                "sport": self.sport,
                "league": self.league,
                "key": self.api_key,
                "game": game_id,
                "odds": "true"
            }
            
            async with self.client as client:
                response = await client.get(f"{self.base_url}/odds", params=params)
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error(f"Error getting odds comparison: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_head_to_head")
    async def get_head_to_head(self, team1: str, team2: str) -> NBAHeadToHead:
        """Get head-to-head comparison between two teams"""
        try:
            params = {
                "sport": self.sport,
                "league": self.league,
                "key": self.api_key,
                "team1": team1,
                "team2": team2,
                "h2h": "true"
            }
            
            async with self.client as client:
                response = await client.get(f"{self.base_url}/h2h", params=params)
                response.raise_for_status()
                data = response.json()
                
                return NBAHeadToHead(**data.get("h2h", {}))
                
        except Exception as e:
            logger.error(f"Error getting head-to-head stats: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_standings")
    async def get_standings(self, conference: Optional[str] = None) -> List[NBAStandings]:
        """Get current NBA standings, optionally filtered by conference"""
        try:
            params = {
                "sport": self.sport,
                "league": self.league,
                "key": self.api_key,
                "standings": "true"
            }
            if conference:
                params["conference"] = conference
            
            async with self.client as client:
                response = await client.get(f"{self.base_url}/standings", params=params)
                response.raise_for_status()
                data = response.json()
                
                return [NBAStandings(**team) for team in data.get("standings", [])]
                
        except Exception as e:
            logger.error(f"Error getting standings: {str(e)}", exc_info=True)
            raise

    @observe(name="goalserve_get_live_scores")
    async def get_live_scores(self, game_ids: Optional[List[str]] = None) -> List[NBALiveScore]:
        """Get live scores for NBA games, optionally filtered by game IDs"""
        try:
            params = {
                "sport": self.sport,
                "league": self.league,
                "key": self.api_key,
                "live": "true"
            }
            if game_ids:
                params["games"] = ",".join(game_ids)
            
            async with self.client as client:
                response = await client.get(f"{self.base_url}/scores", params=params)
                response.raise_for_status()
                data = response.json()
                
                scores = []
                for game in data.get("games", []):
                    game["updated_at"] = datetime.now(UTC)  # Add timestamp
                    scores.append(NBALiveScore(**game))
                return scores
                
        except Exception as e:
            logger.error(f"Error getting live scores: {str(e)}", exc_info=True)
            raise 