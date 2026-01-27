import logging

from fastapi import APIRouter, Depends, Request

from super_rag.db.models import User
from super_rag.schema import view_models
from super_rag.service.flow_service import flow_service_global
from super_rag.api.user import default_user


logger = logging.getLogger(__name__)

router = APIRouter(tags=["workflows"])


@router.post("/workflows/run", response_model=view_models.WorkflowRunResponse)
async def run_workflow_once_view(
    request: Request,
    body: view_models.WorkflowRunRequest,
    user: User = Depends(default_user),
) -> view_models.WorkflowRunResponse:
    """
    直接运行一次 WorkflowDefinition（不持久化），用于前端编排器的「运行」按钮。
    """
    return await flow_service_global.run_workflow_once(str(user.id), body)

