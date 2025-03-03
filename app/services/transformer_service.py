from typing import Dict, Any, List, Optional, Type
from app.transformers.base import SportDataTransformer, TransformedSportData
from app.transformers.basketball import BasketballTransformer
from app.config import get_logger
from app.utils.langfuse import get_langfuse_client
from langfuse.decorators import observe

logger = get_logger(__name__)
langfuse = get_langfuse_client()

class TransformerService:
    """Service to coordinate sport-specific data transformers"""
    
    def __init__(self):
        self._transformers: Dict[str, SportDataTransformer] = {
            "basketball": BasketballTransformer(),
            # Add other sport transformers here as they are implemented
        }
        
    @observe(name="transform_sport_data")
    async def transform_data(
        self,
        sport: str,
        raw_data: Dict[str, Any],
        required_data: List[str],
        trace_id: Optional[str] = None
    ) -> TransformedSportData:
        """Transform raw sport data into common format"""
        try:
            transformer = self._get_transformer(sport)
            if not transformer:
                logger.error(f"No transformer found for sport: {sport}")
                return TransformedSportData(
                    sport_type=sport,
                    team_data={"error": f"No transformer found for sport: {sport}", "statistics": {}},
                    game_data=[],
                    player_data={}
                )
            
            transformed_data = TransformedSportData(sport_type=sport)
            has_error = False
            error_messages = []
            
            # Transform team data if present
            if "team_data" in raw_data:
                transformed_teams = {}
                for team_name, team_data in raw_data["team_data"].items():
                    team_transformed = await transformer.transform_team_data(
                        team_data,
                        required_data
                    )
                    if "error" in team_transformed:
                        error_messages.append(f"Team {team_name} data: {team_transformed['error']}")
                        has_error = True
                        # Ensure we have a statistics field even in error case
                        team_transformed["statistics"] = {}
                    transformed_teams[team_name] = team_transformed
                transformed_data.team_data = transformed_teams
            
            # Transform game data if present
            if "game_data" in raw_data:
                game_data = await transformer.transform_game_data(
                    raw_data["game_data"],
                    required_data
                )
                if "error" in game_data:
                    error_messages.append(f"Game data: {game_data['error']}")
                    has_error = True
                    transformed_data.game_data = [{"error": game_data["error"]}]
                else:
                    transformed_data.game_data = [game_data]
            
            # Transform player data if present
            if "player_data" in raw_data:
                transformed_players = {}
                for player_name, player_data in raw_data["player_data"].items():
                    player_transformed = await transformer.transform_player_data(
                        player_data,
                        required_data
                    )
                    if "error" in player_transformed:
                        error_messages.append(f"Player {player_name} data: {player_transformed['error']}")
                        has_error = True
                    transformed_players[player_name] = player_transformed
                transformed_data.player_data = transformed_players
            
            # Validate transformed data
            is_valid = await transformer.validate_data(transformed_data)
            if not is_valid:
                logger.error("Data validation failed")
                error_msg = "Data validation failed"
                if error_messages:
                    error_msg = "Multiple validation errors occurred:\n" + "\n".join(error_messages)
                
                return TransformedSportData(
                    sport_type=sport,
                    team_data={"error": error_msg, "statistics": {}},
                    game_data=[],
                    player_data={}
                )
            
            return transformed_data
            
        except Exception as e:
            error_msg = f"Error transforming {sport} data: {str(e)}"
            logger.error(error_msg)
            return TransformedSportData(
                sport_type=sport,
                team_data={"error": error_msg, "statistics": {}},
                game_data=[],
                player_data={}
            )
    
    def _get_transformer(self, sport: str) -> Optional[SportDataTransformer]:
        """Get the appropriate transformer for a sport"""
        return self._transformers.get(sport.lower()) 