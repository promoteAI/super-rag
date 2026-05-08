import asyncio
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import WebSocket
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketDisconnect

from super_rag.agent import (
    AgentHistoryManager,
    AgentMemoryManager,
    AgentMessageQueue,
    format_agent_setup_error,
    format_invalid_json_error,
    format_invalid_model_spec_error,
    format_mcp_connection_error,
    format_processing_error,
    format_query_required_error,
)
from super_rag.agent.agno_runner import run_agno_agent
from super_rag.agent.exceptions import (
    AgentConfigurationError,
    JSONParsingError,
    MCPAppInitializationError,
    MCPConnectionError,
    handle_agent_error,
    safe_json_parse,
)
from super_rag.agent.response_types import AgentErrorResponse, AgentToolCallResultResponse
from super_rag.db.ops import AsyncDatabaseOps, async_db_ops
from super_rag.history.message import (
    StoredChatMessage,
    create_assistant_message,
    messages_to_openai_format,
)
from super_rag.schema import view_models
from super_rag.service.prompt_template_service import (
    build_agent_query_prompt,
    format_agent_instruction_with_hindsight_bank,
    get_agent_system_prompt,
)
from super_rag.trace import trace_async_function

logger = logging.getLogger(__name__)


def format_websocket_error(error: Exception, data: str) -> AgentErrorResponse:
    try:
        parsed = safe_json_parse(data, "language_detection")
        language = parsed.get("language", "en-US")
    except Exception:
        language = "en-US"

    if isinstance(error, JSONParsingError):
        return format_invalid_json_error(str(error), language)

    if isinstance(error, AgentConfigurationError):
        error_msg = str(error).lower()
        if "query" in error_msg:
            return format_query_required_error(language)
        if "completion" in error_msg or "modelspec" in error_msg:
            return format_invalid_model_spec_error(str(error), language)

    return format_processing_error(str(error), language)


class AgentChatService:
    """
    Chat service for agent-type bots, powered entirely by Agno.

    The previous implementation drove a custom mcp-agent + OpenAIAugmentedLLM
    loop. It has been fully replaced with `agno.agent.Agent` + `agno.tools.mcp`
    (super_rag and hindsight). The WebSocket protocol, history persistence
    and message queue layer are intentionally preserved so callers do not
    need to change.
    """

    def __init__(self, session: AsyncSession = None):
        if session is None:
            self.db_ops = async_db_ops
        else:
            self.db_ops = AsyncDatabaseOps(session)

        self.memory_manager = AgentMemoryManager()
        self.history_manager = AgentHistoryManager()

    async def _convert_db_collections_to_pydantic(self, db_collections) -> List[view_models.Collection]:
        """Convert SQLAlchemy Collection models to Pydantic Collection models"""
        from super_rag.schema.utils import parseCollectionConfig

        pydantic_collections = []
        for db_collection in db_collections:
            pydantic_collection = view_models.Collection(
                id=db_collection.id,
                title=db_collection.title,
                description=db_collection.description,
                type=db_collection.type,
                status=getattr(db_collection, "status", None),
                config=parseCollectionConfig(db_collection.config),
                created=db_collection.gmt_created.isoformat(),
                updated=db_collection.gmt_updated.isoformat(),
            )
            pydantic_collections.append(pydantic_collection)
        return pydantic_collections

    def _parse_websocket_message(
        self, raw_data: str
    ) -> Tuple[Optional[view_models.AgentMessage], Optional[AgentErrorResponse]]:
        """Parse WebSocket message using Go-style error handling."""
        try:
            message_data = safe_json_parse(raw_data, "websocket_message")

            query = (
                message_data.get("query")
                or message_data.get("data")
                or message_data.get("message")
                or ""
            ).strip()
            if not query:
                from super_rag.agent.exceptions import agent_config_invalid

                error = agent_config_invalid("query", "Query is required and cannot be empty")
                error_response = format_websocket_error(error, raw_data)
                return None, error_response

            if not message_data.get("query"):
                message_data["query"] = query

            agent_message = view_models.AgentMessage(**message_data)
            logger.info(f"Agent message: {agent_message}")
            return agent_message, None

        except (JSONParsingError, AgentConfigurationError) as e:
            error_response = format_websocket_error(e, raw_data)
            return None, error_response
        except Exception as e:
            from super_rag.agent.exceptions import agent_config_invalid

            config_error = agent_config_invalid("agent_message", f"Unexpected error: {str(e)}")
            error_response = format_websocket_error(config_error, raw_data)
            return None, error_response

    @handle_agent_error("websocket_agent_chat", reraise=False)
    async def handle_websocket_agent_chat(self, websocket: WebSocket, user: str, agent_id: str, chat_id: str):
        """Handle WebSocket connections for agent-type bot chats with message queue architecture"""
        agent = await self.db_ops.query_agent(user, agent_id)
        if not agent:
            error_response = format_processing_error("Agent not found", "en-US")
            await websocket.send_text(json.dumps(error_response))
            return

        bot_config = None
        default_collections = []
        custom_system_prompt = None
        custom_query_prompt = None

        if agent.config:
            try:
                config_dict = json.loads(agent.config)
                if config_dict:
                    from super_rag.schema.utils import normalize_schema_fields
                    config_dict = normalize_schema_fields(config_dict)
                    bot_config = view_models.AgentConfig(**config_dict)
            except (json.JSONDecodeError, ValueError):
                bot_config = None

        if bot_config and bot_config.agent:
            custom_system_prompt = bot_config.agent.system_prompt_template
            custom_query_prompt = bot_config.agent.query_prompt_template

            if bot_config.agent.collections:
                collection_ids = [collection.id for collection in bot_config.agent.collections]
                db_collections = await self.db_ops.query_collections_by_ids(user, collection_ids)
                default_collections = await self._convert_db_collections_to_pydantic(db_collections)

        try:
            while True:
                data = await websocket.receive_text()
                logger.info(f"Received message from WebSocket: {data}")
                agent_message, error_response = self._parse_websocket_message(data)
                if error_response:
                    await websocket.send_text(json.dumps(error_response))
                    continue
                logger.info(f"Parsed agent message: {agent_message}")
                await self._handle_single_message(
                    websocket,
                    agent_message,
                    user,
                    agent_id,
                    chat_id,
                    bot_config=bot_config,
                    default_collections=default_collections,
                    custom_system_prompt=custom_system_prompt,
                    custom_query_prompt=custom_query_prompt,
                )
        except WebSocketDisconnect as e:
            logger.info(f"WebSocket disconnected for agent chat {chat_id}: {e.code}")
            return
        except RuntimeError as e:
            logger.info(f"WebSocket runtime closed for agent chat {chat_id}: {e}")
            return

    @trace_async_function("name=handle_single_websocket_message", new_trace=True)
    async def _handle_single_message(
        self,
        websocket: WebSocket,
        agent_message: view_models.AgentMessage,
        user: str,
        agent_id: str,
        chat_id: str,
        bot_config=None,
        default_collections=None,
        custom_system_prompt=None,
        custom_query_prompt=None,
    ):
        """Handle a single WebSocket message with its own trace"""
        trace_id = None
        try:
            message_id = str(uuid.uuid4())
            message_queue = AgentMessageQueue()
            trace_id = await self.register_message_queue(
                agent_message.language, chat_id, message_id, message_queue
            )

            from super_rag.service.chat_document_service import chat_document_service

            files = await chat_document_service.associate_documents_with_message(
                chat_id=chat_id,
                message_id=message_id,
                files=[file.id for file in agent_message.files],
                user=user,
            )

            process_task = asyncio.create_task(
                self.process_agent_message(
                    agent_message,
                    user,
                    agent_id,
                    chat_id,
                    message_id,
                    message_queue,
                    bot_config=bot_config,
                    default_collections=default_collections,
                    custom_system_prompt=custom_system_prompt,
                    custom_query_prompt=custom_query_prompt,
                )
            )
            consumer_task = asyncio.create_task(
                self._consume_messages_from_queue(chat_id, message_id, trace_id, message_queue, websocket)
            )
            process_result, consumer_result = await asyncio.gather(
                process_task, consumer_task, return_exceptions=True
            )

            if isinstance(process_result, Exception):
                logger.error(f"Process task failed: {process_result}")
                error_response = self._format_exception_to_error_response(
                    process_result, agent_message.language or "en-US"
                )
                await websocket.send_text(json.dumps(error_response))
                return

            if isinstance(consumer_result, Exception):
                logger.error(f"Consumer task failed: {consumer_result}")
                error_response = format_processing_error(str(consumer_result), agent_message.language or "en-US")
                await websocket.send_text(json.dumps(error_response))
                return

            query = process_result.get("query", "")
            ai_response = process_result.get("content", "")
            references = process_result.get("references", "")
            tool_use_list = consumer_result
            await self._save_conversation_history(
                chat_id, message_id, trace_id, query, ai_response, files, tool_use_list, references
            )

        except Exception as e:
            logger.error(f"Unexpected error processing agent websocket message: {e}")
            error_response = format_processing_error(str(e), agent_message.language or "en-US")
            await websocket.send_text(json.dumps(error_response))
        finally:
            pass

    async def register_message_queue(self, language, chat_id, message_id, message_queue):
        from super_rag.trace import get_current_trace_info

        trace_id, _ = get_current_trace_info()
        return trace_id

    async def _stream_message_content(
        self, message: Dict[str, Any], websocket: WebSocket, chunk_size: int = 5, delay: float = 0.01
    ) -> None:
        """Stream message content in small chunks to simulate typing effect."""
        content = message.get("data", "")
        if not content:
            await websocket.send_text(json.dumps(message))
            return

        chunks = [content[i: i + chunk_size] for i in range(0, len(content), chunk_size)]

        for i, chunk in enumerate(chunks):
            chunk_message = {
                "type": "message",
                "id": message.get("id"),
                "data": chunk,
                "timestamp": message.get("timestamp", int(time.time())),
            }

            await websocket.send_text(json.dumps(chunk_message))
            logger.debug(f"Sent message chunk {i + 1}/{len(chunks)}: {len(chunk)} chars")

            if i < len(chunks) - 1:
                await asyncio.sleep(delay)

    async def _consume_messages_from_queue(
        self, chat_id: str, message_id: str, trace_id: str, message_queue: AgentMessageQueue, websocket: WebSocket
    ) -> List[AgentToolCallResultResponse]:
        """
        Consume messages from queue, send to WebSocket, and collect AgentToolCallResultResponse messages.
        """
        try:
            tool_call_results: List[Dict] = []

            while True:
                message = await message_queue.get()

                if message is None:
                    logger.debug("Received end-of-stream signal from message queue")
                    break

                if isinstance(message, dict) and message.get("type") == "tool_call_result":
                    tool_call_results.append(message)

                if isinstance(message, dict) and message.get("type") == "message":
                    await self._stream_message_content(message, websocket)
                    logger.debug(f"Streamed message content: {message.get('type', 'unknown')}")
                else:
                    await websocket.send_text(json.dumps(message))
                    logger.debug(f"Sent message to WebSocket: {message.get('type', 'unknown')}")

            return tool_call_results

        except Exception as e:
            logger.error(f"Error in message consumer: {e}")
            raise

    async def _resolve_runtime_settings(
        self,
        agent_message: view_models.AgentMessage,
        user: str,
        custom_system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolve provider/api keys and build the system instruction.

        Important:
        - We do NOT trust `completion.model_service_provider` blindly.
        - We first reverse-map provider by model (`api=completion`) from DB.
        - Then we pick a provider that both supports the model and has available key.
        """
        requested_provider = agent_message.completion.model_service_provider
        requested_model = agent_message.completion.model

        # Build model -> provider candidates from DB model registry.
        provider_models = await self.db_ops.query_llm_provider_models()
        candidate_providers: List[str] = []
        fallback_case_insensitive: List[str] = []
        for item in provider_models:
            api_value = getattr(item, "api", None)
            if str(api_value).lower().endswith("completion"):
                if item.model == requested_model:
                    candidate_providers.append(item.provider_name)
                elif item.model.lower() == requested_model.lower():
                    fallback_case_insensitive.append(item.provider_name)

        # Keep unique order, prefer requested provider if it is in candidates.
        dedup = []
        seen = set()
        ordered = candidate_providers or fallback_case_insensitive
        if requested_provider and requested_provider in ordered:
            dedup.append(requested_provider)
            seen.add(requested_provider)
        for p in ordered:
            if p not in seen:
                dedup.append(p)
                seen.add(p)
        candidate_providers = dedup

        # If no provider can be mapped by model, fall back to requested provider for compatibility.
        if not candidate_providers and requested_provider:
            candidate_providers = [requested_provider]

        selected_provider_name = None
        selected_provider_info = None
        selected_api_key = None
        for provider_name in candidate_providers:
            provider_info = await self.db_ops.query_llm_provider_by_name(provider_name)
            if not provider_info:
                continue
            api_key = await self.db_ops.query_provider_api_key(
                provider_name, user_id=user, need_public=True
            )
            if not api_key:
                continue
            selected_provider_name = provider_name
            selected_provider_info = provider_info
            selected_api_key = api_key
            break

        if not selected_provider_info or not selected_api_key:
            candidate_preview = ", ".join(candidate_providers) if candidate_providers else "none"
            raise AgentConfigurationError(
                "completion.model_service_provider",
                (
                    f"Cannot resolve provider/base_url/api_key for model '{requested_model}'. "
                    f"Requested provider='{requested_provider}', matched providers=[{candidate_preview}]"
                ),
            )

        if requested_provider and selected_provider_name != requested_provider:
            logger.warning(
                "Model/provider mismatch detected, auto-switched provider from '%s' to '%s' for model '%s'",
                requested_provider,
                selected_provider_name,
                requested_model,
            )

        super_rag_api_keys = await self.db_ops.query_api_keys(user, is_system=True)
        super_rag_api_key = None
        for item in super_rag_api_keys:
            super_rag_api_key = item.key
        if not super_rag_api_key:
            logger.info(f"No super_rag API key found for user {user}, creating a new system key")
            try:
                api_key_result = await self.db_ops.create_api_key(
                    user=user, description="super_rag", is_system=True
                )
                super_rag_api_key = api_key_result.key
                logger.info(f"Successfully created new system super_rag API key for user {user}")
            except Exception as e:
                error_msg = f"Failed to create super_rag API key for user {user}: {str(e)}"
                logger.error(error_msg)
                raise AgentConfigurationError("super_rag_api_key", error_msg)

        base_instruction = (
            custom_system_prompt
            if custom_system_prompt
            else get_agent_system_prompt(language=agent_message.language)
        )
        system_prompt = format_agent_instruction_with_hindsight_bank(
            base_instruction, user, agent_message.language or "en-US"
        )

        return {
            "provider_name": selected_provider_name,
            "api_key": selected_api_key,
            "base_url": selected_provider_info.base_url,
            "super_rag_api_key": super_rag_api_key,
            "super_rag_mcp_url": os.getenv("super_rag_MCP_URL", "http://localhost:8000/mcp/"),
            "system_prompt": system_prompt,
        }

    async def _build_history_openai_messages(
        self, chat_id: str, context_limit: int = 4
    ) -> List[Dict[str, Any]]:
        """Load chat history and convert it to OpenAI-format dicts for Agno."""
        try:
            history = await self.history_manager.get_chat_history(chat_id)
            messages = await history.messages
            if not messages:
                return []
            recent_messages = (
                messages[-(context_limit * 2):]
                if len(messages) > context_limit * 2
                else messages
            )
            return messages_to_openai_format(recent_messages)
        except Exception as e:
            logger.warning(f"Failed to load chat history for {chat_id}: {e}")
            return []

    async def _validate_model_provider_compatibility(
        self,
        provider_name: str,
        model_name: str,
        base_url: str,
    ) -> None:
        """
        Validate model/provider/base_url compatibility before invoking Agno.

        The DB keeps provider-scoped model lists (llm_provider_models). If the
        requested completion model is not in that provider's completion models,
        we fail early with an actionable message instead of letting provider SDK
        fail later with opaque "Unknown model error".
        """
        provider_models = await self.db_ops.query_llm_provider_models(provider_name=provider_name)
        completion_models: List[str] = []
        for item in provider_models:
            api_value = getattr(item, "api", None)
            if str(api_value).lower().endswith("completion"):
                completion_models.append(item.model)

        if not completion_models:
            logger.warning(
                "No completion models configured for provider=%s (base_url=%s), skip strict compatibility check",
                provider_name,
                base_url,
            )
            return

        if model_name in completion_models:
            return

        # Also accept case-insensitive exact match.
        lower_map = {m.lower(): m for m in completion_models}
        if model_name.lower() in lower_map:
            return

        preview = ", ".join(completion_models[:10])
        if len(completion_models) > 10:
            preview += ", ..."
        raise AgentConfigurationError(
            "completion.model",
            (
                f"Model '{model_name}' does not match provider '{provider_name}' "
                f"(base_url='{base_url}'). Available completion models: [{preview}]"
            ),
        )

    async def process_agent_message(
        self,
        agent_message: view_models.AgentMessage,
        user: str,
        agent_id: str,
        chat_id: str,
        message_id: str,
        message_queue: AgentMessageQueue,
        bot_config=None,
        default_collections=None,
        custom_system_prompt=None,
        custom_query_prompt=None,
    ) -> Dict[str, Any]:
        # Priority: agent_message > bot_config > defaults
        final_completion = agent_message.completion
        final_collections = agent_message.collections

        if not final_completion and bot_config and bot_config.agent and bot_config.agent.completion:
            final_completion = bot_config.agent.completion

        if not final_collections and default_collections:
            final_collections = default_collections

        if not final_completion or not final_completion.model:
            raise AgentConfigurationError(
                config_key="completion.model",
                reason="Model specification is required for AI response generation",
            )

        merged_agent_message = view_models.AgentMessage(
            query=agent_message.query,
            collections=final_collections,
            completion=final_completion,
            web_search_enabled=agent_message.web_search_enabled,
            language=agent_message.language,
            files=agent_message.files,
        )

        runtime = await self._resolve_runtime_settings(
            merged_agent_message, user, custom_system_prompt
        )
        await self._validate_model_provider_compatibility(
            provider_name=runtime["provider_name"],
            model_name=final_completion.model,
            base_url=runtime["base_url"],
        )

        history_openai_messages = await self._build_history_openai_messages(chat_id, context_limit=4)

        comprehensive_prompt = build_agent_query_prompt(
            chat_id,
            agent_message=merged_agent_message,
            user=user,
            custom_template=custom_query_prompt,
        )

        run_result = await run_agno_agent(
            message_id=message_id,
            message_queue=message_queue,
            user_id=user,
            chat_id=chat_id,
            api_key=runtime["api_key"],
            base_url=runtime["base_url"],
            model_name=final_completion.model,
            instruction=runtime["system_prompt"],
            prompt=comprehensive_prompt,
            history_openai_messages=history_openai_messages,
            super_rag_mcp_url=runtime["super_rag_mcp_url"],
            super_rag_api_key=runtime["super_rag_api_key"],
            hindsight_bank_id=user,
            enable_hindsight=True,
            temperature=final_completion.temperature
            if final_completion.temperature is not None
            else 0.7,
            max_tokens=final_completion.max_tokens or 8192,
        )

        return {
            "query": merged_agent_message.query,
            "content": run_result.get("content", ""),
            "references": run_result.get("references", []),
        }

    def _format_exception_to_error_response(self, exception: Exception, language: str) -> AgentErrorResponse:
        """Convert exception to properly formatted error response."""
        if isinstance(exception, AgentConfigurationError):
            error_msg = str(exception).lower()
            if "model" in error_msg or "completion" in error_msg:
                return format_invalid_model_spec_error(str(exception), language)
            else:
                return format_agent_setup_error(str(exception), language)

        elif isinstance(exception, MCPConnectionError):
            return format_mcp_connection_error(language)

        elif isinstance(exception, MCPAppInitializationError):
            return format_agent_setup_error(str(exception), language)

        else:
            return format_processing_error(str(exception), language)

    async def chat_for_evaluation(
        self,
        query: str,
        user_id: str,
        model_name: str,
        model_service_provider: str,
        custom_llm_provider: Optional[Dict],
        collections: List[view_models.Collection],
        language: str = "en-US",
    ) -> StoredChatMessage | AgentErrorResponse:
        """
        Handle internal chat requests for evaluation tasks, bypassing WebSockets.
        Returns the AI response as a dictionary representation of StoredChatMessage.
        """
        agent_message = view_models.AgentMessage(
            query=query,
            completion=view_models.ModelSpec(
                model=model_name,
                model_service_provider=model_service_provider,
                custom_llm_provider=custom_llm_provider,
            ),
            collections=collections,
            language=language,
        )

        chat_id = f"eval-chat-{uuid.uuid4()}"
        message_id = str(uuid.uuid4())
        trace_id = None

        try:
            message_queue = AgentMessageQueue()
            trace_id = await self.register_message_queue(
                agent_message.language, chat_id, message_id, message_queue
            )

            async def consume_and_collect():
                tool_calls = []
                while True:
                    message = await message_queue.get()
                    if message is None:
                        break
                    if isinstance(message, dict) and message.get("type") == "tool_call_result":
                        tool_calls.append(message)
                return tool_calls

            process_task = asyncio.create_task(
                self.process_agent_message(
                    agent_message,
                    user_id,
                    None,
                    chat_id,
                    message_id,
                    message_queue,
                )
            )
            consumer_task = asyncio.create_task(consume_and_collect())

            process_result, consumer_result = await asyncio.gather(
                process_task, consumer_task, return_exceptions=True
            )

            if isinstance(process_result, Exception):
                logger.error(f"Process task failed: {process_result}")
                error_response = self._format_exception_to_error_response(
                    process_result, agent_message.language or "en-US"
                )
                return error_response

            if isinstance(consumer_result, Exception):
                logger.error(f"Consumer task failed: {consumer_result}")
                error_response = format_processing_error(str(consumer_result), agent_message.language or "en-US")
                return error_response

            query = process_result.get("query", "")
            ai_response = process_result.get("content", "")
            references = process_result.get("references", "")
            tool_use_list = consumer_result

            ai_message = create_assistant_message(
                content=ai_response,
                chat_id=chat_id,
                message_id=message_id,
                trace_id=trace_id,
                tool_use_list=tool_use_list,
                references=references,
            )
            return ai_message

        except Exception as e:
            logger.error(f"Error during internal agent chat for evaluation: {e}")
            error_response = self._format_exception_to_error_response(e, agent_message.language or "en-US")
            return error_response
        finally:
            pass

    async def _save_conversation_history(
        self,
        chat_id: str,
        message_id: str,
        trace_id: str,
        query: str,
        ai_response: str,
        files: List[Dict[str, Any]],
        tool_use_list: List[Dict],
        tool_references: List[Dict[str, Any]],
    ) -> None:
        """Save conversation history from successful agent processing."""
        try:
            history = await self.history_manager.get_chat_history(chat_id)

            history_saved = await self.history_manager.save_conversation_turn(
                message_id=message_id,
                trace_id=trace_id,
                history=history,
                user_query=query,
                ai_response=ai_response,
                files=files,
                tool_use_list=tool_use_list,
                tool_references=tool_references,
            )

            if not history_saved:
                logger.warning(f"Failed to save conversation history for chat: {chat_id}")

        except Exception as e:
            logger.error(f"Error saving conversation history for chat {chat_id}: {e}")
