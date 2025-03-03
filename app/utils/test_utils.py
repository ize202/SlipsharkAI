"""Test utilities for the application."""
from app.models.research_models import ClientMetadata

def create_test_metadata() -> ClientMetadata:
    """Create test client metadata"""
    return ClientMetadata(
        user_id="test_user",
        timezone="America/New_York",
        preferences={
            "favorite_teams": ["Los Angeles Lakers", "Boston Celtics"],
            "favorite_players": ["LeBron James", "Jayson Tatum"]
        }
    ) 