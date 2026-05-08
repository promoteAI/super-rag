"""
Agno-based agent runner.

This module fully replaces the previous mcp-agent / SuperRagOpenAIAugmentedLLM
custom agent loop. It drives an `agno.agent.Agent` connected to the
super_rag and hindsight MCP servers, then forwards Agno streaming events
into the existing `AgentMessageQueue` protocol so the WebSocket layer and
all downstream consumers (history, references, etc.) continue to work
without changes.
"""

import asyncio
import json
import logging
import os
import time
from datetime import timedelta
from urllib.parse import quote
from typing import Any, Dict, List, Optional

from agno.agent import Agent as AgnoAgent
from agno.exceptions import ModelProviderError
from agno.models.message import Message as AgnoMessage
from agno.models.openai.like import OpenAILike
from agno.run.agent import (
    RunCompletedEvent,
    RunContentEvent,
    RunErrorEvent,
    RunStartedEvent,
    ToolCallCompletedEvent,
    ToolCallErrorEvent,
    ToolCallStartedEvent,
)
from agno.tools.mcp import MCPTools, StreamableHTTPClientParams

from super_rag.agent.agent_message_queue import AgentMessageQueue
from super_rag.agent.exceptions import AgentConfigurationError
from super_rag.agent.response_types import AgentErrorResponse
from super_rag.agent.stream_formatters import (
    format_stream_content,
    format_stream_end,
    format_stream_start,
    format_tool_call_result,
    format_tool_call_start,
)
from super_rag.agent.tool_reference_extractor import (
    _format_generic_reference,
    _format_list_reference,
    _format_search_chat_files_reference,
    _format_search_reference,
    _format_web_read_reference,
    _format_web_search_reference,
)

logger = logging.getLogger(__name__)


# Tool name prefixes applied to MCP tools so we can route them to the
# correct reference extractor below.
SUPER_RAG_PREFIX = "super_rag"
HINDSIGHT_PREFIX = "hindsight"
_DEFAULT_HINDSIGHT_MCP_BASE = "http://localhost:8888/mcp"


def hindsight_mcp_url_for_bank_id(bank_id: str) -> str:
    """Single-bank Hindsight MCP URL: /mcp/{bank_id}/ with path-safe encoding."""
    base = os.getenv("HINDSIGHT_MCP_URL", _DEFAULT_HINDSIGHT_MCP_BASE).rstrip("/")
    segment = quote(bank_id, safe="")
    return f"{base}/{segment}/"


def _flatten_exception_message(exc: BaseException) -> str:
    """
    Flatten ExceptionGroup + cause/context chains into readable message.
    """
    seen: List[str] = []
    visited: set[int] = set()

    def _record(msg: Optional[str]) -> None:
        if not msg:
            return
        msg = str(msg).strip()
        if msg and msg != "Unknown model error" and msg not in seen:
            seen.append(msg)

    def _walk(e: Optional[BaseException]) -> None:
        if e is None or id(e) in visited:
            return
        visited.add(id(e))

        sub_exceptions = getattr(e, "exceptions", None)
        if sub_exceptions:
            for sub in sub_exceptions:
                _walk(sub)
        else:
            _record(str(e))

        response = getattr(e, "response", None)
        if response is not None:
            try:
                body = response.json()
                if isinstance(body, dict):
                    if "message" in body and body["message"]:
                        _record(body["message"])
                    elif "error" in body and isinstance(body["error"], dict):
                        _record(body["error"].get("message"))
            except Exception:
                try:
                    _record(response.text)
                except Exception:
                    pass

        _walk(getattr(e, "__cause__", None))
        _walk(getattr(e, "__context__", None))

    _walk(exc)
    if not seen:
        return f"{exc.__class__.__name__}: {exc!s}"
    return " | ".join(seen)


def _enrich_model_error(message: str, model_name: str, base_url: str) -> str:
    """
    Provide an actionable message when provider/SDK only reports
    'Unknown model error'.
    """
    normalized = (message or "").strip()
    if not normalized:
        normalized = "Unknown model error"

    unknown_markers = {
        "Unknown model error",
        "unknown model error",
        "Non-retryable model provider error: Unknown model error",
    }
    if normalized in unknown_markers:
        return (
            f"模型不可用或配置错误：model='{model_name}'。"
            f"请检查该模型是否在当前 provider/base_url 可用（base_url='{base_url}'）。"
        )
    return normalized


def _strip_prefix(tool_name: Optional[str], prefix: str) -> str:
    if not tool_name:
        return ""
    head = f"{prefix}_"
    if tool_name.startswith(head):
        return tool_name[len(head):]
    return tool_name


def _coerce_tool_result_to_text(result: Any) -> Optional[str]:
    """Best-effort conversion of an MCP tool result to a string for parsing."""
    if result is None:
        return None
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False)
    except Exception:
        return str(result)


def _build_reference_for_tool(
    full_tool_name: str,
    tool_args: Dict[str, Any],
    tool_result: Any,
) -> Optional[Dict[str, Any]]:
    """Convert a single tool execution result to the reference dict format."""
    result_text = _coerce_tool_result_to_text(tool_result)
    if result_text is None:
        return None

    # Resolve which extractor to use based on the (prefixed) tool name.
    base_name = _strip_prefix(full_tool_name, SUPER_RAG_PREFIX)
    if base_name == full_tool_name:
        # Wasn't a super_rag tool - try hindsight stripping.
        base_name = _strip_prefix(full_tool_name, HINDSIGHT_PREFIX)

    args = tool_args or {}

    try:
        if base_name == "search_collection":
            return _format_search_reference(result_text, args)
        if base_name == "search_chat_files":
            return _format_search_chat_files_reference(result_text, args)
        if base_name == "list_collections":
            return _format_list_reference(result_text, args)
        if base_name == "web_search":
            return _format_web_search_reference(result_text, args)
        if base_name == "web_read":
            return _format_web_read_reference(result_text, args)
        return _format_generic_reference(full_tool_name, result_text, args)
    except Exception as e:
        logger.warning("Failed to build reference for tool %s: %s", full_tool_name, e)
        return None


def _build_history_messages(openai_messages: List[Dict[str, Any]]) -> List[AgnoMessage]:
    """Convert OpenAI-format history messages into Agno `Message` objects."""
    out: List[AgnoMessage] = []
    for msg in openai_messages or []:
        role = msg.get("role")
        content = msg.get("content")
        if not role or content is None:
            continue
        # Skip tool/system reflections from history; they are rebuilt by Agno.
        if role not in ("user", "assistant"):
            continue
        out.append(AgnoMessage(role=role, content=content))
    return out


async def run_agno_agent(
    *,
    message_id: str,
    message_queue: AgentMessageQueue,
    user_id: str,
    chat_id: str,
    api_key: str,
    base_url: str,
    model_name: str,
    instruction: str,
    prompt: str,
    history_openai_messages: Optional[List[Dict[str, Any]]] = None,
    super_rag_mcp_url: Optional[str] = None,
    super_rag_api_key: Optional[str] = None,
    hindsight_bank_id: Optional[str] = None,
    enable_hindsight: bool = True,
    temperature: float = 0.7,
    max_tokens: int = 8192,
    request_timeout_seconds: int = 120,
) -> Dict[str, Any]:
    """
    Run an Agno-based agent and stream events into ``message_queue``.

    Returns a dict with ``content`` (final text) and ``references``
    (extracted from tool calls in the same shape used by the existing
    history layer).
    """
    if not super_rag_mcp_url:
        raise AgentConfigurationError("super_rag_mcp_url", "super_rag MCP URL is required")
    if not super_rag_api_key:
        raise AgentConfigurationError("super_rag_api_key", "super_rag API key is required")
    if not api_key or not base_url or not model_name:
        raise AgentConfigurationError("completion", "model api_key/base_url/model are required")

    await message_queue.put(format_stream_start(message_id))

    super_rag_params = StreamableHTTPClientParams(
        url=super_rag_mcp_url,
        headers={
            "Authorization": f"Bearer {super_rag_api_key}",
            "Content-Type": "application/json",
        },
        timeout=timedelta(seconds=request_timeout_seconds),
    )

    hindsight_url = (
        hindsight_mcp_url_for_bank_id(hindsight_bank_id)
        if hindsight_bank_id
        else os.getenv("HINDSIGHT_MCP_URL", _DEFAULT_HINDSIGHT_MCP_BASE)
    )
    hindsight_params = StreamableHTTPClientParams(
        url=hindsight_url,
        headers={"Content-Type": "application/json"},
        timeout=timedelta(seconds=request_timeout_seconds),
    )

    full_text_parts: List[str] = []
    captured_tools: Dict[str, Dict[str, Any]] = {}
    emitted_tool_results: set[str] = set()
    references: List[Dict[str, Any]] = []

    async def _emit_run_content(delta: str) -> None:
        if not delta:
            return
        full_text_parts.append(delta)
        try:
            await message_queue.put(
                {"type": "text_delta", "id": message_id, "data": delta}
            )
        except Exception as e:  # noqa: BLE001
            logger.debug("Failed to push text_delta: %s", e)

    async def _emit_tool_start(tool: Any) -> None:
        try:
            tool_call_id = getattr(tool, "tool_call_id", None) or "unknown"
            tool_name = getattr(tool, "tool_name", None) or "unknown"
            args_str = json.dumps(getattr(tool, "tool_args", None) or {}, ensure_ascii=False)
            await message_queue.put(
                format_tool_call_start(message_id, tool_call_id, tool_name, args_str)
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to send tool_call_start: %s", e)

    async def _emit_tool_completed(tool: Any) -> None:
        try:
            tool_call_id = getattr(tool, "tool_call_id", None) or "unknown"
            tool_name = getattr(tool, "tool_name", None) or "unknown"
            tool_args = getattr(tool, "tool_args", None) or {}
            result = getattr(tool, "result", None)
            captured_tools[tool_call_id] = {
                "tool_name": tool_name,
                "tool_args": tool_args,
                "result": result,
            }
            if tool_call_id in emitted_tool_results:
                return
            args_str = None
            try:
                args_str = json.dumps(tool_args, ensure_ascii=False)
            except Exception:
                args_str = None
            display_text = result if isinstance(result, str) else _coerce_tool_result_to_text(result) or ""
            await message_queue.put(
                format_tool_call_result(
                    message_id,
                    display_text,
                    tool_name,
                    None,
                    tool_call_id=tool_call_id,
                    arguments=args_str,
                )
            )
            emitted_tool_results.add(tool_call_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to send tool_call_result: %s", e)

    async def _emit_tool_error(tool: Any, error: Any) -> None:
        try:
            tool_call_id = getattr(tool, "tool_call_id", None) or "unknown"
            tool_name = getattr(tool, "tool_name", None) or "unknown"
            tool_args = getattr(tool, "tool_args", None) or {}
            error_text = str(error) if error is not None else "Tool call failed"
            error_result = {"error": error_text}
            captured_tools[tool_call_id] = {
                "tool_name": tool_name,
                "tool_args": tool_args,
                "result": error_result,
            }
            if tool_call_id in emitted_tool_results:
                return
            args_str = None
            try:
                args_str = json.dumps(tool_args, ensure_ascii=False)
            except Exception:
                args_str = None
            await message_queue.put(
                format_tool_call_result(
                    message_id,
                    error_text,
                    tool_name,
                    error_result,
                    tool_call_id=tool_call_id,
                    arguments=args_str,
                )
            )
            emitted_tool_results.add(tool_call_id)
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to send tool_call_error result: %s", e)

    pending_error_msg: Optional[str] = None

    async def _run_agno_loop(tool_kits: List[Any]) -> None:
        nonlocal pending_error_msg

        model = OpenAILike(
            id=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=request_timeout_seconds,
        )

        agno_agent = AgnoAgent(
            model=model,
            instructions=instruction,
            tools=tool_kits,
            user_id=user_id,
            session_id=chat_id,
            markdown=True,
            add_history_to_context=False,
        )

        history_messages = _build_history_messages(history_openai_messages or [])
        history_messages.append(AgnoMessage(role="user", content=prompt))

        try:
            async for event in agno_agent.arun(
                input=history_messages,
                stream=True,
                stream_events=True,
            ):
                if isinstance(event, RunStartedEvent):
                    continue
                if isinstance(event, RunContentEvent):
                    delta = event.content if isinstance(event.content, str) else None
                    if delta:
                        await _emit_run_content(delta)
                    continue
                if isinstance(event, ToolCallStartedEvent):
                    if event.tool is not None:
                        await _emit_tool_start(event.tool)
                    continue
                if isinstance(event, ToolCallCompletedEvent):
                    if event.tool is not None:
                        await _emit_tool_completed(event.tool)
                    continue
                if isinstance(event, ToolCallErrorEvent):
                    if event.tool is not None:
                        logger.error(
                            "Tool call error: %s -> %s",
                            getattr(event.tool, "tool_name", "unknown"),
                            event.error,
                        )
                        await _emit_tool_error(event.tool, event.error)
                    continue
                if isinstance(event, RunCompletedEvent):
                    if not full_text_parts and isinstance(event.content, str) and event.content:
                        full_text_parts.append(event.content)
                    if event.tools:
                        for tool in event.tools:
                            tool_call_id = getattr(tool, "tool_call_id", None) or "unknown"
                            if tool_call_id in emitted_tool_results:
                                continue
                            await _emit_tool_completed(tool)
                    continue
                if isinstance(event, RunErrorEvent):
                    pending_error_msg = _enrich_model_error(
                        event.content or "Agno run error",
                        model_name=model_name,
                        base_url=base_url,
                    )
                    logger.error("Agno run error: %s", pending_error_msg)
                    return
        except ModelProviderError as e:
            pending_error_msg = _enrich_model_error(
                _flatten_exception_message(e),
                model_name=model_name,
                base_url=base_url,
            )
            logger.error("Model provider error: %s", pending_error_msg)
        except BaseException as e:
            pending_error_msg = _enrich_model_error(
                _flatten_exception_message(e),
                model_name=model_name,
                base_url=base_url,
            )
            logger.exception("Agno run failed: %s", pending_error_msg)

    # NOTE:
    # super_rag MCP tools internally call back into /api/v1/* endpoints and
    # currently fall back to SUPER_RAG_API_KEY when request headers are not
    # available in tool-call context. To avoid 401 (wrong/empty env key),
    # inject the per-user system key for this run and restore afterwards.
    previous_super_rag_api_key = os.getenv("SUPER_RAG_API_KEY")
    os.environ["SUPER_RAG_API_KEY"] = super_rag_api_key

    try:
        try:
            async with MCPTools(
                server_params=super_rag_params,
                transport="streamable-http",
                timeout_seconds=request_timeout_seconds,
                tool_name_prefix=SUPER_RAG_PREFIX,
            ) as super_rag_tools:
                tool_kits: List[Any] = [super_rag_tools]
                hindsight_tools_cm = None
                if enable_hindsight:
                    hindsight_tools_cm = MCPTools(
                        server_params=hindsight_params,
                        transport="streamable-http",
                        timeout_seconds=request_timeout_seconds,
                        tool_name_prefix=HINDSIGHT_PREFIX,
                    )
                    try:
                        hindsight_tools = await hindsight_tools_cm.__aenter__()
                        tool_kits.append(hindsight_tools)
                    except Exception as e:  # noqa: BLE001
                        logger.warning(
                            "Hindsight MCP not available, continuing without it: %s", e
                        )
                        hindsight_tools_cm = None

                try:
                    await _run_agno_loop(tool_kits)
                finally:
                    if hindsight_tools_cm is not None:
                        try:
                            await hindsight_tools_cm.__aexit__(None, None, None)
                        except Exception as e:  # noqa: BLE001
                            logger.debug("Hindsight MCP cleanup error: %s", e)
        except BaseException as e:
            if pending_error_msg is None:
                pending_error_msg = _enrich_model_error(
                    _flatten_exception_message(e),
                    model_name=model_name,
                    base_url=base_url,
                )
                logger.exception("Agno runner outer error: %s", pending_error_msg)

        if pending_error_msg:
            await message_queue.put(
                AgentErrorResponse(
                    type="error",
                    id=message_id,
                    data=pending_error_msg,
                    timestamp=int(time.time()),
                )
            )
            raise RuntimeError(pending_error_msg)

        for tool_info in captured_tools.values():
            ref = _build_reference_for_tool(
                tool_info.get("tool_name") or "",
                tool_info.get("tool_args") or {},
                tool_info.get("result"),
            )
            if ref:
                references.append(ref)

        full_content = "".join(full_text_parts) if full_text_parts else "No response generated"

        await asyncio.sleep(0.05)
        await message_queue.put(format_stream_content(message_id, full_content))
        await message_queue.put(format_stream_end(message_id, references=references, urls=[]))

        return {
            "content": full_content,
            "references": references,
        }
    finally:
        if previous_super_rag_api_key is None:
            os.environ.pop("SUPER_RAG_API_KEY", None)
        else:
            os.environ["SUPER_RAG_API_KEY"] = previous_super_rag_api_key
        await message_queue.close()
