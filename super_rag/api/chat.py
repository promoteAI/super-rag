import asyncio
import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, WebSocket, status
from fastapi.responses import StreamingResponse

from super_rag.db.models import User
from super_rag.exceptions import BusinessException
from super_rag.schema import view_models
from super_rag.service.chat_collection_service import chat_collection_service
from super_rag.service.chat_document_service import chat_document_service
from super_rag.service.chat_service import chat_service_global
from super_rag.service.chat_title_service import chat_title_service
from super_rag.service.collection_service import collection_service
from super_rag.api.auth import required_user
from super_rag.ag_ui import stream_ag_ui_events, get_ag_ui_sse_media_type, AGUIRunRequest
from super_rag.agent import AgentMessageQueue
from super_rag.service.agent_chat_service import AgentChatService
from super_rag.agent.agent_event_listener import agent_event_listener

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chats"])


@router.post("/agents/{agent_id}/chats")
async def create_chat_view(request: Request, agent_id: str, user: User = Depends(required_user)) -> view_models.Chat:
    return await chat_service_global.create_chat(str(user.id), agent_id)


@router.get("/agents/{agent_id}/chats")
async def list_chats_view(
    request: Request,
    agent_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: User = Depends(required_user),
) -> view_models.ChatList:
    return await chat_service_global.list_chats(str(user.id), agent_id, page, page_size)


@router.get("/agents/{agent_id}/chats/{chat_id}")
async def get_chat_view(
    request: Request, agent_id: str, chat_id: str, user: User = Depends(required_user)
) -> view_models.ChatDetails:
    return await chat_service_global.get_chat(str(user.id), agent_id, chat_id)


@router.put("/agents/{agent_id}/chats/{chat_id}")
async def update_chat_view(
    request: Request,
    agent_id: str,
    chat_id: str,
    chat_in: view_models.ChatUpdate,
    user: User = Depends(required_user),
) -> view_models.Chat:
    return await chat_service_global.update_chat(str(user.id), agent_id, chat_id, chat_in)


@router.post("/agents/{agent_id}/chats/{chat_id}/messages/{message_id}")
async def feedback_message_view(
    request: Request,
    agent_id: str,
    chat_id: str,
    message_id: str,
    feedback: view_models.Feedback,
    user: User = Depends(required_user),
):
    return await chat_service_global.feedback_message(
        str(user.id), chat_id, message_id, feedback.type, feedback.tag, feedback.message
    )

# 优化 WebSocket 握手响应，确保接管和定制协议头部
@router.websocket("/agents/{agent_id}/chats/{chat_id}/connect")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    agent_id: str,
    chat_id: str,
    user: User = Depends(required_user),
):
    """
    WebSocket 端点，用于与机器人进行实时聊天。
    对协议头部和握手进行优化，提高兼容性和调试体验。
    先 accept 再处理业务，异常时显式关闭连接，避免客户端收到 1006。
    """
    logger.info(f"WebSocket chat endpoint called with agent_id: {agent_id}, chat_id: {chat_id}, user: {user}")
    try:
        # 不传自定义 headers，避免 permessage-deflate 等扩展导致握手后立即 1006 断开
        await websocket.accept()
    except Exception as e:
        logger.exception(f"WebSocket accept failed: {e}")
        raise
    logger.debug("WebSocket handshake: 协议升级完成。")
    try:
        await chat_service_global.handle_websocket_chat(
            websocket,
            str(user.id),
            agent_id,
            chat_id
        )
    except Exception as e:
        logger.exception(f"WebSocket handler error: {e}")
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
        raise


def _build_agent_message_from_ag_ui(
    request: AGUIRunRequest,
    bot_config,
    default_collections: list,
) -> view_models.AgentMessage:
    """Build AgentMessage from AGUIRunRequest and optional bot_config/default_collections."""
    query = request.get_query_from_messages()
    fp = request.forwarded_props or {}

    collections = default_collections or []
    if fp.get("collections") and isinstance(fp["collections"], list):
        collections = [
            view_models.Collection(id=c.get("id"), title=c.get("title"), description=c.get("description"), type=c.get("type"), status=c.get("status"), config=c.get("config"), created=c.get("created"), updated=c.get("updated"))
            for c in fp["collections"]
            if isinstance(c, dict)
        ]

    completion = None
    if bot_config and getattr(bot_config, "agent", None) and getattr(bot_config.agent, "completion", None):
        completion = bot_config.agent.completion
    if fp.get("completion") and isinstance(fp["completion"], dict):
        completion = view_models.ModelSpec(**{k: v for k, v in fp["completion"].items() if k in view_models.ModelSpec.model_fields})

    language = (fp.get("language") or "en-US") if isinstance(fp.get("language"), str) else "en-US"
    files = fp.get("files") or []
    if isinstance(files, list):
        files = [view_models.File(id=f.get("id"), name=f.get("name")) for f in files if isinstance(f, dict)]
    web_search_enabled = bool(fp.get("web_search_enabled", False))

    return view_models.AgentMessage(
        query=query or "",
        collections=collections,
        completion=completion,
        web_search_enabled=web_search_enabled,
        language=language,
        files=files or None,
    )


@router.post("/agents/{agent_id}/chats/{chat_id}/ag-ui")
async def ag_ui_run_endpoint(
    request: Request,
    agent_id: str,
    chat_id: str,
    body: AGUIRunRequest,
    user: User = Depends(required_user),
):
    """
    AG-UI protocol SSE endpoint. Accepts RunAgentInput-like body, runs agent, streams AG-UI events.
    """
    agent_service = AgentChatService()
    agent = await agent_service.db_ops.query_agent(str(user.id), agent_id)
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    bot_config = None
    default_collections = []
    custom_system_prompt = None
    custom_query_prompt = None
    if agent.config:
        try:
            from super_rag.schema.utils import normalize_schema_fields
            config_dict = json.loads(agent.config)
            if config_dict:
                config_dict = normalize_schema_fields(config_dict)
                bot_config = view_models.AgentConfig(**config_dict)
        except (json.JSONDecodeError, ValueError):
            bot_config = None
    if bot_config and getattr(bot_config, "agent", None):
        custom_system_prompt = getattr(bot_config.agent, "system_prompt_template", None)
        custom_query_prompt = getattr(bot_config.agent, "query_prompt_template", None)
        if getattr(bot_config.agent, "collections", None):
            collection_ids = [c.id for c in bot_config.agent.collections]
            db_collections = await agent_service.db_ops.query_collections_by_ids(str(user.id), collection_ids)
            default_collections = await agent_service._convert_db_collections_to_pydantic(db_collections)

    agent_message = _build_agent_message_from_ag_ui(body, bot_config, default_collections)
    query = agent_message.query
    if not (query and query.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing query (no user message in body)")

    message_id = body.run_id
    message_queue = AgentMessageQueue()
    trace_id = await agent_service.register_message_queue(agent_message.language or "en-US", chat_id, message_id, message_queue)

    async def on_done():
        if trace_id:
            await agent_event_listener.unregister_listener(str(trace_id))

    process_task = asyncio.create_task(
        agent_service.process_agent_message(
            agent_message,
            str(user.id),
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

    tool_use_list = []

    async def stream_with_cleanup():
        try:
            accept = request.headers.get("accept") or ""
            async for chunk in stream_ag_ui_events(
                message_queue,
                thread_id=chat_id,
                run_id=message_id,
                message_id=message_id,
                accept_header=accept,
                tool_call_results=tool_use_list,
            ):
                yield chunk
        finally:
            await on_done()
            # Save conversation history after stream ends (same as WebSocket flow)
            try:
                process_result = await process_task
                if isinstance(process_result, dict):
                    await agent_service._save_conversation_history(
                        chat_id=chat_id,
                        message_id=message_id,
                        trace_id=trace_id or "",
                        query=process_result.get("query", ""),
                        ai_response=process_result.get("content", ""),
                        files=[],
                        tool_use_list=tool_use_list,
                        tool_references=process_result.get("references") or [],
                    )
            except Exception as e:
                logger.exception("AG-UI: failed to save conversation history: %s", e)

    media_type = get_ag_ui_sse_media_type(request.headers.get("accept"))
    return StreamingResponse(
        stream_with_cleanup(),
        media_type=media_type,
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/agents/{agent_id}/chats/{chat_id}/title")
async def generate_chat_title_view(
    agent_id: str,
    chat_id: str,
    request_body: view_models.TitleGenerateRequest = view_models.TitleGenerateRequest(),
    user: User = Depends(required_user),
) -> view_models.TitleGenerateResponse:
    try:
        title = await chat_title_service.generate_title(
            user_id=str(user.id),
            agent_id=agent_id,
            chat_id=chat_id,
            max_length=request_body.max_length,
            language=request_body.language,
            turns=request_body.turns,
        )
        return {"title": title}
    except BusinessException as be:
        raise HTTPException(status_code=400, detail={"error_code": be.error_code.name, "message": str(be)})


@router.post("/chat/completions/frontend", tags=["chats"])
async def frontend_chat_completions_view(request: Request, user: User = Depends(required_user)):
    body = await request.body()

    # Try to parse JSON first, fallback to text for backward compatibility
    try:
        data = json.loads(body.decode("utf-8"))
        message = data.get("message", "")
        files = data.get("files", [])
    except (json.JSONDecodeError, UnicodeDecodeError):
        # Fallback to text message for backward compatibility
        message = body.decode("utf-8")
        files = []

    query_params = dict(request.query_params)
    stream = query_params.get("stream", "false").lower() == "true"
    agent_id = query_params.get("agent_id", "")
    chat_id = query_params.get("chat_id", "")
    msg_id = request.headers.get("msg_id", "")
    return await chat_service_global.frontend_chat_completions(
        str(user.id), 
        message, 
        stream, 
        agent_id, 
        chat_id, 
        msg_id, 
        files,
    )


@router.post("/chats/{chat_id}/search")
async def search_chat_files_view(
    request: Request,
    chat_id: str,
    data: view_models.SearchRequest,
    user: User = Depends(required_user),
) -> view_models.SearchResult:
    """Search files within a specific chat using hybrid search capabilities"""
    try:
        # Get user's chat collection
        chat_collection_id = await chat_collection_service.get_user_chat_collection_id(str(user.id))
        if not chat_collection_id:
            raise HTTPException(status_code=404, detail="Chat collection not found")

        if not chat_id:
            raise HTTPException(status_code=400, detail="Chat ID is required")

        # Execute search flow using the helper method from collection_service
        items, _ = await collection_service.execute_search_flow(
            data=data,
            collection_id=chat_collection_id,
            search_user_id=str(user.id),
            chat_id=chat_id,  # Add chat_id for filtering in chat searches
            flow_name="chat_search",
            flow_title="Chat Search",
        )

        # Return search result without saving to database for chat searches
        from super_rag.schema.view_models import SearchResult

        return SearchResult(
            id=None,  # No ID since not saved
            query=data.query,
            vector_search=data.vector_search,
            fulltext_search=data.fulltext_search,
            graph_search=data.graph_search,
            summary_search=data.summary_search,
            items=items,
            created=None,  # No creation time since not saved
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search chat files: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/chats/{chat_id}/documents")
async def upload_chat_document_view(
    request: Request,
    chat_id: str,
    file: UploadFile = File(...),
    user: User = Depends(required_user),
) -> view_models.Document:
    """Upload a document to a chat session"""
    return await chat_document_service.upload_chat_document(chat_id=chat_id, user_id=str(user.id), file=file)


@router.get("/chats/{chat_id}/documents/{document_id}")
async def get_chat_document_view(
    request: Request,
    chat_id: str,
    document_id: str,
    user: User = Depends(required_user),
) -> view_models.Document:
    """Get chat document details"""
    document = await chat_document_service.get_chat_document_by_id(
        chat_id=chat_id, document_id=document_id, user_id=str(user.id)
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return document


@router.delete("/agents/{agent_id}/chats/{chat_id}")
async def delete_chat_view(request: Request, agent_id: str, chat_id: str, user: User = Depends(required_user)):
    await chat_service_global.delete_chat(str(user.id), agent_id, chat_id)
    return Response(status_code=204)
