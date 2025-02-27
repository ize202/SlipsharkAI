"""
Configuration package for the sports betting AI assistant.
Contains initialization for external services and configuration variables.
"""

# Import auth module to initialize API key validation
from . import auth 

# Export the get_logger function
from .logging_config import get_logger, configure_logging 