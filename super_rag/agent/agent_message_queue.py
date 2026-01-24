

"""Message queue for agent chat communication."""

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AgentMessageQueue:
    """
    Async message queue for agent chat communication.

    Acts like Go channels - producers put messages, consumers get messages.
    Supports graceful shutdown and end-of-stream signaling.
    """

    def __init__(self):
        self.queue = asyncio.Queue()
        self._closed = False

    async def put(self, message: Dict[str, Any]) -> None:
        """Put a message into the queue"""
        if self._closed:
            logger.warning(f"Attempted to put message into closed queue, message: {message}")
            return

        await self.queue.put(message)
        logger.debug(f"Message queued: {message.get('type', 'unknown')}")

    async def get(self) -> Optional[Dict[str, Any]]:
        """Get a message from the queue. Returns None when queue is closed and empty."""
        try:
            return await self.queue.get()
        except asyncio.CancelledError:
            return None

    async def close(self) -> None:
        """Close the queue and signal end of stream"""
        self._closed = True
        # Put a sentinel value to signal end of stream
        await self.queue.put(None)
        logger.debug("Message queue closed")

    def is_closed(self) -> bool:
        """Check if the queue is closed"""
        return self._closed

    def qsize(self) -> int:
        """Get the current queue size"""
        return self.queue.qsize()
