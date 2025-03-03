from typing import Optional
from langfuse import Langfuse
from app.config import get_logger, get_settings

logger = get_logger(__name__)
settings = get_settings()

_langfuse_client = None

def get_langfuse_client() -> Langfuse:
    """Get or create Langfuse client instance"""
    global _langfuse_client
    
    if not _langfuse_client:
        try:
            _langfuse_client = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST
            )
            logger.info("Langfuse client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Langfuse client: {str(e)}")
            # Return a mock client that implements the required interface
            return type(
                "MockLangfuse",
                (),
                {
                    "span": lambda *args, **kwargs: type(
                        "MockSpan",
                        (),
                        {
                            "__enter__": lambda self: self,
                            "__exit__": lambda *args: None,
                            "error": lambda *args: None,
                            "ok": lambda *args: None
                        }
                    )()
                }
            )()
    
    return _langfuse_client 