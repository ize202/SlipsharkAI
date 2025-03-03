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

logger = get_logger(__name__)

class BasketballTransformer(SportDataTransformer):
    """Transformer for basketball data"""
    
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
            
            player_info = raw_data.get("player_info")
            if not player_info:
                return {"error": "No player information found"}
            
            # Validate required player fields
            if not player_info.get("id") or not player_info.get("name"):
                return {"error": "Invalid player data: missing required fields"}
            
            statistics = raw_data.get("statistics", {})
            
            transformed = {
                "basic_info": {
                    "id": player_info.get("id"),
                    "name": player_info.get("firstname", "") + " " + player_info.get("lastname", ""),
                    "jersey": player_info.get("jersey", ""),
                    "position": player_info.get("position", ""),
                    "height": player_info.get("height", {}).get("meters", ""),
                    "weight": player_info.get("weight", {}).get("kilograms", ""),
                    "birth": {
                        "date": player_info.get("birth", {}).get("date", ""),
                        "country": player_info.get("birth", {}).get("country", "")
                    },
                    "college": player_info.get("college", ""),
                    "draft": {
                        "year": player_info.get("draft", {}).get("year", ""),
                        "round": player_info.get("draft", {}).get("round", ""),
                        "pick": player_info.get("draft", {}).get("pick", "")
                    }
                },
                
                "season_stats": {
                    "games_played": statistics.get("games_played", 0),
                    "minutes_per_game": statistics.get("minutes_per_game", "0.0"),
                    "points_per_game": statistics.get("points_per_game", "0.0"),
                    "rebounds_per_game": statistics.get("rebounds_per_game", "0.0"),
                    "assists_per_game": statistics.get("assists_per_game", "0.0"),
                    "steals_per_game": statistics.get("steals_per_game", "0.0"),
                    "blocks_per_game": statistics.get("blocks_per_game", "0.0"),
                    "field_goal_percentage": statistics.get("field_goal_percentage", "0.0"),
                    "three_point_percentage": statistics.get("three_point_percentage", "0.0"),
                    "free_throw_percentage": statistics.get("free_throw_percentage", "0.0")
                }
            }
            
            if "recent_games" in required_data and "games" in raw_data:
                transformed["recent_games"] = []
                for game in raw_data["games"][:5]:
                    try:
                        transformed_game = self._transform_game(game)
                        transformed["recent_games"].append(transformed_game)
                    except Exception as e:
                        logger.error(f"Error transforming game in player recent games: {str(e)}")
                        continue
            
            return transformed
            
        except Exception as e:
            logger.error(f"Error transforming basketball player data: {str(e)}")
            return {"error": f"Failed to transform player data: {str(e)}"}

    async def validate_data(self, data: TransformedSportData) -> bool:
        """Validate transformed basketball data"""
        try:
            if data.team_data:
                assert "basic_info" in data.team_data
                assert "league_info" in data.team_data
                assert "season_stats" in data.team_data
                
            if data.game_data:
                for game in data.game_data:
                    assert "teams" in game
                    assert "score" in game
                    
            if data.player_data:
                assert "basic_info" in data.player_data
                assert "season_stats" in data.player_data
                
            return True
            
        except AssertionError:
            logger.error("Invalid basketball data structure")
            return False
        except Exception as e:
            logger.error(f"Error validating basketball data: {str(e)}")
            return False 