from typing import List, Optional, Dict, Any
import os
import logging
from datetime import datetime, timedelta, UTC
from supabase import create_client, Client
from langfuse.decorators import observe
from app.models.betting_models import BetHistory, UserStats, UserPreferences
from ..utils.cache import redis_cache, memory_cache

# Set up logging
logger = logging.getLogger(__name__)

class SupabaseService:
    """Service for interacting with Supabase database"""
    
    def __init__(self):
        """Initialize the Supabase service with API key and configuration"""
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY environment variables must be set")
        
        self.client = create_client(self.url, self.key)
    
    # Cache bet history for 15 minutes
    @redis_cache(ttl=900, prefix="supabase_bet_history")
    @observe(name="supabase_get_bet_history")
    async def get_bet_history(self, user_id: str, days_back: int = 30) -> List[BetHistory]:
        """Get betting history for a user within the specified time range"""
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days_back)
            response = await self.client.table("bet_details") \
                .select("*") \
                .eq("user_id", user_id) \
                .gte("placed_at", cutoff_date.isoformat()) \
                .execute()
            
            return [BetHistory(**bet) for bet in response.data]
                
        except Exception as e:
            logger.error(f"Error fetching bet history: {str(e)}")
            raise Exception(f"Error fetching bet history: {str(e)}")
    
    # Cache user preferences for 1 hour
    @redis_cache(ttl=3600, prefix="supabase_user_prefs")
    @observe(name="supabase_get_user_preferences")
    async def get_user_preferences(self, user_id: str) -> UserPreferences:
        """Get user betting preferences"""
        try:
            response = await self.client.table("user_preferences") \
                .select("*") \
                .eq("user_id", user_id) \
                .execute()
            
            if not response.data:
                raise Exception(f"No preferences found for user {user_id}")
            
            return UserPreferences(**response.data[0])
                
        except Exception as e:
            logger.error(f"Error fetching user preferences: {str(e)}")
            raise Exception(f"Error fetching user preferences: {str(e)}")
    
    # Cache user stats for 30 minutes
    @redis_cache(ttl=1800, prefix="supabase_user_stats")
    @observe(name="supabase_get_user_stats")
    async def get_user_stats(self, user_id: str) -> List[UserStats]:
        """Get user betting statistics"""
        try:
            response = await self.client.table("user_stats") \
                .select("*") \
                .eq("user_id", user_id) \
                .execute()
            
            return [UserStats(**stat) for stat in response.data]
                
        except Exception as e:
            logger.error(f"Error fetching user stats: {str(e)}")
            raise Exception(f"Error fetching user stats: {str(e)}")
    
    # Cache user bets for 15 minutes
    @redis_cache(ttl=900, prefix="supabase_user_bets")
    @observe(name="supabase_get_user_bets")
    async def get_user_bets(
        self,
        user_id: str,
        sport: str = "basketball",
        days_back: int = 30
    ) -> List[BetHistory]:
        """Get user bets for a specific sport"""
        try:
            cutoff_date = datetime.now(UTC) - timedelta(days=days_back)
            response = await self.client.table("bet_details") \
                .select("*") \
                .eq("user_id", user_id) \
                .eq("sport", sport) \
                .gte("placed_at", cutoff_date.isoformat()) \
                .execute()
            
            return [BetHistory(**bet) for bet in response.data]
                
        except Exception as e:
            logger.error(f"Error fetching user bets: {str(e)}")
            raise Exception(f"Error fetching user bets: {str(e)}")
    
    # Cache similar bets for 1 hour
    @redis_cache(ttl=3600, prefix="supabase_similar_bets")
    @observe(name="supabase_get_similar_bets")
    async def get_similar_bets(
        self,
        sport: str,
        bet_type: str,
        days_back: int = 30,
        min_odds: Optional[float] = None,
        max_odds: Optional[float] = None
    ) -> List[BetHistory]:
        """Get similar bets across all users"""
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
            response = await query.execute()
            
            # Convert response to BetHistory objects
            return [BetHistory(**bet) for bet in response.data]
            
        except Exception as e:
            logger.error(f"Error getting similar bets: {str(e)}", exc_info=True)
            raise Exception(f"Error getting similar bets: {str(e)}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass 