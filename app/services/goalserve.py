from typing import Optional, Dict, Any, List
import os
import logging
import httpx
import gzip
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
        """Initialize the Goalserve NBA service with API key and configuration"""
        self.api_key = os.getenv("GOALSERVE_API_KEY")
        if not self.api_key:
            raise ValueError("GOALSERVE_API_KEY environment variable is not set")
        
        self.base_url = "http://www.goalserve.com/getfeed"
        self.api_key_path = self.api_key  # The API key is included in the URL path
        
        # Initialize async client with GZIP support
        self.client = httpx.AsyncClient(
            timeout=30.0,  # 30 second timeout
            headers={"Accept-Encoding": "gzip"}
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def _build_url(self, endpoint: str) -> str:
        """Build the full URL for a Goalserve API endpoint"""
        return f"{self.base_url}/{self.api_key_path}/bsktbl/{endpoint}"
    
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a request to the Goalserve API with proper error handling and GZIP support"""
        if params is None:
            params = {}
        
        # Always request JSON output
        params["json"] = "1"
        
        try:
            url = self._build_url(endpoint)
            async with self.client as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                
                # Handle GZIP compression if present
                if response.headers.get("content-encoding") == "gzip":
                    decompressed_data = gzip.decompress(response.content)
                    return httpx.loads(decompressed_data)
                
                return response.json()
                
        except httpx.RequestError as e:
            logger.error(f"Request error for endpoint {endpoint}: {str(e)}", exc_info=True)
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for endpoint {endpoint}: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Unexpected error for endpoint {endpoint}: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_upcoming_games")
    async def get_upcoming_games(self, team_name: str) -> List[NBASchedule]:
        """Get upcoming games schedule for an NBA team"""
        try:
            # Use the nba-shedule endpoint
            data = await self._make_request("nba-shedule")
            
            # Filter games for the requested team
            games = []
            for game in data.get("games", []):
                if team_name.lower() in [game["hometeam"].lower(), game["awayteam"].lower()]:
                    schedule = NBASchedule(
                        game_id=game["id"],
                        start_time=datetime.strptime(f"{game['date']} {game['time']}", "%Y-%m-%d %H:%M"),
                        home_team=game["hometeam"],
                        away_team=game["awayteam"],
                        venue=game.get("venue", ""),
                        status=game["status"],
                        score_home=game.get("score_home"),
                        score_away=game.get("score_away")
                    )
                    games.append(schedule)
            
            return games
                
        except Exception as e:
            logger.error(f"Error getting upcoming games: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_team_stats")
    async def get_team_stats(self, team_id: str) -> NBATeamStats:
        """Get current season statistics for an NBA team"""
        try:
            # Use the team_stats endpoint with team ID
            data = await self._make_request(f"{team_id}_stats")
            
            stats = data.get("statistics", {}).get("team", {})
            return NBATeamStats(
                team_id=team_id,
                name=stats.get("name", ""),
                wins=int(stats.get("wins", 0)),
                losses=int(stats.get("losses", 0)),
                win_percentage=float(stats.get("win_percentage", 0.0)),
                points_per_game=float(stats.get("points_per_game", 0.0)),
                points_allowed=float(stats.get("points_allowed", 0.0)),
                last_ten=stats.get("last_ten", "0-0"),
                streak=stats.get("streak", ""),
                home_record=stats.get("home_record", "0-0"),
                away_record=stats.get("away_record", "0-0"),
                conference_rank=int(stats.get("conference_rank", 0))
            )
                
        except Exception as e:
            logger.error(f"Error getting team stats: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_player_stats")
    async def get_player_stats(self, team_id: str) -> List[NBAPlayerStats]:
        """Get current season statistics for all players on an NBA team"""
        try:
            # Use the team_stats endpoint with team ID
            data = await self._make_request(f"{team_id}_stats")
            
            players = []
            for player in data.get("statistics", {}).get("players", []):
                players.append(NBAPlayerStats(
                    player_id=player.get("id", ""),
                    name=player.get("name", ""),
                    position=player.get("position", ""),
                    status=player.get("status", "Active"),
                    points_per_game=float(player.get("points_per_game", 0.0)),
                    rebounds_per_game=float(player.get("rebounds_per_game", 0.0)),
                    assists_per_game=float(player.get("assists_per_game", 0.0)),
                    minutes_per_game=float(player.get("minutes_per_game", 0.0))
                ))
            
            return players
                
        except Exception as e:
            logger.error(f"Error getting player stats: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_game_odds")
    async def get_game_odds(self, team_name: str) -> List[NBAGameOdds]:
        """Get upcoming game odds for an NBA team"""
        try:
            params = {
                "sport": "basketball",
                "league": "nba",
                "key": self.api_key,
                "team": team_name,
                "odds": "true"
            }
            
            data = await self._make_request("odds", params)
            
            # TODO: Parse the response and map to list of NBAGameOdds models
            # This will need to be adjusted based on actual Goalserve API response format
            return [NBAGameOdds(**game_data) for game_data in data["games"]]
                
        except Exception as e:
            logger.error(f"Error getting game odds: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_injuries")
    async def get_injuries(self, team_id: str) -> List[NBAPlayerStats]:
        """Get current injuries for an NBA team"""
        try:
            # Use the injuries endpoint with team ID
            data = await self._make_request(f"{team_id}_injuries")
            
            injuries = []
            for player in data.get("team", {}).get("report", []):
                injuries.append(NBAPlayerStats(
                    player_id=player.get("id", ""),
                    name=player.get("player_name", ""),
                    position=player.get("position", ""),
                    status="Injured",
                    points_per_game=0.0,  # Injury report doesn't include stats
                    rebounds_per_game=0.0,
                    assists_per_game=0.0,
                    minutes_per_game=0.0,
                    injury_status=player.get("status", ""),
                    injury_details=player.get("description", "")
                ))
            
            return injuries
                
        except Exception as e:
            logger.error(f"Error getting injuries: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_odds_comparison")
    async def get_odds_comparison(self, date1: Optional[str] = None, date2: Optional[str] = None) -> List[NBAGameOdds]:
        """Get odds comparison from various bookmakers for a date range"""
        try:
            # Build the endpoint with showodds parameter
            endpoint = "nba-shedule"
            params = {"showodds": "1"}
            
            # Add date range if provided
            if date1:
                params["date1"] = date1
            if date2:
                params["date2"] = date2
            
            data = await self._make_request(endpoint, params)
            
            odds_list = []
            for match in data.get("matches", []):
                if "odds" not in match:
                    continue
                    
                odds = match["odds"]
                game_odds = NBAGameOdds(
                    game_id=match["contestID"],
                    start_time=datetime.strptime(f"{match['formatted_date']} {match['time']}", "%Y-%m-%d %H:%M"),
                    home_team=match["hometeam"],
                    away_team=match["awayteam"],
                    spread=float(odds.get("spread", {}).get("home", 0.0)),
                    total=float(odds.get("total", {}).get("total", 0.0)),
                    home_moneyline=int(odds.get("moneyline", {}).get("home", 0)),
                    away_moneyline=int(odds.get("moneyline", {}).get("away", 0)),
                    last_updated=datetime.now(UTC)
                )
                odds_list.append(game_odds)
            
            return odds_list
                
        except Exception as e:
            logger.error(f"Error getting odds comparison: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_head_to_head")
    async def get_head_to_head(self, team1_id: str, team2_id: str) -> NBAHeadToHead:
        """Get head-to-head comparison between two teams"""
        try:
            # Use the h2h endpoint with team IDs
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
            logger.error(f"Error getting head to head comparison: {str(e)}", exc_info=True)
            raise
    
    @observe(name="goalserve_get_standings")
    async def get_standings(self) -> List[NBAStandings]:
        """Get current NBA standings"""
        try:
            data = await self._make_request("nba-standings")
            
            standings_list = []
            for conference in data.get("standings", {}).values():
                for team in conference:
                    standings = NBAStandings(
                        conference=team.get("conference", ""),
                        rank=int(team.get("position", 0)),
                        team_id=team.get("id", ""),
                        team_name=team.get("name", ""),
                        wins=int(team.get("won", 0)),
                        losses=int(team.get("lost", 0)),
                        win_percentage=float(team.get("percentage", 0.0)),
                        games_back=float(team.get("games_back", 0.0)),
                        last_ten=team.get("last_ten", "0-0"),
                        streak=team.get("streak", ""),
                        points_for=float(team.get("points_for", 0.0)),
                        points_against=float(team.get("points_against", 0.0))
                    )
                    standings_list.append(standings)
            
            return standings_list
                
        except Exception as e:
            logger.error(f"Error getting standings: {str(e)}", exc_info=True)
            raise

    @observe(name="goalserve_get_live_scores")
    async def get_live_scores(self) -> List[NBALiveScore]:
        """Get live NBA game scores"""
        try:
            data = await self._make_request("nba-scores")
            
            scores = []
            for match in data.get("matches", []):
                score = NBALiveScore(
                    game_id=match.get("id", ""),
                    status=match.get("status", ""),
                    current_period=match.get("period", ""),
                    time_remaining=match.get("timer", ""),
                    home_team=match["hometeam"].get("name", ""),
                    away_team=match["awayteam"].get("name", ""),
                    home_score=int(match["hometeam"].get("score", 0)),
                    away_score=int(match["awayteam"].get("score", 0)),
                    last_play=match.get("last_play", ""),
                    scoring_leaders={
                        "home": match["hometeam"].get("scoring_leader", {}),
                        "away": match["awayteam"].get("scoring_leader", {})
                    },
                    updated_at=datetime.now(UTC)
                )
                scores.append(score)
            
            return scores
                
        except Exception as e:
            logger.error(f"Error getting live scores: {str(e)}", exc_info=True)
            raise 