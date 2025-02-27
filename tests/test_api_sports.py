import asyncio
import logging
import os
from app.services.api_sports_basketball import APISportsBasketballService

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

async def test_api_sports():
    """Test main functionality of the API Sports service"""
    logger.info("Starting API Sports service test")
    
    if not os.getenv("API_SPORTS_KEY"):
        logger.error("API_SPORTS_KEY environment variable not set")
        return
    
    async with APISportsBasketballService() as service:
        try:
            # Test team stats
            logger.info("Testing get_team_stats for Lakers...")
            stats = await service.get_team_stats('Lakers')
            logger.info(f"Got team stats: {stats}")
            
            # Test upcoming games
            logger.info("Testing get_upcoming_games for Lakers...")
            games = await service.get_upcoming_games('Lakers')
            logger.info(f"Got {len(games)} upcoming games")
            
            # Test head to head
            logger.info("Testing get_head_to_head for Lakers vs Warriors...")
            h2h = await service.get_head_to_head('Lakers', 'Warriors')
            logger.info(f"Got {len(h2h)} head to head games")
            
        except Exception as e:
            logger.error(f"Error during testing: {str(e)}")
            raise

if __name__ == "__main__":
    asyncio.run(test_api_sports()) 