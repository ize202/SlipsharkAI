from typing import Optional, Dict, Any, List
import os
import logging
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from langfuse.decorators import observe
from supabase import create_client, Client

# Set up logging
logger = logging.getLogger(__name__)

class BetHistory(BaseModel):
    """User's betting history from Supabase"""
    entry_id: str
    bet_type: str
    sport: str
    game_id: str
    odds: float
    boost_applied: bool
    boost_percentage: Optional[float]
    metadata: Dict[str, Any]
    created_at: datetime

class UserStats(BaseModel):
    """User's betting statistics from Supabase"""
    user_id: str
    entry_type: str
    sport: str
    period: str  # all_time, last_month, last_week
    total_entries: int
    won_entries: int
    total_stake: float
    total_payout: float
    roi: float
    updated_at: datetime

class SupabaseService:
    """Service for interacting with Supabase"""
    
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")
        
        self.client: Client = create_client(self.url, self.key)
    
    @observe(name="supabase_get_user_bets")
    async def get_user_bets(
        self,
        user_id: str,
        sport: str = "basketball",
        days_back: int = 30
    ) -> List[BetHistory]:
        """Get user's betting history for a specific sport"""
        try:
            # Calculate the date range
            start_date = datetime.now() - timedelta(days=days_back)
            
            # Query bet_details table
            response = self.client.table("bet_details").select("*").eq("sport", sport)\
                .gte("created_at", start_date.isoformat())\
                .execute()
            
            # Convert response to BetHistory objects
            bets = []
            for bet_data in response.data:
                bets.append(BetHistory(**bet_data))
            
            return bets
            
        except Exception as e:
            logger.error(f"Error getting user bets: {str(e)}", exc_info=True)
            raise
    
    @observe(name="supabase_get_user_stats")
    async def get_user_stats(
        self,
        user_id: str,
        sport: str = "basketball"
    ) -> List[UserStats]:
        """Get user's betting statistics for a specific sport"""
        try:
            # Query user_stats table
            response = self.client.table("user_stats").select("*")\
                .eq("user_id", user_id)\
                .eq("sport", sport)\
                .execute()
            
            # Convert response to UserStats objects
            stats = []
            for stat_data in response.data:
                stats.append(UserStats(**stat_data))
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting user stats: {str(e)}", exc_info=True)
            raise
    
    @observe(name="supabase_get_similar_bets")
    async def get_similar_bets(
        self,
        sport: str,
        bet_type: str,
        days_back: int = 30,
        min_odds: Optional[float] = None,
        max_odds: Optional[float] = None
    ) -> List[BetHistory]:
        """Get similar bets from all users for analysis"""
        try:
            # Calculate the date range
            start_date = datetime.now() - timedelta(days=days_back)
            
            # Start building the query
            query = self.client.table("bet_details").select("*")\
                .eq("sport", sport)\
                .eq("bet_type", bet_type)\
                .gte("created_at", start_date.isoformat())
            
            # Add odds filters if provided
            if min_odds is not None:
                query = query.gte("odds", min_odds)
            if max_odds is not None:
                query = query.lte("odds", max_odds)
            
            # Execute query
            response = query.execute()
            
            # Convert response to BetHistory objects
            bets = []
            for bet_data in response.data:
                bets.append(BetHistory(**bet_data))
            
            return bets
            
        except Exception as e:
            logger.error(f"Error getting similar bets: {str(e)}", exc_info=True)
            raise 