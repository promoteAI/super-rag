

"""
OpenTelemetry instrumentation for FastAPI and SQLAlchemy.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Try to import optional instrumentors
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FASTAPI_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    FASTAPI_INSTRUMENTATION_AVAILABLE = False

try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    SQLALCHEMY_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    SQLALCHEMY_INSTRUMENTATION_AVAILABLE = False


def init_fastapi_instrumentation(app: Any = None) -> bool:
    """
    Initialize FastAPI instrumentation for automatic HTTP request tracing.

    Args:
        app: FastAPI application instance (optional, can be called later)

    Returns:
        True if instrumentation was configured, False otherwise
    """
    if not FASTAPI_INSTRUMENTATION_AVAILABLE:
        logger.warning("FastAPI instrumentation not available - skipping")
        return False

    try:
        if app is not None:
            # Instrument specific app
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI app instrumentation enabled")
        else:
            # Global instrumentation - will apply to all FastAPI apps
            FastAPIInstrumentor().instrument()
            logger.info("FastAPI global instrumentation enabled")
        return True
    except Exception as e:
        logger.warning(f"Failed to instrument FastAPI: {e}")
        return False


def init_sqlalchemy_instrumentation() -> bool:
    """
    Initialize SQLAlchemy instrumentation for automatic database query tracing.

    Returns:
        True if instrumentation was configured, False otherwise
    """
    if not SQLALCHEMY_INSTRUMENTATION_AVAILABLE:
        logger.warning("SQLAlchemy instrumentation not available - skipping")
        return False

    try:
        # Global SQLAlchemy instrumentation
        SQLAlchemyInstrumentor().instrument()
        logger.info("SQLAlchemy instrumentation enabled")
        return True
    except Exception as e:
        logger.warning(f"Failed to instrument SQLAlchemy: {e}")
        return False


def is_fastapi_instrumentation_available() -> bool:
    """Check if FastAPI instrumentation is available."""
    return FASTAPI_INSTRUMENTATION_AVAILABLE


def is_sqlalchemy_instrumentation_available() -> bool:
    """Check if SQLAlchemy instrumentation is available."""
    return SQLALCHEMY_INSTRUMENTATION_AVAILABLE
