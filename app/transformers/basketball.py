from typing import Dict, Any, List, Optional
from datetime import datetime
from app.transformers.base import (
    SportDataTransformer,
    TransformedSportData,
    CommonTeamInfo,
    CommonGameInfo,
    CommonPlayerInfo
)
from app.config import get_logger
from app.utils.cache import redis_cache
from app.services.api_sports_basketball import NBA_TEAM_IDS

logger = get_logger(__name__)

class BasketballTransformer(SportDataTransformer):
    """Transformer for basketball data"""
    
    def _validate_team_id(self, team_id: int) -> bool:
        """Validate that a team ID exists in our static mapping"""
        return team_id in set(NBA_TEAM_IDS.values())
    
    @redis_cache(ttl=3600, prefix="basketball_team")
    async def transform_team_data(
        self,
        raw_data: Dict[str, Any],
        required_data: List[str]
    ) -> Dict[str, Any]:
        """Transform raw basketball team data into common format"""
        try:
            if not raw_data:
                return {"error": "No team data provided"}
                
            # Validate team ID
            team_id = raw_data.get("id")
            if team_id and not self._validate_team_id(team_id):
                logger.warning(f"Unknown team ID: {team_id}")
                
            # Initialize result with team info
            result = {
                "id": raw_data.get("id"),
                "name": raw_data.get("name"),
                "team_info": raw_data.get("team_info", {}),
                "season_context": raw_data.get("season_context", {}),
                "statistics": {},  # Initialize statistics
                "season_stats": raw_data.get("season_stats", {})  # Use provided season_stats
            }
            
            # Transform statistics if present
            if "statistics" in raw_data and raw_data["statistics"]:
                result["statistics"] = raw_data["statistics"]
                
            # Transform season_stats if not already present
            if not result["season_stats"] and "statistics" in raw_data:
                stats = raw_data["statistics"]
                result["season_stats"] = {
                    "points_per_game": stats.get("points", 0),
                    "wins": stats.get("wins", 0),
                    "losses": stats.get("losses", 0),
                    "field_goal_percentage": stats.get("fgp", "0"),
                    "three_point_percentage": stats.get("tpp", "0"),
                    "free_throw_percentage": stats.get("ftp", "0"),
                    "rebounds_per_game": stats.get("totReb", 0),
                    "assists_per_game": stats.get("assists", 0),
                    "steals_per_game": stats.get("steals", 0),
                    "blocks_per_game": stats.get("blocks", 0)
                }
            
            # Transform games if present
            if "games" in raw_data and raw_data["games"]:
                if isinstance(raw_data["games"], list):
                    result["games"] = raw_data["games"]
                elif isinstance(raw_data["games"], dict):
                    result["games"] = [raw_data["games"]]
                else:
                    result["games"] = []
            
            return result
            
        except Exception as e:
            logger.error(f"Error transforming team data: {str(e)}")
            return {"error": f"Failed to transform team data: {str(e)}"}

    @redis_cache(ttl=300, prefix="basketball_game")  # 5 minute cache for game data
    async def transform_game_data(
        self,
        raw_data: Dict[str, Any],
        required_data: List[str]
    ) -> Dict[str, Any]:
        """Transform basketball game data to common format"""
        try:
            return self._transform_game(raw_data)
        except Exception as e:
            logger.error(f"Error transforming basketball game data: {str(e)}")
            return {}

    def _transform_game(self, game: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a single basketball game to common format"""
        if not game:
            raise ValueError("No game data provided")
            
        # Validate required game fields
        required_fields = ["id", "date", "teams", "scores"]
        for field in required_fields:
            if field not in game:
                raise ValueError(f"Missing required game field: {field}")
                
        try:
            home_team = game.get("teams", {}).get("home", {})
            away_team = game.get("teams", {}).get("away", {})
            scores = game.get("scores", {})
            
            # Validate team IDs
            home_id = home_team.get("id")
            away_id = away_team.get("id")
            if home_id and not self._validate_team_id(home_id):
                logger.warning(f"Unknown home team ID: {home_id}")
            if away_id and not self._validate_team_id(away_id):
                logger.warning(f"Unknown away team ID: {away_id}")
                
            if not home_team or not away_team:
                raise ValueError("Missing team information in game data")
                
            return CommonGameInfo(
                id=game["id"],
                date=game["date"],
                home_team={
                    "id": home_team.get("id", ""),
                    "name": home_team.get("name", ""),
                    "code": home_team.get("code", ""),
                    "logo": home_team.get("logo", "")
                },
                away_team={
                    "id": away_team.get("id", ""),
                    "name": away_team.get("name", ""),
                    "code": away_team.get("code", ""),
                    "logo": away_team.get("logo", "")
                },
                scores={
                    "home": scores.get("home", {}).get("total", 0),
                    "away": scores.get("away", {}).get("total", 0),
                    "quarters": [
                        {
                            "home": scores.get("home", {}).get("quarter", {}).get(str(i), 0),
                            "away": scores.get("away", {}).get("quarter", {}).get(str(i), 0)
                        }
                        for i in range(1, 5)
                    ]
                },
                status={
                    "long": game.get("status", {}).get("long", ""),
                    "short": game.get("status", {}).get("short", "")
                }
            ).model_dump()
            
        except Exception as e:
            logger.error(f"Error transforming game data: {str(e)}")
            raise ValueError(f"Failed to transform game: {str(e)}")

    @redis_cache(ttl=3600, prefix="basketball_player")
    async def transform_player_data(
        self,
        raw_data: Dict[str, Any],
        required_data: List[str]
    ) -> Dict[str, Any]:
        """Transform basketball player data to common format"""
        try:
            # Handle error cases in raw_data
            if "error" in raw_data:
                return {"error": raw_data["error"]}
            
            # Extract statistics from raw_data
            statistics = raw_data.get("statistics", [])
            if not statistics:
                return {"error": "No player statistics found"}
            
            # Get player info from first game (they're all the same)
            first_game = statistics[0]
            player_info = first_game.get("player", {})
            team_info = first_game.get("team", {})
            
            # Validate required player fields
            if not player_info.get("id"):
                return {"error": "Invalid player data: missing player id"}
            
            # Calculate season averages
            total_games = len(statistics)
            total_points = sum(game.get("points", 0) for game in statistics)
            total_rebounds = sum(game.get("totReb", 0) for game in statistics)
            total_assists = sum(game.get("assists", 0) for game in statistics)
            total_fgm = sum(game.get("fgm", 0) for game in statistics)
            total_fga = sum(game.get("fga", 0) for game in statistics)
            total_ftm = sum(game.get("ftm", 0) for game in statistics)
            total_fta = sum(game.get("fta", 0) for game in statistics)
            total_tpm = sum(game.get("tpm", 0) for game in statistics)
            total_tpa = sum(game.get("tpa", 0) for game in statistics)
            
            # Build transformed data
            transformed = {
                "basic_info": {
                    "id": player_info.get("id"),
                    "name": f"{player_info.get('firstname', '')} {player_info.get('lastname', '')}".strip(),
                    "team": {
                        "id": team_info.get("id"),
                        "name": team_info.get("name"),
                        "nickname": team_info.get("nickname"),
                        "code": team_info.get("code")
                    }
                },
                "season_stats": {
                    "games_played": total_games,
                    "points_per_game": round(total_points / total_games, 1),
                    "rebounds_per_game": round(total_rebounds / total_games, 1),
                    "assists_per_game": round(total_assists / total_games, 1),
                    "field_goal_percentage": round(total_fgm / total_fga * 100, 1) if total_fga > 0 else 0,
                    "free_throw_percentage": round(total_ftm / total_fta * 100, 1) if total_fta > 0 else 0,
                    "three_point_percentage": round(total_tpm / total_tpa * 100, 1) if total_tpa > 0 else 0
                },
                "statistics": statistics
            }
            
            return transformed
            
        except Exception as e:
            logger.error(f"Error transforming basketball player data: {str(e)}")
            return {"error": f"Failed to transform player data: {str(e)}"}

    async def validate_data(self, data: TransformedSportData) -> bool:
        """Validate transformed basketball data"""
        try:
            if data.team_data:
                if "error" not in data.team_data:
                    assert "league_info" in data.team_data
                    assert "season_stats" in data.team_data
                
            if data.game_data:
                for game in data.game_data:
                    if "error" not in game:
                        assert "teams" in game
                        assert "score" in game
                    
            if data.player_data:
                for player_name, player_data in data.player_data.items():
                    if "error" not in player_data:
                        # Check for either statistics or error in player data
                        assert "statistics" in player_data or "error" in player_data
                        if "statistics" in player_data:
                            # Validate at least one game stat exists
                            assert len(player_data["statistics"]) > 0
                
            return True
            
        except AssertionError:
            logger.error("Invalid basketball data structure")
            return False
        except Exception as e:
            logger.error(f"Error validating basketball data: {str(e)}")
            return False 