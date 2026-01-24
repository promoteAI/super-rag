import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from langchain.schema import (
    AIMessage,
    BaseMessage,
    ChatMessage,
    FunctionMessage,
    HumanMessage,
    SystemMessage,
)

from super_rag.history import (
    StoredChatMessage,
    create_assistant_message,
    create_user_message,
    message_to_storage_dict,
    storage_dict_to_message,
)

from super_rag.db.ops import AsyncDatabaseOps, async_db_ops

logger = logging.getLogger(__name__)


class BaseChatMessageHistory(ABC):
    """Abstract base class for storing chat message history."""

    async def add_user_message(self, message: str, message_id: str, files: List[Dict[str, Any]] = None) -> None:
        """Convenience method for adding a human message string to the store.

        Args:
            message: The string contents of a human message.
            message_id: Unique message identifier.
            files: Optional list of file metadata associated with the message.
        """
        raise NotImplementedError()

    async def add_ai_message(
        self,
        content: str,
        chat_id: str,
        message_id: str = None,
        tool_use_list: List = None,
        references: List[Dict[str, Any]] = None,
        urls: List[str] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Convenience method for adding an AI message string to the store.

        Args:
            message: The string contents of an AI message.
        """
        raise NotImplementedError()

    @abstractmethod
    async def clear(self) -> None:
        """Remove all messages from the store"""
        raise NotImplementedError()

    @property
    async def messages(self) -> List[StoredChatMessage]:
        """Retrieve all messages from the store.

        Returns:
            A list of BaseMessage objects.
        """
        raise NotImplementedError()


async def message_from_dict(message: dict) -> BaseMessage:
    _type = message["type"]
    if _type == "human":
        return HumanMessage(**message["data"])
    elif _type == "ai":
        return AIMessage(**message["data"])
    elif _type == "system":
        return SystemMessage(**message["data"])
    elif _type == "chat":
        return ChatMessage(**message["data"])
    elif _type == "function":
        return FunctionMessage(**message["data"])
    else:
        raise ValueError(f"Got unexpected message type: {_type}")


class MySQLChatMessageHistory:
    """Chat message history stored in a MySQL database using StoredChatMessage format."""

    def __init__(self, session_id: str, db_session=None):
        """
        db_session: an async SQLAlchemy session or compatible async session instance.
        """
        self.session_id = session_id
        self.db_session = db_session
        self.db_ops = AsyncDatabaseOps(self.db_session) if self.db_session is not None else async_db_ops

    @property
    async def messages(self) -> List[StoredChatMessage]:
        """Retrieve the messages from MySQL as StoredChatMessage objects"""
        try:
            # Use db_ops to get all messages by chat_id
            rows = await self.db_ops.get_messages(self.session_id)
            messages = []
            for row in rows:
                try:
                    item = json.loads(row.raw_message) if hasattr(row, "raw_message") else row.to_dict()
                    message = storage_dict_to_message(item)
                    messages.append(message)
                except Exception as e:
                    logger.warning(f"Failed to parse message from MySQL for {self.session_id}: {e}")
        except Exception as e:
            logger.error(f"Failed to fetch chat history from MySQL for {self.session_id}: {e}")
            messages = []
        return messages

    async def add_stored_message(self, message: StoredChatMessage) -> None:
        """Add a StoredChatMessage directly to MySQL"""
        try:
            msg_dict = message_to_storage_dict(message)
            raw_message = json.dumps(msg_dict)
            await self.db_ops.insert_message(
                chat_id=self.session_id,
                role=msg_dict.get("role"),
                raw_message=raw_message,
                message_id=msg_dict.get("message_id"),
            )
        except Exception as e:
            logger.error(f"Failed to add chat message to MySQL: {e}")

    async def add_user_message(self, message: str, message_id: str, files: List[Dict[str, Any]] = None) -> None:
        """Add a user message using new format"""
        stored_message = create_user_message(
            content=message,
            chat_id=self.session_id,
            message_id=message_id,
            files=files,
        )
        await self.add_stored_message(stored_message)

    async def add_ai_message(
        self,
        content: str,
        chat_id: str,
        message_id: str = None,
        tool_use_list: List = None,
        references: List[Dict[str, Any]] = None,
        urls: List[str] = None,
        trace_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Add an AI message using new format"""
        stored_message = create_assistant_message(
            content=content,
            chat_id=self.session_id,
            message_id=message_id,
            tool_use_list=tool_use_list,
            references=references,
            urls=urls,
            trace_id=trace_id,
            metadata=metadata,
        )
        await self.add_stored_message(stored_message)

    async def clear(self) -> None:
        """Clear session memory from MySQL"""
        try:
            await self.db_ops.soft_delete_messages_by_chat(self.session_id)
        except Exception as e:
            logger.error(f"Failed to clear chat history from MySQL: {e}")



async def query_chat_messages(user: str, chat_id: str, db_session=None):
    """
    Query chat messages from MySQL and convert to frontend format.

    Returns:
        Array of conversation turns, where each turn is an array of message parts
        格式: [[turn1_parts], [turn2_parts], ...]
    """
    from super_rag.schema import view_models

    # Use AsyncDatabaseOps/db_ops to get chat history and feedbacks
    db_ops = AsyncDatabaseOps(db_session) if db_session is not None else async_db_ops

    try:
        # Get all stored messages (each StoredChatMessage represents one conversation turn)
        chat_history = MySQLChatMessageHistory(chat_id, db_session=db_session)
        stored_messages = await chat_history.messages

        if not stored_messages:
            return []

        # Get feedbacks for this chat
        feedbacks = await db_ops.query_chat_feedbacks(user, chat_id)
        feedback_map = {feedback.message_id: feedback for feedback in feedbacks}

        # Convert each StoredChatMessage (conversation turn) to frontend format
        conversation_turns = []
        for stored_message in stored_messages:
            chat_message_list = stored_message.to_frontend_format()
            # Add feedback data if available
            for chat_msg in chat_message_list:
                msg_id = getattr(chat_msg, 'id', None)
                feedback = feedback_map.get(msg_id)
                if feedback and getattr(chat_msg, 'role', None) == "ai":
                    chat_msg.feedback = view_models.Feedback(
                        type=feedback.type, tag=feedback.tag, message=feedback.message
                    )
            conversation_turns.append(chat_message_list)
        return conversation_turns

    except Exception as e:
        logger.error(f"Error querying chat messages: {e}")
        return []


def success_response(message_id, data):
    return json.dumps(
        {
            "type": "message",
            "id": message_id,
            "data": data,
            "timestamp": int(time.time()),
        }
    )


def fail_response(message_id, error):
    return json.dumps(
        {
            "type": "error",
            "id": message_id,
            "data": error,
            "timestamp": int(time.time()),
        }
    )


def start_response(message_id):
    return json.dumps(
        {
            "type": "start",
            "id": message_id,
            "timestamp": int(time.time()),
        }
    )


def references_response(message_id, references, memory_count=0, urls=[]):
    if references is None:
        references = []
    return json.dumps(
        {
            "type": "references",
            "id": message_id,
            "data": references,
            "memoryCount": memory_count,
            "urls": urls,
            "timestamp": int(time.time()),
        }
    )


def stop_response(message_id):
    return json.dumps(
        {
            "type": "stop",
            "id": message_id,
            "timestamp": int(time.time()),
        }
    )

# There is no get_async_redis_client or similar for MySQL; acquire db session elsewhere.
