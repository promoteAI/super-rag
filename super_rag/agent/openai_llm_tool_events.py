"""
OpenAI Augmented LLM that explicitly sends each MCP tool call (start + result) to the frontend,
and supports token-by-token streaming of the final text response.
"""

import functools
import json
import logging
import re
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from openai.types.chat import (
    ChatCompletion,
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessage,
    ChatCompletionMessageParam,
    ChatCompletionMessageToolCall,
    ChatCompletionSystemMessageParam,
    ChatCompletionToolParam,
)
from openai.types.chat.chat_completion_message_tool_call import Function as ToolCallFunction
from mcp.types import CallToolRequest, CallToolResult, ListToolsResult, TextContent
from mcp_agent.workflows.llm.augmented_llm import RequestParams
from mcp_agent.workflows.llm.augmented_llm_openai import (
    OpenAIAugmentedLLM,
    OpenAICompletionTasks,
    RequestCompletionRequest,
)
from mcp_agent.workflows.llm.multipart_converter_openai import OpenAIConverter
from mcp_agent.tracing.telemetry import get_tracer
from mcp_agent.utils.common import ensure_serializable

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
    OpenAI Augmented LLM that forwards each MCP tool call to the frontend
    and supports real-time token streaming for text responses.
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
            try:
                args_str = json.dumps(request.params.arguments or {}, ensure_ascii=False)
            except Exception:
                args_str = None
            tid = tool_call_id or "unknown"
            try:
                msg = format_tool_call_result(
                    message_id,
                    display_text,
                    tool_name,
                    None,
                    tool_call_id=tid,
                    arguments=args_str,
                )
                await message_queue.put(msg)
            except Exception as e:
                logger.warning("Failed to send tool_call_result to frontend: %s", e)
        return await super().post_tool_call(
            tool_call_id=tool_call_id, request=request, result=result
        )

    # ------------------------------------------------------------------
    # Streaming generate: uses OpenAI stream=True so text tokens are
    # forwarded to the frontend message queue in real-time, while tool
    # call iterations are handled identically to the base class.
    # ------------------------------------------------------------------

    async def generate_str_streaming(
        self,
        message,
        request_params: RequestParams | None = None,
    ) -> str:
        """
        Like generate_str but streams text tokens to the message queue.
        Tool-call iterations still use non-streaming calls (same as base).
        Only the *final* text response iteration uses streaming.
        """
        ctx = get_tool_call_context()
        if not ctx:
            return await self.generate_str(message, request_params)

        message_id, message_queue = ctx

        params = self.get_request_params(request_params)

        messages: List[ChatCompletionMessageParam] = []
        if params.use_history:
            messages.extend(self.history.get())

        system_prompt = self.instruction or params.systemPrompt
        if system_prompt and len(messages) == 0:
            messages.append(
                ChatCompletionSystemMessageParam(role="system", content=system_prompt)
            )
        messages.extend(OpenAIConverter.convert_mixed_messages_to_openai(message))

        response_list: ListToolsResult = await self.agent.list_tools(
            tool_filter=params.tool_filter
        )
        available_tools: Optional[List[ChatCompletionToolParam]] = [
            ChatCompletionToolParam(
                type="function",
                function={
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            )
            for tool in response_list.tools
        ]
        if not available_tools:
            available_tools = None

        model = await self.select_model(params)
        user = params.user or getattr(self.context.config.openai, "user", None)

        final_text_parts: List[str] = []

        for i in range(params.max_iterations):
            arguments: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "tools": available_tools,
            }
            if user:
                arguments["user"] = user
            if params.stopSequences is not None:
                arguments["stop"] = params.stopSequences

            if self._reasoning(model):
                arguments["max_completion_tokens"] = params.maxTokens
                arguments["reasoning_effort"] = (
                    params.reasoning_effort or self._reasoning_effort
                )
            else:
                arguments["max_tokens"] = params.maxTokens

            if params.metadata:
                arguments.update(params.metadata)

            # Try streaming call via direct OpenAI client
            streamed_text, finish_reason, tool_calls, response_usage = (
                await self._streaming_completion(arguments, message_id, message_queue)
            )

            if response_usage and self.context.token_counter:
                await self.context.token_counter.record_usage(
                    input_tokens=response_usage.get("prompt_tokens", 0),
                    output_tokens=response_usage.get("completion_tokens", 0),
                    model_name=model,
                    provider=self.provider,
                )

            # Build ChatCompletionMessage equivalent
            sanitized_name = (
                re.sub(r"[^a-zA-Z0-9_-]", "_", self.name)
                if isinstance(self.name, str)
                else None
            )
            assistant_msg_params: Dict[str, Any] = {"role": "assistant"}
            if sanitized_name:
                assistant_msg_params["name"] = sanitized_name
            if streamed_text:
                assistant_msg_params["content"] = streamed_text
            if tool_calls:
                assistant_msg_params["tool_calls"] = [
                    tc.model_dump() if hasattr(tc, "model_dump") else tc
                    for tc in tool_calls
                ]
            messages.append(ChatCompletionAssistantMessageParam(**assistant_msg_params))

            if finish_reason in ("tool_calls", "function_call") and tool_calls:
                tool_tasks = [
                    functools.partial(self.execute_tool_call, tool_call=tc)
                    for tc in tool_calls
                ]
                tool_results = await self.executor.execute_many(tool_tasks)
                for result in tool_results:
                    if isinstance(result, BaseException):
                        logger.error("Tool execution error: %s", result)
                        continue
                    if result is not None:
                        messages.append(result)
            elif finish_reason in ("stop", "length", "content_filter", None):
                if streamed_text:
                    final_text_parts.append(streamed_text)
                break
            else:
                if streamed_text:
                    final_text_parts.append(streamed_text)
                break

        if params.use_history:
            self.history.set(messages)

        return "\n".join(final_text_parts)

    async def _streaming_completion(
        self,
        arguments: Dict[str, Any],
        message_id: str,
        message_queue,
    ) -> tuple:
        """
        Execute a single OpenAI ChatCompletion call with stream=True.
        Forwards text deltas to message_queue and assembles tool calls.
        Returns (text, finish_reason, tool_calls, usage_dict).
        """
        from .stream_formatters import format_stream_content

        config = self.context.config.openai

        try:
            async with AsyncOpenAI(
                api_key=config.api_key,
                base_url=config.base_url,
                default_headers=(
                    config.default_headers
                    if hasattr(config, "default_headers")
                    else None
                ),
            ) as client:
                stream_args = {**arguments, "stream": True, "stream_options": {"include_usage": True}}
                stream = await client.chat.completions.create(**stream_args)

                collected_text = ""
                finish_reason = None
                tool_call_map: Dict[int, Dict[str, Any]] = {}
                usage_info: Optional[Dict[str, int]] = None

                async for chunk in stream:
                    if not chunk.choices and chunk.usage:
                        usage_info = {
                            "prompt_tokens": chunk.usage.prompt_tokens or 0,
                            "completion_tokens": chunk.usage.completion_tokens or 0,
                        }
                        continue

                    if not chunk.choices:
                        continue

                    delta = chunk.choices[0].delta
                    chunk_finish = chunk.choices[0].finish_reason

                    if chunk_finish:
                        finish_reason = chunk_finish

                    # Text content delta
                    if delta and delta.content:
                        collected_text += delta.content
                        try:
                            await message_queue.put({
                                "type": "text_delta",
                                "id": message_id,
                                "data": delta.content,
                            })
                        except Exception:
                            pass

                    # Tool call deltas
                    if delta and delta.tool_calls:
                        for tc_delta in delta.tool_calls:
                            idx = tc_delta.index
                            if idx not in tool_call_map:
                                tool_call_map[idx] = {
                                    "id": tc_delta.id or "",
                                    "function_name": "",
                                    "function_arguments": "",
                                }
                            entry = tool_call_map[idx]
                            if tc_delta.id:
                                entry["id"] = tc_delta.id
                            if tc_delta.function:
                                if tc_delta.function.name:
                                    entry["function_name"] += tc_delta.function.name
                                if tc_delta.function.arguments:
                                    entry["function_arguments"] += tc_delta.function.arguments

                # Assemble tool calls
                assembled_tool_calls: Optional[List[ChatCompletionMessageToolCall]] = None
                if tool_call_map:
                    assembled_tool_calls = []
                    for idx in sorted(tool_call_map.keys()):
                        entry = tool_call_map[idx]
                        assembled_tool_calls.append(
                            ChatCompletionMessageToolCall(
                                id=entry["id"],
                                type="function",
                                function=ToolCallFunction(
                                    name=entry["function_name"],
                                    arguments=entry["function_arguments"],
                                ),
                            )
                        )

                return collected_text, finish_reason, assembled_tool_calls, usage_info

        except Exception as e:
            logger.error("Streaming completion failed, falling back to non-streaming: %s", e)
            # Fallback to non-streaming call
            request = RequestCompletionRequest(
                config=config,
                payload=arguments,
            )
            response: ChatCompletion = await self.executor.execute(
                OpenAICompletionTasks.request_completion_task,
                ensure_serializable(request),
            )
            if isinstance(response, BaseException):
                raise response

            text = ""
            tool_calls = None
            fr = None
            usage = None

            if response.choices:
                choice = response.choices[0]
                text = choice.message.content or ""
                tool_calls = choice.message.tool_calls
                fr = choice.finish_reason
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }

            return text, fr, tool_calls, usage
