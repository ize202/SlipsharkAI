"""
Logging configuration for the Sports Research API.
Provides structured logging with consistent formatting and levels.
"""
import os
import logging
import json
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

# Environment variables for logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
ENABLE_JSON_LOGGING = os.getenv("ENABLE_JSON_LOGGING", "false").lower() == "true"

# Map string log levels to their numeric values
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs logs as JSON objects.
    This is particularly useful for log aggregation services.
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
            
        # Add extra fields if present
        if hasattr(record, "extra") and record.extra:
            log_record.update(record.extra)
            
        return json.dumps(log_record)

class StructuredLoggerAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds structured context to log messages.
    Allows adding request_id, user_id, and other context to logs.
    """
    def process(self, msg, kwargs):
        # Ensure extra dict exists
        if 'extra' not in kwargs:
            kwargs['extra'] = {}
        
        # Add adapter's extra context to the kwargs extra
        if self.extra:
            for key, value in self.extra.items():
                kwargs['extra'][key] = value
                
        return msg, kwargs

def get_logger(name: str, extra: Optional[Dict[str, Any]] = None) -> StructuredLoggerAdapter:
    """
    Get a configured logger with the specified name and extra context.
    
    Args:
        name: The name of the logger
        extra: Optional extra context to include in all log messages
        
    Returns:
        A configured StructuredLoggerAdapter
    """
    logger = logging.getLogger(name)
    return StructuredLoggerAdapter(logger, extra or {})

def configure_logging():
    """
    Configure the root logger with appropriate handlers and formatters.
    Should be called once at application startup.
    """
    # Get the root logger
    root_logger = logging.getLogger()
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set the log level
    level = LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO)
    root_logger.setLevel(level)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    
    # Choose formatter based on environment
    if ENABLE_JSON_LOGGING:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            '%Y-%m-%d %H:%M:%S'
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Log the configuration
    root_logger.info(f"Logging configured with level: {LOG_LEVEL}")
    root_logger.info(f"JSON logging: {'enabled' if ENABLE_JSON_LOGGING else 'disabled'}")
    
    return root_logger 