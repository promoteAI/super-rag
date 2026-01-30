import logging

from fastapi import APIRouter, Depends, Request, Response

from super_rag.api.user import default_user
from super_rag.db.models import User
from super_rag.schema import view_models
from super_rag.service.agent_service import agent_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agents"])


@router.post("/agents")
async def create_agent_view(
    request: Request,
    agent_in: view_models.AgentCreate,
    user: User = Depends(default_user),
) -> view_models.AgentRecord:
    return await agent_service.create_agent(str(user.id), agent_in)


@router.get("/agents")
async def list_agents_view(request: Request, user: User = Depends(default_user)) -> view_models.AgentList:
    return await agent_service.list_agents(str(user.id))


@router.get("/agents/{agent_id}")
async def get_agent_view(request: Request, agent_id: str, user: User = Depends(default_user)) -> view_models.AgentRecord:
    return await agent_service.get_agent(str(user.id), agent_id)


@router.put("/agents/{agent_id}")
async def update_agent_view(
    request: Request,
    agent_id: str,
    agent_in: view_models.AgentUpdate,
    user: User = Depends(default_user),
) -> view_models.AgentRecord:
    return await agent_service.update_agent(str(user.id), agent_id, agent_in)


@router.delete("/agents/{agent_id}")
async def delete_agent_view(request: Request, agent_id: str, user: User = Depends(default_user)):
    await agent_service.delete_agent(str(user.id), agent_id)
    return Response(status_code=204)
