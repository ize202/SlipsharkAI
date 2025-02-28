from datetime import datetime
import asyncio
from typing import List, Dict, Any, Optional
from app.services.api_sports_basketball import NBAService, NBAApiConfig
from app.config import get_logger
from langfuse.decorators import observe

logger = get_logger(__name__)

class BasketballService:
    """
    Simple service for basketball data that wraps the NBA API.
    Provides methods to get team, player, and game data.
    """

    def __init__(self):
        """Initialize the NBA API config"""
        self.nba_config = NBAApiConfig.from_env()
        self._nba_service = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self._ensure_nba_service()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self._cleanup_nba_service()

    async def _ensure_nba_service(self):
        """Ensure NBA service is initialized in async context"""
        if not self._nba_service:
            self._nba_service = NBAService(self.nba_config)
            await self._nba_service.__aenter__()
        return self._nba_service

    async def _cleanup_nba_service(self):
        """Cleanup NBA service if initialized"""
        if self._nba_service:
            await self._nba_service.__aexit__(None, None, None)
            self._nba_service = None

    def determine_season(self, game_date: Optional[str] = None) -> str:
        """
        Determine the NBA season to use based on date or current date.
        
        NBA seasons span two calendar years (e.g., 2023-2024 season is referred to as "2023").
        The season typically starts in October and ends in June of the following year.
        """
        # Check if a specific date was provided
        if game_date:
            try:
                # Extract year from date
                date_obj = datetime.strptime(game_date, "%Y-%m-%d")
                # If date is between July and December, use that year
                # If date is between January and June, use previous year
                year = date_obj.year if date_obj.month > 6 else date_obj.year - 1
                return str(year)
            except (ValueError, TypeError):
                # If date parsing fails, fall back to current season
                pass
        
        # Default: determine current season based on today's date
        current_date = datetime.now()
        # If current month is between July and December, use current year
        # If current month is between January and June, use previous year
        current_season = current_date.year if current_date.month > 6 else current_date.year - 1
        
        return str(current_season)

    @observe(name="find_team")
    async def find_team(self, team_name: str, season: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a team by name or nickname"""
        if not team_name:
            return None
            
        nba = await self._ensure_nba_service()
        
        # Use provided season or determine current season
        season_to_use = season or self.determine_season()
        
        try:
            # Get teams data
            teams = await nba.teams.list_teams()
            
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
    async def get_team_data(self, team_name: str, season: Optional[str] = None) -> Dict[str, Any]:
        """Get comprehensive data for a team"""
        nba = await self._ensure_nba_service()
        
        # Use provided season or determine current season
        season_to_use = season or self.determine_season()
        
        # Find the team
        team_info = await self.find_team(team_name, season_to_use)
        if not team_info:
            return {"error": f"Team not found: {team_name}"}
            
        team_id = team_info["id"]
        
        try:
            # Gather comprehensive team data in parallel
            team_tasks = [
                # Team stats
                nba.teams.get_team_statistics(team_id, season=season_to_use),
                # Standings
                nba.standings.get_standings("standard", season_to_use, team_id),
                # Recent and upcoming games
                nba.games.list_games(season=season_to_use, team_id=team_id)
            ]
            
            # Execute team tasks
            team_results = await asyncio.gather(*team_tasks, return_exceptions=True)
            
            # Process team results
            return {
                "team_info": team_info,
                "statistics": team_results[0].model_dump() if not isinstance(team_results[0], Exception) else {"error": str(team_results[0])},
                "standings": [s.model_dump() for s in team_results[1]] if not isinstance(team_results[1], Exception) else {"error": str(team_results[1])},
                "games": [g.model_dump() for g in team_results[2]] if not isinstance(team_results[2], Exception) else {"error": str(team_results[2])}
            }
            
        except Exception as e:
            logger.error(f"Error getting data for team {team_name}: {str(e)}")
            return {"error": f"Failed to get data for team {team_name}: {str(e)}"}

    @observe(name="get_player_data")
    async def get_player_data(self, player_name: str, season: Optional[str] = None, team_name: Optional[str] = None) -> Dict[str, Any]:
        """Get data for a player"""
        nba = await self._ensure_nba_service()
        
        # Use provided season or determine current season
        season_to_use = season or self.determine_season()
        
        try:
            # If team name is provided, try to find the team first
            team_id = None
            if team_name:
                team_info = await self.find_team(team_name, season_to_use)
                if team_info:
                    team_id = team_info["id"]
            
            # Split player name into parts for more accurate search
            name_parts = player_name.split()
            
            # Try searching by first name first (which is usually more unique for NBA players)
            players = await nba.players.get_players(
                season=season_to_use,
                search=name_parts[0],  # Use first name for search
                team_id=team_id
            )
            
            # If no results or multiple results, try full name search
            if not players or (len(players) > 1 and len(name_parts) > 1):
                players = await nba.players.get_players(
                    season=season_to_use,
                    search=player_name,  # Try full name
                    team_id=team_id
                )
            
            if not players:
                return {"error": f"Player not found: {player_name}"}
            
            # Filter players to find exact match if possible
            exact_match = None
            for player in players:
                full_name = f"{player.firstname} {player.lastname}".lower()
                if full_name == player_name.lower():
                    exact_match = player
                    break
            
            # Use exact match if found, otherwise use first result
            player = exact_match or players[0]
            
            # Get player statistics
            try:
                player_stats = await nba.players.get_player_statistics(
                    player_id=player.id,
                    season=season_to_use,
                    team_id=team_id
                )
            except Exception as stats_error:
                logger.error(f"Error getting statistics for player {player_name}: {str(stats_error)}")
                player_stats = []
            
            return {
                "player_info": player.model_dump(),
                "statistics": [s.model_dump() for s in player_stats] if player_stats else [],
                "search_results": len(players),  # Include number of matches found
                "exact_match_found": exact_match is not None  # Include whether this was an exact match
            }
            
        except Exception as e:
            logger.error(f"Error getting data for player {player_name}: {str(e)}")
            return {"error": f"Failed to get data for player {player_name}: {str(e)}"}

    @observe(name="get_matchup_data")
    async def get_matchup_data(self, team1_name: str, team2_name: str, season: Optional[str] = None) -> Dict[str, Any]:
        """Get data for a matchup between two teams"""
        nba = await self._ensure_nba_service()
        
        # Use provided season or determine current season
        season_to_use = season or self.determine_season()
        
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
    async def get_league_data(self, season: Optional[str] = None, limit_games: int = 10) -> Dict[str, Any]:
        """
        Get general league data including standings and recent games.
        
        Args:
            season: Optional season to get data for. If not provided, uses current season.
            limit_games: Maximum number of games to return (default 10).
        """
        nba = await self._ensure_nba_service()
        
        # Use provided season or determine current season
        season_to_use = season or self.determine_season()
        
        try:
            # Get standings and recent games
            tasks = [
                nba.standings.get_standings("standard", season_to_use),
                nba.games.list_games(season=season_to_use)
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process standings - get only essential info
            standings = []
            if not isinstance(results[0], Exception):
                for standing in results[0]:
                    # Calculate win percentage manually
                    total_games = standing.win.total + standing.loss.total
                    win_percentage = standing.win.total / total_games if total_games > 0 else 0.0
                    
                    standings.append({
                        "team": standing.team.name,
                        "conference": standing.conference.name,
                        "conference_rank": standing.conference.rank,
                        "division": standing.division.name,
                        "division_rank": standing.division.rank,
                        "win": standing.win.total,
                        "loss": standing.loss.total,
                        "winPercentage": round(win_percentage, 3),
                        "lastTenWin": standing.win.lastTen or 0,
                        "lastTenLoss": standing.loss.lastTen or 0,
                        "streak": standing.streak,
                        "winStreak": standing.winStreak
                    })
                
                # Sort standings by conference rank
                standings.sort(key=lambda x: (x["conference"], x["conference_rank"]))
            else:
                standings = {"error": str(results[0])}
            
            # Process games - limit the number returned
            games = []
            if not isinstance(results[1], Exception):
                # Sort games by date (most recent first) and take only the specified limit
                sorted_games = sorted(
                    results[1], 
                    key=lambda x: x.date["start"] if isinstance(x.date, dict) and "start" in x.date else "0000-00-00",
                    reverse=True
                )
                
                for game in sorted_games[:limit_games]:
                    game_dict = game.model_dump()  # Convert to dictionary first
                    games.append({
                        "id": game.id,
                        "date": game_dict["date"]["start"] if isinstance(game_dict["date"], dict) and "start" in game_dict["date"] else None,
                        "home_team": game_dict["teams"]["home"]["name"] if "home" in game_dict["teams"] else None,
                        "away_team": game_dict["teams"]["visitors"]["name"] if "visitors" in game_dict["teams"] else None,
                        "home_score": game_dict["scores"]["home"]["points"] if game_dict["scores"] and "home" in game_dict["scores"] else None,
                        "away_score": game_dict["scores"]["visitors"]["points"] if game_dict["scores"] and "visitors" in game_dict["scores"] else None,
                        "status": game_dict["status"]["long"] if "status" in game_dict and "long" in game_dict["status"] else None
                    })
            else:
                games = {"error": str(results[1])}
            
            return {
                "standings": standings,
                "recent_games": games,
                "timestamp": datetime.now().isoformat(),
                "confidence": 0.7  # Confidence score for the data
            }
            
        except Exception as e:
            logger.error(f"Error getting league data: {str(e)}")
            return {"error": f"Failed to get league data: {str(e)}"} 