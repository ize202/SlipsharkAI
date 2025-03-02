"""
NBA-specific date handling logic.
"""

from datetime import datetime
from typing import Optional, Tuple
from dataclasses import dataclass
from app.config import get_logger

logger = get_logger(__name__)

@dataclass
class NBASeasonBoundary:
    """Represents NBA season boundary dates"""
    start_month: int = 10  # October
    end_month: int = 6    # June
    playoff_start_month: int = 4  # April
    playoff_end_month: int = 6    # June

class BasketballDateHandler:
    """Handler for NBA-specific date operations"""
    
    def __init__(self):
        self.season_boundary = NBASeasonBoundary()
    
    def determine_season(self, date: datetime) -> str:
        """
        Determine the NBA season for a given date.
        NBA seasons span two calendar years (e.g., 2023-2024 season is "2023")
        
        Args:
            date: The date to determine season for
            
        Returns:
            Season year as string (e.g., "2023" for 2023-24 season)
        """
        # If date is between July and December, use that year
        # If date is between January and June, use previous year
        year = date.year if date.month > 6 else date.year - 1
        return str(year)
    
    def validate_game_date(self, date: datetime) -> bool:
        """
        Check if date falls within NBA season or near future
        
        Args:
            date: The date to validate
            
        Returns:
            True if date is valid for NBA queries
        """
        current_date = datetime.now()
        
        # Allow queries up to next season
        max_future_date = current_date.replace(
            year=current_date.year + 1,
            month=12,
            day=31
        )
        
        # Don't allow queries more than 1 year in the past
        min_past_date = current_date.replace(
            year=current_date.year - 1
        )
        
        return min_past_date <= date <= max_future_date
    
    def is_playoff_period(self, date: datetime) -> bool:
        """Check if date falls in typical playoff period"""
        return self.season_boundary.playoff_start_month <= date.month <= self.season_boundary.playoff_end_month
    
    def get_season_phase(self, date: datetime) -> str:
        """Get the phase of the season (preseason, regular, playoffs, offseason)"""
        month = date.month
        
        if month == self.season_boundary.start_month:
            return "preseason"
        elif self.is_playoff_period(date):
            return "playoffs"
        elif month == 7 or month == 8 or month == 9:
            return "offseason"
        else:
            return "regular"
    
    def get_season_boundaries(self, season: str) -> Tuple[datetime, datetime]:
        """
        Get start and end dates for a season
        
        Args:
            season: Season year (e.g., "2023" for 2023-24 season)
            
        Returns:
            Tuple of (season_start, season_end) dates
        """
        season_year = int(season)
        season_start = datetime(
            year=season_year,
            month=self.season_boundary.start_month,
            day=1
        )
        season_end = datetime(
            year=season_year + 1,
            month=self.season_boundary.end_month,
            day=30
        )
        return season_start, season_end 