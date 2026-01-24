

"""Chat history message types and utilities."""

from .message import (
    StoredChatMessage,
    StoredChatMessagePart,
    create_assistant_message,
    create_user_message,
    group_messages_by_message_id,
    group_parts_by_message_id,
    message_to_storage_dict,
    messages_to_frontend_format,
    messages_to_openai_format,
    storage_dict_to_message,
)

__all__ = [
    # Core message classes
    "StoredChatMessagePart",
    "StoredChatMessage",
    # Helper functions for creating messages
    "create_user_message",
    "create_assistant_message",
    # Conversion functions
    "message_to_storage_dict",
    "storage_dict_to_message",
    "group_messages_by_message_id",
    "group_parts_by_message_id",
    "messages_to_frontend_format",
    "messages_to_openai_format",
]
