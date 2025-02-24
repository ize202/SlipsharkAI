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
import xml.etree.ElementTree as ET
from io import StringIO
from ..utils.cache import redis_cache, memory_cache

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
    
    def __init__(self):
        """Initialize the Goalserve NBA service with API key and configuration"""
        self.api_key = os.getenv("GOALSERVE_API_KEY")
        if not self.api_key:
            raise ValueError("GOALSERVE_API_KEY environment variable is not set")
        
        self.base_url = "https://www.goalserve.com/getfeed"
        self.api_key_path = self.api_key  # The API key is included in the URL path
        self.client = None
        self._team_ids = {}  # Cache for team IDs
    
    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(
            timeout=30.0,  # 30 second timeout
            headers={"Accept-Encoding": "gzip"}
        )
        # Load team IDs when entering context
        await self._load_team_ids()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()
            self.client = None
    
    def _build_url(self, endpoint: str) -> str:
        """Build the full URL for a Goalserve API endpoint"""
        # Make sure json=1 is the first parameter if there are other parameters in the endpoint
        if '?' in endpoint:
            endpoint = endpoint.replace('?', '?json=1&')
        else:
            endpoint = f"{endpoint}?json=1"
        return f"{self.base_url}/{self.api_key_path}/bsktbl/{endpoint}"
    
    def _parse_xml_response(self, xml_text: str) -> Dict[str, Any]:
        """Parse XML response into a dictionary"""
        try:
            root = ET.fromstring(xml_text)
            result = {}
            
            def parse_element(element, parent_dict):
                """Recursively parse XML elements"""
                if len(element) == 0:  # No children
                    # Get all attributes
                    attrs = element.attrib
                    if attrs:
                        parent_dict[element.tag] = attrs
                    else:
                        parent_dict[element.tag] = element.text
                else:
                    # Has children
                    if element.tag not in parent_dict:
                        parent_dict[element.tag] = {}
                    
                    # If there are multiple children with the same tag, make it a list
                    child_tags = [child.tag for child in element]
                    for tag in set(child_tags):
                        if child_tags.count(tag) > 1:
                            parent_dict[element.tag][tag] = []
                            for child in element.findall(tag):
                                child_dict = {}
                                parse_element(child, child_dict)
                                parent_dict[element.tag][tag].append(child_dict.get(tag, {}))
                        else:
                            for child in element.findall(tag):
                                parse_element(child, parent_dict[element.tag])
            
            parse_element(root, result)
            return result
            
        except ET.ParseError as e:
            logger.error(f"Failed to parse XML: {str(e)}")
            logger.error(f"XML content: {xml_text[:500]}")
            raise ValueError("Failed to parse XML response")

    # Cache the request for 5 minutes - this is a low-level method used by other methods
    @redis_cache(ttl=300, prefix="goalserve_request")
    @observe(name="goalserve_make_request")
    async def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a request to the Goalserve API"""
        if not self.client:
            raise RuntimeError("Client not initialized. Use async with context manager.")
            
        try:
            url = self._build_url(endpoint)
            params = params or {}
            # Remove duplicate API key if present
            params.pop("key", None)
            # Ensure json=1 is in params
            params["json"] = "1"
            
            logger.info(f"Making request to endpoint: {endpoint}")
            logger.debug(f"Full URL: {url}")
            logger.debug(f"Params: {params}")

            # Add retries for 500 errors
            for attempt in range(3):
                try:
                    response = await self.client.get(url, params=params)
                    logger.debug(f"Response status: {response.status_code}")
                    logger.debug(f"Response headers: {dict(response.headers)}")
                    
                    # Log the first 500 characters of the response for debugging
                    content_preview = response.text[:500] if response.text else "Empty response"
                    logger.debug(f"Response preview: {content_preview}")
                    
                    response.raise_for_status()
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 500 and attempt < 2:
                        logger.warning(f"Attempt {attempt + 1}: Got 500 error, retrying...")
                        await asyncio.sleep(1)  # Wait 1 second before retry
                        continue
                    logger.error(f"HTTP error {e.response.status_code} for {endpoint}")
                    logger.error(f"Response content: {e.response.text[:500]}")
                    raise

            # Try to parse the response content
            try:
                # First try direct JSON parsing
                return response.json()
            except json.JSONDecodeError:
                # If that fails, check if it's gzipped
                if response.headers.get("content-encoding") == "gzip":
                    try:
                        decompressed_content = gzip.decompress(response.content)
                        return json.loads(decompressed_content)
                    except (gzip.BadGzipFile, json.JSONDecodeError) as e:
                        logger.error(f"Failed to process gzipped content: {str(e)}")
                        logger.error(f"Content preview: {response.content[:500] if response.content else 'Empty content'}")
                        raise ValueError("Failed to process gzipped response content")
                else:
                    # If we got XML, try to parse it
                    if response.text.strip().startswith('<?xml'):
                        logger.info("Received XML response, attempting to parse")
                        return self._parse_xml_response(response.text)
                    else:
                        logger.error("Response is not valid JSON, XML, or gzipped")
                        logger.error(f"Response content type: {response.headers.get('content-type')}")
                        logger.error(f"Response content preview: {response.text[:500]}")
                        raise ValueError("Invalid response format from API")

        except Exception as e:
            logger.error(f"Error in API request to {endpoint}: {str(e)}")
            if isinstance(e, httpx.HTTPStatusError):
                logger.error(f"Response content: {e.response.text[:500]}")
            raise
    
    # Cache team IDs for 24 hours since they rarely change
    @redis_cache(ttl=86400, prefix="goalserve_team_id")
    def get_team_id(self, team_name: str) -> str:
        """Get the Goalserve team ID for a given team name"""
        logger.debug(f"Looking up team ID for: '{team_name}'")
        logger.debug(f"Available team mappings: {json.dumps(self._team_ids, indent=2)}")
        team_id = self._team_ids.get(team_name)
        if not team_id:
            logger.error(f"Could not find team ID for '{team_name}'. Available teams: {list(self._team_ids.keys())}")
            raise ValueError(f"Unknown team name: {team_name}")
        logger.info(f"Found team ID '{team_id}' for team '{team_name}'")
        return team_id
    
    # Cache upcoming games for 30 minutes
    @redis_cache(ttl=1800, prefix="goalserve_upcoming")
    @observe(name="goalserve_get_upcoming_games")
    async def get_upcoming_games(self, team_name: str) -> List[NBASchedule]:
        """Get upcoming games for a specific team."""
        data = await self._make_request("nba-shedule")
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
    
    # Cache team stats for 1 hour
    @redis_cache(ttl=3600, prefix="goalserve_team_stats")
    @observe(name="goalserve_get_team_stats")
    async def get_team_stats(self, team_name_or_id: str) -> Dict[str, Any]:
        """Get team stats from Goalserve API.
        
        Args:
            team_name_or_id (str): Either the team name or team ID. If a name is provided,
                                  it will be converted to an ID using the standings data.
            
        Returns:
            Dict[str, Any]: A dictionary containing team statistics organized by category
            
        Raises:
            ValueError: If the response structure is invalid or missing required data
        """
        try:
            # If a team name was provided, convert it to an ID
            team_id = team_name_or_id
            if not team_name_or_id.isdigit():
                team_id = self.get_team_id(team_name_or_id)
                logger.info(f"Converted team name '{team_name_or_id}' to ID '{team_id}'")

            # Use the correct endpoint format: team_id_team_stats
            response = await self._make_request(f"{team_id}_team_stats")
            
            if not isinstance(response, dict) or "statistic" not in response:
                logger.error(f"Invalid response format: {json.dumps(response, indent=2)[:1000]}")
                raise ValueError(f"Invalid response format for team {team_id}")

            stats = response["statistic"]
            if not isinstance(stats, dict) or "category" not in stats:
                logger.error(f"Invalid stats format: {json.dumps(stats, indent=2)[:1000]}")
                raise ValueError(f"Invalid stats format for team {team_id}")

            # Get categories - handle both single category and list of categories
            categories = stats["category"]
            if not isinstance(categories, list):
                categories = [categories]

            # Initialize stats dictionary with default values
            team_stats = {
                "general": {
                    "games_played": 0,
                    "total_rebounds": 0,
                    "rebounds_avg": 0.0,
                    "technical_fouls_total": 0,
                    "fouls_total": 0,
                    "fouls_avg": 0.0,
                    "defensive_rebounds_total": 0,
                    "defensive_rebounds_avg": 0.0,
                    "steals_total": 0,
                    "steals_avg": 0.0,
                    "blocks_total": 0,
                    "blocks_avg": 0.0
                },
                "offensive": {
                    "points_avg": 0.0,
                    "points_total": 0,
                    "fieldgoals_avg": 0.0,
                    "fieldgoals_attempts_avg": 0.0,
                    "fieldgoals_pct": 0.0,
                    "threepoint_avg": 0.0,
                    "threepoint_attempts_avg": 0.0,
                    "threepoint_pct": 0.0,
                    "freethrows_avg": 0.0,
                    "freethrows_attempts_avg": 0.0,
                    "freethrows_pct": 0.0,
                    "assists_avg": 0.0,
                    "offensive_rebounds_avg": 0.0
                },
                "defensive": {
                    "defensive_rebounds_total": 0,
                    "defensive_rebounds_avg": 0.0,
                    "steals_total": 0,
                    "steals_avg": 0.0,
                    "blocks_total": 0,
                    "blocks_avg": 0.0
                }
            }

            # Process each category
            for category in categories:
                if not isinstance(category, dict) or "name" not in category:
                    continue

                category_name = category["name"].lower()
                team_data = category.get("team", {})
                
                if not team_data:
                    logger.warning(f"No team data found for category {category_name}")
                    continue

                # Update stats based on category
                if category_name == "general":
                    for key in team_stats["general"].keys():
                        if key in team_data:
                            try:
                                team_stats["general"][key] = float(team_data[key]) if "avg" in key else int(team_data[key])
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Error converting {key} value: {team_data[key]}, Error: {str(e)}")
                                
                elif category_name == "offensive":
                    for key in team_stats["offensive"].keys():
                        if key in team_data:
                            try:
                                team_stats["offensive"][key] = float(team_data[key])
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Error converting {key} value: {team_data[key]}, Error: {str(e)}")
                                
                elif category_name == "defensive":
                    for key in team_stats["defensive"].keys():
                        if key in team_data:
                            try:
                                team_stats["defensive"][key] = float(team_data[key]) if "avg" in key else int(team_data[key])
                            except (ValueError, TypeError) as e:
                                logger.warning(f"Error converting {key} value: {team_data[key]}, Error: {str(e)}")

            # Add metadata
            team_stats["team_id"] = team_id
            team_stats["team_name"] = stats.get("team", "")
            team_stats["season"] = stats.get("season", "")

            return team_stats

        except Exception as e:
            logger.error(f"Error getting team stats for team {team_id}: {str(e)}")
            raise ValueError(f"Error getting team stats for team {team_id}") from e
    
    # Cache player stats for 1 hour
    @redis_cache(ttl=3600, prefix="goalserve_player_stats")
    @observe(name="goalserve_get_player_stats")
    async def get_player_stats(self, team_name_or_id: str) -> List[NBAPlayerStats]:
        """Get current season statistics for all players on an NBA team
        
        Args:
            team_name_or_id (str): Either the team name or team ID. If a name is provided,
                                  it will be converted to an ID using the standings data.
        
        Returns:
            List[NBAPlayerStats]: List of player statistics
            
        Raises:
            ValueError: If the team cannot be found or if there's an error getting stats
        """
        try:
            # If a team name was provided, convert it to an ID
            team_id = team_name_or_id
            if not team_name_or_id.isdigit():
                team_id = self.get_team_id(team_name_or_id)
                logger.info(f"Converted team name '{team_name_or_id}' to ID '{team_id}'")

            # Use the correct endpoint format: team_id_stats
            response = await self._make_request(f"{team_id}_stats")
            logger.debug(f"Player stats response: {json.dumps(response, indent=2)[:1000]}")

            if not isinstance(response, dict) or "statistic" not in response:
                raise ValueError(f"Invalid response format: {response}")

            stats = response["statistic"]
            if not isinstance(stats, dict) or "category" not in stats:
                raise ValueError(f"Invalid stats format: {stats}")

            categories = stats["category"]
            if not isinstance(categories, list):
                categories = [categories]  # Handle single category case

            player_stats_list = []
            
            # Process each category
            for category in categories:
                if not isinstance(category, dict) or "name" not in category:
                    continue

                if category["name"] == "Game":
                    players = category.get("player", [])
                    if not isinstance(players, list):
                        players = [players]  # Handle single player case

                    for player in players:
                        try:
                            player_stats = NBAPlayerStats(
                                player_id=player.get("id", ""),
                                name=player.get("name", ""),
                                position=player.get("position", ""),
                                status=player.get("status", "Active"),
                                points_per_game=float(player.get("points_per_game", 0)),
                                rebounds_per_game=float(player.get("rebounds_per_game", 0)),
                                assists_per_game=float(player.get("assists_per_game", 0)),
                                minutes_per_game=float(player.get("minutes", 0)),
                                injury_status=player.get("injury_status"),
                                injury_details=player.get("injury_details")
                            )
                            player_stats_list.append(player_stats)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Error parsing stats for player {player.get('name', 'unknown')}: {str(e)}")
                            continue

            return player_stats_list

        except Exception as e:
            logger.error(f"Error getting player stats: {str(e)}")
            raise ValueError(f"Error getting player stats for team {team_id}") from e
    
    # Cache head-to-head data for 6 hours
    @redis_cache(ttl=21600, prefix="goalserve_h2h")
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
    
    # Cache standings for 1 hour
    @redis_cache(ttl=3600, prefix="goalserve_standings")
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
    
    # Cache live scores for only 1 minute since they change frequently
    @redis_cache(ttl=60, prefix="goalserve_live")
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
    
    # Cache injuries for 2 hours
    @redis_cache(ttl=7200, prefix="goalserve_injuries")
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
    
    async def _load_team_ids(self):
        """Load team IDs from standings data"""
        try:
            # Get the standings data
            data = await self._make_request("nba-standings")
            logger.info("Fetching standings data for team ID mapping")
            
            if not isinstance(data, dict):
                raise ValueError(f"Invalid standings data format: expected dict, got {type(data)}")
            
            # Initialize team mappings
            self._team_ids = {}
            
            # Handle the nested format
            if "standings" in data and isinstance(data["standings"], dict):
                standings = data["standings"]
                if "category" in standings:
                    categories = standings["category"]
                    # Handle both list and dict cases
                    if isinstance(categories, dict):
                        categories = [categories]
                    elif not isinstance(categories, list):
                        raise ValueError(f"Invalid category format: expected list or dict, got {type(categories)}")
                    
                    for category in categories:
                        if "league" in category:
                            leagues = category["league"]
                            # Handle both list and dict cases
                            if isinstance(leagues, dict):
                                leagues = [leagues]
                            elif not isinstance(leagues, list):
                                continue
                            
                            for league in leagues:
                                if "division" in league:
                                    divisions = league["division"]
                                    # Handle both list and dict cases
                                    if isinstance(divisions, dict):
                                        divisions = [divisions]
                                    elif not isinstance(divisions, list):
                                        continue
                                    
                                    for division in divisions:
                                        if "team" in division:
                                            teams = division["team"]
                                            # Handle both list and dict cases
                                            if isinstance(teams, dict):
                                                teams = [teams]
                                            elif not isinstance(teams, list):
                                                continue
                                            
                                            for team in teams:
                                                name = team.get("name", "")
                                                team_id = team.get("id", "")
                                                if name and team_id:
                                                    # Clean up team name
                                                    if name.startswith("USA: NBA "):
                                                        name = name[9:]
                                                    self._team_ids[name] = team_id
                                                    logger.debug(f"Added team mapping: {name} -> {team_id}")
            
            if not self._team_ids:
                logger.error("No team IDs were loaded from the standings data")
                logger.error(f"Raw data structure: {json.dumps(data, indent=2)[:1000]}")
                raise ValueError("No team IDs were loaded from the standings data")
            
            logger.info(f"Successfully loaded {len(self._team_ids)} team IDs")
            logger.debug(f"Team mappings: {self._team_ids}")
            
        except Exception as e:
            logger.error(f"Error loading team IDs: {str(e)}")
            logger.error("Team ID loading failed. Some methods may not work correctly.")
            self._team_ids = {}  # Reset to empty dict on error
            raise 