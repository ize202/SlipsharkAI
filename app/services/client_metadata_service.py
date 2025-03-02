"""
Service for handling client metadata operations and timezone conversions.
"""

from datetime import datetime
import pytz
from typing import Optional
from app.models.research_models import ClientMetadata
from app.config import get_logger

logger = get_logger(__name__)

class ClientMetadataService:
    """Service for handling client metadata operations"""
    
    def __init__(self):
        self._default_timezone = "UTC"
        self._default_locale = "en-US"
    
    def create_metadata(
        self,
        timestamp: Optional[datetime] = None,
        timezone: Optional[str] = None,
        locale: Optional[str] = None
    ) -> ClientMetadata:
        """
        Create a new ClientMetadata instance with validation
        
        Args:
            timestamp: Optional timestamp (defaults to current UTC time)
            timezone: Optional timezone string (defaults to UTC)
            locale: Optional locale string (defaults to en-US)
            
        Returns:
            ClientMetadata instance
        """
        try:
            # Validate timezone
            if timezone:
                pytz.timezone(timezone)
            else:
                timezone = self._default_timezone
                
            # Use provided timestamp or current UTC time
            if not timestamp:
                timestamp = datetime.utcnow()
                
            # Use provided locale or default
            if not locale:
                locale = self._default_locale
                
            return ClientMetadata(
                timestamp=timestamp,
                timezone=timezone,
                locale=locale
            )
            
        except pytz.exceptions.UnknownTimeZoneError as e:
            logger.error(f"Invalid timezone provided: {timezone}")
            # Fall back to UTC
            return ClientMetadata(
                timestamp=timestamp or datetime.utcnow(),
                timezone=self._default_timezone,
                locale=locale or self._default_locale
            )
    
    def convert_to_client_time(
        self,
        utc_time: datetime,
        client_metadata: ClientMetadata
    ) -> datetime:
        """
        Convert a UTC timestamp to the client's timezone
        
        Args:
            utc_time: UTC datetime to convert
            client_metadata: Client metadata containing timezone
            
        Returns:
            datetime in client's timezone
        """
        if not utc_time.tzinfo:
            utc_time = pytz.UTC.localize(utc_time)
            
        client_tz = pytz.timezone(client_metadata.timezone)
        return utc_time.astimezone(client_tz)
    
    def get_current_time_for_client(
        self,
        client_metadata: ClientMetadata
    ) -> datetime:
        """
        Get the current time in the client's timezone
        
        Args:
            client_metadata: Client metadata containing timezone
            
        Returns:
            Current datetime in client's timezone
        """
        return self.convert_to_client_time(
            datetime.utcnow(),
            client_metadata
        ) 