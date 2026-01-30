

import json
import logging
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from super_rag.db import models as db_models
from super_rag.db.ops import AsyncDatabaseOps, async_db_ops
from super_rag.exceptions import ChatNotFoundException, ResourceNotFoundException
from super_rag.nodeflow.engine import NodeflowEngine
from super_rag.nodeflow.parser import nodeflowParser
from super_rag.schema import view_models
from super_rag.schema.view_models import Chat, ChatDetails
from super_rag.utils.constant import DOC_QA_REFERENCES, DOCUMENT_URLS
from super_rag.utils.history import (
    MySQLChatMessageHistory,
    fail_response,
    references_response,
    start_response,
    stop_response,
    success_response,
)

logger = logging.getLogger(__name__)


class FrontendFormatter:
    """Format responses according to super_rag custom format"""

    @staticmethod
    def format_stream_start(msg_id: str) -> Dict[str, Any]:
        """Format the start event for streaming"""
        return {
            "type": "start",
            "id": msg_id,
            "timestamp": int(time.time()),
        }

    @staticmethod
    def format_stream_content(msg_id: str, content: str) -> Dict[str, Any]:
        """Format a content chunk for streaming"""
        return {
            "type": "message",
            "id": msg_id,
            "data": content,
            "timestamp": int(time.time()),
        }

    @staticmethod
    def format_stream_end(
        msg_id: str,
        references: List[str] = None,
        memory_count: int = 0,
        urls: List[str] = None,
    ) -> Dict[str, Any]:
        """Format the end event for streaming"""
        if references is None:
            references = []
        if urls is None:
            urls = []

        return {
            "type": "stop",
            "id": msg_id,
            "data": references,
            "memoryCount": memory_count,
            "urls": urls,
            "timestamp": int(time.time()),
        }

    @staticmethod
    def format_complete_response(msg_id: str, content: str) -> Dict[str, Any]:
        """Format a complete response for non-streaming mode"""
        return {
            "type": "message",
            "id": msg_id,
            "data": content,
            "timestamp": int(time.time()),
        }

    @staticmethod
    def format_error(error: str) -> Dict[str, Any]:
        """Format an error response"""
        return {
            "type": "error",
            "id": str(uuid.uuid4()),
            "data": error,
            "timestamp": int(time.time()),
        }


class ChatService:
    """Chat service that handles business logic for chats"""

    def __init__(self, session: AsyncSession = None):
        # Use global db_ops instance by default, or create custom one with provided session
        if session is None:
            self.db_ops = async_db_ops  # Use global instance
        else:
            self.db_ops = AsyncDatabaseOps(session)  # Create custom instance for transaction control

    def build_chat_response(self, chat: db_models.Chat) -> view_models.Chat:
        """Build Chat response object for API return."""
        return Chat(
            id=chat.id,
            title=chat.title,
            agent_id=chat.agent_id,
            peer_type=chat.peer_type,
            peer_id=chat.peer_id,
            created=chat.gmt_created.isoformat(),
            updated=chat.gmt_updated.isoformat(),
        )

    async def create_chat(self, user: str, agent_id: str) -> view_models.Chat:
        agent = await self.db_ops.query_agent(user, agent_id)
        if agent is None:
            raise ResourceNotFoundException("Agent", agent_id)

        # Direct call to repository method, which handles its own transaction
        chat = await self.db_ops.create_chat(user=user, agent_id=agent_id)

        return self.build_chat_response(chat)

    async def list_chats(
        self,
        user: str,
        agent_id: str,
        page: int = 1,
        page_size: int = 50,
    ):
        """List chats with pagination, sorting and search capabilities."""

        # Define sort field mapping
        sort_mapping = {
            "created": db_models.Chat.gmt_created,
        }

        # Define search fields mapping
        search_fields = {"title": db_models.Chat.title}

        async def _execute_paginated_query(session):
            from sqlalchemy import and_, desc, select

            # Build base query
            query = select(db_models.Chat).where(
                and_(
                    db_models.Chat.user == user,
                    db_models.Chat.agent_id == agent_id,
                    db_models.Chat.status != db_models.ChatStatus.DELETED,
                )
            )

            # Build query parameters
            from super_rag.utils.pagination import ListParams, PaginationHelper, PaginationParams, SortParams

            params = ListParams(
                pagination=PaginationParams(page=page, page_size=page_size),
                sort=SortParams(sort_by="created", sort_order="desc"),
            )

            # Use pagination helper
            items, total = await PaginationHelper.paginate_query(
                query=query,
                session=session,
                params=params,
                sort_mapping=sort_mapping,
                search_fields=search_fields,
                default_sort=desc(db_models.Chat.gmt_created),
            )

            # Build chat responses
            chat_responses = []
            for chat in items:
                chat_responses.append(self.build_chat_response(chat))

            return PaginationHelper.build_response(items=chat_responses, total=total, page=page, page_size=page_size)

        return await self.db_ops._execute_query(_execute_paginated_query)

    async def get_chat(self, user: str, agent_id: str, chat_id: str) -> view_models.ChatDetails:
        # Import here to avoid circular imports
        from super_rag.utils.history import query_chat_messages

        chat = await self.db_ops.query_chat(user, agent_id, chat_id)
        if chat is None:
            raise ChatNotFoundException(chat_id)

        # Get chat history
        messages = await query_chat_messages(user, chat_id)

        # Convert ChatMessage objects to dicts for Pydantic validation
        # messages is list[list[ChatMessage]], need to convert each ChatMessage to dict
        history = [
            [msg.model_dump() if hasattr(msg, 'model_dump') else msg for msg in turn]
            for turn in messages
        ]

        # Build response object
        chat_obj = self.build_chat_response(chat)
        return ChatDetails(**chat_obj.model_dump(), history=history)

    async def update_chat(
        self, user: str, agent_id: str, chat_id: str, chat_in: view_models.ChatUpdate
    ) -> view_models.Chat:
        # First check if chat exists
        chat = await self.db_ops.query_chat(user, agent_id, chat_id)
        if chat is None:
            raise ChatNotFoundException(chat_id)

        # Direct call to repository method, which handles its own transaction
        updated_chat = await self.db_ops.update_chat_by_id(user, agent_id, chat_id, chat_in.title)

        if not updated_chat:
            raise ChatNotFoundException(chat_id)

        return self.build_chat_response(updated_chat)

    async def delete_chat(self, user: str, agent_id: str, chat_id: str) -> Optional[view_models.Chat]:
        """Delete chat by ID (idempotent operation)

        Returns the deleted chat or None if already deleted/not found
        """
        # Check if chat exists - if not, silently succeed (idempotent)
        chat = await self.db_ops.query_chat(user, agent_id, chat_id)
        if chat is None:
            return None

        # Direct call to repository method, which handles its own transaction
        deleted_chat = await self.db_ops.delete_chat_by_id(user, agent_id, chat_id)

        if deleted_chat:
            # Clear chat history from Redis
            history = MySQLChatMessageHistory(chat_id)
            await history.clear()

            return self.build_chat_response(deleted_chat)

        return None

    def stream_frontend_sse_response(
        self,
        generator: AsyncGenerator[Any, Any],
        formatter: FrontendFormatter,
        msg_id: str,
        history: MySQLChatMessageHistory = None,
        chat_id: str = None,
    ):
        """Yield SSE events for FastAPI StreamingResponse."""

        async def event_stream():
            full_content = ""
            references = []
            urls = []

            yield f"data: {json.dumps(formatter.format_stream_start(msg_id))}\n\n"
            async for chunk in generator:
                # Handle special tokens for references and URLs
                if chunk.startswith(DOC_QA_REFERENCES):
                    try:
                        references = json.loads(chunk[len(DOC_QA_REFERENCES) :])
                        continue
                    except Exception as e:
                        logger.exception(f"Error parsing doc qa references: {chunk}, {e}")

                if chunk.startswith(DOCUMENT_URLS):
                    try:
                        urls = eval(chunk[len(DOCUMENT_URLS) :])
                        continue
                    except Exception as e:
                        logger.exception(f"Error parsing document urls: {chunk}, {e}")

                yield f"data: {json.dumps(formatter.format_stream_content(msg_id, chunk))}\n\n"
                full_content += chunk

            yield f"data: {json.dumps(formatter.format_stream_end(msg_id, references=references, urls=urls))}\n\n"

            # Save AI message to history after streaming completes
            if history and chat_id:
                try:
                    await history.add_ai_message(
                        content=full_content,
                        chat_id=chat_id,
                        message_id=msg_id,
                        references=references,
                        urls=urls,
                    )
                except Exception as e:
                    logger.error(f"Failed to save AI message to history: {e}")

        return event_stream()

    async def frontend_chat_completions(
        self,
        user: str,
        message: str,
        stream: bool,
        agent_id: str,
        chat_id: str,
        msg_id: str,
        upload_files: List[str] = None,
    ) -> Any:
        """Frontend chat completions with special error handling for UI responses"""

        # Get document metadata and associate documents with message if files are provided
        from super_rag.service.chat_document_service import chat_document_service

        files = await chat_document_service.associate_documents_with_message(
            chat_id=chat_id, message_id=msg_id, files=upload_files or [], user=user
        )

        # Validate agent_id - return formatted error for frontend
        if not agent_id:
            return FrontendFormatter.format_error("agent_id is required")

        agent = await self.db_ops.query_agent(user, agent_id)
        if not agent:
            return FrontendFormatter.format_error("Agent not found")

        # Use flow engine instead of MessageProcessor/pipeline
        formatter = FrontendFormatter()

        # Get agent's flow configuration (deprecated)
        agent_config = json.loads(agent.config or "{}")
        flow_config = agent_config.get("flow")
        if not flow_config:
            return FrontendFormatter.format_error("Agent flow config not found")

        try:
            flow = nodeflowParser.parse(flow_config)
            engine = NodeflowEngine()

            # Prepare initial data for flow execution
            initial_data = {
                "query": message,
                "user": user,
                "message_id": msg_id or str(uuid.uuid4()),
                "chat_id": chat_id,
            }

            # Save user message to history with file metadata
            from super_rag.utils.history import MySQLChatMessageHistory

            history = MySQLChatMessageHistory(chat_id)
            await history.add_user_message(message, msg_id, files=files)

            # Execute flow
            _, system_outputs = await engine.execute_nodeflow(flow, initial_data)
            logger.info("Flow executed successfully!")

            # Find the async generator from flow outputs
            async_generator = None
            nodes = engine.find_end_nodes(flow)
            for node in nodes:
                async_generator = system_outputs[node].get("async_generator")
                if async_generator:
                    break

            if not async_generator:
                return FrontendFormatter.format_error("No output node found")

            # Return streaming or non-streaming response
            if stream:
                return StreamingResponse(
                    self.stream_frontend_sse_response(
                        async_generator(),
                        formatter,
                        msg_id or str(uuid.uuid4()),
                        history=history,
                        chat_id=chat_id,
                    ),
                    media_type="text/event-stream",
                )
            else:
                # Collect all content for non-streaming response
                full_content = ""
                references = []
                urls = []
                async for chunk in async_generator():
                    # Handle special tokens for references and URLs
                    if chunk.startswith(DOC_QA_REFERENCES):
                        try:
                            references = json.loads(chunk[len(DOC_QA_REFERENCES) :])
                            continue
                        except Exception as e:
                            logger.exception(f"Error parsing doc qa references: {chunk}, {e}")

                    if chunk.startswith(DOCUMENT_URLS):
                        try:
                            urls = eval(chunk[len(DOCUMENT_URLS) :])
                            continue
                        except Exception as e:
                            logger.exception(f"Error parsing document urls: {chunk}, {e}")

                    full_content += chunk

                # Save AI message to history
                await history.add_ai_message(
                    content=full_content,
                    chat_id=chat_id,
                    message_id=msg_id or str(uuid.uuid4()),
                    references=references,
                    urls=urls,
                )
                return formatter.format_complete_response(msg_id or str(uuid.uuid4()), full_content)

        except Exception as e:
            logger.exception(e)
            return FrontendFormatter.format_error(str(e))

    async def feedback_message(
        self,
        user: str,
        chat_id: str,
        message_id: str,
        feedback_type: str = None,
        feedback_tag: str = None,
        feedback_message: str = None,
    ) -> dict:
        """Handle message feedback for chat messages"""
        # Get message from Redis history to validate it exists and get context
        history = MySQLChatMessageHistory(chat_id)
        ai_msg = None
        human_msg = None
        for message in await history.messages:
            if message.message_id != message_id:
                continue
            if message.role == "ai":
                ai_msg = message
            if message.role == "human":
                human_msg = message

        if not ai_msg:
            raise ResourceNotFoundException("AI Message", message_id)
        if not human_msg:
            raise ResourceNotFoundException("Human Message", message_id)

        # Handle feedback state change based on UX design principles
        if feedback_type is None:
            # User wants to remove feedback (cancel like/dislike)
            success_removed = await self.db_ops.remove_message_feedback(user, chat_id, message_id)
            result = {"action": "deleted", "success": success_removed}
        else:
            # User wants to set feedback state (like/dislike)
            feedback = await self.db_ops.set_message_feedback_state(
                user=user,
                chat_id=chat_id,
                message_id=message_id,
                feedback_type=feedback_type,
                feedback_tag=feedback_tag,
                feedback_message=feedback_message,
                question=human_msg.get_main_content(),
                original_answer=ai_msg.get_main_content(),
            )
            result = {"action": "upserted", "feedback": feedback}
        return result

    async def handle_websocket_chat(
        self,
        websocket: WebSocket,
        user: str,
        agent_id: str,
        chat_id: str,
    ):
        """Handle WebSocket chat connections and message streaming"""

        try:
            agent = await self.db_ops.query_agent(user, agent_id)
            if not agent:
                await websocket.send_text(fail_response("error", "Agent not found"))
                return

            from super_rag.service.agent_chat_service import AgentChatService

            agent_service = AgentChatService()
            await agent_service.handle_websocket_agent_chat(websocket, user, agent_id, chat_id)
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for agent {agent_id}, chat {chat_id}")
        except Exception as e:
            logger.exception(f"WebSocket error: {e}")
            try:
                await websocket.send_text(fail_response("error", str(e)))
            except Exception as e:
                logger.exception(f"Error sending fail response: {e}")


# Create a global service instance for easy access
# This uses the global db_ops instance and doesn't require session management in views
chat_service_global = ChatService()
