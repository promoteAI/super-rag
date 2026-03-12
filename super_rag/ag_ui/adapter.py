"""
Consume super_rag message queue and yield AG-UI protocol events as SSE.
Maps: start -> RunStarted; message -> TextMessageStart/Content/End; tool_call_result -> ToolCallResult; stop -> RunFinished; error -> RunError.
"""

import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional

from super_rag.agent.agent_message_queue import AgentMessageQueue

logger = logging.getLogger(__name__)

# Lazy import so ag-ui-protocol is optional at import time
def _get_encoder(accept: Optional[str] = None):
    from ag_ui.core import (
        EventType,
        RunStartedEvent,
        RunFinishedEvent,
        RunErrorEvent,
        TextMessageStartEvent,
        TextMessageContentEvent,
        TextMessageEndEvent,
        ToolCallStartEvent,
        ToolCallEndEvent,
        ToolCallResultEvent,
        ReasoningMessageChunkEvent,
        ActivitySnapshotEvent,
    )
    from ag_ui.encoder import EventEncoder
    enc = EventEncoder(accept=accept or "")
    return enc, EventType, {
        "RunStartedEvent": RunStartedEvent,
        "RunFinishedEvent": RunFinishedEvent,
        "RunErrorEvent": RunErrorEvent,
        "TextMessageStartEvent": TextMessageStartEvent,
        "TextMessageContentEvent": TextMessageContentEvent,
        "TextMessageEndEvent": TextMessageEndEvent,
        "ToolCallStartEvent": ToolCallStartEvent,
        "ToolCallEndEvent": ToolCallEndEvent,
        "ToolCallResultEvent": ToolCallResultEvent,
        "ReasoningMessageChunkEvent": ReasoningMessageChunkEvent,
        "ActivitySnapshotEvent": ActivitySnapshotEvent,
    }


async def stream_ag_ui_events(
    message_queue: AgentMessageQueue,
    thread_id: str,
    run_id: str,
    message_id: str,
    accept_header: Optional[str] = None,
    chunk_size: int = 32,
    tool_call_results: Optional[list] = None,
) -> AsyncGenerator[bytes, None]:
    """
    Consume messages from queue, convert to AG-UI events, encode as SSE, and yield bytes.
    If tool_call_results is provided, append each tool_call_result message dict to it for history saving.
    """
    try:
        encoder, EventType, events = _get_encoder(accept_header)
    except ImportError as e:
        logger.error("ag-ui-protocol not installed: %s", e)
        yield b"data: {\"type\":\"RUN_ERROR\",\"message\":\"ag-ui-protocol not installed\"}\n\n"
        return

    RunStartedEvent = events["RunStartedEvent"]
    RunFinishedEvent = events["RunFinishedEvent"]
    RunErrorEvent = events["RunErrorEvent"]
    TextMessageStartEvent = events["TextMessageStartEvent"]
    TextMessageContentEvent = events["TextMessageContentEvent"]
    TextMessageEndEvent = events["TextMessageEndEvent"]
    ToolCallStartEvent = events["ToolCallStartEvent"]
    ToolCallEndEvent = events["ToolCallEndEvent"]
    ToolCallResultEvent = events["ToolCallResultEvent"]
    ReasoningMessageChunkEvent = events["ReasoningMessageChunkEvent"]
    ActivitySnapshotEvent = events["ActivitySnapshotEvent"]

    def _enc(event):
        raw = encoder.encode(event)
        return raw.encode("utf-8") if isinstance(raw, str) else raw

    tool_call_index = 0
    tool_call_starts_sent = set()  # tool_call_ids for which we already emitted ToolCallStartEvent

    try:
        while True:
            message = await message_queue.get()
            if message is None:
                break

            if not isinstance(message, dict):
                continue

            msg_type = message.get("type")
            msg_id = message.get("id") or message_id

            if msg_type == "tool_call_start":
                tool_call_id = message.get("tool_call_id") or f"tool_{msg_id}_{tool_call_index}"
                tool_call_index += 1
                tool_name = message.get("tool_name") or "tool"
                tool_call_starts_sent.add(tool_call_id)
                start_kwargs: Dict[str, Any] = dict(
                    type=EventType.TOOL_CALL_START,
                    tool_call_id=tool_call_id,
                    tool_call_name=tool_name,
                    parent_message_id=msg_id,
                )
                args_data = message.get("data")
                if args_data:
                    start_kwargs["tool_call_args"] = args_data
                start_ev = ToolCallStartEvent(**start_kwargs)
                yield _enc(start_ev)

            elif msg_type == "start":
                event = RunStartedEvent(
                    type=EventType.RUN_STARTED,
                    thread_id=thread_id,
                    run_id=run_id,
                )
                yield _enc(event)

            elif msg_type == "message":
                data = message.get("data") or ""
                if not data:
                    continue
                event_start = TextMessageStartEvent(
                    type=EventType.TEXT_MESSAGE_START,
                    message_id=msg_id,
                    role="assistant",
                )
                yield _enc(event_start)
                for i in range(0, len(data), chunk_size):
                    chunk = data[i : i + chunk_size]
                    if chunk:
                        event_content = TextMessageContentEvent(
                            type=EventType.TEXT_MESSAGE_CONTENT,
                            message_id=msg_id,
                            delta=chunk,
                        )
                        yield _enc(event_content)
                event_end = TextMessageEndEvent(
                    type=EventType.TEXT_MESSAGE_END,
                    message_id=msg_id,
                )
                yield _enc(event_end)

            elif msg_type == "tool_call_result":
                if tool_call_results is not None:
                    tool_call_results.append(message)
                tool_call_id = message.get("tool_call_id") or f"tool_{msg_id}_{tool_call_index}"
                if tool_call_id not in tool_call_starts_sent:
                    tool_call_index += 1
                    tool_call_starts_sent.add(tool_call_id)
                    tool_name = message.get("tool_name") or "tool"
                    fallback_kwargs: Dict[str, Any] = dict(
                        type=EventType.TOOL_CALL_START,
                        tool_call_id=tool_call_id,
                        tool_call_name=tool_name,
                        parent_message_id=msg_id,
                    )
                    start_ev = ToolCallStartEvent(**fallback_kwargs)
                    yield _enc(start_ev)
                content = message.get("data") or ""
                if not isinstance(content, str):
                    content = str(content)
                end_ev = ToolCallEndEvent(
                    type=EventType.TOOL_CALL_END,
                    tool_call_id=tool_call_id,
                )
                yield _enc(end_ev)
                result_ev = ToolCallResultEvent(
                    type=EventType.TOOL_CALL_RESULT,
                    message_id=msg_id,
                    tool_call_id=tool_call_id,
                    content=content,
                    role="tool",
                )
                yield _enc(result_ev)

            elif msg_type == "activity_snapshot":
                activity_type = message.get("activity_type") or "SEARCH_RESULTS"
                content = message.get("content")
                if content is not None:
                    event = ActivitySnapshotEvent(
                        type=EventType.ACTIVITY_SNAPSHOT,
                        message_id=msg_id,
                        activity_type=activity_type,
                        content=content,
                        replace=True,
                    )
                    yield _enc(event)

            elif msg_type == "thinking":
                data = message.get("data") or ""
                if data:
                    event = ReasoningMessageChunkEvent(
                        type=EventType.REASONING_MESSAGE_CHUNK,
                        message_id=msg_id,
                        delta=data,
                    )
                    yield _enc(event)

            elif msg_type == "stop":
                refs = message.get("data")
                event = RunFinishedEvent(
                    type=EventType.RUN_FINISHED,
                    thread_id=thread_id,
                    run_id=run_id,
                    result=refs,
                )
                yield _enc(event)

            elif msg_type == "error":
                err_msg = message.get("data") or str(message.get("message", "Unknown error"))
                event = RunErrorEvent(
                    type=EventType.RUN_ERROR,
                    message=err_msg,
                )
                yield _enc(event)

    except Exception as e:
        logger.exception("AG-UI adapter error: %s", e)
        try:
            enc2, _, ev2 = _get_encoder(accept_header)
            RunErrorEvent = ev2["RunErrorEvent"]
            event = RunErrorEvent(type=EventType.RUN_ERROR, message=str(e))
            raw = enc2.encode(event)
            yield raw.encode("utf-8") if isinstance(raw, str) else raw
        except Exception:
            yield f"data: {{\"type\":\"RUN_ERROR\",\"message\":\"{str(e)[:200]}\"}}\n\n".encode("utf-8")


def get_ag_ui_sse_media_type(accept: Optional[str] = None) -> str:
    """Return the SSE response Content-Type for AG-UI (e.g. text/event-stream with proper params)."""
    try:
        encoder, _, _ = _get_encoder(accept or "")
        return encoder.get_content_type()
    except ImportError:
        return "text/event-stream"
