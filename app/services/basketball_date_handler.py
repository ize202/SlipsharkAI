"""
NBA-specific date handling logic.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, List
from dataclasses import dataclass
from app.config import get_logger
from app.models.research_models import ClientMetadata
import pytz

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
    
    def _ensure_timezone_aware(self, date: datetime) -> datetime:
        """
        Ensure a datetime is timezone-aware, converting to UTC if naive
        
        Args:
            date: The datetime to check/convert
            
        Returns:
            Timezone-aware datetime in UTC
        """
        if date.tzinfo is None:
            return date.replace(tzinfo=timezone.utc)
        return date.astimezone(timezone.utc)
    
    def determine_season(self, date: datetime) -> str:
        """
        Determine the NBA season for a given date.
        NBA seasons span two calendar years (e.g., 2023-2024 season is "2023")
        
        Args:
            date: The date to determine season for
            
        Returns:
            Season year as string (e.g., "2023" for 2023-24 season)
        """
        # Ensure both dates are timezone-aware
        date = self._ensure_timezone_aware(date)
        current_date = datetime.now(timezone.utc)
        
        # If the date is in the future, use the appropriate season
        if date > current_date:
            # For future dates between January and June, use previous year
            if date.month <= 6:
                return str(date.year - 1)
            # For future dates between July and December, use current year
            return str(date.year)
        
        # For past/current dates
        if date.month <= 6:
            return str(date.year - 1)
        return str(date.year)
    
    def validate_game_date(self, date: datetime) -> bool:
        """
        Check if date falls within NBA season or near future
        
        Args:
            date: The date to validate
            
        Returns:
            True if date is valid for NBA queries
        """
        # Ensure both dates are timezone-aware
        date = self._ensure_timezone_aware(date)
        current_date = datetime.now(timezone.utc)
        
        # Allow queries up to next season's end
        season_year = self.determine_season(current_date)
        _, season_end = self.get_season_boundaries(season_year)
        
        # Don't allow queries more than 1 year in the past
        min_past_date = current_date.replace(
            year=current_date.year - 1
        )
        
        return min_past_date <= date <= season_end
    
    def is_playoff_period(self, date: datetime) -> bool:
        """Check if date falls in typical playoff period"""
        date = self._ensure_timezone_aware(date)
        return self.season_boundary.playoff_start_month <= date.month <= self.season_boundary.playoff_end_month
    
    def get_season_phase(self, date: datetime) -> str:
        """Get the phase of the season (preseason, regular, playoffs, offseason)"""
        date = self._ensure_timezone_aware(date)
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
            day=1,
            tzinfo=timezone.utc
        )
        season_end = datetime(
            year=season_year + 1,
            month=self.season_boundary.end_month,
            day=30,
            tzinfo=timezone.utc
        )
        return season_start, season_end

    async def resolve_date_reference(self, date_ref: str, client_metadata: ClientMetadata) -> List[datetime]:
        """
        Resolve a date reference into a list of actual dates
        
        Args:
            date_ref: Date reference string (e.g., "today", "next game", "last 5 games")
            client_metadata: Client metadata containing timezone info
            
        Returns:
            List of resolved dates
        """
        try:
            # Get client's timezone
            tz = pytz.timezone(client_metadata.timezone)
            now = datetime.now(tz)
            now = self._ensure_timezone_aware(now)
            
            # Get current season
            current_season = self.determine_season(now)
            season_start, season_end = self.get_season_boundaries(current_season)
            
            # Handle special cases first
            if date_ref.lower() in ["today", "tonight"]:
                return [now]
            elif date_ref.lower() == "tomorrow":
                tomorrow = now + timedelta(days=1)
                if tomorrow <= season_end:
                    return [tomorrow]
                return [now]  # Fallback to today if tomorrow is beyond season
            elif date_ref.lower() == "yesterday":
                yesterday = now - timedelta(days=1)
                if yesterday >= season_start:
                    return [yesterday]
                return [now]  # Fallback to today if yesterday is before season
            elif "recent" in date_ref.lower():
                # For recent, look at last 14 days within season
                dates = []
                for i in range(14):
                    date = now - timedelta(days=i)
                    if season_start <= date <= season_end:
                        dates.append(date)
                return dates or [now]
            elif "last" in date_ref.lower():
                # Handle "last X games" or "last X days"
                try:
                    num = int(''.join(filter(str.isdigit, date_ref)))
                    if "games" in date_ref.lower():
                        # For last X games, look back up to 30 days within season
                        dates = []
                        for i in range(30):
                            date = now - timedelta(days=i)
                            if season_start <= date <= season_end:
                                dates.append(date)
                        return dates or [now]
                    else:
                        # For last X days, stay within season boundaries
                        dates = []
                        for i in range(num):
                            date = now - timedelta(days=i)
                            if season_start <= date <= season_end:
                                dates.append(date)
                        return dates or [now]
                except ValueError:
                    # If no number found, default to last 7 days within season
                    dates = []
                    for i in range(7):
                        date = now - timedelta(days=i)
                        if season_start <= date <= season_end:
                            dates.append(date)
                    return dates or [now]
            elif "next" in date_ref.lower():
                # Handle "next game" or "next X days"
                try:
                    num = int(''.join(filter(str.isdigit, date_ref)))
                    if "games" in date_ref.lower():
                        # For next X games, look ahead up to 30 days within season
                        dates = []
                        for i in range(30):
                            date = now + timedelta(days=i)
                            if date <= season_end:
                                dates.append(date)
                        return dates or [now]
                    else:
                        # For next X days, stay within season boundaries
                        dates = []
                        for i in range(num):
                            date = now + timedelta(days=i)
                            if date <= season_end:
                                dates.append(date)
                        return dates or [now]
                except ValueError:
                    # If no number found, default to next 7 days within season
                    dates = []
                    for i in range(7):
                        date = now + timedelta(days=i)
                        if date <= season_end:
                            dates.append(date)
                    return dates or [now]
            elif "upcoming" in date_ref.lower():
                # Return next 7 days within season boundaries
                dates = []
                for i in range(7):
                    date = now + timedelta(days=i)
                    if date <= season_end:
                        dates.append(date)
                return dates or [now]
            elif "head to head" in date_ref.lower():
                # For head to head, look at current season only
                days = (season_end - season_start).days
                return [season_start + timedelta(days=i) for i in range(days)]
            elif "matchups" in date_ref.lower():
                try:
                    num = int(''.join(filter(str.isdigit, date_ref)))
                    # Look at last 60 days within season
                    dates = []
                    for i in range(60):
                        date = now - timedelta(days=i)
                        if season_start <= date <= season_end:
                            dates.append(date)
                    return dates or [now]
                except ValueError:
                    # Default to last 30 days within season
                    dates = []
                    for i in range(30):
                        date = now - timedelta(days=i)
                        if season_start <= date <= season_end:
                            dates.append(date)
                    return dates or [now]
            elif "this season" in date_ref.lower():
                # Return all dates in current season
                days = (season_end - season_start).days
                return [season_start + timedelta(days=i) for i in range(days)]
            else:
                # Default to today if date reference not recognized
                logger.warning(f"Unrecognized date reference: {date_ref}, defaulting to today")
                return [now]
                
        except Exception as e:
            logger.error(f"Error resolving date reference '{date_ref}': {str(e)}")
            # Return today's date as fallback
            return [datetime.now(timezone.utc)] 