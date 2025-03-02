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
        r"yesterday": -1,
        r"tomorrow": 1,
        r"next week": 7,
        r"last week": -7,
        r"next month": 30,
        r"last month": -30,
        r"today|tonight": 0,
    }
    
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
        for pattern, days_delta in self.RELATIVE_DATE_PATTERNS.items():
            if re.match(pattern, date_reference):
                return current_time + timedelta(days=days_delta)
        
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