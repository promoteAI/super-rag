"""Context for forwarding MCP tool calls to the frontend message queue."""

import contextvars
from typing import Optional, Tuple

from .agent_message_queue import AgentMessageQueue

# (message_id, message_queue) for the current request so LLM can push tool call messages
current_tool_call_context: contextvars.ContextVar[
    Optional[Tuple[str, AgentMessageQueue]]
] = contextvars.ContextVar("current_tool_call_context", default=None)


def set_tool_call_context(message_id: str, message_queue: AgentMessageQueue) -> None:
    current_tool_call_context.set((message_id, message_queue))


def get_tool_call_context() -> Optional[Tuple[str, AgentMessageQueue]]:
    return current_tool_call_context.get()


def clear_tool_call_context() -> None:
    try:
        current_tool_call_context.set(None)
    except LookupError:
        pass
