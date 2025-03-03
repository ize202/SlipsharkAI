"""
Configuration package for the sports betting AI assistant.
Contains initialization for external services and configuration variables.
"""

# Import auth module to initialize API key validation
from . import auth 

# Export the get_logger function
from .logging_config import get_logger, configure_logging 

import os
import logging
from typing import Dict, Any, Optional
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings"""
    
    # API Keys and Secrets
    LANGFUSE_PUBLIC_KEY: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    LANGFUSE_SECRET_KEY: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    LANGFUSE_HOST: str = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    
    # Redis Configuration
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    REDIS_TTL: int = int(os.getenv("REDIS_TTL", "3600"))
    
    # API Sports Configuration
    API_SPORTS_KEY: str = os.getenv("API_SPORTS_KEY", "")
    API_SPORTS_HOST: str = os.getenv("API_SPORTS_HOST", "v1.basketball.api-sports.io")
    
    # Perplexity Configuration
    PERPLEXITY_API_KEY: str = os.getenv("PERPLEXITY_API_KEY", "")
    
    # Supabase Configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()

def get_logger(name: str, extra: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """Get a logger instance with the specified name and optional extra fields"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(get_settings().LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    logger.setLevel(get_settings().LOG_LEVEL)
    
    if extra:
        logger = logging.LoggerAdapter(logger, extra)
    
    return logger 