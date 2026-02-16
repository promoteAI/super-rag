"""
OpenAI Augmented LLM that explicitly sends each MCP tool call (start + result) to the frontend.
"""

import json
import logging
from typing import Any, Optional

from mcp.types import CallToolRequest, CallToolResult, TextContent
from mcp_agent.workflows.llm.augmented_llm_openai import OpenAIAugmentedLLM

from .stream_formatters import format_tool_call_result, format_tool_call_start
from .tool_call_context import get_tool_call_context

logger = logging.getLogger(__name__)


def _call_result_to_display_text(result: CallToolResult) -> str:
    """Turn MCP CallToolResult content into a single display string."""
    if not result.content:
        return "[empty result]"
    parts = []
    for c in result.content:
        if isinstance(c, TextContent):
            parts.append(c.text)
        elif isinstance(c, dict) and c.get("type") == "text":
            parts.append(c.get("text", ""))
        else:
            parts.append(str(c))
    return "\n".join(parts) if parts else "[empty result]"


class SuperRagOpenAIAugmentedLLM(OpenAIAugmentedLLM):
    """
    OpenAI Augmented LLM that forwards each MCP tool call to the frontend:
    - Before calling the tool: send tool_call_start (tool name + arguments).
    - After the tool returns: send tool_call_result (formatted result).
    """

    async def pre_tool_call(
        self, tool_call_id: str | None, request: CallToolRequest
    ) -> CallToolRequest | bool:
        ctx = get_tool_call_context()
        if ctx:
            message_id, message_queue = ctx
            tid = tool_call_id or "unknown"
            args_str = json.dumps(request.params.arguments or {}, ensure_ascii=False)
            try:
                msg = format_tool_call_start(
                    message_id, tid, request.params.name, args_str
                )
                await message_queue.put(msg)
            except Exception as e:
                logger.warning("Failed to send tool_call_start to frontend: %s", e)
        return await super().pre_tool_call(tool_call_id=tool_call_id, request=request)

    async def post_tool_call(
        self,
        tool_call_id: str | None,
        request: CallToolRequest,
        result: CallToolResult,
    ) -> CallToolResult:
        ctx = get_tool_call_context()
        if ctx:
            message_id, message_queue = ctx
            display_text = _call_result_to_display_text(result)
            tool_name = request.params.name
            tid = tool_call_id or "unknown"
            try:
                msg = format_tool_call_result(
                    message_id,
                    display_text,
                    tool_name,
                    None,
                    tool_call_id=tid,
                )
                await message_queue.put(msg)
            except Exception as e:
                logger.warning("Failed to send tool_call_result to frontend: %s", e)
        return await super().post_tool_call(
            tool_call_id=tool_call_id, request=request, result=result
        )
