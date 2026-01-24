
import logging

from fastapi import APIRouter, Depends, Request, Response

from super_rag.db.models import User
from super_rag.schema import view_models
from super_rag.service.bot_service import bot_service
from super_rag.service.flow_service import flow_service_global
from super_rag.api.user import default_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["bots"])


@router.post("/bots")
async def create_bot_view(
    request: Request,
    bot_in: view_models.BotCreate,
    user: User = Depends(default_user),
) -> view_models.Bot:
    return await bot_service.create_bot(str(user.id), bot_in)


@router.get("/bots")
async def list_bots_view(request: Request, user: User = Depends(default_user)) -> view_models.BotList:
    return await bot_service.list_bots(str(user.id))


@router.get("/bots/{bot_id}")
async def get_bot_view(request: Request, bot_id: str, user: User = Depends(default_user)) -> view_models.Bot:
    return await bot_service.get_bot(str(user.id), bot_id)


@router.put("/bots/{bot_id}")
async def update_bot_view(
    request: Request,
    bot_id: str,
    bot_in: view_models.BotUpdate,
    user: User = Depends(default_user),
) -> view_models.Bot:
    return await bot_service.update_bot(str(user.id), bot_id, bot_in)


@router.delete("/bots/{bot_id}")
async def delete_bot_view(request: Request, bot_id: str, user: User = Depends(default_user)):
    await bot_service.delete_bot(str(user.id), bot_id)
    return Response(status_code=204)


@router.post("/bots/{bot_id}/flow/debug", tags=["flows"])
async def debug_flow_stream_view(
    request: Request,
    bot_id: str,
    debug: view_models.DebugFlowRequest,
    user: User = Depends(default_user),
):
    return await flow_service_global.debug_flow_stream(str(user.id), bot_id, debug)
