from typing import Optional, Dict, Any, List
import os
import logging
import httpx
import gzip
from datetime import datetime, timedelta, UTC
from pydantic import BaseModel, Field
from langfuse.decorators import observe
import json
import asyncio

# Set up logging
logger = logging.getLogger(__name__)

# Added helper function to parse ISO date strings (handles trailing 'Z')
def parse_date(date_str: str) -> datetime:
    """Parse ISO formatted date string, handling trailing 'Z' if present."""
    if date_str and date_str.endswith('Z'):
        date_str = date_str[:-1]
    return datetime.fromisoformat(date_str) if date_str else None

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
    home_team: str
    away_team: str
    home_team_odds: float
    away_team_odds: float
    spread: float
    total: float

class NBASchedule(BaseModel):
    """NBA game schedule from Goalserve"""
    game_id: str
    game_date: datetime
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
    team_id: str
    team_name: str
    conference: str = ""
    wins: int
    losses: int
    win_percentage: float
    rank: int = 0
    games_back: float = 0.0
    last_ten: str = "0-0"
    streak: str = ""
    points_for: float = 0.0
    points_against: float = 0.0

class NBALiveScore(BaseModel):
    """NBA live score from Goalserve"""
    game_id: str
    status: str  # pregame, live, final
    period: Optional[str] = None
    time_remaining: Optional[str] = None
    home_team: str
    away_team: str
    home_team_score: int
    away_team_score: int

class NBAInjuryReport(BaseModel):
    """NBA injury report from Goalserve"""
    player_id: str
    player_name: str
    status: str  # e.g., Sidelined, Questionable
    description: Optional[str] = None
    date: Optional[str] = None

class GoalserveNBAService:
    """Service for interacting with Goalserve NBA API"""
    
    # NBA team IDs mapping (you should load this from a config or database)
    TEAM_IDS = {
        "Lakers": "1066",
        "Warriors": "1067",
        "Celtics": "1068",
        "Bulls": "1069",
        "Heat": "1070",
        # Add more teams...
    }
    
    def __init__(self):
        """Initialize the Goalserve NBA service with API key and configuration"""
        self.api_key = os.getenv("GOALSERVE_API_KEY")
        if not self.api_key:
            raise ValueError("GOALSERVE_API_KEY environment variable is not set")
        
        self.base_url = "https://www.goalserve.com/getfeed"
        self.api_key_path = self.api_key  # The API key is included in the URL path
        self.client = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(
            timeout=30.0,  # 30 second timeout
            headers={"Accept-Encoding": "gzip"}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    def _build_url(self, endpoint: str) -> str:
        """Build the full URL for a Goalserve API endpoint"""
        return f"{self.base_url}/{self.api_key_path}/bsktbl/{endpoint}?json=1"
    
    def get_team_id(self, team_name: str) -> str:
        """Get the Goalserve team ID for a given team name"""
        team_id = self.TEAM_IDS.get(team_name)
        if not team_id:
            raise ValueError(f"Unknown team name: {team_name}")
        return team_id
    
    @observe(name="goalserve_make_request")
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a request to the Goalserve API"""
        if not self.client:
            raise RuntimeError("Client not initialized. Use async with context manager.")
            
        try:
            url = self._build_url(endpoint)
            params = params or {}
            params["key"] = self.api_key

            # Add retries for 500 errors
            for attempt in range(3):
                try:
                    response = await self.client.get(url, params=params)
                    response.raise_for_status()
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 500 and attempt < 2:
                        logger.warning(f"Attempt {attempt + 1}: Got 500 error, retrying...")
                        await asyncio.sleep(1)  # Wait 1 second before retry
                        continue
                    raise
            
            # Handle gzipped content
            if response.headers.get("content-encoding") == "gzip":
                try:
                    content = gzip.decompress(response.content)
                    return json.loads(content)
                except (gzip.BadGzipFile, json.JSONDecodeError) as e:
                    logger.error(f"Failed to process gzipped content: {str(e)}")
                    raise ValueError("Failed to process response content")
            
            # Regular JSON response
            try:
                return response.json()
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Response content: {response.text[:200]}...")
                raise ValueError("Invalid JSON response from API")

        except Exception as e:
            logger.error(f"Error in API request: {str(e)}")
            if isinstance(e, httpx.HTTPStatusError):
                logger.error(f"Response content: {e.response.text[:200]}...")
            raise
    
    @observe(name="goalserve_get_upcoming_games")
    async def get_upcoming_games(self, team_name: str) -> List[NBASchedule]:
        """Get upcoming games schedule for an NBA team"""
        try:
            data = await self._make_request("nba-schedule")
            games = []
            for match in data.get("matches", []):
                home_team = match.get("home_team", {}).get("name")
                away_team = match.get("away_team", {}).get("name")
                if team_name in [home_team, away_team]:
                    games.append(NBASchedule(
                        game_id=match.get("id"),
                        game_date=parse_date(match.get("date")),
                        home_team=home_team,
                        away_team=away_team,
                        venue=match.get("venue_name"),
                        status=match.get("status", "scheduled"),
                        score_home=match.get("home_team", {}).get("totalscore"),
                        score_away=match.get("away_team", {}).get("totalscore")
                    ))
            return games
                
        except Exception as e:
            logger.error(f"Error getting upcoming games: {str(e)}")
            raise
    
    @observe(name="goalserve_get_team_stats")
    async def get_team_stats(self, team_name: str) -> NBATeamStats:
        """Get current season statistics for an NBA team"""
        try:
            team_id = self.get_team_id(team_name)
            data = await self._make_request(f"{team_id}_team_stats")
            team_data = data.get("statistic", {}).get("team", {})
            stats = team_data.get("stats", {})
            return NBATeamStats(
                team_id=team_id,
                name=team_data.get("name", ""),
                wins=int(stats.get("wins", "0")),
                losses=int(stats.get("losses", "0")),
                win_percentage=float(stats.get("win_percentage", "0.0")),
                points_per_game=float(stats.get("points_per_game", "0.0")),
                points_allowed=float(stats.get("points_allowed", "0.0")),
                last_ten=stats.get("last_ten", "0-0"),
                streak=stats.get("streak", ""),
                home_record=stats.get("home_record", "0-0"),
                away_record=stats.get("away_record", "0-0"),
                conference_rank=int(stats.get("conference_rank", "0"))
            )
                
        except Exception as e:
            logger.error(f"Error getting team stats: {str(e)}")
            raise
    
    @observe(name="goalserve_get_player_stats")
    async def get_player_stats(self, team_name: str) -> List[NBAPlayerStats]:
        """Get current season statistics for all players on an NBA team"""
        try:
            team_id = self.get_team_id(team_name)
            data = await self._make_request(f"{team_id}_team_stats")
            players = []
            for player in data.get("statistic", {}).get("team", {}).get("players", []):
                players.append(NBAPlayerStats(
                    player_id=player.get("id", ""),
                    name=player.get("name", ""),
                    position=player.get("position", ""),
                    status=player.get("status", "Active"),
                    points_per_game=float(player.get("points_per_game", "0.0")),
                    rebounds_per_game=float(player.get("rebounds_per_game", "0.0")),
                    assists_per_game=float(player.get("assists_per_game", "0.0")),
                    minutes_per_game=float(player.get("minutes_per_game", "0.0"))
                ))
            return players
                
        except Exception as e:
            logger.error(f"Error getting player stats: {str(e)}")
            raise
    
    @observe(name="goalserve_get_game_odds")
    async def get_odds_comparison(self, date1: Optional[str] = None, date2: Optional[str] = None) -> List[NBAGameOdds]:
        """Get odds comparison from various bookmakers for a date range"""
        try:
            endpoint = "nba-schedule"
            params = {"showodds": "1"}
            if date1:
                params["date1"] = date1
            if date2:
                params["date2"] = date2

            data = await self._make_request(endpoint, params)

            odds_list = []
            for match in data.get("matches", []):
                odds = match.get("odds", {})
                home_team = match.get("home_team", {}).get("name")
                away_team = match.get("away_team", {}).get("name")
                odds_list.append(NBAGameOdds(
                    game_id=match.get("id"),
                    home_team=home_team,
                    away_team=away_team,
                    home_team_odds=float(odds.get("home_odds", "0.0")),
                    away_team_odds=float(odds.get("away_odds", "0.0")),
                    spread=float(odds.get("spread", "0.0")),
                    total=float(odds.get("total", "0.0"))
                ))
            return odds_list
                
        except Exception as e:
            logger.error(f"Error getting odds comparison: {str(e)}")
            raise
    
    @observe(name="goalserve_get_head_to_head")
    async def get_head_to_head(self, team1_id: str, team2_id: str) -> NBAHeadToHead:
        """Get head-to-head comparison between two teams"""
        try:
            data = await self._make_request(f"h2h_{team1_id}-{team2_id}")
            h2h_data = data.get("h2h", {})
            return NBAHeadToHead(
                total_games=int(h2h_data.get("total_games", 0)),
                home_team_wins=int(h2h_data.get("team1_wins", 0)),
                away_team_wins=int(h2h_data.get("team2_wins", 0)),
                last_five=h2h_data.get("last_games", [])[:5],
                avg_points_home=float(h2h_data.get("avg_points_team1", 0.0)),
                avg_points_away=float(h2h_data.get("avg_points_team2", 0.0))
            )
                
        except Exception as e:
            logger.error(f"Error getting head to head comparison: {str(e)}")
            raise
    
    @observe(name="goalserve_get_standings")
    async def get_standings(self) -> List[NBAStandings]:
        """Get current NBA standings"""
        try:
            data = await self._make_request("nba-standings")
            standings_list = []
            # Iterate over each conference key
            for conf, teams in data.get("standings", {}).items():
                for team in teams:
                    standings_list.append(NBAStandings(
                        team_id=team.get("team_id"),
                        team_name=team.get("name"),
                        conference=conf,
                        wins=int(team.get("wins", 0)),
                        losses=int(team.get("losses", 0)),
                        win_percentage=float(team.get("win_percentage", 0.0)),
                        rank=int(team.get("conference_rank", 0))
                    ))
            return standings_list
                
        except Exception as e:
            logger.error(f"Error getting standings: {str(e)}")
            raise
    
    @observe(name="goalserve_get_live_scores")
    async def get_live_scores(self) -> List[NBALiveScore]:
        """Get live NBA game scores"""
        try:
            data = await self._make_request("nba-scores")
            scores = []
            for match in data.get("matches", []):
                home_team = match.get("home_team", {})
                away_team = match.get("away_team", {})
                scores.append(NBALiveScore(
                    game_id=match.get("id"),
                    status=match.get("status", "live"),
                    period=match.get("period"),
                    time_remaining=match.get("time_remaining"),
                    home_team=home_team.get("name"),
                    away_team=away_team.get("name"),
                    home_team_score=int(home_team.get("totalscore", "0")),
                    away_team_score=int(away_team.get("totalscore", "0"))
                ))
            return scores
                
        except Exception as e:
            logger.error(f"Error getting live scores: {str(e)}")
            raise
    
    @observe(name="goalserve_get_injuries")
    async def get_injuries(self, team_name: str) -> List[NBAInjuryReport]:
        """Get injury reports for a team"""
        try:
            team_id = self.get_team_id(team_name)
            data = await self._make_request(f"{team_id}_injuries")
            
            injuries = []
            for report in data.get("team", {}).get("report", []):
                injuries.append(NBAInjuryReport(
                    player_id=report.get("player_id", ""),
                    player_name=report.get("player_name", ""),
                    status=report.get("status", ""),
                    description=report.get("description"),
                    date=report.get("date")
                ))
            return injuries
                
        except Exception as e:
            logger.error(f"Error getting injury reports: {str(e)}")
            raise 