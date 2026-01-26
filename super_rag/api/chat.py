
import json
import logging

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, WebSocket, status

from super_rag.db.models import User
from super_rag.exceptions import BusinessException
from super_rag.schema import view_models
from super_rag.service.chat_collection_service import chat_collection_service
from super_rag.service.chat_document_service import chat_document_service
from super_rag.service.chat_service import chat_service_global
from super_rag.service.chat_title_service import chat_title_service
from super_rag.service.collection_service import collection_service
from super_rag.api.user import default_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chats"])


@router.post("/bots/{bot_id}/chats")
async def create_chat_view(request: Request, bot_id: str, user: User = Depends(default_user)) -> view_models.Chat:
    return await chat_service_global.create_chat(str(user.id), bot_id)


@router.get("/bots/{bot_id}/chats")
async def list_chats_view(
    request: Request,
    bot_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: User = Depends(default_user),
) -> view_models.ChatList:
    return await chat_service_global.list_chats(str(user.id), bot_id, page, page_size)


@router.get("/bots/{bot_id}/chats/{chat_id}")
async def get_chat_view(
    request: Request, bot_id: str, chat_id: str, user: User = Depends(default_user)
) -> view_models.ChatDetails:
    return await chat_service_global.get_chat(str(user.id), bot_id, chat_id)


@router.put("/bots/{bot_id}/chats/{chat_id}")
async def update_chat_view(
    request: Request,
    bot_id: str,
    chat_id: str,
    chat_in: view_models.ChatUpdate,
    user: User = Depends(default_user),
) -> view_models.Chat:
    return await chat_service_global.update_chat(str(user.id), bot_id, chat_id, chat_in)


@router.post("/bots/{bot_id}/chats/{chat_id}/messages/{message_id}")
async def feedback_message_view(
    request: Request,
    bot_id: str,
    chat_id: str,
    message_id: str,
    feedback: view_models.Feedback,
    user: User = Depends(default_user),
):
    return await chat_service_global.feedback_message(
        str(user.id), chat_id, message_id, feedback.type, feedback.tag, feedback.message
    )

# 优化 WebSocket 握手响应，确保接管和定制协议头部
@router.websocket("/bots/{bot_id}/chats/{chat_id}/connect")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    bot_id: str,
    chat_id: str,
    user: User = Depends(default_user),
    model_service_provider: str = None,
    model_name: str = None,
    custom_llm_provider: str = None,
):
    """
    WebSocket 端点，用于与机器人进行实时聊天。
    对协议头部和握手进行优化，提高兼容性和调试体验。
    """
    logger.info(f"WebSocket chat endpoint called with bot_id: {bot_id}, chat_id: {chat_id}, user: {user}")
    logger.info(f"WebSocket chat endpoint called with model_service_provider: {model_service_provider}, model_name: {model_name}, custom_llm_provider: {custom_llm_provider}")

    # 自定义协议升级响应头部(兼容调试、扩展)
    await websocket.accept(
        headers=[
            (b"Sec-WebSocket-Extensions", b"permessage-deflate"),
            (b"Server", b"uvicorn"),
        ]
    )
    logger.debug("WebSocket handshake: 协议升级和扩展头部已设置。")

    # 继续进入业务处理
    await chat_service_global.handle_websocket_chat(
        websocket,
        str(user.id),
        bot_id,
        chat_id,
        model_service_provider,
        model_name,
        custom_llm_provider
    )


@router.post("/bots/{bot_id}/chats/{chat_id}/title")
async def generate_chat_title_view(
    bot_id: str,
    chat_id: str,
    request_body: view_models.TitleGenerateRequest = view_models.TitleGenerateRequest(),
    user: User = Depends(default_user),
) -> view_models.TitleGenerateResponse:
    try:
        title = await chat_title_service.generate_title(
            user_id=str(user.id),
            bot_id=bot_id,
            chat_id=chat_id,
            max_length=request_body.max_length,
            language=request_body.language,
            turns=request_body.turns,
        )
        return {"title": title}
    except BusinessException as be:
        raise HTTPException(status_code=400, detail={"error_code": be.error_code.name, "message": str(be)})


@router.post("/chat/completions/frontend", tags=["chats"])
async def frontend_chat_completions_view(request: Request, user: User = Depends(default_user)):
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
    bot_id = query_params.get("bot_id", "")
    chat_id = query_params.get("chat_id", "")
    msg_id = request.headers.get("msg_id", "")
    model_service_provider = query_params.get("model_service_provider", "")
    model_name = query_params.get("model_name", "")
    custom_llm_provider = query_params.get("custom_llm_provider", "")
    return await chat_service_global.frontend_chat_completions(
        str(user.id), 
        message, 
        stream, 
        bot_id, 
        chat_id, 
        msg_id, 
        files,
        model_service_provider,
        model_name,
        custom_llm_provider
    )


@router.post("/chats/{chat_id}/search")
async def search_chat_files_view(
    request: Request,
    chat_id: str,
    data: view_models.SearchRequest,
    user: User = Depends(default_user),
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
    user: User = Depends(default_user),
) -> view_models.Document:
    """Upload a document to a chat session"""
    return await chat_document_service.upload_chat_document(chat_id=chat_id, user_id=str(user.id), file=file)


@router.get("/chats/{chat_id}/documents/{document_id}")
async def get_chat_document_view(
    request: Request,
    chat_id: str,
    document_id: str,
    user: User = Depends(default_user),
) -> view_models.Document:
    """Get chat document details"""
    document = await chat_document_service.get_chat_document_by_id(
        chat_id=chat_id, document_id=document_id, user_id=str(user.id)
    )

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    return document


@router.delete("/bots/{bot_id}/chats/{chat_id}")
async def delete_chat_view(request: Request, bot_id: str, chat_id: str, user: User = Depends(default_user)):
    await chat_service_global.delete_chat(str(user.id), bot_id, chat_id)
    return Response(status_code=204)
