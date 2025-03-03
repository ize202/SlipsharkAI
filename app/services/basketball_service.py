from datetime import datetime, timezone, timedelta
import asyncio
from typing import List, Dict, Any, Optional
from app.services.api_sports_basketball import NBAService, NBAApiConfig, NBAApiClient, NBATeamService, NBAGameService, NBAPlayerService, NBAStandingService, NBASeasonService, NBALeagueService
from app.services.date_resolution_service import DateResolutionService
from app.services.basketball_date_handler import BasketballDateHandler
from app.models.research_models import ClientMetadata
from app.config import get_logger
from langfuse.decorators import observe

logger = get_logger(__name__)

class BasketballService:
    """
    Service for basketball data that wraps the NBA API.
    Provides methods to get team, player, and game data with proper date handling.
    """

    def __init__(self):
        """Initialize the NBA API config and date handlers"""
        self.nba_config = NBAApiConfig.from_env()
        self.client = NBAApiClient(config=self.nba_config)
        self.date_service = DateResolutionService()
        self.date_handler = BasketballDateHandler()
        
        # Initialize NBA services
        self.teams = NBATeamService(self.client)
        self.games = NBAGameService(self.client)
        self.players = NBAPlayerService(self.client)
        self.standings = NBAStandingService(self.client)
        self.seasons = NBASeasonService(self.client)
        self.leagues = NBALeagueService(self.client)
        
        self._team_cache = {}  # Cache team IDs
        self._nba_service = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)

    async def _ensure_nba_service(self) -> NBAService:
        """Ensure NBA service is initialized"""
        if not self._nba_service:
            self._nba_service = NBAService(self.nba_config)
            await self._nba_service.__aenter__()
        return self._nba_service

    def _resolve_game_date(
        self,
        date_reference: Optional[str],
        client_metadata: ClientMetadata
    ) -> Optional[datetime]:
        """
        Resolve game date from reference and validate it
        
        Args:
            date_reference: Date reference (could be relative like "tomorrow")
            client_metadata: Client metadata for timezone context
            
        Returns:
            Resolved datetime or None if invalid/not provided
        """
        if not date_reference:
            return None
            
        # Try to resolve relative date
        if self.date_service.is_relative_date(date_reference):
            resolved_date = self.date_service.resolve_relative_date(
                date_reference,
                client_metadata
            )
        else:
            # Try to parse as exact date
            resolved_date = self.date_service.parse_api_date(date_reference)
            
        # Validate the resolved date
        if resolved_date and self.date_handler.validate_game_date(resolved_date):
            return resolved_date
            
        return None

    @observe(name="find_team")
    async def find_team(self, team_name: str, season: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a team by name or nickname"""
        if not team_name:
            return None
            
        try:
            # Get teams data
            teams = await self.teams.list_teams()
            
            # Try exact match on name
            team = next((t for t in teams if t.name.lower() == team_name.lower()), None)
            
            # If not found, try nickname
            if not team:
                team = next((t for t in teams if t.nickname.lower() == team_name.lower()), None)
                
            if not team:
                logger.warning(f"Team not found: {team_name}")
                return None
                
            return team.model_dump()
            
        except Exception as e:
            logger.error(f"Error finding team {team_name}: {str(e)}")
            return None

    @observe(name="get_team_data")
    async def get_team_data(
        self,
        team_name: str,
        client_metadata: ClientMetadata,
        game_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get team data including current season stats and standings
        
        Args:
            team_name: Name of the team
            client_metadata: Client metadata for timezone/locale
            game_date: Optional date reference for game data
            
        Returns:
            Dictionary containing team data
        """
        try:
            # Resolve and validate the game date
            resolved_date = None
            if game_date:
                resolved_date = self._resolve_game_date(game_date, client_metadata)
                if game_date and not resolved_date:
                    logger.warning(f"Invalid game date reference: {game_date}")
            
            # Determine season based on the game date or current date
            season = self.date_handler.determine_season(
                resolved_date or datetime.now(timezone.utc)
            )
            
            # Get team data
            teams = await self.teams.list_teams()
            team = next((t for t in teams if t.name.lower() == team_name.lower()), None)
            if not team:
                return {"error": f"Team not found: {team_name}"}
            
            team_id = team.id
            
            try:
                # Gather comprehensive team data in parallel
                team_tasks = [
                    # Team stats
                    self.teams.get_team_statistics(team_id, season=str(season)),
                    # Games - filter by date if provided
                    self.games.list_games(
                        season=str(season),
                        team_id=team_id,
                        date=self.date_service.format_date_for_api(resolved_date) if resolved_date else None
                    ),
                    # Get standings
                    self.standings.get_standings(
                        league="standard",
                        season=str(season),
                        team_id=team_id
                    )
                ]
                
                # Execute team tasks
                team_results = await asyncio.gather(*team_tasks, return_exceptions=True)
                
                # Add season phase if we have a game date
                season_context = {}
                if resolved_date:
                    season_context = {
                        "phase": self.date_handler.get_season_phase(resolved_date),
                        "is_playoff_period": self.date_handler.is_playoff_period(resolved_date)
                    }
                
                # Process team results
                return {
                    "id": team.id,
                    "name": team.name,
                    "team_info": team.model_dump(),
                    "statistics": team_results[0].model_dump() if not isinstance(team_results[0], Exception) else {"error": str(team_results[0])},
                    "games": [g.model_dump() for g in team_results[1]] if not isinstance(team_results[1], Exception) else {"error": str(team_results[1])},
                    "standings": [s.model_dump() for s in team_results[2]] if not isinstance(team_results[2], Exception) else {"error": str(team_results[2])},
                    "season_context": season_context
                }
                
            except Exception as e:
                logger.error(f"Error getting data for team {team_name}: {str(e)}")
                return {"error": f"Failed to get data for team {team_name}: {str(e)}"}
            
        except Exception as e:
            logger.error(f"Error getting team data for {team_name}: {str(e)}")
            return {}

    @observe(name="get_player_data")
    async def get_player_data(
        self,
        player_name: str,
        team_name: Optional[str] = None,
        game_date: Optional[str] = None,
        client_metadata: Optional[ClientMetadata] = None,
        season: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get data for a specific player"""
        nba = await self._ensure_nba_service()
        current_season = season or self.date_handler.determine_season(datetime.now())
        
        logger.info(f"Getting player data for {player_name}, team: {team_name}, season: {current_season}")
        
        try:
            # Always try to find team first
            team_id = None
            if team_name:
                team_info = await self.find_team(team_name, current_season)
                logger.debug(f"Team lookup result for {team_name}: {team_info}")
                if team_info:
                    team_id = team_info["id"]
                    logger.info(f"Found team ID {team_id} for {team_name}")
                else:
                    logger.error(f"Could not find team ID for team name: {team_name}")
                    return {"error": f"Could not find team: {team_name}"}
            
            # Split player name into first and last name
            name_parts = player_name.strip().split(" ", 1)
            if len(name_parts) != 2:
                logger.error(f"Invalid player name format: {player_name}")
                return {"error": f"Invalid player name format. Expected 'First Last', got: {player_name}"}
            
            first_name, last_name = name_parts
            
            # Search for player with team filter if available
            search_params = {
                "name": f"{last_name}",  # Search by last name for better results
                "season": str(current_season)
            }
            
            if team_id:
                search_params["team"] = team_id
            
            logger.debug(f"Searching for player with params: {search_params}")
            players = await nba.players.get_players(**search_params)
            
            if not players:
                logger.warning(f"No players found matching {player_name}")
                return {"error": f"No players found matching {player_name}"}
            
            # Find exact match or closest match
            player = None
            for p in players:
                if (p.firstname.lower() == first_name.lower() and 
                    p.lastname.lower() == last_name.lower()):
                    player = p
                    logger.info(f"Found exact match for player {player_name}")
                    break
            
            if not player:
                # Take first result if no exact match
                player = players[0]
                logger.info(f"No exact match found, using first result for {player_name}")
            
            try:
                # Get player's current team if not provided
                if not team_id and player.leagues and player.leagues.standard:
                    logger.debug(f"Attempting to find team ID from player leagues data")
                    # Try to get team from player's current league info
                    if hasattr(player.leagues.standard, "team") and player.leagues.standard.team:
                        team_id = player.leagues.standard.team.get("id")
                        logger.info(f"Found team ID {team_id} from player leagues data")
                
                if not team_id:
                    logger.error(f"Could not find team ID for player {player_name}")
                    return {"error": f"Could not find team for player {player_name}"}
                
                logger.info(f"Getting player statistics with team_id={team_id}, player_id={player.id}, season={current_season}")
                # Get player statistics with both player_id and team_id
                stats = await nba.players.get_player_statistics(
                    team=int(team_id),  # Team ID must be first
                    player_id=player.id,
                    season=str(current_season)
                )
                
                # Get recent games if date provided
                games = []
                if game_date and client_metadata:
                    resolved_date = self._resolve_game_date(game_date, client_metadata)
                    if resolved_date:
                        games = await nba.games.list_games(
                            season=str(current_season),
                            team_id=team_id,
                            date=self.date_service.format_date_for_api(resolved_date)
                        )
                
                return {
                    "player": player.model_dump(),
                    "statistics": [s.model_dump() for s in stats] if stats else [],
                    "games": [g.model_dump() for g in games] if games else []
                }
                
            except Exception as e:
                logger.error(f"Error getting statistics for player {player_name}: {str(e)}", exc_info=True)
                return {"error": f"Failed to get player statistics: {str(e)}"}
                
        except Exception as e:
            logger.error(f"Error getting player data: {str(e)}", exc_info=True)
            return {"error": f"Failed to get player data: {str(e)}"}

    @observe(name="get_matchup_data")
    async def get_matchup_data(self, team1_name: str, team2_name: str, season: Optional[str] = None) -> Dict[str, Any]:
        """Get data for a matchup between two teams"""
        nba = await self._ensure_nba_service()
        
        # Use provided season or determine current season
        season_to_use = season or self.date_handler.determine_season(datetime.now())
        
        try:
            # Find both teams
            team1_info = await self.find_team(team1_name, season_to_use)
            team2_info = await self.find_team(team2_name, season_to_use)
            
            if not team1_info or not team2_info:
                return {"error": f"One or both teams not found: {team1_name} vs {team2_name}"}
                
            team1_id = team1_info["id"]
            team2_id = team2_info["id"]
            
            # Get games for both teams
            team1_games = await nba.games.list_games(
                season=season_to_use,
                team_id=team1_id
            )
            team2_games = await nba.games.list_games(
                season=season_to_use,
                team_id=team2_id
            )
            
            # Combine and filter for games between these two teams
            all_games = team1_games + team2_games
            matchup_games = [
                g.model_dump() for g in all_games 
                if (g.teams["home"]["id"] == team1_id and g.teams["visitors"]["id"] == team2_id) or
                   (g.teams["home"]["id"] == team2_id and g.teams["visitors"]["id"] == team1_id)
            ]
            
            # Remove duplicates (games appearing in both lists)
            seen_ids = set()
            unique_matchup_games = []
            for game in matchup_games:
                if game["id"] not in seen_ids:
                    seen_ids.add(game["id"])
                    unique_matchup_games.append(game)
            
            # Get team stats for comparison
            team_tasks = [
                self.get_team_data(team1_name, season_to_use),
                self.get_team_data(team2_name, season_to_use)
            ]
            
            team_results = await asyncio.gather(*team_tasks)
            
            return {
                "team1": team_results[0],
                "team2": team_results[1],
                "matchup_games": unique_matchup_games,
                "head_to_head_summary": {
                    "total_games": len(unique_matchup_games),
                    "team1_wins": sum(1 for g in unique_matchup_games if 
                        (g["teams"]["home"]["id"] == team1_id and g["scores"]["home"]["points"] > g["scores"]["visitors"]["points"]) or
                        (g["teams"]["visitors"]["id"] == team1_id and g["scores"]["visitors"]["points"] > g["scores"]["home"]["points"])
                    ),
                    "team2_wins": sum(1 for g in unique_matchup_games if 
                        (g["teams"]["home"]["id"] == team2_id and g["scores"]["home"]["points"] > g["scores"]["visitors"]["points"]) or
                        (g["teams"]["visitors"]["id"] == team2_id and g["scores"]["visitors"]["points"] > g["scores"]["home"]["points"])
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting matchup data for {team1_name} vs {team2_name}: {str(e)}")
            return {"error": f"Failed to get matchup data: {str(e)}"}

    @observe(name="get_league_data")
    async def get_league_data(self, client_metadata: ClientMetadata = None) -> Dict:
        """
        Get NBA league data including standings and recent games.
        
        Args:
            client_metadata: Client metadata for timezone/locale
            
        Returns:
            Dictionary containing league data
        """
        try:
            # Get current season
            current_season = str(datetime.now().year)
            
            # Get standings
            standings = await self.standings.get_standings(
                league="standard",
                season=current_season
            )
            
            # Get recent games
            recent_games = await self.games.list_games(
                season=current_season,
                date=datetime.now().strftime("%Y-%m-%d")
            )
            
            return {
                "id": "nba",  # League identifier
                "name": "National Basketball Association",
                "season": current_season,
                "standings": standings.get("response", []),
                "recent_games": recent_games
            }
            
        except Exception as e:
            logger.error(f"Error getting league data: {e}")
            return {}

    @observe(name="get_game_statistics")
    async def get_game_statistics(self, game_id: int) -> Dict[str, Any]:
        """
        Get statistics for a specific game.
        
        Args:
            game_id: The ID of the game to get statistics for.
            
        Returns:
            Dictionary containing game statistics or error message.
        """
        nba = await self._ensure_nba_service()
        
        try:
            # Get game statistics
            game_stats = await nba.games.get_game_statistics(game_id)
            
            return {
                "game_id": game_id,
                "statistics": game_stats,
                "timestamp": datetime.now().isoformat(),
                "confidence": 0.9
            }
            
        except Exception as e:
            logger.error(f"Error getting game statistics for game {game_id}: {str(e)}")
            return {"error": f"Failed to get game statistics: {str(e)}"}

    @observe(name="get_games")
    async def get_games(
        self, 
        date_reference: str = "recent", 
        team_name: Optional[str] = None,
        client_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get games for a specific date reference and optionally filter by team
        
        Args:
            date_reference: Currently only supports "recent" to get games from yesterday, today, and tomorrow
            team_name: Optional team name to filter games for
            client_metadata: Optional client metadata
            
        Returns:
            List of games matching the criteria
        """
        all_games = []
        team_id = None
        
        try:
            # If team name provided, get team ID first
            if isinstance(team_name, str):  # Only process if it's actually a team name string
                team_info = await self.find_team(team_name)
                if not team_info:
                    logger.warning(f"Team not found: {team_name}")
                    return []
                team_id = team_info["id"]
            
            # Get games for yesterday, today, and tomorrow
            today = datetime.now(timezone.utc)
            dates = [
                (today - timedelta(days=1)).strftime("%Y-%m-%d"),
                today.strftime("%Y-%m-%d"),
                (today + timedelta(days=1)).strftime("%Y-%m-%d")
            ]
            
            # Get current season
            current_season = self.date_handler.determine_season(today)
            
            # Get games for each date
            for date in dates:
                try:
                    games = await self.games.list_games(
                        date=date, 
                        season=str(current_season),
                        team_id=team_id
                    )
                    if games:
                        all_games.extend([g.model_dump() for g in games])
                except Exception as e:
                    logger.error(f"Error getting games for date {date}: {str(e)}")
                    continue
            
            return all_games
                
        except Exception as e:
            logger.error(f"Error getting games for {date_reference}: {str(e)}")
            return []

    async def get_matchups(self, team1: str, team2: str, client_metadata: ClientMetadata) -> List[Dict[str, Any]]:
        """
        Get matchup data between two teams
        
        Args:
            team1: First team name
            team2: Second team name
            client_metadata: Client metadata for timezone/locale
            
        Returns:
            List of games between the two teams
        """
        try:
            # Get team IDs
            if team1 not in self._team_cache or team2 not in self._team_cache:
                teams = await self.client.list_teams()
                for team in teams:
                    self._team_cache[team["name"]] = team["id"]
            
            team1_id = self._team_cache.get(team1)
            team2_id = self._team_cache.get(team2)
            
            if not team1_id or not team2_id:
                logger.error(f"Teams not found: {team1} and/or {team2}")
                return []
            
            # Get current season
            season = self.date_handler.determine_season(
                datetime.now(timezone.utc)
            )
            
            # Get all games for team1
            games = await self.client.list_games(
                season=season,
                team_id=team1_id
            )
            
            # Filter for games against team2
            matchups = []
            for game in games:
                if (game["teams"]["home"]["id"] == team2_id or 
                    game["teams"]["away"]["id"] == team2_id):
                    matchups.append(game)
            
            return matchups
            
        except Exception as e:
            logger.error(f"Error getting matchups between {team1} and {team2}: {str(e)}")
            return []

    async def get_league_data(self, client_metadata: ClientMetadata) -> Dict[str, Any]:
        """
        Get NBA league data including standings
        
        Args:
            client_metadata: Client metadata for timezone/locale
            
        Returns:
            Dictionary containing league data
        """
        try:
            # Get current season
            season = self.date_handler.determine_season(
                datetime.now(timezone.utc)
            )
            
            # Get standings
            standings = await self.client.get_standings(
                league="standard",
                season=season
            )
            
            # Get current season games
            games = await self.client.list_games(season=season)
            
            return {
                "id": "nba",
                "name": "NBA",
                "season": season,
                "standings": standings,
                "games": games
            }
            
        except Exception as e:
            logger.error(f"Error getting league data: {str(e)}")
            return {} 