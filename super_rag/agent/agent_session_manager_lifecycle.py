

"""Super simple lifecycle management for agent sessions."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from super_rag.agent import agent_session_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def agent_session_manager_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Ultra-simple lifecycle management - just start/stop cleanup task."""

    # Startup: start background cleanup
    logger.info("Starting agent session cleanup")
    await agent_session_manager.start_cleanup()

    try:
        yield
    finally:
        # Shutdown: clean everything up
        logger.info("Shutting down agent sessions")
        await agent_session_manager.shutdown_all()
        logger.info("Agent sessions shutdown complete")
