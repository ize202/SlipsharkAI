from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class BetHistory(BaseModel):
    """User's betting history"""
    user_id: str
    sport: str
    bet_type: str
    odds: float
    stake: float
    placed_at: datetime
    result: Optional[str] = None
    payout: Optional[float] = None

class UserStats(BaseModel):
    """User's betting statistics"""
    user_id: str
    sport: str
    total_bets: int
    win_rate: float
    avg_odds: float
    profit_loss: float
    last_updated: datetime

class UserPreferences(BaseModel):
    """User's betting preferences"""
    user_id: str
    preferred_sports: List[str] = Field(default_factory=list)
    preferred_bet_types: List[str] = Field(default_factory=list)
    max_stake: Optional[float] = None
    risk_tolerance: Optional[float] = None
    notification_preferences: Dict[str, bool] = Field(default_factory=dict) 