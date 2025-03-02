"""
Service for handling common date operations across all sports services.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from app.models.research_models import ClientMetadata
import pytz
import re

class DateResolutionService:
    """Base service for handling common date operations"""
    
    RELATIVE_DATE_PATTERNS = {
        # Today/Tonight variations
        r"today|tonight|this evening|rn|right now|now": 0,
        
        # Tomorrow variations
        r"tomorrow|tmr|tmrw|next day": 1,
        
        # Yesterday variations
        r"yesterday|yest|previous day": -1,
        
        # This week variations
        r"this week|current week": 0,
        
        # Next week variations
        r"next week|upcoming week|following week": 7,
        
        # Last week variations
        r"last week|past week|previous week": -7,
        
        # Day-specific patterns (relative to current week)
        r"this (monday|mon)": "next_monday",
        r"this (tuesday|tues|tue)": "next_tuesday",
        r"this (wednesday|wed)": "next_wednesday",
        r"this (thursday|thurs|thu)": "next_thursday",
        r"this (friday|fri)": "next_friday",
        r"this (saturday|sat)": "next_saturday",
        r"this (sunday|sun)": "next_sunday",
        
        # Next specific day
        r"next (monday|mon)": "next_monday",
        r"next (tuesday|tues|tue)": "next_tuesday",
        r"next (wednesday|wed)": "next_wednesday",
        r"next (thursday|thurs|thu)": "next_thursday",
        r"next (friday|fri)": "next_friday",
        r"next (saturday|sat)": "next_saturday",
        r"next (sunday|sun)": "next_sunday",
        
        # Month-based patterns
        r"next month": 30,
        r"last month": -30,
        r"this month": 0,
        
        # Common betting timeframes
        r"tonight['']s games?": 0,
        r"games? today": 0,
        r"games? tomorrow": 1,
        r"games? tonight": 0,
        
        # Weekend references
        r"this weekend": "next_weekend",
        r"next weekend": "next_weekend",
        r"last weekend": "last_weekend",
        
        # Specific timeframes
        r"in (\d+) days?": "days_ahead",
        r"(\d+) days? from now": "days_ahead",
        r"(\d+) days? ago": "days_ago",
        r"(\d+) weeks? from now": "weeks_ahead",
        r"(\d+) weeks? ago": "weeks_ago",
    }
    
    def _get_next_day_of_week(self, current_date: datetime, target_day: int) -> datetime:
        """Get the next occurrence of a specific day of the week"""
        days_ahead = target_day - current_date.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        return current_date + timedelta(days=days_ahead)
    
    def _get_last_day_of_week(self, current_date: datetime, target_day: int) -> datetime:
        """Get the last occurrence of a specific day of the week"""
        days_behind = current_date.weekday() - target_day
        if days_behind <= 0:  # Target day hasn't happened this week yet
            days_behind += 7
        return current_date - timedelta(days=days_behind)
    
    def _handle_special_patterns(
        self,
        pattern: str,
        match: re.Match,
        current_date: datetime
    ) -> Optional[datetime]:
        """Handle special date patterns that need custom logic"""
        
        # Handle "next_[day]" patterns
        day_mapping = {
            "monday": 0, "mon": 0,
            "tuesday": 1, "tues": 1, "tue": 1,
            "wednesday": 2, "wed": 2,
            "thursday": 3, "thurs": 3, "thu": 3,
            "friday": 4, "fri": 4,
            "saturday": 5, "sat": 5,
            "sunday": 6, "sun": 6
        }
        
        if pattern.startswith("next_"):
            day_name = pattern.split("_")[1]
            target_day = day_mapping.get(day_name)
            if target_day is not None:
                return self._get_next_day_of_week(current_date, target_day)
                
        # Handle weekend patterns
        if pattern == "next_weekend":
            # Get next Saturday
            next_saturday = self._get_next_day_of_week(current_date, 5)
            return next_saturday
            
        if pattern == "last_weekend":
            # Get last Saturday
            last_saturday = self._get_last_day_of_week(current_date, 5)
            return last_saturday
            
        # Handle "X days/weeks ahead/ago" patterns
        if pattern in ["days_ahead", "days_ago", "weeks_ahead", "weeks_ago"]:
            number = int(match.group(1))
            multiplier = 7 if "weeks" in pattern else 1
            delta = number * multiplier
            if "ago" in pattern:
                delta = -delta
            return current_date + timedelta(days=delta)
            
        return None
    
    def is_relative_date(self, date_reference: str) -> bool:
        """Check if a date reference is relative"""
        if not date_reference:
            return False
            
        date_reference = date_reference.lower().strip()
        return any(
            re.match(pattern, date_reference)
            for pattern in self.RELATIVE_DATE_PATTERNS.keys()
        )
    
    def resolve_relative_date(
        self,
        date_reference: str,
        client_metadata: ClientMetadata
    ) -> Optional[datetime]:
        """
        Convert relative date references to actual dates based on client's timezone
        
        Args:
            date_reference: String reference like "tomorrow", "next week"
            client_metadata: Client metadata containing timezone info
            
        Returns:
            Resolved datetime or None if can't resolve
        """
        if not date_reference:
            return None
            
        date_reference = date_reference.lower().strip()
        
        # Get current time in client's timezone
        client_tz = pytz.timezone(client_metadata.timezone)
        current_time = datetime.now(client_tz)
        
        # Try to match against relative patterns
        for pattern, value in self.RELATIVE_DATE_PATTERNS.items():
            match = re.match(pattern, date_reference)
            if match:
                if isinstance(value, int):
                    return current_time + timedelta(days=value)
                elif isinstance(value, str):
                    return self._handle_special_patterns(value, match, current_time)
        
        return None
    
    def format_date_for_api(self, date: datetime) -> str:
        """Format datetime object for API calls"""
        return date.strftime("%Y-%m-%d")
    
    def parse_api_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string from API response"""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            return None 