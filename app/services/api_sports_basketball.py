from typing import Optional, Dict, Any, List
import os
import logging
import httpx
from datetime import datetime, UTC
from pydantic import BaseModel, Field
from langfuse.decorators import observe
import json
import asyncio

# Set up logging
logger = logging.getLogger(__name__)

class BasketballTeamStats(BaseModel):
    """Basketball team statistics from API-Sports"""
    team_id: str
    name: str
    games_played: int = Field(default=0)
    wins: int = Field(default=0)
    losses: int = Field(default=0)
    win_percentage: float = Field(default=0.0)
    points_per_game: float = Field(default=0.0)
    points_against_per_game: float = Field(default=0.0)
    field_goals_pct: float = Field(default=0.0)
    three_points_pct: float = Field(default=0.0)
    free_throws_pct: float = Field(default=0.0)
    rebounds_per_game: float = Field(default=0.0)
    assists_per_game: float = Field(default=0.0)
    conference_rank: Optional[int] = None

class BasketballPlayerStats(BaseModel):
    """Basketball player statistics from API-Sports"""
    player_id: str
    name: str
    position: Optional[str] = None
    minutes_per_game: float = Field(default=0.0)
    points_per_game: float = Field(default=0.0)
    rebounds_per_game: float = Field(default=0.0)
    assists_per_game: float = Field(default=0.0)
    steals_per_game: float = Field(default=0.0)
    blocks_per_game: float = Field(default=0.0)
    field_goals_pct: float = Field(default=0.0)
    three_points_pct: float = Field(default=0.0)
    free_throws_pct: float = Field(default=0.0)

class BasketballGame(BaseModel):
    """Basketball game information from API-Sports"""
    game_id: str
    date: datetime
    status: str
    home_team: str
    away_team: str
    home_team_id: str
    away_team_id: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    venue: Optional[str] = None
    stage: Optional[str] = None
    league_id: str
    league_name: str
    season: str

class BasketballStandings(BaseModel):
    """Basketball standings information from API-Sports"""
    team_id: str
    team_name: str
    conference: str
    division: Optional[str] = None
    position: int
    games_played: int
    wins: int
    losses: int
    win_percentage: float
    points_for: float
    points_against: float
    last_ten: Optional[str] = None
    streak: Optional[str] = None

class APISportsBasketballService:
    """Service for interacting with API-Sports Basketball API"""
    
    def __init__(self):
        """Initialize the API-Sports Basketball service with API key and configuration"""
        self.api_key = os.getenv("API_SPORTS_KEY")
        if not self.api_key:
            raise ValueError("API_SPORTS_KEY environment variable is not set")
        
        self.base_url = "https://v1.basketball.api-sports.io"
        self.headers = {
            'x-apisports-key': self.api_key,
            'x-apisports-host': 'v1.basketball.api-sports.io'
        }
        self.client = None
        self._team_ids = {}  # Cache for team IDs
        self.nba_league_id = 12  # NBA league ID in API-Sports
        
        # Standard mappings for team name variations
        self._team_name_mappings = {
            # Los Angeles Lakers variations
            "lakers": "Los Angeles Lakers",
            "la lakers": "Los Angeles Lakers",
            "l.a. lakers": "Los Angeles Lakers",
            
            # Golden State Warriors variations
            "warriors": "Golden State Warriors",
            "gsw": "Golden State Warriors",
            "golden state": "Golden State Warriors",
            
            # Add more team variations as needed...
        }
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(
            timeout=30.0,  # 30 second timeout
            headers=self.headers
        )
        # Load team IDs when entering context
        await self._load_team_ids()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a request to the API-Sports Basketball API"""
        if not self.client:
            raise RuntimeError("Client not initialized. Use async with context manager.")
            
        try:
            url = f"{self.base_url}/{endpoint}"
            params = params or {}
            
            logger.info(f"Making request to endpoint: {endpoint}")
            logger.debug(f"Full URL: {url}")
            logger.debug(f"Params: {params}")

            response = await self.client.get(url, params=params)
            logger.debug(f"Response status: {response.status_code}")
            
            response.raise_for_status()
            data = response.json()
            
            # API-Sports always returns a response object with get, parameters, errors, results, and response fields
            if data.get("errors") and data["errors"]:
                error_msg = json.dumps(data["errors"])
                logger.error(f"API returned errors: {error_msg}")
                raise ValueError(f"API returned errors: {error_msg}")
                
            return data

        except Exception as e:
            logger.error(f"Error in API request to {endpoint}: {str(e)}")
            raise
    
    async def _load_team_ids(self):
        """Load team IDs from the teams endpoint"""
        try:
            # Get current NBA teams
            data = await self._make_request("teams", {
                "league": self.nba_league_id,
                "season": "2023-2024"  # Current season
            })
            
            # Process teams
            if "response" in data and data["response"]:
                for team in data["response"]:
                    name = team.get("name")
                    team_id = str(team.get("id"))
                    if name and team_id:
                        self._team_ids[name] = team_id
                        logger.debug(f"Added team mapping: {name} -> {team_id}")
            
            if not self._team_ids:
                logger.error("No team IDs were loaded")
                raise ValueError("Failed to load team IDs")
                
            logger.info(f"Successfully loaded {len(self._team_ids)} team IDs")
            
        except Exception as e:
            logger.error(f"Error loading team IDs: {str(e)}")
            raise
    
    def normalize_team_name(self, team_name: str) -> str:
        """Normalize team name to match the official names used by API-Sports"""
        if not team_name:
            return ""
            
        # First check if the name is already in the correct format
        if team_name in self._team_ids:
            return team_name
            
        # Try direct mapping from our predefined variations
        normalized = self._team_name_mappings.get(team_name.lower())
        if normalized:
            logger.info(f"Normalized team name from '{team_name}' to '{normalized}'")
            return normalized
            
        # Check if it's a partial match with any of the official team names
        for official_name in self._team_ids.keys():
            if team_name.lower() in official_name.lower():
                logger.info(f"Matched partial team name '{team_name}' to '{official_name}'")
                return official_name
                
        # If we still don't have a match, log a warning and return the original
        logger.warning(f"Could not normalize team name: '{team_name}'")
        return team_name
    
    def get_team_id(self, team_name: str) -> str:
        """Get the API-Sports team ID for a given team name"""
        # First normalize the team name
        normalized_name = self.normalize_team_name(team_name)
        
        logger.debug(f"Looking up team ID for: '{normalized_name}' (original: '{team_name}')")
        
        team_id = self._team_ids.get(normalized_name)
        if not team_id:
            logger.error(f"Could not find team ID for '{normalized_name}'. Available teams: {list(self._team_ids.keys())}")
            raise ValueError(f"Unknown team name: {normalized_name}")
            
        logger.info(f"Found team ID '{team_id}' for team '{normalized_name}'")
        return team_id

    @observe(name="api_sports_get_team_stats")
    async def get_team_stats(self, team_name_or_id: str) -> BasketballTeamStats:
        """Get team statistics from API-Sports Basketball
        
        Args:
            team_name_or_id (str): Either the team name or team ID. If a name is provided,
                                  it will be converted to an ID.
            
        Returns:
            BasketballTeamStats: Team statistics
            
        Raises:
            ValueError: If the team cannot be found or if there's an error getting stats
        """
        try:
            # If a team name was provided, convert it to an ID
            team_id = team_name_or_id
            if not team_name_or_id.isdigit():
                team_id = self.get_team_id(team_name_or_id)
                logger.info(f"Converted team name '{team_name_or_id}' to ID '{team_id}'")

            # Get team statistics for the current season
            data = await self._make_request("statistics", {
                "league": self.nba_league_id,
                "season": "2023-2024",  # Current season
                "team": team_id
            })
            
            if not data.get("response"):
                raise ValueError(f"No statistics found for team {team_id}")
                
            stats = data["response"]
            
            # Extract team info
            team_info = stats.get("team", {})
            games = stats.get("games", {})
            points = stats.get("points", {})
            
            # Calculate averages and percentages
            games_played = games.get("played", {}).get("all", 0)
            points_for = points.get("for", {}).get("average", {}).get("all", 0)
            points_against = points.get("against", {}).get("average", {}).get("all", 0)
            
            # Get standings to determine conference rank
            standings_data = await self._make_request("standings", {
                "league": self.nba_league_id,
                "season": "2023-2024",
                "team": team_id
            })
            
            conference_rank = None
            if standings_data.get("response"):
                for standing in standings_data["response"][0]:  # API returns list of lists
                    if str(standing.get("team", {}).get("id")) == team_id:
                        conference_rank = standing.get("position")
                        break
            
            # Create and return the team stats object
            return BasketballTeamStats(
                team_id=team_id,
                name=team_info.get("name", ""),
                games_played=games_played,
                wins=games.get("wins", {}).get("all", {}).get("total", 0),
                losses=games.get("loses", {}).get("all", {}).get("total", 0),
                win_percentage=float(games.get("wins", {}).get("all", {}).get("percentage", "0")),
                points_per_game=float(points_for),
                points_against_per_game=float(points_against),
                field_goals_pct=float(stats.get("fgp", {}).get("all", 0)),
                three_points_pct=float(stats.get("tpp", {}).get("all", 0)),
                free_throws_pct=float(stats.get("ftp", {}).get("all", 0)),
                rebounds_per_game=float(stats.get("rebounds", {}).get("average", {}).get("all", 0)),
                assists_per_game=float(stats.get("assists", {}).get("average", {}).get("all", 0)),
                conference_rank=conference_rank
            )

        except Exception as e:
            logger.error(f"Error getting team stats for team {team_name_or_id}: {str(e)}")
            raise ValueError(f"Error getting team stats for team {team_name_or_id}") from e
    
    @observe(name="api_sports_get_player_stats")
    async def get_player_stats(self, team_name_or_id: str) -> List[BasketballPlayerStats]:
        """Get current season statistics for all players on a team
        
        Args:
            team_name_or_id (str): Either the team name or team ID. If a name is provided,
                                  it will be converted to an ID.
        
        Returns:
            List[BasketballPlayerStats]: List of player statistics
            
        Raises:
            ValueError: If the team cannot be found or if there's an error getting stats
        """
        try:
            # If a team name was provided, convert it to an ID
            team_id = team_name_or_id
            if not team_name_or_id.isdigit():
                team_id = self.get_team_id(team_name_or_id)
                logger.info(f"Converted team name '{team_name_or_id}' to ID '{team_id}'")

            # First get the team's players
            players_data = await self._make_request("players", {
                "team": team_id,
                "season": "2023-2024"  # Current season
            })
            
            if not players_data.get("response"):
                raise ValueError(f"No players found for team {team_id}")
            
            # Get statistics for each player
            player_stats_list = []
            for player in players_data["response"]:
                player_id = str(player.get("id"))
                
                # Get player statistics
                stats_data = await self._make_request("players/statistics", {
                    "player": player_id,
                    "season": "2023-2024"
                })
                
                if not stats_data.get("response"):
                    # If no stats, create basic player info
                    player_stats = BasketballPlayerStats(
                        player_id=player_id,
                        name=player.get("name", ""),
                        position=player.get("position")
                    )
                else:
                    # Process player statistics
                    stats = stats_data["response"][0]  # Get first stats entry
                    player_stats = BasketballPlayerStats(
                        player_id=player_id,
                        name=player.get("name", ""),
                        position=player.get("position"),
                        minutes_per_game=float(stats.get("minutes", "0").split(":")[0]),  # Convert "MM:SS" to minutes
                        points_per_game=float(stats.get("points", 0)),
                        rebounds_per_game=float(stats.get("rebounds", {}).get("total", 0)),
                        assists_per_game=float(stats.get("assists", 0)),
                        steals_per_game=float(stats.get("steals", 0)),
                        blocks_per_game=float(stats.get("blocks", 0)),
                        field_goals_pct=float(stats.get("fgp", 0)),
                        three_points_pct=float(stats.get("tpp", 0)),
                        free_throws_pct=float(stats.get("ftp", 0))
                    )
                
                player_stats_list.append(player_stats)
            
            return player_stats_list

        except Exception as e:
            logger.error(f"Error getting player stats: {str(e)}")
            raise ValueError(f"Error getting player stats for team {team_name_or_id}") from e

    @observe(name="api_sports_get_standings")
    async def get_standings(self) -> List[BasketballStandings]:
        """Get current NBA standings
        
        Returns:
            List[BasketballStandings]: List of team standings
            
        Raises:
            ValueError: If there's an error getting standings
        """
        try:
            data = await self._make_request("standings", {
                "season": "2023-2024"  # Current season
            })
            
            if not data.get("response"):
                raise ValueError("No standings data available")
            
            standings_list = []
            for conference_standings in data["response"]:  # API returns list of lists for each conference
                for standing in conference_standings:
                    team_info = standing.get("team", {})
                    games = standing.get("games", {})
                    points = standing.get("points", {})
                    group = standing.get("group", {})
                    
                    standings_list.append(BasketballStandings(
                        team_id=str(team_info.get("id")),
                        team_name=team_info.get("name", ""),
                        conference=group.get("name", ""),
                        position=standing.get("position", 0),
                        games_played=games.get("played", 0),
                        wins=games.get("win", {}).get("total", 0),
                        losses=games.get("lose", {}).get("total", 0),
                        win_percentage=float(games.get("win", {}).get("percentage", "0")),
                        points_for=float(points.get("for", 0)),
                        points_against=float(points.get("against", 0)),
                        last_ten=standing.get("form", ""),  # API returns form as "WWLWL" format
                        streak=None  # API doesn't provide streak information directly
                    ))
            
            return standings_list
            
        except Exception as e:
            logger.error(f"Error getting standings: {str(e)}")
            raise ValueError("Error getting standings") from e
    
    @observe(name="api_sports_get_upcoming_games")
    async def get_upcoming_games(self, team_name: str) -> List[BasketballGame]:
        """Get upcoming games for a specific team
        
        Args:
            team_name (str): The name of the team
            
        Returns:
            List[BasketballGame]: List of upcoming games
            
        Raises:
            ValueError: If the team cannot be found or if there's an error getting games
        """
        try:
            team_id = self.get_team_id(team_name)
            
            # Get next 10 games for the team
            data = await self._make_request("games", {
                "league": self.nba_league_id,
                "season": "2023-2024",
                "team": team_id,
                "timezone": "America/New_York"  # Use Eastern Time for NBA games
            })
            
            if not data.get("response"):
                raise ValueError(f"No games found for team {team_name}")
            
            games_list = []
            for game in data["response"]:
                # Only include upcoming games (status "NS" = Not Started)
                if game.get("status", {}).get("short") == "NS":
                    teams = game.get("teams", {})
                    scores = game.get("scores", {})
                    league = game.get("league", {})
                    
                    games_list.append(BasketballGame(
                        game_id=str(game.get("id")),
                        date=datetime.fromtimestamp(game.get("timestamp", 0), UTC),
                        status=game.get("status", {}).get("long", "Not Started"),
                        home_team=teams.get("home", {}).get("name", ""),
                        away_team=teams.get("away", {}).get("name", ""),
                        home_team_id=str(teams.get("home", {}).get("id", "")),
                        away_team_id=str(teams.get("away", {}).get("id", "")),
                        home_score=scores.get("home", {}).get("total"),
                        away_score=scores.get("away", {}).get("total"),
                        venue=game.get("venue"),
                        stage=game.get("stage"),
                        league_id=str(league.get("id")),
                        league_name=league.get("name", ""),
                        season=league.get("season", "")
                    ))
            
            return games_list
            
        except Exception as e:
            logger.error(f"Error getting upcoming games for team {team_name}: {str(e)}")
            raise ValueError(f"Error getting upcoming games for team {team_name}") from e
    
    @observe(name="api_sports_get_head_to_head")
    async def get_head_to_head(self, team1_name: str, team2_name: str) -> List[BasketballGame]:
        """Get head-to-head games between two teams
        
        Args:
            team1_name (str): Name of the first team
            team2_name (str): Name of the second team
            
        Returns:
            List[BasketballGame]: List of games between the two teams
            
        Raises:
            ValueError: If either team cannot be found or if there's an error getting games
        """
        try:
            team1_id = self.get_team_id(team1_name)
            team2_id = self.get_team_id(team2_name)
            
            # Get head-to-head games
            data = await self._make_request("games", {
                "h2h": f"{team1_id}-{team2_id}",
                "league": self.nba_league_id,
                "season": "2023-2024",  # Current season
                "timezone": "America/New_York"
            })
            
            if not data.get("response"):
                raise ValueError(f"No head-to-head games found between {team1_name} and {team2_name}")
            
            games_list = []
            for game in data["response"]:
                teams = game.get("teams", {})
                scores = game.get("scores", {})
                league = game.get("league", {})
                
                games_list.append(BasketballGame(
                    game_id=str(game.get("id")),
                    date=datetime.fromtimestamp(game.get("timestamp", 0), UTC),
                    status=game.get("status", {}).get("long", ""),
                    home_team=teams.get("home", {}).get("name", ""),
                    away_team=teams.get("away", {}).get("name", ""),
                    home_team_id=str(teams.get("home", {}).get("id", "")),
                    away_team_id=str(teams.get("away", {}).get("id", "")),
                    home_score=scores.get("home", {}).get("total"),
                    away_score=scores.get("away", {}).get("total"),
                    venue=game.get("venue"),
                    stage=game.get("stage"),
                    league_id=str(league.get("id")),
                    league_name=league.get("name", ""),
                    season=league.get("season", "")
                ))
            
            return games_list
            
        except Exception as e:
            logger.error(f"Error getting head-to-head games: {str(e)}")
            raise ValueError(f"Error getting head-to-head games between {team1_name} and {team2_name}") from e

    