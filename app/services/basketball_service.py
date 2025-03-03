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

    async def __aenter__(self):
        """Async context manager entry"""
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.client.__aexit__(exc_type, exc_val, exc_tb)

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
    async def get_player_data(self, player_name: str, team_name: Optional[str] = None, game_date: Optional[str] = None, client_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Get data for a specific player"""
        current_season = self.date_handler.determine_season(datetime.now())
        
        try:
            # Get teams first
            teams = await self.teams.list_teams()
            team_id = None
            
            if team_name:
                # Find the team by name
                team = next((t for t in teams if t.name.lower() == team_name.lower()), None)
                if team:
                    team_id = team.id
            
            # Get players for the team
            players = await self.players.get_players(
                season=str(current_season),
                team_id=team_id,
                search=player_name
            )
            
            if not players:
                return {"error": f"No players found for team {team_name}"}
                
            # Find exact match if possible
            player = next((p for p in players if f"{p.firstname} {p.lastname}".lower() == player_name.lower()), None)
                
            if not player and players:
                # Try partial match
                player = next((p for p in players if player_name.lower() in f"{p.firstname} {p.lastname}".lower()), None)
                
            if not player:
                return {"error": f"Player not found: {player_name}"}
            
            # Get player statistics if available
            try:
                stats = await self.players.get_player_statistics(
                    player_id=player.id,
                    season=str(current_season)
                )
                
                # Get recent games if date provided
                games = []
                if game_date:
                    resolved_date = self._resolve_game_date(game_date, client_metadata)
                    if resolved_date:
                        games = await self.games.list_games(
                            season=str(current_season),
                            player_id=player.id,
                            date=self.date_service.format_date_for_api(resolved_date)
                        )
                
                return {
                    "player": player.model_dump(),
                    "statistics": stats[0].model_dump() if stats else {},
                    "recent_games": [g.model_dump() for g in games] if games else [],
                    "season": current_season
                }
                
            except Exception as e:
                logger.error(f"Error getting player statistics: {str(e)}")
                return {
                    "player": player.model_dump(),
                    "error": f"Failed to get player statistics: {str(e)}"
                }
                
        except Exception as e:
            logger.error(f"Error getting player data: {str(e)}")
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
    async def get_games(self, date_reference: str = "today", client_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get games for a specific date reference"""
        all_games = []
        
        try:
            if date_reference == "recent":
                # Get games for yesterday, today, and tomorrow
                today = datetime.now()
                dates = [
                    (today - timedelta(days=1)).strftime("%Y-%m-%d"),
                    today.strftime("%Y-%m-%d"),
                    (today + timedelta(days=1)).strftime("%Y-%m-%d")
                ]
                
                for date in dates:
                    season = self.date_handler.determine_season(datetime.strptime(date, "%Y-%m-%d"))
                    games = await self.games.list_games(date=date, season=str(season))
                    if games:
                        all_games.extend([g.model_dump() for g in games])
                        
                return all_games
            else:
                # Handle single date reference
                resolved_date = self._resolve_game_date(date_reference, client_metadata)
                if not resolved_date:
                    logger.warning(f"Invalid date reference: {date_reference}")
                    return []
                    
                season = self.date_handler.determine_season(resolved_date)
                games = await self.games.list_games(
                    date=self.date_service.format_date_for_api(resolved_date),
                    season=str(season)
                )
                
                return [g.model_dump() for g in games] if games else []
                
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