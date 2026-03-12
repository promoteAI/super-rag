

"""Stream message formatters for agent responses."""

import time
from typing import Any, Dict, List

from .i18n import ERROR_MESSAGES
from .response_types import (
    AgentErrorResponse,
    AgentMessageResponse,
    AgentStartResponse,
    AgentStopResponse,
    AgentThinkingResponse,
    AgentToolCallResultResponse,
    AgentToolCallStartResponse,
)


def format_i18n_error(error_key: str, language: str = "en-US", **kwargs) -> AgentErrorResponse:
    """Format internationalized error message."""
    messages = ERROR_MESSAGES.get(language, ERROR_MESSAGES["en-US"])

    if error_key in messages:
        error_message = messages[error_key]
        # If the message contains placeholders, format it with kwargs
        if kwargs:
            try:
                error_message = error_message.format(**kwargs)
            except KeyError:
                # If formatting fails, just use the base message
                pass
    else:
        # Fallback to unknown error if key doesn't exist
        error_message = messages.get("unknown_error", "An error occurred")

    return AgentErrorResponse(
        type="error",
        id="error",
        data=error_message,
        timestamp=int(time.time()),
    )


# Backward compatibility functions
def format_stream_start(msg_id: str) -> AgentStartResponse:
    """Format stream start event - backward compatibility"""
    return AgentStartResponse(
        type="start",
        id=msg_id,
        timestamp=int(time.time()),
    )


def format_stream_content(msg_id: str, content: str) -> AgentMessageResponse:
    """Format stream content event - backward compatibility"""
    return AgentMessageResponse(
        type="message",
        id=msg_id,
        data=content,
        timestamp=int(time.time()),
    )


def format_stream_end(
    msg_id: str, references: List[Dict[str, Any]] = None, urls: List[str] = None
) -> AgentStopResponse:
    """Format stream end event - backward compatibility"""
    if references is None:
        references = []
    if urls is None:
        urls = []

    return AgentStopResponse(
        type="stop",
        id=msg_id,
        data=references,
        urls=urls,
        timestamp=int(time.time()),
    )


def format_thinking(msg_id: str, content: str) -> AgentThinkingResponse:
    """Format thinking step event - backward compatibility"""
    return AgentThinkingResponse(
        type="thinking",
        id=msg_id,
        data=content,
        timestamp=int(time.time()),
    )


def format_tool_call_start(
    msg_id: str, tool_call_id: str, tool_name: str, arguments_str: str
) -> AgentToolCallStartResponse:
    """Format tool call start event (explicit MCP tool invocation) for frontend."""
    return AgentToolCallStartResponse(
        type="tool_call_start",
        id=msg_id,
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        data=arguments_str,
        timestamp=int(time.time()),
    )


def format_tool_call_result(
    msg_id: str,
    data: str,
    tool_name: str,
    result: Any,
    tool_call_id: str | None = None,
    arguments: str | None = None,
) -> AgentToolCallResultResponse:
    """
    Format tool call result event.

    `arguments` is optional and may contain the JSON-encoded tool input,
    which is useful for persisting full tool traces in history.
    """
    msg: AgentToolCallResultResponse = AgentToolCallResultResponse(
        type="tool_call_result",
        id=msg_id,
        data=data,
        tool_name=tool_name,
        result=result,
        tool_call_id=tool_call_id,
        timestamp=int(time.time()),
    )
    # Attach arguments in a backward-compatible way (extra field on the dict)
    if arguments is not None:
        # type: ignore[assignment]
        msg["args"] = arguments
    return msg


# New unified formatter functions
def format_agent_start_message(trace_id: str, language: str = "en-US") -> Dict[str, Any]:
    """Format agent start message."""
    return {
        "type": "start",
        "id": trace_id,
        "timestamp": int(time.time()),
    }


def format_agent_stop_message(trace_id: str, references: list = None, urls: list = None) -> Dict[str, Any]:
    """Format agent stop message with references."""
    return {
        "type": "stop",
        "id": trace_id,
        "data": references or [],
        "urls": urls or [],
        "timestamp": int(time.time()),
    }


def format_agent_thinking_message(trace_id: str, thinking_content: str) -> Dict[str, Any]:
    """Format agent thinking message."""
    return {
        "type": "thinking",
        "id": trace_id,
        "data": thinking_content,
        "timestamp": int(time.time()),
    }


def format_agent_message(trace_id: str, content: str) -> Dict[str, Any]:
    """Format regular agent message."""
    return {
        "type": "message",
        "id": trace_id,
        "data": content,
        "timestamp": int(time.time()),
    }


def format_activity_snapshot(msg_id: str, activity_type: str, content: Dict[str, Any]) -> Dict[str, Any]:
    """Format activity snapshot for AG-UI generative UI (e.g. SEARCH_RESULTS)."""
    return {
        "type": "activity_snapshot",
        "id": msg_id,
        "activity_type": activity_type,
        "content": content,
        "timestamp": int(time.time()),
    }
