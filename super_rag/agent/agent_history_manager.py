

"""Agent chat history management for persistent storage - pure functions for testability."""

import logging
from typing import Any, Dict, List

from super_rag.utils.history import MySQLChatMessageHistory
from ..history import create_assistant_message, create_user_message
from .exceptions import handle_agent_error

logger = logging.getLogger(__name__)


class AgentHistoryManager:
    """
    Manages chat history persistence and retrieval using pure functions.

    This class provides pure functions that accept external dependencies,
    making it highly testable and free from hidden dependencies.

    Most methods require external RedisChatMessageHistory instances to be passed in,
    eliminating internal state and hidden dependencies.
    """

    @handle_agent_error("history_creation", reraise=True)
    async def get_chat_history(self, chat_id: str) -> MySQLChatMessageHistory:
        """
        Get chat history instance for a given chat ID.

        This method encapsulates the creation of RedisChatMessageHistory instances,
        providing a central point for history management configuration.

        Args:
            chat_id: Chat session identifier

        Returns:
            RedisChatMessageHistory: Configured history instance
        """
        logger.debug(f"Creating chat history instance for chat_id: {chat_id}")

        # Create history instance with Redis client
        history = MySQLChatMessageHistory(chat_id)

        logger.debug(f"Successfully created chat history instance for chat_id: {chat_id}")
        return history

    @handle_agent_error("conversation_save", reraise=False)
    async def save_conversation_turn(
        self,
        message_id: str,
        trace_id: str,
        history: MySQLChatMessageHistory,
        user_query: str,
        ai_response: str,
        files: List[Dict[str, Any]],
        tool_use_list: List[Dict],
        tool_references: List,
    ) -> bool:
        """
        Save a complete conversation turn to persistent storage.

        This is a pure function that accepts external history instance.
        Uses agent-specific saving format (plain text) instead of flow-based Message JSON.

        Args:
            history: External RedisChatMessageHistory instance
            user_query: User's query message
            ai_response: AI's response message
            tool_references: Tool call references from the conversation

        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            logger.debug(f"Saving conversation turn for history session: {history.session_id}")

            user_message = create_user_message(
                content=user_query,
                chat_id=history.session_id,
                message_id=message_id,
                trace_id=trace_id,
                files=files,
            )
            # Save human message (plain text for agent conversations)
            await history.add_stored_message(user_message)

            # Save AI message (plain text for agent conversations)
            ai_message = create_assistant_message(
                content=ai_response,
                chat_id=history.session_id,
                message_id=message_id,
                trace_id=trace_id,
                tool_use_list=tool_use_list,
                references=tool_references,
                # urls=,
            )
            await history.add_stored_message(ai_message)

            logger.debug(f"Successfully saved conversation turn for session: {history.session_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save conversation turn for session {history.session_id}: {e}")
            return False
